"""
Authentication Router
Handles user authentication, OAuth flows, and session management
"""
import logging
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse

from tools_gateway import oauth_provider_manager, jwt_manager, UserInfo
from tools_gateway import rbac_manager
from tools_gateway import audit_logger, AuditEventType, AuditSeverity
from tools_gateway import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/welcome")
async def auth_welcome():
    """Welcome page with OAuth login options"""
    return FileResponse("static/index.html")


@router.get("/providers")
async def list_oauth_providers():
    """List available OAuth providers"""
    providers = oauth_provider_manager.list_providers()
    return JSONResponse(content={"providers": providers})


@router.get("/providers/{provider_id}/details")
async def get_oauth_provider_details(provider_id: str):
    """Get OAuth provider configuration details with masked secrets"""
    provider = oauth_provider_manager.get_provider(provider_id)

    if not provider:
        raise HTTPException(status_code=404, detail="OAuth provider not found")

    # Return provider details with masked client secret
    provider_details = {
        "provider_id": provider.provider_id,
        "provider_name": provider.provider_name,
        "client_id": provider.client_id,
        "client_secret": "•" * 20 + provider.client_secret[-4:] if len(provider.client_secret) > 4 else "••••",
        "authorize_url": provider.authorize_url,
        "token_url": provider.token_url,
        "userinfo_url": provider.userinfo_url,
        "scopes": provider.scopes,
        "enabled": provider.enabled
    }

    return JSONResponse(content=provider_details)


@router.post("/login/local")
async def local_login(request: Request, request_data: Dict[str, Any]):
    """Local authentication with email and password"""
    email = request_data.get("email")
    password = request_data.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    # Authenticate user
    user = rbac_manager.authenticate_local_user(email, password)

    if not user:
        audit_logger.log_event(
            AuditEventType.AUTH_LOGIN_FAILURE,
            severity=AuditSeverity.WARNING,
            user_email=email,
            ip_address=request.client.host if request.client else None,
            details={"provider": "local", "reason": "invalid_credentials"},
            success=False
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create UserInfo for JWT
    user_info = UserInfo(
        sub=user.user_id,
        email=user.email,
        name=user.name,
        provider="local",
        raw_data={}
    )

    # Create JWT access token
    access_token = jwt_manager.create_access_token(user_info)

    audit_logger.log_event(
        AuditEventType.AUTH_LOGIN_SUCCESS,
        user_id=user.user_id,
        user_email=user.email,
        ip_address=request.client.host if request.client else None,
        details={"provider": "local"}
    )

    return JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "name": user.name,
            "roles": [rbac_manager.get_role(rid).role_name for rid in user.roles if rbac_manager.get_role(rid)]
        }
    })


@router.post("/login")
async def oauth_login(request: Request, provider_id: str):
    """Initiate OAuth login flow"""
    # Build redirect URI
    base_url = str(request.base_url).rstrip('/')
    redirect_uri = f"{base_url}/auth/callback"

    auth_data = oauth_provider_manager.create_authorization_url(provider_id, redirect_uri)

    if not auth_data:
        raise HTTPException(status_code=404, detail="OAuth provider not found")

    audit_logger.log_event(
        AuditEventType.AUTH_LOGIN_SUCCESS,
        ip_address=request.client.host if request.client else None,
        details={"provider": provider_id, "step": "initiated"}
    )

    return JSONResponse(content=auth_data)


@router.get("/callback")
async def oauth_callback(request: Request, code: str, state: str):
    """Handle OAuth callback"""
    try:
        logger.info(f"OAuth callback received - code: {code[:20]}..., state: {state[:20]}...")

        # Exchange code for token
        result = await oauth_provider_manager.exchange_code_for_token(code, state)
        if not result:
            logger.error("Failed to exchange authorization code")
            raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

        oauth_token, provider_id = result
        logger.info(f"Token exchange successful for provider: {provider_id}")

        # Get user info from provider
        user_info = await oauth_provider_manager.get_user_info(provider_id, oauth_token.access_token)
        if not user_info:
            logger.error("Failed to retrieve user information from provider")
            raise HTTPException(status_code=400, detail="Failed to retrieve user information")

        logger.info(f"User info retrieved: email={user_info.email}, name={user_info.name}")

        # Validate email exists
        if not user_info.email:
            logger.error("User email is missing from OAuth provider response")
            raise HTTPException(status_code=400, detail="Email not provided by OAuth provider")

        # Get or create user in RBAC system
        user = rbac_manager.get_or_create_user(
            email=user_info.email,
            name=user_info.name,
            provider=provider_id
        )
        logger.info(f"User created/retrieved: user_id={user.user_id}, email={user.email}, roles={user.roles}")

        # Create JWT access token for MCP gateway
        access_token = jwt_manager.create_access_token(user_info)
        logger.info(f"JWT token created for user: {user.email}")

        audit_logger.log_event(
            AuditEventType.AUTH_LOGIN_SUCCESS,
            user_id=user.user_id,
            user_email=user.email,
            ip_address=request.client.host if request.client else None,
            details={"provider": provider_id}
        )

        # Redirect to portal with token
        redirect_url = f"/?token={access_token}"
        logger.info(f"Redirecting to: {redirect_url[:50]}...")
        return RedirectResponse(url=redirect_url)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"OAuth callback error: {e}\n{error_details}")
        audit_logger.log_event(
            AuditEventType.AUTH_LOGIN_FAILURE,
            severity=AuditSeverity.ERROR,
            ip_address=request.client.host if request.client else None,
            details={"error": str(e), "traceback": error_details},
            success=False
        )
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@router.get("/user")
async def get_current_user_info(request: Request):
    """Get current authenticated user info"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    permissions = rbac_manager.get_user_permissions(user.user_id)

    return JSONResponse(content={
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
        "roles": [rbac_manager.get_role(rid).role_name for rid in user.roles if rbac_manager.get_role(rid)],
        "permissions": [p.value for p in permissions],
        "enabled": user.enabled
    })


@router.post("/logout")
async def logout(request: Request):
    """Logout user"""
    user = get_current_user(request)
    if user:
        audit_logger.log_event(
            AuditEventType.AUTH_LOGOUT,
            user_id=user.user_id,
            user_email=user.email,
            ip_address=request.client.host if request.client else None
        )

    return JSONResponse(content={"message": "Logged out successfully"})

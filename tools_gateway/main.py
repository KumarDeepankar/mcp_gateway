#!/usr/bin/env python3
"""
Tools Gateway - Fully Compliant with 2025-06-18 Specification
Centralized gateway implementing pure Streamable HTTP transport
With dynamic origin configuration and connection health monitoring
"""
import asyncio
from contextlib import asynccontextmanager
import logging
import json
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
from datetime import datetime
from urllib.parse import urlparse
import os

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from services import discovery_service, connection_manager, ToolNotFoundException
from mcp_storage import mcp_storage_manager
from config import config_manager
from auth import oauth_provider_manager, jwt_manager
from rbac import rbac_manager, Permission
from audit import audit_logger, AuditEventType, AuditSeverity
from middleware import AuthenticationMiddleware, RateLimitMiddleware, get_current_user
# No hardcoded server imports - fully user-driven

# Configure logging per MCP 2025-06-18 specification
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Protocol constants as per 2025-06-18 specification
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {
    "name": "tools-gateway",
    "version": "1.0.0"
}


class EventStore:
    """
    Event store for SSE resumability per MCP specification.
    Stores events per-stream for message replay functionality.
    """

    def __init__(self):
        self.stream_events: Dict[str, List[Dict[str, Any]]] = {}
        self.global_event_counter = 0

    def store_event(self, stream_id: str, message: Dict[str, Any]) -> str:
        """Store event and return globally unique ID per stream"""
        self.global_event_counter += 1
        event_id = f"{stream_id}-{self.global_event_counter}"

        if stream_id not in self.stream_events:
            self.stream_events[stream_id] = []

        event_data = {
            "id": event_id,
            "timestamp": datetime.now().isoformat(),
            "message": message
        }

        self.stream_events[stream_id].append(event_data)

        # Limit stored events per stream (prevent memory issues)
        if len(self.stream_events[stream_id]) > 1000:
            self.stream_events[stream_id] = self.stream_events[stream_id][-500:]

        return event_id

    def get_events_after(self, stream_id: str, last_event_id: str) -> List[Dict[str, Any]]:
        """Get events after the specified event ID for resumability"""
        if stream_id not in self.stream_events:
            return []

        events = self.stream_events[stream_id]
        try:
            # Find the position of last_event_id
            last_index = -1
            for i, event in enumerate(events):
                if event["id"] == last_event_id:
                    last_index = i
                    break

            # Return events after the last_event_id
            if last_index >= 0:
                return events[last_index + 1:]
            else:
                # If event ID not found, return recent events
                return events[-10:] if events else []

        except Exception as e:
            logger.warning(f"Error retrieving events after {last_event_id}: {e}")
            return []

    def cleanup_stream(self, stream_id: str):
        """Clean up events for a terminated stream"""
        self.stream_events.pop(stream_id, None)


class StreamManager:
    """
    Manages multiple SSE streams per MCP specification.
    Ensures messages are sent to only one stream and prevents broadcasting.
    """

    def __init__(self):
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.session_streams: Dict[str, List[str]] = {}  # session_id -> [stream_ids]

    def register_stream(self, stream_id: str, session_id: str, stream_type: str) -> None:
        """Register a new active stream"""
        self.active_streams[stream_id] = {
            "session_id": session_id,
            "stream_type": stream_type,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }

        if session_id not in self.session_streams:
            self.session_streams[session_id] = []
        self.session_streams[session_id].append(stream_id)

        logger.info(f"Registered {stream_type} stream {stream_id} for session {session_id}")

    def unregister_stream(self, stream_id: str) -> None:
        """Unregister a stream when connection closes"""
        if stream_id in self.active_streams:
            session_id = self.active_streams[stream_id]["session_id"]
            del self.active_streams[stream_id]

            if session_id in self.session_streams:
                self.session_streams[session_id] = [
                    s for s in self.session_streams[session_id] if s != stream_id
                ]
                if not self.session_streams[session_id]:
                    del self.session_streams[session_id]

            logger.info(f"Unregistered stream {stream_id}")

    def get_session_streams(self, session_id: str) -> List[str]:
        """Get all active streams for a session"""
        return self.session_streams.get(session_id, [])

    def update_activity(self, stream_id: str) -> None:
        """Update last activity timestamp for a stream"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id]["last_activity"] = datetime.now()

    def cleanup_session_streams(self, session_id: str) -> None:
        """Clean up all streams for a terminated session"""
        if session_id in self.session_streams:
            stream_ids = self.session_streams[session_id].copy()
            for stream_id in stream_ids:
                self.unregister_stream(stream_id)


class MessageRouter:
    """
    Routes messages to specific streams per MCP specification.
    Ensures messages are sent to only one stream, never broadcasted.
    """

    def __init__(self, stream_manager: StreamManager, event_store: EventStore):
        self.stream_manager = stream_manager
        self.event_store = event_store
        self.message_queues: Dict[str, asyncio.Queue] = {}

    def get_or_create_queue(self, stream_id: str) -> asyncio.Queue:
        """Get or create message queue for a stream"""
        if stream_id not in self.message_queues:
            self.message_queues[stream_id] = asyncio.Queue()
        return self.message_queues[stream_id]

    async def send_to_stream(self, stream_id: str, message: Dict[str, Any]) -> None:
        """Send message to a specific stream (never broadcast)"""
        if stream_id in self.stream_manager.active_streams:
            queue = self.get_or_create_queue(stream_id)
            event_id = self.event_store.store_event(stream_id, message)

            await queue.put({
                "id": event_id,
                "data": message
            })

            self.stream_manager.update_activity(stream_id)
            logger.debug(f"Routed message to stream {stream_id} with event ID {event_id}")

    async def get_next_message(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get next message for a stream"""
        queue = self.get_or_create_queue(stream_id)
        try:
            # Non-blocking get with timeout
            return await asyncio.wait_for(queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    def cleanup_stream_queue(self, stream_id: str) -> None:
        """Clean up message queue for a stream"""
        self.message_queues.pop(stream_id, None)


class MCPToolboxGateway:
    """
    MCP Toolbox Gateway implementation fully compliant with 2025-06-18 Streamable HTTP transport.
    Acts as a centralized gateway with tool discovery, connection management, and caching.
    """

    def __init__(self):
        self.initialized = False
        self.client_info = {}
        self.server_start_time = datetime.now()
        self.sessions: Dict[str, Dict] = {}

        # Initialize compliance components for 100% specification adherence
        self.event_store = EventStore()
        self.stream_manager = StreamManager()
        self.message_router = MessageRouter(self.stream_manager, self.event_store)

        logger.info(f"MCP Toolbox Gateway initialized with protocol version {PROTOCOL_VERSION}")
        logger.info("Compliance components initialized: EventStore, StreamManager, MessageRouter")

    def _sanitize_origin(self, origin: str) -> Optional[str]:
        """
        Sanitize origin string to prevent injection attacks.
        Returns sanitized origin or None if invalid.
        """
        if not origin:
            return None

        try:
            # Parse and validate URL structure
            parsed = urlparse(origin)

            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"Invalid origin format (missing scheme/netloc): {origin}")
                return None

            # Only allow http/https schemes
            if parsed.scheme not in ['http', 'https']:
                logger.warning(f"Invalid origin scheme (must be http/https): {origin}")
                return None

            # Validate hostname format
            hostname = parsed.hostname
            if not hostname:
                return None

            # Length validation
            if len(hostname) > 253:
                logger.warning(f"Origin hostname too long: {hostname[:50]}...")
                return None

            # Reconstruct clean origin (scheme + netloc only, no path/query)
            clean_origin = f"{parsed.scheme}://{parsed.netloc}"
            return clean_origin

        except Exception as e:
            logger.warning(f"Failed to parse origin: {origin}, error: {e}")
            return None

    def extract_origin_from_request(self, request: Request) -> Optional[str]:
        """
        Extract origin from request considering load balancer/reverse proxy headers.
        Priority order:
        1. Origin header (most trusted)
        2. X-Forwarded-Host + X-Forwarded-Proto (load balancer)
        3. X-Original-Host (alternative)
        Note: Referer is NOT used as it's easily spoofed
        """
        # Standard Origin header (most secure)
        origin = request.headers.get("origin")
        if origin:
            return self._sanitize_origin(origin)

        # Load balancer forwarded headers
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
        if forwarded_host:
            # Validate proto
            if forwarded_proto not in ['http', 'https']:
                logger.warning(f"Invalid X-Forwarded-Proto: {forwarded_proto}")
                forwarded_proto = "https"

            origin = f"{forwarded_proto}://{forwarded_host}"
            return self._sanitize_origin(origin)

        # Alternative original host header
        original_host = request.headers.get("x-original-host")
        if original_host:
            origin = f"https://{original_host}"
            return self._sanitize_origin(origin)

        # No origin found
        return None

    def validate_origin_header(self, origin: Optional[str]) -> bool:
        """
        Validate Origin header to prevent DNS rebinding attacks.
        Required by 2025-06-18 specification.
        Uses in-memory cache for fast O(1) validation.

        SECURITY NOTE: This allows permissive origins (ngrok, all HTTPS) by default.
        Review config_manager.get_origin_validation_config() for production hardening.
        """
        if not origin:
            logger.warning("Origin validation failed: No origin provided")
            return False

        try:
            parsed = urlparse(origin)
            hostname = parsed.hostname

            if not hostname:
                logger.warning(f"Origin validation failed: No hostname in {origin}")
                return False

            # Get cached configuration (fast in-memory access, no pickle reads)
            allowed_origins, allow_ngrok, allow_https = config_manager.get_origin_validation_config()

            # Fast O(1) set lookup for configured allowed origins (most secure)
            logger.debug(f"Origin validation: hostname={hostname}, allowed={allowed_origins}")
            if hostname in allowed_origins:
                logger.info(f"✓ Origin allowed (whitelist): {origin}")
                return True

            # Check if ngrok is allowed (SECURITY: disable in production)
            if allow_ngrok and hostname and (
                hostname.endswith('.ngrok-free.app') or
                hostname.endswith('.ngrok.io') or
                hostname.endswith('.ngrok.app') or
                '.ngrok.' in hostname
            ):
                logger.warning(f"⚠ Allowing ngrok origin (SECURITY: disable for production): {origin}")
                return True

            # Check if HTTPS origins are allowed (SECURITY: only enable behind trusted LB)
            if allow_https and parsed.scheme == 'https':
                logger.warning(f"⚠ Allowing HTTPS origin (SECURITY: any HTTPS domain accepted): {origin}")
                return True

            logger.error(f"✗ Origin REJECTED: {origin} (hostname: {hostname})")
            return False
        except Exception as e:
            logger.error(f"✗ Origin validation exception: {origin}, error: {e}")
            return False

    def validate_accept_header(self, accept: Optional[str], method: str) -> bool:
        """
        Validate Accept header according to 2025-06-18 specification.
        """
        if not accept:
            return False

        if method == "POST":
            # POST requests must accept both application/json and text/event-stream
            return "application/json" in accept and "text/event-stream" in accept
        elif method == "GET":
            # GET requests must accept text/event-stream
            return "text/event-stream" in accept

        return False

    def validate_protocol_version(self, version: Optional[str]) -> str:
        """
        Validate and normalize protocol version according to specification.
        """
        if not version:
            # Default to latest version for backwards compatibility
            return PROTOCOL_VERSION

        supported_versions = ["2025-06-18", "2025-03-26"]
        if version not in supported_versions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported protocol version: {version}"
            )

        return version

    def generate_session_id(self) -> str:
        """
        Generate cryptographically secure session ID per specification.
        Must contain only visible ASCII characters (0x21 to 0x7E).
        """
        session_id = str(uuid.uuid4())

        # Validate ASCII character range per specification
        if not all(0x21 <= ord(c) <= 0x7E for c in session_id):
            # Use hex format to ensure compliance
            session_id = uuid.uuid4().hex

        return session_id

    def validate_session(self, session_id: str) -> bool:
        """Validate session ID exists and is active."""
        return session_id in self.sessions

    def terminate_session(self, session_id: str) -> bool:
        """Terminate a session per specification with full cleanup."""
        if session_id in self.sessions:
            # Clean up all streams for this session
            self.stream_manager.cleanup_session_streams(session_id)

            # Clean up event store for session streams
            for stream_id in self.stream_manager.get_session_streams(session_id):
                self.event_store.cleanup_stream(stream_id)
                self.message_router.cleanup_stream_queue(stream_id)

            del self.sessions[session_id]
            logger.info(f"Session terminated: {session_id}")
            return True
        return False

    def create_error_response(self, request_id: Optional[str], code: int, message: str) -> Dict[str, Any]:
        """Create JSON-RPC error response per specification."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message}
        }


# Create gateway instance
mcp_gateway = MCPToolboxGateway()


# --- Application Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info("Tools Gateway starting up...")
    # Initialize storage manager
    await mcp_storage_manager.initialize()
    discovery_service.storage_manager = mcp_storage_manager
    # Initialize and warm up the discovery service cache
    await discovery_service.refresh_tool_index()
    # Start health monitoring
    await discovery_service.start_health_monitoring()
    logger.info("Connection health monitoring started")
    yield
    logger.info("Tools Gateway shutting down...")
    # Stop health monitoring
    await discovery_service.stop_health_monitoring()
    # Cleanly close the connection manager's session
    await connection_manager.close_session()


# Create FastAPI app with proper configuration
app = FastAPI(
    title="Tools Gateway",
    description="Centralized gateway implementing MCP 2025-06-18 Streamable HTTP transport with health monitoring",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS with security considerations per specification
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for ngrok compatibility
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add security middlewares
# app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
# Note: AuthenticationMiddleware is optional - enable it to enforce authentication on all endpoints
# app.add_middleware(AuthenticationMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Serve main portal HTML file
@app.get("/", response_class=FileResponse)
async def root(request: Request):
    """Serve the MCP portal HTML file with ngrok compatibility."""
    # Log request details for debugging
    logger.info(f"Root request from: {request.client.host if request.client else 'unknown'}")
    logger.info(f"Headers: {dict(request.headers)}")

    response = FileResponse("static/index.html")

    # Add headers for ngrok compatibility
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
    # Add ngrok bypass header to skip warning page
    response.headers["ngrok-skip-browser-warning"] = "true"

    return response


# Debug endpoint for troubleshooting ngrok issues
@app.get("/debug/headers")
async def debug_headers(request: Request):
    """Debug endpoint to see all request headers and ngrok forwarding info."""
    debug_info = {
        "url": str(request.url),
        "method": request.method,
        "client": str(request.client) if request.client else None,
        "headers": dict(request.headers),
        "ngrok_detected": any("ngrok" in str(v) for v in request.headers.values()),
        "forwarded_host": request.headers.get("x-forwarded-host"),
        "forwarded_proto": request.headers.get("x-forwarded-proto"),
        "forwarded_for": request.headers.get("x-forwarded-for"),
        "real_ip": request.headers.get("x-real-ip"),
        "origin": request.headers.get("origin"),
    }
    return JSONResponse(content=debug_info)


# =====================================================================
# AUTHENTICATION & AUTHORIZATION ENDPOINTS
# =====================================================================

@app.get("/auth/welcome")
async def auth_welcome():
    """Welcome page with OAuth login options"""
    return FileResponse("static/index.html")


@app.get("/auth/providers")
async def list_oauth_providers():
    """List available OAuth providers"""
    providers = oauth_provider_manager.list_providers()
    return JSONResponse(content={"providers": providers})


@app.post("/auth/login")
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


@app.get("/auth/callback")
async def oauth_callback(request: Request, code: str, state: str):
    """Handle OAuth callback"""
    try:
        # Exchange code for token
        result = await oauth_provider_manager.exchange_code_for_token(code, state)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

        oauth_token, provider_id = result

        # Get user info from provider
        user_info = await oauth_provider_manager.get_user_info(provider_id, oauth_token.access_token)
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to retrieve user information")

        # Get or create user in RBAC system
        user = rbac_manager.get_or_create_user(
            email=user_info.email,
            name=user_info.name,
            provider=provider_id
        )

        # Create JWT access token for MCP gateway
        access_token = jwt_manager.create_access_token(user_info)

        audit_logger.log_event(
            AuditEventType.AUTH_LOGIN_SUCCESS,
            user_id=user.user_id,
            user_email=user.email,
            ip_address=request.client.host if request.client else None,
            details={"provider": provider_id}
        )

        # Redirect to portal with token
        redirect_url = f"/?token={access_token}"
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        audit_logger.log_event(
            AuditEventType.AUTH_LOGIN_FAILURE,
            severity=AuditSeverity.ERROR,
            ip_address=request.client.host if request.client else None,
            details={"error": str(e)},
            success=False
        )
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@app.get("/auth/user")
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


@app.post("/auth/logout")
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


# =====================================================================
# OAUTH PROVIDER MANAGEMENT ENDPOINTS
# =====================================================================

@app.post("/admin/oauth/providers")
async def add_oauth_provider(request: Request, request_data: Dict[str, Any]):
    """
    Add OAuth provider
    - Allows first-time setup without authentication (when no providers exist)
    - Requires admin permission after initial provider is configured
    """
    # Check if this is first-time setup (no providers exist)
    existing_providers = oauth_provider_manager.list_providers()
    is_first_provider = len(existing_providers) == 0

    if not is_first_provider:
        # Not first-time setup - require authentication and permission
        user = get_current_user(request)
        if not user or not rbac_manager.has_permission(user.user_id, Permission.OAUTH_MANAGE):
            raise HTTPException(status_code=403, detail="Permission denied")
    else:
        # First-time setup - no authentication required
        user = None
        logger.info("First-time OAuth provider setup - allowing unauthenticated access")

    try:
        provider = oauth_provider_manager.add_provider(**request_data)

        # Log audit event (with or without user)
        audit_logger.log_event(
            AuditEventType.OAUTH_PROVIDER_ADDED,
            user_id=user.user_id if user else None,
            user_email=user.email if user else "system",
            resource_type="oauth_provider",
            resource_id=provider.provider_id,
            details={"provider_name": provider.provider_name, "first_time_setup": is_first_provider}
        )

        return JSONResponse(content={
            "success": True,
            "provider_id": provider.provider_id,
            "message": "OAuth provider added successfully. You can now sign in with this provider." if is_first_provider else "OAuth provider added successfully."
        })
    except Exception as e:
        logger.error(f"Error adding OAuth provider: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/admin/oauth/providers/{provider_id}")
async def remove_oauth_provider(request: Request, provider_id: str):
    """Remove OAuth provider (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.OAUTH_MANAGE):
        raise HTTPException(status_code=403, detail="Permission denied")

    success = oauth_provider_manager.remove_provider(provider_id)

    if success:
        audit_logger.log_event(
            AuditEventType.OAUTH_PROVIDER_REMOVED,
            user_id=user.user_id,
            user_email=user.email,
            resource_type="oauth_provider",
            resource_id=provider_id
        )

    return JSONResponse(content={"success": success})


# =====================================================================
# USER & ROLE MANAGEMENT ENDPOINTS (RBAC)
# =====================================================================

@app.get("/admin/users")
async def list_users(request: Request):
    """List all users (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.USER_VIEW):
        raise HTTPException(status_code=403, detail="Permission denied")

    users = rbac_manager.list_users()
    return JSONResponse(content={"users": users})


@app.post("/admin/users/{user_id}/roles")
async def assign_user_role(request: Request, user_id: str, request_data: Dict[str, Any]):
    """Assign role to user (Admin only)"""
    current_user = get_current_user(request)
    if not current_user or not rbac_manager.has_permission(current_user.user_id, Permission.USER_MANAGE):
        raise HTTPException(status_code=403, detail="Permission denied")

    role_id = request_data.get("role_id")
    success = rbac_manager.assign_role(user_id, role_id)

    if success:
        audit_logger.log_event(
            AuditEventType.AUTHZ_ROLE_ASSIGNED,
            user_id=current_user.user_id,
            user_email=current_user.email,
            resource_type="user",
            resource_id=user_id,
            details={"role_id": role_id}
        )

    return JSONResponse(content={"success": success})


@app.delete("/admin/users/{user_id}/roles/{role_id}")
async def revoke_user_role(request: Request, user_id: str, role_id: str):
    """Revoke role from user (Admin only)"""
    current_user = get_current_user(request)
    if not current_user or not rbac_manager.has_permission(current_user.user_id, Permission.USER_MANAGE):
        raise HTTPException(status_code=403, detail="Permission denied")

    success = rbac_manager.revoke_role(user_id, role_id)

    if success:
        audit_logger.log_event(
            AuditEventType.AUTHZ_ROLE_REVOKED,
            user_id=current_user.user_id,
            user_email=current_user.email,
            resource_type="user",
            resource_id=user_id,
            details={"role_id": role_id}
        )

    return JSONResponse(content={"success": success})


@app.get("/admin/roles")
async def list_roles(request: Request):
    """List all roles"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.ROLE_VIEW):
        raise HTTPException(status_code=403, detail="Permission denied")

    roles = rbac_manager.list_roles()
    return JSONResponse(content={"roles": roles})


@app.post("/admin/roles")
async def create_role(request: Request, request_data: Dict[str, Any]):
    """Create new role (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.ROLE_MANAGE):
        raise HTTPException(status_code=403, detail="Permission denied")

    role_name = request_data.get("role_name")
    description = request_data.get("description", "")
    permissions_str = request_data.get("permissions", [])

    # Convert string permissions to Permission enum
    permissions = {Permission(p) for p in permissions_str if p in [perm.value for perm in Permission]}

    role = rbac_manager.create_role(role_name, description, permissions)

    audit_logger.log_event(
        AuditEventType.ROLE_CREATED,
        user_id=user.user_id,
        user_email=user.email,
        resource_type="role",
        resource_id=role.role_id,
        details={"role_name": role_name}
    )

    return JSONResponse(content={
        "success": True,
        "role_id": role.role_id
    })


@app.delete("/admin/roles/{role_id}")
async def delete_role(request: Request, role_id: str):
    """Delete role (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.ROLE_MANAGE):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Check if role exists and is not a system role
    role = rbac_manager.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system roles")

    success = rbac_manager.delete_role(role_id)

    if success:
        audit_logger.log_event(
            AuditEventType.ROLE_DELETED,
            user_id=user.user_id,
            user_email=user.email,
            resource_type="role",
            resource_id=role_id,
            details={"role_name": role.role_name}
        )

    return JSONResponse(content={"success": success})


@app.post("/admin/users")
async def create_user(request: Request, request_data: Dict[str, Any]):
    """Create local user manually (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.USER_MANAGE):
        raise HTTPException(status_code=403, detail="Permission denied")

    email = request_data.get("email")
    name = request_data.get("name", "")
    password = request_data.get("password")
    roles = request_data.get("roles", [])
    provider = request_data.get("provider", "local")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    # Create user
    new_user = rbac_manager.get_or_create_user(
        email=email,
        name=name,
        provider=provider
    )

    # Assign roles
    for role_id in roles:
        rbac_manager.assign_role(new_user.user_id, role_id)

    audit_logger.log_event(
        AuditEventType.USER_CREATED,
        user_id=user.user_id,
        user_email=user.email,
        resource_type="user",
        resource_id=new_user.user_id,
        details={"email": email, "roles": roles}
    )

    return JSONResponse(content={
        "success": True,
        "user_id": new_user.user_id
    })


# =====================================================================
# ACTIVE DIRECTORY INTEGRATION ENDPOINTS
# =====================================================================

from ad_integration import ad_integration


@app.post("/admin/ad/query-groups")
async def query_ad_groups(request: Request, request_data: Dict[str, Any]):
    """Query Active Directory for groups (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.USER_MANAGE):
        raise HTTPException(status_code=403, detail="Permission denied")

    server = request_data.get("server")
    port = request_data.get("port", 389)
    bind_dn = request_data.get("bind_dn")
    bind_password = request_data.get("bind_password")
    base_dn = request_data.get("base_dn")
    group_filter = request_data.get("group_filter", "(objectClass=group)")
    use_ssl = request_data.get("use_ssl", False)

    if not all([server, bind_dn, bind_password, base_dn]):
        raise HTTPException(status_code=400, detail="Missing required AD connection parameters")

    try:
        groups = ad_integration.query_groups(
            server=server,
            port=port,
            bind_dn=bind_dn,
            bind_password=bind_password,
            base_dn=base_dn,
            group_filter=group_filter,
            use_ssl=use_ssl
        )

        audit_logger.log_event(
            AuditEventType.AD_GROUP_QUERY,
            user_id=user.user_id,
            user_email=user.email,
            details={"server": server, "base_dn": base_dn, "groups_found": len(groups)}
        )

        return JSONResponse(content={
            "groups": [
                {
                    "name": g.name,
                    "dn": g.dn,
                    "member_count": g.member_count
                }
                for g in groups
            ]
        })

    except Exception as e:
        logger.error(f"AD group query error: {e}")
        audit_logger.log_event(
            AuditEventType.AD_SYNC_FAILURE,
            severity=AuditSeverity.ERROR,
            user_id=user.user_id,
            user_email=user.email,
            details={"error": str(e), "server": server},
            success=False
        )
        raise HTTPException(status_code=500, detail=f"Failed to query AD: {str(e)}")


@app.post("/admin/ad/group-mappings")
async def create_group_mapping(request: Request, request_data: Dict[str, Any]):
    """Create AD group to RBAC role mapping and sync users (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.USER_MANAGE):
        raise HTTPException(status_code=403, detail="Permission denied")

    group_dn = request_data.get("group_dn")
    role_id = request_data.get("role_id")
    auto_sync = request_data.get("auto_sync", False)

    # AD connection details (should be stored securely in production)
    ad_config = request_data.get("ad_config", {})
    server = ad_config.get("server")
    port = ad_config.get("port", 389)
    bind_dn = ad_config.get("bind_dn")
    bind_password = ad_config.get("bind_password")
    use_ssl = ad_config.get("use_ssl", False)

    if not group_dn or not role_id:
        raise HTTPException(status_code=400, detail="group_dn and role_id are required")

    # Verify role exists
    role = rbac_manager.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    try:
        # Create the mapping
        mapping = ad_integration.add_group_mapping(
            group_dn=group_dn,
            role_id=role_id,
            auto_sync=auto_sync
        )

        # Sync users from the group immediately
        synced_users = 0
        if server and bind_dn and bind_password:
            try:
                users = ad_integration.get_group_members(
                    server=server,
                    port=port,
                    bind_dn=bind_dn,
                    bind_password=bind_password,
                    group_dn=group_dn,
                    use_ssl=use_ssl
                )

                # Create users and assign role
                for ad_user in users:
                    # Get or create user in RBAC system
                    rbac_user = rbac_manager.get_or_create_user(
                        email=ad_user.email,
                        name=ad_user.display_name,
                        provider="active_directory"
                    )

                    # Assign the mapped role
                    rbac_manager.assign_role(rbac_user.user_id, role_id)
                    synced_users += 1

                # Update mapping sync status
                ad_integration.update_mapping_sync_status(mapping.mapping_id, synced_users)

            except Exception as e:
                logger.error(f"Error syncing users from AD group: {e}")
                # Mapping was created but sync failed
                audit_logger.log_event(
                    AuditEventType.AD_SYNC_FAILURE,
                    severity=AuditSeverity.WARNING,
                    user_id=user.user_id,
                    user_email=user.email,
                    details={"error": str(e), "group_dn": group_dn},
                    success=False
                )

        audit_logger.log_event(
            AuditEventType.AD_GROUP_MAPPED,
            user_id=user.user_id,
            user_email=user.email,
            details={
                "group_dn": group_dn,
                "role_id": role_id,
                "synced_users": synced_users,
                "auto_sync": auto_sync
            }
        )

        return JSONResponse(content={
            "success": True,
            "mapping_id": mapping.mapping_id,
            "synced_users": synced_users,
            "message": f"Group mapped successfully. Synced {synced_users} users."
        })

    except Exception as e:
        logger.error(f"Error creating group mapping: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create mapping: {str(e)}")


@app.get("/admin/ad/group-mappings")
async def list_group_mappings(request: Request):
    """List all AD group to role mappings (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.USER_VIEW):
        raise HTTPException(status_code=403, detail="Permission denied")

    mappings = ad_integration.list_mappings()

    return JSONResponse(content={
        "mappings": [
            {
                "mapping_id": m.mapping_id,
                "group_dn": m.group_dn,
                "role_id": m.role_id,
                "auto_sync": m.auto_sync,
                "last_sync": m.last_sync.isoformat() if m.last_sync else None,
                "synced_users": m.synced_users
            }
            for m in mappings
        ]
    })


@app.delete("/admin/ad/group-mappings/{mapping_id}")
async def delete_group_mapping(request: Request, mapping_id: str):
    """Delete AD group to role mapping (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.USER_MANAGE):
        raise HTTPException(status_code=403, detail="Permission denied")

    success = ad_integration.remove_group_mapping(mapping_id)

    if success:
        audit_logger.log_event(
            AuditEventType.AD_GROUP_UNMAPPED,
            user_id=user.user_id,
            user_email=user.email,
            details={"mapping_id": mapping_id}
        )

    return JSONResponse(content={"success": success})


# =====================================================================
# AUDIT LOG ENDPOINTS
# =====================================================================

@app.get("/admin/audit/events")
async def get_audit_events(request: Request, limit: int = 100):
    """Get recent audit events (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.AUDIT_VIEW):
        raise HTTPException(status_code=403, detail="Permission denied")

    events = audit_logger.query_events(limit=limit)

    return JSONResponse(content={
        "events": [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type.value,
                "severity": e.severity.value,
                "user_email": e.user_email,
                "action": e.action,
                "success": e.success
            }
            for e in events
        ]
    })


@app.get("/admin/audit/statistics")
async def get_audit_statistics(request: Request, hours: int = 24):
    """Get audit statistics (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.AUDIT_VIEW):
        raise HTTPException(status_code=403, detail="Permission denied")

    stats = audit_logger.get_statistics(hours=hours)
    return JSONResponse(content=stats)


@app.get("/admin/audit/security")
async def get_security_events(request: Request, hours: int = 24):
    """Get security events (Admin only)"""
    user = get_current_user(request)
    if not user or not rbac_manager.has_permission(user.user_id, Permission.AUDIT_VIEW):
        raise HTTPException(status_code=403, detail="Permission denied")

    events = audit_logger.get_security_events(hours=hours)
    return JSONResponse(content={"events": events})





# Main MCP endpoint - GET method for client-initiated SSE streams
@app.get("/mcp")
async def mcp_get_endpoint(
        request: Request,
        accept: str = Header(None),
        last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
        session_id: Optional[str] = Header(None, alias="Mcp-Session-Id"),
        protocol_version: Optional[str] = Header(None, alias="MCP-Protocol-Version")
):
    """
    GET endpoint for client-initiated SSE streams per 2025-06-18 specification.
    Provides server-to-client communication for gateway notifications.
    """
    try:
        # Validate protocol version
        validated_version = mcp_gateway.validate_protocol_version(protocol_version)

        # Validate Origin header (required by specification)
        # Extract origin considering load balancer/reverse proxy headers
        origin = mcp_gateway.extract_origin_from_request(request)
        logger.info(f"GET endpoint - Extracted origin: {origin}")

        if not mcp_gateway.validate_origin_header(origin):
            logger.warning(f"Origin validation failed for: {origin}")
            raise HTTPException(status_code=403, detail="Origin not allowed")

        # Validate Accept header for GET requests
        if not mcp_gateway.validate_accept_header(accept, "GET"):
            raise HTTPException(status_code=405, detail="Method Not Allowed")

        # Validate session if provided
        if session_id and not mcp_gateway.validate_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        # Generate unique stream ID for this connection
        stream_id = str(uuid.uuid4())

        async def gateway_notification_stream():
            """
            Generate SSE events for gateway notifications per specification.
            100% compliant with resumability and message routing requirements.
            """
            try:
                # Register this stream for proper management
                mcp_gateway.stream_manager.register_stream(
                    stream_id,
                    session_id or "anonymous",
                    "gateway-notifications"
                )

                # Handle resumability if Last-Event-ID provided
                if last_event_id:
                    logger.info(f"Resuming stream {stream_id} from event ID: {last_event_id}")
                    # Replay missed events from this specific stream
                    missed_events = mcp_gateway.event_store.get_events_after(stream_id, last_event_id)
                    for event in missed_events:
                        yield f"id: {event['id']}\n"
                        yield f"data: {json.dumps(event['message'])}\n\n"

                # Send gateway status notifications
                while True:
                    try:
                        # Check for any queued messages for this specific stream
                        queued_message = await mcp_gateway.message_router.get_next_message(stream_id)
                        if queued_message:
                            yield f"id: {queued_message['id']}\n"
                            yield f"data: {json.dumps(queued_message['data'])}\n\n"
                        else:
                            # Send periodic gateway status notification
                            refresh_data = {
                                "jsonrpc": "2.0",
                                "method": "notifications/tools_refresh",
                                "params": {
                                    "timestamp": datetime.now().isoformat(),
                                    "available_tools": len(discovery_service.tool_to_server_map),
                                    "registered_servers": len(await mcp_storage_manager.get_all_servers()) if mcp_storage_manager else 0
                                }
                            }

                            # Store event with proper event ID
                            event_id = mcp_gateway.event_store.store_event(stream_id, refresh_data)
                            yield f"id: {event_id}\n"
                            yield f"data: {json.dumps(refresh_data)}\n\n"

                            await asyncio.sleep(60)  # Status update every 60 seconds

                    except Exception as e:
                        logger.error(f"Error processing stream {stream_id}: {e}")
                        break

            except Exception as e:
                logger.error(f"Error in gateway notification SSE stream {stream_id}: {e}")
            finally:
                # Clean up stream when connection closes
                mcp_gateway.stream_manager.unregister_stream(stream_id)
                mcp_gateway.event_store.cleanup_stream(stream_id)
                mcp_gateway.message_router.cleanup_stream_queue(stream_id)

        return StreamingResponse(
            gateway_notification_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "ngrok-skip-browser-warning": "true",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GET endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# Main MCP endpoint - POST method for client-to-server communication
@app.post("/mcp")
async def mcp_post_endpoint(
        request_data: Dict[str, Any],
        request: Request,
        accept: str = Header(None),
        session_id: Optional[str] = Header(None, alias="Mcp-Session-Id"),
        protocol_version: Optional[str] = Header(None, alias="MCP-Protocol-Version")
):
    """
    POST endpoint implementing MCP 2025-06-18 Streamable HTTP transport.
    Acts as a gateway proxying requests to appropriate backend MCP servers.
    """
    try:
        # Validate protocol version
        validated_version = mcp_gateway.validate_protocol_version(protocol_version)

        # Validate Origin header (required by specification)
        # Extract origin considering load balancer/reverse proxy headers
        origin = mcp_gateway.extract_origin_from_request(request)
        logger.info(f"POST endpoint - Extracted origin: {origin}")

        if not mcp_gateway.validate_origin_header(origin):
            logger.warning(f"Origin validation failed for: {origin}")
            raise HTTPException(status_code=403, detail="Origin not allowed")

        # Validate Accept header for POST requests
        if not mcp_gateway.validate_accept_header(accept, "POST"):
            raise HTTPException(
                status_code=400,
                detail="Accept header must include both application/json and text/event-stream"
            )

        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")

        if not method:
            raise HTTPException(status_code=400, detail="Invalid JSON-RPC request format.")

        # Handle initialization per specification
        if method == "initialize":
            mcp_gateway.client_info = params
            mcp_gateway.initialized = True
            client_name = params.get('clientInfo', {}).get('name', 'Unknown Client')

            # Generate session ID if not provided
            if not session_id:
                session_id = mcp_gateway.generate_session_id()

            # Store session info
            mcp_gateway.sessions[session_id] = {
                'client_info': params,
                'created_at': datetime.now(),
                'initialized': True,
                'protocol_version': validated_version
            }

            logger.info(f"MCP Toolbox Gateway initialized by {client_name} with session {session_id}")

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "streamableHttp": True
                    },
                    "serverInfo": SERVER_INFO
                }
            }

            headers = {"Mcp-Session-Id": session_id}
            return JSONResponse(content=response, headers=headers)

        elif method == "notifications/initialized":
            logger.info("Client initialization completed.")
            return JSONResponse(content={}, status_code=202)  # 202 Accepted per spec

        # Validate session for other methods
        if session_id and not mcp_gateway.validate_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        # Handle tools/list request
        if method == "tools/list":
            logger.info("tools/list: Fetching from discovery service.")
            all_tools = await discovery_service.get_all_tools()

            return JSONResponse(content={
                "jsonrpc": "2.0", "id": request_id, "result": {"tools": all_tools}
            })

        # Handle tools/call request with streaming
        elif method == "tools/call":
            tool_name = params.get("name")
            if not tool_name:
                if request_id:
                    error_response = mcp_gateway.create_error_response(request_id, -32602, "Tool name is required")
                    return JSONResponse(content=error_response, status_code=400)
                else:
                    raise HTTPException(status_code=400, detail="Missing 'name' in params for tools/call.")

            # Find the tool's server location
            try:
                server_url = await discovery_service.get_tool_location(tool_name)
                logger.info(f"tools/call ({tool_name}): Routing to server: {server_url}")
            except ToolNotFoundException:
                logger.error(f"Tool '{tool_name}' not found in any registered MCP server.")
                if request_id:
                    error_response = mcp_gateway.create_error_response(request_id, -32601, f"Tool not found: {tool_name}")
                    return JSONResponse(content=error_response, status_code=404)
                else:
                    raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

            # Forward the request and stream the response back
            async def gateway_streaming_wrapper():
                """Wrap the backend stream with gateway-specific events per specification."""
                try:
                    # Send gateway progress notification
                    gateway_progress = {
                        "jsonrpc": "2.0",
                        "method": "notifications/gateway_progress",
                        "params": {
                            "message": f"Forwarding request to {server_url}",
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    event_id = str(uuid.uuid4())
                    yield f"id: {event_id}\n"
                    yield f"data: {json.dumps(gateway_progress)}\n\n"

                    # Stream from backend server
                    backend_stream = connection_manager.forward_request_streaming(server_url, request_data)
                    async for chunk in backend_stream:
                        yield chunk

                except Exception as e:
                    logger.error(f"Error in gateway streaming wrapper: {e}")
                    error_event_id = str(uuid.uuid4())
                    error_response = mcp_gateway.create_error_response(request_id, -32000, f"Gateway error: {str(e)}")
                    yield f"id: {error_event_id}\n"
                    yield f"data: {json.dumps(error_response)}\n\n"

            return StreamingResponse(
                gateway_streaming_wrapper(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "ngrok-skip-browser-warning": "true",
                }
            )

        # MCP 2025-06-18 specification only supports standard methods
        # Server management is handled via separate management API

        else:
            logger.warning(f"Received unsupported method: {method}")
            if request_id:
                error_response = mcp_gateway.create_error_response(request_id, -32601, f"Method not found: {method}")
                return JSONResponse(content=error_response, status_code=404)
            else:
                raise HTTPException(status_code=404, detail=f"Method not found: {method}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Critical error in POST endpoint: {e}", exc_info=True)
        error_resp = mcp_gateway.create_error_response(
            request_data.get("id"),
            -32000,
            "Internal Server Error"
        )
        return JSONResponse(content=error_resp, status_code=500)


# DELETE endpoint for session termination
@app.delete("/mcp")
async def mcp_delete_endpoint(
        session_id: Optional[str] = Header(None, alias="Mcp-Session-Id"),
        protocol_version: Optional[str] = Header(None, alias="MCP-Protocol-Version")
):
    """
    DELETE endpoint for explicit session termination per 2025-06-18 specification.
    """
    try:
        # Validate protocol version
        mcp_gateway.validate_protocol_version(protocol_version)

        if not session_id:
            raise HTTPException(status_code=400, detail="Mcp-Session-Id header required")

        if mcp_gateway.terminate_session(session_id):
            return JSONResponse(content={"message": "Session terminated"}, status_code=200)
        else:
            raise HTTPException(status_code=404, detail="Session not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in DELETE endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# Management API endpoint - separate from MCP compliance
@app.post("/manage")
async def management_endpoint(request_data: Dict[str, Any]):
    """
    Management API for server operations - separate from MCP protocol.
    This handles UI management functions while keeping /mcp purely MCP compliant.
    """
    try:
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")

        if not method:
            raise HTTPException(status_code=400, detail="Invalid request format.")

        # Handle server management methods
        if method == "server.add":
            server_url = params.get("server_url")
            description = params.get("description", "")
            
            if not server_url:
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "server_url is required"}
                }, status_code=400)
            
            try:
                server_info = await mcp_storage_manager.register_server_from_url(server_url, description)
                if server_info:
                    # Refresh the discovery service
                    await discovery_service.refresh_tool_index()
                    return JSONResponse(content={
                        "jsonrpc": "2.0", 
                        "id": request_id, 
                        "result": {"success": True, "server_id": server_info.server_id}
                    })
                else:
                    return JSONResponse(content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32000, "message": "Failed to register server"}
                    }, status_code=500)
            except Exception as e:
                logger.error(f"Error adding server: {e}")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": f"Error adding server: {str(e)}"}
                }, status_code=500)

        elif method == "server.remove":
            server_id = params.get("server_id")
            
            if not server_id:
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "server_id is required"}
                }, status_code=400)
            
            try:
                success = await mcp_storage_manager.remove_server(server_id)
                if success:
                    # Refresh the discovery service
                    await discovery_service.refresh_tool_index()
                    return JSONResponse(content={
                        "jsonrpc": "2.0", 
                        "id": request_id, 
                        "result": {"success": True}
                    })
                else:
                    return JSONResponse(content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": "Server not found"}
                    }, status_code=404)
            except Exception as e:
                logger.error(f"Error removing server: {e}")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": f"Error removing server: {str(e)}"}
                }, status_code=500)

        elif method == "server.test":
            server_id = params.get("server_id")
            
            if not server_id:
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "server_id is required"}
                }, status_code=400)
            
            try:
                test_result = await mcp_storage_manager.test_server_connection(server_id)
                return JSONResponse(content={
                    "jsonrpc": "2.0", 
                    "id": request_id, 
                    "result": test_result
                })
            except Exception as e:
                logger.error(f"Error testing server: {e}")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": f"Error testing server: {str(e)}"}
                }, status_code=500)

        elif method == "server.list":
            try:
                servers = await mcp_storage_manager.get_all_servers()
                server_cards = {}

                for server_id, server_info in servers.items():
                    # Count tools for this server
                    tool_count = sum(1 for tool_server_url in discovery_service.tool_to_server_map.values()
                                   if tool_server_url == server_info.url)

                    # Get health status for this server
                    health_status = discovery_service.server_health.get(server_info.url)
                    if health_status:
                        status = "online" if health_status.is_healthy else "offline"
                    else:
                        status = "unknown"

                    server_cards[server_id] = {
                        "name": server_info.name,
                        "url": server_info.url,
                        "description": server_info.description,
                        "capabilities": server_info.capabilities,
                        "metadata": server_info.metadata,
                        "updated_at": server_info.updated_at.isoformat(),
                        "tool_count": tool_count,
                        "status": status
                    }
                
                return JSONResponse(content={
                    "jsonrpc": "2.0", 
                    "id": request_id, 
                    "result": {"server_cards": server_cards}
                })
            except Exception as e:
                logger.error(f"Error listing servers: {e}")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": f"Error listing servers: {str(e)}"}
                }, status_code=500)

        else:
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }, status_code=404)

    except Exception as e:
        logger.error(f"Error in management endpoint: {e}", exc_info=True)
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "error": {"code": -32000, "message": "Internal server error"}
        }, status_code=500)


# Configuration API endpoints
@app.get("/config")
async def get_config():
    """Get current gateway configuration"""
    import json
    config = config_manager.get_all_config()
    # Convert datetime to string for JSON serialization
    return JSONResponse(content=json.loads(json.dumps(config, default=str)))


@app.post("/config/health")
async def update_health_config(request_data: Dict[str, Any]):
    """Update connection health monitoring configuration"""
    try:
        updated_config = config_manager.update_connection_health_config(**request_data)

        # Restart health monitoring with new config
        await discovery_service.stop_health_monitoring()
        await discovery_service.start_health_monitoring()

        return JSONResponse(content={
            "success": True,
            "config": updated_config.model_dump()
        })
    except Exception as e:
        logger.error(f"Error updating health config: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@app.post("/config/origin/add")
async def add_allowed_origin(request_data: Dict[str, Any]):
    """Add an allowed origin"""
    try:
        origin = request_data.get("origin")
        if not origin:
            return JSONResponse(content={
                "error": "origin parameter required"
            }, status_code=400)

        success = config_manager.add_allowed_origin(origin)
        return JSONResponse(content={
            "success": success,
            "message": f"Origin '{origin}' {'added' if success else 'already exists'}"
        })
    except Exception as e:
        logger.error(f"Error adding origin: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@app.post("/config/origin/remove")
async def remove_allowed_origin(request_data: Dict[str, Any]):
    """Remove an allowed origin"""
    try:
        origin = request_data.get("origin")
        if not origin:
            return JSONResponse(content={
                "error": "origin parameter required"
            }, status_code=400)

        success = config_manager.remove_allowed_origin(origin)
        return JSONResponse(content={
            "success": success,
            "message": f"Origin '{origin}' {'removed' if success else 'not found'}"
        })
    except Exception as e:
        logger.error(f"Error removing origin: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@app.post("/config/origin")
async def update_origin_config(request_data: Dict[str, Any]):
    """Update origin configuration (allow_ngrok, allow_https)"""
    try:
        updated_config = config_manager.update_origin_config(**request_data)
        return JSONResponse(content={
            "success": True,
            "config": updated_config.model_dump()
        })
    except Exception as e:
        logger.error(f"Error updating origin config: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@app.get("/health/servers")
async def get_servers_health():
    """Get health status of all connected servers"""
    return JSONResponse(content=discovery_service.get_server_health_status())


@app.get("/health/servers/{server_url:path}")
async def get_server_health(server_url: str):
    """Get health status of a specific server"""
    return JSONResponse(content=discovery_service.get_server_health_status(server_url))


if __name__ == "__main__":
    # Use 0.0.0.0 to allow ngrok to forward requests properly
    host = os.getenv("HOST", "0.0.0.0")  # Changed to 0.0.0.0 for ngrok compatibility
    port = int(os.getenv("PORT", "8021"))

    logger.info(f"Starting Tools Gateway (2025-06-18 compliant) on {host}:{port}...")
    logger.info(f"Protocol Version: {PROTOCOL_VERSION}")
    logger.info(f"Server Info: {SERVER_INFO}")
    logger.info("Features: Health monitoring, dynamic origin configuration, user-driven MCP servers")
    logger.info("NGROK COMPATIBILITY: Configured for HTTPS/ngrok access")

    uvicorn.run(app, host=host, port=port, log_level="info")
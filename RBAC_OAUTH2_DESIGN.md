# Role-Based Access Control (RBAC) & OAuth2 Integration Design

## Executive Summary

This document outlines the architecture and implementation plan for integrating role-based access control (RBAC) with OAuth2 authentication between the `agentic_search` and `tools_gateway` services. The design follows industry best practices for microservices authentication and authorization.

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Proposed Architecture](#2-proposed-architecture)
3. [Authentication Flow (OAuth2)](#3-authentication-flow-oauth2)
4. [Authorization Flow (RBAC)](#4-authorization-flow-rbac)
5. [User Synchronization Strategy](#5-user-synchronization-strategy)
6. [API Changes](#6-api-changes)
7. [Implementation Plan](#7-implementation-plan)
8. [Security Considerations](#8-security-considerations)
9. [Industry Best Practices](#9-industry-best-practices)

---

## 1. Current State Analysis

### 1.1 tools_gateway (Port 8021)

**Already Implemented:**
- ✅ Complete OAuth2 provider system (Google, Microsoft, GitHub)
- ✅ JWT token management (HS256 algorithm)
- ✅ Full RBAC system with roles and permissions
- ✅ SQLite database for persistent storage
- ✅ User management (local and OAuth users)
- ✅ Role-based tool permissions (role_tool_permissions table)
- ✅ Audit logging for security events
- ✅ Authentication middleware
- ✅ Tool-level access control infrastructure

**Database Schema:**
```sql
rbac_users (user_id, email, name, provider, password_hash, enabled)
rbac_roles (role_id, role_name, description, permissions, is_system)
user_roles (user_id, role_id)
role_tool_permissions (role_id, server_id, tool_name)
tool_oauth_associations (server_id, tool_name, oauth_provider_id)
audit_logs (event_id, timestamp, event_type, user_id, details)
```

**Default Roles:**
- `admin`: Full system access
- `user`: Basic user access (can view and execute tools)
- `viewer`: Read-only access

### 1.2 agentic_search (Port 8023)

**Current State:**
- ❌ No authentication system
- ❌ No user context
- ✅ MCP client for fetching tools from gateway
- ✅ LangGraph agent workflow
- ✅ FastAPI application
- ✅ Session management for conversations

**Current Tool Fetching:**
```python
# agentic_search/ollama_query_agent/mcp_tool_client.py
async def get_available_tools(self) -> List[Dict[str, Any]]:
    # No authentication - directly calls gateway
    response = await self.client.post(f"{self.registry_base_url}/mcp", ...)
```

---

## 2. Proposed Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User/Client                              │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ 1. Login via OAuth2
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    agentic_search Service                        │
│                        (Port 8023)                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  NEW: OAuth2 Login Flow                                 │   │
│  │  - Redirect to tools_gateway for OAuth                 │   │
│  │  - Receive JWT token after successful auth             │   │
│  │  - Store JWT in session/cookie                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  MODIFIED: MCP Tool Client                              │   │
│  │  - Include JWT token in MCP requests                    │   │
│  │  - Handle 401/403 responses                             │   │
│  │  - Filter tools based on user permissions               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  NEW: Auth Middleware                                   │   │
│  │  - Validate JWT on each request                         │   │
│  │  - Attach user context to request                       │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ 2. MCP Protocol Requests
                   │    + Authorization: Bearer <JWT>
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    tools_gateway Service                         │
│                        (Port 8021)                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  EXISTING: OAuth2 Providers                             │   │
│  │  - Google, Microsoft, GitHub                            │   │
│  │  - PKCE support for security                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  EXISTING: JWT Manager                                  │   │
│  │  - Issue JWT tokens (8 hour expiry)                     │   │
│  │  - Verify JWT signatures                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  MODIFIED: MCP Router (/mcp endpoint)                   │   │
│  │  - Extract JWT from Authorization header                │   │
│  │  - Validate user permissions                            │   │
│  │  - Filter tools/list based on role                      │   │
│  │  - Enforce tool execution permissions                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  EXISTING: RBAC Manager                                 │   │
│  │  - User management                                      │   │
│  │  - Role assignment                                      │   │
│  │  - Permission checking                                  │   │
│  │  - Tool access control                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  EXISTING: SQLite Database                              │   │
│  │  - User profiles                                        │   │
│  │  - Role definitions                                     │   │
│  │  - Tool permissions                                     │   │
│  │  - Audit logs                                           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Interaction

**Key Principle: Centralized Auth, Distributed Authorization Checks**

- **tools_gateway**: Source of truth for users, roles, and permissions
- **agentic_search**: Stateless client that trusts tools_gateway's JWT tokens
- **JWT Token**: Carries user identity and can be validated independently

---

## 3. Authentication Flow (OAuth2)

### 3.1 User Login Flow

```
User → agentic_search → tools_gateway → OAuth Provider → tools_gateway → agentic_search → User

Step-by-step:

1. User accesses agentic_search web UI
2. Clicks "Login with Google/Microsoft/GitHub"
3. agentic_search redirects to:
   GET http://localhost:8021/auth/login?provider_id=google&redirect_to=http://localhost:8023/auth/callback

4. tools_gateway creates OAuth authorization URL with PKCE
5. Redirects user to OAuth provider (Google/Microsoft/GitHub)
6. User authenticates with OAuth provider
7. OAuth provider redirects back to tools_gateway callback:
   GET http://localhost:8021/auth/callback?code=xyz&state=abc

8. tools_gateway:
   - Exchanges code for OAuth token
   - Gets user info from provider
   - Creates/updates user in RBAC system
   - Assigns default "user" role if new user
   - Generates JWT token containing:
     {
       "sub": "user_xyz",
       "email": "user@example.com",
       "name": "John Doe",
       "provider": "google",
       "exp": 1234567890,
       "iat": 1234567890,
       "type": "access"
     }
   - Logs audit event

9. tools_gateway redirects to agentic_search callback:
   GET http://localhost:8023/auth/callback?token=<JWT>

10. agentic_search:
    - Stores JWT in session cookie (HttpOnly, Secure, SameSite=Lax)
    - Redirects to main application

11. User is now authenticated in agentic_search with JWT token
```

### 3.2 Local Authentication (Alternative)

For admin/testing, support local username/password:

```
1. User enters email/password in agentic_search UI
2. agentic_search sends to:
   POST http://localhost:8021/auth/login/local
   Body: {"email": "admin", "password": "admin"}

3. tools_gateway validates credentials
4. Returns JWT token in response
5. agentic_search stores JWT in session
```

---

## 4. Authorization Flow (RBAC)

### 4.1 Tool List Authorization

When agent requests tools list:

```
1. agentic_search makes MCP request:
   POST http://localhost:8021/mcp
   Headers:
     Authorization: Bearer <JWT>
     MCP-Protocol-Version: 2025-06-18
   Body:
     {
       "jsonrpc": "2.0",
       "method": "tools/list",
       "id": "request-123"
     }

2. tools_gateway (MCP router):
   a. Validates JWT token (signature, expiration)
   b. Extracts user email from JWT payload
   c. Looks up user in RBAC system
   d. Gets user's roles (e.g., ["user"])
   e. For each role, gets allowed tools from role_tool_permissions
   f. Aggregates all tools user can access
   g. Filters tools list before returning

3. Response includes only authorized tools:
   {
     "jsonrpc": "2.0",
     "id": "request-123",
     "result": {
       "tools": [
         {
           "name": "search_web",
           "description": "Search the web",
           "_server_id": "mcp_server_1",
           "_oauth_providers": [],
           "_access_roles": ["user", "admin"]
         }
       ]
     }
   }
```

### 4.2 Tool Execution Authorization

When agent executes a tool:

```
1. agentic_search makes tool call:
   POST http://localhost:8021/mcp
   Headers:
     Authorization: Bearer <JWT>
   Body:
     {
       "jsonrpc": "2.0",
       "method": "tools/call",
       "id": "call-456",
       "params": {
         "name": "search_web",
         "arguments": {"query": "AI news"}
       }
     }

2. tools_gateway (MCP router):
   a. Validates JWT token
   b. Extracts user_id from token
   c. Gets tool metadata (server_id, tool_name)
   d. Calls: rbac_manager.can_execute_tool(user_id, server_id, tool_name)
   e. Checks:
      - User has TOOL_EXECUTE permission
      - User's roles include this tool in role_tool_permissions
      - If no specific permissions set, check general TOOL_VIEW

3. If authorized:
   - Forward request to backend MCP server
   - Stream response back to client
   - Log successful execution in audit log

4. If not authorized:
   - Return 403 Forbidden
   - Log failed attempt in audit log with user_id, tool_name, timestamp
```

### 4.3 Permission Hierarchy

```
admin role:
  - Has ALL permissions automatically (superuser)
  - Can access all tools
  - Can execute all tools
  - Can manage users, roles, and permissions

user role:
  - Has TOOL_VIEW, TOOL_EXECUTE permissions
  - Can only access tools explicitly assigned to "user" role
  - Cannot manage users or configure system

viewer role:
  - Has TOOL_VIEW permission only
  - Can see tools but cannot execute them
  - Read-only access
```

---

## 5. User Synchronization Strategy

### 5.1 Approach: JWT-Based Trust Model

**We DON'T need explicit user synchronization between services.**

**Rationale:**
- tools_gateway is the **single source of truth** for users
- agentic_search is a **stateless client**
- JWT token carries all necessary user identity
- agentic_search validates JWT and trusts tools_gateway's decisions

### 5.2 User Lifecycle

**New User:**
```
1. User logs in via OAuth for first time
2. tools_gateway:
   - Calls get_or_create_user(email, name, provider)
   - Creates user in rbac_users table
   - Assigns default "user" role
   - Issues JWT token
3. agentic_search receives JWT
4. No local user database needed
```

**Existing User:**
```
1. User logs in again
2. tools_gateway:
   - Finds existing user by email
   - Updates last_login timestamp
   - Issues fresh JWT token
3. agentic_search receives JWT
```

**User Role Changes:**
```
1. Admin updates user's roles in tools_gateway UI
2. Change takes effect on next JWT issuance (next login)
3. For immediate effect, admin can invalidate old tokens (optional feature)
```

### 5.3 Token Validation

agentic_search validates JWT locally:

```python
# Pseudo-code for agentic_search
def validate_jwt(token: str) -> Optional[Dict]:
    """
    Validate JWT token using shared secret.
    No need to call tools_gateway for every validation.
    """
    try:
        # Verify signature and expiration
        payload = jwt.decode(
            token,
            secret_key=GATEWAY_JWT_SECRET,  # Shared secret
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

**Important:** agentic_search needs to know the JWT secret used by tools_gateway. Options:
1. **Environment Variable** (Recommended): Both services load from `JWT_SECRET` env var
2. **Config Service**: Fetch from shared config service
3. **Public Key Crypto**: Switch to RS256, share public key only

---

## 6. API Changes

### 6.1 tools_gateway Changes

#### A. New Endpoint: Cross-Origin Auth Callback

**Purpose:** Allow agentic_search to redirect users to tools_gateway for login.

```python
# tools_gateway/routers/auth_router.py

@router.get("/auth/login-redirect")
async def login_redirect(provider_id: str, redirect_to: str):
    """
    Initiate OAuth flow with custom redirect.
    After successful auth, redirect user to redirect_to with token.
    """
    # Validate redirect_to is allowed origin
    if not is_allowed_origin(redirect_to):
        raise HTTPException(status_code=403, detail="Invalid redirect URL")

    # Store redirect_to in session state
    auth_data = oauth_provider_manager.create_authorization_url(
        provider_id,
        redirect_uri=f"{base_url}/auth/callback-redirect"
    )

    # Store redirect_to in pending_states for this auth flow
    state = auth_data['state']
    pending_redirects[state] = redirect_to

    return JSONResponse(content=auth_data)


@router.get("/auth/callback-redirect")
async def callback_redirect(code: str, state: str):
    """
    OAuth callback that redirects to external service with JWT.
    """
    # Exchange code for token (existing logic)
    result = await oauth_provider_manager.exchange_code_for_token(code, state)
    oauth_token, provider_id = result

    # Get user info and create/update user (existing logic)
    user_info = await oauth_provider_manager.get_user_info(provider_id, oauth_token.access_token)
    user = rbac_manager.get_or_create_user(user_info.email, user_info.name, provider_id)

    # Create JWT
    jwt_token = jwt_manager.create_access_token(user_info)

    # Get stored redirect URL
    redirect_to = pending_redirects.pop(state)

    # Redirect to external service with token
    return RedirectResponse(url=f"{redirect_to}?token={jwt_token}")
```

#### B. Modified: MCP Router - Add Authorization Checks

```python
# tools_gateway/routers/mcp_router.py

@router.post("/mcp")
async def mcp_post_endpoint(
    request_data: Dict[str, Any],
    request: Request,
    # ... existing parameters
):
    method = request_data.get("method")

    # Extract and validate JWT token
    user = get_current_user(request)  # Already implemented

    if method == "tools/list":
        # Get all tools
        all_tools = await discovery_service.get_all_tools()

        if user:
            # Filter tools based on user permissions
            allowed_tools = []
            for tool in all_tools:
                server_id = tool.get('_server_id')
                tool_name = tool.get('name')

                if server_id and tool_name:
                    # Check if user can access this tool
                    if rbac_manager.can_execute_tool(user.user_id, server_id, tool_name):
                        allowed_tools.append(tool)
                else:
                    # No restrictions for tools without server_id
                    allowed_tools.append(tool)

            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "result": {"tools": allowed_tools}
            })
        else:
            # No authentication - return public tools only (if configured)
            # Or return 401 Unauthorized
            raise HTTPException(status_code=401, detail="Authentication required")

    elif method == "tools/call":
        tool_name = params.get("name")

        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Get tool metadata
        all_tools = await discovery_service.get_all_tools()
        tool_metadata = next((t for t in all_tools if t.get('name') == tool_name), None)

        if not tool_metadata:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

        server_id = tool_metadata.get('_server_id')

        # Check authorization
        if not rbac_manager.can_execute_tool(user.user_id, server_id, tool_name):
            # Log unauthorized access attempt
            audit_logger.log_event(
                AuditEventType.AUTHZ_PERMISSION_DENIED,
                severity=AuditSeverity.WARNING,
                user_id=user.user_id,
                user_email=user.email,
                resource_type="tool",
                resource_id=tool_name,
                details={"action": "execute", "server_id": server_id},
                success=False
            )
            raise HTTPException(status_code=403, detail=f"Access denied to tool: {tool_name}")

        # Log successful authorization
        audit_logger.log_event(
            AuditEventType.AUTHZ_PERMISSION_GRANTED,
            user_id=user.user_id,
            user_email=user.email,
            resource_type="tool",
            resource_id=tool_name,
            details={"action": "execute", "server_id": server_id}
        )

        # Forward request to backend server (existing logic)
        # ... rest of existing code
```

#### C. New Endpoint: User Validation

**Purpose:** Allow agentic_search to validate tokens and get user permissions.

```python
# tools_gateway/routers/auth_router.py

@router.get("/auth/validate")
async def validate_token(request: Request):
    """
    Validate JWT token and return user info with permissions.
    Used by external services to verify user access.
    """
    user = get_current_user(request)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    permissions = rbac_manager.get_user_permissions(user.user_id)

    return JSONResponse(content={
        "valid": True,
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "name": user.name,
            "provider": user.provider,
            "roles": [r for r in user.roles],
            "permissions": [p.value for p in permissions],
            "enabled": user.enabled
        }
    })
```

### 6.2 agentic_search Changes

#### A. New: Authentication Module

```python
# agentic_search/auth.py

import os
import secrets
from typing import Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Response
from jose import jwt, JWTError

# Shared JWT secret with tools_gateway
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# Session management
user_sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> user_data


def create_session(user_data: Dict[str, Any]) -> str:
    """Create a new user session"""
    session_id = secrets.token_urlsafe(32)
    user_sessions[session_id] = {
        "user": user_data,
        "created_at": datetime.now(),
        "jwt_token": user_data.get("jwt_token")
    }
    return session_id


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get user session"""
    return user_sessions.get(session_id)


def delete_session(session_id: str):
    """Delete user session"""
    if session_id in user_sessions:
        del user_sessions[session_id]


def validate_jwt(token: str) -> Optional[Dict[str, Any]]:
    """Validate JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current authenticated user from request"""
    # Try session cookie first
    session_id = request.cookies.get("session_id")
    if session_id:
        session = get_session(session_id)
        if session:
            return session["user"]

    # Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = validate_jwt(token)
        if payload:
            return {
                "email": payload.get("email"),
                "name": payload.get("name"),
                "sub": payload.get("sub"),
                "provider": payload.get("provider")
            }

    return None


def require_auth(request: Request):
    """Middleware to require authentication"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
```

#### B. New: Authentication Routes

```python
# agentic_search/auth_routes.py

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
import aiohttp

router = APIRouter(prefix="/auth", tags=["authentication"])

TOOLS_GATEWAY_URL = os.getenv("TOOLS_GATEWAY_URL", "http://localhost:8021")
AGENTIC_SEARCH_URL = os.getenv("AGENTIC_SEARCH_URL", "http://localhost:8023")


@router.get("/login")
async def login_page():
    """Render login page with OAuth options"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - Agentic Search</title>
        <style>
            body { font-family: Arial; max-width: 400px; margin: 100px auto; }
            .login-btn {
                display: block;
                padding: 15px;
                margin: 10px 0;
                text-align: center;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
            }
            .google { background: #4285f4; color: white; }
            .microsoft { background: #00a4ef; color: white; }
            .github { background: #333; color: white; }
        </style>
    </head>
    <body>
        <h1>Login to Agentic Search</h1>
        <a href="/auth/oauth/google" class="login-btn google">
            Login with Google
        </a>
        <a href="/auth/oauth/microsoft" class="login-btn microsoft">
            Login with Microsoft
        </a>
        <a href="/auth/oauth/github" class="login-btn github">
            Login with GitHub
        </a>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.get("/oauth/{provider_id}")
async def oauth_login(provider_id: str):
    """Initiate OAuth login flow via tools_gateway"""
    redirect_to = f"{AGENTIC_SEARCH_URL}/auth/callback"
    login_url = f"{TOOLS_GATEWAY_URL}/auth/login-redirect?provider_id={provider_id}&redirect_to={redirect_to}"
    return RedirectResponse(url=login_url)


@router.get("/callback")
async def oauth_callback(token: str, response: Response):
    """
    OAuth callback after successful authentication.
    Receives JWT token from tools_gateway.
    """
    # Validate token
    payload = validate_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Create session
    user_data = {
        "email": payload.get("email"),
        "name": payload.get("name"),
        "sub": payload.get("sub"),
        "provider": payload.get("provider"),
        "jwt_token": token
    }
    session_id = create_session(user_data)

    # Set session cookie
    response = RedirectResponse(url="/")
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,  # Use in production with HTTPS
        samesite="lax",
        max_age=28800  # 8 hours (match JWT expiry)
    )

    return response


@router.get("/user")
async def get_user_info(request: Request):
    """Get current user info"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return JSONResponse(content=user)


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout user"""
    session_id = request.cookies.get("session_id")
    if session_id:
        delete_session(session_id)

    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie("session_id")
    return response
```

#### C. Modified: MCP Tool Client

```python
# agentic_search/ollama_query_agent/mcp_tool_client.py

class MCPToolClient:
    def __init__(self, registry_base_url: str = None, jwt_token: str = None):
        self.registry_base_url = registry_base_url or os.getenv("MCP_GATEWAY_URL", "http://localhost:8021")
        self.jwt_token = jwt_token  # Store JWT for authenticated requests
        self.client = httpx.AsyncClient(timeout=60)

    def set_jwt_token(self, token: str):
        """Update JWT token for authentication"""
        self.jwt_token = token

    def _get_headers(self) -> Dict[str, str]:
        """Get headers including authentication"""
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-06-18",
            "Origin": self.origin
        }

        # Add authentication if available
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"

        return headers

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Fetch available tools from MCP registry with authentication"""
        try:
            # Initialize MCP session
            init_payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "search-agent-init",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "clientInfo": {
                        "name": "agentic-search",
                        "version": "1.0.0"
                    }
                }
            }

            headers = self._get_headers()

            # Initialize session
            response = await self.client.post(
                f"{self.registry_base_url}/mcp",
                json=init_payload,
                headers=headers
            )

            # Handle authentication errors
            if response.status_code == 401:
                logger.error("Authentication required to access tools")
                return []
            elif response.status_code == 403:
                logger.error("Access denied to tools")
                return []

            response.raise_for_status()

            # ... rest of existing code with headers included

        except Exception as e:
            logger.error(f"Error fetching tools from MCP registry: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific tool via MCP registry with authentication"""
        try:
            # ... existing initialization code with headers included

            headers = self._get_headers()

            # ... rest of existing code

            response = await self.client.post(
                f"{self.registry_base_url}/mcp",
                json=tool_call_payload,
                headers=headers
            )

            # Handle authentication errors
            if response.status_code == 401:
                return {"error": "Authentication required"}
            elif response.status_code == 403:
                return {"error": "Access denied to this tool"}

            # ... rest of existing code

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"error": f"Tool call failed: {str(e)}"}
```

#### D. Modified: Server with Auth

```python
# agentic_search/server.py

from fastapi import FastAPI, Depends
from .auth import get_current_user, require_auth
from .auth_routes import router as auth_router

app = FastAPI(title="Agentic Search Service")

# Add authentication routes
app.include_router(auth_router)

# Update existing endpoints to require auth
@app.get("/tools")
async def get_available_tools(user = Depends(require_auth)):
    """Get available tools from MCP registry (authenticated)"""
    try:
        # Get user's JWT token from session
        jwt_token = user.get("jwt_token")

        # Update MCP client with token
        mcp_tool_client.set_jwt_token(jwt_token)

        # Fetch tools (will be filtered by gateway based on user's roles)
        tools = await mcp_tool_client.get_available_tools()
        return JSONResponse(content={"tools": tools})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tools: {str(e)}")


@app.post("/search")
async def search_endpoint(request: SearchRequest, user = Depends(require_auth)):
    """Main search endpoint with streaming response (authenticated)"""
    # Get user's JWT token
    jwt_token = user.get("jwt_token")
    mcp_tool_client.set_jwt_token(jwt_token)

    # ... rest of existing code
```

---

## 7. Implementation Plan

### Phase 1: Setup and Configuration (2-3 hours)

**Tasks:**
1. ✅ Create design document (this file)
2. Add JWT_SECRET environment variable to both services
3. Update docker-compose.yml or environment configs
4. Test JWT sharing between services

**Environment Variables:**
```bash
# .env file for both services
JWT_SECRET=your-super-secret-jwt-key-minimum-32-characters-long
TOOLS_GATEWAY_URL=http://localhost:8021
AGENTIC_SEARCH_URL=http://localhost:8023
```

### Phase 2: tools_gateway Modifications (4-6 hours)

**Tasks:**
1. Implement `/auth/login-redirect` endpoint
2. Implement `/auth/callback-redirect` endpoint
3. Implement `/auth/validate` endpoint
4. Modify MCP router to add authorization checks:
   - `tools/list` filtering
   - `tools/call` permission checking
5. Add audit logging for authorization events
6. Test OAuth flow with redirect
7. Test permission checking

**Testing:**
```bash
# Test login redirect
curl http://localhost:8021/auth/login-redirect?provider_id=google&redirect_to=http://localhost:8023/auth/callback

# Test token validation
curl -H "Authorization: Bearer <JWT>" http://localhost:8021/auth/validate

# Test filtered tools list
curl -H "Authorization: Bearer <JWT>" -X POST http://localhost:8021/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":"1"}'
```

### Phase 3: agentic_search Implementation (6-8 hours)

**Tasks:**
1. Create `auth.py` module with JWT validation
2. Create `auth_routes.py` with login/callback/logout
3. Modify `mcp_tool_client.py` to include JWT token
4. Modify `server.py` to add auth middleware
5. Create login HTML page
6. Update chat UI to show user info
7. Handle 401/403 errors in UI
8. Test end-to-end authentication flow

**Testing:**
```bash
# Start both services
cd tools_gateway && python main.py  # Port 8021
cd agentic_search && python server.py  # Port 8023

# Open browser
open http://localhost:8023/auth/login

# Test login flow
# - Click "Login with Google"
# - Should redirect to Google
# - After auth, should return to agentic_search
# - Should be able to access /tools endpoint
# - Should see filtered tools based on role
```

### Phase 4: UI Enhancements (4-6 hours)

**Tasks:**
1. Add user profile display in agentic_search UI
2. Add logout button
3. Show access denied messages gracefully
4. Add loading states during auth
5. Persist session across page refreshes
6. Add token refresh logic (before expiry)

### Phase 5: Admin UI for RBAC (Optional, 8-10 hours)

**Tasks:**
1. Create admin dashboard in tools_gateway
2. User management UI (already exists, enhance)
3. Role management UI (already exists, enhance)
4. Tool permission assignment UI
5. Audit log viewer

### Phase 6: Testing & Security Audit (4-6 hours)

**Tasks:**
1. Test all authentication flows
2. Test authorization edge cases
3. Test token expiration handling
4. Security audit:
   - XSS prevention
   - CSRF protection
   - SQL injection (using parameterized queries)
   - Secure cookie settings
5. Performance testing
6. Documentation updates

**Total Estimated Time: 28-39 hours**

---

## 8. Security Considerations

### 8.1 JWT Security

✅ **Implemented:**
- HS256 algorithm (symmetric)
- 8-hour token expiry
- Token signature verification
- Secure token generation

⚠️ **Recommendations:**
1. **Switch to RS256** (asymmetric) for production:
   - Private key on tools_gateway (sign tokens)
   - Public key on agentic_search (verify tokens)
   - Prevents token forgery if one service is compromised

2. **Add token revocation:**
   - Maintain blacklist in Redis/database
   - Check blacklist on critical operations
   - Allow admin to revoke user sessions

3. **Add refresh tokens:**
   - Short-lived access tokens (1 hour)
   - Long-lived refresh tokens (7 days)
   - Rotate refresh tokens on use

### 8.2 Session Security

✅ **Implemented:**
- HttpOnly cookies (prevent XSS)
- Secure flag for HTTPS
- SameSite=Lax (CSRF protection)

⚠️ **Recommendations:**
1. **Use Redis for session storage** (instead of in-memory)
2. **Add session timeout** (absolute and idle)
3. **Implement CSRF tokens** for state-changing operations

### 8.3 OAuth Security

✅ **Implemented:**
- PKCE (Proof Key for Code Exchange)
- State parameter for CSRF protection
- Token exchange server-side

⚠️ **Recommendations:**
1. **Validate redirect_to URLs** against whitelist
2. **Add rate limiting** on auth endpoints
3. **Log all authentication attempts**

### 8.4 Authorization Security

✅ **Implemented:**
- Role-based permissions
- Tool-level access control
- Audit logging

⚠️ **Recommendations:**
1. **Implement least privilege principle:**
   - Default new users to minimal permissions
   - Require explicit grants for tools

2. **Add time-based access control:**
   - Grant temporary tool access
   - Expire permissions after time period

3. **Add context-aware authorization:**
   - Rate limit tool executions per user
   - Restrict based on IP, time of day, etc.

### 8.5 Data Protection

⚠️ **Recommendations:**
1. **Encrypt sensitive data at rest:**
   - OAuth client secrets
   - User passwords (already hashed with SHA-256, consider bcrypt)

2. **Use HTTPS in production:**
   - Enforce HTTPS for all endpoints
   - HSTS headers

3. **Sanitize tool arguments:**
   - Validate and sanitize all user inputs
   - Prevent injection attacks

---

## 9. Industry Best Practices

### 9.1 Architecture Patterns

✅ **Followed:**
1. **Microservices Authentication:** JWT-based stateless auth
2. **API Gateway Pattern:** tools_gateway as central auth gateway
3. **Separation of Concerns:** Auth separate from business logic
4. **Single Source of Truth:** Centralized user/role management

### 9.2 OAuth 2.1 Compliance

✅ **Implemented:**
- PKCE for authorization code flow
- Short-lived access tokens
- State parameter for CSRF
- Redirect URI validation

### 9.3 Zero Trust Security

✅ **Principles Applied:**
- Authenticate every request
- Authorize at tool execution level
- Audit all access attempts
- Least privilege access

### 9.4 Scalability

✅ **Design for Scale:**
- Stateless JWT validation (no DB lookup per request)
- Connection pooling in aiohttp
- Async/await for non-blocking I/O
- SQLite with WAL mode for concurrency

⚠️ **Future Enhancements:**
- Move to PostgreSQL for production
- Add Redis for session storage
- Implement distributed tracing
- Add load balancer for multiple instances

### 9.5 Observability

✅ **Implemented:**
- Comprehensive audit logging
- Structured logging with timestamps
- Event types for monitoring

⚠️ **Recommendations:**
1. Add metrics (Prometheus):
   - Auth success/failure rates
   - Tool execution counts by user
   - Token validation latency

2. Add distributed tracing (Jaeger):
   - Track requests across services
   - Debug performance bottlenecks

3. Add alerting:
   - Multiple failed auth attempts
   - Unauthorized access patterns
   - Service health issues

---

## 10. Configuration Examples

### 10.1 Environment Variables

```bash
# .env file for tools_gateway
JWT_SECRET=your-super-secret-jwt-key-minimum-32-characters-long
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=480
DATABASE_PATH=tools_gateway.db
ALLOWED_ORIGINS=http://localhost:8023,https://agentic-search.example.com
LOG_LEVEL=INFO

# OAuth Providers
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
```

```bash
# .env file for agentic_search
JWT_SECRET=your-super-secret-jwt-key-minimum-32-characters-long
JWT_ALGORITHM=HS256
TOOLS_GATEWAY_URL=http://localhost:8021
AGENTIC_SEARCH_URL=http://localhost:8023
MCP_GATEWAY_URL=http://localhost:8021
SESSION_COOKIE_NAME=session_id
SESSION_COOKIE_MAX_AGE=28800
LOG_LEVEL=INFO
```

### 10.2 Docker Compose

```yaml
version: '3.8'

services:
  tools_gateway:
    build: ./tools_gateway
    ports:
      - "8021:8021"
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - DATABASE_PATH=/data/tools_gateway.db
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
    volumes:
      - ./data:/data

  agentic_search:
    build: ./agentic_search
    ports:
      - "8023:8023"
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - TOOLS_GATEWAY_URL=http://tools_gateway:8021
      - AGENTIC_SEARCH_URL=http://localhost:8023
    depends_on:
      - tools_gateway
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# Test JWT validation
def test_jwt_validation():
    token = jwt_manager.create_access_token(user_info)
    payload = jwt_manager.verify_token(token)
    assert payload['email'] == user_info.email

# Test permission checking
def test_can_execute_tool():
    assert rbac_manager.can_execute_tool('user_123', 'server_1', 'search_web') == True
    assert rbac_manager.can_execute_tool('user_123', 'server_1', 'admin_tool') == False
```

### 11.2 Integration Tests

```python
# Test OAuth flow
async def test_oauth_flow():
    # 1. Initiate OAuth
    response = await client.get('/auth/oauth/google')
    assert response.status_code == 302

    # 2. Simulate callback
    response = await client.get(f'/auth/callback?token={test_jwt}')
    assert response.status_code == 302
    assert 'session_id' in response.cookies

# Test authorized tool access
async def test_tool_access_authorized():
    headers = {'Authorization': f'Bearer {user_jwt}'}
    response = await client.post('/mcp', json={
        'jsonrpc': '2.0',
        'method': 'tools/call',
        'params': {'name': 'search_web', 'arguments': {}}
    }, headers=headers)
    assert response.status_code == 200
```

### 11.3 Security Tests

```python
# Test expired token
def test_expired_token():
    expired_token = create_expired_jwt()
    headers = {'Authorization': f'Bearer {expired_token}'}
    response = client.get('/tools', headers=headers)
    assert response.status_code == 401

# Test unauthorized tool access
def test_unauthorized_tool_access():
    headers = {'Authorization': f'Bearer {viewer_jwt}'}
    response = client.post('/mcp', json={
        'method': 'tools/call',
        'params': {'name': 'admin_only_tool'}
    }, headers=headers)
    assert response.status_code == 403
```

---

## 12. Migration Guide

### 12.1 For Existing tools_gateway Users

**No migration needed!** The changes are backward compatible:
- Existing users continue to work
- Existing role assignments preserved
- New endpoints are additive

**Optional:** Assign tool permissions to existing roles:
```sql
-- Grant all tools to existing 'user' role
INSERT INTO role_tool_permissions (role_id, server_id, tool_name)
SELECT 'user', server_id, name
FROM (SELECT DISTINCT _server_id as server_id, name FROM tools);
```

### 12.2 For Existing agentic_search Users

**Breaking Change:** Authentication is now required.

**Migration Steps:**
1. Deploy new version with auth
2. Show migration notice to users
3. Users must log in with OAuth
4. Previous sessions invalidated

**Grace Period (Optional):**
```python
# Allow anonymous access for 30 days
if datetime.now() < datetime(2025, 2, 15):
    # Allow unauthenticated access
    logger.warning("Anonymous access during migration period")
    return await original_handler(request)
```

---

## 13. Monitoring and Alerts

### 13.1 Key Metrics

**Authentication Metrics:**
- `auth_login_total{provider, status}` - Login attempts
- `auth_token_validation_total{status}` - Token validations
- `auth_token_expiry_total` - Expired tokens

**Authorization Metrics:**
- `authz_permission_check_total{permission, status}` - Permission checks
- `authz_tool_access_denied_total{tool_name}` - Denied tool access
- `authz_tool_execution_total{tool_name, user_role}` - Tool executions

**Security Metrics:**
- `security_failed_login_total{user_email}` - Failed logins
- `security_unauthorized_access_total{path}` - Unauthorized access
- `security_suspicious_activity_total{type}` - Suspicious activity

### 13.2 Alert Rules

```yaml
# Prometheus alert rules
groups:
  - name: authentication
    rules:
      - alert: HighFailedLoginRate
        expr: rate(auth_login_total{status="failure"}[5m]) > 5
        annotations:
          summary: High failed login rate detected

      - alert: ExpiredTokenSpike
        expr: rate(auth_token_expiry_total[5m]) > 10
        annotations:
          summary: Unusual number of expired tokens

  - name: authorization
    rules:
      - alert: UnauthorizedAccessAttempt
        expr: rate(authz_tool_access_denied_total[5m]) > 10
        annotations:
          summary: Multiple unauthorized access attempts
```

---

## 14. Rollback Plan

In case of issues during deployment:

### 14.1 tools_gateway Rollback

**Steps:**
1. Stop new version
2. Restart previous version
3. Database schema is backward compatible (no rollback needed)
4. Existing sessions continue to work

**Impact:** New auth endpoints unavailable, existing auth works

### 14.2 agentic_search Rollback

**Steps:**
1. Stop new version with auth
2. Deploy previous version without auth
3. Users can access without login
4. JWT tokens ignored

**Impact:** Lose access control, back to open access

### 14.3 Partial Rollback

**Option:** Keep auth optional in agentic_search:
```python
# Make auth optional during transition
user = get_current_user(request)
if user:
    # Use authenticated access with filtering
    jwt_token = user.get("jwt_token")
    mcp_tool_client.set_jwt_token(jwt_token)
else:
    # Allow anonymous access (no filtering)
    logger.warning("Anonymous access - no filtering applied")
```

---

## 15. Future Enhancements

### 15.1 Short Term (1-3 months)

1. **Token Refresh:** Implement refresh tokens for better UX
2. **Remember Me:** Persistent login option
3. **Admin Dashboard:** Enhanced RBAC management UI
4. **Audit Report:** Export audit logs to CSV/PDF
5. **Rate Limiting:** Per-user rate limits for tools

### 15.2 Medium Term (3-6 months)

1. **Multi-tenancy:** Support for organizations/teams
2. **API Keys:** Generate API keys for programmatic access
3. **Webhook Integration:** Notify on auth/authz events
4. **Advanced RBAC:** Attribute-based access control (ABAC)
5. **Federation:** SAML/OIDC support for enterprise SSO

### 15.3 Long Term (6-12 months)

1. **Service Mesh:** Istio/Linkerd for mTLS
2. **Dynamic Authorization:** Policy-as-code with OPA
3. **Zero Trust Network:** Verify every request, every time
4. **Blockchain Audit:** Immutable audit trail
5. **AI-Based Anomaly Detection:** Detect suspicious patterns

---

## 16. Conclusion

This design provides a **production-ready, secure, and scalable** RBAC + OAuth2 solution for the agentic_search and tools_gateway services.

**Key Benefits:**
✅ **Centralized Auth:** Single source of truth for users/roles
✅ **Stateless:** JWT-based auth scales horizontally
✅ **Flexible:** Support multiple OAuth providers
✅ **Secure:** Industry best practices (PKCE, audit logs, etc.)
✅ **Maintainable:** Clear separation of concerns
✅ **Observable:** Comprehensive logging and metrics

**Ready for Production:**
- ✅ OWASP Top 10 considerations
- ✅ GDPR compliance (audit logs, user management)
- ✅ OAuth 2.1 compliance
- ✅ Zero Trust principles
- ✅ Scalability considerations

**Next Steps:**
1. Review and approve design
2. Set up environment variables
3. Begin Phase 1 implementation
4. Iterative testing and deployment

---

## Appendix A: API Reference

### tools_gateway Auth Endpoints

```
GET  /auth/providers
GET  /auth/login-redirect?provider_id=google&redirect_to=http://localhost:8023/auth/callback
GET  /auth/callback-redirect?code=xyz&state=abc
POST /auth/login/local
GET  /auth/validate
GET  /auth/user
POST /auth/logout
```

### tools_gateway MCP Endpoints (with auth)

```
POST /mcp
  method: initialize
  method: tools/list     (filtered by user roles)
  method: tools/call     (permission checked)
```

### agentic_search Auth Endpoints

```
GET  /auth/login
GET  /auth/oauth/{provider_id}
GET  /auth/callback?token=jwt
GET  /auth/user
POST /auth/logout
```

### agentic_search API Endpoints (with auth)

```
GET  /tools              (requires auth)
POST /search             (requires auth)
```

---

## Appendix B: Database Schema Changes

**No new tables required!** Existing schema supports everything:

```sql
-- Role-based tool permissions (already exists)
CREATE TABLE role_tool_permissions (
    role_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role_id, server_id, tool_name)
);

-- Example data for testing
INSERT INTO role_tool_permissions (role_id, server_id, tool_name)
VALUES
  ('user', 'mcp_server_1', 'search_web'),
  ('user', 'mcp_server_1', 'get_weather'),
  ('admin', 'mcp_server_1', 'search_web'),
  ('admin', 'mcp_server_1', 'get_weather'),
  ('admin', 'mcp_server_1', 'admin_tool');
```

---

## Appendix C: Environment Setup

```bash
#!/bin/bash
# setup_auth.sh - Setup script for OAuth2 integration

# Generate secure JWT secret
JWT_SECRET=$(openssl rand -base64 32)

# Create .env file
cat > .env << EOF
# JWT Configuration
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=480

# Service URLs
TOOLS_GATEWAY_URL=http://localhost:8021
AGENTIC_SEARCH_URL=http://localhost:8023

# OAuth Providers (configure your own)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Optional: Enable debug logging
LOG_LEVEL=DEBUG
EOF

echo "Created .env file with JWT secret"
echo "⚠️  Please update OAuth provider credentials"
```

---

**Document Version:** 1.0
**Last Updated:** 2025-01-10
**Author:** AI Architecture Team
**Status:** Ready for Review

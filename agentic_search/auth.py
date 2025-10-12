#!/usr/bin/env python3
"""
Authentication Module for Agentic Search
Handles JWT validation, session management, and user context
"""
import os
import secrets
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, Request
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# JWT Configuration (must match tools_gateway)
JWT_SECRET = os.getenv("JWT_SECRET", "AGD80F/Dp1s2m4nruBRkddaYI7pvCT9vGzhfOkSxrBo=")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Session Configuration
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session_id")
SESSION_COOKIE_MAX_AGE = int(os.getenv("SESSION_COOKIE_MAX_AGE", "28800"))  # 8 hours

# In-memory session store (use Redis in production)
user_sessions: Dict[str, Dict[str, Any]] = {}


def validate_jwt(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate JWT token and return payload.

    Args:
        token: JWT token string

    Returns:
        Decoded payload if valid, None if invalid/expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Check if token is expired (additional check besides jwt.decode)
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            logger.warning("JWT token expired")
            return None

        return payload

    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error validating JWT: {e}")
        return None


def create_session(user_data: Dict[str, Any], jwt_token: str) -> str:
    """
    Create a new user session.

    Args:
        user_data: User information from JWT payload
        jwt_token: Original JWT token for API calls

    Returns:
        Session ID
    """
    session_id = secrets.token_urlsafe(32)

    user_sessions[session_id] = {
        "user": user_data,
        "jwt_token": jwt_token,
        "created_at": datetime.now(),
        "last_accessed": datetime.now()
    }

    logger.info(f"Created session for user {user_data.get('email')}")
    return session_id


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user session by ID.

    Args:
        session_id: Session identifier

    Returns:
        Session data if found and valid, None otherwise
    """
    if session_id not in user_sessions:
        return None

    session = user_sessions[session_id]

    # Check if session has expired (8 hours)
    created_at = session.get("created_at")
    if created_at:
        age = datetime.now() - created_at
        if age.total_seconds() > SESSION_COOKIE_MAX_AGE:
            logger.info(f"Session {session_id[:8]}... expired")
            delete_session(session_id)
            return None

    # Update last accessed time
    session["last_accessed"] = datetime.now()

    return session


def delete_session(session_id: str):
    """
    Delete user session.

    Args:
        session_id: Session identifier
    """
    if session_id in user_sessions:
        del user_sessions[session_id]
        logger.info(f"Deleted session {session_id[:8]}...")


def cleanup_expired_sessions():
    """
    Remove expired sessions from memory.
    Should be called periodically in production.
    """
    now = datetime.now()
    expired_sessions = []

    for session_id, session in user_sessions.items():
        created_at = session.get("created_at")
        if created_at:
            age = now - created_at
            if age.total_seconds() > SESSION_COOKIE_MAX_AGE:
                expired_sessions.append(session_id)

    for session_id in expired_sessions:
        delete_session(session_id)

    if expired_sessions:
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user from request.
    Checks both session cookie and Authorization header.

    Args:
        request: FastAPI request object

    Returns:
        User data dict if authenticated, None otherwise
    """
    # Try session cookie first (for browser-based access)
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        session = get_session(session_id)
        if session:
            user_data = session.get("user", {})
            user_data["jwt_token"] = session.get("jwt_token")  # Add JWT for API calls
            return user_data

    # Try Authorization header (for API access)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        payload = validate_jwt(token)
        if payload:
            user_data = {
                "email": payload.get("email"),
                "name": payload.get("name"),
                "sub": payload.get("sub"),
                "provider": payload.get("provider"),
                "jwt_token": token
            }
            return user_data

    return None


def require_auth(request: Request) -> Dict[str, Any]:
    """
    Middleware to require authentication.
    Raises 401 if not authenticated.

    Args:
        request: FastAPI request object

    Returns:
        User data dict

    Raises:
        HTTPException: 401 if not authenticated
    """
    user = get_current_user(request)
    if not user:
        logger.warning(f"Unauthorized access attempt to {request.url.path}")
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in."
        )
    return user


def get_jwt_token(request: Request) -> Optional[str]:
    """
    Extract JWT token from request (session or header).

    Args:
        request: FastAPI request object

    Returns:
        JWT token string if found, None otherwise
    """
    user = get_current_user(request)
    if user:
        return user.get("jwt_token")
    return None


# Session statistics (for monitoring)
def get_session_stats() -> Dict[str, Any]:
    """
    Get session statistics for monitoring.

    Returns:
        Dictionary with session statistics
    """
    active_sessions = len(user_sessions)
    now = datetime.now()

    recent_sessions = sum(
        1 for s in user_sessions.values()
        if (now - s.get("last_accessed", now)).total_seconds() < 300  # Active in last 5 min
    )

    return {
        "total_sessions": active_sessions,
        "recent_active": recent_sessions,
        "last_cleanup": now.isoformat()
    }

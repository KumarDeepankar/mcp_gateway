#!/usr/bin/env python3
"""
OAuth 2.1 Authentication Module for Tools Gateway
Supports multiple OAuth providers: Google, Microsoft, GitHub
Implements MCP-compliant authentication with token management
Uses SQLite database for provider storage
"""
import asyncio
import logging
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode, parse_qs, urlparse
import aiohttp
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from database import database

logger = logging.getLogger(__name__)


class OAuthProvider(BaseModel):
    """OAuth Provider Configuration"""
    provider_id: str
    provider_name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: List[str] = Field(default_factory=list)
    enabled: bool = True


class OAuthToken(BaseModel):
    """OAuth Token"""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    issued_at: datetime = Field(default_factory=datetime.now)

    def is_expired(self) -> bool:
        """Check if token is expired"""
        expiry = self.issued_at + timedelta(seconds=self.expires_in)
        return datetime.now() >= expiry


class UserInfo(BaseModel):
    """User information from OAuth provider"""
    sub: str  # Subject (user ID)
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    provider: str
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class OAuthState(BaseModel):
    """OAuth state for CSRF protection"""
    state: str
    provider_id: str
    redirect_uri: str
    code_verifier: str  # PKCE code verifier
    created_at: datetime = Field(default_factory=datetime.now)

    def is_expired(self, timeout_seconds: int = 600) -> bool:
        """Check if state is expired (default 10 minutes)"""
        age = datetime.now() - self.created_at
        return age.total_seconds() > timeout_seconds


class OAuthProviderManager:
    """
    Manages OAuth 2.1 providers with PKCE support
    Implements secure authentication flow per OAuth 2.1 spec
    """

    # Built-in provider templates
    PROVIDER_TEMPLATES = {
        "google": {
            "provider_name": "Google",
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
            "scopes": ["openid", "email", "profile"]
        },
        "microsoft": {
            "provider_name": "Microsoft",
            "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "userinfo_url": "https://graph.microsoft.com/v1.0/me",
            "scopes": ["openid", "email", "profile"]
        },
        "github": {
            "provider_name": "GitHub",
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "scopes": ["read:user", "user:email"]
        }
    }

    def __init__(self):
        """Initialize OAuth provider manager with SQLite database backend"""
        self.providers: Dict[str, OAuthProvider] = {}  # In-memory cache for faster access
        self.pending_states: Dict[str, OAuthState] = {}  # OAuth state tracking
        self._load_providers()
        logger.info("OAuthProviderManager initialized with SQLite database backend")

    def _load_providers(self):
        """Load providers from database into memory cache"""
        try:
            providers_data = database.get_all_oauth_providers()
            for provider_data in providers_data:
                provider = OAuthProvider(**provider_data)
                self.providers[provider.provider_id] = provider
            logger.info(f"Loaded {len(self.providers)} OAuth providers from database")
        except Exception as e:
            logger.error(f"Error loading OAuth providers: {e}")

    def _save_provider_to_db(self, provider: OAuthProvider):
        """Save single provider to database"""
        try:
            database.save_oauth_provider(
                provider_id=provider.provider_id,
                provider_name=provider.provider_name,
                client_id=provider.client_id,
                client_secret=provider.client_secret,
                authorize_url=provider.authorize_url,
                token_url=provider.token_url,
                userinfo_url=provider.userinfo_url,
                scopes=provider.scopes,
                enabled=provider.enabled
            )
        except Exception as e:
            logger.error(f"Error saving OAuth provider: {e}")

    def add_provider(self, provider_id: str, client_id: str, client_secret: str,
                     template: Optional[str] = None, **kwargs) -> OAuthProvider:
        """Add OAuth provider"""
        if template and template in self.PROVIDER_TEMPLATES:
            template_data = self.PROVIDER_TEMPLATES[template].copy()
            template_data.update(kwargs)
            kwargs = template_data

        provider = OAuthProvider(
            provider_id=provider_id,
            client_id=client_id,
            client_secret=client_secret,
            **kwargs
        )

        # Save to database
        self._save_provider_to_db(provider)

        # Update in-memory cache
        self.providers[provider_id] = provider

        logger.info(f"Added OAuth provider: {provider_id}")
        return provider

    def remove_provider(self, provider_id: str) -> bool:
        """Remove OAuth provider"""
        if provider_id in self.providers:
            # Remove from database
            database.delete_oauth_provider(provider_id)

            # Remove from cache
            del self.providers[provider_id]

            logger.info(f"Removed OAuth provider: {provider_id}")
            return True
        return False

    def get_provider(self, provider_id: str) -> Optional[OAuthProvider]:
        """Get OAuth provider from cache (or reload from database if not found)"""
        provider = self.providers.get(provider_id)
        if not provider:
            # Try to reload from database
            provider_data = database.get_oauth_provider(provider_id)
            if provider_data:
                provider = OAuthProvider(**provider_data)
                self.providers[provider_id] = provider  # Update cache
        return provider

    def list_providers(self) -> List[Dict[str, Any]]:
        """List all providers (without secrets)"""
        return [
            {
                "provider_id": p.provider_id,
                "provider_name": p.provider_name,
                "enabled": p.enabled,
                "scopes": p.scopes
            }
            for p in self.providers.values()
        ]

    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge per OAuth 2.1"""
        import base64

        # Generate code verifier (43-128 characters)
        code_verifier = secrets.token_urlsafe(96)[:128]

        # Generate code challenge (SHA256 hash of verifier, base64url encoded)
        challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')

        return code_verifier, code_challenge

    def create_authorization_url(self, provider_id: str, redirect_uri: str) -> Optional[Dict[str, str]]:
        """
        Create authorization URL with PKCE for OAuth 2.1 flow
        Returns: {url, state} or None if provider not found
        """
        provider = self.get_provider(provider_id)
        if not provider or not provider.enabled:
            logger.error(f"Provider {provider_id} not found or disabled")
            return None

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Generate PKCE pair
        code_verifier, code_challenge = self._generate_pkce_pair()

        # Store state
        oauth_state = OAuthState(
            state=state,
            provider_id=provider_id,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier
        )
        self.pending_states[state] = oauth_state

        # Build authorization URL
        params = {
            "client_id": provider.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(provider.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }

        auth_url = f"{provider.authorize_url}?{urlencode(params)}"

        logger.info(f"Created authorization URL for provider {provider_id}")
        return {
            "url": auth_url,
            "state": state
        }

    async def exchange_code_for_token(self, code: str, state: str) -> Optional[tuple[OAuthToken, str]]:
        """
        Exchange authorization code for access token
        Returns: (token, provider_id) or None
        """
        # Validate state
        oauth_state = self.pending_states.get(state)
        if not oauth_state:
            logger.error("Invalid or expired state")
            return None

        if oauth_state.is_expired():
            del self.pending_states[state]
            logger.error("State expired")
            return None

        provider = self.get_provider(oauth_state.provider_id)
        if not provider:
            logger.error(f"Provider {oauth_state.provider_id} not found")
            return None

        # Exchange code for token with PKCE
        token_params = {
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "code": code,
            "redirect_uri": oauth_state.redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": oauth_state.code_verifier
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    provider.token_url,
                    data=token_params,
                    headers={"Accept": "application/json"}
                ) as response:
                    if response.status == 200:
                        token_data = await response.json()

                        # Create token object
                        token = OAuthToken(
                            access_token=token_data["access_token"],
                            token_type=token_data.get("token_type", "Bearer"),
                            expires_in=token_data.get("expires_in", 3600),
                            refresh_token=token_data.get("refresh_token"),
                            scope=token_data.get("scope")
                        )

                        # Clean up state
                        del self.pending_states[state]

                        logger.info(f"Successfully exchanged code for token: {provider.provider_id}")
                        return token, provider.provider_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Token exchange failed: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Error during token exchange: {e}")
            return None

    async def get_user_info(self, provider_id: str, access_token: str) -> Optional[UserInfo]:
        """Get user information from OAuth provider"""
        provider = self.get_provider(provider_id)
        if not provider:
            logger.error(f"Provider {provider_id} not found")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }

                async with session.get(provider.userinfo_url, headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()

                        # Normalize user info across providers
                        email = user_data.get("email")
                        if not email and provider_id == "github":
                            # GitHub may require separate email endpoint
                            email = await self._get_github_email(session, access_token)

                        user_info = UserInfo(
                            sub=user_data.get("id") or user_data.get("sub") or user_data.get("oid"),
                            email=email,
                            name=user_data.get("name") or user_data.get("displayName") or user_data.get("login"),
                            picture=user_data.get("picture") or user_data.get("avatar_url"),
                            provider=provider_id,
                            raw_data=user_data
                        )

                        logger.info(f"Retrieved user info for {user_info.email} from {provider_id}")
                        return user_info
                    else:
                        logger.error(f"Failed to get user info: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    async def _get_github_email(self, session: aiohttp.ClientSession, access_token: str) -> Optional[str]:
        """Get primary email from GitHub (separate endpoint)"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            async with session.get("https://api.github.com/user/emails", headers=headers) as response:
                if response.status == 200:
                    emails = await response.json()
                    # Find primary verified email
                    for email_obj in emails:
                        if email_obj.get("primary") and email_obj.get("verified"):
                            return email_obj.get("email")
        except Exception as e:
            logger.error(f"Error getting GitHub email: {e}")
        return None


class JWTManager:
    """
    Manages JWT tokens for MCP gateway authentication
    Issues short-lived access tokens after OAuth validation
    """

    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        self.secret_key = secret_key or secrets.token_urlsafe(64)
        self.algorithm = algorithm
        self.token_expiry_minutes = 480  # 8 hours (for development/admin sessions)

    def create_access_token(self, user_info: UserInfo, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.token_expiry_minutes)

        expire = datetime.utcnow() + expires_delta

        payload = {
            "sub": user_info.sub,
            "email": user_info.email,
            "name": user_info.name,
            "provider": user_info.provider,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Created access token for {user_info.email}")
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"Token verification failed: {e}")
            return None


# Singleton instances
oauth_provider_manager = OAuthProviderManager()
jwt_manager = JWTManager()

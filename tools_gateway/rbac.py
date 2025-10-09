#!/usr/bin/env python3
"""
Role-Based Access Control (RBAC) Module for Tools Gateway
Manages users, roles, and permissions for MCP servers and tools
Uses SQLite database for storage
"""
import logging
import secrets
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from enum import Enum
from pydantic import BaseModel, Field
from database import database

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """System permissions"""
    # MCP Server permissions
    SERVER_VIEW = "server:view"
    SERVER_ADD = "server:add"
    SERVER_EDIT = "server:edit"
    SERVER_DELETE = "server:delete"
    SERVER_TEST = "server:test"

    # Tool permissions
    TOOL_VIEW = "tool:view"
    TOOL_EXECUTE = "tool:execute"
    TOOL_MANAGE = "tool:manage"

    # Configuration permissions
    CONFIG_VIEW = "config:view"
    CONFIG_EDIT = "config:edit"

    # User management permissions
    USER_VIEW = "user:view"
    USER_MANAGE = "user:manage"

    # Role management permissions
    ROLE_VIEW = "role:view"
    ROLE_MANAGE = "role:manage"

    # Audit permissions
    AUDIT_VIEW = "audit:view"

    # OAuth permissions
    OAUTH_MANAGE = "oauth:manage"


class Role(BaseModel):
    """Role definition"""
    role_id: str
    role_name: str
    description: str
    permissions: Set[Permission] = Field(default_factory=set)
    is_system: bool = False  # System roles cannot be deleted
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class User(BaseModel):
    """User definition"""
    user_id: str
    email: str
    name: Optional[str] = None
    provider: Optional[str] = None  # OAuth provider
    roles: Set[str] = Field(default_factory=set)  # Role IDs
    mcp_server_access: Dict[str, Set[str]] = Field(default_factory=dict)  # server_id -> tool_names
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None


class MCPServerPermission(BaseModel):
    """MCP Server-specific permissions"""
    server_id: str
    role_id: str
    allowed_tools: Set[str] = Field(default_factory=set)  # Empty set = all tools
    can_view: bool = True
    can_execute: bool = True
    can_manage: bool = False


class RBACManager:
    """
    Role-Based Access Control Manager
    Manages users, roles, and permissions
    """

    # Default system roles
    DEFAULT_ROLES = {
        "admin": Role(
            role_id="admin",
            role_name="Administrator",
            description="Full system access",
            permissions={
                Permission.SERVER_VIEW, Permission.SERVER_ADD, Permission.SERVER_EDIT,
                Permission.SERVER_DELETE, Permission.SERVER_TEST,
                Permission.TOOL_VIEW, Permission.TOOL_EXECUTE, Permission.TOOL_MANAGE,
                Permission.CONFIG_VIEW, Permission.CONFIG_EDIT,
                Permission.USER_VIEW, Permission.USER_MANAGE,
                Permission.ROLE_VIEW, Permission.ROLE_MANAGE,
                Permission.AUDIT_VIEW, Permission.OAUTH_MANAGE
            },
            is_system=True
        ),
        "user": Role(
            role_id="user",
            role_name="Standard User",
            description="Basic user access",
            permissions={
                Permission.SERVER_VIEW, Permission.TOOL_VIEW,
                Permission.TOOL_EXECUTE, Permission.CONFIG_VIEW
            },
            is_system=True
        ),
        "viewer": Role(
            role_id="viewer",
            role_name="Viewer",
            description="Read-only access",
            permissions={
                Permission.SERVER_VIEW, Permission.TOOL_VIEW,
                Permission.CONFIG_VIEW
            },
            is_system=True
        )
    }

    def __init__(self):
        """Initialize RBAC manager with SQLite database backend"""
        self._initialize_default_roles()
        logger.info("RBACManager initialized with SQLite database backend")

    def _initialize_default_roles(self):
        """Ensure default roles exist in database"""
        for role_id, role in self.DEFAULT_ROLES.items():
            existing = database.get_role(role_id)
            if not existing:
                # Create default role
                database.save_role(
                    role_id=role.role_id,
                    role_name=role.role_name,
                    description=role.description,
                    permissions=[p.value for p in role.permissions],
                    is_system=role.is_system
                )
                logger.info(f"Created default role: {role.role_name}")

    def _load_data(self):
        """No-op: Data is loaded from database on demand"""
        pass

    def _save_data(self):
        """No-op: Data is saved directly to database in each method"""
        pass

    # --- Role Management ---

    def create_role(self, role_name: str, description: str,
                    permissions: Optional[Set[Permission]] = None) -> Role:
        """Create a new role"""
        role_id = f"role_{secrets.token_urlsafe(8)}"

        # Convert permissions to list of strings
        perm_list = [p.value for p in (permissions or set())]

        # Save to database
        database.save_role(
            role_id=role_id,
            role_name=role_name,
            description=description,
            permissions=perm_list,
            is_system=False
        )

        logger.info(f"Created role: {role_name} ({role_id})")

        # Return role object
        role = Role(
            role_id=role_id,
            role_name=role_name,
            description=description,
            permissions=permissions or set(),
            is_system=False
        )
        return role

    def update_role(self, role_id: str, role_name: Optional[str] = None,
                    description: Optional[str] = None,
                    permissions: Optional[Set[Permission]] = None) -> Optional[Role]:
        """Update a role"""
        # Get role from database
        role_data = database.get_role(role_id)
        if not role_data:
            logger.error(f"Role {role_id} not found")
            return None

        if role_data.get('is_system'):
            logger.error(f"Cannot modify system role: {role_id}")
            return None

        # Update fields
        if role_name:
            role_data['role_name'] = role_name
        if description:
            role_data['description'] = description
        if permissions is not None:
            role_data['permissions'] = [p.value for p in permissions]

        # Save to database
        database.save_role(
            role_id=role_id,
            role_name=role_data['role_name'],
            description=role_data['description'],
            permissions=role_data['permissions'],
            is_system=role_data['is_system']
        )

        logger.info(f"Updated role: {role_id}")

        # Return role object
        return Role(
            role_id=role_id,
            role_name=role_data['role_name'],
            description=role_data['description'],
            permissions={Permission(p) for p in role_data['permissions']},
            is_system=role_data['is_system']
        )

    def delete_role(self, role_id: str) -> bool:
        """Delete a role"""
        # Use database.delete_role() which handles system role check and cascade deletion
        result = database.delete_role(role_id)
        if result:
            logger.info(f"Deleted role: {role_id}")
        return result

    def get_role(self, role_id: str) -> Optional[Role]:
        """Get role by ID"""
        role_data = database.get_role(role_id)
        if not role_data:
            return None

        # Convert database dict to Role object with Permission enums
        return Role(
            role_id=role_data['role_id'],
            role_name=role_data['role_name'],
            description=role_data['description'],
            permissions={Permission(p) for p in role_data['permissions']},
            is_system=role_data['is_system']
        )

    def list_roles(self) -> List[Dict[str, Any]]:
        """List all roles"""
        roles_data = database.get_all_roles()
        all_users = database.get_all_users()

        result = []
        for role_data in roles_data:
            # Count users with this role
            user_count = sum(1 for u in all_users if role_data['role_id'] in u.get('roles', []))

            result.append({
                "role_id": role_data['role_id'],
                "role_name": role_data['role_name'],
                "description": role_data['description'],
                "permissions": role_data['permissions'],  # Already a list of strings from database
                "is_system": role_data['is_system'],
                "user_count": user_count
            })

        return result

    # --- User Management ---

    def create_user(self, email: str, name: Optional[str] = None,
                    provider: Optional[str] = None,
                    roles: Optional[Set[str]] = None) -> User:
        """Create a new user"""
        user_id = f"user_{secrets.token_urlsafe(12)}"

        # Default to 'user' role if none specified
        if roles is None:
            roles = {"user"}

        # Save user to database
        database.save_user(
            user_id=user_id,
            email=email,
            name=name,
            provider=provider,
            enabled=True
        )

        # Assign roles
        for role_id in roles:
            database.assign_role_to_user(user_id, role_id)

        logger.info(f"Created user: {email} ({user_id})")

        # Return user object
        user = User(
            user_id=user_id,
            email=email,
            name=name,
            provider=provider,
            roles=roles
        )
        return user

    def get_or_create_user(self, email: str, name: Optional[str] = None,
                           provider: Optional[str] = None) -> User:
        """Get existing user by email or create new one"""
        # Try to get existing user from database
        user_data = database.get_user_by_email(email)

        if user_data:
            # Update last login
            database.update_user_last_login(user_data['user_id'])

            # Convert to User object
            return User(
                user_id=user_data['user_id'],
                email=user_data['email'],
                name=user_data.get('name'),
                provider=user_data.get('provider'),
                roles=set(user_data.get('roles', [])),
                enabled=user_data.get('enabled', True),
                created_at=datetime.fromisoformat(user_data['created_at']) if user_data.get('created_at') else datetime.now(),
                last_login=datetime.now()
            )

        # Create new user
        return self.create_user(email, name, provider)

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        user_data = database.get_user(user_id)
        if not user_data:
            return None

        # Convert to User object
        return User(
            user_id=user_data['user_id'],
            email=user_data['email'],
            name=user_data.get('name'),
            provider=user_data.get('provider'),
            roles=set(user_data.get('roles', [])),
            enabled=user_data.get('enabled', True),
            created_at=datetime.fromisoformat(user_data['created_at']) if user_data.get('created_at') else datetime.now(),
            last_login=datetime.fromisoformat(user_data['last_login']) if user_data.get('last_login') else None
        )

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        user_data = database.get_user_by_email(email)
        if not user_data:
            return None

        # Convert to User object
        return User(
            user_id=user_data['user_id'],
            email=user_data['email'],
            name=user_data.get('name'),
            provider=user_data.get('provider'),
            roles=set(user_data.get('roles', [])),
            enabled=user_data.get('enabled', True),
            created_at=datetime.fromisoformat(user_data['created_at']) if user_data.get('created_at') else datetime.now(),
            last_login=datetime.fromisoformat(user_data['last_login']) if user_data.get('last_login') else None
        )

    def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        """Update user"""
        # Get current user data
        user_data = database.get_user(user_id)
        if not user_data:
            logger.error(f"User {user_id} not found")
            return None

        # Update fields (only those that are in the database schema)
        email = kwargs.get('email', user_data['email'])
        name = kwargs.get('name', user_data.get('name'))
        provider = kwargs.get('provider', user_data.get('provider'))
        enabled = kwargs.get('enabled', user_data.get('enabled', True))

        # Save updated user to database
        database.save_user(
            user_id=user_id,
            email=email,
            name=name,
            provider=provider,
            enabled=enabled
        )

        logger.info(f"Updated user: {user_id}")

        # Fetch updated user and return as User object
        return self.get_user(user_id)

    def assign_role(self, user_id: str, role_id: str) -> bool:
        """Assign role to user"""
        # Check if user exists
        user_data = database.get_user(user_id)
        if not user_data:
            logger.error(f"User {user_id} not found")
            return False

        # Check if role exists
        role_data = database.get_role(role_id)
        if not role_data:
            logger.error(f"Role {role_id} not found")
            return False

        # Assign role using database
        result = database.assign_role_to_user(user_id, role_id)
        if result:
            logger.info(f"Assigned role {role_id} to user {user_id}")
        return result

    def revoke_role(self, user_id: str, role_id: str) -> bool:
        """Revoke role from user"""
        # Use database to revoke role
        result = database.revoke_role_from_user(user_id, role_id)
        if result:
            logger.info(f"Revoked role {role_id} from user {user_id}")
        return result

    def list_users(self) -> List[Dict[str, Any]]:
        """List all users"""
        users_data = database.get_all_users()
        all_roles = database.get_all_roles()

        # Create a mapping of role_id to role_name for efficient lookup
        role_names = {role['role_id']: role['role_name'] for role in all_roles}

        result = []
        for user_data in users_data:
            # Map role IDs to role names
            user_role_ids = user_data.get('roles', [])
            user_role_names = [role_names[rid] for rid in user_role_ids if rid in role_names]

            result.append({
                "user_id": user_data['user_id'],
                "email": user_data['email'],
                "name": user_data.get('name'),
                "provider": user_data.get('provider'),
                "roles": user_role_names,
                "enabled": user_data.get('enabled', True),
                "created_at": user_data.get('created_at'),
                "last_login": user_data.get('last_login')
            })

        return result

    # --- Permission Checking ---

    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has a specific permission"""
        # Get user from database
        user_data = database.get_user(user_id)
        if not user_data or not user_data.get('enabled', True):
            return False

        # Check all user's roles for the permission
        for role_id in user_data.get('roles', []):
            role_data = database.get_role(role_id)
            if role_data and permission.value in role_data['permissions']:
                return True

        return False

    def has_any_permission(self, user_id: str, permissions: List[Permission]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(self.has_permission(user_id, perm) for perm in permissions)

    def has_all_permissions(self, user_id: str, permissions: List[Permission]) -> bool:
        """Check if user has all of the specified permissions"""
        return all(self.has_permission(user_id, perm) for perm in permissions)

    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """Get all permissions for a user"""
        # Get user from database
        user_data = database.get_user(user_id)
        if not user_data or not user_data.get('enabled', True):
            return set()

        # Aggregate permissions from all user's roles
        permissions = set()
        for role_id in user_data.get('roles', []):
            role_data = database.get_role(role_id)
            if role_data:
                # Convert permission strings to Permission enums
                for perm_str in role_data['permissions']:
                    try:
                        permissions.add(Permission(perm_str))
                    except ValueError:
                        logger.warning(f"Invalid permission string: {perm_str}")

        return permissions

    # --- MCP Server Access Control ---
    # Note: Server access is stored in the user_server_access table in the database

    def grant_server_access(self, user_id: str, server_id: str,
                           allowed_tools: Optional[Set[str]] = None):
        """Grant user access to specific MCP server"""
        # Check if user exists
        user_data = database.get_user(user_id)
        if not user_data:
            logger.error(f"User {user_id} not found")
            return False

        if allowed_tools is None:
            allowed_tools = set()  # Empty = all tools

        # Note: For now, we'll store this in-memory since user_server_access table
        # isn't fully implemented yet. This is a limitation to address later.
        # TODO: Implement user_server_access table operations in database.py

        logger.warning(f"grant_server_access not yet implemented with database - needs user_server_access table support")
        logger.info(f"Would grant server {server_id} access to user {user_id}")
        return True

    def revoke_server_access(self, user_id: str, server_id: str) -> bool:
        """Revoke user access to MCP server"""
        # TODO: Implement with database user_server_access table
        logger.warning(f"revoke_server_access not yet implemented with database - needs user_server_access table support")
        logger.info(f"Would revoke server {server_id} access from user {user_id}")
        return True

    def can_access_server(self, user_id: str, server_id: str) -> bool:
        """Check if user can access a specific server"""
        user_data = database.get_user(user_id)
        if not user_data or not user_data.get('enabled', True):
            return False

        # Admins can access all servers
        if self.has_permission(user_id, Permission.TOOL_MANAGE):
            return True

        # TODO: Check explicit server access from user_server_access table
        # For now, users with TOOL_VIEW or TOOL_EXECUTE can access all servers
        return self.has_permission(user_id, Permission.TOOL_VIEW)

    def can_execute_tool(self, user_id: str, server_id: str, tool_name: str) -> bool:
        """Check if user can execute a specific tool on a server"""
        user_data = database.get_user(user_id)
        if not user_data or not user_data.get('enabled', True):
            return False

        # Must have tool execute permission
        if not self.has_permission(user_id, Permission.TOOL_EXECUTE):
            return False

        # Admins can execute all tools
        if self.has_permission(user_id, Permission.TOOL_MANAGE):
            return True

        # TODO: Check server access and tool restrictions from user_server_access table
        # For now, if user has TOOL_EXECUTE permission, they can execute on all servers
        return self.can_access_server(user_id, server_id)


# Singleton instance
rbac_manager = RBACManager()

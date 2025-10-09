#!/usr/bin/env python3
"""
Migration script from pickle files to SQLite database
Safely migrates all existing pickle-based storage to SQLite
"""
import pickle
import logging
from pathlib import Path
from datetime import datetime
from database import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_rbac_data():
    """Migrate RBAC data from pickle to SQLite"""
    pickle_file = Path("rbac_data.pkl")
    if not pickle_file.exists():
        logger.info("No RBAC pickle file found, skipping...")
        return

    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)

        # Migrate roles
        roles_migrated = 0
        for role_data in data.get("roles", []):
            permissions = role_data.get("permissions", [])
            # Convert Permission enum to strings
            if permissions and isinstance(permissions[0], str):
                pass  # Already strings
            else:
                permissions = [str(p.value) if hasattr(p, 'value') else str(p) for p in permissions]

            database.save_role(
                role_id=role_data["role_id"],
                role_name=role_data["role_name"],
                description=role_data["description"],
                permissions=permissions,
                is_system=role_data.get("is_system", False)
            )
            roles_migrated += 1

        # Migrate users
        users_migrated = 0
        for user_data in data.get("users", []):
            database.save_user(
                user_id=user_data["user_id"],
                email=user_data["email"],
                name=user_data.get("name"),
                provider=user_data.get("provider"),
                enabled=user_data.get("enabled", True)
            )

            # Assign roles
            for role_id in user_data.get("roles", []):
                database.assign_role_to_user(user_data["user_id"], role_id)

            users_migrated += 1

        logger.info(f"✓ Migrated {roles_migrated} roles and {users_migrated} users from RBAC pickle")

        # Backup pickle file
        pickle_file.rename(pickle_file.with_suffix('.pkl.migrated'))

    except Exception as e:
        logger.error(f"Error migrating RBAC data: {e}")


def migrate_ad_mappings():
    """Migrate AD mappings from pickle to SQLite"""
    pickle_file = Path("ad_mappings.pkl")
    if not pickle_file.exists():
        logger.info("No AD mappings pickle file found, skipping...")
        return

    try:
        with open(pickle_file, 'rb') as f:
            mappings = pickle.load(f)

        migrated = 0
        for mapping_id, mapping in mappings.items():
            database.save_ad_mapping(
                mapping_id=mapping.mapping_id,
                group_dn=mapping.group_dn,
                role_id=mapping.role_id,
                auto_sync=mapping.auto_sync,
                synced_users=mapping.synced_users
            )
            migrated += 1

        logger.info(f"✓ Migrated {migrated} AD group mappings")

        # Backup pickle file
        pickle_file.rename(pickle_file.with_suffix('.pkl.migrated'))

    except Exception as e:
        logger.error(f"Error migrating AD mappings: {e}")


def migrate_mcp_servers():
    """Migrate MCP servers from pickle to SQLite"""
    pickle_file = Path("mcp_configs.pkl")
    if not pickle_file.exists():
        logger.info("No MCP servers pickle file found, skipping...")
        return

    try:
        with open(pickle_file, 'rb') as f:
            servers = pickle.load(f)

        migrated = 0
        for server_id, server_data in servers.items():
            database.save_mcp_server(
                server_id=server_data["server_id"],
                name=server_data["name"],
                url=server_data["url"],
                description=server_data.get("description", ""),
                capabilities=server_data.get("capabilities", {}),
                metadata=server_data.get("metadata", {}),
                registered_via=server_data.get("registered_via", "ui")
            )
            migrated += 1

        logger.info(f"✓ Migrated {migrated} MCP servers")

        # Backup pickle file
        pickle_file.rename(pickle_file.with_suffix('.pkl.migrated'))

    except Exception as e:
        logger.error(f"Error migrating MCP servers: {e}")


def migrate_oauth_providers():
    """Migrate OAuth providers from pickle to SQLite"""
    pickle_file = Path("oauth_providers.pkl")
    if not pickle_file.exists():
        logger.info("No OAuth providers pickle file found, skipping...")
        return

    try:
        with open(pickle_file, 'rb') as f:
            providers = pickle.load(f)

        migrated = 0
        for provider_data in providers:
            database.save_oauth_provider(
                provider_id=provider_data["provider_id"],
                provider_name=provider_data["provider_name"],
                client_id=provider_data["client_id"],
                client_secret=provider_data["client_secret"],
                authorize_url=provider_data["authorize_url"],
                token_url=provider_data["token_url"],
                userinfo_url=provider_data["userinfo_url"],
                scopes=provider_data.get("scopes", []),
                enabled=provider_data.get("enabled", True)
            )
            migrated += 1

        logger.info(f"✓ Migrated {migrated} OAuth providers")

        # Backup pickle file
        pickle_file.rename(pickle_file.with_suffix('.pkl.migrated'))

    except Exception as e:
        logger.error(f"Error migrating OAuth providers: {e}")


def migrate_gateway_config():
    """Migrate gateway configuration from pickle to SQLite"""
    pickle_file = Path("gateway_config.pkl")
    if not pickle_file.exists():
        logger.info("No gateway config pickle file found, skipping...")
        return

    try:
        with open(pickle_file, 'rb') as f:
            config_data = pickle.load(f)

        # Save connection health config
        if "connection_health" in config_data:
            database.save_config("connection_health", config_data["connection_health"])

        # Save origin config
        if "origin" in config_data:
            database.save_config("origin", config_data["origin"])

        logger.info("✓ Migrated gateway configuration")

        # Backup pickle file
        pickle_file.rename(pickle_file.with_suffix('.pkl.migrated'))

    except Exception as e:
        logger.error(f"Error migrating gateway config: {e}")


def main():
    """Run all migrations"""
    logger.info("=" * 60)
    logger.info("Starting migration from pickle files to SQLite")
    logger.info("=" * 60)

    # Run migrations in order
    migrate_rbac_data()
    migrate_ad_mappings()
    migrate_mcp_servers()
    migrate_oauth_providers()
    migrate_gateway_config()

    logger.info("=" * 60)
    logger.info("Migration completed successfully!")
    logger.info("All pickle files have been renamed to *.pkl.migrated")
    logger.info("You can safely delete them after verifying the migration")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

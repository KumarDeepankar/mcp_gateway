# SQLite Migration Guide

This document outlines the complete migration from pickle files to SQLite database for the Tools Gateway.

## Overview

All pickle-based storage has been replaced with SQLite for:
- Better concurrency and thread safety
- ACID transactions
- Query capabilities
- Data integrity with foreign keys
- Standard backup/restore procedures

## New Files Created

### 1. `database.py`
- Comprehensive SQLite database manager
- Thread-safe with connection pooling
- Schema version tracking and migrations
- Full CRUD operations for all entities

### 2. `migrate_to_sqlite.py`
- One-time migration script
- Safely converts all pickle files to SQLite
- Creates backups of pickle files

## Migration Steps

### Step 1: Run Migration (One-time)
```bash
cd /Users/deepankar/Documents/mcp_gateway/tools_gateway
python3 migrate_to_sqlite.py
```

This will:
- Create `tools_gateway.db` SQLite database
- Migrate all data from pickle files
- Rename pickle files to `*.pkl.migrated`

### Step 2: Update Each Module

All modules need to be updated to use the new `database` module instead of pickle.

## Module Updates Required

### A. `rbac.py` - RBAC Manager

**Changes needed:**
1. Remove `import pickle` and pickle-related code
2. Add `from database import database`
3. Replace `_load_data()` with database queries
4. Replace `_save_data()` with database operations
5. Update all CRUD methods to use database

**Key method changes:**
```python
# OLD (pickle):
def _load_data(self):
    with open(self.storage_file, 'rb') as f:
        data = pickle.load(f)

# NEW (SQLite):
def _load_data(self):
    # Roles are loaded on-demand from database
    pass  # No need to load everything into memory

# OLD:
def create_role(...):
    role = Role(...)
    self.roles[role_id] = role
    self._save_data()

# NEW:
def create_role(...):
    database.save_role(role_id, role_name, description, permissions, is_system)
```

### B. `ad_integration.py` - AD Integration

**Changes needed:**
1. Remove pickle imports
2. Add `from database import database`
3. Update `_load_mappings()` to use `database.get_all_ad_mappings()`
4. Update `_save_mappings()` to use `database.save_ad_mapping()`
5. Update all mapping operations

### C. `mcp_storage.py` - MCP Server Storage

**Changes needed:**
1. Remove pickle and aiofiles for pickle
2. Add `from database import database`
3. Replace `_load_from_disk()` with database queries
4. Replace `_save_to_disk()` with database operations
5. Remove async locks (database handles concurrency)

**Note:** Keep async methods for HTTP operations, but storage is now synchronous.

### D. `auth.py` - OAuth Provider Manager

**Changes needed:**
1. Remove pickle imports in `OAuthProviderManager`
2. Add `from database import database`
3. Update `_load_providers()` to use `database.get_all_oauth_providers()`
4. Update `_save_providers()` to use `database.save_oauth_provider()`

### E. `config.py` - Configuration Manager

**Changes needed:**
1. Remove pickle imports
2. Add `from database import database`
3. Update `_load_config()` to use `database.get_config()`
4. Update `_save_config()` to use `database.save_config()`
5. Keep in-memory caching for performance

## Benefits of Migration

### 1. **Concurrency**
- Multiple threads/processes can safely access database
- No more pickle file locking issues
- WAL mode for better concurrent reads

### 2. **Data Integrity**
- Foreign key constraints ensure referential integrity
- Transactions prevent partial updates
- Schema validation

### 3. **Performance**
- Indexed queries for fast lookups
- Only load needed data (not entire pickle file)
- Efficient updates (no full file rewrite)

### 4. **Query Capabilities**
- Complex queries across relations
- Filtering, sorting, aggregations
- Easy to add reporting features

### 5. **Backup & Recovery**
- Standard SQLite backup tools
- Point-in-time recovery possible
- Easy to export/import

## Database Schema

See `database.py` for full schema. Key tables:

- `mcp_servers` - MCP server configurations
- `oauth_providers` - OAuth provider credentials
- `rbac_roles` - RBAC roles and permissions
- `rbac_users` - User accounts
- `user_roles` - User-role assignments (many-to-many)
- `ad_group_mappings` - AD group to role mappings
- `gateway_config` - Gateway configuration key-value store

## Testing After Migration

1. **Verify Data Migration:**
   ```bash
   sqlite3 tools_gateway.db ".tables"
   sqlite3 tools_gateway.db "SELECT COUNT(*) FROM rbac_users;"
   ```

2. **Test API Endpoints:**
   - OAuth login flow
   - User/role management
   - MCP server registration
   - AD group sync

3. **Check Logs:**
   - No pickle-related errors
   - Database operations logging correctly

## Rollback Plan

If issues arise:

1. Stop the service
2. Rename `*.pkl.migrated` back to `*.pkl`
3. Restore old code from git
4. Restart service

## Performance Considerations

### Connection Pooling
- Thread-local connections
- Automatic connection reuse
- WAL mode for concurrent reads

### Indexing
- Indexes on frequently queried fields
- See SCHEMA in `database.py`

### Caching
- Keep in-memory caching where beneficial (e.g., origin validation)
- Cache invalidation on database updates

## Future Enhancements

With SQLite, we can easily add:

1. **Audit Trail**: Track all changes with timestamps
2. **User Sessions**: Store active sessions in database
3. **Rate Limiting**: Database-backed rate limit counters
4. **Analytics**: Query historical data for insights
5. **Multi-tenancy**: Add tenant_id to tables

## Maintenance

### Vacuum Database (optional, monthly)
```bash
sqlite3 tools_gateway.db "VACUUM;"
```

### Backup Database
```bash
sqlite3 tools_gateway.db ".backup tools_gateway_backup.db"
```

### Check Database Integrity
```bash
sqlite3 tools_gateway.db "PRAGMA integrity_check;"
```

## Support

For issues or questions about the migration, check:
- Database logs in application logs
- SQLite error messages
- This migration guide

## Completion Checklist

- [x] Create `database.py` module
- [x] Create migration script
- [ ] Update `rbac.py`
- [ ] Update `ad_integration.py`
- [ ] Update `mcp_storage.py`
- [ ] Update `auth.py`
- [ ] Update `config.py`
- [ ] Run migration script
- [ ] Test all functionality
- [ ] Remove pickle dependencies from `requirements.txt`
- [ ] Update documentation


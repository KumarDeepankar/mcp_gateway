# Tools Gateway - Directory Structure

**Last Updated**: October 9, 2025

## Overview

The tools_gateway directory has been reorganized for better maintainability and clarity. All files are now properly categorized.

---

## Directory Layout

```
tools_gateway/
├── docs/                           # Documentation files
│   ├── DIRECTORY_STRUCTURE.md      # This file
│   ├── ENTERPRISE_SECURITY_GUIDE.md
│   ├── MIGRATION_COMPLETE.md
│   ├── OAUTH_UI_GUIDE.md
│   ├── QUICKSTART.md
│   ├── SQLITE_MIGRATION_GUIDE.md
│   ├── SQLITE_MIGRATION_SUMMARY.md
│   ├── TEST_RESULTS.md
│   └── UI_TESTING_GUIDE.md
│
├── migrations/                     # Database migration scripts
│   ├── migrate_audit_logs.py       # Migrates audit logs from files to SQLite
│   └── migrate_to_sqlite.py        # Migrates pickle data to SQLite
│
├── scripts/                        # Utility scripts (empty for now)
│
├── static/                         # Web assets
│   ├── css/                        # Stylesheets
│   │   └── oauth-forms.css
│   ├── images/                     # Images (if any)
│   ├── js/                         # JavaScript files
│   │   └── admin-security.js
│   ├── index.html                  # Main web interface (formerly test_mcp.html)
│   └── debug.html                  # Debug interface
│
├── tests/                          # Test scripts
│   ├── setup_oauth_test.py
│   └── test_oauth.py
│
├── Core Python Modules (root)
│   ├── main.py                     # FastAPI application entry point
│   ├── database.py                 # SQLite database layer
│   ├── audit.py                    # Audit logging system
│   ├── auth.py                     # OAuth 2.1 authentication
│   ├── rbac.py                     # Role-based access control
│   ├── ad_integration.py           # Active Directory integration
│   ├── config.py                   # Configuration management
│   ├── encryption.py               # Encryption utilities
│   ├── middleware.py               # FastAPI middlewares
│   ├── mcp_storage.py              # MCP server storage manager
│   └── services.py                 # Business logic services
│
├── Configuration Files
│   ├── requirements.txt            # Python dependencies
│   ├── .gitignore                  # Git ignore rules
│   ├── .dockerignore               # Docker ignore rules
│   └── mcp_toolbox.dockerfile      # Docker configuration
│
└── Data Files
    └── tools_gateway.db            # SQLite database
```

---

## File Categories

### 1. Documentation (`docs/`)

All markdown documentation has been moved here:
- Migration guides
- Security guides
- Quickstart guides
- Test results and UI guides

**Purpose**: Centralize all user-facing documentation

### 2. Migrations (`migrations/`)

Database migration scripts:
- `migrate_to_sqlite.py` - One-time migration from pickle to SQLite
- `migrate_audit_logs.py` - Migrates audit logs from JSONL files to database

**Purpose**: Keep all migration scripts together for reference

### 3. Static Assets (`static/`)

Web interface files:
- `index.html` - Main portal interface (formerly `test_mcp.html`)
- `debug.html` - Debug tools interface
- `css/` - Stylesheets
- `js/` - JavaScript modules
- `images/` - Image assets

**Purpose**: Organize all web assets in a standard location

**Note**: The main interface was renamed from `test_mcp.html` to `index.html` for clarity

### 4. Tests (`tests/`)

Test scripts and test utilities:
- OAuth setup and testing scripts
- Integration tests

**Purpose**: Separate test code from production code

### 5. Core Modules (Root Directory)

Python application modules remain in root for easy imports:
- **main.py** - Application entry point
- **database.py** - SQLite persistence layer
- **auth.py** - Authentication system
- **rbac.py** - Authorization system
- **audit.py** - Audit logging
- **ad_integration.py** - LDAP/AD integration
- **config.py** - Configuration management
- **mcp_storage.py** - MCP server management
- **services.py** - Business logic
- **middleware.py** - Request/response middlewares
- **encryption.py** - Security utilities

---

## Key Changes from Previous Structure

### Files Moved:
1. **test_mcp.html** → `static/index.html` (renamed and moved)
2. **debug.html** → `static/debug.html`
3. All `*.md` files → `docs/`
4. `migrate_*.py` → `migrations/`
5. `test_*.py` and `setup_*.py` → `tests/`

### Files Removed:
1. `gateway_config.json` (temporary config file)
2. `.encryption_key` (generated at runtime)
3. All `*.pkl` files (migrated to SQLite)
4. `audit_logs/` folder (migrated to SQLite)

### Updated References:
1. `main.py` - Updated FileResponse paths from `"test_mcp.html"` to `"static/index.html"`
2. `.gitignore` - Added `gateway_config.json` and `*.backup` patterns

---

## Benefits of New Structure

### ✅ Improved Organization
- Clear separation of concerns
- Easy to find files by category
- Standard web project layout

### ✅ Better Maintainability
- Documentation in one place
- Tests isolated from production code
- Migration scripts preserved for reference

### ✅ Cleaner Root Directory
- Only essential Python modules in root
- No clutter from HTML, test files, or docs
- Easier to understand project structure

### ✅ Standard Conventions
- `docs/` for documentation
- `tests/` for test files
- `static/` for web assets
- `migrations/` for database migrations

---

## Usage Notes

### Accessing the Web Interface

The main portal is now available at the root URL:
```
http://localhost:8021/
```

It serves `static/index.html` (formerly `test_mcp.html`)

### Running Migrations

If you need to re-run migrations:
```bash
python migrations/migrate_to_sqlite.py
python migrations/migrate_audit_logs.py
```

### Running Tests

```bash
python tests/test_oauth.py
python tests/setup_oauth_test.py
```

### Finding Documentation

All documentation is now in the `docs/` folder:
```bash
ls docs/
cat docs/QUICKSTART.md
cat docs/SQLITE_MIGRATION_SUMMARY.md
```

---

## Future Organization

### Potential Additions:

1. **scripts/** - Utility scripts for deployment, backup, etc.
2. **templates/** - If we add email templates or other templates
3. **logs/** - If we want to keep structured logs (currently ignored)
4. **backups/** - Database backup location (not in git)

---

## Configuration

### .gitignore Updates

Added patterns to ignore:
- `gateway_config.json` (temporary config)
- `*.backup` (backup files)
- Kept `audit_logs/` exclusion (folder no longer created)

### Import Paths

All Python imports remain unchanged since core modules are still in the root directory:
```python
from database import database
from auth import oauth_provider_manager
from rbac import rbac_manager
# etc.
```

---

## Verification

To verify the structure is correct:

```bash
# Check that all imports work
python -c "import main"

# Check that static files are accessible
ls static/index.html
ls static/debug.html

# Check that docs are organized
ls docs/*.md

# Check that migrations are preserved
ls migrations/*.py

# Check that tests are isolated
ls tests/*.py
```

All checks should pass without errors.

---

## Summary

The tools_gateway directory is now well-organized with:
- ✅ Centralized documentation
- ✅ Isolated test files
- ✅ Standard static asset structure
- ✅ Preserved migration scripts
- ✅ Clean root directory
- ✅ Renamed main interface (test_mcp.html → index.html)
- ✅ All paths updated in code

The structure follows industry best practices and makes the project easier to navigate and maintain.

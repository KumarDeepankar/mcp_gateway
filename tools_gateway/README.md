# Tools Gateway - MCP Server Management Platform

**Enterprise-grade authentication, authorization, and management platform for Model Context Protocol (MCP) servers.**

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Features](#features)
4. [Architecture](#architecture)
5. [Installation](#installation)
6. [Authentication](#authentication)
7. [Authorization (RBAC)](#authorization-rbac)
8. [User Management](#user-management)
9. [Role Management](#role-management)
10. [MCP Server Management](#mcp-server-management)
11. [Tool Credentials](#tool-credentials)
12. [Audit Logging](#audit-logging)
13. [Active Directory / LDAP Integration](#active-directory--ldap-integration)
14. [API Reference](#api-reference)
15. [Security Best Practices](#security-best-practices)
16. [Production Deployment](#production-deployment)
17. [Troubleshooting](#troubleshooting)
18. [Database](#database)
19. [Directory Structure](#directory-structure)

---

## Overview

The Tools Gateway is a comprehensive management platform for MCP (Model Context Protocol) servers. It provides enterprise-grade security features including:

- **Multiple Authentication Methods**: Local (username/password), OAuth 2.1 (Google, Microsoft, GitHub), and Active Directory/LDAP
- **Role-Based Access Control (RBAC)**: Granular permissions for users, servers, and tools
- **Comprehensive Audit Logging**: Track all security-relevant events
- **Encryption**: Automatic encryption for sensitive data at rest
- **Web-Based Admin Portal**: Modern UI for managing everything
- **MCP-Compliant**: Full support for MCP protocol specification

---

## Quick Start

### 1. Install Dependencies

```bash
cd tools_gateway
pip install -r requirements.txt
```

### 2. Start the Gateway

```bash
python main.py
```

The gateway starts on `http://localhost:8021`

### 3. Sign In

**Default Admin Account**:
- Email: `admin`
- Password: `admin`

**⚠️ Change the default password immediately after first login!**

### 4. Access the Portal

Open your browser: `http://localhost:8021`

You'll see the admin portal with tabs for:
- **Servers** - Manage MCP servers
- **OAuth Providers** - Configure authentication providers
- **Users & Roles** - Manage users and permissions
- **Audit Logs** - View security events
- **Active Directory** - Configure LDAP/AD integration

---

## Features

### ✅ Authentication
- Local authentication (username/password)
- OAuth 2.1 (Google, Microsoft, GitHub)
- Active Directory / LDAP integration
- JWT token-based API access
- Automatic token refresh

### ✅ Authorization (RBAC)
- Built-in roles: Administrator, Standard User, Viewer
- Custom role creation with granular permissions
- Per-server and per-tool access control
- User-to-role assignments
- Group-based permissions (AD/LDAP)

### ✅ User Management
- Create, view, edit, delete users
- Assign roles and permissions
- Enable/disable accounts
- Password management for local users
- Automatic user provisioning from OAuth/AD

### ✅ Role Management
- Create custom roles with configurable permissions
- View and modify all existing roles
- System role protection (Administrator, Standard User, Viewer)
- Visual permission assignment

### ✅ MCP Server Management
- Add, configure, and manage MCP servers
- Test server connections
- Configure per-server credentials
- Grant user access to specific servers
- Tool-level access control

### ✅ Tool Credentials
- Secure storage of tool-specific credentials
- Username/password or API key authentication
- Per-user credential management
- Encrypted storage

### ✅ Audit Logging
- Comprehensive event tracking
- Security event monitoring
- User action logging
- SQLite-based storage
- Filterable event history

### ✅ Active Directory / LDAP
- AD/LDAP authentication
- Group-to-role mapping
- Automatic user provisioning
- Multi-directory support
- Test connection feature

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Tools Gateway                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Authentication Layer                     │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │  │
│  │  │  Local   │  │  OAuth   │  │   AD/LDAP    │  │  │
│  │  │  Auth    │  │  (G,M,GH)│  │              │  │  │
│  │  └──────────┘  └──────────┘  └──────────────┘  │  │
│  └──────────────────┬───────────────────────────────┘  │
│                     │                                   │
│                     ▼                                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │            JWT Token Manager                     │  │
│  └──────────────────┬───────────────────────────────┘  │
│                     │                                   │
│                     ▼                                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │          Authorization (RBAC)                    │  │
│  │  - Users, Roles, Permissions                     │  │
│  │  - Server Access Control                         │  │
│  │  - Tool Access Control                           │  │
│  └──────────────────┬───────────────────────────────┘  │
│                     │                                   │
│                     ▼                                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │            Audit Logger                          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │            MCP Server Manager                    │  │
│  │  - Server Registration                           │  │
│  │  - Tool Discovery                                │  │
│  │  - Credential Management                         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │         SQLite Database                          │  │
│  │  - Users, Roles, Permissions                     │  │
│  │  - OAuth Providers, AD Configs                   │  │
│  │  - MCP Servers, Credentials                      │  │
│  │  - Audit Logs                                    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Installation

### Prerequisites

- Python 3.8+
- pip
- (Optional) Active Directory / LDAP server
- (Optional) OAuth provider credentials (Google, Microsoft, or GitHub)

### Install Dependencies

```bash
cd tools_gateway
pip install -r requirements.txt
```

**Key Dependencies**:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `python-jose[cryptography]` - JWT tokens
- `cryptography` - Data encryption
- `pydantic` - Data validation
- `ldap3` - LDAP/AD integration
- `aiofiles` - Async file operations

### Environment Setup

No environment variables are required for basic operation. The system uses sensible defaults:

- Default port: `8021`
- Database: `tools_gateway.db` (auto-created)
- Encryption key: `.encryption_key` (auto-generated)

**Optional environment variables**:

```bash
# Server configuration
export PORT=8021
export HOST=0.0.0.0
export LOG_LEVEL=INFO

# OAuth providers (optional)
export GOOGLE_CLIENT_ID=xxx
export GOOGLE_CLIENT_SECRET=xxx
export MICROSOFT_CLIENT_ID=xxx
export MICROSOFT_CLIENT_SECRET=xxx
export GITHUB_CLIENT_ID=xxx
export GITHUB_CLIENT_SECRET=xxx

# Security
export JWT_SECRET_KEY=$(openssl rand -hex 32)
export ENCRYPTION_KEY_FILE=/secure/path/.encryption_key
```

---

## Authentication

The Tools Gateway supports **three authentication methods**, all working simultaneously:

### 1. Local Authentication

**Use Case**: Internal users, admin access, no external dependencies

**Sign In**:
```bash
curl -X POST http://localhost:8021/auth/login/local \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin",
    "password": "admin"
  }'
```

**Response**:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "user": {
    "email": "admin",
    "name": "Administrator",
    "roles": ["Administrator"]
  }
}
```

**Default Admin Account**:
- Email: `admin`
- Password: `admin`
- ⚠️ **Change this immediately!**

### 2. OAuth 2.1

**Use Case**: Enterprise SSO, external users, social login

**Supported Providers**:
- Google
- Microsoft (Azure AD)
- GitHub

**Configuration** (via Web UI):
1. Navigate to "OAuth Providers" tab
2. Click "Add OAuth Provider"
3. Select template (Google, Microsoft, or GitHub)
4. Enter Client ID and Client Secret
5. Save

**OAuth Setup Guides**:

#### Google OAuth
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 credentials
3. Add redirect URI: `http://localhost:8021/auth/callback`
4. Copy Client ID and Secret

#### Microsoft OAuth
1. Go to [Azure Portal](https://portal.azure.com/)
2. Register application
3. Add redirect URI: `http://localhost:8021/auth/callback`
4. Create client secret
5. Copy Application ID and Secret

#### GitHub OAuth
1. Go to GitHub Settings → Developer settings → OAuth Apps
2. Create OAuth App
3. Set callback URL: `http://localhost:8021/auth/callback`
4. Copy Client ID and Secret

### 3. Active Directory / LDAP

**Use Case**: Enterprise environments with existing AD/LDAP infrastructure

**Configuration** (via Web UI):
1. Navigate to "Active Directory" tab
2. Click "Add Configuration"
3. Enter connection details
4. Configure group mappings
5. Test connection
6. Save

### JWT Tokens

All authentication methods issue JWT tokens with:
- **Lifetime**: 60 minutes (configurable)
- **Algorithm**: HS256
- **Claims**: user_id, email, name, provider, roles

**Using Tokens**:
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8021/admin/users
```

---

## Authorization (RBAC)

### Built-in Roles

1. **Administrator**
   - Full system access
   - User and role management
   - OAuth and AD configuration
   - Audit log access
   - All server and tool permissions

2. **Standard User**
   - View servers and tools
   - Execute tools (with server permissions)
   - View configuration
   - Cannot manage users or roles

3. **Viewer**
   - Read-only access
   - Cannot execute tools or modify configuration

### Permissions

```python
# Server permissions
SERVER_READ = "server:read"         # View servers
SERVER_WRITE = "server:write"       # Add/modify servers
SERVER_DELETE = "server:delete"     # Delete servers
SERVER_TEST = "server:test"         # Test connections

# Tool permissions
TOOL_VIEW = "tool:view"             # View tools
TOOL_EXECUTE = "tool:execute"       # Execute tools
TOOL_MANAGE = "tool:manage"         # Manage tool credentials

# Configuration permissions
CONFIG_VIEW = "config:view"         # View config
CONFIG_EDIT = "config:edit"         # Edit config

# User management
USER_VIEW = "user:view"             # View users
USER_MANAGE = "user:manage"         # Create/modify users

# Role management
ROLE_VIEW = "role:view"             # View roles
ROLE_MANAGE = "role:manage"         # Create/modify roles

# Audit permissions
AUDIT_VIEW = "audit:view"           # View audit logs

# OAuth permissions
OAUTH_MANAGE = "oauth:manage"       # Manage OAuth providers

# AD permissions
AD_MANAGE = "ad:manage"             # Manage AD configs
```

---

## User Management

### Create Local User

**Via Web UI**:
1. Navigate to "Users & Roles" tab
2. Click "Create User"
3. Fill in details
4. Click "Create User"

**Via API**:
```bash
curl -X POST http://localhost:8021/admin/users \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "name": "John Doe",
    "password": "SecurePassword123",
    "provider": "local",
    "roles": ["user"]
  }'
```

### Change User Password

```bash
curl -X POST http://localhost:8021/admin/users/{user_id}/password \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_password": "NewSecurePassword123"
  }'
```

---

## Role Management

### Create Custom Role

**Via Web UI**:
1. Navigate to "Users & Roles" tab
2. Scroll to "Roles Management" section
3. Click "Create Role"
4. Fill in details and select permissions
5. Click "Create Role"

**Via API**:
```bash
curl -X POST http://localhost:8021/admin/roles \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role_name": "Developer",
    "description": "Developers with tool execution access",
    "permissions": [
      "server:read",
      "tool:view",
      "tool:execute",
      "config:view"
    ]
  }'
```

### Update Role

```bash
curl -X PUT http://localhost:8021/admin/roles/{role_id} \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role_name": "Developer",
    "description": "Updated description",
    "permissions": [
      "server:read",
      "tool:view",
      "tool:execute"
    ]
  }'
```

---

## MCP Server Management

### Add MCP Server

**Via Web UI**:
1. Navigate to "Servers" tab
2. Click "Add MCP Server"
3. Fill in details
4. Click "Add Server"

**Via API**:
```bash
curl -X POST http://localhost:8021/mcp/servers \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "weather_server",
    "name": "Weather API Server",
    "command": "python",
    "args": ["weather_server.py"],
    "env": {
      "API_KEY": "your_api_key"
    }
  }'
```

---

## Tool Credentials

### Create Credential

**Via API**:
```bash
# Username/Password
curl -X POST http://localhost:8021/admin/tools/{server_id}/{tool_name}/credentials \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "credential_type": "username_password",
    "username": "myuser",
    "password": "mypassword"
  }'

# API Key
curl -X POST http://localhost:8021/admin/tools/{server_id}/{tool_name}/credentials \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "credential_type": "api_key",
    "api_key": "sk-abc123..."
  }'
```

---

## Audit Logging

All security-relevant events are automatically logged.

### View Audit Logs

**Via API**:
```bash
# Recent events
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  http://localhost:8021/admin/audit/events?limit=100

# Security events
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  http://localhost:8021/admin/audit/security?hours=24

# Statistics
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  http://localhost:8021/admin/audit/statistics?hours=24
```

---

## Active Directory / LDAP Integration

### Configure AD/LDAP

**Via API**:
```bash
curl -X POST http://localhost:8021/admin/ad/config \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "company_ad",
    "server_url": "ldap://dc.company.com:389",
    "base_dn": "dc=company,dc=com",
    "bind_dn": "cn=service,dc=company,dc=com",
    "bind_password": "password",
    "user_search_filter": "(sAMAccountName={username})",
    "enabled": true
  }'
```

### Map AD Groups to Roles

```bash
curl -X POST http://localhost:8021/admin/ad/mappings \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "company_ad",
    "ad_group": "CN=Admins,OU=Groups,DC=company,DC=com",
    "role_id": "admin"
  }'
```

---

## API Reference

### Authentication Endpoints

- `POST /auth/login/local` - Local login
- `POST /auth/login/ad` - AD/LDAP login
- `POST /auth/login?provider_id=google` - OAuth login
- `GET /auth/callback` - OAuth callback
- `GET /auth/providers` - List OAuth providers
- `GET /auth/user` - Get current user
- `POST /auth/logout` - Logout

### User Management

- `GET /admin/users` - List users
- `POST /admin/users` - Create user
- `DELETE /admin/users/{user_id}` - Delete user
- `POST /admin/users/{user_id}/password` - Change password
- `POST /admin/users/{user_id}/roles` - Assign role

### Role Management

- `GET /admin/roles` - List roles
- `POST /admin/roles` - Create role
- `PUT /admin/roles/{role_id}` - Update role
- `DELETE /admin/roles/{role_id}` - Delete role

---

## Security Best Practices

1. **Change Default Password** - Immediately change the default admin password
2. **Use HTTPS** - Always use HTTPS in production
3. **Backup Encryption Key** - Backup `.encryption_key` file securely
4. **Monitor Audit Logs** - Regularly review security events
5. **Least Privilege** - Assign minimal permissions needed
6. **Strong Passwords** - Require strong passwords for local users

---

## Production Deployment

### Systemd Service

Create `/etc/systemd/system/tools-gateway.service`:

```ini
[Unit]
Description=MCP Tools Gateway
After=network.target

[Service]
Type=simple
User=gateway
WorkingDirectory=/opt/tools_gateway
ExecStart=/opt/tools_gateway/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8021 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name gateway.example.com;

    ssl_certificate /etc/ssl/certs/gateway.crt;
    ssl_certificate_key /etc/ssl/private/gateway.key;

    location / {
        proxy_pass http://127.0.0.1:8021;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Troubleshooting

### OAuth Callback Error

**Solutions**:
1. Verify OAuth client ID and secret
2. Check redirect URI matches exactly
3. Ensure OAuth provider is enabled

### Permission Denied

**Solutions**:
1. Verify user has appropriate role
2. Check role has required permissions
3. Review audit logs for details

### AD/LDAP Connection Failed

**Solutions**:
1. Verify server URL is correct
2. Check bind DN and password
3. Ensure network connectivity
4. Test with LDAP client

---

## Database

The system uses SQLite for all persistence:

**Main Tables**:
- `users` - User accounts
- `roles` - Role definitions
- `permissions` - Role-to-permission mappings
- `oauth_providers` - OAuth provider configurations
- `ad_configs` - AD/LDAP configurations
- `mcp_servers` - MCP server definitions
- `tool_credentials` - Tool authentication credentials
- `audit_logs` - Audit event logs

---

## Directory Structure

```
tools_gateway/
├── migrations/                     # Database migration scripts
├── static/                         # Web assets
│   ├── css/                        # Stylesheets
│   ├── js/                         # JavaScript
│   └── index.html                  # Admin portal
├── tests/                          # Test scripts
├── main.py                         # FastAPI entry point
├── database.py                     # SQLite database layer
├── auth.py                         # OAuth authentication
├── rbac.py                         # Role-based access control
├── ad_integration.py               # AD/LDAP integration
├── audit.py                        # Audit logging
├── requirements.txt                # Dependencies
└── README.md                       # This file
```

---

## Support

For issues or questions, please contact the development team.

---

## License

Internal use only. All rights reserved.

---

**🎉 You're ready to use the Tools Gateway!**

Start the server with `python main.py` and visit `http://localhost:8021`

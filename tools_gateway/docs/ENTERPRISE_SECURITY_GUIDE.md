# Enterprise Security Guide - Tools Gateway

## Overview

The Tools Gateway has been enhanced with enterprise-grade security features including:

- **OAuth 2.1 Authentication** with support for Google, Microsoft, and GitHub
- **Role-Based Access Control (RBAC)** with granular permissions
- **Comprehensive Audit Logging** for compliance and security monitoring
- **Encryption** for sensitive data at rest
- **MCP-compliant authentication** for tool access control

## Architecture

```
┌─────────────────┐
│   OAuth 2.1     │
│   Providers     │
│  (G, M, GitHub) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  Authorization  │─────►│ JWT Manager  │
│     Flow        │      └──────────────┘
└────────┬────────┘              │
         │                       │
         ▼                       ▼
┌─────────────────────────────────────┐
│         Tools Gateway               │
│  ┌────────────────────────────────┐ │
│  │  Authentication Middleware     │ │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │  RBAC Manager                  │ │
│  │  - Users, Roles, Permissions   │ │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │  Audit Logger                  │ │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │  MCP Servers                   │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## Installation

### 1. Install Dependencies

```bash
cd tools_gateway
pip install -r requirements.txt
```

New dependencies added:
- `python-jose[cryptography]` - JWT token management
- `cryptography` - Data encryption
- `pydantic` - Data validation
- `python-multipart` - Form data handling

### 2. Configure OAuth Providers

Before starting the gateway, you need to configure at least one OAuth provider. You have two options:

#### Option A: Configure via API (Recommended)

1. Start the gateway in development mode
2. Access the admin portal at `http://localhost:8021`
3. Navigate to "OAuth Providers" tab
4. Click "Add OAuth Provider"

#### Option B: Configure Programmatically

Create a configuration script:

```python
from tools_gateway.auth import oauth_provider_manager

# Add Google OAuth
oauth_provider_manager.add_provider(
    provider_id="google",
    client_id="YOUR_GOOGLE_CLIENT_ID",
    client_secret="YOUR_GOOGLE_CLIENT_SECRET",
    template="google"  # Uses built-in Google template
)

# Add Microsoft OAuth
oauth_provider_manager.add_provider(
    provider_id="microsoft",
    client_id="YOUR_MICROSOFT_CLIENT_ID",
    client_secret="YOUR_MICROSOFT_CLIENT_SECRET",
    template="microsoft"
)

# Add GitHub OAuth
oauth_provider_manager.add_provider(
    provider_id="github",
    client_id="YOUR_GITHUB_CLIENT_ID",
    client_secret="YOUR_GITHUB_CLIENT_SECRET",
    template="github"
)
```

### 3. Obtain OAuth Credentials

#### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URI: `http://localhost:8021/auth/callback`
6. Copy Client ID and Client Secret

#### Microsoft OAuth Setup

1. Go to [Azure Portal](https://portal.azure.com/)
2. Register a new application
3. Add redirect URI: `http://localhost:8021/auth/callback`
4. Create a client secret
5. Copy Application (client) ID and Client Secret

#### GitHub OAuth Setup

1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Create a new OAuth App
3. Set Authorization callback URL: `http://localhost:8021/auth/callback`
4. Copy Client ID and Client Secret

## Running the Gateway

### Development Mode

```bash
cd tools_gateway
python main.py
```

The gateway will start on `http://localhost:8021`

### Production Mode

```bash
cd tools_gateway
uvicorn main:app --host 0.0.0.0 --port 8021 --workers 4
```

### With ngrok (for testing OAuth with public URLs)

```bash
ngrok http 8021
```

Update OAuth provider redirect URIs to use the ngrok URL.

## Authentication Flow

### 1. User Login

```
User → Portal → OAuth Provider → Callback → JWT Token → Portal
```

1. User clicks "Sign in with Google/Microsoft/GitHub"
2. Gateway redirects to OAuth provider
3. User authenticates with provider
4. Provider redirects back with authorization code
5. Gateway exchanges code for access token
6. Gateway retrieves user info from provider
7. Gateway creates or updates user in RBAC system
8. Gateway issues JWT token for MCP access
9. User is redirected to portal with token

### 2. API Access

All API requests must include JWT token:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8021/mcp
```

### 3. Token Expiration

- Default token lifetime: 60 minutes
- Tokens are automatically refreshed on portal
- API clients must handle 401 responses and re-authenticate

## Role-Based Access Control (RBAC)

### Default Roles

1. **Administrator**
   - Full system access
   - User and role management
   - OAuth provider configuration
   - Audit log access

2. **Standard User**
   - View servers and tools
   - Execute tools (with server permissions)
   - View configuration

3. **Viewer**
   - Read-only access to servers and tools
   - Cannot execute tools or modify configuration

### Permissions

```python
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
```

### Managing Users and Roles

#### Assign Role to User

```bash
curl -X POST \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role_id": "admin"}' \
  http://localhost:8021/admin/users/USER_ID/roles
```

#### Create Custom Role

```bash
curl -X POST \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role_name": "Developer",
    "description": "Developers with tool execution access",
    "permissions": [
      "server:view",
      "tool:view",
      "tool:execute"
    ]
  }' \
  http://localhost:8021/admin/roles
```

### MCP Server Access Control

Grant user access to specific MCP servers:

```python
from tools_gateway.rbac import rbac_manager

# Grant user access to server with all tools
rbac_manager.grant_server_access(
    user_id="user_abc123",
    server_id="server_xyz789"
)

# Grant access to specific tools only
rbac_manager.grant_server_access(
    user_id="user_abc123",
    server_id="server_xyz789",
    allowed_tools={"get_weather", "search_location"}
)
```

## Audit Logging

### Event Types

All security-relevant events are logged:

- Authentication (login, logout, token issued)
- Authorization (permission granted/denied, role changes)
- MCP Server operations (add, remove, update)
- Tool execution
- Configuration changes
- Security events (unauthorized access, invalid tokens)

### Viewing Audit Logs

#### Via Portal

1. Navigate to "Audit Logs" tab
2. View recent events and statistics
3. Filter by event type, user, or date range

#### Via API

```bash
# Get recent audit events
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  http://localhost:8021/admin/audit/events?limit=100

# Get audit statistics
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  http://localhost:8021/admin/audit/statistics?hours=24

# Get security events
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  http://localhost:8021/admin/audit/security?hours=24
```

### Log Storage

- Logs are stored in `audit_logs/` directory
- One file per day: `audit_YYYYMMDD.jsonl`
- JSON Lines format for easy parsing
- Configurable retention period (default: 90 days)

### Log Cleanup

```python
from tools_gateway.audit import audit_logger

# Clean up logs older than 90 days
audit_logger.cleanup_old_logs(days_to_keep=90)
```

## Encryption

### Data at Rest

Sensitive data is automatically encrypted:
- OAuth client secrets
- User credentials (if any)
- Configuration files

### Encryption Key Management

The encryption key is stored in `.encryption_key` file with 600 permissions.

**IMPORTANT**: Backup this file securely. Without it, encrypted data cannot be recovered.

```bash
# Backup encryption key
cp .encryption_key .encryption_key.backup

# Store in secure location
mv .encryption_key.backup /secure/backup/location/
```

### Rotating Encryption Keys

```python
from tools_gateway.encryption import EncryptionManager

# Create new encryption manager with new key
new_manager = EncryptionManager(key_file=".encryption_key.new")

# Re-encrypt data with new key
# (Implementation depends on your data storage)
```

## Security Best Practices

### 1. OAuth Configuration

- **Never commit OAuth secrets to version control**
- Use environment variables for production:
  ```bash
  export GOOGLE_CLIENT_ID=xxx
  export GOOGLE_CLIENT_SECRET=xxx
  ```
- Restrict OAuth redirect URIs to known domains
- Use HTTPS in production

### 2. JWT Tokens

- Configure appropriate token expiry (default: 60 minutes)
- Use strong secret keys (auto-generated on first run)
- Implement token refresh mechanism in clients
- Store tokens securely (httpOnly cookies preferred)

### 3. RBAC

- Follow principle of least privilege
- Regularly audit user permissions
- Remove unused roles and users
- Log all permission changes

### 4. Audit Logs

- Monitor for suspicious activity
- Set up alerts for failed authentication attempts
- Regular review of security events
- Maintain log retention per compliance requirements

### 5. Network Security

- Use HTTPS in production
- Configure firewall rules
- Implement rate limiting (already included)
- Use reverse proxy (nginx, Traefik) for TLS termination

## Production Deployment

### 1. Environment Variables

```bash
# Gateway Configuration
export PORT=8021
export HOST=0.0.0.0
export LOG_LEVEL=INFO

# OAuth Providers
export GOOGLE_CLIENT_ID=xxx
export GOOGLE_CLIENT_SECRET=xxx
export MICROSOFT_CLIENT_ID=xxx
export MICROSOFT_CLIENT_SECRET=xxx
export GITHUB_CLIENT_ID=xxx
export GITHUB_CLIENT_SECRET=xxx

# Security
export JWT_SECRET_KEY=$(openssl rand -hex 32)
export ENCRYPTION_KEY_FILE=/secure/path/.encryption_key

# Database (if using external storage)
export DB_CONNECTION_STRING=postgresql://...
```

### 2. Systemd Service

Create `/etc/systemd/system/tools-gateway.service`:

```ini
[Unit]
Description=MCP Tools Gateway
After=network.target

[Service]
Type=simple
User=gateway
WorkingDirectory=/opt/tools_gateway
EnvironmentFile=/etc/tools_gateway/environment
ExecStart=/opt/tools_gateway/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8021 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable tools-gateway
sudo systemctl start tools-gateway
```

### 3. Nginx Reverse Proxy

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

### 4. Enable Authentication Middleware

Uncomment in `main.py`:

```python
# Enable authentication for all endpoints
app.add_middleware(AuthenticationMiddleware)

# Enable rate limiting
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
```

### 5. Monitoring

Set up monitoring for:
- Failed authentication attempts
- Permission denied events
- Unusual API access patterns
- Server health status

## API Reference

### Authentication Endpoints

- `GET /auth/providers` - List OAuth providers
- `POST /auth/login?provider_id=google` - Initiate OAuth login
- `GET /auth/callback` - OAuth callback handler
- `GET /auth/user` - Get current user info
- `POST /auth/logout` - Logout

### OAuth Management (Admin)

- `POST /admin/oauth/providers` - Add OAuth provider
- `DELETE /admin/oauth/providers/{provider_id}` - Remove provider

### User Management (Admin)

- `GET /admin/users` - List users
- `POST /admin/users/{user_id}/roles` - Assign role
- `DELETE /admin/users/{user_id}/roles/{role_id}` - Revoke role

### Role Management (Admin)

- `GET /admin/roles` - List roles
- `POST /admin/roles` - Create role

### Audit Logs (Admin)

- `GET /admin/audit/events` - Get audit events
- `GET /admin/audit/statistics` - Get statistics
- `GET /admin/audit/security` - Get security events

## Troubleshooting

### OAuth Callback Error

**Problem**: "Failed to exchange authorization code"

**Solutions**:
1. Verify OAuth client ID and secret
2. Check redirect URI matches exactly
3. Ensure OAuth provider is enabled
4. Check network connectivity

### Permission Denied

**Problem**: User cannot access resources

**Solutions**:
1. Verify user has appropriate role
2. Check role has required permissions
3. Review audit logs for details
4. Ensure user is enabled

### Token Expired

**Problem**: API returns 401 Unauthorized

**Solutions**:
1. Re-authenticate to get new token
2. Implement automatic token refresh
3. Check token expiry configuration

### Audit Logs Not Appearing

**Problem**: Events not logged

**Solutions**:
1. Check `audit_logs/` directory permissions
2. Verify disk space
3. Check log level configuration
4. Review error logs

## Support

For issues or questions:
1. Check audit logs for error details
2. Review this guide
3. Check MCP specification compliance
4. File an issue with logs and configuration (redact secrets!)

## License

[Your License Here]

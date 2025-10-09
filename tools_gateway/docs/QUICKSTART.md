# Quick Start Guide - Enterprise Security Features

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd tools_gateway
pip install -r requirements.txt
```

### 2. Configure OAuth Provider (Google Example)

#### Get Google OAuth Credentials

1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Application type: "Web application"
6. Authorized redirect URIs: `http://localhost:8021/auth/callback`
7. Copy Client ID and Client Secret

#### Add Provider via Python

Create `setup_oauth.py`:

```python
from auth import oauth_provider_manager

oauth_provider_manager.add_provider(
    provider_id="google",
    client_id="YOUR_CLIENT_ID_HERE",
    client_secret="YOUR_CLIENT_SECRET_HERE",
    template="google"
)

print("✓ Google OAuth provider configured!")
```

Run:
```bash
python setup_oauth.py
```

### 3. Start the Gateway

```bash
python main.py
```

Gateway starts on `http://localhost:8021`

### 4. Access the Portal

Open browser: `http://localhost:8021`

You'll see:
- Sign in with Google button
- No authentication required yet (development mode)

### 5. Sign In

1. Click "Sign in with Google"
2. Authenticate with your Google account
3. You'll be redirected back to the portal with a JWT token
4. You're now logged in!

### 6. Explore Admin Features

Navigate through the tabs:

**OAuth Providers**
- View configured providers
- Add more providers (Microsoft, GitHub)

**Users & Roles**
- See all authenticated users
- Assign roles to users
- Create custom roles

**Audit Logs**
- View security events
- Monitor authentication attempts
- Track permission changes

**Servers**
- Add MCP servers
- Configure server access per user

## First Admin User

The first user to sign in is automatically assigned the "admin" role. To manually create an admin:

```python
from rbac import rbac_manager

# Create user with admin role
user = rbac_manager.create_user(
    email="admin@example.com",
    name="Administrator",
    roles={"admin"}
)

print(f"Admin user created: {user.user_id}")
```

## Testing with Multiple Providers

### Add Microsoft OAuth

```python
from auth import oauth_provider_manager

oauth_provider_manager.add_provider(
    provider_id="microsoft",
    client_id="YOUR_MICROSOFT_CLIENT_ID",
    client_secret="YOUR_MICROSOFT_CLIENT_SECRET",
    template="microsoft"
)
```

### Add GitHub OAuth

```python
from auth import oauth_provider_manager

oauth_provider_manager.add_provider(
    provider_id="github",
    client_id="YOUR_GITHUB_CLIENT_ID",
    client_secret="YOUR_GITHUB_CLIENT_SECRET",
    template="github"
)
```

## Using Authentication with MCP

### Get JWT Token

After signing in, your token is stored in localStorage. To use it with API requests:

```javascript
// In browser console
const token = localStorage.getItem('mcp_auth_token');
console.log(token);
```

### Make Authenticated API Calls

```bash
# List tools (requires authentication)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": "1"
  }' \
  http://localhost:8021/mcp
```

### Call a Tool

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "your_tool_name",
      "arguments": {}
    },
    "id": "2"
  }' \
  http://localhost:8021/mcp
```

## Enable Full Authentication Mode

To require authentication for all endpoints:

Edit `main.py` and uncomment:

```python
# Enable authentication for all endpoints
app.add_middleware(AuthenticationMiddleware)

# Enable rate limiting
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
```

Restart the gateway. Now all endpoints require JWT authentication.

## Managing RBAC

### Create Custom Role

```python
from rbac import rbac_manager, Permission

# Create developer role
role = rbac_manager.create_role(
    role_name="Developer",
    description="Developers with tool execution rights",
    permissions={
        Permission.SERVER_VIEW,
        Permission.TOOL_VIEW,
        Permission.TOOL_EXECUTE
    }
)
```

### Assign Role to User

```python
# Assign developer role to user
rbac_manager.assign_role(
    user_id="user_abc123",
    role_id="developer"
)
```

### Grant Server Access

```python
# Allow user to access specific server
rbac_manager.grant_server_access(
    user_id="user_abc123",
    server_id="weather_server",
    allowed_tools={"get_weather", "get_forecast"}  # Empty set = all tools
)
```

## Viewing Audit Logs

### Via Python

```python
from audit import audit_logger

# Get recent events
events = audit_logger.query_events(limit=50)

for event in events:
    print(f"{event.timestamp} - {event.event_type} - {event.user_email}")

# Get security events
security_events = audit_logger.get_security_events(hours=24)

# Get statistics
stats = audit_logger.get_statistics(hours=24)
print(f"Total events: {stats['total_events']}")
```

### Via Web Portal

1. Navigate to "Audit Logs" tab
2. View real-time events
3. Filter by type, user, or severity

## Common Tasks

### Reset User Password (OAuth)

Users authenticate via OAuth providers, so password reset is handled by the provider (Google, Microsoft, GitHub).

### Revoke Access

```python
# Disable user
rbac_manager.update_user(
    user_id="user_abc123",
    enabled=False
)
```

### Export Audit Logs

Logs are stored in `audit_logs/` as JSON Lines:

```bash
# View today's logs
cat audit_logs/audit_$(date +%Y%m%d).jsonl | jq .

# Export to CSV
cat audit_logs/audit_*.jsonl | \
  jq -r '[.timestamp, .event_type, .user_email, .success] | @csv' \
  > audit_export.csv
```

### Backup Encryption Key

**CRITICAL**: Backup your encryption key:

```bash
# Backup
cp .encryption_key /secure/backup/location/

# Restore
cp /secure/backup/location/.encryption_key .
```

## Testing the System

### 1. Test OAuth Flow

```bash
# Start gateway
python main.py

# Open browser
open http://localhost:8021

# Click "Sign in with Google"
# Verify redirect and authentication
```

### 2. Test RBAC

```python
from rbac import rbac_manager, Permission

# Create test user
user = rbac_manager.create_user(
    email="test@example.com",
    roles={"viewer"}  # Read-only
)

# Check permissions
can_execute = rbac_manager.has_permission(user.user_id, Permission.TOOL_EXECUTE)
print(f"Can execute tools: {can_execute}")  # False

# Upgrade to user role
rbac_manager.assign_role(user.user_id, "user")

can_execute = rbac_manager.has_permission(user.user_id, Permission.TOOL_EXECUTE)
print(f"Can execute tools: {can_execute}")  # True
```

### 3. Test Audit Logging

```python
from audit import audit_logger, AuditEventType, AuditSeverity

# Log test event
audit_logger.log_event(
    AuditEventType.TOOL_EXECUTED,
    user_id="test_user",
    user_email="test@example.com",
    resource_type="tool",
    resource_id="weather_tool",
    action="execute",
    details={"tool_name": "get_weather", "params": {"city": "NYC"}}
)

# Query events
events = audit_logger.query_events(
    user_email="test@example.com",
    limit=10
)

for event in events:
    print(f"{event.event_type}: {event.action}")
```

## Next Steps

- Read the full [ENTERPRISE_SECURITY_GUIDE.md](./ENTERPRISE_SECURITY_GUIDE.md)
- Configure production OAuth providers
- Set up HTTPS with reverse proxy
- Configure backup strategy
- Set up monitoring and alerting

## Troubleshooting

**Can't sign in**
- Check OAuth credentials are correct
- Verify redirect URI matches exactly
- Check browser console for errors

**Permission denied**
- Verify user has appropriate role
- Check role has required permissions
- View audit logs for details

**Token expired**
- Re-authenticate through portal
- Check token expiry settings (default: 60 min)

## Support

See [ENTERPRISE_SECURITY_GUIDE.md](./ENTERPRISE_SECURITY_GUIDE.md) for comprehensive documentation.

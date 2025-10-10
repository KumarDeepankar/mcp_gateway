# Local Authentication Guide for Tools Gateway

## Overview

The Tools Gateway now supports **local authentication** with username/password in addition to OAuth providers (Google, Microsoft, GitHub). This allows you to manage the gateway without requiring external OAuth configuration.

## Default Admin Account

When the system starts for the first time (no users exist), a default admin account is automatically created:

- **Email/Username**: `admin`
- **Password**: `admin`
- **Role**: Administrator (full permissions)

**⚠️ SECURITY WARNING**: Change the default password immediately after first login!

## Sign In

### Using the API

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

### Using the Token

Include the access token in subsequent requests:

```bash
curl -X GET http://localhost:8021/admin/users \
  -H "Authorization: Bearer eyJhbGci..."
```

## User Management

### Create a New Local User

**Endpoint**: `POST /admin/users`

**Request Body**:
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "password": "securepassword123",
  "provider": "local",
  "roles": ["user"]
}
```

**Available Roles**:
- `admin` - Full system access
- `user` - Standard user access (view/execute tools)
- `viewer` - Read-only access

**Example**:
```bash
curl -X POST http://localhost:8021/admin/users \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "name": "John Doe",
    "password": "securepassword",
    "provider": "local",
    "roles": ["user"]
  }'
```

### Change User Password

**Endpoint**: `POST /admin/users/{user_id}/password`

Users can change their own password, or admins can change any user's password.

**Request Body**:
```json
{
  "new_password": "newSecurePassword123"
}
```

**Example**:
```bash
curl -X POST http://localhost:8021/admin/users/user_abc123/password \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_password": "newPassword123"
  }'
```

### Change Admin Password

To change the default admin password:

1. First, get your access token by logging in
2. Get the user ID:
   ```bash
   curl -X GET http://localhost:8021/auth/user \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
3. Change the password:
   ```bash
   curl -X POST http://localhost:8021/admin/users/YOUR_USER_ID/password \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "new_password": "YourNewSecurePassword!"
     }'
   ```

## Managing OAuth Providers

Now that you have admin access, you can configure OAuth providers for Google, Microsoft, or GitHub sign-in.

### Add Google OAuth Provider

**Endpoint**: `POST /admin/oauth/providers`

**Request Body**:
```json
{
  "provider_id": "google",
  "template": "google",
  "client_id": "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com",
  "client_secret": "YOUR_GOOGLE_CLIENT_SECRET"
}
```

**Example**:
```bash
curl -X POST http://localhost:8021/admin/oauth/providers \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "google",
    "template": "google",
    "client_id": "123456789.apps.googleusercontent.com",
    "client_secret": "GOCSPX-YourClientSecret"
  }'
```

## API Endpoints Summary

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/auth/login/local` | POST | Login with email/password | No |
| `/auth/user` | GET | Get current user info | Yes |
| `/auth/logout` | POST | Logout | Yes |
| `/admin/users` | GET | List all users | Admin |
| `/admin/users` | POST | Create new user | Admin |
| `/admin/users/{user_id}/password` | POST | Change password | Admin or Self |
| `/admin/oauth/providers` | GET | List OAuth providers | No |
| `/admin/oauth/providers` | POST | Add OAuth provider | Admin |
| `/admin/oauth/providers/{id}` | DELETE | Remove OAuth provider | Admin |

## Security Best Practices

1. **Change Default Password**: Immediately change the default `admin` password after first login
2. **Use Strong Passwords**: Require passwords with at least 12 characters, including uppercase, lowercase, numbers, and symbols
3. **Limit Admin Access**: Only grant admin role to trusted users
4. **Enable OAuth**: Configure OAuth providers for enterprise authentication
5. **Regular Audits**: Review audit logs regularly at `/admin/audit/events`
6. **HTTPS Only**: Use HTTPS in production (behind reverse proxy/load balancer)

## Password Security

- Passwords are hashed using **SHA-256** before storage
- Password hashes are never exposed via API
- Local users cannot use OAuth and vice versa (provider separation)

## Troubleshooting

### "Invalid credentials" error

- Double-check email and password
- Ensure the user is a local user (not OAuth)
- Check if the user is enabled

### "Permission denied" error

- Verify your access token is valid
- Check if your role has the required permissions
- Refresh your token if expired (default: 1 hour)

### Can't create OAuth provider

- First sign in with the default admin account
- Ensure you have admin role permissions

## Example Workflow

1. **Start the gateway**:
   ```bash
   python main.py
   ```

2. **Sign in as admin**:
   ```bash
   TOKEN=$(curl -s -X POST http://localhost:8021/auth/login/local \
     -H "Content-Type: application/json" \
     -d '{"email":"admin","password":"admin"}' | jq -r '.access_token')
   ```

3. **Change admin password**:
   ```bash
   USER_ID=$(curl -s http://localhost:8021/auth/user \
     -H "Authorization: Bearer $TOKEN" | jq -r '.user_id')

   curl -X POST http://localhost:8021/admin/users/$USER_ID/password \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"new_password":"NewSecurePass123!"}'
   ```

4. **Create additional users**:
   ```bash
   curl -X POST http://localhost:8021/admin/users \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "developer@company.com",
       "name": "Dev User",
       "password": "DevPassword123",
       "provider": "local",
       "roles": ["user"]
     }'
   ```

5. **Configure Google OAuth** (optional):
   ```bash
   curl -X POST http://localhost:8021/admin/oauth/providers \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "provider_id": "google",
       "template": "google",
       "client_id": "YOUR_CLIENT_ID",
       "client_secret": "YOUR_CLIENT_SECRET"
     }'
   ```

## Support

For issues or questions:
- Check the application logs
- Review audit logs at `/admin/audit/events`
- Consult the main README.md for additional documentation

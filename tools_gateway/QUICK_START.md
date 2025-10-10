# Quick Start Guide - Tools Gateway Local Authentication

## 🚀 Getting Started in 3 Steps

### 1. Start the Gateway
```bash
cd tools_gateway
python main.py
```

You'll see:
```
⚠️  Default admin user created with email 'admin' and password 'admin'
⚠️  SECURITY: Change this password immediately after first login!
...
INFO: Uvicorn running on http://0.0.0.0:8021
```

### 2. Login as Admin
```bash
curl -X POST http://localhost:8021/auth/login/local \
  -H "Content-Type: application/json" \
  -d '{"email":"admin","password":"admin"}'
```

**Response**: You'll get an `access_token` - copy it!
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

### 3. Use the Token
```bash
# Set your token
export TOKEN="eyJhbGci..."

# Now you can access admin features
curl -H "Authorization: Bearer $TOKEN" http://localhost:8021/admin/users
```

## 📝 Common Tasks

### Change Admin Password
```bash
# 1. Get your user ID
curl -H "Authorization: Bearer $TOKEN" http://localhost:8021/auth/user

# 2. Change password (replace USER_ID with the actual ID)
curl -X POST http://localhost:8021/admin/users/USER_ID/password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"new_password":"NewSecurePassword123!"}'
```

### Create a New User
```bash
curl -X POST http://localhost:8021/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "name": "John Doe",
    "password": "SecurePass123",
    "provider": "local",
    "roles": ["user"]
  }'
```

### Configure Google OAuth (Web App)
```bash
curl -X POST http://localhost:8021/admin/oauth/providers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "google",
    "template": "google",
    "client_id": "YOUR-CLIENT-ID.apps.googleusercontent.com",
    "client_secret": "YOUR-CLIENT-SECRET"
  }'
```

## 🔑 Default Credentials

| Field | Value |
|-------|-------|
| Email | `admin` |
| Password | `admin` |
| Role | Administrator |

**⚠️ Change this password immediately in production!**

## 🔐 Roles & Permissions

| Role | Can View | Can Execute | Can Manage |
|------|----------|-------------|------------|
| **admin** | ✅ | ✅ | ✅ |
| **user** | ✅ | ✅ | ❌ |
| **viewer** | ✅ | ❌ | ❌ |

## 📚 More Information

- **Full Guide**: See `LOCAL_AUTH_GUIDE.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Web UI**: Open http://localhost:8021 in your browser

## ⚡ Quick Reference - All Endpoints

```bash
# Authentication
POST /auth/login/local        # Login (email + password)
GET  /auth/user               # Get current user info
POST /auth/logout             # Logout

# User Management (Admin only)
GET  /admin/users             # List all users
POST /admin/users             # Create new user
POST /admin/users/{id}/password  # Change password

# OAuth Providers (Admin only)
GET  /admin/oauth/providers   # List OAuth providers
POST /admin/oauth/providers   # Add OAuth provider
DELETE /admin/oauth/providers/{id}  # Remove OAuth provider

# Roles (Admin only)
GET  /admin/roles             # List all roles
POST /admin/roles             # Create new role
DELETE /admin/roles/{id}      # Delete role

# Audit Logs (Admin only)
GET  /admin/audit/events      # Get audit logs
GET  /admin/audit/statistics  # Get audit statistics
GET  /admin/audit/security    # Get security events
```

## 🎯 Troubleshooting

### Can't login?
- Check email and password are correct
- Make sure you're using `/auth/login/local` (not OAuth)
- Verify the server is running on port 8021

### "Permission denied"?
- Make sure you're including the Authorization header
- Check your token hasn't expired (1 hour default)
- Verify your role has the required permissions

### Google OAuth not working?
- Use **Web Application** credentials, not "Installed"
- Set redirect URI to: `http://localhost:8021/auth/callback`
- Make sure you're using the client_id and client_secret from the **web** section

## 🛟 Need Help?

1. Check server logs for error messages
2. Review audit logs: `curl -H "Authorization: Bearer $TOKEN" http://localhost:8021/admin/audit/events`
3. Consult the full documentation in `LOCAL_AUTH_GUIDE.md`

---

**Congratulations! You're ready to use the Tools Gateway!** 🎉

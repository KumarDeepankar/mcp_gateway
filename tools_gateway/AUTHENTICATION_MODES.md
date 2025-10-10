# Authentication Modes Guide

## Overview

The Tools Gateway supports **both** local authentication and OAuth 2.0 simultaneously. You don't need to "switch" between modes - **both work at the same time**! Users can choose their preferred method to sign in.

## Authentication Architecture

```
┌─────────────────────────────────────────────────┐
│         Tools Gateway Authentication            │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐        ┌──────────────┐     │
│  │   Local      │        │   OAuth 2.0  │     │
│  │   Auth       │        │   Providers  │     │
│  └──────────────┘        └──────────────┘     │
│        │                       │               │
│        │                       ├─ Google       │
│        │                       ├─ Microsoft    │
│        │                       └─ GitHub       │
│        │                       │               │
│        └───────────┬───────────┘               │
│                    │                           │
│              ┌─────▼─────┐                     │
│              │  JWT      │                     │
│              │  Tokens   │                     │
│              └───────────┘                     │
│                    │                           │
│              ┌─────▼─────┐                     │
│              │   RBAC    │                     │
│              │   System  │                     │
│              └───────────┘                     │
└─────────────────────────────────────────────────┘
```

## How It Works

### User Perspective

Users can sign in using **either**:

1. **Local Authentication**
   - Username/email + password
   - Stored in local database
   - Managed by admin

2. **OAuth 2.0**
   - Sign in with Google
   - Sign in with Microsoft
   - Sign in with GitHub

**Both create the same JWT token** and provide the same access based on assigned roles.

### User Records

Each user has a `provider` field that indicates how they were created:

```
User 1:
  email: admin
  provider: local          ← Local user
  password_hash: abc123... ← Has password

User 2:
  email: john@gmail.com
  provider: google         ← OAuth user
  password_hash: null      ← No password
```

## Sign In Methods

### Method 1: Local Authentication

**Endpoint**: `POST /auth/login/local`

**Use Case**:
- Internal users
- Admin access
- No external OAuth dependency
- Custom user management

**Example**:
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

### Method 2: OAuth 2.0 (Google Example)

**Endpoint**: `POST /auth/login?provider_id=google`

**Use Case**:
- Enterprise SSO
- External users
- Social login
- No password management

**Flow**:
```bash
# 1. Initiate OAuth flow
curl -X POST http://localhost:8021/auth/login?provider_id=google

# Response includes authorization URL
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "abc123..."
}

# 2. User visits URL, grants permission

# 3. Google redirects to: http://localhost:8021/auth/callback?code=...

# 4. Gateway exchanges code for token and returns JWT
```

## Creating Users for Each Mode

### Create Local User

```bash
curl -X POST http://localhost:8021/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "name": "John Doe",
    "password": "SecurePass123",
    "provider": "local",           ← Local auth
    "roles": ["user"]
  }'
```

### Create OAuth User (Auto-created on first sign-in)

OAuth users are **automatically created** when they first sign in with Google/Microsoft/GitHub.

You can also pre-create them:

```bash
curl -X POST http://localhost:8021/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@gmail.com",
    "name": "John Doe",
    "provider": "google",          ← OAuth provider
    "roles": ["user"]
    # No password needed
  }'
```

## Mixing Both Methods

You can use both authentication methods simultaneously:

**Scenario**:
- Admin users → Local authentication
- Regular users → OAuth (Google)

**Setup**:

```bash
# 1. Admin creates local admin accounts
curl -X POST http://localhost:8021/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "email": "admin1@company.com",
    "password": "SecurePass",
    "provider": "local",
    "roles": ["admin"]
  }'

# 2. Configure Google OAuth for regular users
curl -X POST http://localhost:8021/admin/oauth/providers \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "provider_id": "google",
    "template": "google",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_SECRET"
  }'

# 3. Regular users can now sign in with Google
# (automatically get "user" role on first sign-in)
```

## Managing Authentication Modes

### Disable OAuth (Local Only)

To run in **local-only mode**, simply don't configure any OAuth providers:

```bash
# Check configured providers
curl http://localhost:8021/auth/providers

# Response: {"providers": []}  ← Empty, local only
```

Users can only sign in with local credentials.

### Disable Local Auth (OAuth Only)

To run in **OAuth-only mode**:

1. Configure OAuth providers
2. Don't create local users (except admin)
3. Use OAuth for all user sign-ins

**Note**: You should always keep the local admin account as a backup!

### Enable Both (Recommended)

1. Keep local admin account for emergency access
2. Configure OAuth providers for users
3. Users choose their preferred method

```bash
# Check what's available
curl http://localhost:8021/auth/providers

# Response
{
  "providers": [
    {
      "provider_id": "google",
      "provider_name": "Google",
      "enabled": true,
      "scopes": ["openid", "email", "profile"]
    },
    {
      "provider_id": "microsoft",
      "provider_name": "Microsoft",
      "enabled": true,
      "scopes": ["openid", "email", "profile"]
    }
  ]
}
```

## User Interface Behavior

When users visit the login page, they see:

```
┌─────────────────────────────────────┐
│      Sign in to Tools Gateway       │
├─────────────────────────────────────┤
│                                     │
│  Local Sign In                      │
│  ┌─────────────────────────────┐   │
│  │ Email    [____________]     │   │
│  │ Password [____________]     │   │
│  │        [Sign In]            │   │
│  └─────────────────────────────┘   │
│                                     │
│  ─────────── OR ───────────────    │
│                                     │
│  Sign in with OAuth                 │
│  ┌─────────────────────────────┐   │
│  │ [Sign in with Google]       │   │
│  │ [Sign in with Microsoft]    │   │
│  │ [Sign in with GitHub]       │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

## API Endpoints Summary

### Local Authentication
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/login/local` | POST | Login with email/password |

### OAuth Authentication
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/providers` | GET | List available OAuth providers |
| `/auth/login?provider_id=google` | POST | Initiate OAuth flow |
| `/auth/callback` | GET | OAuth callback (automatic) |

### Universal (Both Methods)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/user` | GET | Get current user info |
| `/auth/logout` | POST | Logout |

## Common Scenarios

### Scenario 1: Enterprise (SSO Only)

**Goal**: All users must sign in with company Google Workspace

**Setup**:
```bash
# 1. Configure Google OAuth with company domain
curl -X POST http://localhost:8021/admin/oauth/providers \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "provider_id": "google",
    "template": "google",
    "client_id": "COMPANY_CLIENT_ID",
    "client_secret": "COMPANY_SECRET"
  }'

# 2. Don't create local users (except admin for emergencies)
# 3. Users automatically get "user" role on first Google sign-in
# 4. Admins can upgrade specific users to admin role
```

### Scenario 2: Mixed Environment

**Goal**: Admins use local auth, users use OAuth

**Setup**:
```bash
# 1. Create local admin accounts
curl -X POST http://localhost:8021/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "email": "admin@company.com",
    "password": "SecurePass",
    "provider": "local",
    "roles": ["admin"]
  }'

# 2. Configure multiple OAuth providers
# - Google for gmail users
# - Microsoft for company users
# - GitHub for developers

# 3. Users choose their preferred OAuth method
```

### Scenario 3: Internal Tool (Local Only)

**Goal**: No external dependencies, all local

**Setup**:
```bash
# 1. Don't configure any OAuth providers

# 2. Create all users locally
curl -X POST http://localhost:8021/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "email": "user@internal.com",
    "password": "SecurePass",
    "provider": "local",
    "roles": ["user"]
  }'

# 3. Users sign in with email/password only
```

## Switching Individual Users

### Convert OAuth User to Local User

**Not recommended**, but if needed:

```bash
# 1. Create new local user with same email
curl -X POST http://localhost:8021/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "email": "existing@gmail.com",  # Same email
    "password": "NewPassword",
    "provider": "local",
    "roles": ["user"]
  }'

# This will fail because email must be unique
# Instead, you need to delete the OAuth user first
```

**Better approach**: User can have **one provider only**. If you need to switch:

1. Admin deletes old user
2. Admin creates new user with different provider
3. Admin reassigns roles

### Allow User to Use Both?

**No** - Each user account has one provider. Users must choose:
- Local (email/password)
- Google
- Microsoft
- GitHub

**Why?** Security and clarity - one authentication method per account prevents confusion and security issues.

## Checking Current Mode

### For Administrators

```bash
# Check what authentication methods are available
curl http://localhost:8021/auth/providers

# List all users and their providers
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8021/admin/users
```

**Response**:
```json
{
  "users": [
    {
      "user_id": "user_abc123",
      "email": "admin",
      "provider": "local",        ← Local auth
      "roles": ["Administrator"]
    },
    {
      "user_id": "user_def456",
      "email": "john@gmail.com",
      "provider": "google",       ← OAuth
      "roles": ["Standard User"]
    }
  ]
}
```

### For Users

When you try to sign in, the UI shows:
- Local sign-in form (if you're a local user)
- OAuth buttons (if OAuth providers are configured)

Try signing in with both methods - you'll see which one works for your account.

## Security Considerations

1. **Backup Admin**: Always keep a local admin account for emergency access
2. **OAuth Downtime**: If OAuth provider is down, local users can still sign in
3. **Password Security**: Local passwords are hashed with SHA-256
4. **Token Security**: JWT tokens work the same regardless of auth method
5. **Audit Trail**: All sign-ins are logged with the provider used

## Summary

**Key Points**:
- ✅ Both local and OAuth work **simultaneously**
- ✅ No "switching" needed - both are always available
- ✅ Each user has **one** provider (local, google, microsoft, or github)
- ✅ Same permissions/roles regardless of auth method
- ✅ Same JWT tokens regardless of auth method
- ✅ Admins can enable/disable OAuth providers independently

**Recommendation**:
- Use **local auth** for admin accounts (backup access)
- Use **OAuth** for regular users (easier management)
- Enable **multiple OAuth providers** to give users choice

For more information:
- `LOCAL_AUTH_GUIDE.md` - Local authentication details
- `GOOGLE_OAUTH_FIX.md` - OAuth configuration guide
- `QUICK_START.md` - Quick reference

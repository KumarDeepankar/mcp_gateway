# Google OAuth 2.1 Configuration Fix

## Problem

You received this error when trying to sign in with Google:
```
You can't sign in to this app because it doesn't comply with Google's OAuth 2.0 policy
Error 400: invalid_request
```

## Root Cause

Your OAuth credentials were for an **"installed"** application type, but the Tools Gateway needs **"web"** application credentials.

**Wrong credentials (what you had)**:
```json
{
  "installed": {
    "client_id": "...",
    "redirect_uris": ["http://localhost"]  // ❌ Wrong format
  }
}
```

**Correct credentials (what you need)**:
```json
{
  "web": {
    "client_id": "...",
    "redirect_uris": ["http://localhost:8021/auth/callback"]  // ✅ Correct
  }
}
```

## Solution: Create Web Application Credentials

### Step 1: Go to Google Cloud Console

1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project: `himan-474623`
3. Navigate to **APIs & Services** → **Credentials**

### Step 2: Create Web Application OAuth Client

1. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
2. **Application type**: Select **Web application** ⚠️ (NOT Desktop/Installed)
3. **Name**: `tools_gateway_web` (or any name you prefer)
4. **Authorized redirect URIs**: Click **+ ADD URI** and add:
   ```
   http://localhost:8021/auth/callback
   ```
   If using ngrok, also add:
   ```
   https://your-ngrok-url.ngrok-free.app/auth/callback
   ```

5. Click **CREATE**

### Step 3: Download Credentials

After creation, you'll see a dialog with:
- Client ID: `XXXXX.apps.googleusercontent.com`
- Client secret: `GOCSPX-XXXXX`

Click **DOWNLOAD JSON** and you'll get:

```json
{
  "web": {
    "client_id": "755202107433-NEWID.apps.googleusercontent.com",
    "project_id": "himan-474623",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-NEWSECRET",
    "redirect_uris": [
      "http://localhost:8021/auth/callback"
    ]
  }
}
```

### Step 4: Configure in Tools Gateway

Now use the **local authentication** to configure Google OAuth:

```bash
# 1. Login as admin
curl -X POST http://localhost:8021/auth/login/local \
  -H "Content-Type: application/json" \
  -d '{"email":"admin","password":"admin"}'

# Copy the access_token from the response

# 2. Add Google OAuth provider
curl -X POST http://localhost:8021/admin/oauth/providers \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "google",
    "template": "google",
    "client_id": "755202107433-NEWID.apps.googleusercontent.com",
    "client_secret": "GOCSPX-NEWSECRET"
  }'
```

### Step 5: Test Google Sign-In

1. Open the web UI: http://localhost:8021
2. Click "Sign in with Google"
3. You should now see the Google OAuth consent screen ✅

## Key Differences

| Installed App | Web App |
|--------------|---------|
| `"installed": {...}` | `"web": {...}` |
| `"redirect_uris": ["http://localhost"]` | `"redirect_uris": ["http://localhost:8021/auth/callback"]` |
| For desktop/CLI apps | For web applications |
| No specific callback | Specific callback endpoint |
| ❌ Doesn't work with Tools Gateway | ✅ Works perfectly |

## Why This Matters

- **OAuth 2.1 Compliance**: Web applications MUST use web application credentials
- **Security**: Proper redirect URI validation prevents authorization code interception
- **PKCE Support**: Your code implements PKCE (Proof Key for Code Exchange), which requires proper web app setup

## Additional Security Tips

### 1. Configure OAuth Consent Screen

In Google Cloud Console:
- **APIs & Services** → **OAuth consent screen**
- Set **User type**: Internal (for G Suite) or External (for public)
- Add required scopes: `email`, `profile`, `openid`
- Add test users if using External with "Testing" status

### 2. Production Setup

For production, use HTTPS:

1. Update redirect URI in Google Cloud Console:
   ```
   https://your-domain.com/auth/callback
   ```

2. Configure the OAuth provider with HTTPS redirect:
   ```bash
   curl -X POST https://your-domain.com/admin/oauth/providers \
     -H "Authorization: Bearer TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "provider_id": "google",
       "template": "google",
       "client_id": "YOUR_CLIENT_ID",
       "client_secret": "YOUR_CLIENT_SECRET"
     }'
   ```

### 3. Multiple Redirect URIs

You can add multiple redirect URIs for different environments:

```
Development:
http://localhost:8021/auth/callback

Staging:
https://staging.example.com/auth/callback

Production:
https://app.example.com/auth/callback

Ngrok/Testing:
https://abc123.ngrok-free.app/auth/callback
```

## Verification Checklist

✅ Created **Web application** OAuth client (not Installed)
✅ Added redirect URI: `http://localhost:8021/auth/callback`
✅ Downloaded credentials with `"web": {...}` structure
✅ Configured OAuth provider using local admin authentication
✅ Tested sign-in flow - no more 400 error!

## What You Can Do Now

1. ✅ **Use Local Authentication**: Sign in with `admin`/`admin`
2. ✅ **Configure OAuth Providers**: Add Google, Microsoft, GitHub
3. ✅ **Manage Users**: Create local users with passwords
4. ✅ **Manage the Gateway**: Full admin access to all features

## Summary

The issue was simple: **wrong application type**. By switching from "Installed" to "Web" application credentials, Google OAuth now works perfectly with the Tools Gateway's OAuth 2.1 implementation.

**You're all set!** 🎉

For more information, see:
- `LOCAL_AUTH_GUIDE.md` - Complete authentication guide
- `QUICK_START.md` - Quick reference
- `IMPLEMENTATION_SUMMARY.md` - Technical details

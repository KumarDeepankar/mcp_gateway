# OAuth Provider Management - User Interface Guide

## Overview

The Tools Gateway now provides a complete web-based interface for managing OAuth 2.1 providers. You can add, configure, and manage authentication providers directly from the portal without editing configuration files.

## Features

✅ **Template-Based Configuration** - Pre-configured templates for Google, Microsoft, and GitHub
✅ **Custom Provider Support** - Add any OAuth 2.1 compatible provider
✅ **Visual Form Builder** - Intuitive forms with validation
✅ **Scope Management** - Add/remove OAuth scopes visually
✅ **Setup Guides** - Step-by-step instructions for each provider
✅ **Real-time Refresh** - See changes immediately
✅ **Encrypted Storage** - Client secrets are automatically encrypted

## Accessing the OAuth Management Interface

### 1. Start the Gateway

```bash
cd tools_gateway
python main.py
```

The gateway will start on `http://localhost:8021`

### 2. Open the Portal

```bash
open http://localhost:8021
```

Or visit: `http://localhost:8021` in your browser

### 3. Navigate to OAuth Providers Tab

Click on the **"OAuth Providers"** tab in the left sidebar.

## Adding an OAuth Provider

### Method 1: Using a Template (Recommended)

1. **Click "Add OAuth Provider"** button
2. **Select Provider Template:**
   - Google OAuth
   - Microsoft OAuth
   - GitHub OAuth
   - Custom Provider

3. **Template Auto-Fills:**
   - Provider ID
   - Provider Name
   - Authorization URL
   - Token URL
   - User Info URL
   - Default Scopes

4. **Enter Your Credentials:**
   - Client ID (from provider's developer console)
   - Client Secret (will be encrypted)

5. **Review Scopes:**
   - Default scopes are pre-filled
   - Add or remove scopes as needed

6. **Click "Save Provider"**

### Method 2: Custom Provider

1. **Click "Add OAuth Provider"**
2. **Leave template as "Custom Provider"**
3. **Fill in all fields manually:**
   - Provider ID (unique, lowercase)
   - Provider Name (display name)
   - Client ID
   - Client Secret
   - Authorization URL
   - Token URL
   - User Info URL
   - Scopes

4. **Click "Save Provider"**

## Detailed Configuration Guide

### Google OAuth Setup

#### Step 1: Get Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Navigate to **"APIs & Services"** → **"Credentials"**
4. Click **"Create Credentials"** → **"OAuth 2.0 Client ID"**
5. Application type: **Web application**
6. Add Authorized redirect URI:
   ```
   http://localhost:8021/auth/callback
   ```
   For production, use your domain:
   ```
   https://yourdomain.com/auth/callback
   ```
7. Click **"Create"**
8. Copy **Client ID** and **Client Secret**

#### Step 2: Configure in Portal

1. In the portal, click **"Add OAuth Provider"**
2. Select **"Google OAuth"** template
3. Paste your **Client ID**
4. Paste your **Client Secret**
5. Verify scopes: `openid`, `email`, `profile`
6. Click **"Save Provider"**

### Microsoft OAuth Setup

#### Step 1: Get Credentials

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **"Azure Active Directory"** → **"App registrations"**
3. Click **"New registration"**
4. Enter application name
5. Supported account types: Choose based on your needs
6. Add Redirect URI (Web):
   ```
   http://localhost:8021/auth/callback
   ```
7. After creation, go to **"Certificates & secrets"**
8. Create a new **client secret**
9. Copy **Application (client) ID** and **Client Secret**

#### Step 2: Configure in Portal

1. Click **"Add OAuth Provider"**
2. Select **"Microsoft OAuth"** template
3. Paste your **Client ID**
4. Paste your **Client Secret**
5. Verify scopes: `openid`, `email`, `profile`
6. Click **"Save Provider"**

### GitHub OAuth Setup

#### Step 1: Get Credentials

1. Go to GitHub **Settings** → [**Developer settings**](https://github.com/settings/developers)
2. Click **"OAuth Apps"** → **"New OAuth App"**
3. Fill in application details:
   - **Application name:** Your app name
   - **Homepage URL:** Your homepage
   - **Authorization callback URL:**
     ```
     http://localhost:8021/auth/callback
     ```
4. Click **"Register application"**
5. Copy **Client ID**
6. Generate a new **client secret** and copy it

#### Step 2: Configure in Portal

1. Click **"Add OAuth Provider"**
2. Select **"GitHub OAuth"** template
3. Paste your **Client ID**
4. Paste your **Client Secret**
5. Verify scopes: `read:user`, `user:email`
6. Click **"Save Provider"**

## Managing Scopes

### Understanding OAuth Scopes

Scopes define what permissions your application requests from the OAuth provider.

**Common Scopes:**
- `openid` - OpenID Connect authentication
- `email` - Access to user's email
- `profile` - Access to user's profile information
- `read:user` - Read user data (GitHub)
- `user:email` - Read user email (GitHub)

### Adding a Scope

1. In the OAuth provider form, find the **"Scopes"** section
2. Enter the scope name in the input field
3. Click **"Add"** button
4. The scope appears as a tag

### Removing a Scope

1. Find the scope tag in the **"Scopes"** section
2. Click the **×** button on the tag
3. The scope is removed

## Viewing OAuth Setup Guide

1. Click the **"Setup Guide"** button in the toolbar
2. A modal opens with step-by-step instructions for:
   - Google OAuth
   - Microsoft OAuth
   - GitHub OAuth

3. Each guide includes:
   - Direct links to developer consoles
   - Detailed setup steps
   - Redirect URI examples

## Testing Your OAuth Configuration

### 1. After Saving Provider

Once you save a provider, it appears in the providers list with:
- Provider icon
- Provider name
- Provider ID
- Configured scopes
- Status badge (Enabled/Disabled)

### 2. Testing Login

1. Open a new browser tab (incognito mode recommended)
2. Go to `http://localhost:8021`
3. You should see **"Sign in with [Provider]"** buttons
4. Click on your configured provider
5. You'll be redirected to the OAuth provider
6. Authorize the application
7. You'll be redirected back to the portal
8. You're now authenticated!

### 3. Verifying Authentication

After successful login:
- Your email/name appears in the header
- You can access admin features (if assigned admin role)
- JWT token is stored in localStorage

## Refreshing Providers

To reload the providers list:
1. Click the **"Refresh"** button in the toolbar
2. The list updates with current providers

## Removing a Provider

1. Find the provider card you want to remove
2. Click the **"Remove"** button
3. Confirm the deletion
4. The provider is removed immediately

**Note:** Removing a provider does not delete existing users who authenticated with it.

## Advanced Configuration

### Enable/Disable Provider

In the OAuth provider form:
1. Expand **"Advanced Options"**
2. Toggle **"Enable this provider"** checkbox
3. Disabled providers won't show on the login page

### Custom Redirect URI

By default, redirect URI is:
```
http://localhost:8021/auth/callback
```

For production, configure your OAuth provider with:
```
https://yourdomain.com/auth/callback
```

No changes needed in the portal form - the gateway automatically handles the redirect.

## Security Considerations

### Client Secret Encryption

- Client secrets are **automatically encrypted** before storage
- Encryption uses Fernet (AES-128-CBC + HMAC-SHA256)
- Encryption key is stored in `.encryption_key` file
- **Backup the encryption key file** for disaster recovery

### Redirect URI Validation

- The gateway validates redirect URIs to prevent DNS rebinding attacks
- Only configured OAuth providers can authenticate
- State parameter prevents CSRF attacks
- PKCE protects against authorization code interception

### Best Practices

1. **Never commit OAuth secrets to version control**
2. **Use HTTPS in production**
3. **Restrict redirect URIs to known domains**
4. **Regularly rotate client secrets**
5. **Monitor audit logs for suspicious activity**
6. **Disable unused providers**

## Troubleshooting

### Provider Not Appearing on Login Page

**Problem:** Added provider doesn't show up

**Solutions:**
- Click **"Refresh"** button
- Check if provider is **enabled** (Advanced Options)
- Clear browser cache and reload

### "Invalid redirect_uri" Error

**Problem:** OAuth provider shows redirect URI error

**Solutions:**
- Verify redirect URI in provider console exactly matches:
  ```
  http://localhost:8021/auth/callback
  ```
- For production, update to your domain
- No trailing slashes
- Match http/https exactly

### "Client authentication failed" Error

**Problem:** Authentication fails at OAuth provider

**Solutions:**
- Verify Client ID is correct
- Verify Client Secret is correct
- Check if OAuth app is approved/active
- Ensure scopes are supported by provider

### Cannot Access Admin Features

**Problem:** Logged in but can't manage providers

**Solutions:**
- Check your user role in **"Users & Roles"** tab
- First user is auto-assigned admin role
- Contact admin to assign appropriate role

## API Reference

### List Providers

```bash
curl http://localhost:8021/auth/providers
```

Response:
```json
{
  "providers": [
    {
      "provider_id": "google",
      "provider_name": "Google",
      "enabled": true,
      "scopes": ["openid", "email", "profile"]
    }
  ]
}
```

### Add Provider (Admin Only)

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "google",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "provider_name": "Google",
    "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_url": "https://oauth2.googleapis.com/token",
    "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
    "scopes": ["openid", "email", "profile"],
    "enabled": true
  }' \
  http://localhost:8021/admin/oauth/providers
```

### Remove Provider (Admin Only)

```bash
curl -X DELETE \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8021/admin/oauth/providers/google
```

## Form Validation

The OAuth provider form validates:

✅ **Provider ID:** Lowercase, no spaces, alphanumeric + hyphens/underscores
✅ **Required Fields:** All required fields must be filled
✅ **URL Format:** OAuth endpoints must be valid URLs
✅ **Scopes:** At least one scope required
✅ **Unique Provider ID:** Cannot duplicate existing provider

Invalid submissions show error messages.

## Keyboard Shortcuts

- **Enter** in scope input → Add scope
- **Escape** → Close modal
- **Tab** → Navigate form fields

## Browser Compatibility

Tested and working on:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## FAQ

**Q: Can I have multiple OAuth providers?**
A: Yes! Add as many providers as needed. Users can choose which one to use.

**Q: Can I edit an existing provider?**
A: Currently, remove and re-add. Edit functionality coming soon.

**Q: Is the Client Secret visible after saving?**
A: No. Client secrets are encrypted and never displayed after saving.

**Q: Can non-admin users add providers?**
A: No. Only users with `oauth:manage` permission can add/remove providers.

**Q: What happens to existing users if I remove a provider?**
A: Users remain in the system but cannot login via that provider. Assign them another provider or role.

## Support

For issues or questions:
1. Check audit logs in the **"Audit Logs"** tab
2. Review browser console for errors
3. Check server logs for detailed error messages
4. Refer to the [ENTERPRISE_SECURITY_GUIDE.md](./ENTERPRISE_SECURITY_GUIDE.md)

## Summary

The OAuth Provider Management UI provides a complete, user-friendly interface for configuring authentication without touching configuration files. With template support, visual validation, and comprehensive guides, you can have OAuth authentication running in minutes!

🎉 **Ready to configure your OAuth providers!**

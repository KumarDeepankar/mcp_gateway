# Quick Start Guide - RBAC & OAuth2 Integration

## 🚀 Get Started in 5 Steps

### Step 1: Generate JWT Secret (2 minutes)

```bash
# Generate a secure 32-byte secret
openssl rand -base64 32

# Output example: 3K9Xm2P5nQ8rT6wY9zA1bC4dF7gH0jK3mN5pQ8sT1vX4
```

Save this secret - you'll need it for both services!

---

### Step 2: Configure Environment Variables (3 minutes)

Create `.env` file in **both** service directories:

#### tools_gateway/.env
```bash
# JWT Configuration (USE THE SAME SECRET IN BOTH SERVICES!)
JWT_SECRET=3K9Xm2P5nQ8rT6wY9zA1bC4dF7gH0jK3mN5pQ8sT1vX4
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=480

# OAuth Providers (Get these from Google/Microsoft/GitHub developer consoles)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Optional: Microsoft, GitHub
# MICROSOFT_CLIENT_ID=your-microsoft-client-id
# MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
```

#### agentic_search/.env
```bash
# JWT Configuration (MUST MATCH tools_gateway!)
JWT_SECRET=3K9Xm2P5nQ8rT6wY9zA1bC4dF7gH0jK3mN5pQ8sT1vX4
JWT_ALGORITHM=HS256

# Service URLs
TOOLS_GATEWAY_URL=http://localhost:8021
AGENTIC_SEARCH_URL=http://localhost:8023
MCP_GATEWAY_URL=http://localhost:8021

# Session Configuration
SESSION_COOKIE_NAME=session_id
SESSION_COOKIE_MAX_AGE=28800
```

---

### Step 3: Set Up OAuth Provider (10 minutes)

#### For Google OAuth:

1. **Go to Google Cloud Console:**
   https://console.cloud.google.com/

2. **Create a new project** (or select existing)

3. **Enable Google+ API:**
   - APIs & Services → Library
   - Search "Google+ API"
   - Click Enable

4. **Create OAuth 2.0 Credentials:**
   - APIs & Services → Credentials
   - Create Credentials → OAuth client ID
   - Application type: Web application
   - Name: "Agentic Search"
   - Authorized redirect URIs:
     ```
     http://localhost:8021/auth/callback
     http://localhost:8021/auth/callback-redirect
     ```
   - Click Create

5. **Copy Client ID and Secret:**
   - Download JSON or copy from screen
   - Add to `tools_gateway/.env`

#### For Microsoft OAuth:

1. **Go to Azure Portal:**
   https://portal.azure.com/

2. **Register application:**
   - Azure Active Directory → App registrations → New registration
   - Name: "Agentic Search"
   - Redirect URI: `http://localhost:8021/auth/callback`

3. **Create client secret:**
   - Certificates & secrets → New client secret
   - Copy the secret value

4. **Add to .env**

---

### Step 4: Configure OAuth Provider in tools_gateway (2 minutes)

**Option A: Via Admin UI** (Recommended)

```bash
# 1. Start tools_gateway
cd tools_gateway
python -m uvicorn tools_gateway.main:app --port 8021

# 2. Open browser
open http://localhost:8021/

# 3. Login with default admin credentials
Email: admin
Password: admin

# 4. Go to Admin Panel → OAuth Providers
# 5. Click "Add Provider"
# 6. Select "Google" template
# 7. Paste your Client ID and Secret
# 8. Click Save
```

**Option B: Via Python Script**

```python
# tools_gateway/setup_oauth.py
from tools_gateway import oauth_provider_manager

# Add Google provider
oauth_provider_manager.add_provider(
    provider_id="google",
    client_id="your-google-client-id",
    client_secret="your-google-client-secret",
    template="google"  # Uses built-in Google config
)

print("✅ OAuth provider configured!")
```

Run: `python setup_oauth.py`

**Option C: Via Database**

```bash
# SQLite command
sqlite3 tools_gateway/tools_gateway.db

INSERT INTO oauth_providers (
    provider_id,
    provider_name,
    client_id,
    client_secret,
    authorize_url,
    token_url,
    userinfo_url,
    scopes,
    enabled
) VALUES (
    'google',
    'Google',
    'your-google-client-id',
    'your-google-client-secret',
    'https://accounts.google.com/o/oauth2/v2/auth',
    'https://oauth2.googleapis.com/token',
    'https://www.googleapis.com/oauth2/v2/userinfo',
    '["openid","email","profile"]',
    1
);

.quit
```

---

### Step 5: Test the Setup (5 minutes)

#### Start Both Services

Terminal 1 (tools_gateway):
```bash
cd tools_gateway
python -m uvicorn tools_gateway.main:app --port 8021 --reload
```

Terminal 2 (agentic_search):
```bash
cd agentic_search
python server.py
# Or: uvicorn server:app --port 8023 --reload
```

#### Test OAuth Login Flow

1. **Open agentic_search:**
   ```bash
   open http://localhost:8023/auth/login
   ```

2. **Click "Login with Google"**
   - Should redirect to Google
   - Ask for permission
   - Redirect back to agentic_search
   - You should be logged in!

3. **Verify you're logged in:**
   ```bash
   curl http://localhost:8023/auth/user \
     -H "Cookie: session_id=<your-session-id>"
   ```

   Should return:
   ```json
   {
     "email": "you@gmail.com",
     "name": "Your Name",
     "sub": "user_xyz",
     "provider": "google"
   }
   ```

#### Test Tool Access

1. **Get tools list:**
   ```bash
   # Get your JWT token from browser dev tools or session
   curl http://localhost:8021/mcp \
     -H "Authorization: Bearer <your-jwt-token>" \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "method": "tools/list",
       "id": "test-1"
     }'
   ```

   Should return tools filtered by your role!

2. **Call a tool:**
   ```bash
   curl http://localhost:8021/mcp \
     -H "Authorization: Bearer <your-jwt-token>" \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "method": "tools/call",
       "id": "test-2",
       "params": {
         "name": "search_web",
         "arguments": {"query": "AI news"}
       }
     }'
   ```

---

## ✅ Verification Checklist

- [ ] JWT_SECRET is set in both `.env` files (and they match!)
- [ ] OAuth provider configured in tools_gateway
- [ ] Both services start without errors
- [ ] Can access http://localhost:8021 (tools_gateway)
- [ ] Can access http://localhost:8023 (agentic_search)
- [ ] Login flow works: click login → redirect to provider → redirect back
- [ ] After login, can see user info at `/auth/user`
- [ ] Can fetch tools list with authentication
- [ ] Tools are filtered based on user's role
- [ ] Unauthorized tool access returns 403 Forbidden
- [ ] Audit logs are being created in database

---

## 🔧 Troubleshooting

### "redirect_uri_mismatch" error

**Problem:** OAuth provider rejects redirect URI.

**Solution:**
1. Check OAuth console (Google/Microsoft)
2. Verify redirect URI exactly matches:
   ```
   http://localhost:8021/auth/callback
   http://localhost:8021/auth/callback-redirect
   ```
3. No trailing slash!
4. Protocol must match (http vs https)

### "Invalid JWT signature" error

**Problem:** JWT_SECRET mismatch between services.

**Solution:**
1. Check both `.env` files
2. Ensure JWT_SECRET is EXACTLY the same
3. Restart both services after changing .env
4. Verify with: `echo $JWT_SECRET` (if using export)

### "No OAuth provider found" error

**Problem:** OAuth provider not configured in tools_gateway.

**Solution:**
1. Check database: `sqlite3 tools_gateway.db "SELECT * FROM oauth_providers;"`
2. If empty, run setup (Step 4)
3. Verify `enabled` field is 1
4. Restart tools_gateway

### "Permission denied" / 403 errors

**Problem:** User role doesn't have tool permissions.

**Solution:**
1. Login as admin (email: admin, password: admin)
2. Go to Admin Panel → Tools
3. Assign tools to "user" role
4. Or run SQL:
   ```sql
   INSERT INTO role_tool_permissions (role_id, server_id, tool_name)
   VALUES ('user', 'your-server-id', 'your-tool-name');
   ```
5. Logout and login again

### Services won't start

**Problem:** Port already in use or missing dependencies.

**Solution:**
1. Check ports: `lsof -i :8021` and `lsof -i :8023`
2. Kill existing processes or change ports
3. Install dependencies:
   ```bash
   # tools_gateway
   cd tools_gateway
   pip install -r requirements.txt

   # agentic_search
   cd agentic_search
   pip install -r requirements.txt
   ```

---

## 🎯 What's Next?

### Immediate Actions:

1. **Change default admin password:**
   ```bash
   # Login to http://localhost:8021
   # Go to Admin → Users → admin → Change Password
   ```

2. **Create additional users:**
   - Option A: Have them login via OAuth (auto-creates user)
   - Option B: Create manually in Admin UI

3. **Assign tool permissions:**
   - Go to Admin → Tools
   - For each tool, select which roles can access it

### For Production Deployment:

1. **Use HTTPS:**
   - Get SSL certificate (Let's Encrypt)
   - Configure reverse proxy (nginx/Apache)
   - Update redirect URIs in OAuth console

2. **Secure JWT:**
   - Use environment variable for JWT_SECRET
   - Consider switching to RS256 (asymmetric)
   - Enable token revocation

3. **Database:**
   - Migrate from SQLite to PostgreSQL
   - Set up backups
   - Enable connection pooling

4. **Monitoring:**
   - Set up Prometheus + Grafana
   - Configure alerts for failed logins
   - Monitor tool usage metrics

5. **Rate Limiting:**
   - Enable rate limiting middleware
   - Configure per-user limits
   - Add IP-based rate limiting

---

## 📚 Additional Resources

- **Detailed Design:** See `RBAC_OAUTH2_DESIGN.md`
- **Implementation Summary:** See `IMPLEMENTATION_SUMMARY.md`
- **OAuth Setup Guides:**
  - Google: https://developers.google.com/identity/protocols/oauth2
  - Microsoft: https://docs.microsoft.com/en-us/azure/active-directory/develop/
  - GitHub: https://docs.github.com/en/developers/apps/building-oauth-apps

---

## 🆘 Getting Help

If you encounter issues:

1. **Check logs:**
   ```bash
   # tools_gateway logs
   tail -f tools_gateway/logs/gateway.log

   # agentic_search logs
   tail -f agentic_search/logs/search.log
   ```

2. **Check database:**
   ```bash
   sqlite3 tools_gateway/tools_gateway.db

   -- Check OAuth providers
   SELECT * FROM oauth_providers;

   -- Check users
   SELECT * FROM rbac_users;

   -- Check roles
   SELECT * FROM rbac_roles;

   -- Check permissions
   SELECT * FROM role_tool_permissions;

   -- Check audit logs
   SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10;
   ```

3. **Enable debug logging:**
   ```bash
   # In .env
   LOG_LEVEL=DEBUG
   ```

4. **Test JWT manually:**
   ```python
   from jose import jwt

   token = "your-jwt-token"
   secret = "your-jwt-secret"

   try:
       payload = jwt.decode(token, secret, algorithms=["HS256"])
       print("✅ Valid token:", payload)
   except Exception as e:
       print("❌ Invalid token:", e)
   ```

---

**Success!** 🎉

If all checks pass, you now have a fully functional OAuth2 + RBAC system!

Users can:
- ✅ Login via Google/Microsoft/GitHub
- ✅ Access tools based on their role
- ✅ Have all actions audited

Admins can:
- ✅ Manage users and roles
- ✅ Assign tool permissions
- ✅ View audit logs
- ✅ Configure OAuth providers

---

**Need more help?** Refer to the detailed design document or implementation summary.

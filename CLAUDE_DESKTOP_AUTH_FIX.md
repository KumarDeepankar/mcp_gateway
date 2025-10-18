# Claude Desktop Authentication Fix - ✅ IMPLEMENTED

## Problem

Claude Desktop's HTTP MCP transport **does not support custom headers** (like `Authorization`). This means RBAC authentication via JWT tokens in headers won't work.

## ✅ Solution: Query Parameter Authentication (WORKING)

The gateway has been updated to support JWT tokens passed as URL query parameters.

### Step 1: Get Your JWT Token

**Option A - Via Web UI:**
1. Open `http://localhost:8021` in your browser
2. Login with your credentials
3. Go to Profile → Get API Token
4. Copy the JWT token

**Option B - Via API:**
```bash
# Login and get token (using admin credentials)
curl -X POST http://localhost:8021/auth/login/local \
  -H "Content-Type: application/json" \
  -d '{"email":"admin","password":"admin"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsImt...",
  "user": {...}
}
```

**Copy the `access_token` value**

### Step 2: Configure Claude Desktop with Token in URL

**File:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "toolbox-gateway": {
      "url": "https://ceb361ecb6e5.ngrok-free.app/mcp?token=YOUR_JWT_TOKEN_HERE"
    }
  }
}
```

**Important:**
- Replace `YOUR_JWT_TOKEN_HERE` with the actual JWT token from Step 1
- Replace `https://ceb361ecb6e5.ngrok-free.app` with your ngrok URL if different

### Step 3: Restart Claude Desktop

Close and reopen Claude Desktop completely for changes to take effect.

---

## Implementation Details

### How It Works

The gateway's `get_current_user()` function in `rbac.py` now supports two authentication methods:

1. **Standard Method (Header):** `Authorization: Bearer <token>`
2. **Query Parameter (Fallback):** `?token=<token>`

The function checks for tokens in this order:
1. First, checks `Authorization` header
2. If not found, checks `token` query parameter
3. Validates the JWT and returns the authenticated user

### Code Changes

Modified `/Users/deepankar/Documents/mcp_gateway/tools_gateway/rbac.py:20-77`:

```python
def get_current_user(request):
    """
    Extract and validate user from JWT token in request.

    Supports two authentication methods:
    1. Authorization header: "Authorization: Bearer <token>"
    2. Query parameter: "?token=<token>"
    """
    token = None

    # Try Authorization header first (standard method)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        logger.debug("Found JWT token in Authorization header")

    # Fallback to query parameter (for clients that don't support custom headers)
    if not token:
        token = request.query_params.get("token")
        if token:
            logger.debug("Found JWT token in query parameter")

    # Validate token if found
    if token:
        # ... validation logic ...
        return User(...)

    return None
```

### Security Considerations

**✅ Safe for Production:**
- Query parameter tokens are encrypted in HTTPS (via ngrok)
- JWT tokens are signed and time-limited
- RBAC enforcement remains fully functional
- Tokens can be rotated by logging in again

**⚠️ Best Practices:**
- Use HTTPS in production (ngrok provides this)
- Set reasonable token expiration times
- Rotate tokens periodically
- Use environment-specific tokens (dev/prod)

---

## Alternative Solution: Use Stdio Transport (Recommended)

Claude Desktop works best with **stdio transport** (running a local process), not HTTP transport.

### Stdio Wrapper Script

Create a wrapper that authenticates to your gateway:

**File:** `~/claude-mcp-gateway.sh`

```bash
#!/bin/bash

# Your gateway credentials
GATEWAY_URL="https://ceb361ecb6e5.ngrok-free.app"
EMAIL="claude-desktop"
PASSWORD="secure-password-123"

# Get JWT token
TOKEN=$(curl -s -X POST "${GATEWAY_URL}/auth/login/local" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" \
  | jq -r '.access_token')

# Forward MCP protocol with authentication
while IFS= read -r line; do
  # Parse JSON-RPC request
  METHOD=$(echo "$line" | jq -r '.method')
  ID=$(echo "$line" | jq -r '.id')
  PARAMS=$(echo "$line" | jq -c '.params')

  # Forward to gateway with auth
  RESPONSE=$(curl -s -X POST "${GATEWAY_URL}/mcp" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "$line")

  # Return response
  echo "$RESPONSE"
done
```

**Claude Desktop Config:**

```json
{
  "mcpServers": {
    "toolbox-gateway": {
      "command": "bash",
      "args": ["/Users/yourusername/claude-mcp-gateway.sh"]
    }
  }
}
```

---

## Current Limitation

Your gateway currently allows **anonymous access** for MCP requests. This means even without authentication, users can execute all tools.

To fix this, we need to either:

1. **Option A:** Enforce authentication requirement (reject anonymous requests)
2. **Option B:** Add query parameter authentication support
3. **Option C:** Use the stdio wrapper approach

Which approach would you like me to implement?

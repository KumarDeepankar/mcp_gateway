# Claude Desktop Tool Access Control Guide

## Overview

Your MCP Gateway has a comprehensive Role-Based Access Control (RBAC) system that allows you to restrict which tools Claude Desktop (or any MCP client) can access.

## Current Status

✅ **Gateway is running:** `http://localhost:8021`
✅ **NgrokURL:** `https://ceb361ecb6e5.ngrok-free.app`
✅ **Claude Desktop:** Connected and working
✅ **FastMCP Server:** Running at `http://localhost:8002/sse`
✅ **Available Tools:**
- `fuzzy_autocomplete` - Intelligent fuzzy autocomplete
- `validate_entity` - Entity validation

---

## How RBAC Works

### Architecture

```
┌─────────────────┐
│ Claude Desktop  │
│   (MCP Client)  │
└────────┬────────┘
         │ JWT Token
         │ (Bearer Auth)
         ▼
┌─────────────────────────────────────┐
│     MCP Gateway (Port 8021)         │
│  ┌────────────────────────────┐     │
│  │   RBAC Enforcement Layer   │     │
│  │  - Verify JWT Token        │     │
│  │  - Check User Permissions  │     │
│  │  - Check Tool Permissions  │     │
│  └────────────────────────────┘     │
└────────┬────────────────────────────┘
         │ Only if ALLOWED
         ▼
┌─────────────────────────────┐
│  FastMCP Backend Server     │
│  (Executes Actual Tool)     │
└─────────────────────────────┘
```

### Security Model

**Deny by Default:**
- Users can ONLY execute tools explicitly assigned to their role
- No assignment = Access Denied
- Admin role has access to ALL tools (superuser)

**Multi-Level Control:**
1. **Permission Level:** `tool:execute` permission required
2. **Role Level:** User must have a role with tool access
3. **Tool Level:** Specific tools must be assigned to the role

---

## Step-by-Step Setup Guide

### 1. Access the Gateway UI

1. Open browser: `http://localhost:8021`
2. Login: `admin` / `admin`

### 2. Create a Restricted Role

**Navigation:** Security → Roles → Add Role

**Configuration:**
```
Role Name: Claude Desktop User
Description: Limited access for Claude Desktop client
Permissions:
  ✅ tool:view      - Can see available tools
  ✅ tool:execute   - Can execute tools
  ✅ server:view    - Can see servers
  ❌ tool:manage    - Cannot manage all tools
  ❌ server:add     - Cannot add servers
  ... (deselect admin permissions)
```

**Result:** Role created with basic tool execution rights

### 3. Assign Specific Tools to the Role

**Navigation:** Security → Roles → [Your New Role] → Manage Tool Access

**Configuration:**
```
Server: mcp_localhost_8002 (FastMCP Server)

Allowed Tools:
  ✅ fuzzy_autocomplete  - ALLOW
  ❌ validate_entity     - DENY (not selected)

Click "Save Tool Access"
```

**Result:** Role can ONLY execute `fuzzy_autocomplete`

### 4. Create User for Claude Desktop

**Navigation:** Security → Users → Add User

**Configuration:**
```
Email: claude-desktop
Password: secure-password-123
Name: Claude Desktop Client
Provider: Local
```

**Result:** User account created

### 5. Assign Role to User

**Navigation:** Security → Users → Find "claude-desktop" → Manage Roles

**Configuration:**
```
Select Roles:
  ✅ Claude Desktop User

Click "Assign Role"
```

**Result:** User has restricted permissions

### 6. Generate JWT Token

**Option A - Via UI:**
1. Logout from admin
2. Login as: `claude-desktop` / `secure-password-123`
3. Profile Menu → Get API Token
4. Copy the JWT token

**Option B - Via API:**
```bash
curl -X POST http://localhost:8021/auth/login/local \
  -H "Content-Type: application/json" \
  -d '{"email":"claude-desktop","password":"secure-password-123"}' | jq -r '.access_token'
```

### 7. Configure Claude Desktop

**File:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "toolbox-gateway": {
      "url": "https://ceb361ecb6e5.ngrok-free.app/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_JWT_TOKEN_HERE"
      }
    }
  }
}
```

**Important:** Replace `YOUR_JWT_TOKEN_HERE` with the actual JWT token from step 6

### 8. Restart Claude Desktop

Close and reopen Claude Desktop completely

---

## Testing Access Control

### Expected Behavior

**✅ ALLOWED - fuzzy_autocomplete:**
```
User: "Search for 'test'"
Claude: [Uses fuzzy_autocomplete tool successfully]
```

**❌ DENIED - validate_entity:**
```
User: "Validate entity test123"
Claude: [Receives "Permission Denied" error]
Gateway Log: "RBAC: User denied access to tool 'validate_entity'"
```

### Verification via Logs

**Check Gateway Logs:**
```bash
# Watch for RBAC enforcement
tail -f /tmp/gateway.log | grep RBAC
```

**Expected Log Output:**
```
✅ RBAC: Tool 'fuzzy_autocomplete' explicitly allowed for role 'Claude Desktop User'
❌ RBAC: User denied access to tool 'validate_entity' - No explicit role assignment found
```

---

## Advanced Configuration

### Option 1: Multiple Roles

Create different roles for different use cases:

```
Role: "Read-Only User"
  - fuzzy_autocomplete only

Role: "Power User"
  - fuzzy_autocomplete
  - validate_entity

Role: "Admin User"
  - ALL tools (via admin role)
```

### Option 2: Per-Server Restrictions

Assign different tools from different servers:

```
Server: mcp_localhost_8002
  ✅ fuzzy_autocomplete

Server: another_server
  ✅ some_other_tool
```

### Option 3: Audit Trail

**View Access Attempts:**
Navigation: Admin → Audit → Events

**Filter by:**
- User: `claude-desktop`
- Action: `tool_execution_*`

**Example Audit Entry:**
```json
{
  "user_id": "user_xyz",
  "action": "tool_execution_denied",
  "status": "denied",
  "details": {
    "tool_name": "validate_entity",
    "server_id": "mcp_localhost_8002",
    "reason": "No explicit role assignment"
  },
  "timestamp": "2025-10-18T00:00:00Z"
}
```

---

## Security Best Practices

### 1. JWT Token Security

**DO:**
- ✅ Use strong passwords for service accounts
- ✅ Rotate tokens periodically
- ✅ Store tokens securely (not in version control)
- ✅ Use HTTPS (ngrok) for production

**DON'T:**
- ❌ Share tokens between users
- ❌ Commit tokens to Git
- ❌ Use default passwords in production

### 2. Role Design

**Principle of Least Privilege:**
- Only grant permissions actually needed
- Start restrictive, expand as needed
- Separate roles for different use cases

**Example:**
```
❌ BAD: All users have "admin" role
✅ GOOD: Most users have "user" role with specific tool access
```

### 3. Monitoring

**Enable Audit Logging:**
- All tool executions are logged
- Failed access attempts are logged
- Review logs regularly for suspicious activity

---

## Troubleshooting

### Issue: Claude Desktop sees tools but can't execute them

**Symptom:** Tools appear in Claude Desktop, but execution fails with permission error

**Solution:**
1. Check user has `tool:execute` permission
2. Verify specific tool is assigned to user's role
3. Check JWT token is valid and not expired

**Diagnostic:**
```bash
# Check user's permissions
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8021/admin/users/USER_ID | jq '.roles'
```

### Issue: All tool executions denied

**Symptom:** Every tool execution returns "Permission Denied"

**Solution:**
1. Verify JWT token is in Authorization header
2. Check token is valid: `curl -H "Authorization: Bearer $TOKEN" http://localhost:8021/auth/me`
3. Ensure user has roles assigned
4. Check role has tool permissions

### Issue: Can't create roles or users

**Symptom:** API returns 403 Forbidden when creating roles

**Solution:**
1. Must be logged in as admin user
2. Check Authorization header has admin JWT token
3. Verify admin user has `role:manage` permission

---

## API Reference

### Create Role
```bash
POST /admin/roles
Authorization: Bearer $ADMIN_TOKEN

{
  "role_name": "Custom Role",
  "description": "Description",
  "permissions": ["tool:view", "tool:execute"]
}
```

### Assign Tools to Role
```bash
POST /admin/roles/{role_id}/tools
Authorization: Bearer $ADMIN_TOKEN

{
  "server_id": "mcp_localhost_8002",
  "allowed_tools": ["fuzzy_autocomplete"]
}
```

### Create User
```bash
POST /auth/register

{
  "email": "user@example.com",
  "password": "secure-password",
  "name": "User Name"
}
```

### Assign Role to User
```bash
POST /admin/users/{user_id}/roles
Authorization: Bearer $ADMIN_TOKEN

{
  "role_id": "role_xyz"
}
```

### Login and Get Token
```bash
POST /auth/login/local

{
  "email": "user@example.com",
  "password": "secure-password"
}

Response:
{
  "access_token": "eyJ...",
  "user": {...}
}
```

---

## Summary

✅ **Gateway Features:**
- Fine-grained tool-level access control
- JWT-based authentication
- Role-based permissions
- Audit trail for compliance
- Deny-by-default security model

✅ **Claude Desktop Integration:**
- Authenticated via JWT in headers
- Only sees/executes allowed tools
- Transparent to end user (they just see fewer tools)
- Secure even over public internet (via ngrok)

✅ **Production Ready:**
- HTTPS support (ngrok)
- Database-backed persistence
- Comprehensive audit logging
- Multi-tenant capable

---

## Next Steps

1. ✅ Follow steps 1-8 above to configure restricted access
2. ✅ Test by trying to execute both allowed and denied tools
3. ✅ Check audit logs to verify enforcement
4. ✅ Adjust permissions as needed for your use case

For questions or issues, check the gateway logs at `/tmp/gateway.log`

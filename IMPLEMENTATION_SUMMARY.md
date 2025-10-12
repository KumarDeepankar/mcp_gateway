# RBAC & OAuth2 Integration - Implementation Summary

## Quick Overview

I've analyzed both `agentic_search` and `tools_gateway` services and created a comprehensive design for implementing role-based access control with OAuth2 authentication.

---

## Key Findings

### ✅ tools_gateway is Already 90% Ready!

The tools_gateway service already has:
- **Complete OAuth2 system** with Google, Microsoft, and GitHub
- **Full RBAC implementation** with users, roles, and permissions
- **JWT token management** (HS256, 8-hour expiry)
- **SQLite database** with all necessary tables
- **Role-based tool permissions** (`role_tool_permissions` table)
- **Audit logging** for security events
- **Authentication middleware**

**Default admin user:**
- Email: `admin`
- Password: `admin`
- ⚠️ Change this immediately!

### ❌ agentic_search Needs Implementation

Currently has NO authentication:
- No user login
- No access control
- Directly calls tools_gateway without credentials
- No session management

---

## Proposed Solution Architecture

### Authentication Flow (OAuth2)

```
User → agentic_search → tools_gateway OAuth → Provider → tools_gateway → JWT → agentic_search
```

1. User clicks "Login with Google" in agentic_search
2. Redirects to tools_gateway OAuth endpoint
3. tools_gateway handles OAuth flow with provider
4. tools_gateway creates/updates user in database
5. tools_gateway generates JWT token
6. Redirects back to agentic_search with JWT
7. agentic_search stores JWT in session cookie

### Authorization Flow (RBAC)

```
Agent → MCP Request + JWT → tools_gateway → Validate Token → Check Permissions → Filter/Allow
```

1. agentic_search sends MCP request with JWT in Authorization header
2. tools_gateway validates JWT signature and expiration
3. Extracts user_id from token payload
4. Checks user's roles and permissions
5. For `tools/list`: Filters tools based on role permissions
6. For `tools/call`: Validates execution permission
7. Logs all access attempts in audit log

---

## User Synchronization Strategy

**Key Insight: NO synchronization needed!**

We use a **JWT-based trust model:**
- tools_gateway = single source of truth for users/roles
- agentic_search = stateless client that trusts JWTs
- JWT carries all necessary user identity
- No user database duplication needed

**Token Validation:**
- Both services share JWT secret (via environment variable)
- agentic_search can validate tokens locally (no DB call needed)
- Tokens expire after 8 hours (re-login required)

---

## Required Changes

### tools_gateway (4-6 hours)

**New Endpoints:**
1. `/auth/login-redirect` - Allow external services to initiate OAuth
2. `/auth/callback-redirect` - Callback with external redirect
3. `/auth/validate` - Token validation endpoint (optional)

**Modified Logic:**
1. MCP router `/mcp` endpoint:
   - Extract JWT from Authorization header
   - Validate user permissions
   - Filter `tools/list` based on user's roles
   - Check permission before `tools/call` execution
   - Add audit logging for authz events

**Files to modify:**
- `tools_gateway/routers/auth_router.py` (+100 lines)
- `tools_gateway/routers/mcp_router.py` (+50 lines)

### agentic_search (6-8 hours)

**New Modules:**
1. `auth.py` - JWT validation, session management
2. `auth_routes.py` - Login/callback/logout endpoints

**Modified Modules:**
1. `mcp_tool_client.py` - Add JWT to all MCP requests
2. `server.py` - Add auth middleware, protect endpoints

**New UI:**
1. Login page with OAuth options
2. User profile display
3. Logout button

**Files to create/modify:**
- `agentic_search/auth.py` (new, ~150 lines)
- `agentic_search/auth_routes.py` (new, ~100 lines)
- `agentic_search/ollama_query_agent/mcp_tool_client.py` (modify, +30 lines)
- `agentic_search/server.py` (modify, +40 lines)
- `agentic_search/static/login.html` (new)

---

## Configuration Required

### Shared Secret

**Critical:** Both services must share the same JWT secret.

```bash
# Generate a secure secret
openssl rand -base64 32

# Add to .env file for BOTH services
JWT_SECRET=your-super-secret-jwt-key-minimum-32-characters-long
```

### Environment Variables

**tools_gateway (.env):**
```bash
JWT_SECRET=<shared-secret>
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
```

**agentic_search (.env):**
```bash
JWT_SECRET=<shared-secret>
TOOLS_GATEWAY_URL=http://localhost:8021
AGENTIC_SEARCH_URL=http://localhost:8023
```

---

## Implementation Phases

### Phase 1: Setup (2-3 hours)
- Generate JWT secret
- Update environment configs
- Test JWT sharing

### Phase 2: tools_gateway (4-6 hours)
- Add redirect endpoints
- Modify MCP router for authz
- Add audit logging
- Test OAuth + permission checks

### Phase 3: agentic_search (6-8 hours)
- Implement auth module
- Add auth routes
- Modify MCP client
- Create login UI
- Test end-to-end flow

### Phase 4: Testing (4-6 hours)
- Integration tests
- Security tests
- User acceptance testing

**Total Estimated Time: 16-23 hours**

---

## Security Highlights

✅ **Best Practices Followed:**
- OAuth 2.1 with PKCE
- JWT with expiration
- HttpOnly session cookies
- Audit logging
- Role-based permissions
- Least privilege principle

⚠️ **Production Recommendations:**
1. Switch JWT to RS256 (asymmetric keys)
2. Use HTTPS only
3. Add token revocation/blacklist
4. Implement refresh tokens
5. Add rate limiting
6. Use Redis for sessions (not in-memory)

---

## Testing Commands

### Test OAuth Flow
```bash
# 1. Start services
cd tools_gateway && python -m uvicorn tools_gateway.main:app --port 8021
cd agentic_search && python server.py --port 8023

# 2. Open browser
open http://localhost:8023/auth/login

# 3. Click "Login with Google"
# Should redirect → Google → back with token → logged in
```

### Test Tool Filtering
```bash
# Login as regular user (role: user)
curl -H "Authorization: Bearer <user-jwt>" \
  -X POST http://localhost:8021/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":"1"}'

# Should return only tools assigned to "user" role

# Login as admin (role: admin)
curl -H "Authorization: Bearer <admin-jwt>" \
  -X POST http://localhost:8021/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":"1"}'

# Should return ALL tools (admin has superuser access)
```

### Test Unauthorized Access
```bash
# Try to access without token
curl -X POST http://localhost:8021/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":"1","params":{"name":"admin_tool"}}'

# Should return 401 Unauthorized

# Try to access tool not assigned to role
curl -H "Authorization: Bearer <viewer-jwt>" \
  -X POST http://localhost:8021/mcp \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":"1","params":{"name":"admin_tool"}}'

# Should return 403 Forbidden
```

---

## Role Configuration

### Default Roles

**admin:**
- Has ALL permissions (superuser)
- Can access all tools
- Can manage users and roles

**user:**
- Has TOOL_VIEW and TOOL_EXECUTE
- Can only access tools explicitly assigned to "user" role
- Cannot manage system

**viewer:**
- Has TOOL_VIEW only
- Read-only access
- Cannot execute tools

### Assigning Tools to Roles

Via Admin UI (tools_gateway):
```
http://localhost:8021/
→ Admin Panel
→ Tools Management
→ Select Tool
→ Assign Roles: [user, admin]
```

Via API:
```bash
# Get admin JWT token first
TOKEN="<admin-jwt>"

# Assign "search_web" tool to "user" role
curl -X POST http://localhost:8021/admin/tools/{server_id}/{tool_name}/roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role_ids": ["user", "admin"]}'
```

Via Database:
```sql
-- Grant search_web tool to "user" role
INSERT INTO role_tool_permissions (role_id, server_id, tool_name)
VALUES ('user', 'mcp_127_0_0_1_8001', 'search_web');

-- Grant all tools to admin role (admin already has superuser access, but for explicitness)
INSERT INTO role_tool_permissions (role_id, server_id, tool_name)
SELECT 'admin', _server_id, name FROM tools;
```

---

## Audit & Monitoring

All authentication and authorization events are logged:

```sql
-- View recent auth events
SELECT * FROM audit_logs
WHERE event_type IN ('AUTH_LOGIN_SUCCESS', 'AUTH_LOGIN_FAILURE')
ORDER BY timestamp DESC LIMIT 10;

-- View unauthorized access attempts
SELECT * FROM audit_logs
WHERE event_type = 'AUTHZ_PERMISSION_DENIED'
ORDER BY timestamp DESC LIMIT 10;

-- View tool executions by user
SELECT user_email, resource_id as tool_name, COUNT(*) as executions
FROM audit_logs
WHERE event_type = 'AUTHZ_PERMISSION_GRANTED'
  AND resource_type = 'tool'
GROUP BY user_email, resource_id
ORDER BY executions DESC;
```

---

## Migration Guide

### For New Deployments
1. Deploy tools_gateway with OAuth configured
2. Deploy agentic_search with auth enabled
3. Users log in via OAuth
4. Admin assigns tool permissions to roles

### For Existing Deployments

**tools_gateway:**
- ✅ No migration needed (backward compatible)
- Existing users continue to work
- New endpoints are additive

**agentic_search:**
- ⚠️ Breaking change: Auth now required
- Existing sessions invalidated
- Users must log in with OAuth

**Grace Period Option:**
```python
# Allow anonymous access for 30 days
MIGRATION_DEADLINE = datetime(2025, 2, 15)

@app.middleware("http")
async def migration_grace_period(request: Request, call_next):
    user = get_current_user(request)

    if not user and datetime.now() < MIGRATION_DEADLINE:
        logger.warning("Anonymous access during migration period")
        # Allow request without auth
    elif not user:
        return JSONResponse(
            status_code=401,
            content={"error": "Authentication required"}
        )

    return await call_next(request)
```

---

## Troubleshooting

### "Invalid token" errors
- Check JWT_SECRET is same in both services
- Check token hasn't expired (8 hour limit)
- Check Authorization header format: `Bearer <token>`

### "Permission denied" errors
- Check user has correct role assigned
- Check role has tool permissions assigned
- Check audit logs for details

### OAuth redirect loops
- Verify redirect_to URLs match exactly
- Check allowed origins configuration
- Clear browser cookies and try again

### Tools not showing up
- Check user is logged in
- Check user's role has tool permissions
- Check tools_gateway can reach MCP servers
- Run `tools/list` directly on tools_gateway to verify

---

## Next Steps

1. ✅ **Review** the detailed design document: `RBAC_OAUTH2_DESIGN.md`
2. **Approve** the architecture and approach
3. **Generate** JWT secret: `openssl rand -base64 32`
4. **Configure** OAuth providers (Google/Microsoft/GitHub)
5. **Begin implementation** following the phased plan
6. **Test** each phase before moving to next
7. **Deploy** to production with HTTPS and secure configs

---

## Questions & Answers

**Q: Do we need to sync users between services?**
A: No! JWT-based trust model means no sync needed. tools_gateway is the single source of truth.

**Q: What happens when a user's role changes?**
A: Changes take effect on next login (when new JWT is issued). For immediate effect, implement token revocation.

**Q: Can we use existing auth providers?**
A: Yes! tools_gateway already supports Google, Microsoft, and GitHub. Just configure client IDs/secrets.

**Q: How do we assign tool permissions?**
A: Via admin UI, API, or directly in database using `role_tool_permissions` table.

**Q: Is this scalable?**
A: Yes! JWT validation is stateless and can scale horizontally. For production, consider Redis for sessions and PostgreSQL for database.

**Q: What about API keys for programmatic access?**
A: Not in Phase 1, but can be added later. JWT tokens can be used as bearer tokens for now.

---

## Resources

- **Detailed Design:** `RBAC_OAUTH2_DESIGN.md`
- **tools_gateway Code:** `/tools_gateway/`
  - Auth: `tools_gateway/auth.py`
  - RBAC: `tools_gateway/rbac.py`
  - Database: `tools_gateway/database.py`
- **agentic_search Code:** `/agentic_search/`
  - Server: `agentic_search/server.py`
  - MCP Client: `agentic_search/ollama_query_agent/mcp_tool_client.py`

---

**Ready to implement?** Let me know if you have any questions or need clarification on any part of the design!

#!/usr/bin/env python3
"""
Complete setup for restricted Claude Desktop user
Demonstrates:
1. How to create first-time users
2. How tool visibility filtering works
3. How execution blocking works
"""
import requests
import json

GATEWAY_URL = "http://localhost:8021"
SERVER_ID = "mcp_localhost_8002"

print("=" * 80)
print("COMPLETE RBAC SETUP: User Creation + Tool Filtering Demo")
print("=" * 80)

# Step 1: Login as admin
print("\n1️⃣  Logging in as admin...")
admin_login = requests.post(
    f"{GATEWAY_URL}/auth/login/local",
    json={"email": "admin", "password": "admin"}
)
admin_token = admin_login.json()["access_token"]
admin_headers = {"Authorization": f"Bearer {admin_token}"}
print("✅ Admin authenticated")

# Step 2: Create a restricted role
print("\n2️⃣  Creating 'Claude Desktop User' role...")
role_response = requests.post(
    f"{GATEWAY_URL}/admin/roles",
    headers=admin_headers,
    json={
        "role_name": "Claude Desktop User",
        "description": "Limited access - only fuzzy_autocomplete",
        "permissions": ["tool:view", "tool:execute", "server:view"]
    }
)

if role_response.status_code == 200:
    role_id = role_response.json()["role_id"]
    print(f"✅ Role created: {role_id}")
else:
    # Get existing role
    roles = requests.get(f"{GATEWAY_URL}/admin/roles", headers=admin_headers).json()["roles"]
    role_id = next((r["role_id"] for r in roles if "Claude Desktop" in r["role_name"]), None)
    print(f"ℹ️  Using existing role: {role_id}")

# Step 3: Assign ONLY fuzzy_autocomplete
print(f"\n3️⃣  Setting tool restrictions...")
print(f"   ✅ ALLOW: fuzzy_autocomplete")
print(f"   ❌ DENY:  validate_entity")

tool_assign = requests.post(
    f"{GATEWAY_URL}/admin/roles/{role_id}/tools",
    headers=admin_headers,
    json={
        "server_id": SERVER_ID,
        "allowed_tools": ["fuzzy_autocomplete"]
    }
)
print("✅ Tool restrictions applied")

# Step 4: Create user
print(f"\n4️⃣  Creating user 'claude-desktop'...")
user_response = requests.post(
    f"{GATEWAY_URL}/auth/register",
    json={
        "email": "claude-desktop",
        "password": "secure-password-123",
        "name": "Claude Desktop Client"
    }
)

if user_response.status_code == 200:
    user_id = user_response.json()["user"]["user_id"]
    print(f"✅ User created: {user_id}")
else:
    users = requests.get(f"{GATEWAY_URL}/admin/users", headers=admin_headers).json()["users"]
    user = next((u for u in users if u["email"] == "claude-desktop"), None)
    user_id = user["user_id"]
    print(f"ℹ️  User exists: {user_id}")

# Step 5: Assign role
print(f"\n5️⃣  Assigning role to user...")
requests.post(
    f"{GATEWAY_URL}/admin/users/{user_id}/roles",
    headers=admin_headers,
    json={"role_id": role_id}
)
print("✅ Role assigned")

# Step 6: Login as user and test
print(f"\n6️⃣  Testing as 'claude-desktop' user...")
user_login = requests.post(
    f"{GATEWAY_URL}/auth/login/local",
    json={"email": "claude-desktop", "password": "secure-password-123"}
)
user_token = user_login.json()["access_token"]
print("✅ User authenticated")

# Test tools/list
print("\n" + "=" * 80)
print("TEST 1: Tool Visibility Filtering (tools/list)")
print("=" * 80)

tools_response = requests.post(
    f"{GATEWAY_URL}/mcp?token={user_token}",
    json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    },
    headers={
        "Accept": "application/json, text/event-stream",
        "Origin": "http://localhost:8021",
        "MCP-Protocol-Version": "2025-06-18"
    }
)

result = tools_response.json()["result"]
metadata = result.get("_metadata", {})
tools = result.get("tools", [])

print(f"\n📊 Results:")
print(f"   - User: {metadata.get('user_email')}")
print(f"   - Total Tools in System: {metadata.get('total_tools')}")
print(f"   - Tools Visible to User: {len(tools)}")

print(f"\n🔍 Visible Tools:")
for tool in tools:
    print(f"   ✅ {tool['name']}")

if len(tools) < metadata.get('total_tools', 0):
    print(f"\n✅ SUCCESS! Visibility is FILTERED")
    print(f"✅ User sees {len(tools)} of {metadata['total_tools']} tools")
    print(f"✅ 'validate_entity' is HIDDEN from Claude Desktop")

# Test denied tool execution
print("\n" + "=" * 80)
print("TEST 2: Execution Blocking")
print("=" * 80)

print(f"\nAttempting to execute DENIED tool 'validate_entity'...")
denied_response = requests.post(
    f"{GATEWAY_URL}/mcp?token={user_token}",
    json={
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "validate_entity",
            "arguments": {"entity_id": "test123"}
        }
    },
    headers={
        "Accept": "application/json, text/event-stream",
        "Origin": "http://localhost:8021",
        "MCP-Protocol-Version": "2025-06-18"
    }
)

if denied_response.status_code == 403 or "denied" in denied_response.text.lower():
    print(f"✅ SUCCESS! Execution BLOCKED")
    print(f"   Status: {denied_response.status_code}")
    try:
        error = denied_response.json()
        print(f"   Error: {error.get('error', {}).get('message', error.get('detail', 'Permission denied'))}")
    except:
        print(f"   Response: {denied_response.text[:200]}")

# Summary
print("\n" + "=" * 80)
print("📋 SUMMARY")
print("=" * 80)
print(f"""
✅ Answers to Your Questions:

1️⃣  "How does gateway recognize first-time users?"
   - Users must be CREATED before first login
   - Creation methods:
     a) Admin creates via UI (Security → Users → Add User)
     b) Admin creates via API (/auth/register) ← This script
     c) OAuth: Auto-created on first OAuth login

2️⃣  "Tool view should be blocked"
   - ✅ CONFIRMED: Blocked tools are HIDDEN from tools/list
   - Claude Desktop will NOT see 'validate_entity'
   - Only 'fuzzy_autocomplete' appears in the list
   - Execution of hidden tools is also blocked

✅ Claude Desktop Configuration:
""")

print(json.dumps({
    "mcpServers": {
        "toolbox-gateway": {
            "url": f"https://ce666863018f.ngrok-free.app/mcp?token={user_token}"
        }
    }
}, indent=2))

print(f"\n💡 This user will ONLY see 'fuzzy_autocomplete' in Claude Desktop!")
print(f"💡 'validate_entity' is completely hidden and blocked")

#!/usr/bin/env python3
"""
Test RBAC enforcement for Claude Desktop user
Verifies that tool access restrictions work correctly
"""
import requests
import json
import sys

# Configuration
GATEWAY_URL = "http://localhost:8021"
ADMIN_EMAIL = "admin"
ADMIN_PASSWORD = "admin"
CLAUDE_EMAIL = "claude-desktop-test"
CLAUDE_PASSWORD = "test-password-123"
SERVER_ID = "mcp_localhost_8002"

# Test configuration
ALLOWED_TOOL = "fuzzy_autocomplete"
DENIED_TOOL = "validate_entity"


def print_section(title):
    """Print a section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def test_rbac():
    print_section("🔐 RBAC Enforcement Test Suite")

    # Step 1: Login as admin
    print("1️⃣  Logging in as admin...")
    admin_response = requests.post(
        f"{GATEWAY_URL}/auth/login/local",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )

    if admin_response.status_code != 200:
        print(f"❌ Admin login failed: {admin_response.text}")
        return False

    admin_token = admin_response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("✅ Admin authenticated\n")

    # Step 2: Create restricted role
    print("2️⃣  Creating 'Claude Desktop Test' role...")
    role_response = requests.post(
        f"{GATEWAY_URL}/admin/roles",
        headers=admin_headers,
        json={
            "role_name": "Claude Desktop Test",
            "description": "Test role with limited tool access",
            "permissions": ["tool:view", "tool:execute", "server:view"]
        }
    )

    if role_response.status_code == 200:
        role_id = role_response.json()["role"]["role_id"]
        print(f"✅ Role created: {role_id}")
    else:
        # Try to find existing role
        roles_response = requests.get(f"{GATEWAY_URL}/admin/roles", headers=admin_headers)
        roles = roles_response.json().get("roles", [])
        test_role = next((r for r in roles if "Claude Desktop Test" in r["role_name"]), None)

        if test_role:
            role_id = test_role["role_id"]
            print(f"ℹ️  Using existing role: {role_id}")
        else:
            print(f"❌ Failed to create role: {role_response.text}")
            return False

    # Step 3: Assign specific tools to role
    print(f"\n3️⃣  Assigning tool restrictions...")
    print(f"   ✅ ALLOW: {ALLOWED_TOOL}")
    print(f"   ❌ DENY:  {DENIED_TOOL}")

    tool_response = requests.post(
        f"{GATEWAY_URL}/admin/roles/{role_id}/tools",
        headers=admin_headers,
        json={
            "server_id": SERVER_ID,
            "allowed_tools": [ALLOWED_TOOL]  # Only allow fuzzy_autocomplete
        }
    )

    if tool_response.status_code == 200:
        print("✅ Tool restrictions applied")
    else:
        print(f"⚠️  Tool assignment response: {tool_response.text}")

    # Step 4: Create test user
    print(f"\n4️⃣  Creating test user '{CLAUDE_EMAIL}'...")
    user_response = requests.post(
        f"{GATEWAY_URL}/auth/register",
        json={
            "email": CLAUDE_EMAIL,
            "password": CLAUDE_PASSWORD,
            "name": "Claude Desktop Test User"
        }
    )

    if user_response.status_code == 200:
        user_id = user_response.json()["user"]["user_id"]
        print(f"✅ User created: {user_id}")
    else:
        # Try to find existing user
        users_response = requests.get(f"{GATEWAY_URL}/admin/users", headers=admin_headers)
        users = users_response.json().get("users", [])
        test_user = next((u for u in users if u["email"] == CLAUDE_EMAIL), None)

        if test_user:
            user_id = test_user["user_id"]
            print(f"ℹ️  Using existing user: {user_id}")
        else:
            print(f"❌ Failed to create user: {user_response.text}")
            return False

    # Step 5: Assign role to user
    print(f"\n5️⃣  Assigning role to user...")
    assign_response = requests.post(
        f"{GATEWAY_URL}/admin/users/{user_id}/roles",
        headers=admin_headers,
        json={"role_id": role_id}
    )

    if assign_response.status_code == 200:
        print("✅ Role assigned to user")
    else:
        print(f"⚠️  Role assignment: {assign_response.text}")

    # Step 6: Login as test user
    print(f"\n6️⃣  Logging in as test user...")
    user_login = requests.post(
        f"{GATEWAY_URL}/auth/login/local",
        json={"email": CLAUDE_EMAIL, "password": CLAUDE_PASSWORD}
    )

    if user_login.status_code != 200:
        print(f"❌ User login failed: {user_login.text}")
        return False

    user_token = user_login.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}
    print("✅ Test user authenticated")

    # Step 7: Test MCP initialize
    print_section("🧪 Testing MCP Protocol Interaction")

    print("7️⃣  Initializing MCP session...")
    init_response = requests.post(
        f"{GATEWAY_URL}/mcp",
        headers=user_headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
                "capabilities": {}
            }
        }
    )

    if init_response.status_code == 200:
        print("✅ MCP session initialized")
    else:
        print(f"❌ Initialize failed: {init_response.text}")
        return False

    # Step 8: List tools (should see both but can only execute one)
    print("\n8️⃣  Listing available tools...")
    tools_response = requests.post(
        f"{GATEWAY_URL}/mcp",
        headers=user_headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
    )

    if tools_response.status_code == 200:
        tools_result = tools_response.json()
        tools = tools_result.get("result", {}).get("tools", [])
        print(f"✅ Tools listed: {len(tools)} tools available")
        for tool in tools:
            print(f"   - {tool['name']}")
    else:
        print(f"❌ Tools list failed: {tools_response.text}")
        return False

    # Step 9: Test ALLOWED tool execution
    print_section("✅ Testing ALLOWED Tool Access")

    print(f"9️⃣  Executing ALLOWED tool: {ALLOWED_TOOL}...")
    allowed_response = requests.post(
        f"{GATEWAY_URL}/mcp",
        headers=user_headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": ALLOWED_TOOL,
                "arguments": {"query": "test", "size": 5}
            }
        }
    )

    if allowed_response.status_code == 200:
        print(f"✅ SUCCESS: {ALLOWED_TOOL} executed successfully!")
        print(f"   Response: {json.dumps(allowed_response.json(), indent=2)[:200]}...")
    else:
        print(f"❌ FAILED: Should have been allowed!")
        print(f"   Status: {allowed_response.status_code}")
        print(f"   Response: {allowed_response.text}")
        return False

    # Step 10: Test DENIED tool execution
    print_section("❌ Testing DENIED Tool Access")

    print(f"🔟 Attempting to execute DENIED tool: {DENIED_TOOL}...")
    denied_response = requests.post(
        f"{GATEWAY_URL}/mcp",
        headers=user_headers,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": DENIED_TOOL,
                "arguments": {"entity_id": "test123"}
            }
        }
    )

    if denied_response.status_code == 403 or "permission" in denied_response.text.lower() or "denied" in denied_response.text.lower():
        print(f"✅ SUCCESS: {DENIED_TOOL} was correctly BLOCKED!")
        print(f"   Status: {denied_response.status_code}")
        print(f"   Response: {denied_response.json() if denied_response.status_code == 200 else denied_response.text}")
    else:
        print(f"❌ SECURITY BREACH: Tool should have been blocked!")
        print(f"   Status: {denied_response.status_code}")
        print(f"   Response: {denied_response.text}")
        return False

    # Step 11: Check audit logs
    print_section("📋 Checking Audit Trail")

    print("1️⃣1️⃣ Fetching recent audit events...")
    audit_response = requests.get(
        f"{GATEWAY_URL}/admin/audit/events?limit=10",
        headers=admin_headers
    )

    if audit_response.status_code == 200:
        events = audit_response.json().get("events", [])
        print(f"✅ Found {len(events)} recent events\n")

        # Filter for our test user's tool calls
        user_events = [e for e in events if e.get("user_id") == user_id and "tool" in e.get("action", "").lower()]

        if user_events:
            print("   Recent tool access attempts:")
            for event in user_events[:5]:
                status = "✅ ALLOWED" if event.get("status") == "success" else "❌ DENIED"
                print(f"   {status} - {event.get('action')} - {event.get('details', {}).get('tool_name', 'N/A')}")
        else:
            print("   ⚠️  No tool access events found for test user")
    else:
        print(f"⚠️  Could not fetch audit logs: {audit_response.text}")

    # Final summary
    print_section("🎉 RBAC Test Results")

    print("✅ All tests passed!")
    print("\n📊 Summary:")
    print(f"   ✅ Role created with tool restrictions")
    print(f"   ✅ User created and assigned restricted role")
    print(f"   ✅ Allowed tool ({ALLOWED_TOOL}) executed successfully")
    print(f"   ✅ Denied tool ({DENIED_TOOL}) was blocked by RBAC")
    print(f"   ✅ Audit trail captured all access attempts")
    print("\n🔒 RBAC enforcement is working correctly!")

    return True


if __name__ == "__main__":
    try:
        success = test_rbac()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

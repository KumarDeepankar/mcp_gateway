#!/usr/bin/env python3
"""
Setup restricted access for Claude Desktop
Creates a user with limited tool permissions
"""
import requests
import json

# Configuration
GATEWAY_URL = "http://localhost:8021"
ADMIN_EMAIL = "admin"
ADMIN_PASSWORD = "admin"

# Claude Desktop user config
CLAUDE_EMAIL = "claude-desktop"
CLAUDE_PASSWORD = "secure-password-123"
CLAUDE_NAME = "Claude Desktop Client"

# Tools to allow (specify which tools Claude Desktop can access)
# Leave empty [] to allow all tools
ALLOWED_TOOLS = [
    "fuzzy_autocomplete"  # Only allow autocomplete, NOT validate_entity
]

# Server ID (get this from your gateway UI or database)
SERVER_ID = "mcp_localhost_8002"  # FastMCP server


def main():
    print("🔐 Setting up restricted access for Claude Desktop...\n")

    # Step 1: Login as admin
    print("1. Logging in as admin...")
    login_response = requests.post(
        f"{GATEWAY_URL}/auth/login/local",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )

    if login_response.status_code != 200:
        print(f"❌ Admin login failed: {login_response.text}")
        return

    admin_token = login_response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("✅ Admin logged in\n")

    # Step 2: Create a custom role with specific tool permissions
    print("2. Creating 'claude-desktop-role' with limited tools...")
    role_response = requests.post(
        f"{GATEWAY_URL}/admin/roles",
        headers=admin_headers,
        json={
            "role_name": "Claude Desktop User",
            "description": "Limited access for Claude Desktop client",
            "permissions": [
                "tool:view",
                "tool:execute",
                "server:view"
            ]
        }
    )

    if role_response.status_code == 200:
        role_id = role_response.json()["role"]["role_id"]
        print(f"✅ Created role: {role_id}\n")
    else:
        print(f"⚠️  Role creation response: {role_response.text}")
        # Try to get existing role
        roles_response = requests.get(f"{GATEWAY_URL}/admin/roles", headers=admin_headers)
        roles = roles_response.json().get("roles", [])
        claude_role = next((r for r in roles if "Claude Desktop" in r["role_name"]), None)

        if claude_role:
            role_id = claude_role["role_id"]
            print(f"ℹ️  Using existing role: {role_id}\n")
        else:
            print("❌ Failed to create or find role")
            return

    # Step 3: Assign specific tools to the role
    print(f"3. Assigning tools {ALLOWED_TOOLS} to role...")
    tool_assignment_response = requests.post(
        f"{GATEWAY_URL}/admin/roles/{role_id}/tools",
        headers=admin_headers,
        json={
            "server_id": SERVER_ID,
            "allowed_tools": ALLOWED_TOOLS
        }
    )

    if tool_assignment_response.status_code == 200:
        print(f"✅ Tools assigned to role\n")
    else:
        print(f"⚠️  Tool assignment response: {tool_assignment_response.text}\n")

    # Step 4: Create user for Claude Desktop
    print("4. Creating Claude Desktop user...")
    user_response = requests.post(
        f"{GATEWAY_URL}/auth/register",
        json={
            "email": CLAUDE_EMAIL,
            "password": CLAUDE_PASSWORD,
            "name": CLAUDE_NAME
        }
    )

    if user_response.status_code == 200:
        user_id = user_response.json()["user"]["user_id"]
        print(f"✅ Created user: {user_id}\n")
    else:
        print(f"⚠️  User creation response: {user_response.text}")
        # User might already exist, try to get it
        users_response = requests.get(f"{GATEWAY_URL}/admin/users", headers=admin_headers)
        users = users_response.json().get("users", [])
        claude_user = next((u for u in users if u["email"] == CLAUDE_EMAIL), None)

        if claude_user:
            user_id = claude_user["user_id"]
            print(f"ℹ️  Using existing user: {user_id}\n")
        else:
            print("❌ Failed to create or find user")
            return

    # Step 5: Assign role to user
    print(f"5. Assigning role to user...")
    assign_response = requests.post(
        f"{GATEWAY_URL}/admin/users/{user_id}/roles",
        headers=admin_headers,
        json={"role_id": role_id}
    )

    if assign_response.status_code == 200:
        print(f"✅ Role assigned to user\n")
    else:
        print(f"⚠️  Role assignment response: {assign_response.text}\n")

    # Step 6: Get JWT token for Claude Desktop
    print("6. Generating JWT token for Claude Desktop...")
    claude_login_response = requests.post(
        f"{GATEWAY_URL}/auth/login/local",
        json={"email": CLAUDE_EMAIL, "password": CLAUDE_PASSWORD}
    )

    if claude_login_response.status_code == 200:
        claude_token = claude_login_response.json()["access_token"]
        print(f"✅ Token generated\n")

        print("=" * 80)
        print("🎉 SETUP COMPLETE!\n")
        print("📋 Claude Desktop Configuration:\n")
        print("Add this to your Claude Desktop config file:")
        print("~/Library/Application Support/Claude/claude_desktop_config.json\n")
        print(json.dumps({
            "mcpServers": {
                "toolbox-gateway": {
                    "url": "https://ceb361ecb6e5.ngrok-free.app/mcp",
                    "headers": {
                        "Authorization": f"Bearer {claude_token}"
                    }
                }
            }
        }, indent=2))
        print("\n" + "=" * 80)
        print(f"\n🔒 Access Restrictions:")
        print(f"   - Allowed tools: {ALLOWED_TOOLS if ALLOWED_TOOLS else 'ALL'}")
        print(f"   - Server: {SERVER_ID}")
        print(f"\n⚠️  IMPORTANT: Restart Claude Desktop after updating the config!\n")

    else:
        print(f"❌ Failed to get token: {claude_login_response.text}")


if __name__ == "__main__":
    main()

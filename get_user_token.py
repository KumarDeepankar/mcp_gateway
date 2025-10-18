#!/usr/bin/env python3
"""
Simple helper to get JWT token for any user
Usage: python get_user_token.py <email> <password>
"""
import requests
import sys
import json

GATEWAY_URL = "http://localhost:8021"

if len(sys.argv) != 3:
    print("Usage: python get_user_token.py <email> <password>")
    print("\nExample:")
    print("  python get_user_token.py claude-desktop secure-password-123")
    print("  python get_user_token.py admin admin")
    sys.exit(1)

email = sys.argv[1]
password = sys.argv[2]

print(f"Getting JWT token for user: {email}")
print("=" * 80)

response = requests.post(
    f"{GATEWAY_URL}/auth/login/local",
    json={"email": email, "password": password}
)

if response.status_code == 200:
    data = response.json()
    token = data["access_token"]
    user = data.get("user", {})

    print(f"✅ Login successful!")
    print(f"\nUser Details:")
    print(f"  Email: {user.get('email')}")
    print(f"  Name: {user.get('name')}")
    print(f"  Roles: {', '.join(user.get('roles', []))}")

    print(f"\n" + "=" * 80)
    print(f"JWT TOKEN:")
    print(f"=" * 80)
    print(token)

    print(f"\n" + "=" * 80)
    print(f"Claude Desktop Configuration:")
    print(f"=" * 80)
    config = {
        "mcpServers": {
            "toolbox-gateway": {
                "url": f"https://ce666863018f.ngrok-free.app/mcp?token={token}"
            }
        }
    }
    print(json.dumps(config, indent=2))

    print(f"\nFile location: ~/Library/Application Support/Claude/claude_desktop_config.json")

else:
    print(f"❌ Login failed!")
    print(f"Status: {response.status_code}")
    print(f"Error: {response.json().get('detail', 'Unknown error')}")
    sys.exit(1)

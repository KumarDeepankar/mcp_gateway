#!/usr/bin/env python3
"""
Test script to verify the tools_gateway is returning full tool definitions
"""
import requests
import json

def test_gateway_tools_list():
    """Test that the gateway returns full tool definitions"""

    # Gateway endpoint
    gateway_url = "http://localhost:8021/mcp"

    # MCP tools/list request
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": "test-tools-list"
    }

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-06-18",
        "Origin": "http://localhost:8021"  # Add origin header to pass validation
    }

    print("=" * 80)
    print("Testing tools_gateway tools/list endpoint")
    print("=" * 80)
    print(f"\nRequesting: {gateway_url}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")

    try:
        response = requests.post(gateway_url, json=payload, headers=headers, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}\n")

        if response.status_code == 200:
            data = response.json()

            if "result" in data and "tools" in data["result"]:
                tools = data["result"]["tools"]
                print(f"Total tools returned: {len(tools)}\n")

                # Find search_events_by_title
                search_by_title = next((t for t in tools if t.get("name") == "search_events_by_title"), None)

                if search_by_title:
                    print("=" * 80)
                    print("Tool: search_events_by_title")
                    print("=" * 80)
                    print("\nFull tool definition from gateway:\n")
                    print(json.dumps(search_by_title, indent=2))

                    # Check what we have
                    print("\n" + "=" * 80)
                    print("Analysis:")
                    print("=" * 80)
                    print(f"✓ Name: {search_by_title.get('name')}")
                    print(f"✓ Description length: {len(search_by_title.get('description', ''))} characters")
                    print(f"✓ Description: {search_by_title.get('description', 'N/A')[:150]}...")

                    if "inputSchema" in search_by_title:
                        schema = search_by_title["inputSchema"]
                        print(f"✓ inputSchema present: Yes")
                        print(f"  - Properties: {list(schema.get('properties', {}).keys())}")
                        print(f"  - Required: {schema.get('required', [])}")
                        print(f"  - Examples: {'Yes' if 'examples' in schema else 'No'}")

                        if "examples" in schema:
                            print(f"    Examples count: {len(schema['examples'])}")
                    else:
                        print(f"✗ inputSchema present: No")

                    # Check for metadata added by gateway
                    print(f"\nGateway metadata:")
                    print(f"  - _server_url: {search_by_title.get('_server_url', 'N/A')}")
                    print(f"  - _server_id: {search_by_title.get('_server_id', 'N/A')}")
                    print(f"  - _discovery_timestamp: {search_by_title.get('_discovery_timestamp', 'N/A')}")

                else:
                    print("✗ Tool 'search_events_by_title' not found in response")
                    print(f"\nAvailable tools: {[t.get('name') for t in tools]}")
            else:
                print("✗ No tools in response")
                print(f"Response: {json.dumps(data, indent=2)}")
        else:
            print(f"✗ Request failed: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_gateway_tools_list()

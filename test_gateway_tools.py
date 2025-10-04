#!/usr/bin/env python3
"""Test script to check gateway tool discovery"""
import asyncio
import httpx

async def test_gateway_tools():
    """Test gateway MCP tool discovery"""

    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Initialize session
        print("1. Initializing MCP session...")
        init_payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": "test-init",
            "params": {
                "protocolVersion": "2025-06-18",
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }

        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-06-18"
        }

        response = await client.post("http://localhost:8021/mcp", json=init_payload, headers=headers)
        print(f"   Status: {response.status_code}")
        init_result = response.json()
        print(f"   Result: {init_result}")

        session_id = response.headers.get("Mcp-Session-Id")
        print(f"   Session ID: {session_id}")

        # Step 2: Send initialized notification
        print("\n2. Sending initialized notification...")
        headers["Mcp-Session-Id"] = session_id

        init_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }

        response = await client.post("http://localhost:8021/mcp", json=init_notification, headers=headers)
        print(f"   Status: {response.status_code}")

        # Step 3: Request tools list
        print("\n3. Requesting tools list...")
        tools_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "test-tools"
        }

        response = await client.post("http://localhost:8021/mcp", json=tools_payload, headers=headers)
        print(f"   Status: {response.status_code}")
        tools_result = response.json()
        print(f"   Result: {tools_result}")

        tools = tools_result.get("result", {}).get("tools", [])
        print(f"\n✓ Found {len(tools)} tools")

        if tools:
            for tool in tools:
                print(f"   - {tool.get('name')}: {tool.get('description', 'No description')[:50]}")
        else:
            print("   ⚠ No tools found!")
            print("\n4. Checking registered servers...")

            # Check management API
            server_list_payload = {
                "jsonrpc": "2.0",
                "method": "server.list",
                "id": "test-servers"
            }

            response = await client.post("http://localhost:8021/manage", json=server_list_payload)
            servers_result = response.json()
            servers = servers_result.get("result", {}).get("server_cards", {})

            print(f"   Registered servers: {len(servers)}")
            for server_id, server_info in servers.items():
                print(f"   - {server_id}: {server_info.get('url')}")

if __name__ == "__main__":
    asyncio.run(test_gateway_tools())

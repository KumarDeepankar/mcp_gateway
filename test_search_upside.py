#!/usr/bin/env python3
"""Test script to test search_stories with 'upside' keyword"""
import asyncio
import httpx

async def test_search_upside():
    """Test search_stories tool with 'upside' keyword through gateway"""

    async with httpx.AsyncClient(timeout=60) as client:
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

        # Step 3: Call search_stories tool with 'upside'
        print("\n3. Calling search_stories tool with query='upside'...")
        tool_call_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": "test-search-upside",
            "params": {
                "name": "search_stories",
                "arguments": {
                    "query": "upside",
                    "size": 10
                }
            }
        }

        print("   Sending request...")
        print(f"   Payload: {tool_call_payload}")

        # Stream the response
        print("\n   Streaming response...")
        async with client.stream("POST", "http://localhost:8021/mcp", json=tool_call_payload, headers=headers) as response:
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('content-type')}")

            event_buffer = ""
            result_found = False
            error_found = False

            async for chunk in response.aiter_text():
                print("   ---")
                print(chunk)
                event_buffer += chunk

                # Check for errors
                if '"error"' in chunk:
                    error_found = True
                    print("\n   ⚠ ERROR DETECTED in response")

                # Check for successful result
                if '"result"' in chunk and '"content"' in chunk:
                    result_found = True

            print("\n" + "="*80)
            if error_found:
                print("❌ Test FAILED - Error occurred during search")
            elif result_found:
                print("✅ Test PASSED - Search completed successfully!")
            else:
                print("⚠ Test INCOMPLETE - No clear result or error")
            print("="*80)

if __name__ == "__main__":
    asyncio.run(test_search_upside())

#!/usr/bin/env python3
"""
Test script for MCP OpenSearch service
Tests the OpenSearch MCP tools functionality
"""
import requests
import json
import time
import sys


def test_mcp_opensearch_server():
    """Test the MCP OpenSearch server endpoints and tools."""
    base_url = "http://localhost:8002"

    print("🔍 Testing MCP OpenSearch Server")
    print("=" * 40)

    # Test 1: Check server is running
    print("1. Testing server availability...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            server_info = response.json()
            print(f"   ✅ Server is running: {server_info.get('name', 'Unknown')}")
            print(f"   📋 Version: {server_info.get('version', 'Unknown')}")
        else:
            print(f"   ❌ Server responded with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Server not reachable: {e}")
        return False

    # Test 2: Initialize MCP session
    print("\n2. Testing MCP initialization...")
    try:
        init_request = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        response = requests.post(f"{base_url}/mcp", json=init_request, headers=headers, timeout=10)

        if response.status_code == 200:
            init_result = response.json()
            session_id = response.headers.get("Mcp-Session-Id")
            print(f"   ✅ MCP initialized successfully")
            print(f"   🔑 Session ID: {session_id}")
            print(f"   📋 Protocol: {init_result.get('result', {}).get('protocolVersion', 'Unknown')}")
        else:
            print(f"   ❌ Initialization failed with status {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Initialization request failed: {e}")
        return False

    # Test 3: Send initialized notification
    print("\n3. Sending initialized notification...")
    try:
        initialized_request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id
        }

        response = requests.post(f"{base_url}/mcp", json=initialized_request, headers=headers, timeout=10)

        if response.status_code == 202:
            print("   ✅ Initialized notification sent successfully")
        else:
            print(f"   ⚠️  Notification response status: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Initialized notification failed: {e}")

    # Test 4: List available tools
    print("\n4. Testing tools/list...")
    try:
        tools_request = {
            "jsonrpc": "2.0",
            "id": "tools-1",
            "method": "tools/list"
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id
        }

        response = requests.post(f"{base_url}/mcp", json=tools_request, headers=headers, timeout=10)

        if response.status_code == 200:
            tools_result = response.json()
            tools = tools_result.get('result', {}).get('tools', [])
            print(f"   ✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"      - {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
        else:
            print(f"   ❌ Tools list failed with status {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Tools list request failed: {e}")
        return False

    # Test 5: Test OpenSearch status tool
    print("\n5. Testing opensearch_status tool...")
    try:
        status_request = {
            "jsonrpc": "2.0",
            "id": "status-1",
            "method": "tools/call",
            "params": {
                "name": "opensearch_status",
                "arguments": {}
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id
        }

        response = requests.post(f"{base_url}/mcp", json=status_request, headers=headers, timeout=15)

        if response.status_code == 200:
            # Handle streaming response
            if "text/event-stream" in response.headers.get("content-type", ""):
                print("   📡 Streaming response received")
                lines = response.text.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])  # Remove 'data: ' prefix
                            if 'result' in data:
                                content = data['result'].get('content', [])
                                if content:
                                    status_text = content[0].get('text', 'No content')
                                    print(f"   📊 OpenSearch Status: {status_text}")
                        except json.JSONDecodeError:
                            continue
            else:
                result = response.json()
                print(f"   📊 Status result: {result}")
        else:
            print(f"   ❌ Status check failed with status {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Status check request failed: {e}")

    # Test 6: Test OpenSearch info tool
    print("\n6. Testing opensearch_info tool...")
    try:
        info_request = {
            "jsonrpc": "2.0",
            "id": "info-1",
            "method": "tools/call",
            "params": {
                "name": "opensearch_info",
                "arguments": {}
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id
        }

        response = requests.post(f"{base_url}/mcp", json=info_request, headers=headers, timeout=15)

        if response.status_code == 200:
            # Handle streaming response
            if "text/event-stream" in response.headers.get("content-type", ""):
                print("   📡 Streaming response received")
                lines = response.text.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])  # Remove 'data: ' prefix
                            if 'result' in data:
                                content = data['result'].get('content', [])
                                if content:
                                    info_text = content[0].get('text', 'No content')
                                    print(f"   📊 OpenSearch Info:")
                                    print(f"      {info_text[:200]}..." if len(info_text) > 200 else f"      {info_text}")
                        except json.JSONDecodeError:
                            continue
        else:
            print(f"   ❌ Info request failed with status {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Info request failed: {e}")

    # Test 7: Test OpenSearch search tool
    print("\n7. Testing opensearch_search tool...")
    try:
        search_request = {
            "jsonrpc": "2.0",
            "id": "search-1",
            "method": "tools/call",
            "params": {
                "name": "opensearch_search",
                "arguments": {
                    "query": "test",
                    "size": 5
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id
        }

        response = requests.post(f"{base_url}/mcp", json=search_request, headers=headers, timeout=15)

        if response.status_code == 200:
            # Handle streaming response
            if "text/event-stream" in response.headers.get("content-type", ""):
                print("   📡 Streaming response received")
                lines = response.text.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])  # Remove 'data: ' prefix
                            if 'result' in data:
                                content = data['result'].get('content', [])
                                if content:
                                    search_text = content[0].get('text', 'No content')
                                    print(f"   🔍 Search Results:")
                                    print(f"      {search_text[:300]}..." if len(search_text) > 300 else f"      {search_text}")
                        except json.JSONDecodeError:
                            continue
        else:
            print(f"   ❌ Search request failed with status {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Search request failed: {e}")

    print("\n✅ MCP OpenSearch Server test completed!")
    return True


if __name__ == "__main__":
    print("🚀 Starting MCP OpenSearch Server Tests")
    print("Make sure the server is running on localhost:8002")
    print("You can start it with: PORT=8002 python mcp_opensearch/mcp_server.py")
    print()

    # Wait a moment for any startup
    time.sleep(1)

    success = test_mcp_opensearch_server()

    if success:
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
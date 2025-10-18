#!/usr/bin/env python3
"""
Test if the gateway successfully connects to FastMCP and lists tools
"""
import requests
import json

BASE_URL = "http://localhost:8021"

print("Testing Gateway with FastMCP...")
print("=" * 60)

# Step 1: Initialize
print("\n1. Initializing MCP session...")
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
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Origin": "http://localhost:8021"
}

try:
    response = requests.post(f"{BASE_URL}/mcp", json=init_payload, headers=headers, timeout=10)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Initialized: {data.get('result', {}).get('serverInfo', {}).get('name')}")
    else:
        print(f"   ✗ Failed: {response.text}")
        exit(1)
except Exception as e:
    print(f"   ✗ Error: {e}")
    exit(1)

# Step 2: List tools
print("\n2. Listing tools...")
tools_payload = {
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": "test-tools",
    "params": {}
}

try:
    response = requests.post(f"{BASE_URL}/mcp", json=tools_payload, headers=headers, timeout=10)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        tools = data.get('result', {}).get('tools', [])
        print(f"   ✓ Found {len(tools)} tools from FastMCP:")
        for tool in tools:
            print(f"      - {tool.get('name')}: {tool.get('description', 'No description')}")
    else:
        print(f"   ✗ Failed: {response.text}")
        exit(1)
except Exception as e:
    print(f"   ✗ Error: {e}")
    exit(1)

print("\n" + "=" * 60)
print("SUCCESS: Gateway successfully connected to FastMCP!")
print("=" * 60)

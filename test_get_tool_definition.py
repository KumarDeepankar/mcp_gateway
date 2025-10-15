#!/usr/bin/env python3
"""
Test script to show the exact tool definition that clients will receive
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_opensearch.tools import MCPTools


def main():
    # Initialize MCPTools
    tools = MCPTools(opensearch_url="http://localhost:9200")

    # Get all tool definitions (what clients get from tools/list)
    tool_definitions = tools.get_tool_definitions()

    # Find search_events_by_title
    search_by_title = next((t for t in tool_definitions if t["name"] == "search_events_by_title"), None)

    if search_by_title:
        print("=" * 80)
        print("Tool Definition for: search_events_by_title")
        print("=" * 80)
        print("\nThis is what the client receives from the tools/list endpoint:\n")
        print(json.dumps(search_by_title, indent=2))
    else:
        print("Tool not found!")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

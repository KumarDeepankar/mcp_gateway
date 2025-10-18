#!/usr/bin/env python3
"""Simple test for FastMCP autocomplete server"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_autocomplete():
    """Test the fuzzy_autocomplete tool"""
    server_params = StdioServerParameters(
        command="python",
        args=["server.py", "stdio"],
        env=None
    )

    print("=" * 60)
    print("Testing FastMCP Autocomplete Server")
    print("=" * 60)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            print("\n✓ Initializing session...")
            await session.initialize()

            # List tools
            print("✓ Listing tools...")
            tools_result = await session.list_tools()
            print(f"  Found {len(tools_result.tools)} tools:")
            for tool in tools_result.tools:
                print(f"    - {tool.name}: {tool.description[:60]}...")

            # Test fuzzy_autocomplete
            print("\n✓ Testing fuzzy_autocomplete with query='climate'...")
            result = await session.call_tool(
                "fuzzy_autocomplete",
                arguments={"query": "climate", "size": 5}
            )

            print("\nResults:")
            for content in result.content:
                if hasattr(content, 'text'):
                    import json
                    data = json.loads(content.text)
                    print(f"  Query: {data.get('query')}")
                    print(f"  Type: {data.get('query_type')}")
                    print(f"  Total Matches: {data.get('total_matches')}")
                    print(f"  Suggestions: {data.get('count')}\n")

                    for sug in data.get('suggestions', [])[:3]:
                        print(f"    {sug['rank']}. {sug['title']}")
                        if sug.get('subtitle'):
                            print(f"       {sug['subtitle']}")
                        if sug.get('highlight'):
                            print(f"       Highlight: {sug['highlight']}")
                        print()

            # Test validate_entity
            print("✓ Testing validate_entity...")
            if data.get('suggestions'):
                entity_id = data['suggestions'][0]['id']
                result = await session.call_tool(
                    "validate_entity",
                    arguments={"entity_id": entity_id}
                )

                for content in result.content:
                    if hasattr(content, 'text'):
                        validation = json.loads(content.text)
                        if validation.get('exists'):
                            print(f"  ✓ Entity exists: {validation['entity']['title']}")
                        else:
                            print(f"  ✗ Entity not found")

            print("\n" + "=" * 60)
            print("Test Complete!")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_autocomplete())

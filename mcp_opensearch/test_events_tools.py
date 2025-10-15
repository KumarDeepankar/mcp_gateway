#!/usr/bin/env python3
"""
Test script for Events MCP Tools
Tests all 17 granular tools created for the events index
"""
import asyncio
import json
from tools import MCPTools


async def test_all_tools():
    """Test all events tools."""
    print("=" * 80)
    print("Testing Events MCP Tools")
    print("=" * 80)
    print()

    # Initialize tools
    tools = MCPTools(opensearch_url="http://localhost:9200")

    # Get all tool definitions
    tool_defs = tools.get_tool_definitions()
    print(f"✅ Initialized {len(tool_defs)} tools")
    print()

    # List all available tools
    print("Available Tools:")
    print("-" * 80)
    for i, tool_def in enumerate(tool_defs, 1):
        print(f"{i:2d}. {tool_def['name']}")
        print(f"    {tool_def['description']}")
    print()
    print("=" * 80)
    print()

    # ========================================================================
    # Test Search Tools
    # ========================================================================

    print("1. TESTING SEARCH TOOLS")
    print("-" * 80)

    # Test 1: Basic search
    print("\n1.1 Testing search_events (basic fuzzy search)")
    try:
        result = await tools.execute_tool("search_events", {
            "query": "renewable energy",
            "size": 3
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 2: Search by title
    print("\n1.2 Testing search_events_by_title")
    try:
        result = await tools.execute_tool("search_events_by_title", {
            "query": "summit",
            "size": 3
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 3: Search by theme
    print("\n1.3 Testing search_events_by_theme")
    try:
        result = await tools.execute_tool("search_events_by_theme", {
            "theme": "technology",
            "size": 3
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 4: Hybrid search
    print("\n1.4 Testing search_events_hybrid")
    try:
        result = await tools.execute_tool("search_events_hybrid", {
            "query": "climat chang",  # Misspelled intentionally
            "size": 3
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 5: Autocomplete
    print("\n1.5 Testing search_events_autocomplete")
    try:
        result = await tools.execute_tool("search_events_autocomplete", {
            "prefix": "tech",
            "size": 3
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    print()
    print("=" * 80)
    print()

    # ========================================================================
    # Test Filter Tools
    # ========================================================================

    print("2. TESTING FILTER TOOLS")
    print("-" * 80)

    # Test 6: Filter by country
    print("\n2.1 Testing filter_events_by_country")
    try:
        result = await tools.execute_tool("filter_events_by_country", {
            "country": "Denmark",
            "size": 3
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 7: Filter by year
    print("\n2.2 Testing filter_events_by_year")
    try:
        result = await tools.execute_tool("filter_events_by_year", {
            "year": 2023,
            "size": 3
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 8: Filter by year range
    print("\n2.3 Testing filter_events_by_year_range")
    try:
        result = await tools.execute_tool("filter_events_by_year_range", {
            "start_year": 2021,
            "end_year": 2022,
            "size": 3
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 9: Filter by attendance
    print("\n2.4 Testing filter_events_by_attendance")
    try:
        result = await tools.execute_tool("filter_events_by_attendance", {
            "min_attendance": 10000,
            "size": 3
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 10: Combined search and filter
    print("\n2.5 Testing search_and_filter_events (complex query)")
    try:
        result = await tools.execute_tool("search_and_filter_events", {
            "query": "energy",
            "country": "Denmark",
            "start_year": 2022,
            "end_year": 2023,
            "size": 3,
            "sort_by": "year",
            "sort_order": "desc"
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    print()
    print("=" * 80)
    print()

    # ========================================================================
    # Test Aggregation Tools
    # ========================================================================

    print("3. TESTING AGGREGATION/ANALYTICS TOOLS")
    print("-" * 80)

    # Test 11: Year-wise statistics
    print("\n3.1 Testing get_events_stats_by_year")
    try:
        result = await tools.execute_tool("get_events_stats_by_year", {})
        print(f"✅ Result:\n{str(result[0]['text'])}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 12: Country-wise statistics
    print("\n3.2 Testing get_events_stats_by_country")
    try:
        result = await tools.execute_tool("get_events_stats_by_country", {})
        print(f"✅ Result:\n{str(result[0]['text'])}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 13: Theme aggregation
    print("\n3.3 Testing get_events_by_theme_aggregation")
    try:
        result = await tools.execute_tool("get_events_by_theme_aggregation", {
            "top_n": 5
        })
        print(f"✅ Result:\n{str(result[0]['text'])[:1000]}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 14: Attendance statistics
    print("\n3.4 Testing get_event_attendance_stats")
    try:
        result = await tools.execute_tool("get_event_attendance_stats", {
            "country": "Denmark"
        })
        print(f"✅ Result:\n{str(result[0]['text'])}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print()
    print("=" * 80)
    print()

    # ========================================================================
    # Test Retrieval Tools
    # ========================================================================

    print("4. TESTING RETRIEVAL TOOLS")
    print("-" * 80)

    # Test 15: Get event by ID (we'll use the first event from list)
    print("\n4.1 Testing list_all_events first to get an ID")
    try:
        result = await tools.execute_tool("list_all_events", {
            "size": 1
        })
        result_text = result[0]['text']
        print(f"✅ Result (first 300 chars): {result_text[:300]}...")

        # Try to extract an ID from the result
        if '"id":' in result_text:
            import re
            id_match = re.search(r'"id":\s*"([^"]+)"', result_text)
            if id_match:
                event_id = id_match.group(1)

                print(f"\n4.2 Testing get_event_by_id with ID: {event_id}")
                result = await tools.execute_tool("get_event_by_id", {
                    "event_id": event_id
                })
                print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 16: List all events with sorting
    print("\n4.3 Testing list_all_events with sorting")
    try:
        result = await tools.execute_tool("list_all_events", {
            "size": 5,
            "sort_by": "event_count",
            "sort_order": "desc"
        })
        print(f"✅ Result (first 500 chars): {str(result)[:500]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 17: Count events
    print("\n4.4 Testing count_events (total)")
    try:
        result = await tools.execute_tool("count_events", {})
        print(f"✅ Result: {str(result[0]['text'])}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n4.5 Testing count_events (with filter)")
    try:
        result = await tools.execute_tool("count_events", {
            "country": "Denmark",
            "year": 2023
        })
        print(f"✅ Result: {str(result[0]['text'])}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print()
    print("=" * 80)
    print()
    print("🎉 All tests completed!")
    print("=" * 80)


# ========================================================================
# Demonstrate Agent Use Cases
# ========================================================================

async def demonstrate_agent_use_cases():
    """Demonstrate how an agentic assistant would use these tools."""
    print()
    print("=" * 80)
    print("DEMONSTRATING AGENTIC ASSISTANT USE CASES")
    print("=" * 80)
    print()

    tools = MCPTools(opensearch_url="http://localhost:9200")

    # Use Case 1: User asks about technology events in Denmark
    print("Use Case 1: 'Find technology-related events in Denmark from 2022-2023'")
    print("-" * 80)
    print("Agent Plan:")
    print("  Step 1: Use search_and_filter_events with query='technology', country='Denmark', year_range=[2022-2023]")
    print()
    try:
        result = await tools.execute_tool("search_and_filter_events", {
            "query": "technology",
            "country": "Denmark",
            "start_year": 2022,
            "end_year": 2023,
            "size": 5
        })
        print("Agent Response:")
        print(str(result[0]['text'])[:800] + "...")
    except Exception as e:
        print(f"❌ Error: {e}")

    print()
    print("=" * 80)
    print()

    # Use Case 2: User asks for year-wise analysis
    print("Use Case 2: 'Show me year-wise event statistics for Denmark'")
    print("-" * 80)
    print("Agent Plan:")
    print("  Step 1: Use get_events_stats_by_year with country='Denmark'")
    print()
    try:
        result = await tools.execute_tool("get_events_stats_by_year", {
            "country": "Denmark"
        })
        print("Agent Response:")
        print(str(result[0]['text']))
    except Exception as e:
        print(f"❌ Error: {e}")

    print()
    print("=" * 80)
    print()

    # Use Case 3: User asks about popular themes
    print("Use Case 3: 'What are the most popular event themes in 2023?'")
    print("-" * 80)
    print("Agent Plan:")
    print("  Step 1: Use get_events_by_theme_aggregation with year=2023")
    print()
    try:
        result = await tools.execute_tool("get_events_by_theme_aggregation", {
            "year": 2023,
            "top_n": 10
        })
        print("Agent Response:")
        print(str(result[0]['text']))
    except Exception as e:
        print(f"❌ Error: {e}")

    print()
    print("=" * 80)
    print()

    # Use Case 4: Complex multi-step query
    print("Use Case 4: 'Find large renewable energy events and show me the average attendance'")
    print("-" * 80)
    print("Agent Plan:")
    print("  Step 1: Use filter_events_by_attendance with min_attendance=5000 and query='renewable energy'")
    print("  Step 2: Use get_event_attendance_stats to show statistics")
    print()
    try:
        # Step 1
        result1 = await tools.execute_tool("filter_events_by_attendance", {
            "query": "renewable energy",
            "min_attendance": 5000,
            "size": 5
        })
        print("Step 1 - Found events:")
        print(str(result1[0]['text'])[:600] + "...")
        print()

        # Step 2
        result2 = await tools.execute_tool("get_event_attendance_stats", {})
        print("Step 2 - Overall attendance statistics:")
        print(str(result2[0]['text']))
    except Exception as e:
        print(f"❌ Error: {e}")

    print()
    print("=" * 80)
    print()


async def main():
    """Run all tests."""
    # Test all tools
    await test_all_tools()

    # Demonstrate agent use cases
    await demonstrate_agent_use_cases()

    print()
    print("🎯 Summary:")
    print("=" * 80)
    print("✅ Created 17 granular MCP tools for events index")
    print("✅ Tools organized into 4 categories:")
    print("   1. Search Tools (5): Basic, by field, hybrid, autocomplete")
    print("   2. Filter Tools (5): Country, year, year range, attendance, combined")
    print("   3. Aggregation Tools (4): Year stats, country stats, theme, attendance")
    print("   4. Retrieval Tools (3): Get by ID, list all, count")
    print()
    print("🤖 These tools enable agentic assistants to:")
    print("   - Break down complex queries into atomic operations")
    print("   - Perform multi-step analysis workflows")
    print("   - Filter and search with various combinations")
    print("   - Generate statistical insights and aggregations")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

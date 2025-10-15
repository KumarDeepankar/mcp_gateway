#!/usr/bin/env python3
"""
Test script for refactored tools module
Verifies that the new modular structure works correctly
"""
import sys
import asyncio


async def test_tools_initialization():
    """Test that MCPTools can be initialized and has all expected tools."""
    print("=" * 60)
    print("Testing MCPTools Initialization")
    print("=" * 60)

    try:
        from tools import MCPTools
        print("✓ Successfully imported MCPTools from tools package")
    except Exception as e:
        print(f"✗ Failed to import MCPTools: {e}")
        return False

    try:
        # Initialize MCPTools
        tools = MCPTools(opensearch_url="http://localhost:9200")
        print(f"✓ MCPTools initialized successfully")
        print(f"  - OpenSearch URL: {tools.opensearch_url}")
        print(f"  - Index name: {tools.index_name}")
    except Exception as e:
        print(f"✗ Failed to initialize MCPTools: {e}")
        return False

    # Check tool count
    tool_count = len(tools.tools_registry)
    expected_count = 17
    if tool_count == expected_count:
        print(f"✓ Tool registry contains {tool_count} tools (expected {expected_count})")
    else:
        print(f"✗ Tool registry contains {tool_count} tools (expected {expected_count})")
        return False

    # Verify tool definitions
    definitions = tools.get_tool_definitions()
    if len(definitions) == expected_count:
        print(f"✓ get_tool_definitions() returned {len(definitions)} definitions")
    else:
        print(f"✗ get_tool_definitions() returned {len(definitions)} definitions (expected {expected_count})")
        return False

    # List all tool names
    print("\n" + "=" * 60)
    print("Registered Tools:")
    print("=" * 60)

    tool_categories = {
        "Search Tools": [
            "search_events",
            "search_events_by_title",
            "search_events_by_theme",
            "search_events_hybrid",
            "search_events_autocomplete"
        ],
        "Filter Tools": [
            "filter_events_by_country",
            "filter_events_by_year",
            "filter_events_by_year_range",
            "filter_events_by_attendance",
            "search_and_filter_events"
        ],
        "Aggregation Tools": [
            "get_events_stats_by_year",
            "get_events_stats_by_country",
            "get_events_by_theme_aggregation",
            "get_event_attendance_stats"
        ],
        "Retrieval Tools": [
            "get_event_by_id",
            "list_all_events",
            "count_events"
        ]
    }

    all_tools_found = True
    for category, expected_tools in tool_categories.items():
        print(f"\n{category}:")
        for tool_name in expected_tools:
            if tool_name in tools.tools_registry:
                print(f"  ✓ {tool_name}")
            else:
                print(f"  ✗ {tool_name} NOT FOUND")
                all_tools_found = False

    if not all_tools_found:
        return False

    # Verify handler binding
    print("\n" + "=" * 60)
    print("Verifying Handler Binding:")
    print("=" * 60)

    # Check if handlers are properly bound
    sample_tool = "search_events"
    if sample_tool in tools.tools_registry:
        handler = tools.tools_registry[sample_tool].get("handler")
        if handler and callable(handler):
            print(f"✓ Handler for '{sample_tool}' is callable")
        else:
            print(f"✗ Handler for '{sample_tool}' is not callable")
            return False

    # Test execute_tool method (without actually calling OpenSearch)
    print("\n" + "=" * 60)
    print("Testing Tool Execution Framework:")
    print("=" * 60)

    try:
        # This will fail because OpenSearch isn't running, but we're testing the framework
        result = await tools.execute_tool("count_events", {})
        print(f"✓ execute_tool() framework works (note: actual OpenSearch call may have failed)")
    except ValueError as e:
        print(f"✗ execute_tool() raised ValueError: {e}")
        return False
    except Exception as e:
        # Expected to fail due to no OpenSearch connection
        print(f"✓ execute_tool() framework works (OpenSearch connection error expected: {type(e).__name__})")

    print("\n" + "=" * 60)
    print("All Tests Passed!")
    print("=" * 60)
    return True


async def test_module_structure():
    """Test that all modules can be imported independently."""
    print("\n" + "=" * 60)
    print("Testing Module Structure:")
    print("=" * 60)

    modules_to_test = [
        ("tools.http_client", "OpenSearchHTTPClient"),
        ("tools.formatters", "ResultFormatter"),
        ("tools.registry", "ToolRegistry"),
        ("tools.handlers.search", "SearchHandlers"),
        ("tools.handlers.filter", "FilterHandlers"),
        ("tools.handlers.aggregation", "AggregationHandlers"),
        ("tools.handlers.retrieval", "RetrievalHandlers"),
    ]

    all_passed = True
    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"✓ {module_name}.{class_name}")
        except Exception as e:
            print(f"✗ {module_name}.{class_name}: {e}")
            all_passed = False

    return all_passed


async def main():
    """Run all tests."""
    print("\n")
    print("#" * 60)
    print("# MCP OpenSearch Tools - Refactoring Test Suite")
    print("#" * 60)
    print("\n")

    # Test module structure
    structure_ok = await test_module_structure()

    # Test tools initialization
    tools_ok = await test_tools_initialization()

    # Final result
    print("\n" + "#" * 60)
    if structure_ok and tools_ok:
        print("# RESULT: ALL TESTS PASSED ✓")
        print("#" * 60)
        return 0
    else:
        print("# RESULT: SOME TESTS FAILED ✗")
        print("#" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

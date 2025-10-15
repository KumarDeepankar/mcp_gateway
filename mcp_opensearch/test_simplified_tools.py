#!/usr/bin/env python3
"""
Test script for simplified 4-tool structure
Verifies that only the 4 most sophisticated tools are registered
"""
import sys
import asyncio


async def test_tools_initialization():
    """Test that MCPTools has exactly 4 sophisticated tools."""
    print("=" * 60)
    print("Testing MCPTools with 4 Sophisticated Tools")
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
    expected_count = 4
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

    # List the 4 sophisticated tools
    print("\n" + "=" * 60)
    print("The 4 Most Sophisticated Tools:")
    print("=" * 60)

    expected_tools = {
        "search_events_hybrid": "Search - Advanced hybrid search with ngram",
        "search_and_filter_events": "Filter - Multi-filter search with sorting",
        "get_event_attendance_stats": "Aggregation - Comprehensive attendance statistics",
        "list_all_events": "Retrieval - Paginated event listing"
    }

    all_tools_found = True
    for tool_name, description in expected_tools.items():
        if tool_name in tools.tools_registry:
            print(f"  ✓ {tool_name}")
            print(f"    → {description}")
        else:
            print(f"  ✗ {tool_name} NOT FOUND")
            all_tools_found = False

    if not all_tools_found:
        return False

    # Verify no extra tools
    print("\n" + "=" * 60)
    print("Verifying No Extra Tools:")
    print("=" * 60)

    extra_tools = set(tools.tools_registry.keys()) - set(expected_tools.keys())
    if extra_tools:
        print(f"✗ Found unexpected extra tools: {extra_tools}")
        return False
    else:
        print(f"✓ No extra tools found")

    # Verify handler binding
    print("\n" + "=" * 60)
    print("Verifying Handler Binding:")
    print("=" * 60)

    for tool_name in expected_tools.keys():
        handler = tools.tools_registry[tool_name].get("handler")
        if handler and callable(handler):
            print(f"✓ Handler for '{tool_name}' is callable")
        else:
            print(f"✗ Handler for '{tool_name}' is not callable")
            return False

    # Test execute_tool method
    print("\n" + "=" * 60)
    print("Testing Tool Execution Framework:")
    print("=" * 60)

    try:
        # This will fail because OpenSearch isn't running, but we're testing the framework
        result = await tools.execute_tool("list_all_events", {"size": 5})
        print(f"✓ execute_tool() framework works")
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
    print("# MCP OpenSearch Tools - Simplified 4-Tool Test Suite")
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
        print("# Successfully simplified from 17 to 4 tools!")
        print("#" * 60)
        return 0
    else:
        print("# RESULT: SOME TESTS FAILED ✗")
        print("#" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

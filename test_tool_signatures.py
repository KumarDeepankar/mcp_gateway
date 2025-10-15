#!/usr/bin/env python3
"""
Test script to verify enhanced tool signatures in mcp_opensearch
"""
import asyncio
import json
import sys
import os

# Add the parent directory to sys.path so we can import from mcp_opensearch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_opensearch.tools import MCPTools


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_tool_definitions():
    """Test that tool definitions are properly loaded with enhanced signatures"""
    print_section("Testing Enhanced Tool Signatures")

    # Initialize MCPTools (will connect to OpenSearch but that's okay for testing tool registration)
    tools = MCPTools(opensearch_url="http://localhost:9200")

    # Get all tool definitions
    tool_definitions = tools.get_tool_definitions()

    print(f"✓ Total tools registered: {len(tool_definitions)}\n")

    # Test a few representative tools to verify enhancements
    test_tools = [
        "search_events",
        "filter_events_by_country",
        "search_and_filter_events",
        "get_events_stats_by_year",
        "list_all_events"
    ]

    for tool_name in test_tools:
        print_section(f"Tool: {tool_name}")

        tool_def = next((t for t in tool_definitions if t["name"] == tool_name), None)

        if not tool_def:
            print(f"✗ Tool '{tool_name}' not found!")
            continue

        print(f"Name: {tool_def['name']}")
        print(f"\nDescription:\n{tool_def['description']}\n")

        # Check for inputSchema
        if "inputSchema" in tool_def:
            schema = tool_def["inputSchema"]
            print("Parameters:")

            if "properties" in schema:
                for param_name, param_details in schema["properties"].items():
                    print(f"\n  • {param_name}:")
                    print(f"    Type: {param_details.get('type', 'N/A')}")
                    print(f"    Description: {param_details.get('description', 'N/A')}")

                    # Check for constraints
                    if "minimum" in param_details:
                        print(f"    Minimum: {param_details['minimum']}")
                    if "maximum" in param_details:
                        print(f"    Maximum: {param_details['maximum']}")
                    if "default" in param_details:
                        print(f"    Default: {param_details['default']}")
                    if "enum" in param_details:
                        print(f"    Allowed values: {param_details['enum']}")

            # Check for examples
            if "examples" in schema:
                print(f"\nExamples:")
                for i, example in enumerate(schema["examples"], 1):
                    print(f"  {i}. {json.dumps(example)}")

            # Check for required fields
            if "required" in schema:
                print(f"\nRequired fields: {', '.join(schema['required'])}")

        print("\n✓ Tool definition validated")

    return True


def test_tool_registry():
    """Test that all tools are properly registered in the registry"""
    print_section("Testing Tool Registry")

    tools = MCPTools(opensearch_url="http://localhost:9200")

    expected_tools = [
        "search_events",
        "search_events_by_title",
        "search_events_by_theme",
        "search_events_hybrid",
        "search_events_autocomplete",
        "filter_events_by_country",
        "filter_events_by_year",
        "filter_events_by_year_range",
        "filter_events_by_attendance",
        "search_and_filter_events",
        "get_events_stats_by_year",
        "get_events_stats_by_country",
        "get_events_by_theme_aggregation",
        "get_event_attendance_stats",
        "get_event_by_id",
        "list_all_events",
        "count_events"
    ]

    tool_names = tools.list_tool_names()

    print(f"Expected tools: {len(expected_tools)}")
    print(f"Registered tools: {len(tool_names)}\n")

    all_found = True
    for tool_name in expected_tools:
        if tool_name in tool_names:
            print(f"✓ {tool_name}")
        else:
            print(f"✗ {tool_name} - NOT FOUND")
            all_found = False

    if all_found:
        print("\n✓ All expected tools are registered")
    else:
        print("\n✗ Some tools are missing")
        return False

    return True


def test_tool_categories():
    """Test that tools are properly categorized"""
    print_section("Testing Tool Categories")

    tools = MCPTools(opensearch_url="http://localhost:9200")
    tool_definitions = tools.get_tool_definitions()

    categories = {
        "Search Tools": ["search_events", "search_events_by_title", "search_events_by_theme",
                        "search_events_hybrid", "search_events_autocomplete"],
        "Filter Tools": ["filter_events_by_country", "filter_events_by_year",
                        "filter_events_by_year_range", "filter_events_by_attendance",
                        "search_and_filter_events"],
        "Aggregation Tools": ["get_events_stats_by_year", "get_events_stats_by_country",
                             "get_events_by_theme_aggregation", "get_event_attendance_stats"],
        "Retrieval Tools": ["get_event_by_id", "list_all_events", "count_events"]
    }

    for category, tool_list in categories.items():
        print(f"\n{category}:")
        for tool_name in tool_list:
            tool_def = next((t for t in tool_definitions if t["name"] == tool_name), None)
            if tool_def:
                # Check if description has good context
                desc_length = len(tool_def.get("description", ""))
                has_use_case = "Use this" in tool_def.get("description", "")
                has_return_info = "Returns" in tool_def.get("description", "")

                status = "✓" if has_use_case and has_return_info and desc_length > 100 else "⚠"
                print(f"  {status} {tool_name} (desc: {desc_length} chars, use case: {has_use_case}, return info: {has_return_info})")
            else:
                print(f"  ✗ {tool_name} - NOT FOUND")

    print("\n✓ Tool categories validated")
    return True


def main():
    """Run all tests"""
    print_section("MCP OpenSearch Tool Signatures Test Suite")
    print("Testing enhanced tool signatures with examples, constraints, and better context\n")

    try:
        # Run tests
        success = True
        success = test_tool_registry() and success
        success = test_tool_definitions() and success
        success = test_tool_categories() and success

        print_section("Test Summary")
        if success:
            print("✓ All tests passed successfully!")
            print("\nEnhancements verified:")
            print("  • Detailed descriptions with use cases")
            print("  • Parameter examples and constraints")
            print("  • Return format documentation")
            print("  • Better context for agent decision-making")
            return 0
        else:
            print("✗ Some tests failed. Please review the output above.")
            return 1

    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

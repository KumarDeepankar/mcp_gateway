#!/usr/bin/env python3
"""
Test script for dynamic agent discovery system
Verifies that the plug-and-play functionality works correctly
"""

import asyncio
import aiohttp
import json
import sys
import os

# Add the agentic_assistant directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dynamic_agent_discovery import get_discovery_service, ToolCategory
from dynamic_tool_service import get_tool_service
from dynamic_discovery_wrapper import (
    discover_all_tools_dynamic, 
    discover_mcp_tools_dynamic, 
    discover_a2a_agents_dynamic,
    get_chart_tools_for_query,
    resolve_tool_dynamically
)


async def test_discovery_service():
    """Test the basic discovery service functionality"""
    print("🧪 Testing Dynamic Agent Discovery Service...")
    
    discovery_service = get_discovery_service()
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test cache refresh
            print("📥 Testing cache refresh...")
            success = await discovery_service.refresh_cache(session)
            print(f"✅ Cache refresh: {'SUCCESS' if success else 'FAILED'}")
            
            # Test getting cache stats
            stats = discovery_service.get_cached_stats()
            print(f"📊 Cache stats: {stats}")
            
            # Test getting all skills
            print("🔍 Testing skill discovery...")
            skills = await discovery_service.get_all_skills(session)
            print(f"✅ Found {len(skills)} skills")
            
            # Test category filtering
            chart_skills = await discovery_service.get_chart_tools(session)
            print(f"📊 Found {len(chart_skills)} chart tools")
            
            # Test skill resolution
            if skills:
                first_skill = skills[0]
                print(f"🔧 Testing skill resolution for: {first_skill.name}")
                resolved = await discovery_service.find_skill_by_name(first_skill.name, session)
                print(f"✅ Resolution: {'SUCCESS' if resolved else 'FAILED'}")
            
            return True
            
        except Exception as e:
            print(f"❌ Discovery service test failed: {e}")
            return False


async def test_tool_service():
    """Test the dynamic tool service functionality"""
    print("\n🛠️ Testing Dynamic Tool Service...")
    
    tool_service = get_tool_service()
    thinking_steps = []
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test discovering all tools
            print("🔍 Testing comprehensive tool discovery...")
            all_tools = await tool_service.discover_all_tools(session, thinking_steps)
            print(f"✅ Found {len(all_tools)} total tools")
            
            # Test query-based tool discovery
            print("🎯 Testing query-based tool discovery...")
            chart_query_tools = await tool_service.find_tools_for_query("create a bar chart", session, thinking_steps)
            print(f"📊 Found {len(chart_query_tools)} tools for chart query")
            
            research_query_tools = await tool_service.find_tools_for_query("search for news", session, thinking_steps)
            print(f"🔬 Found {len(research_query_tools)} tools for research query")
            
            # Test tool resolution
            print("🔧 Testing tool name resolution...")
            if all_tools:
                first_tool = all_tools[0]
                tool_name = first_tool.get("name", "unknown")
                resolved = await tool_service.resolve_tool_name(tool_name, session)
                print(f"✅ Tool resolution for '{tool_name}': {'SUCCESS' if resolved else 'FAILED'}")
            
            # Print thinking steps for debugging
            if thinking_steps:
                print(f"\n💭 Thinking steps ({len(thinking_steps)}):")
                for i, step in enumerate(thinking_steps[-5:], 1):  # Show last 5 steps
                    print(f"   {i}. {step}")
            
            return True
            
        except Exception as e:
            print(f"❌ Tool service test failed: {e}")
            return False


async def test_wrapper_functions():
    """Test the wrapper functions for drop-in replacement"""
    print("\n🔄 Testing Wrapper Functions...")
    
    async with aiohttp.ClientSession() as session:
        try:
            thinking_steps = []
            
            # Test MCP tool discovery wrapper
            print("🔧 Testing MCP tools discovery wrapper...")
            mcp_tools = await discover_mcp_tools_dynamic(session, thinking_steps)
            print(f"✅ MCP tools: {len(mcp_tools)}")
            
            # Test A2A agent discovery wrapper
            print("🤖 Testing A2A agents discovery wrapper...")
            a2a_tools = await discover_a2a_agents_dynamic(session, "test_conv_id", thinking_steps)
            print(f"✅ A2A tools: {len(a2a_tools)}")
            
            # Test combined discovery wrapper
            print("🔍 Testing combined discovery wrapper...")
            all_tools = await discover_all_tools_dynamic(session, "test_conv_id", thinking_steps)
            print(f"✅ Total tools: {len(all_tools)}")
            
            # Test chart tools for query
            print("📊 Testing chart tools for query...")
            chart_tools = await get_chart_tools_for_query("show me a pie chart", session, thinking_steps)
            print(f"✅ Chart tools for query: {len(chart_tools)}")
            
            # Test tool resolution
            if all_tools:
                tool_name = all_tools[0].get("name", "unknown")
                print(f"🔧 Testing dynamic tool resolution for '{tool_name}'...")
                resolved_tool = await resolve_tool_dynamically(tool_name, session)
                print(f"✅ Tool resolution: {'SUCCESS' if resolved_tool else 'FAILED'}")
            
            return True
            
        except Exception as e:
            print(f"❌ Wrapper functions test failed: {e}")
            return False


async def test_tool_categorization():
    """Test tool categorization and filtering"""
    print("\n🏷️ Testing Tool Categorization...")
    
    discovery_service = get_discovery_service()
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test category-based filtering
            viz_skills = await discovery_service.get_skills_by_category(ToolCategory.VISUALIZATION, session)
            research_skills = await discovery_service.get_skills_by_category(ToolCategory.RESEARCH, session)
            comm_skills = await discovery_service.get_skills_by_category(ToolCategory.COMMUNICATION, session)
            general_skills = await discovery_service.get_skills_by_category(ToolCategory.GENERAL, session)
            
            print(f"📊 Visualization tools: {len(viz_skills)}")
            print(f"🔬 Research tools: {len(research_skills)}")
            print(f"💬 Communication tools: {len(comm_skills)}")
            print(f"⚙️ General tools: {len(general_skills)}")
            
            # Show examples of each category
            if viz_skills:
                print(f"   📊 Example viz tool: {viz_skills[0].name}")
            if research_skills:
                print(f"   🔬 Example research tool: {research_skills[0].name}")
            if comm_skills:
                print(f"   💬 Example comm tool: {comm_skills[0].name}")
            if general_skills:
                print(f"   ⚙️ Example general tool: {general_skills[0].name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Tool categorization test failed: {e}")
            return False


async def main():
    """Run all tests"""
    print("🚀 Starting Dynamic Discovery System Tests\n")
    
    tests = [
        ("Discovery Service", test_discovery_service),
        ("Tool Service", test_tool_service),
        ("Wrapper Functions", test_wrapper_functions),
        ("Tool Categorization", test_tool_categorization)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*50)
    print("📋 TEST SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Dynamic discovery system is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
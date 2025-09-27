# dynamic_discovery_wrapper.py
"""
Wrapper functions to replace hard-coded tool discovery with dynamic discovery
These functions maintain the same interface as the original functions for drop-in replacement
"""

import asyncio
from typing import Dict, List, Any
import aiohttp

from dynamic_tool_service import get_tool_service


async def discover_all_tools_dynamic(http_session: aiohttp.ClientSession, conv_id: str, thinking_steps: List[str]) -> List[Dict[str, Any]]:
    """
    Drop-in replacement for combined MCP + A2A tool discovery
    Uses dynamic discovery service instead of hard-coded logic
    """
    tool_service = get_tool_service()
    return await tool_service.discover_all_tools(http_session, thinking_steps)


async def discover_mcp_tools_dynamic(http_session: aiohttp.ClientSession, thinking_steps: List[str]) -> List[Dict[str, Any]]:
    """
    Drop-in replacement for MCP tool discovery
    """
    tool_service = get_tool_service()
    return await tool_service._discover_mcp_tools(http_session, thinking_steps)


async def discover_a2a_agents_dynamic(http_session: aiohttp.ClientSession, conv_id: str, thinking_steps: List[str]) -> List[Dict[str, Any]]:
    """
    Drop-in replacement for A2A agent discovery
    """
    tool_service = get_tool_service()
    return await tool_service._discover_a2a_tools_dynamic(http_session, thinking_steps)


async def get_chart_tools_for_query(query: str, http_session: aiohttp.ClientSession, thinking_steps: List[str]) -> List[Dict[str, Any]]:
    """
    Get chart/visualization tools that are relevant for a query
    """
    tool_service = get_tool_service()
    chart_tools = await tool_service.get_chart_tools(http_session, thinking_steps)
    
    # Filter based on query if needed
    query_lower = query.lower()
    viz_keywords = ["chart", "plot", "graph", "visual", "show", "display", "analyze", "data"]
    
    if any(keyword in query_lower for keyword in viz_keywords):
        thinking_steps.append(f"Query '{query}' requires visualization - returning {len(chart_tools)} chart tools")
        return chart_tools
    else:
        thinking_steps.append(f"Query '{query}' does not require visualization - returning empty list")
        return []


async def resolve_tool_dynamically(tool_name: str, http_session: aiohttp.ClientSession) -> Dict[str, Any]:
    """
    Resolve a tool name to its dynamic definition
    """
    tool_service = get_tool_service()
    skill_info = await tool_service.resolve_tool_name(tool_name, http_session)
    
    if skill_info:
        return {
            "name": skill_info.name,
            "description": skill_info.description,
            "inputSchema": skill_info.input_schema,
            "is_a2a_tool": True,
            "agent_id": skill_info.agent_id,
            "skill_id": skill_info.skill_id,
            "skill_name": skill_info.name,
            "agent_name": skill_info.agent_name,
            "is_chart_tool": skill_info.is_chart_tool,
            "tags": skill_info.tags,
            "category": skill_info.category.value,
            "metadata": skill_info.metadata
        }
    return None
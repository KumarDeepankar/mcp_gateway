# dynamic_tool_service.py
"""
Dynamic Tool Service - High-level interface for tool discovery and execution
Replaces hard-coded tool references with dynamic discovery
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
import aiohttp
import logging

from dynamic_agent_discovery import get_discovery_service, DynamicSkillInfo, ToolCategory
from settings import MCP_MESSAGE_ENDPOINT, AGENT_INTERFACE_BASE_URL

logger = logging.getLogger(__name__)


class DynamicToolService:
    """Service for dynamic tool discovery and execution"""
    
    def __init__(self):
        self.discovery_service = get_discovery_service()
    
    async def discover_all_tools(self, http_session: aiohttp.ClientSession, thinking_steps: List[str]) -> List[Dict[str, Any]]:
        """
        Discover all available tools (MCP + A2A) dynamically
        Replaces the hard-coded tool discovery logic
        """
        all_tools = []
        
        # Discover MCP tools
        mcp_tools = await self._discover_mcp_tools(http_session, thinking_steps)
        all_tools.extend(mcp_tools)
        
        # Discover A2A tools/skills dynamically
        a2a_tools = await self._discover_a2a_tools_dynamic(http_session, thinking_steps)
        all_tools.extend(a2a_tools)
        
        thinking_steps.append(f"Dynamic Discovery: Found {len(mcp_tools)} MCP tools + {len(a2a_tools)} A2A tools = {len(all_tools)} total")
        
        return all_tools
    
    async def _discover_mcp_tools(self, http_session: aiohttp.ClientSession, thinking_steps: List[str]) -> List[Dict[str, Any]]:
        """Discover MCP tools using existing logic"""
        payload = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": str(uuid.uuid4())}
        headers = {
            'Accept': 'application/json, text/event-stream',
            'Content-Type': 'application/json',
            'MCP-Protocol-Version': '2025-06-18'
        }
        
        try:
            async with http_session.post(MCP_MESSAGE_ENDPOINT, json=payload, headers=headers, timeout=10) as response:
                if response.status != 200:
                    error_text = await response.text()
                    thinking_steps.append(f"MCP Discovery: HTTP Error {response.status} - {error_text}")
                    return []
                
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    resp_json = await response.json()
                    if resp_json.get("error"):
                        thinking_steps.append(f"MCP Discovery: API Error {resp_json['error']}")
                        return []
                    tools = resp_json.get("result", {}).get("tools", [])
                    thinking_steps.append(f"MCP Discovery: Fetched {len(tools)} tools from gateway")
                    return tools
                elif 'text/event-stream' in content_type:
                    tools = []
                    async for line in response.content:
                        try:
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith('data: '):
                                data_json = json.loads(line_str[6:])
                                if data_json.get('result') and 'tools' in data_json['result']:
                                    tools = data_json['result']['tools']
                                    break
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            continue
                    thinking_steps.append(f"MCP Discovery: Fetched {len(tools)} tools from gateway (SSE)")
                    return tools
                else:
                    thinking_steps.append(f"MCP Discovery: Unexpected content type: {content_type}")
                    return []
        except Exception as e:
            thinking_steps.append(f"MCP Discovery: Exception fetching tools: {e}")
            return []
    
    async def _discover_a2a_tools_dynamic(self, http_session: aiohttp.ClientSession, thinking_steps: List[str]) -> List[Dict[str, Any]]:
        """Dynamically discover A2A tools using the discovery service"""
        try:
            # Get all skills from discovery service
            skills = await self.discovery_service.get_all_skills(http_session)
            
            tool_definitions = []
            for skill in skills:
                # Create tool definition compatible with existing system
                tool_def = {
                    "name": skill.name,
                    "description": skill.description,
                    "inputSchema": skill.input_schema,
                    "is_a2a_tool": True,
                    "agent_id": skill.agent_id,
                    "skill_id": skill.skill_id,
                    "skill_name": skill.name,
                    "agent_name": skill.agent_name,
                    "is_chart_tool": skill.is_chart_tool,
                    "tags": skill.tags,
                    "category": skill.category.value,
                    "metadata": skill.metadata
                }
                tool_definitions.append(tool_def)
            
            thinking_steps.append(f"Dynamic A2A Discovery: Found {len(tool_definitions)} tools from {len(set(s.agent_id for s in skills))} agents")
            return tool_definitions
            
        except Exception as e:
            thinking_steps.append(f"Dynamic A2A Discovery: Exception: {e}")
            return []
    
    async def find_tools_for_query(self, query: str, http_session: aiohttp.ClientSession, thinking_steps: List[str]) -> List[Dict[str, Any]]:
        """
        Find relevant tools for a user query
        Replaces hard-coded tool matching logic
        """
        # Get relevant skills based on query
        relevant_skills = await self.discovery_service.get_skills_for_query(query, http_session)
        
        tool_definitions = []
        for skill in relevant_skills:
            tool_def = {
                "name": skill.name,
                "description": skill.description,
                "inputSchema": skill.input_schema,
                "is_a2a_tool": True,
                "agent_id": skill.agent_id,
                "skill_id": skill.skill_id,
                "skill_name": skill.name,
                "agent_name": skill.agent_name,
                "is_chart_tool": skill.is_chart_tool,
                "tags": skill.tags,
                "category": skill.category.value,
                "metadata": skill.metadata
            }
            tool_definitions.append(tool_def)
        
        thinking_steps.append(f"Query-based tool discovery: Found {len(tool_definitions)} relevant tools for query")
        return tool_definitions
    
    async def get_chart_tools(self, http_session: aiohttp.ClientSession, thinking_steps: List[str]) -> List[Dict[str, Any]]:
        """Get all available chart/visualization tools dynamically"""
        chart_skills = await self.discovery_service.get_chart_tools(http_session)
        
        tool_definitions = []
        for skill in chart_skills:
            tool_def = {
                "name": skill.name,
                "description": skill.description,
                "inputSchema": skill.input_schema,
                "is_a2a_tool": True,
                "agent_id": skill.agent_id,
                "skill_id": skill.skill_id,
                "skill_name": skill.name,
                "agent_name": skill.agent_name,
                "is_chart_tool": True,
                "tags": skill.tags,
                "category": skill.category.value,
                "metadata": skill.metadata
            }
            tool_definitions.append(tool_def)
        
        thinking_steps.append(f"Chart tools discovery: Found {len(tool_definitions)} chart/visualization tools")
        return tool_definitions
    
    async def resolve_tool_name(self, tool_name: str, http_session: aiohttp.ClientSession) -> Optional[DynamicSkillInfo]:
        """
        Resolve a tool name to actual skill info
        Replaces hard-coded tool name mapping
        """
        # Try exact match first
        skill = await self.discovery_service.find_skill_by_name(tool_name, http_session)
        if skill:
            return skill
        
        # Try mapping common aliases to actual skill names
        alias_mappings = await self._get_dynamic_alias_mappings(http_session)
        
        if tool_name in alias_mappings:
            actual_skill_id = alias_mappings[tool_name]
            skill = await self.discovery_service.get_skill_by_id(actual_skill_id, http_session)
            if skill:
                return skill
        
        return None
    
    async def _get_dynamic_alias_mappings(self, http_session: aiohttp.ClientSession) -> Dict[str, str]:
        """
        Generate dynamic alias mappings based on discovered skills
        Replaces hard-coded tool name mappings
        """
        skills = await self.discovery_service.get_all_skills(http_session)
        mappings = {}
        
        for skill in skills:
            # Create aliases based on skill properties
            skill_name_lower = skill.name.lower()
            
            # Chart tool aliases
            if skill.is_chart_tool:
                if "data" in skill_name_lower and "analy" in skill_name_lower:
                    mappings["data_analyzer_and_visualizer"] = skill.skill_id
                    mappings["data_analyzer"] = skill.skill_id
                if "chart" in skill_name_lower:
                    mappings["specific_graph_plotter"] = skill.skill_id
                    mappings["natural_language_chart"] = skill.skill_id
                    mappings["create_chart_visualization"] = skill.skill_id
            
            # Communication tool aliases
            if skill.category == ToolCategory.COMMUNICATION:
                if "joke" in skill_name_lower:
                    mappings["tell-joke"] = skill.skill_id
                if "hello" in skill_name_lower or "greet" in skill_name_lower:
                    mappings["hello"] = skill.skill_id
        
        return mappings
    
    async def get_tool_execution_params(self, tool_id: str, payload: Dict[str, Any], http_session: aiohttp.ClientSession) -> Dict[str, Any]:
        """
        Generate tool execution parameters dynamically based on skill schema
        Uses the skill's input_schema to map parameters correctly without hardcoding
        """
        skill = await self.discovery_service.get_skill_by_id(tool_id, http_session)
        if not skill:
            # Fallback to generic content preparation
            return {
                "content": payload.get("content", payload.get("message", payload.get("query", json.dumps(payload))))
            }
        
        # Use schema-aware parameter mapping
        return self._map_params_by_schema(payload, skill)
    
    def _map_params_by_schema(self, payload: Dict[str, Any], skill: DynamicSkillInfo) -> Dict[str, Any]:
        """
        Map payload parameters to skill parameters based on the skill's input schema
        This is truly dynamic and doesn't hardcode parameter names
        """
        if not skill.input_schema or not isinstance(skill.input_schema, dict):
            # Fallback if no schema available
            return self._prepare_generic_params(payload, skill)
        
        schema_properties = skill.input_schema.get("properties", {})
        required_params = skill.input_schema.get("required", [])
        mapped_params = {}
        
        # Try to map each required parameter from the schema
        for param_name, param_schema in schema_properties.items():
            param_description = param_schema.get("description", "").lower()
            param_type = param_schema.get("type")
            
            # Try to find the best match from payload
            mapped_value = self._find_best_payload_match(
                param_name, param_description, param_type, payload
            )
            
            if mapped_value is not None:
                mapped_params[param_name] = mapped_value
            elif param_name in required_params:
                # For required params, provide a reasonable default
                mapped_params[param_name] = self._get_default_for_required_param(
                    param_name, param_description, param_type, payload
                )
        
        # Ensure we have at least a 'content' parameter for the skill.execute endpoint
        if "content" not in mapped_params:
            # Find the most appropriate content from mapped params or payload
            content_value = self._extract_content_value(mapped_params, payload)
            mapped_params["content"] = content_value
        
        return mapped_params
    
    def _find_best_payload_match(self, param_name: str, param_description: str, param_type: str, payload: Dict[str, Any]) -> Any:
        """Find the best matching value from payload for a given parameter"""
        param_name_lower = param_name.lower()
        
        # Direct name matches (highest priority)
        if param_name in payload:
            return payload[param_name]
        
        # Common aliases based on parameter name
        name_aliases = {
            "raw_data": ["data", "content", "input_data", "dataset", "document_content"],
            "analysis_context": ["context", "analysis_type", "intent", "purpose"],
            "preferences": ["options", "settings", "config", "parameters"],
            "query": ["question", "request", "message", "text", "input"],
            "content": ["text", "message", "input", "data", "raw_data"],
            "data": ["raw_data", "dataset", "input_data", "content"]
        }
        
        # Try aliases for this parameter name
        if param_name_lower in name_aliases:
            for alias in name_aliases[param_name_lower]:
                if alias in payload:
                    return payload[alias]
        
        # Description-based matching (medium priority)
        description_keywords = {
            "raw data": ["data", "raw_data", "content", "input_data", "dataset"],
            "data to analyze": ["data", "raw_data", "content", "dataset"],
            "context": ["context", "analysis_context", "intent"],
            "preferences": ["preferences", "options", "settings"],
            "query": ["query", "question", "message", "content"]
        }
        
        for keyword, candidate_fields in description_keywords.items():
            if keyword in param_description:
                for field in candidate_fields:
                    if field in payload:
                        return payload[field]
        
        # Type-based fallback (lowest priority)
        if param_type in ["string", ["string", "object", "array"]]:
            # For string/mixed types, try common content fields
            for field in ["content", "query", "message", "text", "data"]:
                if field in payload:
                    value = payload[field]
                    if isinstance(value, str) or param_type == ["string", "object", "array"]:
                        return value
        
        return None
    
    def _get_default_for_required_param(self, param_name: str, param_description: str, param_type: str, payload: Dict[str, Any]) -> Any:
        """Generate a reasonable default for a required parameter that wasn't found"""
        param_name_lower = param_name.lower()
        
        # Special handling for known required parameters
        if param_name_lower == "raw_data":
            # For raw_data, serialize the entire payload as fallback
            return json.dumps(payload) if payload else "No data provided"
        
        if param_name_lower in ["content", "query", "message"]:
            # Extract any textual content from payload
            for field in ["content", "query", "message", "text", "input"]:
                if field in payload and payload[field]:
                    return str(payload[field])
            return json.dumps(payload) if payload else "No content provided"
        
        # Type-based defaults
        if param_type == "string" or param_type == ["string", "object", "array"]:
            return json.dumps(payload) if payload else ""
        elif param_type == "object":
            return payload if isinstance(payload, dict) else {}
        elif param_type == "array":
            return payload if isinstance(payload, list) else []
        
        return ""
    
    def _extract_content_value(self, mapped_params: Dict[str, Any], payload: Dict[str, Any]) -> str:
        """Extract the most appropriate content value for the skill.execute 'content' parameter"""
        # If we already mapped a content-like parameter, use it
        for param_name, value in mapped_params.items():
            if param_name.lower() in ["raw_data", "query", "message", "input", "text"]:
                return str(value) if value is not None else ""
        
        # Otherwise, extract from payload
        for field in ["content", "query", "message", "text", "raw_data", "data"]:
            if field in payload and payload[field]:
                return str(payload[field])
        
        # Final fallback: serialize the entire payload
        return json.dumps(payload) if payload else "No content provided"
    
    def _prepare_visualization_params(self, payload: Dict[str, Any], skill: DynamicSkillInfo) -> Dict[str, Any]:
        """Prepare parameters for visualization tools"""
        # Try different field names that might contain the query
        content = payload.get("user_query", payload.get("query", payload.get("content", "")))
        
        # If still empty but we have data, create a descriptive query
        if not content and payload.get("data"):
            content = f"Analyze and visualize the following data: {json.dumps(payload['data'])}"
        
        # Check if skill expects specific parameters based on input schema
        params = {"content": content}
        
        # Add data if provided
        if payload.get("data"):
            params["data"] = payload["data"]
        
        # Add chart type if specified
        if payload.get("chart_type"):
            params["chart_type"] = payload["chart_type"]
        
        return params
    
    def _prepare_communication_params(self, payload: Dict[str, Any], skill: DynamicSkillInfo) -> Dict[str, Any]:
        """Prepare parameters for communication tools"""
        content = payload.get("content", payload.get("message", payload.get("text", "")))
        
        # Provide defaults for common communication tools
        if "joke" in skill.skill_id.lower() and not content:
            content = "Tell me a joke"
        elif "hello" in skill.skill_id.lower() and not content:
            content = "Hello"
        
        return {"content": content}
    
    def _prepare_research_params(self, payload: Dict[str, Any], skill: DynamicSkillInfo) -> Dict[str, Any]:
        """Prepare parameters for research tools"""
        return {
            "content": payload.get("query", payload.get("content", payload.get("search_query", "")))
        }
    
    def _prepare_generic_params(self, payload: Dict[str, Any], skill: DynamicSkillInfo) -> Dict[str, Any]:
        """Prepare parameters for generic tools"""
        return {
            "content": payload.get("content", payload.get("message", payload.get("query", json.dumps(payload))))
        }


# Global singleton instance
_tool_service: Optional[DynamicToolService] = None

def get_tool_service() -> DynamicToolService:
    """Get the global tool service instance"""
    global _tool_service
    if _tool_service is None:
        _tool_service = DynamicToolService()
    return _tool_service
# agentic_assistant/gemini_query_agent/tool_interactions.py
import asyncio
import json
import uuid
from typing import List, Dict, Any, Tuple, Optional

import aiohttp

from settings import (
    MCP_MESSAGE_ENDPOINT, AGENT_INTERFACE_BASE_URL
)
from .a2a_models import (
    A2AAgentMessage, A2APerformative, A2AClientToolDefinition,
    A2AChartSpec, A2AErrorPayload, A2AMultiChartResponse
)
from dynamic_tool_service import get_tool_service


async def discover_mcp_tools(http_session: aiohttp.ClientSession, thinking_steps: List[str]) -> List[Dict[str, Any]]:
    """
    Fetches available tools from the MCP Toolbox Gateway using the 2025-06-18 specification.
    """
    payload = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": str(uuid.uuid4())}
    # Headers per MCP 2025-06-18 specification
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
            
            # Handle both JSON and SSE responses from the gateway
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
                # Parse SSE response for tools/list
                tools = []
                async for line in response.content:
                    try:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            data_json = json.loads(line_str[6:])
                            if data_json.get('result') and 'tools' in data_json['result']:
                                tools = data_json['result']['tools']
                                break
                    except (UnicodeDecodeError, json.JSONDecodeError) as e:
                        continue
                thinking_steps.append(f"MCP Discovery: Fetched {len(tools)} tools from gateway (SSE)")
                return tools
            else:
                thinking_steps.append(f"MCP Discovery: Unexpected content type: {content_type}")
                return []
    except Exception as e:
        thinking_steps.append(f"MCP Discovery: Exception fetching tools: {e}")
        return []

async def call_mcp_tool(http_session: aiohttp.ClientSession, tool_name: str, arguments: Dict[str, Any]) -> Tuple[
    Optional[str], List[Dict[str, Any]], str]:
    """
    Calls a tool via the MCP Toolbox Gateway and handles the streaming SSE response.
    Updated for MCP 2025-06-18 specification compliance.
    """
    if not isinstance(arguments, dict):
        return None, [], f"Tool arguments for '{tool_name}' must be a dictionary."

    payload = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}, "id": str(uuid.uuid4())}

    text_result = None
    sources_list = []
    status_message = f"Tool '{tool_name}' initiated."

    try:
        # Headers per MCP 2025-06-18 specification
        headers = {
            'Accept': 'application/json, text/event-stream',
            'Content-Type': 'application/json',
            'MCP-Protocol-Version': '2025-06-18'
        }
        async with http_session.post(MCP_MESSAGE_ENDPOINT, json=payload, timeout=45, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                return None, [], f"HTTP Error {response.status} calling {tool_name}: {error_text}"

            # Handle both JSON and SSE responses from the gateway
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                # Handle direct JSON response
                resp_json = await response.json()
                if resp_json.get("error"):
                    error_details = resp_json['error'].get('message', 'Unknown error from MCP gateway.')
                    return None, [], f"MCP Error for '{tool_name}': {error_details}"
                
                result = resp_json.get("result", {})
                content_list = result.get("content", [])
                for item in content_list:
                    if item.get("type") == "text":
                        text_result = (text_result + "\n" if text_result else "") + item.get("text", "")
                    elif item.get("type") == "source_references":
                        sources_list.extend(item.get("sources", []))
                    elif item.get("type") == "resource":
                        # Convert MCP resource format to source format expected by frontend
                        resource = item.get("resource", {})
                        if resource.get("uri"):
                            source = {
                                "url": resource.get("uri"),
                                "title": resource.get("name", "Untitled"),
                                "snippet": resource.get("description", "No description available")
                            }
                            sources_list.append(source)
                status_message = f"Tool '{tool_name}' completed successfully."
                return text_result, sources_list, status_message
                
            elif 'text/event-stream' in content_type:
                # Process the Server-Sent Events (SSE) stream from gateway
                async for line in response.content:
                    try:
                        line_str = line.decode('utf-8').strip()
                        
                        # Handle SSE event format with id: and data: prefixes
                        if line_str.startswith('data: '):
                            chunk_str = line_str[6:].strip()
                            if not chunk_str:
                                continue
                            chunk = json.loads(chunk_str)

                            # Handle gateway progress notifications
                            if chunk.get("method") == "notifications/gateway_progress":
                                status_message = chunk.get("params", {}).get("message", status_message)
                            elif chunk.get("method") == "tools/call_progress":
                                status_message = chunk.get("params", {}).get("status", status_message)
                            elif "result" in chunk:
                                content_list = chunk["result"].get("content", [])
                                for item in content_list:
                                    if item.get("type") == "text":
                                        text_result = (text_result + "\n" if text_result else "") + item.get("text", "")
                                    elif item.get("type") == "source_references":
                                        sources_list.extend(item.get("sources", []))
                                    elif item.get("type") == "resource":
                                        # Convert MCP resource format to source format expected by frontend
                                        resource = item.get("resource", {})
                                        if resource.get("uri"):
                                            source = {
                                                "url": resource.get("uri"),
                                                "title": resource.get("name", "Untitled"),
                                                "snippet": resource.get("description", "No description available")
                                            }
                                            sources_list.append(source)
                                status_message = f"Tool '{tool_name}' completed successfully."
                            elif "error" in chunk:
                                error_details = chunk['error'].get('message', 'Unknown error from MCP gateway.')
                                return None, [], f"MCP Error for '{tool_name}': {error_details}"
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        # Ignore lines that are not valid JSON (like heartbeats or comments)
                        continue

                return text_result, sources_list, status_message
            else:
                return None, [], f"Unexpected content type from gateway: {content_type}"
                
    except Exception as e:
        return None, [], f"Exception calling streaming tool '{tool_name}': {e}"


async def discover_a2a_agents(http_session: aiohttp.ClientSession, conv_id: str, thinking_steps: List[str]) -> List[Dict[str, Any]]:
    """
    Discovers A2A tools using dynamic discovery service.
    """
    if not conv_id:
        thinking_steps.append("A2A Discovery: Conversation ID missing")
        return []

    try:
        # Use dynamic tool service for discovery
        tool_service = get_tool_service()
        tool_definitions = await tool_service._discover_a2a_tools_dynamic(http_session, thinking_steps)
        return tool_definitions
    except Exception as e:
        thinking_steps.append(f"Dynamic A2A Discovery: Exception: {e}")
        return []


async def call_a2a_agent(http_session: aiohttp.ClientSession, tool_id: str, payload: Dict, conv_id: str, thinking_steps: List[str]) -> Tuple[Optional[List[A2AChartSpec]], str]:
    """
    Calls an A2A tool using the new agent_interface JSON-RPC skill.execute endpoint.
    """
    if not conv_id:
        return None, "A2A Tool Execution: Conversation ID missing."

    try:
        # Use dynamic tool service to prepare execution parameters
        tool_service = get_tool_service()
        execution_params = await tool_service.get_tool_execution_params(tool_id, payload, http_session)
        content = execution_params.get("content", "")
        
        # Create JSON-RPC skill.execute request
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "method": "skill.execute",
            "params": {
                "skill_id": tool_id,
                "content": content,
                "data": payload if isinstance(payload, dict) else {},
                "context_id": conv_id
            },
            "id": f"skill_exec_{uuid.uuid4().hex[:8]}"
        }

        thinking_steps.append(f"A2A Tool Execution: Executing skill {tool_id} via JSON-RPC")

        async with http_session.post(
            f"{AGENT_INTERFACE_BASE_URL}/rpc",
            json=jsonrpc_request,
            headers={"Content-Type": "application/json"},
            timeout=30
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                thinking_steps.append(f"A2A Tool Execution: HTTP Error {response.status} - {error_text}")
                return None, f"A2A Tool Execution: HTTP Error {response.status}."

            response_data = await response.json()
            
            if "error" in response_data:
                error_msg = response_data["error"].get("message", "Unknown error")
                thinking_steps.append(f"A2A Tool Execution: JSON-RPC Error {error_msg}")
                return None, f"A2A Tool Execution: {error_msg}"
            
            result = response_data.get("result", {})
            task_id = result.get("task_id")
            executing_agent = result.get("executing_agent")
            skill_id_used = result.get("skill_id")
            
            if task_id:
                thinking_steps.append(f"A2A Tool Execution: Task {task_id} created on agent {executing_agent}, waiting for completion...")
                # Wait for task completion using the new JSON-RPC method
                return await wait_for_a2a_task_completion_jsonrpc(http_session, task_id, thinking_steps, skill_id_used)
            else:
                return None, "No task_id returned from skill execution"
                    
    except Exception as e:
        thinking_steps.append(f"A2A Tool Execution: Exception: {e}")
        return None, f"Exception during A2A tool call: {e}"


async def wait_for_a2a_task_completion_jsonrpc(http_session: aiohttp.ClientSession, task_id: str, thinking_steps: List[str], skill_id: str = None, max_wait_time: int = 60) -> Tuple[Optional[List[A2AChartSpec]], str]:
    """
    Waits for an A2A task to complete using JSON-RPC task.get endpoint.
    """
    elapsed_time = 0
    poll_interval = 2
    
    while elapsed_time < max_wait_time:
        try:
            # Use JSON-RPC task.get endpoint
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": "task.get",
                "params": {"task_id": task_id},
                "id": f"task_get_{uuid.uuid4().hex[:8]}"
            }
            
            async with http_session.post(
                f"{AGENT_INTERFACE_BASE_URL}/rpc",
                json=jsonrpc_request,
                headers={"Content-Type": "application/json"},
                timeout=10
            ) as response:
                if response.status != 200:
                    thinking_steps.append(f"A2A Task Status: HTTP Error {response.status}")
                    return None, f"Failed to get task status: {response.status}"
                
                response_data = await response.json()
                
                if "error" in response_data:
                    error_msg = response_data["error"].get("message", "Unknown error")
                    thinking_steps.append(f"A2A Task Status: JSON-RPC Error {error_msg}")
                    return None, f"Failed to get task status: {error_msg}"
                
                task_data = response_data.get("result", {})
                task_state = task_data.get("state", "unknown")
                
                if task_state == "completed":
                    thinking_steps.append(f"A2A Task {task_id}: Completed successfully")
                    
                    # Check if this is a chart skill by looking at skill_id or artifacts
                    is_chart_skill = skill_id and any(keyword in skill_id.lower() for keyword in ["chart", "visual", "graph", "plot", "visualization"])
                    
                    # Extract chart data from artifacts if it's a chart skill
                    artifacts = task_data.get("artifacts", [])
                    chart_specs = []
                    
                    if artifacts:
                        for artifact in artifacts:
                            # Check multiple possible fields for chart artifact type
                            artifact_type = artifact.get("artifact_type", artifact.get("name", "")).lower()
                            artifact_metadata = artifact.get("metadata", {})
                            # For chart recommendation agent, check for "chart recommendations" in name or description
                            if (artifact_type == "chart" or 
                                "chart" in artifact.get("name", "").lower() or 
                                "chart" in artifact.get("description", "").lower() or
                                artifact_metadata.get("artifact_type") == "chart" or
                                artifact_metadata.get("is_chart_data") == True or
                                is_chart_skill):
                                parts = artifact.get("parts", [])
                                for part in parts:
                                    # Check both "type" and "kind" fields for data parts
                                    part_type = part.get("type", part.get("kind", ""))
                                    if part_type == "data":
                                        # Chart data can be in either 'content' or 'data' field
                                        chart_content = part.get("content", part.get("data", {}))
                                        
                                        # Handle chart recommendation agent format with multiple chart options
                                        if "chart_options" in chart_content:
                                            for chart_option in chart_content.get("chart_options", []):
                                                chart_spec = A2AChartSpec(
                                                    chart_type=chart_option.get("chart_type", "unknown"),
                                                    data=chart_option.get("data", []),
                                                    options=chart_option.get("options", {}),
                                                    metadata={
                                                        "data_summary": chart_option.get("data_summary", ""),
                                                        "confidence": chart_option.get("confidence", 0.0),
                                                        "reasoning": chart_option.get("reasoning", ""),
                                                        "primary_recommendation": chart_content.get("primary_recommendation", ""),
                                                        **chart_content.get("metadata", {})
                                                    }
                                                )
                                                chart_specs.append(chart_spec)
                                        else:
                                            # Legacy single chart format
                                            chart_spec = A2AChartSpec(
                                                chart_type=chart_content.get("chart_type", "unknown"),
                                                data=chart_content.get("data", []),
                                                options=chart_content.get("options", {}),
                                                metadata=chart_content.get("metadata", {})
                                            )
                                            chart_specs.append(chart_spec)
                    
                    # For non-chart skills, return None for chart_specs but indicate success
                    if chart_specs:
                        return chart_specs, "Task completed successfully"
                    else:
                        # Non-chart skill completed successfully
                        return None, f"Task completed successfully (non-chart skill: {skill_id})"
                
                elif task_state == "failed":
                    thinking_steps.append(f"A2A Task {task_id}: Failed")
                    return None, "Task failed"
                
                elif task_state == "running":
                    thinking_steps.append(f"A2A Task {task_id}: Still running... ({elapsed_time}s)")
                
                # Wait before next poll
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
                
        except Exception as e:
            thinking_steps.append(f"A2A Task Status: Exception: {e}")
            return None, f"Exception checking task status: {e}"
    
    thinking_steps.append(f"A2A Task {task_id}: Timeout after {max_wait_time}s")
    return None, f"Task timeout after {max_wait_time} seconds"


# Legacy function for backward compatibility
async def wait_for_a2a_task_completion(http_session: aiohttp.ClientSession, task_id: str, thinking_steps: List[str], max_wait_time: int = 60) -> Tuple[Optional[List[A2AChartSpec]], str]:
    """
    Legacy wrapper - redirects to new JSON-RPC method.
    """
    return await wait_for_a2a_task_completion_jsonrpc(http_session, task_id, thinking_steps, None, max_wait_time)

import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)


class MCPToolClient:
    """Client for communicating with MCP Registry Discovery service"""

    def __init__(self, registry_base_url: str = None, origin: str = None):
        # Support environment-based configuration for distributed deployments
        self.registry_base_url = registry_base_url or os.getenv("MCP_GATEWAY_URL", "http://localhost:8021")

        # Dynamic origin determination:
        # 1. Explicit origin parameter (highest priority)
        # 2. Environment variable AGENTIC_SEARCH_ORIGIN
        # 3. Infer from AGENTIC_SEARCH_URL if available
        # 4. Default to registry_base_url
        if origin:
            self.origin = origin
        elif os.getenv("AGENTIC_SEARCH_ORIGIN"):
            self.origin = os.getenv("AGENTIC_SEARCH_ORIGIN")
        elif os.getenv("AGENTIC_SEARCH_URL"):
            self.origin = os.getenv("AGENTIC_SEARCH_URL")
        else:
            self.origin = self.registry_base_url

        self.client = httpx.AsyncClient(timeout=60)
        logger.info(f"MCPToolClient initialized: gateway={self.registry_base_url}, origin={self.origin}")

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Fetch available tools from MCP registry"""
        try:
            # Initialize MCP session
            init_payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "search-agent-init",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "clientInfo": {
                        "name": "agentic-search",
                        "version": "1.0.0"
                    }
                }
            }

            headers = {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2025-06-18",
                "Origin": self.origin
            }

            # Initialize session
            response = await self.client.post(f"{self.registry_base_url}/mcp", json=init_payload, headers=headers)
            response.raise_for_status()

            session_id = response.headers.get("Mcp-Session-Id")
            if not session_id:
                logger.error("No session ID received from MCP registry")
                return []

            # Add session ID to headers
            headers["Mcp-Session-Id"] = session_id

            # Send initialized notification
            init_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }

            await self.client.post(f"{self.registry_base_url}/mcp", json=init_notification, headers=headers)

            # Get tools list
            tools_payload = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": "search-agent-tools"
            }

            response = await self.client.post(f"{self.registry_base_url}/mcp", json=tools_payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            tools = data.get("result", {}).get("tools", [])

            logger.info(f"Retrieved {len(tools)} tools from MCP registry")
            return tools

        except Exception as e:
            logger.error(f"Error fetching tools from MCP registry: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific tool via MCP registry"""
        try:
            # Initialize session for tool call
            init_payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "search-agent-tool-call",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "clientInfo": {
                        "name": "agentic-search",
                        "version": "1.0.0"
                    }
                }
            }

            headers = {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2025-06-18",
                "Origin": self.origin
            }

            # Initialize session
            response = await self.client.post(f"{self.registry_base_url}/mcp", json=init_payload, headers=headers)
            response.raise_for_status()

            session_id = response.headers.get("Mcp-Session-Id")
            if not session_id:
                logger.error("No session ID received for tool call")
                return {"error": "Failed to establish MCP session"}

            headers["Mcp-Session-Id"] = session_id

            # Send initialized notification
            init_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            await self.client.post(f"{self.registry_base_url}/mcp", json=init_notification, headers=headers)

            # Call the tool
            tool_call_payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": f"search-agent-call-{tool_name}",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            response = await self.client.post(f"{self.registry_base_url}/mcp", json=tool_call_payload, headers=headers)

            # Handle both JSON and streaming responses
            content_type = response.headers.get("content-type", "")

            if "application/json" in content_type:
                response.raise_for_status()
                return response.json()
            elif "text/event-stream" in content_type:
                # Handle streaming response
                result = {}
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if "result" in data:
                                result = data
                                break
                            elif "error" in data:
                                result = data
                                break
                        except json.JSONDecodeError:
                            continue

                return result
            else:
                response.raise_for_status()
                return {"content": [{"type": "text", "text": await response.atext()}]}

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"error": f"Tool call failed: {str(e)}"}

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Create a singleton instance with dynamic configuration
mcp_tool_client = MCPToolClient()
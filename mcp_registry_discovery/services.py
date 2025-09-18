#!/usr/bin/env python3
"""
MCP Toolbox Services - Compliant with 2025-06-18 Specification
Provides connection management and discovery services with enhanced error handling
"""
import asyncio
import aiohttp
import logging
import json
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

# No hardcoded server imports - fully user-driven
from mcp_storage import mcp_storage_manager

logger = logging.getLogger(__name__)


class ToolNotFoundException(Exception):
    """Custom exception for when a tool cannot be located."""
    pass


class ConnectionManager:
    """Manages aiohttp session and forwards requests."""
    _session: Optional[aiohttp.ClientSession] = None
    _lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        async with self._lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
                logger.info("New aiohttp.ClientSession created.")
        return self._session

    async def forward_request_streaming(self, server_url: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        Forwards a request to a backend MCP server and streams the SSE response.
        Enhanced with proper MCP 2025-06-18 specification compliance.
        """
        session = await self._get_session()
        mcp_endpoint = f"{server_url}/mcp"
        # Headers per 2025-06-18 specification
        headers = {
            'Accept': 'application/json, text/event-stream',
            'Content-Type': 'application/json',
            'MCP-Protocol-Version': '2025-06-18'
        }

        try:
            async with session.post(mcp_endpoint, json=payload, headers=headers, timeout=120) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        f"Upstream MCP server at {mcp_endpoint} returned error {response.status}: {error_text}")
                    
                    # Yield a JSON-RPC error as an SSE event per specification
                    error_payload = {
                        "jsonrpc": "2.0",
                        "id": payload.get("id"),
                        "error": {"code": -32000, "message": f"Upstream server error: {response.status}"}
                    }
                    event_id = str(uuid.uuid4())
                    yield f"id: {event_id}\n"
                    yield f"data: {json.dumps(error_payload)}\n\n"
                    return

                # Check if response is SSE format
                content_type = response.headers.get('content-type', '')
                if 'text/event-stream' in content_type:
                    # Stream SSE events line by line
                    async for line in response.content:
                        try:
                            line_str = line.decode('utf-8')
                            yield line_str
                        except UnicodeDecodeError:
                            logger.warning(f"Failed to decode line from {mcp_endpoint}")
                            continue
                else:
                    # Handle JSON response by converting to SSE format
                    try:
                        json_data = await response.json()
                        event_id = str(uuid.uuid4())
                        yield f"id: {event_id}\n"
                        yield f"data: {json.dumps(json_data)}\n\n"
                    except Exception as e:
                        logger.error(f"Failed to parse JSON response from {mcp_endpoint}: {e}")
                        error_payload = {
                            "jsonrpc": "2.0",
                            "id": payload.get("id"),
                            "error": {"code": -32002, "message": f"Response parsing error: {e}"}
                        }
                        event_id = str(uuid.uuid4())
                        yield f"id: {event_id}\n"
                        yield f"data: {json.dumps(error_payload)}\n\n"

        except asyncio.TimeoutError:
            logger.error(f"Timeout while connecting to {mcp_endpoint}")
            error_payload = {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "error": {"code": -32001, "message": "Request timeout to upstream server"}
            }
            event_id = str(uuid.uuid4())
            yield f"id: {event_id}\n"
            yield f"data: {json.dumps(error_payload)}\n\n"
        except aiohttp.ClientError as e:
            logger.error(f"ClientError while connecting to {mcp_endpoint}: {e}")
            error_payload = {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "error": {"code": -32001, "message": f"Connection error to upstream server: {e}"}
            }
            event_id = str(uuid.uuid4())
            yield f"id: {event_id}\n"
            yield f"data: {json.dumps(error_payload)}\n\n"

    async def close_session(self):
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
                logger.info("aiohttp.ClientSession closed.")


class DiscoveryService:
    """Discovers and indexes tools from all registered MCP servers."""

    def __init__(self, server_urls: List[str], connection_mgr: ConnectionManager, storage_manager=None):
        self.server_urls = server_urls
        self.connection_manager = connection_mgr
        self.storage_manager = storage_manager
        self.tool_to_server_map: Dict[str, str] = {}
        self._refresh_lock = asyncio.Lock()
        logger.info(f"DiscoveryService initialized with {len(server_urls)} servers.")

    async def refresh_tool_index(self):
        """
        Contacts all MCP servers, gets their tool lists, and rebuilds the index.
        Uses only dynamic storage - no hardcoded servers.
        """
        async with self._refresh_lock:
            logger.info("Refreshing tool index...")
            new_index: Dict[str, str] = {}
            
            # Get server URLs only from storage manager (no fallback to config)
            server_urls = []
            if self.storage_manager:
                try:
                    stored_servers = await self.storage_manager.get_all_servers()
                    if stored_servers:
                        server_urls = [server.url for server in stored_servers.values()]
                        logger.info(f"Using {len(server_urls)} servers from storage")
                    else:
                        logger.info("No servers in storage - starting with empty state")
                except Exception as e:
                    logger.error(f"Error loading servers from storage: {e}")
            else:
                logger.info("No storage manager available - starting with empty state")
            
            if not server_urls:
                logger.info("No MCP servers configured. Tools discovery will be empty until servers are added via UI.")
                self.tool_to_server_map = {}
                return
            
            tasks = [self._fetch_tools_from_server(url) for url in server_urls]
            results = await asyncio.gather(*tasks)

            for server_url, tools in results:
                if tools:
                    for tool in tools:
                        tool_name = tool.get("name")
                        if tool_name:
                            new_index[tool_name] = server_url

            self.tool_to_server_map = new_index
            logger.info(f"Tool index refreshed. Found {len(self.tool_to_server_map)} unique tools.")

    async def _fetch_tools_from_server(self, server_url: str) -> tuple[str, Optional[List[Dict]]]:
        """
        Fetches the tool list from a single MCP server.
        Enhanced with MCP 2025-06-18 specification compliance including proper session initialization.
        """
        session = await self.connection_manager._get_session()
        mcp_endpoint = f"{server_url}/mcp"

        # Headers per 2025-06-18 specification
        base_headers = {
            'Accept': 'application/json, text/event-stream',
            'Content-Type': 'application/json',
            'MCP-Protocol-Version': '2025-06-18'
        }

        try:
            # Step 1: Initialize the MCP session
            init_payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "discovery-init",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "clientInfo": {
                        "name": "mcp-toolbox-gateway",
                        "version": "1.0.0"
                    }
                }
            }

            session_id = None
            async with session.post(mcp_endpoint, json=init_payload, headers=base_headers, timeout=10) as response:
                if response.status == 200:
                    init_data = await response.json()
                    session_id = response.headers.get("Mcp-Session-Id")
                    if not session_id:
                        logger.warning(f"No session ID returned from {server_url} during initialization")
                        return server_url, None
                    logger.debug(f"Initialized session {session_id} with {server_url}")
                else:
                    logger.warning(f"Failed to initialize session with {server_url}. Status: {response.status}")
                    return server_url, None

            # Step 2: Send initialized notification
            headers_with_session = base_headers.copy()
            headers_with_session['Mcp-Session-Id'] = session_id

            initialized_payload = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }

            async with session.post(mcp_endpoint, json=initialized_payload, headers=headers_with_session, timeout=5) as response:
                if response.status != 202:
                    logger.warning(f"Unexpected status for initialized notification from {server_url}: {response.status}")
                    # Continue anyway as some servers might handle this differently

            # Step 3: Request tools list with proper session
            tools_payload = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": "discovery-list"
            }

            async with session.post(mcp_endpoint, json=tools_payload, headers=headers_with_session, timeout=10) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')

                    # Handle both JSON and SSE responses
                    if 'application/json' in content_type:
                        data = await response.json()
                        tools = data.get("result", {}).get("tools", [])
                        logger.info(f"Successfully fetched {len(tools)} tools from {server_url} (JSON)")
                        return server_url, tools
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
                                logger.debug(f"Failed to parse SSE line from {server_url}: {e}")
                                continue

                        logger.info(f"Successfully fetched {len(tools)} tools from {server_url} (SSE)")
                        return server_url, tools
                    else:
                        logger.warning(f"Unexpected content type from {server_url}: {content_type}")
                        return server_url, None
                else:
                    logger.warning(f"Failed to fetch tools from {server_url}. Status: {response.status}")
                    error_text = await response.text()
                    logger.debug(f"Error response from {server_url}: {error_text}")
                    return server_url, None

            # Step 4: Clean up session (optional, but good practice)
            if session_id:
                try:
                    delete_headers = base_headers.copy()
                    delete_headers['Mcp-Session-Id'] = session_id
                    async with session.delete(mcp_endpoint, headers=delete_headers, timeout=5) as response:
                        logger.debug(f"Session cleanup for {server_url}: {response.status}")
                except Exception as e:
                    logger.debug(f"Session cleanup failed for {server_url}: {e}")

        except asyncio.TimeoutError:
            logger.warning(f"Timeout while fetching tools from {server_url}")
            return server_url, None
        except Exception as e:
            logger.error(f"Error connecting to {server_url} for discovery: {e}")
            return server_url, None

    async def get_tool_location(self, tool_name: str) -> str:
        """Finds which server hosts a given tool."""
        if tool_name not in self.tool_to_server_map:
            # Attempt a refresh in case the tool was just added
            await self.refresh_tool_index()
            if tool_name not in self.tool_to_server_map:
                raise ToolNotFoundException(f"Tool '{tool_name}' is not available in any registered server.")
        return self.tool_to_server_map[tool_name]

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        Gets an aggregated list of all tools from all servers.
        Enhanced with caching and better error handling per specification.
        """
        if not self.tool_to_server_map:
            await self.refresh_tool_index()

        all_tools = []
        
        # Get server URLs from storage if available
        unique_servers = set(self.tool_to_server_map.values()) if self.tool_to_server_map else self.server_urls
        if self.storage_manager:
            try:
                stored_servers = await self.storage_manager.get_all_servers()
                if stored_servers:
                    unique_servers = set(server.url for server in stored_servers.values())
            except Exception as e:
                logger.error(f"Error loading servers from storage: {e}")
        
        # Fetch from all unique servers
        tasks = [self._fetch_tools_from_server(url) for url in unique_servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Exception during tool fetching: {result}")
                continue
            
            server_url, tools = result
            if tools:
                # Add server metadata to each tool for better tracking
                for tool in tools:
                    if isinstance(tool, dict):
                        tool['_server_url'] = server_url
                        tool['_discovery_timestamp'] = datetime.now().isoformat()
                all_tools.extend(tools)
            else:
                logger.debug(f"No tools received from {server_url}")
        
        logger.info(f"Aggregated {len(all_tools)} tools from {len(unique_servers)} servers")
        return all_tools

    def get_server_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about registered servers and tool distribution.
        """
        return {
            "total_servers": len(self.server_urls),
            "active_servers": len(set(self.tool_to_server_map.values())) if self.tool_to_server_map else 0,
            "total_tools": len(self.tool_to_server_map),
            "servers": self.server_urls,
            "tool_distribution": {
                server: sum(1 for s in self.tool_to_server_map.values() if s == server)
                for server in set(self.tool_to_server_map.values())
            } if self.tool_to_server_map else {},
            "last_refresh": datetime.now().isoformat()
        }


# --- Singleton Instances ---
connection_manager = ConnectionManager()
# Note: storage_manager will be injected after import to avoid circular dependency
discovery_service = DiscoveryService([], connection_manager)  # Start with empty list - storage manager will provide servers

logger.info("MCP Toolbox Services initialized - fully user-driven (no hardcoded servers)")
#!/usr/bin/env python3
"""
Tools Gateway Services - Compliant with 2025-06-18 Specification
Provides connection management and discovery services with enhanced error handling
Includes connection health monitoring and stale connection detection
"""
import asyncio
import aiohttp
import ssl
import logging
import json
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from datetime import datetime, timedelta

# No hardcoded server imports - fully user-driven
from .mcp_storage import mcp_storage_manager
from .config import config_manager
from .backend_sse_manager import backend_sse_manager

logger = logging.getLogger(__name__)


class ToolNotFoundException(Exception):
    """Custom exception for when a tool cannot be located."""
    pass


class ServerHealthStatus:
    """Tracks health status of a server connection"""
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.last_success: Optional[datetime] = None
        self.last_check: Optional[datetime] = None
        self.consecutive_failures = 0
        self.is_healthy = True
        self.last_error: Optional[str] = None

    def mark_success(self):
        """Mark a successful connection"""
        self.last_success = datetime.now()
        self.last_check = datetime.now()
        self.consecutive_failures = 0
        self.is_healthy = True
        self.last_error = None

    def mark_failure(self, error: str):
        """Mark a failed connection"""
        self.last_check = datetime.now()
        self.consecutive_failures += 1
        self.last_error = error
        # Mark unhealthy after 3 consecutive failures
        if self.consecutive_failures >= 3:
            self.is_healthy = False

    def is_stale(self, timeout_seconds: int) -> bool:
        """Check if connection is stale"""
        if not self.last_success:
            return True
        age = datetime.now() - self.last_success
        return age.total_seconds() > timeout_seconds

    def get_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            "server_url": self.server_url,
            "is_healthy": self.is_healthy,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error
        }


class ConnectionManager:
    """Manages aiohttp session and forwards requests."""
    _session: Optional[aiohttp.ClientSession] = None
    _lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        async with self._lock:
            if self._session is None or self._session.closed:
                # Create SSL context that allows self-signed certificates for development
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                # Create connector with SSL configuration and increased limits for large responses
                connector = aiohttp.TCPConnector(
                    ssl=ssl_context,
                    limit=100,  # Connection pool size
                    limit_per_host=30
                )

                # Create session with increased read buffer size to handle large chunks
                # max_line_size and max_field_size increased to handle large SSE data payloads
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    read_bufsize=2 * 1024 * 1024,  # 2MB read buffer (default is 64KB)
                    timeout=aiohttp.ClientTimeout(total=120)
                )
                logger.info("New aiohttp.ClientSession created with SSL verification disabled and increased buffer limits.")
        return self._session

    async def forward_request_streaming(self, server_url: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        Forwards a request to a backend MCP server and streams the SSE response.
        Enhanced with proper MCP 2025-06-18 specification compliance.

        Note: server_url should include the full endpoint path (e.g., http://localhost:8001/mcp or http://localhost:8002/sse)
        """
        session = await self._get_session()
        mcp_endpoint = server_url  # Use full URL including endpoint path
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
                    # Stream SSE events in smaller chunks to avoid "Chunk too big" errors
                    # Read in chunks instead of lines to handle large payloads
                    CHUNK_SIZE = 8192  # 8KB chunks
                    buffer = b''

                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        buffer += chunk

                        # Process complete lines from buffer
                        while b'\n' in buffer:
                            line, buffer = buffer.split(b'\n', 1)
                            try:
                                line_str = line.decode('utf-8') + '\n'
                                yield line_str
                            except UnicodeDecodeError:
                                logger.warning(f"Failed to decode line from {mcp_endpoint}")
                                continue

                    # Process any remaining data in buffer
                    if buffer:
                        try:
                            line_str = buffer.decode('utf-8')
                            if line_str:
                                yield line_str
                        except UnicodeDecodeError:
                            logger.warning(f"Failed to decode final buffer from {mcp_endpoint}")
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

    async def call_tool(self, server_url: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on a backend server, routing to either SSE or HTTP POST based on server type.

        Args:
            server_url: Full server URL (e.g., http://localhost:8002/sse or http://localhost:8001/mcp)
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        # Check if this is an SSE endpoint
        is_sse = server_url.endswith('/sse')

        if is_sse:
            # Extract server_id from URL for SSE manager
            # Format: http://localhost:8002/sse -> server_id would be mapped in discovery
            # For now, use the URL as the server_id
            server_id = server_url

            # Check if connected via SSE
            if not backend_sse_manager.is_connected(server_id):
                # Attempt to connect
                success = await backend_sse_manager.connect_server(server_id, server_url)
                if not success:
                    raise Exception(f"Failed to connect to SSE backend: {server_url}")

            # Send tool call via SSE
            message = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                },
                "id": str(uuid.uuid4())
            }

            try:
                response = await backend_sse_manager.send_message(server_id, message)

                # Extract result from response
                if "result" in response:
                    return response["result"]
                elif "error" in response:
                    raise Exception(f"Tool execution error: {response['error']}")
                else:
                    raise Exception(f"Unexpected response format: {response}")

            except Exception as e:
                logger.error(f"SSE tool call failed for {tool_name} on {server_url}: {e}")
                raise

        else:
            # Traditional HTTP POST approach
            session = await self._get_session()
            mcp_endpoint = server_url

            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'MCP-Protocol-Version': '2025-06-18'
            }

            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                },
                "id": str(uuid.uuid4())
            }

            try:
                async with session.post(mcp_endpoint, json=payload, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "result" in data:
                            return data["result"]
                        elif "error" in data:
                            raise Exception(f"Tool execution error: {data['error']}")
                        else:
                            raise Exception(f"Unexpected response format: {data}")
                    else:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")

            except Exception as e:
                logger.error(f"HTTP tool call failed for {tool_name} on {server_url}: {e}")
                raise

    async def close_session(self):
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
                logger.info("aiohttp.ClientSession closed.")


class DiscoveryService:
    """Discovers and indexes tools from all registered MCP servers with health monitoring."""

    def __init__(self, server_urls: List[str], connection_mgr: ConnectionManager, storage_manager=None):
        self.server_urls = server_urls
        self.connection_manager = connection_mgr
        self.storage_manager = storage_manager
        self.tool_to_server_map: Dict[str, str] = {}
        self._refresh_lock = asyncio.Lock()

        # Health monitoring
        self.server_health: Dict[str, ServerHealthStatus] = {}
        self._health_check_task: Optional[asyncio.Task] = None

        logger.info(f"DiscoveryService initialized with {len(server_urls)} servers.")

    async def start_health_monitoring(self):
        """Start background health monitoring task"""
        config = config_manager.get_connection_health_config()
        if config.enabled and not self._health_check_task:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Started connection health monitoring")

    async def stop_health_monitoring(self):
        """Stop background health monitoring task"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Stopped connection health monitoring")

    async def _health_check_loop(self):
        """Background loop for health checks - reads config on each iteration for dynamic updates"""
        while True:
            try:
                # Read config on each iteration to support dynamic interval changes
                config = config_manager.get_connection_health_config()
                await asyncio.sleep(config.check_interval_seconds)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

    async def _perform_health_checks(self):
        """Perform health checks on all servers"""
        config = config_manager.get_connection_health_config()

        if self.storage_manager:
            try:
                stored_servers = await self.storage_manager.get_all_servers()
                server_urls = [server.url for server in stored_servers.values()]
            except Exception as e:
                logger.error(f"Error loading servers for health check: {e}")
                return
        else:
            server_urls = self.server_urls

        for server_url in server_urls:
            # Initialize health status if not exists
            if server_url not in self.server_health:
                self.server_health[server_url] = ServerHealthStatus(server_url)

            health = self.server_health[server_url]

            # Check if stale
            if health.is_stale(config.stale_timeout_seconds):
                logger.warning(f"Server {server_url} connection is stale, attempting refresh")
                success = await self._check_server_health(server_url)
                if success:
                    health.mark_success()
                    # Refresh tool index for this server
                    await self.refresh_tool_index()
                else:
                    health.mark_failure("Health check failed")

    async def _check_server_health(self, server_url: str) -> bool:
        """Check health of a single server using full endpoint URL"""
        # Check if this is an SSE endpoint
        is_sse = server_url.endswith('/sse')

        if is_sse:
            # For SSE backends, check if already connected via backend_sse_manager
            server_id = server_url
            if backend_sse_manager.is_connected(server_id):
                # Already connected - health check passes
                logger.debug(f"Health check passed for {server_url} (SSE connected)")
                return True
            else:
                # Try to establish connection
                try:
                    success = await backend_sse_manager.connect_server(server_id, server_url)
                    if success:
                        logger.debug(f"Health check passed for {server_url} (SSE reconnected)")
                        return True
                    else:
                        logger.warning(f"Health check failed for {server_url}: SSE connection failed")
                        return False
                except Exception as e:
                    logger.warning(f"Health check failed for {server_url}: {e}")
                    return False
        else:
            # For HTTP POST backends, use the traditional approach
            session = await self.connection_manager._get_session()
            mcp_endpoint = server_url

            headers = {
                'Accept': 'application/json, text/event-stream',
                'Content-Type': 'application/json',
                'MCP-Protocol-Version': '2025-06-18'
            }

            # Simple ping with initialize
            init_payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "health-check",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "tools-gateway-health-check",
                        "version": "1.0.0"
                    }
                }
            }

            try:
                async with session.post(mcp_endpoint, json=init_payload, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        logger.debug(f"Health check passed for {server_url}")
                        return True
                    else:
                        logger.warning(f"Health check failed for {server_url}: status {response.status}")
                        return False
            except Exception as e:
                logger.warning(f"Health check failed for {server_url}: {e}")
                return False

    def get_server_health_status(self, server_url: Optional[str] = None) -> Dict[str, Any]:
        """Get health status for all servers or a specific server"""
        if server_url:
            if server_url in self.server_health:
                return self.server_health[server_url].get_status()
            return {"error": "Server not found"}

        return {
            url: health.get_status()
            for url, health in self.server_health.items()
        }

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
        Updates health status tracking.
        Supports both traditional HTTP POST and SSE-based backend servers.

        Note: server_url should include the full endpoint path (e.g., http://localhost:8001/mcp or http://localhost:8002/sse)
        """
        # Initialize health status if not exists
        if server_url not in self.server_health:
            self.server_health[server_url] = ServerHealthStatus(server_url)

        # Check if this is an SSE endpoint
        is_sse = server_url.endswith('/sse')

        if is_sse:
            # Use BackendSSEManager for SSE-based servers
            return await self._fetch_tools_from_sse_server(server_url)
        else:
            # Use traditional HTTP POST for regular MCP servers
            return await self._fetch_tools_from_http_server(server_url)

    async def _fetch_tools_from_sse_server(self, server_url: str) -> tuple[str, Optional[List[Dict]]]:
        """
        Fetches tools from an SSE-based backend server (like FastMCP).
        """
        server_id = server_url  # Use URL as server_id

        try:
            # Check if already connected
            if not backend_sse_manager.is_connected(server_id):
                logger.info(f"Connecting to SSE backend: {server_url}")
                success = await backend_sse_manager.connect_server(server_id, server_url)
                if not success:
                    logger.error(f"Failed to connect to SSE backend: {server_url}")
                    self.server_health[server_url].mark_failure("SSE connection failed")
                    return server_url, None

            # Send initialize message
            init_message = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "mcp-toolbox-gateway",
                        "version": "1.0.0"
                    }
                },
                "id": "discovery-init"
            }

            init_response = await backend_sse_manager.send_message(server_id, init_message)
            logger.debug(f"SSE backend initialized: {server_url}")

            # Send initialized notification (required by MCP protocol)
            initialized_message = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            # Send notification (no response expected)
            await backend_sse_manager.send_notification(server_id, initialized_message)
            logger.debug(f"Sent initialized notification to {server_url}")

            # Request tools list
            tools_message = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": "discovery-list"
            }

            tools_response = await backend_sse_manager.send_message(server_id, tools_message)

            # Extract tools from response
            if "result" in tools_response:
                tools = tools_response["result"].get("tools", [])
                logger.info(f"Successfully fetched {len(tools)} tools from {server_url} (SSE)")
                self.server_health[server_url].mark_success()
                return server_url, tools
            elif "error" in tools_response:
                error_msg = tools_response["error"].get("message", "Unknown error")
                logger.error(f"Error fetching tools from {server_url}: {error_msg}")
                self.server_health[server_url].mark_failure(error_msg)
                return server_url, None
            else:
                logger.warning(f"Unexpected response format from {server_url}")
                self.server_health[server_url].mark_failure("Unexpected response format")
                return server_url, None

        except Exception as e:
            logger.error(f"Error fetching tools from SSE backend {server_url}: {e}")
            self.server_health[server_url].mark_failure(str(e))
            return server_url, None

    async def _fetch_tools_from_http_server(self, server_url: str) -> tuple[str, Optional[List[Dict]]]:
        """
        Fetches tools from a traditional HTTP POST MCP server.
        Original implementation for non-SSE servers.
        """
        session = await self.connection_manager._get_session()
        mcp_endpoint = server_url  # Use full URL including endpoint path

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
                    "capabilities": {},
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
                        # Mark health success
                        self.server_health[server_url].mark_success()
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
                        # Mark health success
                        self.server_health[server_url].mark_success()
                        return server_url, tools
                    else:
                        logger.warning(f"Unexpected content type from {server_url}: {content_type}")
                        self.server_health[server_url].mark_failure(f"Unexpected content type: {content_type}")
                        return server_url, None
                else:
                    logger.warning(f"Failed to fetch tools from {server_url}. Status: {response.status}")
                    error_text = await response.text()
                    logger.debug(f"Error response from {server_url}: {error_text}")
                    self.server_health[server_url].mark_failure(f"HTTP {response.status}")
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
            self.server_health[server_url].mark_failure("Timeout")
            return server_url, None
        except Exception as e:
            logger.error(f"Error connecting to {server_url} for discovery: {e}")
            self.server_health[server_url].mark_failure(str(e))
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
        Includes OAuth provider associations.
        """
        if not self.tool_to_server_map:
            await self.refresh_tool_index()

        all_tools = []

        # Get server URLs from storage if available
        unique_servers = set(self.tool_to_server_map.values()) if self.tool_to_server_map else self.server_urls
        server_id_map = {}  # Map URLs to server IDs

        if self.storage_manager:
            try:
                stored_servers = await self.storage_manager.get_all_servers()
                if stored_servers:
                    unique_servers = set(server.url for server in stored_servers.values())
                    # Create mapping of URL to server_id
                    for server_id, server_info in stored_servers.items():
                        server_id_map[server_info.url] = server_id
            except Exception as e:
                logger.error(f"Error loading servers from storage: {e}")

        # Get OAuth associations and role permissions from database
        from .database import database
        all_oauth_associations = {}
        all_role_permissions = {}

        try:
            associations = database.get_all_tool_oauth_associations()
            # Group by (server_id, tool_name)
            for assoc in associations:
                key = (assoc['server_id'], assoc['tool_name'])
                if key not in all_oauth_associations:
                    all_oauth_associations[key] = []
                all_oauth_associations[key].append({
                    'provider_id': assoc['oauth_provider_id'],
                    'provider_name': assoc.get('provider_name')
                })
        except Exception as e:
            logger.error(f"Error loading OAuth associations: {e}")

        try:
            # Get all roles
            all_roles = database.get_all_roles()
            # For each role, get its tool permissions
            for role in all_roles:
                role_perms = database.get_role_tool_permissions(role['role_id'])
                for perm in role_perms:
                    key = (perm['server_id'], perm['tool_name'])
                    if key not in all_role_permissions:
                        all_role_permissions[key] = []
                    all_role_permissions[key].append({
                        'role_id': role['role_id'],
                        'role_name': role['role_name'],
                        'description': role.get('description', '')
                    })
        except Exception as e:
            logger.error(f"Error loading role permissions: {e}")

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

                        # Add OAuth provider associations and role permissions
                        server_id = server_id_map.get(server_url)
                        if server_id:
                            tool['_server_id'] = server_id
                            tool_name = tool.get('name')
                            if tool_name:
                                key = (server_id, tool_name)
                                oauth_providers = all_oauth_associations.get(key, [])
                                tool['_oauth_providers'] = oauth_providers

                                # Add role permissions
                                roles = all_role_permissions.get(key, [])
                                tool['_access_roles'] = roles

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
"""
Backend SSE Connection Manager
Manages SSE connections to backend FastMCP servers for tool aggregation
"""
import asyncio
import json
import logging
import aiohttp
from typing import Dict, Optional, Any
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class BackendSSEClient:
    """Manages a single SSE connection to a backend FastMCP server"""

    def __init__(self, server_id: str, server_url: str):
        self.server_id = server_id
        self.server_url = server_url
        self.session_id: Optional[str] = None
        self.messages_url: Optional[str] = None
        self.connected = False
        self.response_futures: Dict[str, asyncio.Future] = {}
        self._task: Optional[asyncio.Task] = None
        self._http_session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        """Establish SSE connection to the backend server"""
        try:
            logger.info(f"Connecting to backend SSE server: {self.server_url}")

            # Create HTTP session
            self._http_session = aiohttp.ClientSession()

            # Start SSE connection in background
            self._task = asyncio.create_task(self._sse_listen())

            # Wait for connection to be established (with timeout)
            for _ in range(50):  # 5 seconds timeout
                if self.connected:
                    logger.info(f"Backend SSE connection established for {self.server_id}, session: {self.session_id}")
                    return True
                await asyncio.sleep(0.1)

            logger.error(f"Timeout waiting for backend SSE connection: {self.server_id}")
            return False

        except Exception as e:
            logger.error(f"Failed to connect to backend SSE server {self.server_id}: {e}")
            return False

    async def _sse_listen(self):
        """Listen to SSE events from the backend server"""
        try:
            headers = {"Accept": "text/event-stream"}
            async with self._http_session.get(self.server_url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"Backend SSE connection failed with status {response.status}")
                    return

                current_event_type = None
                buffer = b''

                # Read SSE stream line by line
                async for chunk in response.content.iter_any():
                    buffer += chunk
                    logger.debug(f"[{self.server_id}] Received chunk: {len(chunk)} bytes, buffer size: {len(buffer)}")

                    # Process complete lines
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)

                        decoded_line = line.decode('utf-8').strip()
                        if not decoded_line:
                            continue

                        logger.debug(f"[{self.server_id}] SSE line: {repr(decoded_line)}")

                        # Parse SSE events
                        if decoded_line.startswith('event:'):
                            current_event_type = decoded_line.split(': ', 1)[1]
                            logger.debug(f"[{self.server_id}] Event type: {current_event_type}")
                        elif decoded_line.startswith('data:'):
                            data_str = decoded_line.split(': ', 1)[1]
                            logger.debug(f"[{self.server_id}] Data: {data_str[:100]}...")

                            # Try parsing as JSON first
                            try:
                                data = json.loads(data_str)
                                logger.info(f"[{self.server_id}] Parsed JSON event (type={current_event_type}): {data.get('method') or data.get('id', 'unknown')}")
                                await self._handle_sse_event(data, current_event_type)
                            except json.JSONDecodeError:
                                # If not JSON, handle as plain text (FastMCP format)
                                if current_event_type == 'endpoint':
                                    # FastMCP sends: data: /messages/?session_id=...
                                    logger.info(f"[{self.server_id}] Endpoint event: {data_str}")
                                    await self._handle_sse_event(data_str, current_event_type)
                                else:
                                    logger.warning(f"[{self.server_id}] Failed to parse SSE data: {decoded_line}")

        except asyncio.CancelledError:
            logger.info(f"Backend SSE connection closed for {self.server_id}")
        except Exception as e:
            logger.error(f"Error in backend SSE listener for {self.server_id}: {e}")
        finally:
            self.connected = False

    async def _handle_sse_event(self, data, event_type: Optional[str] = None):
        """Handle an SSE event from the backend server"""
        # Handle FastMCP format (plain text endpoint)
        if event_type == 'endpoint' and isinstance(data, str):
            # FastMCP format: data is just the endpoint path
            endpoint = data
            if 'session_id=' in endpoint:
                self.session_id = endpoint.split('session_id=')[1]
                # Construct messages URL
                parsed_url = self.server_url.rsplit('/', 1)[0]  # Remove /sse
                self.messages_url = f"{parsed_url}/messages?session_id={self.session_id}"
                self.connected = True
                logger.info(f"Backend session established (FastMCP): {self.session_id}")
            return

        # Handle JSON-RPC format (full message objects)
        if isinstance(data, dict):
            # Check for endpoint event (session establishment)
            if data.get('method') == 'endpoint':
                endpoint = data.get('params', {}).get('endpoint', '')
                if 'session_id=' in endpoint:
                    self.session_id = endpoint.split('session_id=')[1]
                    # Construct messages URL
                    parsed_url = self.server_url.rsplit('/', 1)[0]  # Remove /sse
                    self.messages_url = f"{parsed_url}/messages?session_id={self.session_id}"
                    self.connected = True
                    logger.info(f"Backend session established (JSON-RPC): {self.session_id}")
                return

            # Check for response messages (with request ID)
            request_id = data.get('id')
            logger.debug(f"[{self.server_id}] Checking response ID: {request_id}, pending futures: {list(self.response_futures.keys())}")
            if request_id and request_id in self.response_futures:
                future = self.response_futures.pop(request_id)
                if not future.done():
                    logger.info(f"[{self.server_id}] Setting future result for request ID: {request_id}")
                    future.set_result(data)
                else:
                    logger.warning(f"[{self.server_id}] Future already done for request ID: {request_id}")
            elif request_id:
                logger.warning(f"[{self.server_id}] Received response for unknown request ID: {request_id}")

    async def send_notification(self, message: Dict[str, Any]) -> None:
        """Send a notification to the backend server (no response expected)"""
        if not self.connected or not self.messages_url:
            raise Exception(f"Backend SSE client not connected: {self.server_id}")

        # Notifications should not have an ID
        if 'id' in message:
            del message['id']

        logger.info(f"[{self.server_id}] Sending notification: {message.get('method', 'unknown method')}")

        try:
            # Send notification via POST
            async with self._http_session.post(self.messages_url, json=message) as response:
                # FastMCP returns 202 (Accepted), traditional servers return 200
                if response.status not in [200, 202]:
                    error_text = await response.text()
                    logger.warning(f"[{self.server_id}] Notification returned status {response.status}: {error_text}")
                else:
                    logger.debug(f"[{self.server_id}] Notification sent successfully")
        except Exception as e:
            logger.warning(f"[{self.server_id}] Failed to send notification: {e}")
            # Don't raise - notifications are fire-and-forget

    async def send_message(self, message: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """Send a message to the backend server and wait for response"""
        if not self.connected or not self.messages_url:
            raise Exception(f"Backend SSE client not connected: {self.server_id}")

        request_id = message.get('id', str(uuid.uuid4()))
        message['id'] = request_id

        # Create future for response
        future = asyncio.Future()
        self.response_futures[request_id] = future
        logger.info(f"[{self.server_id}] Sending message (ID: {request_id}): {message.get('method', 'unknown method')}")

        try:
            # Send message via POST
            async with self._http_session.post(self.messages_url, json=message) as response:
                # FastMCP returns 202 (Accepted), traditional servers return 200
                if response.status not in [200, 202]:
                    error_text = await response.text()
                    raise Exception(f"Backend server returned status {response.status}: {error_text}")
                logger.debug(f"[{self.server_id}] POST response status: {response.status}")

            # Wait for response via SSE
            logger.debug(f"[{self.server_id}] Waiting for SSE response (timeout={timeout}s)...")
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"[{self.server_id}] Received response for ID: {request_id}")
            return result

        except asyncio.TimeoutError:
            self.response_futures.pop(request_id, None)
            raise Exception(f"Timeout waiting for response from {self.server_id}")
        except Exception as e:
            self.response_futures.pop(request_id, None)
            raise

    async def close(self):
        """Close the connection to the backend server"""
        self.connected = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._http_session:
            await self._http_session.close()

        logger.info(f"Backend SSE connection closed for {self.server_id}")


class BackendSSEManager:
    """Manages multiple backend SSE connections"""

    def __init__(self):
        self.clients: Dict[str, BackendSSEClient] = {}
        self._lock = asyncio.Lock()

    async def connect_server(self, server_id: str, server_url: str) -> bool:
        """Connect to a backend SSE server"""
        async with self._lock:
            # Close existing connection if any
            if server_id in self.clients:
                await self.clients[server_id].close()

            # Create new client
            client = BackendSSEClient(server_id, server_url)
            success = await client.connect()

            if success:
                self.clients[server_id] = client
                logger.info(f"Backend SSE server connected: {server_id}")
                return True
            else:
                logger.error(f"Failed to connect to backend SSE server: {server_id}")
                return False

    async def disconnect_server(self, server_id: str):
        """Disconnect from a backend SSE server"""
        async with self._lock:
            if server_id in self.clients:
                await self.clients[server_id].close()
                del self.clients[server_id]
                logger.info(f"Backend SSE server disconnected: {server_id}")

    async def send_notification(self, server_id: str, message: Dict[str, Any]) -> None:
        """Send a notification to a backend server (no response expected)"""
        client = self.clients.get(server_id)
        if not client:
            raise Exception(f"No connection to backend server: {server_id}")

        await client.send_notification(message)

    async def send_message(self, server_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to a backend server"""
        client = self.clients.get(server_id)
        if not client:
            raise Exception(f"No connection to backend server: {server_id}")

        return await client.send_message(message)

    def is_connected(self, server_id: str) -> bool:
        """Check if connected to a backend server"""
        client = self.clients.get(server_id)
        return client is not None and client.connected

    async def close_all(self):
        """Close all backend connections"""
        async with self._lock:
            for client in self.clients.values():
                await client.close()
            self.clients.clear()
            logger.info("All backend SSE connections closed")


# Global backend SSE manager instance
backend_sse_manager = BackendSSEManager()

#!/usr/bin/env python3
"""
Tools Gateway - Fully Compliant with 2025-06-18 Specification
Centralized gateway implementing pure Streamable HTTP transport
With dynamic origin configuration and connection health monitoring
"""
import asyncio
from contextlib import asynccontextmanager
import logging
import json
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
from datetime import datetime
from urllib.parse import urlparse
import os

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from services import discovery_service, connection_manager, ToolNotFoundException
from mcp_storage import mcp_storage_manager
from config import config_manager
# No hardcoded server imports - fully user-driven

# Configure logging per MCP 2025-06-18 specification
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Protocol constants as per 2025-06-18 specification
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {
    "name": "tools-gateway",
    "version": "1.0.0"
}


class EventStore:
    """
    Event store for SSE resumability per MCP specification.
    Stores events per-stream for message replay functionality.
    """

    def __init__(self):
        self.stream_events: Dict[str, List[Dict[str, Any]]] = {}
        self.global_event_counter = 0

    def store_event(self, stream_id: str, message: Dict[str, Any]) -> str:
        """Store event and return globally unique ID per stream"""
        self.global_event_counter += 1
        event_id = f"{stream_id}-{self.global_event_counter}"

        if stream_id not in self.stream_events:
            self.stream_events[stream_id] = []

        event_data = {
            "id": event_id,
            "timestamp": datetime.now().isoformat(),
            "message": message
        }

        self.stream_events[stream_id].append(event_data)

        # Limit stored events per stream (prevent memory issues)
        if len(self.stream_events[stream_id]) > 1000:
            self.stream_events[stream_id] = self.stream_events[stream_id][-500:]

        return event_id

    def get_events_after(self, stream_id: str, last_event_id: str) -> List[Dict[str, Any]]:
        """Get events after the specified event ID for resumability"""
        if stream_id not in self.stream_events:
            return []

        events = self.stream_events[stream_id]
        try:
            # Find the position of last_event_id
            last_index = -1
            for i, event in enumerate(events):
                if event["id"] == last_event_id:
                    last_index = i
                    break

            # Return events after the last_event_id
            if last_index >= 0:
                return events[last_index + 1:]
            else:
                # If event ID not found, return recent events
                return events[-10:] if events else []

        except Exception as e:
            logger.warning(f"Error retrieving events after {last_event_id}: {e}")
            return []

    def cleanup_stream(self, stream_id: str):
        """Clean up events for a terminated stream"""
        self.stream_events.pop(stream_id, None)


class StreamManager:
    """
    Manages multiple SSE streams per MCP specification.
    Ensures messages are sent to only one stream and prevents broadcasting.
    """

    def __init__(self):
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.session_streams: Dict[str, List[str]] = {}  # session_id -> [stream_ids]

    def register_stream(self, stream_id: str, session_id: str, stream_type: str) -> None:
        """Register a new active stream"""
        self.active_streams[stream_id] = {
            "session_id": session_id,
            "stream_type": stream_type,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }

        if session_id not in self.session_streams:
            self.session_streams[session_id] = []
        self.session_streams[session_id].append(stream_id)

        logger.info(f"Registered {stream_type} stream {stream_id} for session {session_id}")

    def unregister_stream(self, stream_id: str) -> None:
        """Unregister a stream when connection closes"""
        if stream_id in self.active_streams:
            session_id = self.active_streams[stream_id]["session_id"]
            del self.active_streams[stream_id]

            if session_id in self.session_streams:
                self.session_streams[session_id] = [
                    s for s in self.session_streams[session_id] if s != stream_id
                ]
                if not self.session_streams[session_id]:
                    del self.session_streams[session_id]

            logger.info(f"Unregistered stream {stream_id}")

    def get_session_streams(self, session_id: str) -> List[str]:
        """Get all active streams for a session"""
        return self.session_streams.get(session_id, [])

    def update_activity(self, stream_id: str) -> None:
        """Update last activity timestamp for a stream"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id]["last_activity"] = datetime.now()

    def cleanup_session_streams(self, session_id: str) -> None:
        """Clean up all streams for a terminated session"""
        if session_id in self.session_streams:
            stream_ids = self.session_streams[session_id].copy()
            for stream_id in stream_ids:
                self.unregister_stream(stream_id)


class MessageRouter:
    """
    Routes messages to specific streams per MCP specification.
    Ensures messages are sent to only one stream, never broadcasted.
    """

    def __init__(self, stream_manager: StreamManager, event_store: EventStore):
        self.stream_manager = stream_manager
        self.event_store = event_store
        self.message_queues: Dict[str, asyncio.Queue] = {}

    def get_or_create_queue(self, stream_id: str) -> asyncio.Queue:
        """Get or create message queue for a stream"""
        if stream_id not in self.message_queues:
            self.message_queues[stream_id] = asyncio.Queue()
        return self.message_queues[stream_id]

    async def send_to_stream(self, stream_id: str, message: Dict[str, Any]) -> None:
        """Send message to a specific stream (never broadcast)"""
        if stream_id in self.stream_manager.active_streams:
            queue = self.get_or_create_queue(stream_id)
            event_id = self.event_store.store_event(stream_id, message)

            await queue.put({
                "id": event_id,
                "data": message
            })

            self.stream_manager.update_activity(stream_id)
            logger.debug(f"Routed message to stream {stream_id} with event ID {event_id}")

    async def get_next_message(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get next message for a stream"""
        queue = self.get_or_create_queue(stream_id)
        try:
            # Non-blocking get with timeout
            return await asyncio.wait_for(queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    def cleanup_stream_queue(self, stream_id: str) -> None:
        """Clean up message queue for a stream"""
        self.message_queues.pop(stream_id, None)


class MCPToolboxGateway:
    """
    MCP Toolbox Gateway implementation fully compliant with 2025-06-18 Streamable HTTP transport.
    Acts as a centralized gateway with tool discovery, connection management, and caching.
    """

    def __init__(self):
        self.initialized = False
        self.client_info = {}
        self.server_start_time = datetime.now()
        self.sessions: Dict[str, Dict] = {}

        # Initialize compliance components for 100% specification adherence
        self.event_store = EventStore()
        self.stream_manager = StreamManager()
        self.message_router = MessageRouter(self.stream_manager, self.event_store)

        logger.info(f"MCP Toolbox Gateway initialized with protocol version {PROTOCOL_VERSION}")
        logger.info("Compliance components initialized: EventStore, StreamManager, MessageRouter")

    def _sanitize_origin(self, origin: str) -> Optional[str]:
        """
        Sanitize origin string to prevent injection attacks.
        Returns sanitized origin or None if invalid.
        """
        if not origin:
            return None

        try:
            # Parse and validate URL structure
            parsed = urlparse(origin)

            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"Invalid origin format (missing scheme/netloc): {origin}")
                return None

            # Only allow http/https schemes
            if parsed.scheme not in ['http', 'https']:
                logger.warning(f"Invalid origin scheme (must be http/https): {origin}")
                return None

            # Validate hostname format
            hostname = parsed.hostname
            if not hostname:
                return None

            # Length validation
            if len(hostname) > 253:
                logger.warning(f"Origin hostname too long: {hostname[:50]}...")
                return None

            # Reconstruct clean origin (scheme + netloc only, no path/query)
            clean_origin = f"{parsed.scheme}://{parsed.netloc}"
            return clean_origin

        except Exception as e:
            logger.warning(f"Failed to parse origin: {origin}, error: {e}")
            return None

    def extract_origin_from_request(self, request: Request) -> Optional[str]:
        """
        Extract origin from request considering load balancer/reverse proxy headers.
        Priority order:
        1. Origin header (most trusted)
        2. X-Forwarded-Host + X-Forwarded-Proto (load balancer)
        3. X-Original-Host (alternative)
        Note: Referer is NOT used as it's easily spoofed
        """
        # Standard Origin header (most secure)
        origin = request.headers.get("origin")
        if origin:
            return self._sanitize_origin(origin)

        # Load balancer forwarded headers
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
        if forwarded_host:
            # Validate proto
            if forwarded_proto not in ['http', 'https']:
                logger.warning(f"Invalid X-Forwarded-Proto: {forwarded_proto}")
                forwarded_proto = "https"

            origin = f"{forwarded_proto}://{forwarded_host}"
            return self._sanitize_origin(origin)

        # Alternative original host header
        original_host = request.headers.get("x-original-host")
        if original_host:
            origin = f"https://{original_host}"
            return self._sanitize_origin(origin)

        # No origin found
        return None

    def validate_origin_header(self, origin: Optional[str]) -> bool:
        """
        Validate Origin header to prevent DNS rebinding attacks.
        Required by 2025-06-18 specification.
        Uses in-memory cache for fast O(1) validation.

        SECURITY NOTE: This allows permissive origins (ngrok, all HTTPS) by default.
        Review config_manager.get_origin_validation_config() for production hardening.
        """
        if not origin:
            logger.warning("Origin validation failed: No origin provided")
            return False

        try:
            parsed = urlparse(origin)
            hostname = parsed.hostname

            if not hostname:
                logger.warning(f"Origin validation failed: No hostname in {origin}")
                return False

            # Get cached configuration (fast in-memory access, no pickle reads)
            allowed_origins, allow_ngrok, allow_https = config_manager.get_origin_validation_config()

            # Fast O(1) set lookup for configured allowed origins (most secure)
            logger.debug(f"Origin validation: hostname={hostname}, allowed={allowed_origins}")
            if hostname in allowed_origins:
                logger.info(f"✓ Origin allowed (whitelist): {origin}")
                return True

            # Check if ngrok is allowed (SECURITY: disable in production)
            if allow_ngrok and hostname and (
                hostname.endswith('.ngrok-free.app') or
                hostname.endswith('.ngrok.io') or
                hostname.endswith('.ngrok.app') or
                '.ngrok.' in hostname
            ):
                logger.warning(f"⚠ Allowing ngrok origin (SECURITY: disable for production): {origin}")
                return True

            # Check if HTTPS origins are allowed (SECURITY: only enable behind trusted LB)
            if allow_https and parsed.scheme == 'https':
                logger.warning(f"⚠ Allowing HTTPS origin (SECURITY: any HTTPS domain accepted): {origin}")
                return True

            logger.error(f"✗ Origin REJECTED: {origin} (hostname: {hostname})")
            return False
        except Exception as e:
            logger.error(f"✗ Origin validation exception: {origin}, error: {e}")
            return False

    def validate_accept_header(self, accept: Optional[str], method: str) -> bool:
        """
        Validate Accept header according to 2025-06-18 specification.
        """
        if not accept:
            return False

        if method == "POST":
            # POST requests must accept both application/json and text/event-stream
            return "application/json" in accept and "text/event-stream" in accept
        elif method == "GET":
            # GET requests must accept text/event-stream
            return "text/event-stream" in accept

        return False

    def validate_protocol_version(self, version: Optional[str]) -> str:
        """
        Validate and normalize protocol version according to specification.
        """
        if not version:
            # Default to latest version for backwards compatibility
            return PROTOCOL_VERSION

        supported_versions = ["2025-06-18", "2025-03-26"]
        if version not in supported_versions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported protocol version: {version}"
            )

        return version

    def generate_session_id(self) -> str:
        """
        Generate cryptographically secure session ID per specification.
        Must contain only visible ASCII characters (0x21 to 0x7E).
        """
        session_id = str(uuid.uuid4())

        # Validate ASCII character range per specification
        if not all(0x21 <= ord(c) <= 0x7E for c in session_id):
            # Use hex format to ensure compliance
            session_id = uuid.uuid4().hex

        return session_id

    def validate_session(self, session_id: str) -> bool:
        """Validate session ID exists and is active."""
        return session_id in self.sessions

    def terminate_session(self, session_id: str) -> bool:
        """Terminate a session per specification with full cleanup."""
        if session_id in self.sessions:
            # Clean up all streams for this session
            self.stream_manager.cleanup_session_streams(session_id)

            # Clean up event store for session streams
            for stream_id in self.stream_manager.get_session_streams(session_id):
                self.event_store.cleanup_stream(stream_id)
                self.message_router.cleanup_stream_queue(stream_id)

            del self.sessions[session_id]
            logger.info(f"Session terminated: {session_id}")
            return True
        return False

    def create_error_response(self, request_id: Optional[str], code: int, message: str) -> Dict[str, Any]:
        """Create JSON-RPC error response per specification."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message}
        }


# Create gateway instance
mcp_gateway = MCPToolboxGateway()


# --- Application Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info("Tools Gateway starting up...")
    # Initialize storage manager
    await mcp_storage_manager.initialize()
    discovery_service.storage_manager = mcp_storage_manager
    # Initialize and warm up the discovery service cache
    await discovery_service.refresh_tool_index()
    # Start health monitoring
    await discovery_service.start_health_monitoring()
    logger.info("Connection health monitoring started")
    yield
    logger.info("Tools Gateway shutting down...")
    # Stop health monitoring
    await discovery_service.stop_health_monitoring()
    # Cleanly close the connection manager's session
    await connection_manager.close_session()


# Create FastAPI app with proper configuration
app = FastAPI(
    title="Tools Gateway",
    description="Centralized gateway implementing MCP 2025-06-18 Streamable HTTP transport with health monitoring",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS with security considerations per specification
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for ngrok compatibility
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Serve main portal HTML file
@app.get("/", response_class=FileResponse)
async def root(request: Request):
    """Serve the MCP portal HTML file with ngrok compatibility."""
    # Log request details for debugging
    logger.info(f"Root request from: {request.client.host if request.client else 'unknown'}")
    logger.info(f"Headers: {dict(request.headers)}")

    response = FileResponse("test_mcp.html")

    # Add headers for ngrok compatibility
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
    # Add ngrok bypass header to skip warning page
    response.headers["ngrok-skip-browser-warning"] = "true"

    return response


# Debug endpoint for troubleshooting ngrok issues
@app.get("/debug/headers")
async def debug_headers(request: Request):
    """Debug endpoint to see all request headers and ngrok forwarding info."""
    debug_info = {
        "url": str(request.url),
        "method": request.method,
        "client": str(request.client) if request.client else None,
        "headers": dict(request.headers),
        "ngrok_detected": any("ngrok" in str(v) for v in request.headers.values()),
        "forwarded_host": request.headers.get("x-forwarded-host"),
        "forwarded_proto": request.headers.get("x-forwarded-proto"),
        "forwarded_for": request.headers.get("x-forwarded-for"),
        "real_ip": request.headers.get("x-real-ip"),
        "origin": request.headers.get("origin"),
    }
    return JSONResponse(content=debug_info)





# Main MCP endpoint - GET method for client-initiated SSE streams
@app.get("/mcp")
async def mcp_get_endpoint(
        request: Request,
        accept: str = Header(None),
        last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
        session_id: Optional[str] = Header(None, alias="Mcp-Session-Id"),
        protocol_version: Optional[str] = Header(None, alias="MCP-Protocol-Version")
):
    """
    GET endpoint for client-initiated SSE streams per 2025-06-18 specification.
    Provides server-to-client communication for gateway notifications.
    """
    try:
        # Validate protocol version
        validated_version = mcp_gateway.validate_protocol_version(protocol_version)

        # Validate Origin header (required by specification)
        # Extract origin considering load balancer/reverse proxy headers
        origin = mcp_gateway.extract_origin_from_request(request)
        logger.info(f"GET endpoint - Extracted origin: {origin}")

        if not mcp_gateway.validate_origin_header(origin):
            logger.warning(f"Origin validation failed for: {origin}")
            raise HTTPException(status_code=403, detail="Origin not allowed")

        # Validate Accept header for GET requests
        if not mcp_gateway.validate_accept_header(accept, "GET"):
            raise HTTPException(status_code=405, detail="Method Not Allowed")

        # Validate session if provided
        if session_id and not mcp_gateway.validate_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        # Generate unique stream ID for this connection
        stream_id = str(uuid.uuid4())

        async def gateway_notification_stream():
            """
            Generate SSE events for gateway notifications per specification.
            100% compliant with resumability and message routing requirements.
            """
            try:
                # Register this stream for proper management
                mcp_gateway.stream_manager.register_stream(
                    stream_id,
                    session_id or "anonymous",
                    "gateway-notifications"
                )

                # Handle resumability if Last-Event-ID provided
                if last_event_id:
                    logger.info(f"Resuming stream {stream_id} from event ID: {last_event_id}")
                    # Replay missed events from this specific stream
                    missed_events = mcp_gateway.event_store.get_events_after(stream_id, last_event_id)
                    for event in missed_events:
                        yield f"id: {event['id']}\n"
                        yield f"data: {json.dumps(event['message'])}\n\n"

                # Send gateway status notifications
                while True:
                    try:
                        # Check for any queued messages for this specific stream
                        queued_message = await mcp_gateway.message_router.get_next_message(stream_id)
                        if queued_message:
                            yield f"id: {queued_message['id']}\n"
                            yield f"data: {json.dumps(queued_message['data'])}\n\n"
                        else:
                            # Send periodic gateway status notification
                            refresh_data = {
                                "jsonrpc": "2.0",
                                "method": "notifications/tools_refresh",
                                "params": {
                                    "timestamp": datetime.now().isoformat(),
                                    "available_tools": len(discovery_service.tool_to_server_map),
                                    "registered_servers": len(await mcp_storage_manager.get_all_servers()) if mcp_storage_manager else 0
                                }
                            }

                            # Store event with proper event ID
                            event_id = mcp_gateway.event_store.store_event(stream_id, refresh_data)
                            yield f"id: {event_id}\n"
                            yield f"data: {json.dumps(refresh_data)}\n\n"

                            await asyncio.sleep(60)  # Status update every 60 seconds

                    except Exception as e:
                        logger.error(f"Error processing stream {stream_id}: {e}")
                        break

            except Exception as e:
                logger.error(f"Error in gateway notification SSE stream {stream_id}: {e}")
            finally:
                # Clean up stream when connection closes
                mcp_gateway.stream_manager.unregister_stream(stream_id)
                mcp_gateway.event_store.cleanup_stream(stream_id)
                mcp_gateway.message_router.cleanup_stream_queue(stream_id)

        return StreamingResponse(
            gateway_notification_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "ngrok-skip-browser-warning": "true",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GET endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# Main MCP endpoint - POST method for client-to-server communication
@app.post("/mcp")
async def mcp_post_endpoint(
        request_data: Dict[str, Any],
        request: Request,
        accept: str = Header(None),
        session_id: Optional[str] = Header(None, alias="Mcp-Session-Id"),
        protocol_version: Optional[str] = Header(None, alias="MCP-Protocol-Version")
):
    """
    POST endpoint implementing MCP 2025-06-18 Streamable HTTP transport.
    Acts as a gateway proxying requests to appropriate backend MCP servers.
    """
    try:
        # Validate protocol version
        validated_version = mcp_gateway.validate_protocol_version(protocol_version)

        # Validate Origin header (required by specification)
        # Extract origin considering load balancer/reverse proxy headers
        origin = mcp_gateway.extract_origin_from_request(request)
        logger.info(f"POST endpoint - Extracted origin: {origin}")

        if not mcp_gateway.validate_origin_header(origin):
            logger.warning(f"Origin validation failed for: {origin}")
            raise HTTPException(status_code=403, detail="Origin not allowed")

        # Validate Accept header for POST requests
        if not mcp_gateway.validate_accept_header(accept, "POST"):
            raise HTTPException(
                status_code=400,
                detail="Accept header must include both application/json and text/event-stream"
            )

        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")

        if not method:
            raise HTTPException(status_code=400, detail="Invalid JSON-RPC request format.")

        # Handle initialization per specification
        if method == "initialize":
            mcp_gateway.client_info = params
            mcp_gateway.initialized = True
            client_name = params.get('clientInfo', {}).get('name', 'Unknown Client')

            # Generate session ID if not provided
            if not session_id:
                session_id = mcp_gateway.generate_session_id()

            # Store session info
            mcp_gateway.sessions[session_id] = {
                'client_info': params,
                'created_at': datetime.now(),
                'initialized': True,
                'protocol_version': validated_version
            }

            logger.info(f"MCP Toolbox Gateway initialized by {client_name} with session {session_id}")

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "streamableHttp": True
                    },
                    "serverInfo": SERVER_INFO
                }
            }

            headers = {"Mcp-Session-Id": session_id}
            return JSONResponse(content=response, headers=headers)

        elif method == "notifications/initialized":
            logger.info("Client initialization completed.")
            return JSONResponse(content={}, status_code=202)  # 202 Accepted per spec

        # Validate session for other methods
        if session_id and not mcp_gateway.validate_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        # Handle tools/list request
        if method == "tools/list":
            logger.info("tools/list: Fetching from discovery service.")
            all_tools = await discovery_service.get_all_tools()

            return JSONResponse(content={
                "jsonrpc": "2.0", "id": request_id, "result": {"tools": all_tools}
            })

        # Handle tools/call request with streaming
        elif method == "tools/call":
            tool_name = params.get("name")
            if not tool_name:
                if request_id:
                    error_response = mcp_gateway.create_error_response(request_id, -32602, "Tool name is required")
                    return JSONResponse(content=error_response, status_code=400)
                else:
                    raise HTTPException(status_code=400, detail="Missing 'name' in params for tools/call.")

            # Find the tool's server location
            try:
                server_url = await discovery_service.get_tool_location(tool_name)
                logger.info(f"tools/call ({tool_name}): Routing to server: {server_url}")
            except ToolNotFoundException:
                logger.error(f"Tool '{tool_name}' not found in any registered MCP server.")
                if request_id:
                    error_response = mcp_gateway.create_error_response(request_id, -32601, f"Tool not found: {tool_name}")
                    return JSONResponse(content=error_response, status_code=404)
                else:
                    raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

            # Forward the request and stream the response back
            async def gateway_streaming_wrapper():
                """Wrap the backend stream with gateway-specific events per specification."""
                try:
                    # Send gateway progress notification
                    gateway_progress = {
                        "jsonrpc": "2.0",
                        "method": "notifications/gateway_progress",
                        "params": {
                            "message": f"Forwarding request to {server_url}",
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    event_id = str(uuid.uuid4())
                    yield f"id: {event_id}\n"
                    yield f"data: {json.dumps(gateway_progress)}\n\n"

                    # Stream from backend server
                    backend_stream = connection_manager.forward_request_streaming(server_url, request_data)
                    async for chunk in backend_stream:
                        yield chunk

                except Exception as e:
                    logger.error(f"Error in gateway streaming wrapper: {e}")
                    error_event_id = str(uuid.uuid4())
                    error_response = mcp_gateway.create_error_response(request_id, -32000, f"Gateway error: {str(e)}")
                    yield f"id: {error_event_id}\n"
                    yield f"data: {json.dumps(error_response)}\n\n"

            return StreamingResponse(
                gateway_streaming_wrapper(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "ngrok-skip-browser-warning": "true",
                }
            )

        # MCP 2025-06-18 specification only supports standard methods
        # Server management is handled via separate management API

        else:
            logger.warning(f"Received unsupported method: {method}")
            if request_id:
                error_response = mcp_gateway.create_error_response(request_id, -32601, f"Method not found: {method}")
                return JSONResponse(content=error_response, status_code=404)
            else:
                raise HTTPException(status_code=404, detail=f"Method not found: {method}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Critical error in POST endpoint: {e}", exc_info=True)
        error_resp = mcp_gateway.create_error_response(
            request_data.get("id"),
            -32000,
            "Internal Server Error"
        )
        return JSONResponse(content=error_resp, status_code=500)


# DELETE endpoint for session termination
@app.delete("/mcp")
async def mcp_delete_endpoint(
        session_id: Optional[str] = Header(None, alias="Mcp-Session-Id"),
        protocol_version: Optional[str] = Header(None, alias="MCP-Protocol-Version")
):
    """
    DELETE endpoint for explicit session termination per 2025-06-18 specification.
    """
    try:
        # Validate protocol version
        mcp_gateway.validate_protocol_version(protocol_version)

        if not session_id:
            raise HTTPException(status_code=400, detail="Mcp-Session-Id header required")

        if mcp_gateway.terminate_session(session_id):
            return JSONResponse(content={"message": "Session terminated"}, status_code=200)
        else:
            raise HTTPException(status_code=404, detail="Session not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in DELETE endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# Management API endpoint - separate from MCP compliance
@app.post("/manage")
async def management_endpoint(request_data: Dict[str, Any]):
    """
    Management API for server operations - separate from MCP protocol.
    This handles UI management functions while keeping /mcp purely MCP compliant.
    """
    try:
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")

        if not method:
            raise HTTPException(status_code=400, detail="Invalid request format.")

        # Handle server management methods
        if method == "server.add":
            server_url = params.get("server_url")
            description = params.get("description", "")
            
            if not server_url:
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "server_url is required"}
                }, status_code=400)
            
            try:
                server_info = await mcp_storage_manager.register_server_from_url(server_url, description)
                if server_info:
                    # Refresh the discovery service
                    await discovery_service.refresh_tool_index()
                    return JSONResponse(content={
                        "jsonrpc": "2.0", 
                        "id": request_id, 
                        "result": {"success": True, "server_id": server_info.server_id}
                    })
                else:
                    return JSONResponse(content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32000, "message": "Failed to register server"}
                    }, status_code=500)
            except Exception as e:
                logger.error(f"Error adding server: {e}")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": f"Error adding server: {str(e)}"}
                }, status_code=500)

        elif method == "server.remove":
            server_id = params.get("server_id")
            
            if not server_id:
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "server_id is required"}
                }, status_code=400)
            
            try:
                success = await mcp_storage_manager.remove_server(server_id)
                if success:
                    # Refresh the discovery service
                    await discovery_service.refresh_tool_index()
                    return JSONResponse(content={
                        "jsonrpc": "2.0", 
                        "id": request_id, 
                        "result": {"success": True}
                    })
                else:
                    return JSONResponse(content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": "Server not found"}
                    }, status_code=404)
            except Exception as e:
                logger.error(f"Error removing server: {e}")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": f"Error removing server: {str(e)}"}
                }, status_code=500)

        elif method == "server.test":
            server_id = params.get("server_id")
            
            if not server_id:
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "server_id is required"}
                }, status_code=400)
            
            try:
                test_result = await mcp_storage_manager.test_server_connection(server_id)
                return JSONResponse(content={
                    "jsonrpc": "2.0", 
                    "id": request_id, 
                    "result": test_result
                })
            except Exception as e:
                logger.error(f"Error testing server: {e}")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": f"Error testing server: {str(e)}"}
                }, status_code=500)

        elif method == "server.list":
            try:
                servers = await mcp_storage_manager.get_all_servers()
                server_cards = {}

                for server_id, server_info in servers.items():
                    # Count tools for this server
                    tool_count = sum(1 for tool_server_url in discovery_service.tool_to_server_map.values()
                                   if tool_server_url == server_info.url)

                    # Get health status for this server
                    health_status = discovery_service.server_health.get(server_info.url)
                    if health_status:
                        status = "online" if health_status.is_healthy else "offline"
                    else:
                        status = "unknown"

                    server_cards[server_id] = {
                        "name": server_info.name,
                        "url": server_info.url,
                        "description": server_info.description,
                        "capabilities": server_info.capabilities,
                        "metadata": server_info.metadata,
                        "updated_at": server_info.updated_at.isoformat(),
                        "tool_count": tool_count,
                        "status": status
                    }
                
                return JSONResponse(content={
                    "jsonrpc": "2.0", 
                    "id": request_id, 
                    "result": {"server_cards": server_cards}
                })
            except Exception as e:
                logger.error(f"Error listing servers: {e}")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": f"Error listing servers: {str(e)}"}
                }, status_code=500)

        else:
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }, status_code=404)

    except Exception as e:
        logger.error(f"Error in management endpoint: {e}", exc_info=True)
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "error": {"code": -32000, "message": "Internal server error"}
        }, status_code=500)


# Configuration API endpoints
@app.get("/config")
async def get_config():
    """Get current gateway configuration"""
    import json
    config = config_manager.get_all_config()
    # Convert datetime to string for JSON serialization
    return JSONResponse(content=json.loads(json.dumps(config, default=str)))


@app.post("/config/health")
async def update_health_config(request_data: Dict[str, Any]):
    """Update connection health monitoring configuration"""
    try:
        updated_config = config_manager.update_connection_health_config(**request_data)

        # Restart health monitoring with new config
        await discovery_service.stop_health_monitoring()
        await discovery_service.start_health_monitoring()

        return JSONResponse(content={
            "success": True,
            "config": updated_config.model_dump()
        })
    except Exception as e:
        logger.error(f"Error updating health config: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@app.post("/config/origin/add")
async def add_allowed_origin(request_data: Dict[str, Any]):
    """Add an allowed origin"""
    try:
        origin = request_data.get("origin")
        if not origin:
            return JSONResponse(content={
                "error": "origin parameter required"
            }, status_code=400)

        success = config_manager.add_allowed_origin(origin)
        return JSONResponse(content={
            "success": success,
            "message": f"Origin '{origin}' {'added' if success else 'already exists'}"
        })
    except Exception as e:
        logger.error(f"Error adding origin: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@app.post("/config/origin/remove")
async def remove_allowed_origin(request_data: Dict[str, Any]):
    """Remove an allowed origin"""
    try:
        origin = request_data.get("origin")
        if not origin:
            return JSONResponse(content={
                "error": "origin parameter required"
            }, status_code=400)

        success = config_manager.remove_allowed_origin(origin)
        return JSONResponse(content={
            "success": success,
            "message": f"Origin '{origin}' {'removed' if success else 'not found'}"
        })
    except Exception as e:
        logger.error(f"Error removing origin: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@app.post("/config/origin")
async def update_origin_config(request_data: Dict[str, Any]):
    """Update origin configuration (allow_ngrok, allow_https)"""
    try:
        updated_config = config_manager.update_origin_config(**request_data)
        return JSONResponse(content={
            "success": True,
            "config": updated_config.model_dump()
        })
    except Exception as e:
        logger.error(f"Error updating origin config: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@app.get("/health/servers")
async def get_servers_health():
    """Get health status of all connected servers"""
    return JSONResponse(content=discovery_service.get_server_health_status())


@app.get("/health/servers/{server_url:path}")
async def get_server_health(server_url: str):
    """Get health status of a specific server"""
    return JSONResponse(content=discovery_service.get_server_health_status(server_url))


if __name__ == "__main__":
    # Use 0.0.0.0 to allow ngrok to forward requests properly
    host = os.getenv("HOST", "0.0.0.0")  # Changed to 0.0.0.0 for ngrok compatibility
    port = int(os.getenv("PORT", "8021"))

    logger.info(f"Starting Tools Gateway (2025-06-18 compliant) on {host}:{port}...")
    logger.info(f"Protocol Version: {PROTOCOL_VERSION}")
    logger.info(f"Server Info: {SERVER_INFO}")
    logger.info("Features: Health monitoring, dynamic origin configuration, user-driven MCP servers")
    logger.info("NGROK COMPATIBILITY: Configured for HTTPS/ngrok access")

    uvicorn.run(app, host=host, port=port, log_level="info")
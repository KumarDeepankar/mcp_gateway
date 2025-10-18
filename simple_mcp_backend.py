#!/usr/bin/env python3
"""
Simple MCP SSE Backend Server
Demonstrates proper SSE backend implementation for gateway aggregation
"""
import asyncio
import json
import uuid
import logging
from typing import Dict
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory session storage
sessions: Dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan"""
    logger.info("Simple MCP backend starting...")
    yield
    logger.info("Simple MCP backend shutting down...")


app = FastAPI(lifespan=lifespan)


@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint - establishes streaming connection"""
    session_id = str(uuid.uuid4())
    message_queue = asyncio.Queue()
    sessions[session_id] = message_queue

    logger.info(f"New SSE connection, session: {session_id}")

    async def event_generator():
        try:
            # Send endpoint event with session info
            endpoint_event = {
                "jsonrpc": "2.0",
                "method": "endpoint",
                "params": {
                    "endpoint": f"/messages?session_id={session_id}"
                }
            }
            yield {
                "event": "endpoint",
                "data": json.dumps(endpoint_event)
            }

            logger.info(f"Session {session_id} established, streaming events")

            # Stream messages from queue
            while True:
                try:
                    message = await asyncio.wait_for(message_queue.get(), timeout=30.0)
                    yield {
                        "event": "message",
                        "data": json.dumps(message)
                    }
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {
                        "event": "ping",
                        "data": ""
                    }
        except asyncio.CancelledError:
            logger.info(f"Session {session_id} cancelled")
        except Exception as e:
            logger.error(f"Error in SSE generator for session {session_id}: {e}")
        finally:
            # Cleanup
            if session_id in sessions:
                del sessions[session_id]
            logger.info(f"Session {session_id} closed")

    return EventSourceResponse(event_generator())


@app.post("/messages")
async def messages_endpoint(request: Request):
    """Messages endpoint - receives requests and sends responses via SSE"""
    session_id = request.query_params.get("session_id")
    if not session_id or session_id not in sessions:
        return {"error": "Invalid session"}, 404

    body = await request.json()
    message_id = body.get("id")
    method = body.get("method")

    logger.info(f"Received {method} for session {session_id}")

    # Process the message and send response via SSE
    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "simple-mcp-backend",
                    "version": "1.0.0"
                }
            }
        }
        await sessions[session_id].put(response)

    elif method == "tools/list":
        response = {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echoes back the input text",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "Text to echo"
                                }
                            },
                            "required": ["text"]
                        }
                    },
                    {
                        "name": "reverse",
                        "description": "Reverses the input text",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "Text to reverse"
                                }
                            },
                            "required": ["text"]
                        }
                    }
                ]
            }
        }
        await sessions[session_id].put(response)

    elif method == "tools/call":
        tool_name = body.get("params", {}).get("name")
        arguments = body.get("params", {}).get("arguments", {})

        if tool_name == "echo":
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo: {arguments.get('text', '')}"
                    }
                ]
            }
        elif tool_name == "reverse":
            text = arguments.get('text', '')
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": f"Reversed: {text[::-1]}"
                    }
                ]
            }
        else:
            result = {
                "error": {
                    "code": -32601,
                    "message": f"Tool not found: {tool_name}"
                }
            }

        response = {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": result
        }
        await sessions[session_id].put(response)

    else:
        response = {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }
        await sessions[session_id].put(response)

    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)

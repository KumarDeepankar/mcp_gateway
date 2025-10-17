from fastapi import FastAPI, Query, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from typing import Optional, AsyncGenerator, Dict, Any, List
import asyncio
import uuid
import inspect
import traceback
import aiohttp
import json
import os
from pathlib import Path

from pydantic import BaseModel
from langgraph.types import Command, StateSnapshot

from ollama_query_agent.graph_definition import compiled_agent as search_compiled_agent
from ollama_query_agent.mcp_tool_client import mcp_tool_client

# Import auth modules
from auth import (
    get_current_user,
    require_auth,
    get_jwt_token,
    fetch_jwks_from_gateway
)
from auth_routes import router as auth_router
from debug_auth import router as debug_auth_router

app = FastAPI(
    title="Agentic Search Service",
    description="LangGraph-powered search agent using Ollama and MCP tools",
    version="1.0.0",
)

# Include authentication routes
app.include_router(auth_router)
app.include_router(debug_auth_router)


# Startup event to fetch JWKS from tools_gateway
@app.on_event("startup")
async def startup_event():
    """
    Fetch JWKS (JSON Web Key Set) from tools_gateway on startup.

    JWKS contains public keys for RS256 token validation.
    This is the industry-standard approach for microservices JWT authentication.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Fetch JWKS (RS256 - Industry Standard)
    logger.info("Fetching JWKS (RS256 public keys) from tools_gateway...")
    jwks_success = fetch_jwks_from_gateway()

    if jwks_success:
        logger.info("✓ JWKS fetched successfully")
        logger.info("🔐 Authentication ready: RS256 only (industry standard)")
    else:
        logger.error("⚠ Failed to fetch JWKS from gateway - authentication will not work!")
        logger.error("   Please ensure tools_gateway is running and has generated RSA keys")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
CHAT_HTML_FILE = os.path.join(BASE_DIR, "chat.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "agentic-search"}


@app.get("/", response_class=HTMLResponse)
async def get_chat_html(request: Request):
    # Check if user is authenticated
    user = get_current_user(request)

    if not user:
        # Redirect to login page if not authenticated
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/login", status_code=302)

    try:
        with open(CHAT_HTML_FILE, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404,
                            detail="chat.html not found. Please ensure it is in the same directory as server.py")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load chat interface: {e}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/tools")
async def get_available_tools(request: Request):
    """Get available tools from MCP registry (requires authentication)"""
    # Require authentication
    user = require_auth(request)

    try:
        # Get JWT token and set it in MCP client
        jwt_token = get_jwt_token(request)
        if jwt_token:
            mcp_tool_client.set_jwt_token(jwt_token)

        # Fetch tools (will be filtered by gateway based on user's roles)
        tools = await mcp_tool_client.get_available_tools()

        return JSONResponse(content={
            "tools": tools,
            "user": {
                "email": user.get("email"),
                "authenticated": True
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tools: {str(e)}")


class SearchRequest(BaseModel):
    query: str
    enabled_tools: Optional[List[str]] = None
    session_id: Optional[str] = None
    is_followup: Optional[bool] = False


async def search_interaction_stream(session_id: str, query: str, enabled_tools: List[str], is_followup: bool = False) -> \
AsyncGenerator[str, None]:
    """Stream search agent interaction"""

    try:
        # Always use session_id as thread_id to maintain conversation context
        # User will start a new conversation (new session_id) when they want a fresh thread
        thread_id = session_id
        config = {"configurable": {"thread_id": thread_id}}

        # Try to retrieve conversation history from checkpointer
        conversation_history = []
        try:
            state_snapshot = await search_compiled_agent.aget_state(config)
            if state_snapshot and state_snapshot.values:
                conversation_history = state_snapshot.values.get("conversation_history", [])
        except Exception as e:
            # First query in this session - no history available yet
            pass

        inputs = {
            "input": query,
            "conversation_id": session_id,
            "enabled_tools": enabled_tools or [],
            "is_followup_query": bool(conversation_history),  # Auto-detect based on history
            "conversation_history": conversation_history,
        }

        relevant_node_names = [
            "initialize_search_node",
            "discover_tools_node",
            "create_execution_plan_node",
            "execute_all_tasks_parallel_node",
            "gather_and_synthesize_node"
        ]

        final_response_started = False
        final_response_content = ""
        sent_thinking_steps = set()  # Track which thinking steps we've already sent (by content)
        completed_nodes = set()  # Track which nodes have been completed to avoid duplicate completion messages
        started_nodes = set()  # Track which nodes have started to avoid duplicate start messages

        try:
            async for event in search_compiled_agent.astream_events(inputs, config=config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name")
                data = event.get("data", {})

                # Send node start notification BEFORE node executes
                if event_type == "on_chain_start" and event_name in relevant_node_names:
                    if event_name not in started_nodes:
                        started_nodes.add(event_name)
                        # Send node name first, before any thinking steps
                        node_display_name = event_name.replace('_', ' ').title()
                        yield f"THINKING:▶ {node_display_name}\n"
                        await asyncio.sleep(0.01)

                if event_type == "on_chain_end" and event_name in relevant_node_names:
                    node_output = data.get("output")
                    if isinstance(node_output, dict):
                        # Get thinking steps and send only new ones (based on content)
                        thinking_steps_list = node_output.get("thinking_steps", [])

                        # Send only new thinking steps (ones we haven't sent before)
                        for thought in thinking_steps_list:
                            if thought and thought.strip() and thought not in sent_thinking_steps:
                                sent_thinking_steps.add(thought)
                                yield f"PROCESSING_STEP:{thought}\n"
                                await asyncio.sleep(0.01)

                        # Send node completion info only once per node
                        if event_name not in completed_nodes:
                            completed_nodes.add(event_name)
                            yield f"THINKING:✓ Completed: {event_name.replace('_', ' ').title()}\n"
                            await asyncio.sleep(0.01)

                        if node_output.get("final_response_generated_flag") and not final_response_started:
                            final_response_started = True

                            # Signal that final response is starting
                            yield f"FINAL_RESPONSE_START:\n"
                            await asyncio.sleep(0.01)

                            # Handle new FinalResponse structure
                            final_response_obj = node_output.get("final_response")
                            final_response = ""

                            if final_response_obj:
                                # Extract response_content from FinalResponse object
                                if hasattr(final_response_obj, 'response_content'):
                                    final_response = final_response_obj.response_content
                                elif isinstance(final_response_obj, dict):
                                    final_response = final_response_obj.get('response_content', '')

                            # Fallback to old field name for compatibility
                            if not final_response and "final_response_content" in node_output:
                                final_response = node_output.get("final_response_content", "")

                            if final_response:
                                # Check if response contains HTML
                                if '<' in final_response and '>' in final_response:
                                    # Send HTML content in larger chunks to preserve formatting
                                    yield f"HTML_CONTENT_START:\n"
                                    await asyncio.sleep(0.01)
                                    yield final_response
                                    yield f"\nHTML_CONTENT_END:\n"
                                else:
                                    # Simulate streaming by chunking the response for plain text
                                    words = final_response.split()
                                    for i in range(0, len(words), 3):  # Send 3 words at a time
                                        chunk = " ".join(words[i:i + 3])
                                        if i + 3 < len(words):
                                            chunk += " "
                                        final_response_content += chunk
                                        yield chunk
                                        await asyncio.sleep(0.1)  # Slower for better readability

                        if node_output.get("error_message") and not final_response_started:
                            error_msg = node_output['error_message']
                            yield f"ERROR:{error_msg}\n"

                elif event_type == "on_chain_error":
                    error_message = data if isinstance(data, str) else str(data)
                    yield f"ERROR:Agent error in node {event_name}: {error_message}\n"

            if not final_response_started:
                yield "ERROR:Agent finished without generating a final response.\n"

        except Exception as e_main_stream:
            traceback.print_exc()
            yield f"ERROR:A fatal error occurred in the search agent stream: {str(e_main_stream)}\n"


    except Exception as e:
        traceback.print_exc()
        yield f"ERROR:Failed to initialize search agent: {str(e)}\n"


@app.post("/search")
async def search_endpoint(request_body: SearchRequest, http_request: Request):
    """Main search endpoint with streaming response (requires authentication)"""
    # Require authentication
    user = require_auth(http_request)

    # Get JWT token and set it in MCP client
    jwt_token = get_jwt_token(http_request)
    if jwt_token:
        mcp_tool_client.set_jwt_token(jwt_token)

    effective_session_id = request_body.session_id if request_body.session_id else f"search-{str(uuid.uuid4())}"

    return StreamingResponse(
        search_interaction_stream(
            effective_session_id,
            request_body.query,
            request_body.enabled_tools or [],
            request_body.is_followup or False
        ),
        media_type="text/plain"
    )


@app.post("/chat")
async def chat_endpoint(
        request: Request,
        human_message: str = Query(..., description="Your search query"),
        enabled_tools: Optional[str] = Query(None, description="Comma-separated list of enabled tools"),
        session_id: Optional[str] = Query(None, description="Unique session ID")
):
    """Chat-style endpoint for compatibility (requires authentication)"""
    # Require authentication
    user = require_auth(request)

    # Get JWT token and set it in MCP client
    jwt_token = get_jwt_token(request)
    if jwt_token:
        mcp_tool_client.set_jwt_token(jwt_token)

    effective_session_id = session_id if session_id else f"search-{str(uuid.uuid4())}"

    # Parse enabled tools
    enabled_tools_list = []
    if enabled_tools:
        enabled_tools_list = [tool.strip() for tool in enabled_tools.split(",")]

    return StreamingResponse(
        search_interaction_stream(effective_session_id, human_message, enabled_tools_list),
        media_type="text/plain"
    )


if __name__ == "__main__":
    import uvicorn

    # Bind to 0.0.0.0 to accept connections from outside the container
    host = "0.0.0.0"
    port = 8023

    print(f"Starting Agentic Search Service on {host}:{port}")
    print("Make sure Ollama is running with llama3.2:latest model")
    print("Make sure MCP Registry Discovery is running on port 8021")

    uvicorn.run(app, host=host, port=port)

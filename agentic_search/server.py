from fastapi import FastAPI, Query, HTTPException, Request
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

app = FastAPI(
    title="Agentic Search Service",
    description="LangGraph-powered search agent using Ollama and MCP tools",
    version="1.0.0",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
CHAT_HTML_FILE = os.path.join(BASE_DIR, "chat.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "agentic-search"}

@app.get("/", response_class=HTMLResponse)
async def get_chat_html():
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
async def get_available_tools():
    """Get available tools from MCP registry"""
    try:
        tools = await mcp_tool_client.get_available_tools()
        return JSONResponse(content={"tools": tools})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tools: {str(e)}")

class SearchRequest(BaseModel):
    query: str
    enabled_tools: Optional[List[str]] = None
    session_id: Optional[str] = None
    is_followup: Optional[bool] = False

async def search_interaction_stream(session_id: str, query: str, enabled_tools: List[str], is_followup: bool = False) -> AsyncGenerator[str, None]:
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
                print(f"[DEBUG] Retrieved conversation_history: {len(conversation_history)} turns")
        except Exception as e:
            # First query in this session - no history available yet
            print(f"[DEBUG] Error retrieving state: {e}")
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
            "unified_planning_decision_node",
            "execute_tool_step_node"
        ]

        final_response_started = False
        final_response_content = ""
        sent_thinking_steps = set()  # Track which thinking steps we've already sent (by content)
        completed_nodes = set()  # Track which nodes have been completed to avoid duplicate completion messages

        try:
            async for event in search_compiled_agent.astream_events(inputs, config=config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name")
                data = event.get("data", {})

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

                            if "final_response_content" in node_output:
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
                                            chunk = " ".join(words[i:i+3])
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

        # After streaming completes, verify the state was saved
        try:
            final_state = await search_compiled_agent.aget_state(config)
            if final_state and final_state.values:
                conv_hist = final_state.values.get("conversation_history", [])
                print(f"[DEBUG] After stream complete - conversation_history has {len(conv_hist)} turns")
        except Exception as e:
            print(f"[DEBUG] Error checking final state: {e}")

    except Exception as e:
        traceback.print_exc()
        yield f"ERROR:Failed to initialize search agent: {str(e)}\n"

@app.post("/search")
async def search_endpoint(request: SearchRequest):
    """Main search endpoint with streaming response"""
    effective_session_id = request.session_id if request.session_id else f"search-{str(uuid.uuid4())}"

    return StreamingResponse(
        search_interaction_stream(
            effective_session_id,
            request.query,
            request.enabled_tools or [],
            request.is_followup or False
        ),
        media_type="text/plain"
    )

@app.post("/chat")
async def chat_endpoint(
    human_message: str = Query(..., description="Your search query"),
    enabled_tools: Optional[str] = Query(None, description="Comma-separated list of enabled tools"),
    session_id: Optional[str] = Query(None, description="Unique session ID")
):
    """Chat-style endpoint for compatibility"""
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
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8023"))

    print(f"Starting Agentic Search Service on {host}:{port}")
    print("Make sure Ollama is running with llama3.2:latest model")
    print("Make sure MCP Registry Discovery is running on port 8021")

    uvicorn.run(app, host=host, port=port)
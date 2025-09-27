# agentic_assistant/server.py
from fastapi import FastAPI, Query, HTTPException, File, UploadFile, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from typing import Optional, AsyncGenerator, Dict, Any, List, Union
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

from gemini_query_agent.graph_definition import compiled_agent as query_compiled_agent
from researcher_gemini_agent_modular.graph_definition import researcher_compiled_agent

# Note: Assuming document_parser.py exists in the same directory
from document_parser import extract_excel_content, extract_word_content, extract_ppt_content


# Import settings from the root
from settings import (
    APP_HOST, APP_PORT, MCP_SERVER_BASE_URL, 
    AGENT_INTERFACE_BASE_URL
)

from conversation_history import ConversationHistory



app = FastAPI(
    title="LangGraph MCP-Powered Conversational & Research Agent",
    description="Agent for queries and research, plans using tools, executes steps, allows human review for research, and streams responses.",
    version="5.6.0", # Incremented version
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
CHAT_HTML_FILE = os.path.join(BASE_DIR, "chat.html")

# Initialize conversation history manager
conversation_history = ConversationHistory()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Kubernetes readiness probes.
    """
    return {"status": "healthy", "service": "agentic-assistant"}


@app.get("/", response_class=HTMLResponse)
async def get_chat_html():
    try:
        with open(CHAT_HTML_FILE, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404,
                            detail="chat.html not found. Please ensure it is in the same directory as server.py or "
                                   "update the path.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load chat interface: {e}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    """
    Handles document uploads, extracts content, and sends it to the chat endpoint.
    """
    allowed_extensions = {
        '.xlsx': extract_excel_content,
        '.xls': extract_excel_content,
        '.docx': extract_word_content,
        '.doc': extract_word_content,
        '.pptx': extract_ppt_content,
        '.ppt': extract_ppt_content,
        '.txt': lambda content: content.decode('utf-8')
    }

    file_extension = Path(file.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions.keys())}"
        )

    try:
        file_content = await file.read()
        extractor = allowed_extensions[file_extension]
        extracted_content = extractor(file_content)

        return JSONResponse(content={
            "filename": file.filename,
            "content": extracted_content
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


async def agent_interaction_stream(session_id: str, human_message: str) -> AsyncGenerator[str, None]:

        async with aiohttp.ClientSession() as http_session:
            config = {"configurable": {"thread_id": f"{session_id}_query", "http_session": http_session}}
            inputs = {"input": human_message, "conversation_id": session_id}

            relevant_node_names_gemini = [
                "initialize_and_update_history_node",
                "discover_tools_and_agents_node",
                "unified_planning_and_decision_node",
                "prepare_current_step_for_execution_node",
                "execute_tool_step_node",
                "execute_reasoning_step_node",
            ]

            final_response_started = False
            final_response_content = ""
            try:
                async for event in query_compiled_agent.astream_events(inputs, config=config, version="v2"):
                    event_type = event.get("event")
                    event_name = event.get("name")
                    data = event.get("data", {})

                    if event_type == "on_chain_end" and event_name in relevant_node_names_gemini:
                        node_output = data.get("output")
                        if isinstance(node_output, dict):
                            thinking_steps_list = node_output.get("thinking_steps", [])
                            if thinking_steps_list:
                                for thought in thinking_steps_list:
                                    yield f"THINKING:{thought}\n"
                                    await asyncio.sleep(0.01)

                            if node_output.get("final_response_generated_flag") and not final_response_started:
                                final_response_started = True

                                if "final_answer_stream" in node_output:
                                    final_stream_generator = node_output.get("final_answer_stream")
                                    if final_stream_generator and inspect.isasyncgen(final_stream_generator):
                                        try:
                                            async for line in final_stream_generator:
                                                final_response_content += line
                                                yield line
                                                await asyncio.sleep(0.005)
                                        except Exception as e_stream:
                                            traceback.print_exc()
                                            yield f"ERROR:Critical error processing final answer stream: {str(e_stream)}\n"

                            if node_output.get("error_message") and not final_response_started:
                                error_msg = node_output['error_message']
                                yield f"ERROR:{error_msg}\n"

                    elif event_type == "on_chain_error":
                        error_message = data if isinstance(data, str) else str(data)
                        yield f"ERROR:Agent error in node {event_name}: {error_message}\n"

                if not final_response_started:
                    yield "ERROR:Agent finished without generating a final response.\n"
                    yield "STREAM_ENDED_SESSION_DONE\n"

            except Exception as e_main_stream:
                traceback.print_exc()
                yield f"ERROR:A fatal error occurred in the query agent stream: {str(e_main_stream)}\n"
                yield "STREAM_ENDED_SESSION_DONE\n"


async def researcher_interaction_stream_refactored(
        session_id: str,
        edited_plan: List[str],
        research_query: str,
        conversation_history: Optional[List[Dict[str, str]]]
) -> AsyncGenerator[str, None]:
        async with aiohttp.ClientSession() as http_session:
            config = {
                "configurable": {
                    "thread_id": f"{session_id}_research",
                    "http_session": http_session
                }
            }
            research_nodes_of_interest = [
                "initialize_research", "generate_plan", "format_plan_for_review", "prepare_next_step",
                "execute_single_step", "accumulate_result", "synthesize_report"
            ]

            resume_data = {
                "user_research_query": research_query,
                "research_session_conversation_id": session_id,
                "research_session_conversation_history": conversation_history or [],
                "human_edited_research_plan_steps": edited_plan,
                "human_plan_review_completion_flag": True,
                "agent_internal_thinking_steps_log": [
                    f"Human review complete. Resuming research with {len(edited_plan)} edited step(s).",
                    f"DEBUG: Edited plan contents: {edited_plan[:3] if edited_plan else 'None'}..." if edited_plan else "DEBUG: No edited plan provided"
                ]
            }
            yield f"THINKING:Starting research execution with {len(edited_plan)} steps\n"
            final_report_content = ""
            try:
                async for event in researcher_compiled_agent.astream_events(Command(resume=resume_data), config=config,
                                                                            version="v2"):
                    event_type = event.get("event")
                    event_name = event.get("name")
                    output = event.get("data", {}).get("output")
                    
                    # Debug: Log all events to see what's happening
                    if event_type == "on_chain_end":
                        yield f"THINKING:Event: {event_type}, Node: {event_name}\n"

                    if event_type == "on_chain_end" and event_name in research_nodes_of_interest and isinstance(output,
                                                                                                                dict):
                        # Add debug for which node is executing
                        yield f"THINKING:*** Node '{event_name}' completed execution ***\n"
                        for thought in output.get("agent_internal_thinking_steps_log", []):
                            yield f"THINKING:{thought}\n"
                            await asyncio.sleep(0.01)

                        if event_name == "synthesize_report":
                            yield f"THINKING:Report synthesis node completed. Processing final report...\n"
                            if final_report_html := output.get("synthesized_final_research_report_html"):
                                final_report_content = final_report_html
                                yield f"THINKING:Final report generated with {len(final_report_html)} characters\n"
                                
                                # Encode HTML to prevent line-splitting issues
                                import base64
                                encoded_html = base64.b64encode(final_report_html.encode('utf-8')).decode('utf-8')
                                yield f"ANSWER_DATA_ENCODED:{encoded_html}\n"
                            else:
                                yield f"THINKING:WARNING: No final report HTML found in synthesize_report output\n"
                                yield f"THINKING:Available keys in output: {list(output.keys())}\n"
                                
                            if final_sources := output.get("research_turn_accumulated_sources"):
                                yield f"THINKING:Found {len(final_sources)} sources for final report\n"
                                yield f"SOURCES_DATA:{json.dumps(final_sources)}\n"
                            if final_charts := output.get("research_turn_generated_charts_list"):
                                if final_charts: # Ensure the list is not empty
                                    # Convert A2AChartSpec objects to dictionaries for JSON serialization
                                    serializable_charts = []
                                    for chart in final_charts:
                                        if hasattr(chart, 'to_dict'):
                                            serializable_charts.append(chart.to_dict())
                                        elif isinstance(chart, dict):
                                            serializable_charts.append(chart)
                                        else:
                                            # Fallback: convert object attributes to dict
                                            serializable_charts.append({
                                                'chart_type': getattr(chart, 'chart_type', 'unknown'),
                                                'data': getattr(chart, 'data', []),
                                                'options': getattr(chart, 'options', {}),
                                                'metadata': getattr(chart, 'metadata', {})
                                            })
                                    chart_payload = {"chart_options": serializable_charts}
                                    yield f"CHART_DATA:{json.dumps(chart_payload)}\n"
            except Exception as e:
                traceback.print_exc()
                yield f"ERROR:A fatal error occurred in the researcher agent stream: {str(e)}\n"
            finally:
                yield "STREAM_ENDED_SESSION_DONE\n"


@app.post("/chat")
async def chat_with_agent_endpoint(
        human_message: str = Query(..., description="Your message to the agent."),
        session_id: Optional[str] = Query(None, description="Unique session ID.")
):
    effective_session_id = session_id if session_id else f"server-generated-chat-{str(uuid.uuid4())}"
    return StreamingResponse(
        agent_interaction_stream(effective_session_id, human_message),
        media_type="text/plain"
    )


class ResearchStartBody(BaseModel):
    research_query: str
    session_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None


@app.post("/research/start_plan")
async def research_start_plan_endpoint(body: ResearchStartBody):
    research_query = body.research_query
    session_id = body.session_id
    conversation_history_list = body.conversation_history

    effective_session_id = session_id if session_id else f"server-generated-research-{str(uuid.uuid4())}"
    
    async def planning_stream():
        try:
            async with aiohttp.ClientSession() as http_session:
                config = {
                    "configurable": {
                        "thread_id": f"{effective_session_id}_research",
                        "http_session": http_session
                    }
                }

                inputs: Dict[str, Any] = {
                    "user_research_query": research_query,
                    "research_session_conversation_id": effective_session_id
                }
                if conversation_history_list:
                    inputs["research_session_conversation_history"] = conversation_history_list

                # Stream the planning process
                planning_complete = False
                async for event in researcher_compiled_agent.astream_events(inputs, config=config, version="v2"):
                    event_type = event.get("event")
                    event_name = event.get("name")
                    data = event.get("data", {})
                    
                    # Stream thinking steps during planning
                    if event_type == "on_chain_end" and event_name in ["initialize_research", "generate_plan", "format_plan_for_review"]:
                        node_output = data.get("output", {})
                        thinking_steps = node_output.get("agent_internal_thinking_steps_log", [])
                        for step in thinking_steps:
                            yield f"THINKING:{step}\n"
                            await asyncio.sleep(0.01)
                    
                    # Check if we hit the human review interrupt
                    if event_type == "on_chain_end" and event_name == "human_review_plan":
                        planning_complete = True
                        break

                # Get final state
                current_graph_snapshot: Optional[StateSnapshot] = await researcher_compiled_agent.aget_state(config)

                if not current_graph_snapshot:
                    yield "ERROR:Failed to get researcher agent state after initial invocation.\n"
                    return

                next_nodes = current_graph_snapshot.next
                interrupted_state_values = current_graph_snapshot.values

                if "human_review_plan" in next_nodes:
                    plan_to_review = interrupted_state_values.get("human_reviewable_plan_steps_list", [])
                    original_query_from_state = interrupted_state_values.get("user_research_query", research_query)

                    if plan_to_review:
                        response_data = {
                            "session_id": effective_session_id,
                            "plan_to_review": plan_to_review,
                            "task_description": "Please review and edit the research plan. Ensure TOOL_CALL steps have "
                                                "correctly formatted JSON arguments (double quotes for keys and string "
                                                "values). Submit the revised plan.",
                            "original_query": original_query_from_state,
                            "conversation_history": conversation_history_list,
                            "message": "Research plan generated, awaiting review."
                        }
                        yield f"PLAN_READY:{json.dumps(response_data)}\n"
                    else:
                        yield "ERROR:Agent interrupted for review, but no plan_to_review found in state.\n"
                else:
                    final_report = interrupted_state_values.get("synthesized_final_research_report_html")
                    error_message = interrupted_state_values.get("workflow_error_message")
                    thinking_steps = interrupted_state_values.get("agent_internal_thinking_steps_log", [])
                    turn_sources = interrupted_state_values.get("research_turn_accumulated_sources", [])
                    turn_charts = interrupted_state_values.get("research_turn_generated_charts_list", [])

                    if final_report:
                        response_data = {
                            "session_id": effective_session_id,
                            "final_report_direct": final_report,
                            "thinking_steps": thinking_steps,
                            "turn_sources": turn_sources,
                            "turn_charts": turn_charts,
                            "message": "Research process completed without review stage."
                        }
                        yield f"RESEARCH_COMPLETE:{json.dumps(response_data)}\n"
                    elif error_message:
                        yield f"ERROR:Researcher agent error: {error_message}\n"
                    else:
                        yield "ERROR:Agent did not interrupt for review and final output was unclear.\n"
                        
        except Exception as e:
            traceback.print_exc()
            yield f"ERROR:Server error during research plan start: {str(e)}\n"
        finally:
            yield "STREAM_ENDED_SESSION_DONE\n"
    
    return StreamingResponse(planning_stream(), media_type="text/plain")


class ResumeResearchPayload(BaseModel):
    session_id: str
    edited_plan: List[str]
    original_query: str
    conversation_history: Optional[List[Dict[str, str]]] = None


@app.post("/research/execute_plan")
async def research_execute_plan_endpoint(payload: ResumeResearchPayload):
    print(f"DEBUG_SERVER: Execute plan endpoint called with session_id: {payload.session_id}")
    print(f"DEBUG_SERVER: Edited plan has {len(payload.edited_plan)} steps")
    print(f"DEBUG_SERVER: Original query: {payload.original_query}")
    print(f"DEBUG_SERVER: First 3 plan steps: {payload.edited_plan[:3] if payload.edited_plan else 'None'}")

    async def debug_execution_stream():
        yield f"THINKING:=== EXECUTION ENDPOINT REACHED ===\n"
        yield f"THINKING:About to start execution stream for session {payload.session_id}\n"
        
        try:
            async for chunk in researcher_interaction_stream_refactored(
                payload.session_id,
                payload.edited_plan,
                payload.original_query,
                payload.conversation_history
            ):
                yield chunk
        except Exception as e:
            yield f"ERROR:Execution stream error: {str(e)}\n"
            
    return StreamingResponse(debug_execution_stream(), media_type="text/plain")


@app.get("/conversation/history")
async def get_conversation_history():
    """Get conversation history."""
    try:
        conversations = conversation_history.get_conversations()
        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving conversation history: {str(e)}")


@app.post("/conversation/new")
async def start_new_conversation():
    """Start a new conversation and return a new session ID."""
    new_session_id = f"server-generated-chat-{str(uuid.uuid4())}"
    return {"session_id": new_session_id, "message": "New conversation started"}


class SaveConversationRequest(BaseModel):
    session_id: str
    messages: List[Dict[str, str]]
    title: Optional[str] = None


@app.post("/conversation/save")
async def save_conversation(request: SaveConversationRequest):
    """Save current conversation to history."""
    try:
        conversation_history.add_conversation(
            session_id=request.session_id,
            messages=request.messages,
            title=request.title
        )
        return {"message": "Conversation saved to history"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving conversation: {str(e)}")


@app.get("/conversation/{session_id}")
async def get_conversation_by_id(session_id: str):
    """Get a specific conversation by session ID."""
    try:
        conversation = conversation_history.get_conversation_by_id(session_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving conversation: {str(e)}")



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
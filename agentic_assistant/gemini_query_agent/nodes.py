# himan_ai/agentic_assistant/gemini_query_agent/nodes.py
import asyncio
import json
import traceback
import uuid
from typing import Dict, Any, List, Optional
import html
import re
import google.generativeai as genai
from langchain_core.runnables import RunnableConfig
import time  # Import time for evaluation timing

from .state_definition import PlanExecuteAgentState
from settings import gemini_model
from .llm_models import UnifiedPlannerDecisionOutput, PlanStep
from .prompts import create_unified_planner_decider_prompt, create_reasoning_prompt
from .tool_interactions import (
    discover_mcp_tools, discover_a2a_agents, call_mcp_tool, call_a2a_agent
)
from .utils import format_tools_for_llm_prompt, create_fallback_response
from .llm_interactions import call_llm_with_structured_output
# MODIFIED: Import the new evaluation interaction function
from .eval_interactions import log_comprehensive_evaluation




def initialize_and_update_history_node(state: PlanExecuteAgentState) -> Dict[str, Any]:
    """Initialize the conversation and set up initial state variables."""
    user_input = state.get('input', "MISSING_INPUT_IN_STATE")
    print("user raw query")
    print(user_input)

    # MODIFIED: Parse user input to extract query, document content, and selected tools
    # Use more robust regex patterns that can handle compact JSON
    doc_content_match = re.search(r'--- Document Content ---\n(.*?)\n--- End Document ---', user_input, re.DOTALL)
    tools_match = re.search(r'--- Selected Tools ---\n(\[.*?\])\n\n--- Selected Agents ---', user_input, re.DOTALL)
    agents_match = re.search(r'--- Selected Agents ---\n(\[.*?\])\n\n--- User Query ---', user_input, re.DOTALL)
    query_match = re.search(r'--- User Query ---\n(.*)', user_input, re.DOTALL)

    # DEBUG: Print parsing results
    print(f"DEBUG: doc_content_match found: {doc_content_match is not None}")
    print(f"DEBUG: tools_match found: {tools_match is not None}")
    print(f"DEBUG: agents_match found: {agents_match is not None}")
    print(f"DEBUG: query_match found: {query_match is not None}")
    
    # DEBUG: Show what each regex actually matched
    if tools_match:
        print(f"DEBUG: tools_match content: {tools_match.group(1)[:100]}...")
    if agents_match:
        print(f"DEBUG: agents_match content: {agents_match.group(1)[:100]}...")

    doc_content = doc_content_match.group(1).strip() if doc_content_match else ''
    selected_tools_json = tools_match.group(1).strip() if tools_match else '[]'
    selected_agents_json = agents_match.group(1).strip() if agents_match else '[]'
    user_query = query_match.group(1).strip() if query_match else user_input
    
    # FALLBACK: If tools_match failed, try to extract manually from the input
    if not tools_match and '--- Selected Tools ---' in user_input:
        print("DEBUG: FALLBACK - Trying manual extraction of tools section")
        tools_start = user_input.find('--- Selected Tools ---\n')
        if tools_start != -1:
            tools_start += len('--- Selected Tools ---\n')
            # Find the end of the tools section
            tools_end = user_input.find('\n\n--- Selected Agents ---', tools_start)
            if tools_end == -1:
                tools_end = user_input.find('\n\n--- User Query ---', tools_start)
            if tools_end == -1:
                tools_end = len(user_input)
            
            selected_tools_json = user_input[tools_start:tools_end].strip()
            print(f"DEBUG: FALLBACK - Extracted tools JSON: {selected_tools_json[:100]}...")
    
    # FALLBACK: If agents_match failed, try to extract manually from the input  
    if not agents_match and '--- Selected Agents ---' in user_input:
        print("DEBUG: FALLBACK - Trying manual extraction of agents section")
        agents_start = user_input.find('--- Selected Agents ---\n')
        if agents_start != -1:
            agents_start += len('--- Selected Agents ---\n')
            # Find the end of the agents section
            agents_end = user_input.find('\n\n--- User Query ---', agents_start)
            if agents_end == -1:
                agents_end = len(user_input)
            
            selected_agents_json = user_input[agents_start:agents_end].strip()
            print(f"DEBUG: FALLBACK - Extracted agents JSON: {selected_agents_json[:100]}...")

    print(f"DEBUG: selected_tools_json: {selected_tools_json}")
    print(f"DEBUG: selected_tools_json length: {len(selected_tools_json)}")
    print(f"DEBUG: selected_agents_json: {selected_agents_json}")
    print(f"DEBUG: selected_agents_json length: {len(selected_agents_json)}")

    try:
        # Parse tools JSON - handle both empty and malformed JSON
        user_selected_tools_list = []
        if selected_tools_json and selected_tools_json.strip() != '[]':
            try:
                user_selected_tools_list = json.loads(selected_tools_json)
            except json.JSONDecodeError as e:
                print(f"DEBUG: Tools JSON decode error: {e}")
                print(f"DEBUG: Problematic tools JSON: {selected_tools_json[:200]}...")
        
        # Parse agents JSON - handle both empty and malformed JSON
        user_selected_agents_list = []
        if selected_agents_json and selected_agents_json.strip() != '[]':
            try:
                user_selected_agents_list = json.loads(selected_agents_json)
            except json.JSONDecodeError as e:
                print(f"DEBUG: Agents JSON decode error: {e}")
                print(f"DEBUG: Problematic agents JSON: {selected_agents_json[:200]}...")
                # Try to extract just the valid JSON part
                try:
                    # Find the end of the first complete JSON array
                    bracket_count = 0
                    json_end = -1
                    for i, char in enumerate(selected_agents_json):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                json_end = i + 1
                                break
                    
                    if json_end > 0:
                        clean_json = selected_agents_json[:json_end]
                        user_selected_agents_list = json.loads(clean_json)
                        print(f"DEBUG: Successfully parsed cleaned agents JSON")
                except Exception as e2:
                    print(f"DEBUG: Failed to clean agents JSON: {e2}")
        
        user_selected_tool_definitions = user_selected_tools_list + user_selected_agents_list
        print(f"DEBUG: user_selected_tool_definitions: {len(user_selected_tool_definitions)} items")
        for i, tool in enumerate(user_selected_tool_definitions):
            print(f"DEBUG: Tool {i+1}: {tool.get('name', 'no-name')} (is_a2a_tool: {tool.get('is_a2a_tool', False)})")
            
        # DEBUG: Check if we have both tools and agents
        tools_count = len(user_selected_tools_list)
        agents_count = len(user_selected_agents_list)
        print(f"DEBUG: Parsed {tools_count} tools and {agents_count} agents")
        
        # BACKUP: If we have agents but no tools, and the query mentions common MCP tools, add them
        common_mcp_tools = ['search_web', 'search_news']
        if agents_count > 0 and tools_count == 0:
            for tool_name in common_mcp_tools:
                if tool_name.lower() in user_query.lower():
                    print(f"DEBUG: BACKUP - Adding missing MCP tool: {tool_name}")
                    user_selected_tool_definitions.append({
                        "name": tool_name,
                        "description": f"MCP tool: {tool_name}",
                        "is_a2a_tool": False
                    })
            
    except Exception as e:
        print(f"DEBUG: General parsing error: {e}")
        user_selected_tool_definitions = []

    # If there's document content, prepend it to the user query for context
    if doc_content:
        final_query = f"Based on the following document content:\n\n{doc_content}\n\n{user_query}"
    else:
        final_query = user_query

    selected_tools = [tool.get('name') for tool in user_selected_tool_definitions]

    user_message = {"role": "user", "content": final_query}
    conv_id = state.get("conversation_id") or f"gemini-conv-{uuid.uuid4().hex[:8]}"

    print(f"🚀 Starting conversation: {conv_id}")

    thinking_steps = [f"🚀 Starting new conversation"]

    new_state = {
        "input": final_query,
        "conversation_id": conv_id,
        "conversation_history": [user_message],
        "available_tools_for_planner": [],
        "formatted_tools_for_planner_prompt": "No tools discovered yet.",
        "original_plan": None,
        "plan": None,
        "current_step_to_execute": None,
        "past_steps": [],
        "current_ai_response_text": None,
        "final_response_generated_flag": None,
        "thinking_steps": thinking_steps,
        "turn_sources": [],
        "turn_charts": [],
        "error_message": None,
        "current_turn_iteration_count": 0,
        "max_turn_iterations": 2,
        "user_selected_tools": selected_tools,
        "user_selected_tool_definitions": user_selected_tool_definitions
    }

    return new_state


async def discover_tools_and_agents_node(state: PlanExecuteAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Organize both tools and agents that are selected by the user."""
    user_selected_tool_definitions = state.get("user_selected_tool_definitions", [])

    thinking_steps = []
    
    if user_selected_tool_definitions:
        # Separate tools and agents for better display
        mcp_tools = []
        a2a_tools = []
        
        for tool in user_selected_tool_definitions:
            tool_name = tool.get('name', 'Unknown')
            if tool.get('is_a2a_tool'):
                a2a_tools.append(tool_name)
            else:
                mcp_tools.append(tool_name)
        
        # Create informative display message
        selected_resources = []
        if mcp_tools:
            selected_resources.extend(mcp_tools)
        if a2a_tools:
            selected_resources.extend(a2a_tools)
        
        thinking_steps.append(f"🛠️ Using selected resources: {', '.join(selected_resources)}")
        
        # Add breakdown if both types are present
        if mcp_tools and a2a_tools:
            thinking_steps.append(f"🔧 Tools: {', '.join(mcp_tools)}")
            thinking_steps.append(f"🤖 Agents: {', '.join(a2a_tools)}")
        elif mcp_tools:
            thinking_steps.append(f"🔧 Tools: {', '.join(mcp_tools)}")
        elif a2a_tools:
            thinking_steps.append(f"🤖 Agents: {', '.join(a2a_tools)}")
            
    else:
        thinking_steps.append("🛠️ No tools selected by the user.")

    formatted_tools_prompt = format_tools_for_llm_prompt(user_selected_tool_definitions)

    return {
        "available_tools_for_planner": user_selected_tool_definitions,
        "formatted_tools_for_planner_prompt": formatted_tools_prompt,
        "thinking_steps": thinking_steps
    }


async def unified_planning_and_decision_node(state: PlanExecuteAgentState, config: RunnableConfig) -> Dict[str, Any]:
    http_session = config["configurable"]["http_session"]
    current_iteration = state.get("current_turn_iteration_count", 0) + 1
    max_iterations = state.get("max_turn_iterations", 2)

    print(f"🤔 Planning iteration {current_iteration}/{max_iterations}")

    thinking_steps = [f"🤔 Planning and decision making"]

    conversation_history = state.get("conversation_history", [])
    tools_info_str = state.get("formatted_tools_for_planner_prompt", "No tools information available.")
    executed_steps_this_turn = state.get("past_steps", [])
    current_remaining_plan = state.get("plan")
    turn_sources = list(state.get("turn_sources", []))
    turn_charts = list(state.get("turn_charts", []))

    async def create_final_response(html_content: str, is_error: bool = False):
        # MODIFIED: Call comprehensive evaluation service before finishing
        await log_comprehensive_evaluation(
            http_session=http_session,
            question=state.get("input", "N/A"),
            final_answer=html_content,
            past_steps=executed_steps_this_turn,
            turn_sources=turn_sources,
        )

        if not html_content:
            is_error = True
            html_content = _generate_error_response_html(
                "I was unable to generate a final response. Please try rephrasing your query.")

        async def stream_response():
            if html_content:
                cleaned_html_content = html_content.replace("\n", "").replace("\r", "")
                yield f"ANSWER_DATA:{cleaned_html_content}\n"

            if not is_error:
                if turn_sources:
                    yield f"SOURCES_DATA:{json.dumps(turn_sources)}\n"
                if turn_charts:
                    # Ensure charts are wrapped in the expected 'chart_options' structure
                    for chart in turn_charts:
                        # If the chart is not already in the wrapper format, wrap it.
                        if "chart_options" not in chart:
                            wrapped_chart = {"chart_options": [chart]}
                            yield f"CHART_DATA:{json.dumps(wrapped_chart)}\n"
                        else:
                            yield f"CHART_DATA:{json.dumps(chart)}\n"
                await asyncio.sleep(0.02)
            yield "STREAM_ENDED_SESSION_DONE\n"

        conversation_history_update = []
        if not is_error and html_content:
            import re
            text_content = re.sub(r'<[^>]+>', '', html_content)
            text_content = html.unescape(text_content).strip()
            if text_content:
                conversation_history_update = [{"role": "assistant", "content": text_content[:1000] + "..." if len(
                    text_content) > 1000 else text_content}]

        final_thinking = thinking_steps + (
            ["✅ Response ready"] if not is_error else ["❌ Error occurred"])

        return {
            "current_ai_response_text": html_content,
            "final_answer_stream": stream_response(),
            "final_response_generated_flag": True,
            "conversation_history": conversation_history_update,
            "turn_sources": turn_sources,
            "turn_charts": turn_charts,
            "thinking_steps": final_thinking
        }

    async def handle_error(error_msg: str):
        print(f"❌ Error in planning: {error_msg}")
        return await create_final_response(_generate_error_response_html(error_msg), is_error=True)

    prompt_messages = create_unified_planner_decider_prompt(
        conversation_history, executed_steps_this_turn, current_remaining_plan,
        tools_info_str, turn_sources, turn_charts, current_iteration, max_iterations
    )

    print(prompt_messages)

    input_payload = {
        "prompt": prompt_messages,
        "iteration": current_iteration,
        "max_iterations": max_iterations,
        "tools": [tool.get('name') for tool in state.get("available_tools_for_planner", []) if tool.get('name')]
    }

    if current_iteration > max_iterations:
        print(f"⏰ Reached iteration limit ({max_iterations})")
        thinking_steps.append("🔄 Generating summary")

        try:
            llm_response: UnifiedPlannerDecisionOutput = await call_llm_with_structured_output(
                prompt_messages, UnifiedPlannerDecisionOutput, config
            )
            output_payload = llm_response.model_dump()
            return await create_final_response(llm_response.response_summary_html)
        except Exception as e:
            print(f"❌ Error generating summary: {str(e)}")
            limit_response_html = _generate_iteration_limit_response_html(
                executed_steps_this_turn, turn_sources, turn_charts, max_iterations
            )
            return await create_final_response(limit_response_html)

    try:
        llm_response: UnifiedPlannerDecisionOutput = await call_llm_with_structured_output(
            prompt_messages, UnifiedPlannerDecisionOutput, config
        )
        output_payload = llm_response.model_dump()
        print(f"✅ LLM decision: {llm_response.action_type}")
    except Exception as e:
        return await handle_error("LLM call failed during planning/decision")

    if llm_response.action_type == "RESPOND_DIRECTLY":
        thinking_steps.append("📝 Generating response")
        print("📝 Generating direct response")
        response_html = llm_response.response_summary_html or "I apologize, but I encountered an issue generating a proper response. Please try rephrasing."
        return await create_final_response(response_html, is_error=not bool(llm_response.response_summary_html))

    elif llm_response.action_type == "PLAN_NEXT_STEPS":
        if not llm_response.plan:
            return await handle_error("LLM chose to plan but provided no steps")

        is_new_plan = not current_remaining_plan and not executed_steps_this_turn
        if is_new_plan:
            thinking_steps.append(f"📋 Created plan with {len(llm_response.plan)} steps")
            print(f"📋 Created new plan with {len(llm_response.plan)} steps")
        else:
            thinking_steps.append(f"🔄 Updated plan")
            print(f"🔄 Updated plan, {len(llm_response.plan)} steps remaining")

        return {
            "plan": llm_response.plan,
            "original_plan": list(llm_response.plan) if is_new_plan else state.get("original_plan"),
            "final_response_generated_flag": None,
            "thinking_steps": thinking_steps,
            "turn_sources": turn_sources,
            "turn_charts": turn_charts,
            "current_turn_iteration_count": current_iteration,
            "error_message": None
        }

    else:
        return await handle_error(f"Unknown action type from LLM: {llm_response.action_type}")


async def execute_tool_step_node(state: PlanExecuteAgentState, config: RunnableConfig) -> Dict[str, Any]:
    step_to_execute = state.get("current_step_to_execute")
    if not step_to_execute or not step_to_execute.tool_call_details:
        # MODIFIED: Return richer error step data
        error_step = {"description": "Tool Execution Error", "result": "Tool step not defined.",
                      "tool_name": "error_handler", "thought": "System failed to provide a step to execute."}
        return {"error_message": "Tool step not defined.", "past_steps": [error_step]}

    http_session = config["configurable"]["http_session"]
    tool_name = step_to_execute.tool_call_details.tool_name
    tool_args = step_to_execute.tool_call_details.arguments
    step_description = step_to_execute.description

    thinking_steps = [f"🔧 Executing {tool_name}"]
    turn_sources = list(state.get("turn_sources", []))
    turn_charts = list(state.get("turn_charts", []))
    result_text = f"Tool '{tool_name}' did not return a specific text output."
    error_flag = None

    try:
        # FIX: Make the tool definition lookup case-insensitive to handle LLM variations
        tool_def = next((t for t in state.get("available_tools_for_planner", []) if t.get("name", "").lower() == tool_name.lower()), None)
        
        # DEBUG: Print tool definition details
        print(f"DEBUG: Looking for tool '{tool_name}' in available tools")
        available_tools = state.get("available_tools_for_planner", [])
        print(f"DEBUG: Available tools: {[t.get('name', 'no-name') for t in available_tools]}")
        if tool_def:
            print(f"DEBUG: Found tool_def: {tool_def}")
            print(f"DEBUG: is_a2a_tool flag: {tool_def.get('is_a2a_tool')}")
        else:
            print(f"DEBUG: No tool_def found for '{tool_name}'")
            
        # FALLBACK: If tool not found in validated list, create minimal definition
        if not tool_def:
            print(f"DEBUG: Tool '{tool_name}' not found in validated tools, creating fallback definition")
            # Since tools are now validated during discovery, this should be rare
            # Use dynamic tool service to resolve tool information
            from dynamic_tool_service import get_tool_service
            tool_service = get_tool_service()
            
            # Try to resolve the tool dynamically
            skill_info = await tool_service.resolve_tool_name(tool_name, http_session)
            is_a2a_tool = skill_info is not None
            is_chart_tool = skill_info.is_chart_tool if skill_info else False
            
            tool_def = {
                "name": tool_name,
                "is_a2a_tool": is_a2a_tool,
                "is_chart_tool": is_chart_tool,
                "description": f"{'A2A agent' if is_a2a_tool else 'MCP'} tool: {tool_name} (fallback definition)",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
                "skill_id": skill_info.skill_id if skill_info else tool_name,
                "agent_id": skill_info.agent_id if skill_info else None
            }

        if tool_def and tool_def.get("is_a2a_tool"):
            # Determine tool type based on tags or skill characteristics
            is_chart_tool = tool_def.get("is_chart_tool", False)
            tool_type = "Chart Tool" if is_chart_tool else "A2A Tool"
            
            print(f"🤖 Calling A2A {tool_type}: {tool_name} with args {str(tool_args)[:80]}...")

            list_of_chart_specs, tool_message = await call_a2a_agent(
                http_session,
                # Pass the skill_id (not name) for proper routing
                tool_id=tool_def['skill_id'],
                payload=tool_args,
                conv_id=state.get("conversation_id", ""),
                thinking_steps=thinking_steps
            )

            # Handle chart tools (expect chart specs)
            if is_chart_tool:
                if list_of_chart_specs and isinstance(list_of_chart_specs, list):
                    chart_options_as_dicts = [spec.model_dump() for spec in list_of_chart_specs]
                    rebuilt_wrapper = {"chart_options": chart_options_as_dicts,
                                       "metadata": {"source": f"A2A Chart Tool: {tool_def['name']}"}}
                    turn_charts.append(rebuilt_wrapper)
                    result_text = f"{len(list_of_chart_specs)} chart(s) generated via {tool_def['name']}. Available in Images tab."
                    print(f"✅ {result_text}")
                else:
                    error_flag = f"A2A Chart tool '{tool_def['name']}' did not return a valid chart structure. Status: {tool_message}"
                    result_text = error_flag
                    print(f"❌ {error_flag}")
            else:
                # Handle non-chart A2A tools (expect text response)
                if "non-chart skill" in tool_message and "completed successfully" in tool_message:
                    result_text = f"A2A tool '{tool_def['name']}' executed successfully. {tool_message}"
                    print(f"✅ {result_text}")
                elif list_of_chart_specs is None and "completed successfully" in tool_message:
                    result_text = f"A2A tool '{tool_def['name']}' executed successfully. {tool_message}"
                    print(f"✅ {result_text}")
                else:
                    error_flag = f"A2A tool '{tool_def['name']}' execution failed. Status: {tool_message}"
                    result_text = error_flag
                    print(f"❌ {error_flag}")

        else:  # For general MCP tools like search_web
            print(f"🔧 Executing MCP Tool: {tool_name}...")
            tool_text_output, new_tool_sources, tool_message = await call_mcp_tool(http_session, tool_name, tool_args)

            if new_tool_sources:
                synthetic_result = f"{tool_text_output or ''}\n\nExtracted content from sources:\n".strip()
                for src in new_tool_sources[:3]:
                    synthetic_result += f"- {src.get('title', '')}: {src.get('snippet', '')}\n"
                result_text = synthetic_result.strip()
                turn_sources.extend(new_tool_sources)
                print(f"✅ Tool {tool_name} successful. Created synthetic result for LLM.")
            elif tool_text_output:
                result_text = tool_text_output
            else:
                error_flag = f"Tool '{tool_name}' returned no output. Status: {tool_message}"
                result_text = error_flag
                print(f"⚠️ {error_flag}")

    except Exception as e:
        error_flag = f"Exception during tool '{tool_name}' execution: {e}"
        result_text = error_flag
        traceback.print_exc()

    # MODIFIED: Append a dictionary to past_steps for richer data
    past_step_data = {
        "description": step_description,
        "result": result_text,
        "tool_name": tool_name,
        "thought": step_description  # Use description as thought for tool calls
    }

    return {
        "past_steps": [past_step_data],
        "thinking_steps": thinking_steps,
        "turn_sources": turn_sources,
        "turn_charts": turn_charts,
        "error_message": error_flag
    }


def prepare_current_step_for_execution_node(state: PlanExecuteAgentState) -> Dict[str, Any]:
    current_plan_list: List[PlanStep] = list(state.get("plan", []))
    thinking_steps = ["⚙️ Preparing next step"]
    if not current_plan_list:
        print("ℹ️ No more steps in plan")
        return {"current_step_to_execute": None, "plan": [], "thinking_steps": thinking_steps}
    step_to_execute_obj = current_plan_list[0]
    if step_to_execute_obj.tool_call_details:
        thinking_steps.append(f"🔧 Using {step_to_execute_obj.tool_call_details.tool_name}")
    return {
        "current_step_to_execute": step_to_execute_obj,
        "plan": current_plan_list[1:],
        "thinking_steps": thinking_steps
    }


async def execute_reasoning_step_node(state: PlanExecuteAgentState, config: RunnableConfig) -> Dict[str, Any]:
    step_to_execute = state.get("current_step_to_execute")
    if not step_to_execute:
        # MODIFIED: Return richer error step data
        error_step = {"description": "Reasoning Execution Error", "result": "No step details found.",
                      "tool_name": "reasoning", "thought": "System failed to provide a reasoning step."}
        return {"past_steps": [error_step], "error_message": "No step details found."}

    step_description = step_to_execute.description
    print(f"🧠 Reasoning: {step_description[:50]}...")
    reasoning_context = {
        "conversation_history": state.get("conversation_history", []),
        "past_steps": state.get("past_steps", []),
        "turn_sources": state.get("turn_sources", []),
        "turn_charts": state.get("turn_charts", []),
        "input": state.get("input")
    }
    try:
        raw_prompt_messages = create_reasoning_prompt(step_description, reasoning_context)
        gemini_sdk_contents = _format_messages_for_gemini(raw_prompt_messages)
        reasoning_response = await gemini_model.generate_content_async(gemini_sdk_contents,
                                                                       generation_config=genai.types.GenerationConfig(
                                                                           temperature=0.35))
        result_text = reasoning_response.text.strip()
    except Exception as e:
        result_text = f"Exception during reasoning: {e}"

    # MODIFIED: Append a dictionary to past_steps for richer data
    past_step_data = {
        "description": step_description,
        "result": result_text,
        "tool_name": "reasoning",
        "thought": result_text  # Use the reasoning output as the thought
    }

    return {"past_steps": [past_step_data], "thinking_steps": ["🧠 Reasoning complete"]}


def _generate_error_response_html(error_message: str) -> str:
    """
    Creates a formatted HTML response for an error message using the fallback utility.
    """
    fallback_output = create_fallback_response(
        UnifiedPlannerDecisionOutput,
        messages=[],
        error_context=f"An error occurred: {error_message}"
    )
    return fallback_output.response_summary_html or f"<p>An unexpected error occurred: {html.escape(error_message)}</p>"


def _generate_iteration_limit_response_html(executed_steps, turn_sources, turn_charts, max_iterations) -> str:
    """
    Generate a more comprehensive response when iteration limit is reached.
    """
    summary_parts = []
    if executed_steps:
        summary_parts.append("<h4>Actions Taken:</h4><ul>")
        # MODIFIED: Access dictionary key for step description
        for step in executed_steps[-3:]:
            desc = step.get('description', 'N/A')
            res = step.get('result', 'N/A')
            summary_parts.append(
                f"<li><strong>{html.escape(desc[:60])}...:</strong> {html.escape(str(res)[:150])}...</li>")
        summary_parts.append("</ul>")

    if turn_sources:
        summary_parts.append(f"<h4>Found {len(turn_sources)} sources.</h4>")

    if turn_charts:
        summary_parts.append(f"<h4>Generated {len(turn_charts)} chart(s).</h4>")

    summary_html = "".join(
        summary_parts) if summary_parts else "<p>No specific actions were completed before the limit was reached.</p>"

    return f"""<div class="response-container warning-response">
<h2>Processing Limit Reached</h2>
<p>I've reached the maximum number of processing steps ({max_iterations}) for this query. Here is a summary of my progress:</p>
{summary_html}
<p>Please try rephrasing your request, or ask a more specific follow-up question based on the information gathered.</p>
</div>"""


def _format_messages_for_gemini(raw_prompt_messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    gemini_sdk_contents = []
    system_instruction_accumulator = []
    for msg_dict in raw_prompt_messages:
        role, content = msg_dict.get("role"), msg_dict.get("content", "")
        if role == "system":
            system_instruction_accumulator.append(content)
        elif role == "user":
            full_user_content = "\n\n".join(
                system_instruction_accumulator) + "\n\n" + content if system_instruction_accumulator else content
            system_instruction_accumulator = []
            gemini_sdk_contents.append({'role': 'user', 'parts': [{'text': full_user_content.strip()}]})
        elif role == "assistant":
            if system_instruction_accumulator: print("Warning: System instructions before assistant message.")
            gemini_sdk_contents.append({'role': 'model', 'parts': [{'text': content.strip()}]})
    if system_instruction_accumulator:
        if gemini_sdk_contents and gemini_sdk_contents[-1]['role'] == 'user':
            gemini_sdk_contents[-1]['parts'][0]['text'] += "\n\n" + "\n\n".join(system_instruction_accumulator)
        else:
            gemini_sdk_contents.append(
                {'role': 'user', 'parts': [{'text': "\n\n".join(system_instruction_accumulator).strip()}]})
    return gemini_sdk_contents
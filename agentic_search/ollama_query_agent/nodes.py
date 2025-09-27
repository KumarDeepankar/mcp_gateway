import json
import logging
import re
from typing import Dict, Any, List
from .state_definition import SearchAgentState, PlanStep
from .ollama_client import ollama_client
from .mcp_tool_client import mcp_tool_client
from .prompts import (
    create_planning_prompt,
    create_reasoning_response_prompt,
    create_unified_planning_decision_prompt
)

logger = logging.getLogger(__name__)


def clean_json_response(response: str) -> str:
    """Clean JSON response by removing comments and other invalid JSON elements"""
    # Remove single-line comments (// ...)
    response = re.sub(r'//.*$', '', response, flags=re.MULTILINE)

    # Remove multi-line comments (/* ... */)
    response = re.sub(r'/\*.*?\*/', '', response, flags=re.DOTALL)

    # Remove trailing commas before closing brackets/braces
    response = re.sub(r',(\s*[}\]])', r'\1', response)

    # Clean up extra whitespace
    response = re.sub(r'\s+', ' ', response)
    response = response.strip()

    return response


async def initialize_search_node(state: SearchAgentState) -> SearchAgentState:
    """Initialize the search session"""
    logger.info(f"Initializing search for query: {state['input']}")

    # Initialize state
    state["thinking_steps"] = state.get("thinking_steps", [])
    state["current_step_index"] = 0
    state["final_response_generated_flag"] = False
    state["final_response_content"] = None
    state["search_results"] = []
    state["tool_execution_results"] = []
    state["error_message"] = None

    # Initialize iteration control (matching agentic_assistant naming)
    state["current_turn_iteration_count"] = 0
    state["max_turn_iterations"] = 5  # Reasonable limit to prevent infinite loops

    # Initialize conversation history if not present
    state["conversation_history"] = state.get("conversation_history", [])
    state["is_followup_query"] = state.get("is_followup_query", False)

    # Add thinking step
    if state["is_followup_query"]:
        state["thinking_steps"].append("🔄 Followup query initialized - using conversation context")
        if state["conversation_history"]:
            state["thinking_steps"].append(f"📚 Found {len(state['conversation_history'])} previous conversation turns")
    else:
        state["thinking_steps"].append("🚀 Search initialized")

    return state


async def discover_tools_node(state: SearchAgentState) -> SearchAgentState:
    """Discover available tools from MCP registry"""
    logger.info("Discovering available tools from MCP registry")

    try:
        # Fetch available tools
        available_tools = await mcp_tool_client.get_available_tools()
        state["available_tools"] = available_tools

        # If no enabled tools specified, use all available tools
        if not state.get("enabled_tools"):
            state["enabled_tools"] = [tool.get("name", "") for tool in available_tools]

        state["thinking_steps"].append(f"🔍 Discovered {len(available_tools)} tools from MCP registry")
        if state["enabled_tools"]:
            state["thinking_steps"].append(f"✅ Enabled tools: {', '.join(state['enabled_tools'])}")
        else:
            state["thinking_steps"].append("⚠️ No tools enabled by user - using all available tools")

    except Exception as e:
        logger.error(f"Error discovering tools: {e}")
        state["error_message"] = f"Failed to discover tools: {str(e)}"
        state["available_tools"] = []
        state["enabled_tools"] = []

    return state


async def planning_node(state: SearchAgentState) -> SearchAgentState:
    """Create a search plan using available tools"""
    logger.info("Creating search plan")

    try:
        # Create planning prompt with conversation history
        prompt = create_planning_prompt(
            state["input"],
            state.get("available_tools", []),
            state.get("enabled_tools", []),
            state.get("conversation_history", [])
        )

        # Get plan from Ollama
        system_prompt = """You are a search planning assistant. Create plans that PRIORITIZE TOOL USAGE for factual information.

CRITICAL GUIDELINES - NO HALLUCINATION:
1. MANDATORY: Use enabled tools to gather factual information
2. DO NOT create plans that rely on assumptions or general knowledge
3. Create specific, targeted search queries for search tools
4. Always prefer TOOL_CALL over REASONING_STEP when tools are available
5. Break complex queries into focused, factual searches
6. Respond ONLY with valid JSON containing a tool-focused plan
7. If no tools are enabled, state that tools are required for factual answers"""
        response = await ollama_client.generate_response(prompt, system_prompt)

        # Clean and parse the response
        try:
            # Clean the response - extract JSON if wrapped in other text
            response = response.strip()
            if not response:
                raise json.JSONDecodeError("Empty response", "", 0)

            # Find JSON boundaries
            start_idx = response.find('{')
            end_idx = response.rfind('}')

            if start_idx == -1 or end_idx == -1:
                # No JSON found, create a simple plan
                state["thinking_steps"].append("No JSON found in response, creating fallback plan")
                plan_steps = [
                    PlanStep(
                        step_number=1,
                        step_type="REASONING_STEP",
                        description=f"Analyze the query: {state['input']}",
                        reasoning_content=f"Think about the query: {state['input']}"
                    )
                ]
            else:
                json_str = response[start_idx:end_idx+1]

                # Clean JSON comments and invalid syntax
                cleaned_json = clean_json_response(json_str)

                plan_data = json.loads(cleaned_json)
                plan_steps = []

                for step_data in plan_data.get("plan", []):
                    # Only add steps with valid tool names or reasoning steps
                    step_type = step_data.get("step_type", "REASONING_STEP")
                    tool_name = step_data.get("tool_name")

                    # Skip invalid tool calls with placeholder names
                    if (step_type == "TOOL_CALL" and
                        (not tool_name or
                         "placeholder" in tool_name.lower() or
                         tool_name not in state.get("enabled_tools", []))):
                        continue

                    plan_step = PlanStep(
                        step_number=step_data.get("step_number", 0),
                        step_type=step_type,
                        description=step_data.get("description", ""),
                        tool_name=tool_name,
                        tool_arguments=step_data.get("tool_arguments") or step_data.get("arguments"),
                        reasoning_content=step_data.get("reasoning_content")
                    )
                    plan_steps.append(plan_step)

            state["plan"] = plan_steps
            state["thinking_steps"].append(f"📋 Created plan with {len(plan_steps)} steps")

            # Add plan summary
            for i, step in enumerate(plan_steps[:3], 1):  # Show first 3 steps
                step_desc = step.description[:80] + "..." if len(step.description) > 80 else step.description
                state["thinking_steps"].append(f"  {i}. {step.step_type}: {step_desc}")

            if len(plan_steps) > 3:
                state["thinking_steps"].append(f"  ... and {len(plan_steps) - 3} more steps")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}")
            logger.error(f"Raw response: {response}")
            # Create fallback plan
            plan_steps = [
                PlanStep(
                    step_number=1,
                    step_type="REASONING_STEP",
                    description=f"Answer the query: {state['input']}",
                    reasoning_content=f"Provide a direct answer to: {state['input']}"
                )
            ]
            state["plan"] = plan_steps

    except Exception as e:
        logger.error(f"Error in planning: {e}")
        state["error_message"] = f"Planning failed: {str(e)}"

    return state


async def prepare_next_step_node(state: SearchAgentState) -> SearchAgentState:
    """Prepare the next step for execution"""
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)

    if current_index < len(plan):
        current_step = plan[current_index]
        state["current_step_to_execute"] = current_step
        state["thinking_steps"].append(f"⚙️ Preparing step {current_index + 1}/{len(plan)}: {current_step.description}")
        state["thinking_steps"].append(f"🎯 Step type: {current_step.step_type}")
    else:
        # No more steps, move to final response
        state["current_step_to_execute"] = None
        state["thinking_steps"].append("All steps completed, generating final response")

    return state


async def execute_tool_step_node(state: SearchAgentState) -> SearchAgentState:
    """Execute a tool call step"""
    current_step = state.get("current_step_to_execute")

    if not current_step or current_step.step_type != "TOOL_CALL":
        state["error_message"] = "Invalid tool step"
        return state

    try:
        state["thinking_steps"].append(f"🔧 Executing tool: {current_step.tool_name}")

        # Add argument details if available
        if current_step.tool_arguments:
            arg_summary = ", ".join([f"{k}={str(v)[:50]}..." if len(str(v)) > 50 else f"{k}={v}"
                                   for k, v in current_step.tool_arguments.items()])
            state["thinking_steps"].append(f"📋 Tool arguments: {arg_summary}")

        # Call the tool via MCP
        state["thinking_steps"].append(f"📡 Calling MCP service for {current_step.tool_name}")
        result = await mcp_tool_client.call_tool(
            current_step.tool_name,
            current_step.tool_arguments or {}
        )

        # Store the result
        execution_result = {
            "step_number": current_step.step_number,
            "tool_name": current_step.tool_name,
            "arguments": current_step.tool_arguments,
            "result": result
        }

        state["tool_execution_results"].append(execution_result)

        # Add result summary
        result_summary = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
        state["thinking_steps"].append(f"✅ Tool {current_step.tool_name} executed successfully")
        state["thinking_steps"].append(f"📊 Result summary: {result_summary}")

        # Move to next step
        state["current_step_index"] = state.get("current_step_index", 0) + 1

    except Exception as e:
        logger.error(f"Error executing tool step: {e}")
        state["error_message"] = f"Tool execution failed: {str(e)}"

    return state


async def execute_unified_reasoning_and_response_node(state: SearchAgentState) -> SearchAgentState:
    """Execute reasoning step and potentially generate final response if sufficient information is available"""
    current_step = state.get("current_step_to_execute")

    if not current_step or current_step.step_type != "REASONING_STEP":
        state["error_message"] = "Invalid reasoning step"
        return state

    try:
        state["thinking_steps"].append(f"Performing unified reasoning and assessment: {current_step.description}")

        # Create context for reasoning
        context = {
            "user_query": state["input"],
            "tool_results": state.get("tool_execution_results", []),
            "search_results": state.get("search_results", []),
            "thinking_steps": state.get("thinking_steps", [])
        }

        # Get unified reasoning and potential response from Ollama
        prompt = create_reasoning_response_prompt(
            user_query=state["input"],
            search_results=state.get("search_results", []),
            tool_results=state.get("tool_execution_results", []),
            conversation_history=state.get("conversation_history", []),
            current_step_description=current_step.reasoning_content or current_step.description,
            additional_context=context
        )

        unified_result = await ollama_client.generate_response(prompt)

        # Parse the response to extract analysis, assessment, and potential final response
        analysis_section = ""
        assessment_section = ""
        response_section = ""

        # Simple parsing based on the expected format
        sections = unified_result.split("**Assessment:**")
        if len(sections) >= 2:
            analysis_section = sections[0].replace("**Analysis:**", "").strip()

            remaining = sections[1].split("**Response:**")
            if len(remaining) >= 2:
                assessment_section = remaining[0].strip()
                response_section = remaining[1].strip()
            else:
                assessment_section = remaining[0].strip()
        else:
            # Fallback if format is not followed
            analysis_section = unified_result

        # Store reasoning result
        reasoning_entry = {
            "step_number": current_step.step_number,
            "reasoning_task": current_step.description,
            "analysis": analysis_section
        }

        state["search_results"].append(reasoning_entry)
        state["thinking_steps"].append(f"🧠 Reasoning step completed")

        # Add analysis summary
        analysis_preview = analysis_section[:150] + "..." if len(analysis_section) > 150 else analysis_section
        state["thinking_steps"].append(f"💭 Analysis preview: {analysis_preview}")

        # Check if a final response was generated
        if response_section and ("final answer" in assessment_section.lower() or
                                "sufficient information" in assessment_section.lower() or
                                "comprehensive" in response_section.lower()):
            # Mark that final response is ready
            state["final_response_content"] = response_section
            state["final_response_generated_flag"] = True
            state["thinking_steps"].append("✨ Assessment complete - sufficient information available")
            state["thinking_steps"].append("🎯 Generated final response based on available information")
        else:
            # Move to next step if no final response was generated
            state["current_step_index"] = state.get("current_step_index", 0) + 1
            state["thinking_steps"].append("🔄 Assessment complete - need more information")
            state["thinking_steps"].append("➡️ Continuing with plan execution")

    except Exception as e:
        logger.error(f"Error in unified reasoning step: {e}")
        state["error_message"] = f"Unified reasoning failed: {str(e)}"

    return state


async def unified_planning_decision_node(state: SearchAgentState) -> SearchAgentState:
    """Unified node that handles planning, decision-making, and response generation"""
    current_iteration = state.get("current_turn_iteration_count", 0) + 1
    max_iterations = state.get("max_turn_iterations", 5)

    logger.info(f"🤔 Planning iteration {current_iteration}/{max_iterations}")

    if current_iteration > max_iterations:
        logger.info(f"⏰ Reached iteration limit ({max_iterations})")
        state["thinking_steps"].append("🔄 Generating summary")

        try:
            # Try to generate final response using existing prompt
            prompt = create_reasoning_response_prompt(
                user_query=state["input"],
                search_results=state.get("search_results", []),
                tool_results=state.get("tool_execution_results", []),
                conversation_history=state.get("conversation_history", [])
            )

            final_response = await ollama_client.generate_response(prompt)
            state["final_response_content"] = final_response
            state["final_response_generated_flag"] = True
            state["current_turn_iteration_count"] = current_iteration
            return state
        except Exception as e:
            logger.error(f"❌ Error generating summary: {str(e)}")
            # Generate fallback response
            final_response = generate_final_response_from_available_data(state)
            state["final_response_content"] = final_response
            state["final_response_generated_flag"] = True
            state["current_turn_iteration_count"] = current_iteration
            return state

    try:
        # Prepare executed steps for context
        executed_steps = []
        if state.get("tool_execution_results"):
            for i, result in enumerate(state["tool_execution_results"]):
                executed_steps.append({
                    "step_number": i + 1,
                    "type": "tool_execution",
                    "result": result
                })

        # Convert current plan to serializable format
        current_plan = state.get("plan", [])
        serializable_plan = []
        for step in current_plan:
            if hasattr(step, 'model_dump'):  # Pydantic model
                serializable_plan.append(step.model_dump())
            elif hasattr(step, '__dict__'):  # Regular object
                serializable_plan.append(step.__dict__)
            else:  # Already a dict
                serializable_plan.append(step)

        # Create unified prompt
        prompt = create_unified_planning_decision_prompt(
            user_query=state["input"],
            search_results=state.get("search_results", []),
            tool_results=state.get("tool_execution_results", []),
            available_tools=state.get("available_tools", []),
            enabled_tools=state.get("enabled_tools", []),
            executed_steps=executed_steps,
            conversation_history=state.get("conversation_history", []),
            current_plan=serializable_plan
        )

        # Get decision from Ollama
        system_prompt = """You are a unified planning and decision agent. PRIORITIZE TOOL USAGE for factual information.

CRITICAL RULES:
1. DO NOT make up information or hallucinate
2. Use available tools to gather factual information
3. Only generate final response when you have verified, factual information from tools
4. Create specific, targeted search queries for search tools
5. Respond with valid JSON only"""

        response = await ollama_client.generate_response(prompt, system_prompt)

        # Parse the response
        try:
            # Clean and parse JSON response
            response = response.strip()
            start_idx = response.find('{')
            end_idx = response.rfind('}')

            if start_idx == -1 or end_idx == -1:
                raise json.JSONDecodeError("No valid JSON found", "", 0)

            json_str = response[start_idx:end_idx + 1]
            decision_data = json.loads(json_str)

            decision_type = decision_data.get("decision_type")
            reasoning = decision_data.get("reasoning", "")

            state["thinking_steps"].append(f"🤔 Decision: {decision_type} - {reasoning}")

            if decision_type == "GENERATE_RESPONSE":
                # Generate final response
                final_response = decision_data.get("final_response", "")
                if not final_response:
                    raise ValueError("Final response is empty")

                state["final_response_content"] = final_response
                state["final_response_generated_flag"] = True
                state["thinking_steps"].append("✅ Generated final response")

                # Store conversation history
                from datetime import datetime
                new_turn = {
                    "query": state["input"],
                    "response": final_response,
                    "timestamp": datetime.now().isoformat(),
                    "tool_results": state.get("tool_execution_results", [])
                }

                if "conversation_history" not in state:
                    state["conversation_history"] = []
                state["conversation_history"].append(new_turn)
                state["conversation_history"] = state["conversation_history"][-10:]

            elif decision_type in ["PLAN_AND_EXECUTE", "EXECUTE_NEXT_STEP"]:
                # Update plan
                plan_data = decision_data.get("plan", [])
                if plan_data:
                    # Convert to PlanStep objects
                    plan_steps = []
                    for step_data in plan_data:
                        step = PlanStep(
                            step_number=step_data.get("step_number", 1),
                            step_type=step_data.get("step_type", "REASONING_STEP"),
                            description=step_data.get("description", ""),
                            tool_name=step_data.get("tool_name"),
                            tool_arguments=step_data.get("tool_arguments"),
                            reasoning_content=step_data.get("reasoning_content")
                        )
                        plan_steps.append(step)

                    state["plan"] = plan_steps
                    state["current_step_index"] = 0
                    state["thinking_steps"].append(f"📋 Updated plan with {len(plan_steps)} steps")
                else:
                    state["error_message"] = "Decision to plan but no plan provided"
            else:
                state["error_message"] = f"Unknown decision type: {decision_type}"

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Error parsing unified decision response: {e}")
            # Fallback: try to generate direct response
            fallback_prompt = create_reasoning_response_prompt(
                user_query=state["input"],
                search_results=state.get("search_results", []),
                tool_results=state.get("tool_execution_results", []),
                conversation_history=state.get("conversation_history", [])
            )

            fallback_response = await ollama_client.generate_response(fallback_prompt)
            state["final_response_content"] = fallback_response
            state["final_response_generated_flag"] = True
            state["thinking_steps"].append("⚠️ Fallback: Generated direct response due to parsing error")

    except Exception as e:
        logger.error(f"Error in unified planning decision: {e}")
        state["error_message"] = f"Failed in unified planning: {str(e)}"

    # Always update the iteration count
    state["current_turn_iteration_count"] = current_iteration
    return state


async def generate_final_response_node(state: SearchAgentState) -> SearchAgentState:
    """Generate the final response (kept for backward compatibility)"""
    logger.info("Generating final response")

    try:
        # Create final response prompt with conversation context for followup queries
        prompt = create_reasoning_response_prompt(
            user_query=state["input"],
            search_results=state.get("search_results", []),
            tool_results=state.get("tool_execution_results", []),
            conversation_history=state.get("conversation_history", [])
        )

        # Generate complete response as string (not streaming for state storage)
        final_response = await ollama_client.generate_response(prompt)

        state["final_response_content"] = final_response
        state["final_response_generated_flag"] = True
        state["thinking_steps"].append("Generated final response")

        # Store this query-response pair in conversation history for future followup queries
        from datetime import datetime
        new_turn = {
            "query": state["input"],
            "response": final_response,
            "timestamp": datetime.now().isoformat(),
            "tool_results": state.get("tool_execution_results", [])
        }

        # Initialize conversation_history if it doesn't exist and add the new turn
        if "conversation_history" not in state:
            state["conversation_history"] = []
        state["conversation_history"].append(new_turn)

        # Keep only the last 10 conversation turns to prevent context from growing too large
        state["conversation_history"] = state["conversation_history"][-10:]

    except Exception as e:
        logger.error(f"Error generating final response: {e}")
        state["error_message"] = f"Failed to generate response: {str(e)}"

    return state


def generate_final_response_from_available_data(state: SearchAgentState) -> str:
    """Generate a final response when iteration limit is reached"""
    query = state.get("input", "")
    search_results = state.get("search_results", [])
    tool_results = state.get("tool_execution_results", [])
    conversation_history = state.get("conversation_history", [])

    # Create a summary of what was accomplished
    response_parts = []

    # Include conversation context for followup queries
    if conversation_history:
        response_parts.append(f"Building on our previous conversation, I've reached the iteration limit while processing your followup query: '{query}'\n")
    else:
        response_parts.append(f"I've reached the iteration limit while processing your query: '{query}'\n")

    if tool_results:
        response_parts.append("Here's what I was able to gather:")
        for i, result in enumerate(tool_results):
            response_parts.append(f"\n{i+1}. {result.get('summary', 'Tool execution result available')}")

    if search_results:
        response_parts.append("\nSearch results found:")
        for i, result in enumerate(search_results[:3]):  # Show first 3 results
            response_parts.append(f"\n{i+1}. {result.get('title', 'Search result')}")

    if not tool_results and not search_results:
        if conversation_history:
            response_parts.append("I wasn't able to gather additional specific information, but I can provide a response based on our conversation context and my knowledge.")
        else:
            response_parts.append("I wasn't able to gather specific information, but I can provide a general response based on my knowledge.")

    if conversation_history:
        response_parts.append("\nBased on our conversation history, you may want to ask a more specific followup question to get the detailed information you need.")
    else:
        response_parts.append("\nI apologize that I couldn't complete the full analysis within the processing limits. If you need more specific information, please try refining your query or ask a follow-up question.")

    return "\n".join(response_parts)
import json
import logging
import re
from typing import Dict, Any, List
from datetime import datetime
from .state_definition import SearchAgentState, PlanStep
from .ollama_client import ollama_client
from .mcp_tool_client import mcp_tool_client
from .prompts import (
    create_reasoning_response_prompt,
    create_unified_planning_decision_prompt
)

logger = logging.getLogger(__name__)


def strip_html_to_text(html_content: str) -> str:
    """Convert HTML response to plain text for storage"""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_content)
    # Decode HTML entities
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    # Clean up multiple spaces and newlines
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


def save_conversation_turn(state: SearchAgentState, response: str) -> None:
    """Save a conversation turn to history - only user query and plain text response"""
    # Convert HTML response to plain text for storage
    plain_text_response = strip_html_to_text(response)

    new_turn = {
        "query": state["input"],
        "response": plain_text_response
    }

    if "conversation_history" not in state:
        state["conversation_history"] = []
    state["conversation_history"].append(new_turn)
    state["conversation_history"] = state["conversation_history"][-10:]  # Keep last 10 turns

    print(f"[DEBUG] Saved conversation turn. Total history: {len(state['conversation_history'])} turns")


def clean_json_response(response: str) -> str:
    """Clean JSON response by removing comments and other invalid JSON elements"""
    # First, handle encoding and invisible characters
    # Remove BOM and other invisible Unicode characters
    response = response.encode('utf-8', errors='ignore').decode('utf-8')

    # Remove zero-width characters and other problematic Unicode
    invisible_chars = [
        '\u200b',  # zero-width space
        '\u200c',  # zero-width non-joiner
        '\u200d',  # zero-width joiner
        '\u2060',  # word joiner
        '\ufeff',  # BOM
        '\u00a0',  # non-breaking space
    ]
    for char in invisible_chars:
        response = response.replace(char, '')

    # Remove any control characters except standard whitespace
    response = ''.join(char for char in response if ord(char) >= 32 or char in ['\n', '\r', '\t'])

    # Remove single-line comments (// ...)
    response = re.sub(r'//.*$', '', response, flags=re.MULTILINE)

    # Remove multi-line comments (/* ... */)
    response = re.sub(r'/\*.*?\*/', '', response, flags=re.DOTALL)

    # Remove trailing commas before closing brackets/braces
    response = re.sub(r',(\s*[}\]])', r'\1', response)

    # Fix common JSON issues
    # Remove trailing commas in arrays and objects (double-check)
    response = re.sub(r',(\s*[}\]])', r'\1', response)

    # Fix missing quotes around keys (common LLM mistake) - only if not already quoted
    response = re.sub(r'([^"]|^)(\w+)(\s*:\s*)', r'\1"\2"\3', response)

    # Fix single quotes to double quotes (but be careful with content)
    # Only replace quotes that are likely to be JSON quotes, not content quotes
    response = re.sub(r"'(\w+)'(\s*:)", r'"\1"\2', response)  # Keys
    response = re.sub(r":\s*'([^']*)'", r': "\1"', response)   # String values

    # Fix common boolean/null values
    response = re.sub(r'\btrue\b', 'true', response, flags=re.IGNORECASE)
    response = re.sub(r'\bfalse\b', 'false', response, flags=re.IGNORECASE)
    response = re.sub(r'\bnull\b', 'null', response, flags=re.IGNORECASE)

    # Normalize whitespace but preserve structure
    response = re.sub(r'[ \t]+', ' ', response)  # Multiple spaces/tabs to single space
    response = re.sub(r'\n\s*\n', '\n', response)  # Multiple newlines to single
    response = response.strip()

    return response


def validate_json_structure(json_str: str) -> bool:
    """Pre-validate JSON structure before parsing"""
    try:
        # Basic structure checks
        if not json_str.strip().startswith('{') or not json_str.strip().endswith('}'):
            return False

        # Count braces
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        if open_braces != close_braces:
            return False

        # Count brackets
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        if open_brackets != close_brackets:
            return False

        # Count quotes (should be even)
        quote_count = json_str.count('"')
        if quote_count % 2 != 0:
            return False

        return True
    except:
        return False


def extract_json_from_response(response: str) -> dict:
    """Extract and parse JSON from LLM response with robust error handling"""
    try:
        # First try to find JSON block
        response = response.strip()

        # Look for JSON between code blocks - multiple patterns for robustness
        patterns = [
            r'```json\s*\n?(.*?)\n?```',  # ```json block
            r'```\s*\n?(.*?)\n?```',      # generic ``` block
            r'`(.*?)`',                   # single backticks
        ]

        for pattern in patterns:
            json_match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if json_match:
                candidate = json_match.group(1).strip()
                # Only use if it looks like JSON
                if candidate.startswith('{') and '}' in candidate:
                    response = candidate
                    break

        # Find the outermost JSON object
        start_idx = response.find('{')
        if start_idx == -1:
            raise ValueError("No JSON object found in response")

        # Find matching closing brace
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(response)):
            if response[i] == '{':
                brace_count += 1
            elif response[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break

        if end_idx == -1:
            # Fallback: use rfind
            end_idx = response.rfind('}')
            if end_idx == -1:
                raise ValueError("No closing brace found")

        json_str = response[start_idx:end_idx + 1]

        # Pre-validate structure
        if not validate_json_structure(json_str):
            raise ValueError("JSON structure validation failed")

        # Clean the JSON string
        json_str = clean_json_response(json_str)

        # Final validation after cleaning
        if not validate_json_structure(json_str):
            raise ValueError("JSON structure validation failed after cleaning")

        # Parse JSON
        return json.loads(json_str)

    except json.JSONDecodeError as e:
        # Try more aggressive cleaning
        try:
            # Remove extra text around JSON
            lines = response.split('\n')
            json_lines = []
            in_json = False

            for line in lines:
                line = line.strip()
                if line.startswith('{') or in_json:
                    in_json = True
                    json_lines.append(line)
                    if line.endswith('}') and line.count('}') >= line.count('{'):
                        break

            if json_lines:
                json_str = ' '.join(json_lines)
                json_str = clean_json_response(json_str)
                return json.loads(json_str)

        except:
            pass

        raise ValueError(f"Failed to parse JSON: {str(e)}")

    except Exception as e:
        raise ValueError(f"Failed to extract JSON: {str(e)}")


async def initialize_search_node(state: SearchAgentState) -> SearchAgentState:
    """Initialize the search session"""
    logger.info(f"Initializing search for query: {state['input']}")

    # Initialize state
    state["thinking_steps"] = state.get("thinking_steps", [])
    state["current_step_index"] = 0
    state["final_response_generated_flag"] = False
    state["final_response_content"] = None
    state["tool_execution_results"] = []
    state["error_message"] = None

    # Initialize iteration control (matching agentic_assistant naming)
    state["current_turn_iteration_count"] = 0
    state["max_turn_iterations"] = 1  # Reasonable limit to prevent infinite loops

    # Initialize conversation history if not present
    state["conversation_history"] = state.get("conversation_history", [])
    state["is_followup_query"] = state.get("is_followup_query", False)

    # Enhanced thinking steps for streaming UI
    state["thinking_steps"].append("🚀 Initializing Agentic Search Agent")
    state["thinking_steps"].append(f"📝 Query: '{state['input']}'")

    if state["is_followup_query"]:
        state["thinking_steps"].append("🔄 Followup query detected - loading conversation context")
        if state["conversation_history"]:
            state["thinking_steps"].append(f"📚 Found {len(state['conversation_history'])} previous conversation turns")
            # Show latest context
            if state["conversation_history"]:
                latest = state["conversation_history"][-1]
                preview = latest.get("response", "")[:100] + "..." if len(latest.get("response", "")) > 100 else latest.get("response", "")
                state["thinking_steps"].append(f"💭 Previous context: {preview}")
    else:
        state["thinking_steps"].append("🆕 Fresh search session started")

    state["thinking_steps"].append(f"⚙️ Session config: Max iterations = {state['max_turn_iterations']}")
    state["thinking_steps"].append("✅ Search session initialized successfully")

    print(f"[DEBUG initialize_search_node] conversation_history: {state['conversation_history']}")
    print(f"[DEBUG initialize_search_node] is_followup_query: {state['is_followup_query']}")
    print(f"[DEBUG initialize_search_node] conversation_id: {state.get('conversation_id')}")

    return state


async def discover_tools_node(state: SearchAgentState) -> SearchAgentState:
    """Discover available tools from MCP registry"""
    logger.info("Discovering available tools from MCP registry")

    state["thinking_steps"].append("🔍 Connecting to MCP Registry...")
    state["thinking_steps"].append("📡 Querying available tools from port 8021")

    try:
        # Fetch available tools
        state["thinking_steps"].append("⏳ Fetching tool definitions...")
        available_tools = await mcp_tool_client.get_available_tools()
        state["available_tools"] = available_tools

        state["thinking_steps"].append(f"📊 Discovered {len(available_tools)} tools from MCP registry")

        # Show discovered tools for visibility
        if available_tools:
            tool_names = [tool.get("name", "unknown") for tool in available_tools]
            state["thinking_steps"].append(f"🛠️ Available tools: {', '.join(tool_names[:5])}" +
                                         (f" and {len(tool_names)-5} more..." if len(tool_names) > 5 else ""))

        # If no enabled tools specified, use all available tools
        if not state.get("enabled_tools"):
            state["enabled_tools"] = [tool.get("name", "") for tool in available_tools]
            state["thinking_steps"].append("⚙️ No specific tool selection - enabling all available tools")
        else:
            state["thinking_steps"].append(f"🎯 User-selected tools: {', '.join(state['enabled_tools'])}")

        state["thinking_steps"].append("✅ Tool discovery completed successfully")

    except Exception as e:
        logger.error(f"Error discovering tools: {e}")
        state["thinking_steps"].append(f"❌ Tool discovery failed: {str(e)}")
        state["thinking_steps"].append("🔄 Continuing with empty tool set")
        state["error_message"] = f"Failed to discover tools: {str(e)}"
        state["available_tools"] = []
        state["enabled_tools"] = []

    return state


async def execute_tool_step_node(state: SearchAgentState) -> SearchAgentState:
    """Execute the next tool call step from the plan"""
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)

    if current_index >= len(plan):
        state["error_message"] = "No more steps to execute"
        return state

    current_step = plan[current_index]

    try:
        # Execute tool call
        state["thinking_steps"].append(f"🔧 Executing step {current_index + 1}/{len(plan)}: {current_step.tool_name}")

        # Add argument details if available
        if current_step.tool_arguments:
            arg_summary = ", ".join([f"{k}={str(v)[:50]}..." if len(str(v)) > 50 else f"{k}={v}"
                                   for k, v in current_step.tool_arguments.items()])
            state["thinking_steps"].append(f"📋 Arguments: {arg_summary}")

        # Call the tool via MCP
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
        state["thinking_steps"].append(f"✅ Tool executed successfully")
        state["thinking_steps"].append(f"📊 Result: {result_summary}")

        # Move to next step
        state["current_step_index"] = current_index + 1

    except Exception as e:
        logger.error(f"Error executing step: {e}")
        state["error_message"] = f"Step execution failed: {str(e)}"

    return state



async def unified_planning_decision_node(state: SearchAgentState) -> SearchAgentState:
    """Unified node that handles planning, decision-making, and response generation"""
    current_iteration = state.get("current_turn_iteration_count", 0) + 1
    max_iterations = state.get("max_turn_iterations", 5)

    logger.info(f"🤔 Planning iteration {current_iteration}/{max_iterations}")

    # Enhanced thinking steps for planning visibility
    state["thinking_steps"].append(f"🤔 Planning & Decision Phase - Iteration {current_iteration}/{max_iterations}")
    state["thinking_steps"].append("📊 Analyzing current information gathered...")

    # Show current state for transparency
    tool_results_count = len(state.get("tool_execution_results", []))
    state["thinking_steps"].append(f"🔧 Tool executions completed: {tool_results_count}")

    if current_iteration > max_iterations:
        logger.info(f"⏰ Reached iteration limit ({max_iterations})")
        state["thinking_steps"].append(f"⏰ Reached maximum iterations ({max_iterations})")
        state["thinking_steps"].append("📝 Generating summary response with available information")

        try:
            # Try to generate final response using existing prompt
            prompt = create_reasoning_response_prompt(
                user_query=state["input"],
                tool_results=state.get("tool_execution_results", []),
                conversation_history=state.get("conversation_history", [])
            )

            final_response = await ollama_client.generate_response(prompt)
            state["final_response_content"] = final_response
            state["final_response_generated_flag"] = True
            state["current_turn_iteration_count"] = current_iteration

            # Save conversation history
            save_conversation_turn(state, final_response)

            return state
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            final_response = generate_final_response_from_available_data(state)
            state["final_response_content"] = final_response
            state["final_response_generated_flag"] = True
            state["current_turn_iteration_count"] = current_iteration

            # Save conversation history
            save_conversation_turn(state, final_response)

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

        # Filter to only enabled tools for planning
        enabled_tool_names = state.get("enabled_tools", [])
        all_tools = state.get("available_tools", [])
        enabled_tools_only = [
            tool for tool in all_tools
            if tool.get("name") in enabled_tool_names
        ]

        print(f"[DEBUG] Total available tools: {len(all_tools)}")
        print(f"[DEBUG] User-enabled tools: {enabled_tool_names}")
        print(f"[DEBUG] Passing {len(enabled_tools_only)} tools to LLM for planning")

        # Create unified prompt
        prompt = create_unified_planning_decision_prompt(
            user_query=state["input"],
            tool_results=state.get("tool_execution_results", []),
            enabled_tools=enabled_tools_only,
            executed_steps=executed_steps,
            conversation_history=state.get("conversation_history", []),
            current_plan=serializable_plan
        )

        # Get decision from Ollama
        state["thinking_steps"].append("🤖 Consulting AI for planning decision...")
        state["thinking_steps"].append("📋 Analyzing query requirements vs available information")

        system_prompt = """You are a planning agent. Respond with valid JSON only.

CRITICAL RULES:
1. No information? Create a plan with TOOL_CALL steps ONLY
2. Have tool results? Generate final HTML response
3. Valid JSON only - no comments, no extra text
4. NEVER use "REASONING_STEP" - ONLY "TOOL_CALL" with a tool_name

FORMAT:
Planning: {"decision_type": "PLAN_AND_EXECUTE", "reasoning": "why", "plan": [{"step_number": 1, "step_type": "TOOL_CALL", "tool_name": "search_stories", "description": "...", "tool_arguments": {...}}]}
Response: {"decision_type": "GENERATE_RESPONSE", "reasoning": "why", "final_response": "<div>...</div>"}

Every plan step MUST have "step_type": "TOOL_CALL" and a valid "tool_name"."""

        state["thinking_steps"].append("⏳ Generating planning decision (this may take a moment)...")
        response = await ollama_client.generate_response(prompt, system_prompt)
        state["thinking_steps"].append("✅ Received planning decision from AI")

        # Parse the response
        try:
            state["thinking_steps"].append("🔍 Parsing AI decision response...")
            # Use improved JSON extraction
            decision_data = extract_json_from_response(response)
            state["thinking_steps"].append("✅ Successfully parsed AI decision")

            decision_type = decision_data.get("decision_type")
            reasoning = decision_data.get("reasoning", "")

            # Debug information
            if not decision_type:
                logger.error(f"No decision_type found in response. Keys: {list(decision_data.keys())}")
                state["thinking_steps"].append(f"⚠️ No decision_type found. Available keys: {list(decision_data.keys())}")

                # Try to infer decision type from available keys
                if "plan" in decision_data and decision_data.get("plan"):
                    decision_type = "PLAN_AND_EXECUTE"
                    state["thinking_steps"].append("🔧 Inferred decision_type as PLAN_AND_EXECUTE based on plan presence")
                elif "final_response" in decision_data and decision_data.get("final_response"):
                    decision_type = "GENERATE_RESPONSE"
                    state["thinking_steps"].append("🔧 Inferred decision_type as GENERATE_RESPONSE based on final_response presence")
                else:
                    decision_type = "PLAN_AND_EXECUTE"
                    state["thinking_steps"].append("🔧 Defaulting to PLAN_AND_EXECUTE")

            state["thinking_steps"].append(f"📋 Decision received: {decision_type}")
            state["thinking_steps"].append(f"💭 Reasoning: {reasoning}")

            if decision_type == "GENERATE_RESPONSE":
                # Generate final response
                state["thinking_steps"].append("✨ Sufficient information available - generating final response")
                final_response = decision_data.get("final_response", "")
                if not final_response:
                    raise ValueError("Final response is empty")

                state["final_response_content"] = final_response
                state["final_response_generated_flag"] = True
                state["thinking_steps"].append("✅ Final response generated successfully")
                state["thinking_steps"].append("💾 Saving conversation to history")

                # Save conversation history using helper function
                save_conversation_turn(state, final_response)

            elif decision_type in ["PLAN_AND_EXECUTE", "EXECUTE_NEXT_STEP"]:
                # Update plan
                state["thinking_steps"].append("📝 Need more information - creating execution plan")
                plan_data = decision_data.get("plan", [])
                if plan_data:
                    state["thinking_steps"].append(f"🔧 Received plan with {len(plan_data)} steps")

                    # Convert to PlanStep objects
                    plan_steps = []
                    for i, step_data in enumerate(plan_data):
                        step = PlanStep(
                            step_number=step_data.get("step_number", i + 1),
                            step_type=step_data.get("step_type", "REASONING_STEP"),
                            description=step_data.get("description", ""),
                            tool_name=step_data.get("tool_name"),
                            tool_arguments=step_data.get("tool_arguments"),
                            reasoning_content=step_data.get("reasoning_content")
                        )
                        plan_steps.append(step)

                        # Show planned step for transparency
                        if step.step_type == "TOOL_CALL":
                            state["thinking_steps"].append(f"  📋 Step {i+1}: {step.tool_name} - {step.description}")
                        else:
                            state["thinking_steps"].append(f"  🧠 Step {i+1}: {step.description}")

                    state["plan"] = plan_steps
                    state["current_step_index"] = 0
                    state["thinking_steps"].append("✅ Execution plan created - ready to begin")
                else:
                    state["thinking_steps"].append("❌ Decision to plan but no plan provided")
                    state["error_message"] = "Decision to plan but no plan provided"
            else:
                state["thinking_steps"].append(f"❌ Unknown decision type: {decision_type}")
                state["plan"] = [
                    PlanStep(
                        step_number=1,
                        step_type="REASONING_STEP",
                        description="Generate response with available information",
                        reasoning_content="Provide best response with current data"
                    )
                ]
                state["current_step_index"] = 0
                state["thinking_steps"].append("✅ Fallback plan created")

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Error parsing decision response: {e}")
            logger.error(f"Response preview: {response[:200]}")

            state["thinking_steps"].append(f"⚠️ Error parsing AI decision: {str(e)}")
            state["thinking_steps"].append("🔄 Creating fallback plan")

            # Create fallback plan with available tools (TOOL_CALL only)
            first_tool = next((tool["name"] for tool in state.get("available_tools", [])
                             if tool["name"] in state.get("enabled_tools", [])), None)

            if first_tool:
                state["plan"] = [
                    PlanStep(
                        step_number=1,
                        step_type="TOOL_CALL",
                        description="Search for information",
                        tool_name=first_tool,
                        tool_arguments={"query": state["input"], "size": 10}
                    )
                ]
                state["current_step_index"] = 0
                state["thinking_steps"].append(f"✅ Fallback plan created with {first_tool}")
            else:
                # No tools available, skip to response generation
                state["plan"] = []
                state["thinking_steps"].append("⚠️ No enabled tools available for fallback plan")

    except Exception as e:
        logger.error(f"Error in unified planning decision: {e}")
        state["thinking_steps"].append(f"❌ Critical error in planning: {str(e)}")
        state["error_message"] = f"Failed in unified planning: {str(e)}"

    # Always update the iteration count
    state["current_turn_iteration_count"] = current_iteration
    return state


def generate_final_response_from_available_data(state: SearchAgentState) -> str:
    """Generate a simple fallback response when LLM fails"""
    import html as html_lib
    query = html_lib.escape(state.get("input", ""))
    tool_count = len(state.get("tool_execution_results", []))

    return f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; padding: 20px;">
    <h3 style="color: #e74c3c; margin-bottom: 16px;">⚠️ Response Generation Issue</h3>
    <p style="margin-bottom: 12px;">I encountered an issue generating a detailed response for: <strong>"{query}"</strong></p>
    {f'<p style="margin-bottom: 12px; color: #2c3e50;">However, I successfully gathered information from {tool_count} tool(s).</p>' if tool_count > 0 else '<p style="margin-bottom: 12px; color: #666;">No tool results were available.</p>'}
    <div style="background: #fff3cd; padding: 16px; border-radius: 6px; border-left: 3px solid #ffc107; margin: 16px 0;">
        <p style="margin: 0; color: #856404; font-size: 0.9em;">💡 <strong>Suggestion:</strong> Please try rephrasing your query or ask a follow-up question for better results.</p>
    </div>
</div>"""
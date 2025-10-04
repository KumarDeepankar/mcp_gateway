import json
import logging
import re
from typing import Dict, Any, List
from .state_definition import SearchAgentState, PlanStep
from .ollama_client import ollama_client
from .mcp_tool_client import mcp_tool_client
from .prompts import (
    create_reasoning_response_prompt,
    create_unified_planning_decision_prompt
)

logger = logging.getLogger(__name__)


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
    state["search_results"] = []
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


async def prepare_next_step_node(state: SearchAgentState) -> SearchAgentState:
    """Prepare the next step for execution"""
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)

    state["thinking_steps"].append("⚙️ Preparing next execution step...")
    state["thinking_steps"].append(f"📋 Plan status: {current_index}/{len(plan)} steps completed")

    if current_index < len(plan):
        current_step = plan[current_index]
        state["current_step_to_execute"] = current_step

        state["thinking_steps"].append(f"▶️ Next step {current_index + 1}/{len(plan)}: {current_step.description}")
        state["thinking_steps"].append(f"🎯 Step type: {current_step.step_type}")

        if current_step.step_type == "TOOL_CALL":
            state["thinking_steps"].append(f"🔧 Tool to execute: {current_step.tool_name}")
            if current_step.tool_arguments:
                arg_count = len(current_step.tool_arguments)
                state["thinking_steps"].append(f"📋 Tool has {arg_count} argument{'s' if arg_count != 1 else ''}")
        elif current_step.step_type == "REASONING_STEP":
            state["thinking_steps"].append("🧠 Reasoning step - will analyze current information")

        state["thinking_steps"].append("✅ Step preparation complete - ready for execution")
    else:
        # No more steps, move to final response
        state["current_step_to_execute"] = None
        state["thinking_steps"].append("🏁 All planned steps completed")
        state["thinking_steps"].append("📝 Moving to final response generation")

    return state


async def execute_tool_step_node(state: SearchAgentState) -> SearchAgentState:
    """Execute a tool call step with integrated reasoning"""
    current_step = state.get("current_step_to_execute")

    if not current_step:
        state["error_message"] = "No current step to execute"
        return state

    try:
        if current_step.step_type == "TOOL_CALL":
            # Execute tool call
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

        elif current_step.step_type == "REASONING_STEP":
            # Execute reasoning step
            state["thinking_steps"].append(f"🧠 Performing reasoning: {current_step.description}")

            # Create context for reasoning
            context = {
                "user_query": state["input"],
                "tool_results": state.get("tool_execution_results", []),
                "search_results": state.get("search_results", []),
                "thinking_steps": state.get("thinking_steps", [])
            }

            # Get reasoning from Ollama
            prompt = create_reasoning_response_prompt(
                user_query=state["input"],
                search_results=state.get("search_results", []),
                tool_results=state.get("tool_execution_results", []),
                conversation_history=state.get("conversation_history", []),
                current_step_description=current_step.reasoning_content or current_step.description,
                additional_context=context
            )

            reasoning_result = await ollama_client.generate_response(prompt)

            # Store reasoning result
            reasoning_entry = {
                "step_number": current_step.step_number,
                "reasoning_task": current_step.description,
                "analysis": reasoning_result
            }

            state["search_results"].append(reasoning_entry)
            state["thinking_steps"].append(f"🧠 Reasoning step completed")

            # Add analysis summary
            analysis_preview = reasoning_result[:150] + "..." if len(reasoning_result) > 150 else reasoning_result
            state["thinking_steps"].append(f"💭 Analysis preview: {analysis_preview}")

        else:
            state["error_message"] = f"Unknown step type: {current_step.step_type}"
            return state

        # Move to next step
        state["current_step_index"] = state.get("current_step_index", 0) + 1

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
    search_results_count = len(state.get("search_results", []))
    state["thinking_steps"].append(f"🔧 Tool executions completed: {tool_results_count}")
    state["thinking_steps"].append(f"🧠 Reasoning steps completed: {search_results_count}")

    if current_iteration > max_iterations:
        logger.info(f"⏰ Reached iteration limit ({max_iterations})")
        state["thinking_steps"].append(f"⏰ Reached maximum iterations ({max_iterations})")
        state["thinking_steps"].append("📝 Generating summary response with available information")

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
            logger.error(f"Error generating summary: {str(e)}")
            state["final_response_content"] = generate_final_response_from_available_data(state)
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
        state["thinking_steps"].append("🤖 Consulting AI for planning decision...")
        state["thinking_steps"].append("📋 Analyzing query requirements vs available information")

        system_prompt = """You are a planning agent. Respond with valid JSON only.

RULES:
1. No information? Create a plan to gather it
2. Have tool results? Generate final response
3. Valid JSON only - no comments, no extra text

FORMAT:
Planning: {"decision_type": "PLAN_AND_EXECUTE", "reasoning": "why", "plan": [...]}
Response: {"decision_type": "GENERATE_RESPONSE", "reasoning": "why", "final_response": "<div>...</div>"}

Use tools before responding. Make HTML professional."""

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

            # Create fallback plan with available tools
            first_tool = next((tool["name"] for tool in state.get("available_tools", [])
                             if tool["name"] in state.get("enabled_tools", [])), "search_stories")

            state["plan"] = [
                PlanStep(
                    step_number=1,
                    step_type="TOOL_CALL",
                    description="Search for information",
                    tool_name=first_tool,
                    tool_arguments={"query": state["input"], "size": 10}
                ),
                PlanStep(
                    step_number=2,
                    step_type="REASONING_STEP",
                    description="Analyze results and generate response",
                    reasoning_content="Synthesize findings"
                )
            ]
            state["current_step_index"] = 0
            state["thinking_steps"].append("✅ Fallback plan created")

    except Exception as e:
        logger.error(f"Error in unified planning decision: {e}")
        state["thinking_steps"].append(f"❌ Critical error in planning: {str(e)}")
        state["error_message"] = f"Failed in unified planning: {str(e)}"

    # Always update the iteration count
    state["current_turn_iteration_count"] = current_iteration
    return state


def generate_final_response_from_available_data(state: SearchAgentState) -> str:
    """Generate a final HTML-formatted response when iteration limit is reached"""
    import html as html_lib
    query = state.get("input", "")
    search_results = state.get("search_results", [])
    tool_results = state.get("tool_execution_results", [])
    conversation_history = state.get("conversation_history", [])

    # Create HTML-formatted response
    html_parts = []

    # Start main container
    html_parts.append('<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px;">')

    # Header section
    if conversation_history:
        html_parts.append('<h3 style="color: #2c3e50; font-size: 1.2em; margin-bottom: 16px; font-weight: 600;">Followup Query Summary</h3>')
        html_parts.append(f'<p style="margin-bottom: 12px;">Building on our previous conversation, I\'ve processed your followup query: <strong>"{html_lib.escape(query)}"</strong></p>')
    else:
        html_parts.append('<h3 style="color: #2c3e50; font-size: 1.2em; margin-bottom: 16px; font-weight: 600;">Search Results Summary</h3>')
        html_parts.append(f'<p style="margin-bottom: 12px;">I\'ve processed your query: <strong>"{html_lib.escape(query)}"</strong></p>')

    # Tool results section
    if tool_results:
        html_parts.append('<h4 style="color: #2c3e50; font-size: 1.1em; margin: 20px 0 12px 0;">Information Gathered</h4>')
        html_parts.append('<ul style="margin: 12px 0; padding-left: 20px;">')
        for i, result in enumerate(tool_results[:5]):  # Show max 5 results
            tool_name = html_lib.escape(result.get('tool_name', 'Unknown tool'))
            summary = html_lib.escape(str(result.get('result', 'Tool execution result available'))[:200])
            html_parts.append(f'<li style="margin-bottom: 8px;"><strong>{tool_name}:</strong> {summary}{"..." if len(str(result.get("result", ""))) > 200 else ""}</li>')
        html_parts.append('</ul>')

    # Search results section
    if search_results:
        html_parts.append('<h4 style="color: #2c3e50; font-size: 1.1em; margin: 20px 0 12px 0;">Search Results Found</h4>')
        html_parts.append('<ul style="margin: 12px 0; padding-left: 20px;">')
        for i, result in enumerate(search_results[:3]):  # Show first 3 results
            title = html_lib.escape(result.get('reasoning_task', result.get('title', 'Search result')))
            analysis = html_lib.escape(str(result.get('analysis', 'Analysis available'))[:150])
            html_parts.append(f'<li style="margin-bottom: 8px;"><strong>{title}:</strong> {analysis}{"..." if len(str(result.get("analysis", ""))) > 150 else ""}</li>')
        html_parts.append('</ul>')

    # Key insights section
    if tool_results or search_results:
        html_parts.append('<div style="background: #f8f9fa; padding: 16px; border-radius: 6px; border-left: 3px solid #007bff; margin: 16px 0;">')
        html_parts.append('<h4 style="margin-top: 0; margin-bottom: 12px; color: #2c3e50; font-size: 1.1em;">Key Insights</h4>')
        html_parts.append('<ul style="margin: 10px 0 0 0; padding-left: 18px;">')

        if tool_results:
            html_parts.append(f'<li style="margin-bottom: 6px;">Executed {len(tool_results)} tool operations to gather information</li>')
        if search_results:
            html_parts.append(f'<li style="margin-bottom: 6px;">Found {len(search_results)} relevant search results</li>')
        if conversation_history:
            html_parts.append('<li style="margin-bottom: 6px;">Built upon previous conversation context</li>')

        html_parts.append('</ul>')
        html_parts.append('</div>')
    else:
        # No results section
        html_parts.append('<div style="background: #fff3cd; padding: 16px; border-radius: 6px; border-left: 3px solid #ffc107; margin: 16px 0;">')
        html_parts.append('<h4 style="margin-top: 0; margin-bottom: 12px; color: #856404; font-size: 1.1em;">Limited Information Available</h4>')
        if conversation_history:
            html_parts.append('<p style="margin: 0; color: #856404;">I wasn\'t able to gather additional specific information, but I can provide insights based on our conversation context.</p>')
        else:
            html_parts.append('<p style="margin: 0; color: #856404;">I wasn\'t able to gather specific information for this query.</p>')
        html_parts.append('</div>')

    # Next steps section
    html_parts.append('<div style="margin-top: 20px; padding: 12px 0; border-top: 1px solid #e9ecef;">')
    html_parts.append('<h4 style="color: #2c3e50; font-size: 1.0em; margin: 0 0 8px 0;">Next Steps</h4>')
    if conversation_history:
        html_parts.append('<p style="margin: 0; font-size: 0.9em; color: #6c757d;">For more detailed information, try asking a more specific followup question or request particular aspects of the topic.</p>')
    else:
        html_parts.append('<p style="margin: 0; font-size: 0.9em; color: #6c757d;">For more specific information, try refining your query or asking a follow-up question with more details.</p>')
    html_parts.append('</div>')

    # Close main container
    html_parts.append('</div>')

    return "".join(html_parts)
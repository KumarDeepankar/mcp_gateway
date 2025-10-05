import json
import logging
import re
from typing import Dict, Any, List
from datetime import datetime
from .state_definition import SearchAgentState, Task, ExecutionPlan, GatheredInformation, FinalResponse
from .ollama_client import ollama_client
from .mcp_tool_client import mcp_tool_client
from .prompts import (
    create_multi_task_planning_prompt,
    create_information_synthesis_prompt,
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

    # Fix unescaped newlines inside strings (common issue with HTML content)
    # This is a simplified approach - find strings and escape newlines
    def escape_newlines_in_strings(match):
        content = match.group(1)
        # Escape unescaped newlines
        content = content.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f'"{content}"'

    # Be careful with this - only process simple string patterns
    # Don't process strings that already have escape sequences
    response = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', lambda m: m.group(0), response)

    # Fix HTML attributes with single quotes - convert to escaped double quotes
    # Pattern: attribute='value' -> attribute=\"value\"
    def fix_html_attributes(match):
        full_match = match.group(0)
        attr_name = match.group(1)
        attr_value = match.group(2)
        # Replace with escaped double quotes
        return f'{attr_name}=\\"{attr_value}\\"'

    # Find HTML attributes with single quotes
    response = re.sub(r'(\w+)=\'([^\']+)\'', fix_html_attributes, response)

    # Remove trailing commas before closing brackets/braces (more aggressive)
    response = re.sub(r',(\s*[}\]])', r'\1', response)
    response = re.sub(r',(\s*[}\]])', r'\1', response)  # Run twice to catch nested cases

    # Fix missing quotes around keys (common LLM mistake) - only if not already quoted
    response = re.sub(r'([^"]|^)(\w+)(\s*:\s*)', r'\1"\2"\3', response)

    # Fix single quotes to double quotes for JSON structure
    # First, handle the outer JSON structure (keys and simple values)
    # Replace single quotes around keys
    response = re.sub(r"'(\w+)'(\s*:)", r'"\1"\2', response)

    # For string values with single quotes, we need to be more careful
    # Replace single quotes that wrap values (but not quotes inside HTML)
    # This is tricky - let's use a more conservative approach

    # Replace single quotes that appear to be JSON string delimiters
    # Pattern: : 'value' or : 'value with spaces'
    def replace_single_quote_values(match):
        content = match.group(1)
        # If content contains HTML tags or is complex, keep the single quotes escaped
        if '<' in content or '>' in content:
            # This is HTML content - replace outer single quotes with double quotes
            # but keep internal quotes as-is for now
            return f': "{content}"'
        else:
            # Simple value - just replace quotes
            return f': "{content}"'

    response = re.sub(r":\s*'([^']*)'", replace_single_quote_values, response)

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
            r'```\s*\n?(.*?)\n?```',  # generic ``` block
            r'`(.*?)`',  # single backticks
        ]

        json_extracted = False
        for pattern in patterns:
            json_match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if json_match:
                candidate = json_match.group(1).strip()
                # Only use if it looks like JSON
                if candidate.startswith('{') and '}' in candidate:
                    response = candidate
                    json_extracted = True
                    print(f"[DEBUG] Extracted JSON from code block using pattern: {pattern}")
                    break

        if not json_extracted:
            print(f"[DEBUG] No code block found, using raw response")

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
            # Fallback: use rfind for the last closing brace
            end_idx = response.rfind('}')
            if end_idx == -1:
                # Try to recover by finding what looks like the end of JSON
                # Look for common patterns that might indicate truncation
                logger.warning("No proper closing brace found, attempting recovery")

                # Find the last complete structure
                last_quote = response.rfind('"')
                if last_quote > start_idx:
                    # Try to close from the last quote
                    test_end = response.find('\n', last_quote)
                    if test_end == -1:
                        test_end = len(response)

                    # Add closing structures
                    recovered = response[start_idx:test_end].rstrip(',').rstrip() + ']}}'
                    print(f"[DEBUG] Attempting recovery with: {recovered[:100]}")

                    try:
                        # Test if this works
                        test_json = clean_json_response(recovered)
                        json.loads(test_json)
                        response = recovered
                        end_idx = len(recovered) - 1
                    except:
                        raise ValueError("No closing brace found and recovery failed")
                else:
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

        print(f"[DEBUG] Cleaned JSON (first 300 chars): {json_str[:300]}")

        # Parse JSON
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON decode failed at position {e.pos}")
            print(f"[DEBUG] Context around error: {json_str[max(0, e.pos-50):min(len(json_str), e.pos+50)]}")
            raise

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

    # Initialize state with new multi-task structure
    state["thinking_steps"] = state.get("thinking_steps", [])
    state["current_task_index"] = 0
    state["final_response_generated_flag"] = False
    state["final_response"] = None
    state["execution_plan"] = None
    state["gathered_information"] = None
    state["error_message"] = None

    # Initialize iteration control
    state["current_turn_iteration_count"] = 0
    state["max_turn_iterations"] = 1  # One iteration: plan -> execute -> respond

    # Initialize conversation history if not present
    state["conversation_history"] = state.get("conversation_history", [])
    state["is_followup_query"] = state.get("is_followup_query", False)

    # Enhanced thinking steps for streaming UI
    state["thinking_steps"].append("🚀 Initializing Multi-Task Agentic Search")
    state["thinking_steps"].append(f"📝 Query: '{state['input']}'")

    if state["is_followup_query"]:
        state["thinking_steps"].append("🔄 Followup query detected - loading conversation context")
        if state["conversation_history"]:
            state["thinking_steps"].append(f"📚 Found {len(state['conversation_history'])} previous conversation turns")
            if state["conversation_history"]:
                latest = state["conversation_history"][-1]
                preview = latest.get("response", "")[:100] + "..." if len(
                    latest.get("response", "")) > 100 else latest.get("response", "")
                state["thinking_steps"].append(f"💭 Previous context: {preview}")
    else:
        state["thinking_steps"].append("🆕 Fresh search session started")

    state["thinking_steps"].append("✅ Search session initialized - ready for multi-task planning")

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
                                           (f" and {len(tool_names) - 5} more..." if len(tool_names) > 5 else ""))

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


async def create_execution_plan_node(state: SearchAgentState) -> SearchAgentState:
    """Create a multi-task execution plan"""
    logger.info("Creating multi-task execution plan")

    state["thinking_steps"].append("🎯 Creating Multi-Task Execution Plan")
    state["thinking_steps"].append("📊 Analyzing query to identify required tasks")

    try:
        # Filter to only enabled tools
        enabled_tool_names = state.get("enabled_tools", [])
        all_tools = state.get("available_tools", [])
        enabled_tools_only = [
            tool for tool in all_tools
            if tool.get("name") in enabled_tool_names
        ]

        # Create planning prompt
        prompt = create_multi_task_planning_prompt(
            user_query=state["input"],
            enabled_tools=enabled_tools_only,
            conversation_history=state.get("conversation_history", [])
        )

        state["thinking_steps"].append("🤖 Consulting AI for task planning...")

        system_prompt = """You are a JSON-only planning agent. Output ONLY valid JSON, no other text.

FORMAT: Single JSON object with "reasoning" and "tasks" array.
RULES:
- Start with { and end with }
- NO code blocks, NO markdown, NO explanations
- Each task needs: task_number, tool_name, tool_arguments, description
- Ensure proper JSON syntax (commas, quotes, brackets)

Example:
{"reasoning":"Need to search multiple times","tasks":[{"task_number":1,"tool_name":"search_stories","tool_arguments":{"query":"AI","size":10},"description":"Search for AI"}]}

Output JSON now:"""

        response = await ollama_client.generate_response(prompt, system_prompt)
        state["thinking_steps"].append("✅ Received planning response")

        # Parse the response with better error handling
        try:
            plan_data = extract_json_from_response(response)
        except Exception as e:
            logger.error(f"Failed to parse plan JSON: {e}")
            logger.error(f"Response: {response[:300]}")
            state["thinking_steps"].append(f"⚠️ JSON parsing failed, creating fallback plan")

            # Create a simple fallback plan with one task
            enabled_tool_names = state.get("enabled_tools", [])
            if enabled_tool_names:
                first_tool = enabled_tool_names[0]
                plan_data = {
                    "reasoning": "Fallback plan due to parsing error",
                    "tasks": [
                        {
                            "task_number": 1,
                            "tool_name": first_tool,
                            "tool_arguments": {"query": state["input"], "size": 10},
                            "description": f"Search using {first_tool}"
                        }
                    ]
                }
            else:
                raise Exception("No enabled tools available for fallback plan")

        # Create ExecutionPlan with Tasks
        tasks = []
        for task_data in plan_data.get("tasks", []):
            task = Task(
                task_number=task_data.get("task_number", len(tasks) + 1),
                tool_name=task_data["tool_name"],
                tool_arguments=task_data.get("tool_arguments", {}),
                description=task_data.get("description", ""),
                status="pending"
            )
            tasks.append(task)

        execution_plan = ExecutionPlan(
            tasks=tasks,
            reasoning=plan_data.get("reasoning", ""),
            plan_created_at=datetime.now().isoformat()
        )

        state["execution_plan"] = execution_plan
        state["current_task_index"] = 0

        state["thinking_steps"].append(f"📋 Created plan with {len(tasks)} tasks")
        state["thinking_steps"].append(f"💭 Plan reasoning: {execution_plan.reasoning}")

        for i, task in enumerate(tasks):
            state["thinking_steps"].append(f"  Task {i+1}: {task.tool_name} - {task.description}")

    except Exception as e:
        logger.error(f"Error creating execution plan: {e}")
        state["thinking_steps"].append(f"❌ Failed to create plan: {str(e)}")
        state["error_message"] = f"Planning failed: {str(e)}"

    return state


async def execute_task_node(state: SearchAgentState) -> SearchAgentState:
    """Execute the next task from the execution plan (DEPRECATED - use execute_all_tasks_parallel_node)"""
    execution_plan = state.get("execution_plan")
    current_index = state.get("current_task_index", 0)

    if not execution_plan or current_index >= len(execution_plan.tasks):
        state["error_message"] = "No more tasks to execute"
        return state

    current_task = execution_plan.tasks[current_index]

    try:
        # Update task status
        current_task.status = "executing"

        state["thinking_steps"].append(f"🔧 Executing Task {current_index + 1}/{len(execution_plan.tasks)}")
        state["thinking_steps"].append(f"🛠️ Tool: {current_task.tool_name}")
        state["thinking_steps"].append(f"📝 Purpose: {current_task.description}")

        # Add argument details
        if current_task.tool_arguments:
            arg_summary = ", ".join([f"{k}={str(v)[:50]}..." if len(str(v)) > 50 else f"{k}={v}"
                                     for k, v in current_task.tool_arguments.items()])
            state["thinking_steps"].append(f"📋 Parameters: {arg_summary}")

        # Call the tool via MCP
        result = await mcp_tool_client.call_tool(
            current_task.tool_name,
            current_task.tool_arguments
        )

        # Update task with result
        current_task.result = result
        current_task.status = "completed"

        # Add FULL result for debugging (no truncation)
        state["thinking_steps"].append(f"✅ Task completed successfully")
        state["thinking_steps"].append(f"📊 Full Result: {str(result)}")

        # Move to next task
        state["current_task_index"] = current_index + 1

    except Exception as e:
        logger.error(f"Error executing task: {e}")
        current_task.status = "failed"
        current_task.result = {"error": str(e)}
        state["thinking_steps"].append(f"❌ Task failed: {str(e)}")
        state["error_message"] = f"Task execution failed: {str(e)}"

    return state


async def execute_all_tasks_parallel_node(state: SearchAgentState) -> SearchAgentState:
    """Execute ALL tasks from the execution plan in parallel"""
    import asyncio

    execution_plan = state.get("execution_plan")

    if not execution_plan or not execution_plan.tasks:
        state["error_message"] = "No tasks to execute"
        return state

    tasks = execution_plan.tasks
    total_tasks = len(tasks)

    state["thinking_steps"].append(f"🚀 Starting parallel execution of {total_tasks} tasks")
    state["thinking_steps"].append(f"⚡ Tasks will execute concurrently for faster results")

    async def execute_single_task(task: Task, task_index: int) -> tuple[int, Task]:
        """Execute a single task and return its index and updated task"""
        try:
            task.status = "executing"

            # Call the tool via MCP
            result = await mcp_tool_client.call_tool(
                task.tool_name,
                task.tool_arguments
            )

            # Update task with result
            task.result = result
            task.status = "completed"

            logger.info(f"Task {task_index + 1}/{total_tasks} completed: {task.tool_name}")
            return (task_index, task)

        except Exception as e:
            logger.error(f"Error executing task {task_index + 1}: {e}")
            task.status = "failed"
            task.result = {"error": str(e)}
            return (task_index, task)

    # Create coroutines for all tasks
    task_coroutines = [
        execute_single_task(task, idx)
        for idx, task in enumerate(tasks)
    ]

    # Execute all tasks in parallel using asyncio.gather
    state["thinking_steps"].append(f"⏳ Executing {total_tasks} tasks concurrently...")

    try:
        # Use asyncio.gather to run all tasks in parallel
        results = await asyncio.gather(*task_coroutines, return_exceptions=True)

        # Process results
        completed_count = 0
        failed_count = 0

        for result in results:
            if isinstance(result, Exception):
                failed_count += 1
                logger.error(f"Task execution raised exception: {result}")
            else:
                task_index, updated_task = result
                execution_plan.tasks[task_index] = updated_task

                if updated_task.status == "completed":
                    completed_count += 1
                    state["thinking_steps"].append(
                        f"✅ Task {task_index + 1}: {updated_task.tool_name} - {updated_task.description}"
                    )
                    state["thinking_steps"].append(f"📊 Full Result: {str(updated_task.result)}")
                else:
                    failed_count += 1
                    state["thinking_steps"].append(
                        f"❌ Task {task_index + 1}: {updated_task.tool_name} - Failed"
                    )

        state["thinking_steps"].append(f"✨ Parallel execution complete!")
        state["thinking_steps"].append(f"📊 Results: {completed_count} completed, {failed_count} failed")

        # Update current_task_index to indicate all tasks processed
        state["current_task_index"] = total_tasks

        if failed_count > 0 and completed_count == 0:
            state["error_message"] = f"All {total_tasks} tasks failed"

    except Exception as e:
        logger.error(f"Error in parallel execution: {e}")
        state["thinking_steps"].append(f"❌ Parallel execution error: {str(e)}")
        state["error_message"] = f"Parallel execution failed: {str(e)}"

    return state


async def gather_and_synthesize_node(state: SearchAgentState) -> SearchAgentState:
    """Gather all task results and synthesize into final response"""
    logger.info("Gathering information and synthesizing response")

    state["thinking_steps"].append("🧠 Information Synthesis Phase")
    state["thinking_steps"].append("📊 Gathering results from all completed tasks")

    try:
        execution_plan = state.get("execution_plan")
        if not execution_plan:
            state["error_message"] = "No execution plan found"
            return state

        # Gather information from all tasks
        task_results = []
        sources_used = []

        for task in execution_plan.tasks:
            if task.status == "completed" and task.result:
                task_results.append({
                    "task_number": task.task_number,
                    "tool_name": task.tool_name,
                    "description": task.description,
                    "arguments": task.tool_arguments,
                    "result": task.result
                })
                if task.tool_name not in sources_used:
                    sources_used.append(task.tool_name)

        gathered_info = GatheredInformation(
            task_results=task_results,
            sources_used=sources_used
        )

        state["gathered_information"] = gathered_info
        state["thinking_steps"].append(f"✅ Gathered results from {len(task_results)} completed tasks")
        state["thinking_steps"].append(f"📚 Sources used: {', '.join(sources_used)}")

        # Now synthesize the information
        state["thinking_steps"].append("🤖 Synthesizing information into comprehensive response...")

        # Prepare gathered information for synthesis
        synthesis_data = {
            "task_results": task_results,
            "sources_used": sources_used,
            "total_tasks": len(execution_plan.tasks),
            "completed_tasks": len(task_results)
        }

        prompt = create_information_synthesis_prompt(
            user_query=state["input"],
            gathered_information=synthesis_data,
            conversation_history=state.get("conversation_history", [])
        )

        system_prompt = """You are a JSON-only response agent. Output ONLY valid JSON, no other text.

FORMAT REQUIREMENTS:
- Start with { and end with }
- Two fields: "reasoning" (string) and "response_content" (string with HTML)
- NO newlines inside string values
- NO comments
- NO trailing commas
- Escape all quotes inside strings

Example:
{"reasoning": "Analysis of data", "response_content": "<div><h3>Title</h3><p>Content here.</p></div>"}

Output valid JSON now:"""

        response = await ollama_client.generate_response(prompt, system_prompt)
        state["thinking_steps"].append("✅ Received synthesis response")

        # Parse the response with enhanced error handling
        try:
            synthesis_data = extract_json_from_response(response)

            # Validate required fields
            if not synthesis_data.get("response_content"):
                raise ValueError("response_content is missing or empty")

            # Create FinalResponse
            final_response = FinalResponse(
                response_content=synthesis_data.get("response_content", ""),
                reasoning=synthesis_data.get("reasoning", "Information synthesized from task results"),
                information_used=gathered_info
            )

            state["final_response"] = final_response
            state["final_response_generated_flag"] = True

            state["thinking_steps"].append("✅ Final response generated successfully")
            state["thinking_steps"].append(f"💭 Synthesis reasoning: {final_response.reasoning[:100]}...")

            # Save conversation history
            save_conversation_turn(state, final_response.response_content)

        except Exception as json_error:
            logger.error(f"JSON parsing failed: {json_error}")
            logger.error(f"Raw response (first 500 chars): {response[:500]}")

            # Try alternative: extract HTML directly if JSON parsing fails
            state["thinking_steps"].append(f"⚠️ JSON parsing failed, attempting HTML extraction")

            # Look for HTML content in the response
            import re
            html_match = re.search(r'<div[^>]*>.*?</div>', response, re.DOTALL | re.IGNORECASE)

            if html_match:
                html_content = html_match.group(0)
                final_response = FinalResponse(
                    response_content=html_content,
                    reasoning="Extracted from LLM response (JSON parsing failed)",
                    information_used=gathered_info
                )
                state["final_response"] = final_response
                state["final_response_generated_flag"] = True
                save_conversation_turn(state, html_content)
                state["thinking_steps"].append("✅ Extracted HTML response successfully")
            else:
                # Last resort: generate fallback
                raise json_error

    except Exception as e:
        logger.error(f"Error in gather and synthesize: {e}")
        state["thinking_steps"].append(f"❌ Synthesis failed: {str(e)}")
        state["error_message"] = f"Synthesis failed: {str(e)}"

        # Fallback response
        fallback_response = generate_final_response_from_available_data(state)
        final_response = FinalResponse(
            response_content=fallback_response,
            reasoning="Fallback response due to synthesis error",
            information_used=state.get("gathered_information")
        )
        state["final_response"] = final_response
        state["final_response_generated_flag"] = True
        save_conversation_turn(state, fallback_response)

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
    execution_plan = state.get("execution_plan")
    has_plan = execution_plan is not None
    state["thinking_steps"].append(f"📋 Execution plan exists: {has_plan}")

    if current_iteration > max_iterations:
        logger.info(f"⏰ Reached iteration limit ({max_iterations})")
        state["thinking_steps"].append(f"⏰ Reached maximum iterations ({max_iterations})")
        state["thinking_steps"].append("📝 Generating summary response with available information")

        try:
            # Force synthesis with whatever we have
            return await gather_and_synthesize_node(state)
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            final_response_content = generate_final_response_from_available_data(state)
            final_response = FinalResponse(
                response_content=final_response_content,
                reasoning="Fallback response due to iteration limit",
                information_used=state.get("gathered_information")
            )
            state["final_response"] = final_response
            state["final_response_generated_flag"] = True
            state["current_turn_iteration_count"] = current_iteration

            # Save conversation history
            save_conversation_turn(state, final_response_content)

            return state

    # Always update the iteration count
    state["current_turn_iteration_count"] = current_iteration

    # This node is kept for compatibility but is now simplified
    # The actual workflow is: discover_tools -> create_execution_plan -> execute_tasks -> gather_and_synthesize
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

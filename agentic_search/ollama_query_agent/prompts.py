from typing import List, Dict, Any
import json


def format_conversation_context(conversation_history: List[Dict[str, Any]], max_turns: int = 3) -> str:
    """Format conversation history in a readable way for the LLM"""
    if not conversation_history:
        return ""

    recent_turns = conversation_history[-max_turns:]
    formatted_turns = []

    for i, turn in enumerate(recent_turns, 1):
        turn_text = f"""
Turn {i}:
  User Query: {turn.get('query', 'N/A')}
  Assistant Response: {turn.get('response', 'N/A')[:200]}{'...' if len(turn.get('response', '')) > 200 else ''}
  Timestamp: {turn.get('timestamp', 'N/A')}"""

        # Include tool results if available
        tool_results = turn.get('tool_results', [])
        if tool_results:
            tool_summary = []
            for result in tool_results[:2]:  # Show max 2 tool results per turn
                tool_name = result.get('tool_name', 'Unknown')
                summary = result.get('summary', 'No summary')[:100]
                tool_summary.append(f"    - {tool_name}: {summary}")
            if tool_summary:
                turn_text += f"\n  Tools Used:\n" + "\n".join(tool_summary)

        formatted_turns.append(turn_text)

    return f"""
Previous Conversation Context:
{chr(10).join(formatted_turns)}

NOTE: This is a followup query. Consider the conversation context and build upon previous information when planning your response.
"""


def create_planning_prompt(user_query: str, available_tools: List[Dict[str, Any]], enabled_tools: List[str],
                           conversation_history: List[Dict[str, Any]] = None) -> str:
    """Create a prompt for planning the search strategy"""

    enabled_tool_info = []
    for tool in available_tools:
        if tool.get("name") in enabled_tools:
            enabled_tool_info.append({
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", {})
            })

    tools_section = ""
    if enabled_tool_info:
        tools_section = f"""
Available Tools (enabled by user):
{json.dumps(enabled_tool_info, indent=2)}
"""
    else:
        tools_section = "No tools are currently enabled by the user."

    # Add conversation history context if available
    context_section = format_conversation_context(conversation_history)

    return f"""You are a search planning assistant. Create a step-by-step plan to answer the user's query using ONLY available tools.

User Query: {user_query}
{context_section}
{tools_section}

CRITICAL REQUIREMENTS - READ CAREFULLY:
- Respond ONLY with valid JSON
- NO comments, NO trailing commas, NO placeholder values
- Use ONLY real tool names from the enabled tools list above
- DO NOT make up information or create fictional responses
- ALWAYS use tools to gather factual information when available

TOOL USAGE PRIORITY:
1. **MANDATORY**: If tools are available and can help answer the query, you MUST use them
2. **SEARCH STRATEGY**: Break down complex queries into specific, targeted search terms
3. **NO HALLUCINATION**: Do not provide information without tool verification
4. **FACTUAL ONLY**: Only provide answers based on tool results, not assumptions

SEARCH QUERY OPTIMIZATION:
- For search tools (like opensearch_search): Create specific, targeted search queries
- Break complex questions into multiple focused searches
- Use relevant keywords, not full sentences
- Example: "How is the weather in Paris?" → search query: "Paris weather current"
- Example: "Tell me about AI trends" → search query: "artificial intelligence trends 2024"

Instructions:
1. Analyze what specific factual information is needed to answer the query
2. If conversation history exists, check what information is already available
3. Create targeted search queries for any missing information
4. ALWAYS prioritize TOOL_CALL over REASONING_STEP when tools can provide the answer
5. For TOOL_CALL steps:
   - Use ONLY tools from the enabled tools list
   - Create specific, optimized search queries or parameters
   - Focus on factual information gathering
6. For REASONING_STEP: Only use to synthesize tool results, never to create new information
7. If no tools are enabled, state that tools are required for factual answers

Required JSON format (NO COMMENTS):
{{
    "plan": [
        {{
            "step_number": 1,
            "step_type": "TOOL_CALL",
            "description": "Search for relevant information using enabled tool",
            "tool_name": "actual_tool_name",
            "tool_arguments": {{
                "query": "specific search terms",
                "param": "value"
            }}
        }},
        {{
            "step_number": 2,
            "step_type": "REASONING_STEP",
            "description": "Analyze and synthesize the tool results",
            "reasoning_content": "Combine findings to answer the query"
        }}
    ]
}}

IMPORTANT:
- Always start with TOOL_CALL steps when enabled tools are available
- Use multiple tools if they can provide different aspects of the answer
- Only use REASONING_STEP after gathering data with tools
- Make tool arguments specific and relevant to the user's query

Generate valid JSON without any comments or placeholders:"""


def create_unified_planning_decision_prompt(
    user_query: str,
    search_results: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
    available_tools: List[Dict[str, Any]],
    enabled_tools: List[str],
    executed_steps: List[Dict[str, Any]] = None,
    conversation_history: List[Dict[str, Any]] = None,
    current_plan: List[Dict[str, Any]] = None
) -> str:
    """Create a unified prompt for planning, decision-making, and response generation"""

    # Add conversation history context if available
    context_section = format_conversation_context(conversation_history)

    # Add executed steps context
    executed_steps_section = ""
    if executed_steps and len(executed_steps) > 0:
        executed_steps_section = f"""
Steps Already Executed:
{json.dumps(executed_steps, indent=2)}
"""

    # Add current plan context
    current_plan_section = ""
    if current_plan and len(current_plan) > 0:
        # Convert PlanStep objects to dictionaries for JSON serialization
        plan_dicts = []
        for step in current_plan:
            if hasattr(step, 'model_dump'):  # Pydantic model
                plan_dicts.append(step.model_dump())
            elif hasattr(step, '__dict__'):  # Regular object
                plan_dicts.append(step.__dict__)
            else:  # Already a dict
                plan_dicts.append(step)

        current_plan_section = f"""
Current Plan (remaining steps):
{json.dumps(plan_dicts, indent=2)}
"""

    # Tool information
    enabled_tool_info = []
    for tool in available_tools:
        if tool.get("name") in enabled_tools:
            enabled_tool_info.append({
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", {})
            })

    tools_section = ""
    if enabled_tool_info:
        tools_section = f"""
Available Tools (enabled by user):
{json.dumps(enabled_tool_info, indent=2)}
"""

    return f"""You are a unified planning and decision agent. PRIORITIZE TOOL USAGE to provide factual, verified information.

User Query: {user_query}
{context_section}
Current Search Results:
{search_results}

Current Tool Execution Results:
{tool_results}
{executed_steps_section}{current_plan_section}
{tools_section}

DECISION TYPES:
1. "PLAN_AND_EXECUTE" - Create a new plan with next steps using available tools
2. "EXECUTE_NEXT_STEP" - Execute the next step from current plan
3. "GENERATE_RESPONSE" - Generate final response (ONLY when you have sufficient factual information)

CRITICAL REQUIREMENTS - NO HALLUCINATION:
- Respond ONLY with valid JSON
- DO NOT make up information or create fictional responses
- PRIORITIZE using enabled tools to gather factual information
- Only generate final response when you have verified, factual information from tools
- If information is missing, create targeted tool calls to gather it

SEARCH QUERY OPTIMIZATION (for search tools):
- Create specific, keyword-based search queries
- Break complex questions into focused searches
- Use relevant terms, not full sentences
- Target specific information gaps

Your decision process:
1. **Analyze Information Gaps**: What factual information is still needed?
2. **Review Available Data**: Check conversation context and current tool results
3. **Tool Priority**: If enabled tools can fill information gaps, plan to use them
4. **Factual Threshold**: Only choose "GENERATE_RESPONSE" when you have sufficient verified information
5. **Search Strategy**: For missing information, create specific tool calls with optimized parameters

GENERATE_RESPONSE Criteria (ALL must be true):
- You have factual information from tool results or conversation history
- The information directly answers the user's query
- No critical information gaps remain
- You are not relying on assumptions or general knowledge

If any information is missing or unverified, choose "PLAN_AND_EXECUTE" with specific tool calls.

Required JSON format:
{{
    "decision_type": "PLAN_AND_EXECUTE|EXECUTE_NEXT_STEP|GENERATE_RESPONSE",
    "reasoning": "Brief explanation of your decision",
    "plan": [
        {{
            "step_number": 1,
            "step_type": "TOOL_CALL|REASONING_STEP",
            "description": "What this step accomplishes",
            "tool_name": "tool_name_if_tool_call",
            "tool_arguments": {{"key": "value"}},
            "reasoning_content": "reasoning_description_if_reasoning_step"
        }}
    ],
    "final_response": "Complete response text if decision_type is GENERATE_RESPONSE",
    "final_response_generated_flag": true/false
}}

Generate valid JSON without comments:"""


def create_reasoning_response_prompt(
        user_query: str,
        search_results: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        conversation_history: List[Dict[str, Any]] = None,
        current_step_description: str = None,
        additional_context: Dict[str, Any] = None
) -> str:
    """Create a unified prompt for reasoning and response generation (handles both direct responses and reasoning-based analysis)"""

    # Add conversation history context if available
    context_section = format_conversation_context(conversation_history)

    # Add current step context if this is a reasoning step
    step_section = ""
    if current_step_description:
        step_section = f"""
Current Reasoning Step: {current_step_description}

You need to:
1. First, perform the reasoning/analysis for this step: {current_step_description}
2. Then, evaluate if you have sufficient information to provide a complete answer to the user's query
3. Generate either a final response or indicate what additional steps are needed
"""

    # Add additional context if provided
    additional_context_section = ""
    if additional_context:
        additional_context_section = f"""
Additional Context:
{additional_context}
"""

    # Determine the response format based on whether this is a reasoning step or direct response
    if current_step_description:
        format_instructions = """
Format your response as:
**Analysis:** [Your reasoning for the current step]

**Assessment:** [Whether you can provide a final answer or need more information]

**Response:** [Either your final comprehensive answer OR explanation of what additional information is needed]"""
    else:
        format_instructions = """
Generate a helpful, informative response that directly addresses the user's query."""

    return f"""You are a factual information assistant. Provide answers based ONLY on verified information from tools and conversation history.

User Query: {user_query}
{context_section}{step_section}
Search Results:
{search_results}

Tool Execution Results:
{tool_results}
{additional_context_section}

CRITICAL REQUIREMENTS - NO HALLUCINATION:
- Base your response ONLY on information from:
  1. Tool execution results above
  2. Search results above
  3. Previous conversation context (if available)
- DO NOT add information not present in the provided sources
- DO NOT make assumptions or use general knowledge
- If information is incomplete, clearly state what is missing
- Always cite which source provided specific information

Instructions:
1. **Source Analysis**: Identify what factual information is available from tools/search/history
2. **Gap Identification**: Note any missing information needed to fully answer the query
3. **Factual Response**: Provide answers using ONLY verified information from sources
4. **Source Attribution**: Mention where information came from (e.g., "According to the search results...")
5. **Limitations**: If insufficient information exists, clearly state what cannot be answered
6. **Conversation Context**: Build upon previous information if this is a followup
7. **Completeness Check**: If this is a reasoning step, assess if enough information exists for a final answer

RESPONSE STRUCTURE:
- Start with available factual information
- Clearly indicate sources of information
- Note any limitations or missing information
- For followup queries, reference previous conversation appropriately

{format_instructions}"""

from typing import List, Dict, Any
import json
import html


def format_conversation_context(conversation_history: List[Dict[str, Any]], max_turns: int = 3, format_type: str = "xml") -> str:
    """Format conversation history with improved XML structure for better LLM parsing"""
    if not conversation_history:
        return ""

    if format_type == "xml":
        return _build_xml_conversation_context(conversation_history, max_turns)
    else:
        return _build_legacy_conversation_context(conversation_history, max_turns)


def _build_xml_conversation_context(conversation_history: List[Dict[str, Any]], max_turns: int) -> str:
    """Build XML-structured conversation context - optimal for LLM parsing"""
    recent_turns = conversation_history[-max_turns:]

    if not recent_turns:
        return ""

    context_parts = ["\n<conversation_context>"]

    for i, turn in enumerate(recent_turns, 1):
        context_parts.append(f"<turn number='{i}'>")

        query = turn.get('query', 'N/A')
        response = turn.get('response', 'N/A')
        timestamp = turn.get('timestamp', 'N/A')

        # Truncate response for context
        if len(response) > 300:
            response = response[:300] + "..."

        context_parts.append(f"<user_query>{html.escape(query)}</user_query>")
        context_parts.append(f"<assistant_response>{html.escape(response)}</assistant_response>")
        context_parts.append(f"<timestamp>{html.escape(timestamp)}</timestamp>")

        # Include tool results if available
        tool_results = turn.get('tool_results', [])
        if tool_results:
            context_parts.append("<tools_used>")
            for result in tool_results[:3]:  # Show max 3 tool results per turn
                tool_name = result.get('tool_name', 'Unknown')
                summary = str(result.get('result', 'No result'))[:150]
                context_parts.append(f"<tool name='{html.escape(tool_name)}'>{html.escape(summary)}</tool>")
            context_parts.append("</tools_used>")

        context_parts.append("</turn>")

    context_parts.append("</conversation_context>")
    context_parts.append("\nNOTE: This is a followup query. Build upon previous conversation context.")

    return "\n".join(context_parts)


def _build_legacy_conversation_context(conversation_history: List[Dict[str, Any]], max_turns: int) -> str:
    """Legacy conversation context formatting for backward compatibility"""
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

    # Add conversation history context if available - use XML format for better parsing
    context_section = format_conversation_context(conversation_history, max_turns=3, format_type="xml")

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

    # Add conversation history context if available - use XML format for better parsing
    context_section = format_conversation_context(conversation_history, max_turns=3, format_type="xml")

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

    return f"""You are a unified planning and decision agent with advanced multi-query search capabilities. PRIORITIZE TOOL USAGE to provide comprehensive, factual information.

**PRIMARY GOAL:** Fulfill the user's request accurately and efficiently with detailed, well-structured responses.

**CONTEXT**
- CURRENT QUERY: "{html.escape(user_query)}"
{context_section}
- CURRENT STATE:
Search Results: {len(search_results)} results available
Tool Results: {len(tool_results)} tool executions completed
{executed_steps_section}{current_plan_section}
{tools_section}

**DECISION TYPES:**
1. "PLAN_AND_EXECUTE" - Create a new plan with next steps using available tools
2. "EXECUTE_NEXT_STEP" - Execute the next step from current plan
3. "GENERATE_RESPONSE" - Generate final response (ONLY when you have sufficient factual information)

**ADVANCED MULTI-QUERY SEARCH STRATEGY:**
For search tools, implement comprehensive multi-perspective coverage:

1. **ORIGINAL QUERY EXECUTION**: Always execute the user's original query exactly as provided first
2. **INTELLIGENT QUERY EXPANSION**: Generate 2-4 additional strategic search queries using:
   - **Semantic Diversification**: Synonyms, alternative terminology, domain-specific language
   - **Perspective Multiplexing**: Different stakeholder viewpoints (industry, academic, regulatory, consumer)
   - **Temporal Dimension**: Recent developments, trends, future projections
   - **Geographic Context**: Regional variations and global perspectives
   - **Technical Depth Variation**: Both overview and technical deep-dive queries

3. **STRATEGIC QUERY FORMULATION**:
   - **Specificity Gradient**: Mix broad conceptual with highly specific technical queries
   - **Controversy Detection**: Capture different sides of debated topics
   - **Trend Amplification**: Focus on latest developments and emerging patterns
   - **Expert Source Targeting**: Surface academic, industry, and expert perspectives
   - **Use Case Exploration**: Practical applications and real-world implementations

**MULTI-QUERY EXAMPLES:**
Original: "impact of AI on healthcare"
Expanded: ["artificial intelligence medical diagnosis accuracy 2024", "AI healthcare implementation challenges hospitals", "machine learning patient outcomes clinical trials", "healthcare AI regulation FDA approval"]

Original: "renewable energy trends"
Expanded: ["renewable energy market growth 2024", "solar wind power adoption barriers", "clean energy investment opportunities", "renewable energy policy government incentives"]

**CRITICAL REQUIREMENTS - NO HALLUCINATION:**
- Respond ONLY with valid JSON - NO TRAILING COMMAS, NO COMMENTS, NO EXTRA TEXT
- DO NOT make up information or create fictional responses
- PRIORITIZE using enabled tools to gather factual information
- Only generate final response when you have verified, factual information from tools
- If information is missing, create targeted tool calls with strategic multi-query approach

Your decision process:
1. **Analyze Information Gaps**: What factual information is still needed?
2. **Review Available Data**: Check conversation context and current tool results
3. **Tool Priority**: If enabled tools can fill information gaps, plan to use them
4. **Factual Threshold**: Only choose "GENERATE_RESPONSE" when you have sufficient verified information
5. **Search Strategy**: For missing information, create specific tool calls with optimized parameters

GENERATE_RESPONSE Criteria (ALL must be true):
- You have VERIFIED factual information from tool execution results (not just search results)
- The tool execution results directly answer the user's query with specific data
- You have executed at least one tool call that returned relevant information
- No critical information gaps remain that tools could fill
- You are not relying on assumptions, general knowledge, or speculation

**IMPORTANT**: Do NOT choose GENERATE_RESPONSE unless you have actual tool execution results. If tools are available and have not been used, you MUST choose "PLAN_AND_EXECUTE" to gather information first.

If any information is missing or unverified, or if no tools have been executed, choose "PLAN_AND_EXECUTE" with specific tool calls.

**JSON FORMAT REQUIREMENTS:**
- Use double quotes for all strings
- No trailing commas after last array/object elements
- No comments (// or /* */)
- Must be valid JSON that can be parsed by json.loads()
- Only return the JSON object, no explanatory text

**EXAMPLE PLANNING RESPONSE:**
{{
    "decision_type": "PLAN_AND_EXECUTE",
    "reasoning": "Need to search for comprehensive information using multi-query strategy",
    "plan": [
        {{
            "step_number": 1,
            "step_type": "TOOL_CALL",
            "description": "Search using original query for baseline information",
            "tool_name": "opensearch_search",
            "tool_arguments": {{"query": "user original query terms", "size": 10}}
        }},
        {{
            "step_number": 2,
            "step_type": "TOOL_CALL",
            "description": "Search with semantic diversification for broader perspective",
            "tool_name": "opensearch_search",
            "tool_arguments": {{"query": "alternative terminology expert perspective", "size": 10}}
        }},
        {{
            "step_number": 3,
            "step_type": "REASONING_STEP",
            "description": "Synthesize multi-query results for comprehensive response",
            "reasoning_content": "Analyze all search results to provide complete answer"
        }}
    ]
}}

**EXAMPLE HTML FINAL RESPONSE:**
{{
    "decision_type": "GENERATE_RESPONSE",
    "reasoning": "Have sufficient verified information from tools to provide comprehensive answer",
    "final_response": "<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.6; color: #333; max-width: 800px;'><h3 style='color: #2c3e50; font-size: 1.2em; margin-bottom: 16px; font-weight: 600;'>Query Results</h3><p style='margin-bottom: 12px;'>Based on the tool results and search findings, here are the key points:</p><ul style='margin: 12px 0; padding-left: 20px;'><li style='margin-bottom: 8px;'><strong>First key finding:</strong> Details from tool results</li><li style='margin-bottom: 8px;'><strong>Second key finding:</strong> Additional verified information</li></ul><div style='background: #f8f9fa; padding: 16px; border-radius: 6px; border-left: 3px solid #007bff; margin: 16px 0;'><h4 style='margin-top: 0; margin-bottom: 12px; color: #2c3e50; font-size: 1.1em;'>Key Insights</h4><ul style='margin: 10px 0 0 0; padding-left: 18px;'><li style='margin-bottom: 6px;'>Critical insight from analysis</li><li style='margin-bottom: 6px;'>Important implication or conclusion</li></ul></div></div>"
}}

**VALIDATION REQUIREMENTS:**
- decision_type: Must be exactly "PLAN_AND_EXECUTE", "EXECUTE_NEXT_STEP", or "GENERATE_RESPONSE"
- If PLAN_AND_EXECUTE: plan must be non-empty array, final_response must be null
- If GENERATE_RESPONSE: plan must be null, final_response must contain comprehensive response
- For TOOL_CALL steps: tool_name and tool_arguments are required
- For REASONING_STEP steps: reasoning_content is required
- reasoning is always required and must explain the decision clearly

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

    # Add conversation history context if available - use XML format for better parsing
    context_section = format_conversation_context(conversation_history, max_turns=2, format_type="xml")

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
Format your response using proper HTML formatting:

**HTML STRUCTURE FOR REASONING STEP:**
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px;">
  <h3 style="color: #2c3e50; font-size: 1.2em; margin-bottom: 16px; font-weight: 600;">Analysis</h3>
  <p style="margin-bottom: 12px;">[Your reasoning for the current step]</p>

  <h3 style="color: #2c3e50; font-size: 1.2em; margin-bottom: 16px; font-weight: 600;">Assessment</h3>
  <p style="margin-bottom: 12px;">[Whether you can provide a final answer or need more information]</p>

  <h3 style="color: #2c3e50; font-size: 1.2em; margin-bottom: 16px; font-weight: 600;">Response</h3>
  <p style="margin-bottom: 12px;">[Either your final comprehensive answer OR explanation of what additional information is needed]</p>
</div>"""
    else:
        format_instructions = """
Generate a helpful, informative response using proper HTML formatting:

**HTML FORMATTING REQUIREMENTS:**
- Use <div> with professional CSS styling as the main container
- Use <h3> for main headings with color: #2c3e50
- Use <p> for paragraphs with proper margins
- Use <ul> and <li> for bullet points with proper spacing
- Use <strong> for emphasis
- Include professional CSS styling for readability

**EXAMPLE HTML STRUCTURE:**
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px;">
  <h3 style="color: #2c3e50; font-size: 1.2em; margin-bottom: 16px; font-weight: 600;">Main Topic</h3>
  <p style="margin-bottom: 12px;">Opening paragraph with key information...</p>
  <ul style="margin: 12px 0; padding-left: 20px;">
    <li style="margin-bottom: 8px;">Key point with specific details</li>
    <li style="margin-bottom: 8px;">Another important finding</li>
  </ul>
  <div style="background: #f8f9fa; padding: 16px; border-radius: 6px; border-left: 3px solid #007bff; margin: 16px 0;">
    <h4 style="margin-top: 0; margin-bottom: 12px; color: #2c3e50; font-size: 1.1em;">Key Insights</h4>
    <ul style="margin: 10px 0 0 0; padding-left: 18px;">
      <li style="margin-bottom: 6px;">Critical finding</li>
      <li style="margin-bottom: 6px;">Important implication</li>
    </ul>
  </div>
</div>

Generate a comprehensive, well-formatted HTML response that directly addresses the user's query."""

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


def create_search_expansion_prompt(original_query: str) -> str:
    """Create a prompt for expanding search queries with strategic variations"""
    return f"""You are a search query expansion expert. Create 2-3 strategic search query variations for comprehensive coverage.

ORIGINAL QUERY: "{html.escape(original_query)}"

**ADVANCED EXPANSION STRATEGIES:**
1. **SEMANTIC DIVERSIFICATION**: Synonyms, alternative terminology, domain-specific language
2. **PERSPECTIVE MULTIPLEXING**: Different stakeholder viewpoints (industry, academic, regulatory, consumer)
3. **TEMPORAL DIMENSION**: Recent developments, trends, future projections
4. **TECHNICAL DEPTH VARIATION**: Both overview and detailed technical queries

**STRATEGIC FORMULATION PRINCIPLES:**
- **Specificity Gradient**: Mix broad conceptual with highly specific technical queries
- **Controversy Detection**: Include queries that capture different sides of debated topics
- **Trend Amplification**: Add queries focused on latest developments and emerging patterns
- **Expert Source Targeting**: Frame queries to surface academic, industry, and expert perspectives

OUTPUT FORMAT:
Return 2-3 search queries as a JSON array:
["query1", "query2", "query3"]

EXAMPLES:
Original: "AI impact healthcare"
Expanded: ["artificial intelligence medical diagnosis accuracy 2024", "AI healthcare implementation challenges hospitals", "machine learning patient outcomes clinical trials"]

Original: "renewable energy trends"
Expanded: ["renewable energy market growth 2024", "solar wind power adoption barriers", "clean energy investment opportunities"]

Create comprehensive expanded search queries for: '{html.escape(original_query)}'"""


def get_enhanced_html_response_template() -> str:
    """Returns an enhanced HTML response template for professional output formatting"""
    return """
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px;">
  <div style="margin-bottom: 24px;">
    <h3 style="color: #2c3e50; font-size: 1.2em; margin-bottom: 16px; font-weight: 600;">
      [Section Title]
    </h3>

    <p style="margin-bottom: 12px;">
      [Opening paragraph with key information]
    </p>

    <ul style="margin: 12px 0; padding-left: 20px;">
      <li style="margin-bottom: 8px;">[Key point with specific details]</li>
      <li style="margin-bottom: 8px;">[Another important finding]</li>
    </ul>

    <p style="margin-bottom: 16px;">
      [Connecting paragraph with synthesis]
    </p>
  </div>

  <div style="background: #f8f9fa; padding: 16px; border-radius: 6px; border-left: 3px solid #007bff; margin-bottom: 24px;">
    <h4 style="margin-top: 0; margin-bottom: 12px; color: #2c3e50; font-size: 1.1em;">Key Insights</h4>
    <ul style="margin: 10px 0 0 0; padding-left: 18px;">
      <li style="margin-bottom: 6px;">[Critical finding]</li>
      <li style="margin-bottom: 6px;">[Important implication]</li>
    </ul>
  </div>

  [IF_SOURCES_EXIST]
  <div style="margin-top: 24px;">
    <h3 style="color: #2c3e50; font-size: 1.1em; margin-bottom: 12px;">Sources</h3>
    <ul style="padding-left: 20px;">
      <li style="margin-bottom: 8px;">
        <strong>[Source Title]</strong> - [Brief description]
        <a href="[URL]" target="_blank" style="color: #007bff; margin-left: 8px;">🔗</a>
      </li>
    </ul>
  </div>
</div>"""

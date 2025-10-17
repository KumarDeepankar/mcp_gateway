from typing import List, Dict, Any
import json


def format_conversation_context(conversation_history: List[Dict[str, Any]], max_turns: int = 3) -> str:
    """Format conversation history concisely"""
    if not conversation_history:
        return ""

    recent = conversation_history[-max_turns:]
    context = {
        "previous_turns": [
            {
                "q": t.get('query', ''),
                "a": t.get('response', '')[:200] + "..." if len(t.get('response', '')) > 200 else t.get('response', '')
            }
            for t in recent
        ]
    }
    return f"\n<context>{json.dumps(context)}</context>"


def create_multi_task_planning_prompt(
    user_query: str,
    enabled_tools: List[Dict[str, Any]],
    conversation_history: List[Dict[str, Any]] = None
) -> str:
    """Optimized planning prompt using structured output and minimal examples"""

    context = format_conversation_context(conversation_history, max_turns=2) if conversation_history else ""

    # Simplified tool categorization
    tools = {
        "search": [t for t in enabled_tools if "search" in t.get("name", "").lower()],
        "filter": [t for t in enabled_tools if "filter" in t.get("name", "").lower() or "count" in t.get("name", "")],
        "analytics": [t for t in enabled_tools if any(x in t.get("name", "") for x in ["stats", "aggregation", "attendance"])],
        "other": []
    }

    for t in enabled_tools:
        if not any(t in category for category in tools.values()):
            tools["other"].append(t)

    tools_summary = {k: [{"name": t["name"], "params": list(t.get("inputSchema", {}).get("properties", {}).keys())}
                         for t in v[:3]] for k, v in tools.items() if v}

    return f"""You are a query planning agent. Decompose user queries into parallel executable tasks.

<tools>{json.dumps(tools_summary, indent=2)}</tools>

<query>{user_query}</query>{context}

<examples>
Query: "Find technology events in Denmark from 2022"
Analysis: Specific query with clear filters (tech, Denmark, 2022). Need events + context.
Plan:
{{
  "reasoning": "Use year filter + country filter for precision, then get stats for context",
  "tasks": [
    {{"task_number": 1, "tool_name": "filter_events_by_year", "tool_arguments": {{"year": 2022, "query": "technology", "size": 15}}, "description": "Get tech events from 2022"}},
    {{"task_number": 2, "tool_name": "filter_events_by_country", "tool_arguments": {{"country": "Denmark", "query": "technology", "size": 15}}, "description": "Verify with country filter"}},
    {{"task_number": 3, "tool_name": "get_events_stats_by_year", "tool_arguments": {{"country": "Denmark"}}, "description": "Get yearly stats for context"}}
  ]
}}

Query: "Compare renewable energy events between Denmark and Dominica"
Analysis: Comparative query needs data from both countries + size metrics.
Plan:
{{
  "reasoning": "Parallel data collection per country + attendance stats for comparison",
  "tasks": [
    {{"task_number": 1, "tool_name": "filter_events_by_country", "tool_arguments": {{"country": "Denmark", "query": "renewable energy", "size": 20}}, "description": "Denmark renewable events"}},
    {{"task_number": 2, "tool_name": "filter_events_by_country", "tool_arguments": {{"country": "Dominica", "query": "renewable energy", "size": 20}}, "description": "Dominica renewable events"}},
    {{"task_number": 3, "tool_name": "get_event_attendance_stats", "tool_arguments": {{"country": "Denmark"}}, "description": "Denmark attendance stats"}},
    {{"task_number": 4, "tool_name": "get_event_attendance_stats", "tool_arguments": {{"country": "Dominica"}}, "description": "Dominica attendance stats"}}
  ]
}}
</examples>

<rules>
- Output ONLY valid JSON (no markdown)
- 2-5 parallel tasks (no dependencies)
- Use exact tool names from available tools
- Each task: task_number, tool_name, tool_arguments, description
- Include reasoning that explains your strategy
</rules>

Generate JSON plan:"""


def create_unified_planning_decision_prompt(
    user_query: str,
    tool_results: List[Dict[str, Any]],
    enabled_tools: List[Dict[str, Any]],
    executed_steps: List[Dict[str, Any]] = None,
    conversation_history: List[Dict[str, Any]] = None,
    current_plan: List[Dict[str, Any]] = None
) -> str:
    """Optimized decision prompt using ReAct pattern"""

    context = format_conversation_context(conversation_history, max_turns=2)

    state = {
        "results_count": len(tool_results),
        "has_data": len(tool_results) > 0,
        "tools_available": [t.get("name") for t in enabled_tools[:5]]
    }

    return f"""<state>
Query: {user_query}{context}
Status: {json.dumps(state)}
</state>

Decision logic:
- No data (results_count=0) → CREATE_PLAN
- Has data → GENERATE_RESPONSE

<examples>
No data: {{"decision_type": "CREATE_PLAN", "reasoning": "Need to gather data first"}}
Has data: {{"decision_type": "GENERATE_RESPONSE", "reasoning": "Ready with {len(tool_results)} results", "response_content": "<div><h3>Title</h3><p>Answer...</p></div>"}}
</examples>

Output JSON decision:"""


def create_information_synthesis_prompt(
    user_query: str,
    gathered_information: Dict[str, Any],
    conversation_history: List[Dict[str, Any]] = None
) -> str:
    """Optimized synthesis prompt with clear structure"""

    context = format_conversation_context(conversation_history, max_turns=2)
    results = gathered_information.get("task_results", [])

    # Format results in a clear, structured way (not as raw JSON dump)
    formatted_results = []
    for idx, r in enumerate(results[:8], 1):  # Show up to 8 results
        result_text = f"SOURCE {idx}:\n"
        result_text += f"  Tool: {r.get('tool_name', 'unknown')}\n"
        result_text += f"  Task: {r.get('description', 'N/A')}\n"

        # Extract and format the actual data
        result_data = r.get('result', {})
        if isinstance(result_data, dict):
            if 'error' in result_data:
                result_text += f"  Status: Error - {result_data['error'][:150]}\n"
            else:
                # Show the actual data in a readable format
                result_text += f"  Status: Success\n"
                result_text += f"  Data: {json.dumps(result_data, indent=4)[:800]}\n"

        formatted_results.append(result_text)

    results_text = "\n".join(formatted_results)
    if len(results) > 8:
        results_text += f"\n... and {len(results) - 8} more data sources available"

    return f"""You must synthesize the tool results into a comprehensive HTML response.

CRITICAL INSTRUCTION: DO NOT echo back the source data structure below. Your job is to ANALYZE this data and CREATE a new, synthesized HTML response in the required JSON format.

<query>{user_query}</query>{context}

<source_data>
Status: Completed {gathered_information.get("completed_tasks", 0)}/{gathered_information.get("total_tasks", 0)} tasks

{results_text}
</source_data>

<required_output_format>
You MUST output a JSON object with exactly TWO fields:
1. "reasoning" - Brief explanation of your synthesis approach (1-2 sentences)
2. "response_content" - The complete HTML response as a SINGLE-LINE string

DO NOT output:
- The source data structure
- Fields like "data", "task_number", "tool_name", "arguments", "result"
- Any structure that resembles the input data

ONLY output the synthesis in this exact format:
{{
  "reasoning": "your synthesis approach here",
  "response_content": "<div>your complete HTML here</div>"
}}
</required_output_format>

<synthesis_requirements>
1. ANALYZE the source data above and extract key information
2. CREATE a narrative response with clear sections (h3/h4 headings)
3. INCLUDE specific details: numbers, names, dates from the data
4. FORMAT as simple HTML (h3, h4, p, ul, li, strong, table - no fancy CSS)
5. WRITE 300-800 words with multiple sections
6. ENSURE all HTML is on a SINGLE LINE (no newlines in response_content string)
</synthesis_requirements>

<correct_example>
{{
  "reasoning": "Analyzed event data from Denmark and created structured comparison",
  "response_content": "<div><h3>Event Analysis Results</h3><p>Based on data from 2 sources, I found <strong>15 technology events</strong> in Denmark from 2022.</p><h4>Key Events</h4><ul><li><strong>TechConf 2022:</strong> Major technology conference in Copenhagen</li><li><strong>DevSummit:</strong> Developer-focused event in Aarhus</li></ul><h4>Statistics</h4><p>Total events: 15, Average attendance: 250 participants</p></div>"
}}
</correct_example>

<wrong_example>
DO NOT output like this:
{{
  "data": [
    {{
      "task_number": 1,
      "tool_name": "filter_events",
      "result": {{...}}
    }}
  ]
}}
This is WRONG - it's just echoing the source data!
</wrong_example>

Now generate your JSON response with "reasoning" and "response_content" fields:"""


def create_reasoning_response_prompt(
    user_query: str,
    tool_results: List[Dict[str, Any]],
    conversation_history: List[Dict[str, Any]] = None,
    current_step_description: str = None,
    additional_context: Dict[str, Any] = None
) -> str:
    """Optimized reasoning response prompt"""

    context = format_conversation_context(conversation_history, max_turns=2)

    data = {
        "results": tool_results[:5] if tool_results else [],
        "count": len(tool_results),
        "task": current_step_description
    }

    if additional_context:
        data.update(additional_context)

    return f"""Generate data-driven response.

<query>{user_query}</query>{context}
<data>{json.dumps(data, indent=2)}</data>

<requirements>
- Base everything on provided data
- 200-600 words with multiple sections
- Simple HTML: h3, h4, p, ul, strong, table
- No colors or fancy styling
- Structure: Summary → Details → Insights
</requirements>

<template>
<div>
  <h3>Main Title</h3>
  <p>Summary with key findings...</p>
  <h4>Section 1: Data</h4>
  <ul>
    <li><strong>Point:</strong> Value with context</li>
  </ul>
  <h4>Section 2: Insights</h4>
  <p><strong>Key insight:</strong> Analysis with evidence...</p>
</div>
</template>

Generate detailed HTML response:"""

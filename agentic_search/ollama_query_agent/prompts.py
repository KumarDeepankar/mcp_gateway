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

    return f"""Transform tool data into comprehensive response.

<query>{user_query}</query>{context}

<data>
Completed: {gathered_information.get("completed_tasks", 0)}/{gathered_information.get("total_tasks", 0)} tasks
Results: {json.dumps(results[:5], indent=2)}{"..." if len(results) > 5 else ""}
</data>

<format_requirements>
1. DATA-DRIVEN: Use specific numbers, names, dates from results
2. STRUCTURED: Clear h3/h4 headings, organized sections
3. COMPREHENSIVE: 300-800 words, multiple sections
4. FORMAL: Simple HTML (h3, h4, p, ul, li, strong, table)
5. NO STYLING: No colors, gradients, or fancy CSS
</format_requirements>

<example>
{{
  "reasoning": "Analyzed results from tasks, structured comparison with stats and insights",
  "response_content": "<div><h3>Analysis Results</h3><p>Based on <strong>X events</strong> from data:</p><h4>Key Findings</h4><ul><li><strong>Metric 1:</strong> Value and context</li><li><strong>Metric 2:</strong> Value and context</li></ul><h4>Statistical Overview</h4><table style='width:100%;border-collapse:collapse;margin:20px 0;'><thead><tr style='border-bottom:2px solid #333;'><th style='padding:12px;text-align:left;'>Item</th><th style='padding:12px;text-align:left;'>Value</th></tr></thead><tbody><tr><td style='padding:10px;border-bottom:1px solid #ddd;'>Total</td><td style='padding:10px;border-bottom:1px solid #ddd;'>123</td></tr></tbody></table><h4>Insights</h4><p><strong>Key insight:</strong> Detailed analysis with supporting evidence from the data.</p></div>"
}}
</example>

Generate JSON response (single-line HTML, 300+ words):"""


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

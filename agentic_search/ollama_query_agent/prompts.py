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


def create_information_synthesis_prompt(
    user_query: str,
    gathered_information: Dict[str, Any],
    conversation_history: List[Dict[str, Any]] = None
) -> str:
    """Enhanced synthesis prompt for rich structured HTML"""

    context = format_conversation_context(conversation_history, max_turns=2)
    results = gathered_information.get("task_results", [])

    # Format results in a clear, structured way
    formatted_results = []
    for idx, r in enumerate(results[:8], 1):
        result_text = f"SOURCE {idx}:\n"
        result_text += f"  Tool: {r.get('tool_name', 'unknown')}\n"
        result_text += f"  Task: {r.get('description', 'N/A')}\n"

        result_data = r.get('result', {})
        if isinstance(result_data, dict):
            if 'error' in result_data:
                result_text += f"  Status: Error - {result_data['error'][:150]}\n"
            else:
                result_text += f"  Status: Success\n"
                result_text += f"  Data: {json.dumps(result_data, indent=4)[:800]}\n"

        formatted_results.append(result_text)

    results_text = "\n".join(formatted_results)
    if len(results) > 8:
        results_text += f"\n... and {len(results) - 8} more sources"

    return f"""Create structured HTML response from the data below. Output ONLY valid JSON.

Query: {user_query}{context}

Data from {gathered_information.get("completed_tasks", 0)} sources:
{results_text}

HTML REQUIREMENTS:
- Use h3, h4, p, ul/li, strong tags
- Tables: style='width:100%;border-collapse:collapse;margin:15px 0;'
- Single quotes in HTML (avoid escaping complexity)
- Clean, professional formatting

CRITICAL JSON RULES:
1. Output ONLY JSON - no markdown, no code blocks, no extra text
2. Two fields ONLY: "reasoning" and "response_content"
3. HTML must be on ONE LINE inside "response_content" string
4. NO newlines/line breaks inside JSON string values
5. NO control characters (tabs, returns, etc)
6. Start with {{ and end with }}
7. Use double quotes for JSON keys/values
8. Escape any double quotes inside HTML with backslash

CORRECT FORMAT:
{{"reasoning":"Brief analysis","response_content":"<div><h3>Title</h3><p>Content with <strong>emphasis</strong>.</p></div>"}}

Example 1 - List format:
{{"reasoning":"Found 23 tech events in Denmark","response_content":"<div><h3>Technology Events in Denmark</h3><p>Discovered <strong>23 events</strong> across multiple cities.</p><h4>Key Findings</h4><ul><li><strong>Copenhagen Summit</strong> - 5,000 attendees</li><li><strong>AI Conference 2024</strong> - Focus on machine learning</li><li><strong>Tech Meetup</strong> - 500 participants</li></ul><p>Geographic distribution: Copenhagen (<strong>18</strong>), Aarhus (<strong>5</strong>).</p></div>"}}

Example 2 - Comparison with table:
{{"reasoning":"Compared event activity between two countries","response_content":"<div><h3>Denmark vs Dominica: Event Comparison</h3><p>Denmark shows significantly higher event activity with <strong>45 events</strong> compared to Dominica's <strong>3 events</strong>.</p><table style='width:100%;border-collapse:collapse;margin:15px 0;'><thead><tr style='border-bottom:2px solid #333;background:#f5f5f5;'><th style='padding:10px;text-align:left;'>Country</th><th style='padding:10px;text-align:left;'>Total Events</th><th style='padding:10px;text-align:left;'>Avg Attendance</th></tr></thead><tbody><tr style='border-bottom:1px solid #ddd;'><td style='padding:10px;'>Denmark</td><td style='padding:10px;'>45</td><td style='padding:10px;'>250</td></tr><tr style='border-bottom:1px solid #ddd;'><td style='padding:10px;'>Dominica</td><td style='padding:10px;'>3</td><td style='padding:10px;'>80</td></tr></tbody></table><p>Denmark's event ecosystem is approximately <strong>15x larger</strong> in scale.</p></div>"}}

NOW GENERATE - Remember: ONE LINE of JSON, NO newlines inside strings:"""

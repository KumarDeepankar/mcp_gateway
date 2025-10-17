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

    # Enhanced tool categorization with descriptions
    tools = {
        "search": [t for t in enabled_tools if "search" in t.get("name", "").lower()],
        "filter": [t for t in enabled_tools if "filter" in t.get("name", "").lower() or "count" in t.get("name", "")],
        "analytics": [t for t in enabled_tools if any(x in t.get("name", "") for x in ["stats", "aggregation", "attendance"])],
        "other": []
    }

    for t in enabled_tools:
        if not any(t in category for category in tools.values()):
            tools["other"].append(t)

    # Enhanced tool summary with descriptions and parameter details
    tools_summary = {}
    for k, v in tools.items():
        if not v:
            continue
        tools_summary[k] = []
        for t in v[:5]:  # Show up to 5 tools per category
            input_schema = t.get("inputSchema", {})
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            # Build parameter details with types and descriptions
            param_details = {}
            for param_name, param_info in properties.items():
                param_details[param_name] = {
                    "type": param_info.get("type", "any"),
                    "required": param_name in required
                }
                if "description" in param_info:
                    param_details[param_name]["description"] = param_info["description"][:100]  # Limit length

            tool_summary = {
                "name": t["name"],
                "description": t.get("description", "No description available")[:200],  # Include tool description!
                "parameters": param_details
            }
            tools_summary[k].append(tool_summary)

    return f"""<role>You are an expert query planning agent. Your specialty is analyzing user queries and selecting the most appropriate tools to gather comprehensive information.</role>

<task>Decompose the user's query into 2-5 parallel executable tasks using the available tools below. Choose tools based on their descriptions and the user's intent.</task>

<available_tools>
{json.dumps(tools_summary, indent=2)}
</available_tools>

<user_query>{user_query}</user_query>{context}

<planning_instructions>
1. READ the user query carefully and identify what information they need
2. REVIEW the available tools and their descriptions to understand what each tool does
3. SELECT the most relevant tools that will provide the information needed
4. CREATE 2-5 parallel tasks (tasks that can run simultaneously, no dependencies)
5. For each task, specify:
   - task_number: Sequential number (1, 2, 3, ...)
   - tool_name: EXACT name from available tools
   - tool_arguments: Dictionary with required and optional parameters (check "required": true)
   - description: Brief explanation of what this task will accomplish
6. WRITE reasoning that explains your tool selection strategy
</planning_instructions>

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

<output_rules>
- Output ONLY valid JSON (no markdown, no code blocks)
- Start with {{ and end with }}
- Two fields: "reasoning" (string) and "tasks" (array)
- 2-5 parallel tasks (no dependencies between tasks)
- Use EXACT tool names from available tools
- Include all required parameters for each tool
- Each task needs: task_number, tool_name, tool_arguments, description
</output_rules>

Generate JSON plan now:"""


def create_information_synthesis_prompt(
    user_query: str,
    gathered_information: Dict[str, Any],
    conversation_history: List[Dict[str, Any]] = None
) -> str:
    """Advanced synthesis prompt using CoT, role-based prompting, and structured reasoning"""

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

    return f"""<role>You are an expert data analyst and technical writer. Your specialty is transforming raw data from multiple sources into clear, insightful narratives that directly answer user questions. You excel at extracting key insights, identifying patterns, and presenting information in well-structured HTML format.</role>

<task>Analyze the source data below and create a comprehensive narrative response to the user's query. DO NOT echo the raw data structure - instead, synthesize the information into a cohesive story.</task>

<user_query>{user_query}</user_query>{context}

<source_data>
{results_text}
</source_data>

<reasoning_process>
Follow this Chain of Thought process:

STEP 1 - COMPREHENSION:
- What is the user really asking for?
- What type of answer would best serve their needs? (comparison, overview, analysis, trends, specific facts)

STEP 2 - DATA EXTRACTION:
- Read through ALL source data carefully
- Extract key facts: numbers, names, dates, locations, categories, trends
- Identify patterns, anomalies, or interesting insights
- Note any data quality issues or gaps

STEP 3 - SYNTHESIS STRATEGY:
- Decide on narrative structure (chronological, comparative, categorical, problem-solution)
- Plan sections: what should come first, what's most important
- Choose appropriate visualizations (tables for comparisons, lists for items, paragraphs for explanation)

STEP 4 - CONTENT CREATION:
- Write a compelling opening that directly addresses the query
- Develop 3-5 main sections with clear headings
- Use specific numbers and facts from the data (never make up information)
- Add context and interpretation where helpful
- Include a brief summary or key takeaway if appropriate

STEP 5 - HTML FORMATTING:
- Structure content with h3 (main title), h4 (section headings), p (paragraphs), ul/li (lists), table (data comparisons)
- Use <strong> for emphasis on key numbers and terms
- Add inline styles for tables: style='width:100%;border-collapse:collapse;margin:15px 0;'
- Keep HTML clean and on ONE CONTINUOUS LINE (no newlines)
</reasoning_process>

<content_requirements>
✓ DO: Extract and synthesize information into narrative form
✓ DO: Include specific numbers, names, dates, locations from the data
✓ DO: Create clear sections with descriptive headings (h3, h4)
✓ DO: Use tables to compare multiple items or show structured data
✓ DO: Write 300-800 words across multiple sections
✓ DO: Provide insights and interpretation, not just facts
✓ DO: Answer the user's question directly and completely

✗ DON'T: Copy the source data structure (task_number, tool_name, result objects)
✗ DON'T: Use technical field names from tools in your response
✗ DON'T: Leave the data uninterpreted - always add context
✗ DON'T: Make up information not present in the source data
✗ DON'T: Use vague language - be specific with numbers and facts
✗ DON'T: Create overly long paragraphs - break into digestible sections
</content_requirements>

<html_guidelines>
• Main title: <h3>Title</h3>
• Section headings: <h4>Section Name</h4>
• Paragraphs: <p>Content with <strong>emphasis</strong> on key points.</p>
• Bullet lists: <ul><li>Item one</li><li>Item two</li></ul>
• Tables: <table style='width:100%;border-collapse:collapse;margin:15px 0;'><tr><th style='border-bottom:2px solid #333;background:#f5f5f5;padding:8px;text-align:left;'>Header</th></tr><tr><td style='padding:8px;border-bottom:1px solid #ddd;'>Data</td></tr></table>
• Use single quotes for ALL HTML attributes
• Keep ALL HTML on ONE LINE (critical for JSON validity)
</html_guidelines>

<output_format>
CRITICAL: Output EXACTLY ONE LINE of JSON with this structure:
{{"reasoning":"Your 1-2 sentence analysis strategy","response_content":"<div>YOUR FULL HTML RESPONSE HERE</div>"}}

Rules:
1. Start with {{ and end with }}
2. Two fields only: "reasoning" and "response_content"
3. NO newlines, tabs, or control characters inside string values
4. NO markdown formatting, NO code blocks
5. ALL HTML must be on ONE continuous line inside response_content
6. Use double quotes for JSON structure, single quotes for HTML attributes
7. Escape any internal double quotes with backslash if needed
</output_format>

<examples>
Example 1 - Simple Query:
Query: "How many events in Denmark?"
Good: {{"reasoning":"Counted total events from search results","response_content":"<div><h3>Denmark Events Overview</h3><p>Based on the search results, Denmark hosted <strong>47 events</strong> across various categories. The events were distributed across major cities, with Copenhagen accounting for <strong>31 events</strong> (66%) and Aarhus hosting <strong>16 events</strong> (34%).</p><h4>Key Statistics</h4><ul><li>Total events: 47</li><li>Average attendance: 180 participants</li><li>Most common category: Technology (18 events)</li></ul></div>"}}

Example 2 - Comparative Query:
Query: "Compare AI conferences between USA and UK"
Good: {{"reasoning":"Analyzed conference data from both countries focusing on size, topics, and attendance","response_content":"<div><h3>USA vs UK AI Conference Comparison</h3><p>Both countries demonstrated strong AI conference activity, with distinct characteristics in each market.</p><h4>Volume and Scale</h4><p>The <strong>USA hosted 89 AI conferences</strong> compared to the UK's <strong>34 conferences</strong>. However, UK conferences showed higher average attendance at <strong>520 participants</strong> versus <strong>380 in the USA</strong>, suggesting more consolidated events.</p><h4>Regional Distribution</h4><table style='width:100%;border-collapse:collapse;margin:15px 0;'><tr><th style='border-bottom:2px solid #333;background:#f5f5f5;padding:8px;text-align:left;'>Metric</th><th style='border-bottom:2px solid #333;background:#f5f5f5;padding:8px;text-align:left;'>USA</th><th style='border-bottom:2px solid #333;background:#f5f5f5;padding:8px;text-align:left;'>UK</th></tr><tr><td style='padding:8px;border-bottom:1px solid #ddd;'>Total Conferences</td><td style='padding:8px;border-bottom:1px solid #ddd;'>89</td><td style='padding:8px;border-bottom:1px solid #ddd;'>34</td></tr><tr><td style='padding:8px;border-bottom:1px solid #ddd;'>Avg Attendance</td><td style='padding:8px;border-bottom:1px solid #ddd;'>380</td><td style='padding:8px;border-bottom:1px solid #ddd;'>520</td></tr><tr><td style='padding:8px;border-bottom:1px solid #ddd;'>Top Location</td><td style='padding:8px;border-bottom:1px solid #ddd;'>San Francisco (23)</td><td style='padding:8px;border-bottom:1px solid #ddd;'>London (28)</td></tr></table><h4>Topic Focus</h4><p>USA conferences emphasized <strong>applied AI and enterprise applications</strong>, while UK events focused more on <strong>AI ethics and policy frameworks</strong>.</p></div>"}}

Example 3 - BAD (echoing data structure):
{{"task_results":[{{"task_number":1,"tool_name":"search_events","result":{{"events":[{{"id":"evt_123","name":"Conference"}}]}}}}]}}
❌ This is WRONG - it's just copying the source data structure!

Example 4 - BAD (incomplete synthesis):
{{"reasoning":"Found events","response_content":"<div><p>There are events in the database.</p></div>"}}
❌ This is WRONG - too vague, no specific numbers or insights!
</examples>

<final_instruction>
Now, following the Chain of Thought reasoning process above, analyze the source data and generate ONE LINE of JSON containing your synthesized narrative response. Remember: synthesize and interpret the data, don't echo it!</final_instruction>"""

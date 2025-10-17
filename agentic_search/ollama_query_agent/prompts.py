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
Query: "Find SOP-2847 and related incidents"
Analysis: Specific SOP ID search. Need SOP document + incidents linked to this SOP.
Plan:
{{
  "reasoning": "Search for specific SOP ID and find incidents that reference or are related to this SOP",
  "tasks": [
    {{"task_number": 1, "tool_name": "search_documents", "tool_arguments": {{"query": "SOP-2847", "size": 10}}, "description": "Search for SOP-2847 document"}},
    {{"task_number": 2, "tool_name": "search_incidents", "tool_arguments": {{"query": "SOP-2847", "size": 15}}, "description": "Find incidents referencing SOP-2847"}},
    {{"task_number": 3, "tool_name": "get_related_documents", "tool_arguments": {{"doc_id": "SOP-2847", "size": 10}}, "description": "Get related SOPs and procedures"}}
  ]
}}

Query: "What are the common causes of database connection timeout incidents?"
Analysis: Cause analysis query. Need incidents with this cause + aggregated statistics.
Plan:
{{
  "reasoning": "Search for database timeout incidents and aggregate causes to identify patterns",
  "tasks": [
    {{"task_number": 1, "tool_name": "search_incidents", "tool_arguments": {{"query": "database connection timeout", "size": 25}}, "description": "Search database timeout incidents"}},
    {{"task_number": 2, "tool_name": "filter_incidents_by_cause", "tool_arguments": {{"cause": "connection timeout", "category": "database", "size": 20}}, "description": "Filter by timeout cause"}},
    {{"task_number": 3, "tool_name": "aggregate_incident_causes", "tool_arguments": {{"category": "database", "limit": 10}}, "description": "Get top incident causes"}},
    {{"task_number": 4, "tool_name": "get_incident_statistics", "tool_arguments": {{"query": "connection timeout"}}, "description": "Get timeout incident statistics"}}
  ]
}}

Query: "Show all incidents caused by memory leaks in the last 30 days"
Analysis: Cause-based search with time constraint. Need recent incidents + trend data.
Plan:
{{
  "reasoning": "Filter incidents by memory leak cause and recent timeframe, include trend analysis",
  "tasks": [
    {{"task_number": 1, "tool_name": "search_incidents", "tool_arguments": {{"query": "memory leak", "size": 30}}, "description": "Search memory leak incidents"}},
    {{"task_number": 2, "tool_name": "filter_incidents_by_cause", "tool_arguments": {{"cause": "memory leak", "size": 25}}, "description": "Filter by memory leak cause"}},
    {{"task_number": 3, "tool_name": "filter_incidents_by_date", "tool_arguments": {{"days": 30, "query": "memory leak", "size": 25}}, "description": "Get incidents from last 30 days"}},
    {{"task_number": 4, "tool_name": "get_incident_trends", "tool_arguments": {{"cause": "memory leak", "period": "30d"}}, "description": "Get trend data for memory leaks"}}
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
- Write a compelling opening paragraph (2-3 sentences) that directly addresses the query
- Develop 3-5 main sections with clear h4 headings
- Use BULLET LISTS liberally to break down facts, statistics, and findings
- Keep each paragraph to 2-3 sentences maximum - break longer content into multiple paragraphs
- Use specific numbers and facts from the data (never make up information)
- Add context and interpretation where helpful
- Include highlight boxes for key insights or summary statements
- Emphasize important numbers and terms with <strong> tags

STEP 5 - HTML FORMATTING:
- Structure content with h3 (main title), h4 (section headings), p (paragraphs), ul/li (lists), table (data comparisons)
- Use <strong> for emphasis on key numbers and terms
- Add inline styles for tables: style='width:100%;border-collapse:collapse;margin:15px 0;'
- Keep HTML clean and on ONE CONTINUOUS LINE (no newlines)
</reasoning_process>

<content_requirements>
✓ DO: Extract and synthesize information into narrative form with professional styling
✓ DO: Include specific numbers, names, dates, locations from the data
✓ DO: Create clear sections with descriptive headings (h3 for main title, h4 for sections)
✓ DO: Use bullet lists liberally to break down information into digestible points
✓ DO: Keep paragraphs SHORT (2-3 sentences maximum) for readability
✓ DO: Add section headings frequently (every 2-3 paragraphs)
✓ DO: Use tables to compare multiple items or show structured data
✓ DO: Add highlight boxes for key insights or summaries
✓ DO: Write 300-800 words across multiple well-structured sections
✓ DO: Provide insights and interpretation, not just facts
✓ DO: Answer the user's question directly and completely
✓ DO: Use professional color scheme (blues, grays) and proper spacing

✗ DON'T: Copy the source data structure (task_number, tool_name, result objects)
✗ DON'T: Use technical field names from tools in your response
✗ DON'T: Leave the data uninterpreted - always add context
✗ DON'T: Make up information not present in the source data
✗ DON'T: Use vague language - be specific with numbers and facts
✗ DON'T: Create long paragraphs - break into multiple short paragraphs
✗ DON'T: Write walls of text - use bullet lists to improve scannability
✗ DON'T: Forget styling - always apply the professional CSS styles provided
</content_requirements>

<html_styling_guidelines>
Structure your response with professional, readable styling:

CONTAINER:
<div style='font-family:system-ui,-apple-system,sans-serif;line-height:1.6;color:#2c3e50;max-width:100%;'>

MAIN TITLE (use for overall topic):
<h3 style='color:#1a1a1a;font-size:1.5em;font-weight:600;margin:0 0 20px 0;padding-bottom:12px;border-bottom:3px solid #3498db;'>Title</h3>

SECTION HEADINGS (use frequently to break content):
<h4 style='color:#2c3e50;font-size:1.2em;font-weight:600;margin:24px 0 12px 0;'>Section Name</h4>

PARAGRAPHS (keep short, 2-3 sentences max):
<p style='margin:0 0 16px 0;line-height:1.7;color:#34495e;'>Content with <strong style='color:#2c3e50;font-weight:600;'>emphasis</strong> on key numbers and terms.</p>

BULLET LISTS (use liberally for facts, features, items):
<ul style='margin:12px 0;padding-left:24px;line-height:1.8;'>
<li style='margin:8px 0;color:#34495e;'>Item with <strong style='color:#2c3e50;'>emphasis</strong></li>
<li style='margin:8px 0;color:#34495e;'>Another item</li>
</ul>

NUMBERED LISTS (for steps or rankings):
<ol style='margin:12px 0;padding-left:24px;line-height:1.8;'>
<li style='margin:8px 0;color:#34495e;'>First item</li>
<li style='margin:8px 0;color:#34495e;'>Second item</li>
</ol>

HIGHLIGHT BOXES (for key insights or summaries):
<div style='background:#f8f9fa;border-left:4px solid #3498db;padding:16px;margin:20px 0;border-radius:4px;'>
<p style='margin:0;color:#2c3e50;font-weight:500;'>Key insight or summary statement</p>
</div>

TABLES (for comparisons and structured data):
<table style='width:100%;border-collapse:collapse;margin:20px 0;border:1px solid #e1e8ed;'>
<thead><tr style='background:#f8f9fa;'>
<th style='padding:12px;text-align:left;font-weight:600;color:#2c3e50;border-bottom:2px solid #3498db;'>Header</th>
</tr></thead>
<tbody><tr style='border-bottom:1px solid #e1e8ed;'>
<td style='padding:12px;color:#34495e;'>Data</td>
</tr></tbody>
</table>

IMPORTANT NOTES:
• Use single quotes for ALL HTML attributes
• Keep ALL HTML on ONE LINE (critical for JSON validity)
• Use bullet lists frequently (break down information)
• Keep paragraphs short (2-3 sentences)
• Add section headings every 2-3 paragraphs
• Use highlight boxes for key takeaways
• Emphasize numbers and important terms with <strong>
</html_styling_guidelines>

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
Example 1 - Simple Query with Professional Styling:
Query: "How many events in Denmark?"
Good: {{"reasoning":"Analyzed event data and created structured overview with key metrics","response_content":"<div style='font-family:system-ui,-apple-system,sans-serif;line-height:1.6;color:#2c3e50;'><h3 style='color:#1a1a1a;font-size:1.5em;font-weight:600;margin:0 0 20px 0;padding-bottom:12px;border-bottom:3px solid #3498db;'>Denmark Events Overview</h3><p style='margin:0 0 16px 0;line-height:1.7;color:#34495e;'>Based on comprehensive search results, Denmark hosted a total of <strong style='color:#2c3e50;font-weight:600;'>47 events</strong> across various categories and locations.</p><h4 style='color:#2c3e50;font-size:1.2em;font-weight:600;margin:24px 0 12px 0;'>Geographic Distribution</h4><ul style='margin:12px 0;padding-left:24px;line-height:1.8;'><li style='margin:8px 0;color:#34495e;'><strong style='color:#2c3e50;'>Copenhagen:</strong> 31 events (66% of total)</li><li style='margin:8px 0;color:#34495e;'><strong style='color:#2c3e50;'>Aarhus:</strong> 16 events (34% of total)</li></ul><h4 style='color:#2c3e50;font-size:1.2em;font-weight:600;margin:24px 0 12px 0;'>Key Statistics</h4><ul style='margin:12px 0;padding-left:24px;line-height:1.8;'><li style='margin:8px 0;color:#34495e;'>Average attendance: <strong style='color:#2c3e50;'>180 participants</strong></li><li style='margin:8px 0;color:#34495e;'>Most common category: <strong style='color:#2c3e50;'>Technology (18 events)</strong></li><li style='margin:8px 0;color:#34495e;'>Second most common: <strong style='color:#2c3e50;'>Business (12 events)</strong></li></ul><div style='background:#f8f9fa;border-left:4px solid #3498db;padding:16px;margin:20px 0;border-radius:4px;'><p style='margin:0;color:#2c3e50;font-weight:500;'>Denmark demonstrates a strong concentration of events in major urban centers, with Copenhagen serving as the primary hub for large-scale gatherings.</p></div></div>"}}

Example 2 - Comparative Query with Tables:
Query: "Compare AI conferences between USA and UK"
Good: {{"reasoning":"Compared conference metrics across both countries with focus on volume, attendance, and thematic differences","response_content":"<div style='font-family:system-ui,-apple-system,sans-serif;line-height:1.6;color:#2c3e50;'><h3 style='color:#1a1a1a;font-size:1.5em;font-weight:600;margin:0 0 20px 0;padding-bottom:12px;border-bottom:3px solid #3498db;'>USA vs UK AI Conference Comparison</h3><p style='margin:0 0 16px 0;line-height:1.7;color:#34495e;'>Both countries demonstrate strong AI conference activity, with distinct characteristics in scale and focus areas.</p><h4 style='color:#2c3e50;font-size:1.2em;font-weight:600;margin:24px 0 12px 0;'>Volume and Scale Analysis</h4><p style='margin:0 0 16px 0;line-height:1.7;color:#34495e;'>The United States shows significantly higher conference volume, while the UK demonstrates more consolidated event structures.</p><table style='width:100%;border-collapse:collapse;margin:20px 0;border:1px solid #e1e8ed;'><thead><tr style='background:#f8f9fa;'><th style='padding:12px;text-align:left;font-weight:600;color:#2c3e50;border-bottom:2px solid #3498db;'>Metric</th><th style='padding:12px;text-align:left;font-weight:600;color:#2c3e50;border-bottom:2px solid #3498db;'>USA</th><th style='padding:12px;text-align:left;font-weight:600;color:#2c3e50;border-bottom:2px solid #3498db;'>UK</th></tr></thead><tbody><tr style='border-bottom:1px solid #e1e8ed;'><td style='padding:12px;color:#34495e;'>Total Conferences</td><td style='padding:12px;color:#34495e;'><strong style='color:#2c3e50;'>89</strong></td><td style='padding:12px;color:#34495e;'><strong style='color:#2c3e50;'>34</strong></td></tr><tr style='border-bottom:1px solid #e1e8ed;'><td style='padding:12px;color:#34495e;'>Avg Attendance</td><td style='padding:12px;color:#34495e;'><strong style='color:#2c3e50;'>380</strong></td><td style='padding:12px;color:#34495e;'><strong style='color:#2c3e50;'>520</strong></td></tr><tr style='border-bottom:1px solid #e1e8ed;'><td style='padding:12px;color:#34495e;'>Top Location</td><td style='padding:12px;color:#34495e;'>San Francisco (23)</td><td style='padding:12px;color:#34495e;'>London (28)</td></tr></tbody></table><h4 style='color:#2c3e50;font-size:1.2em;font-weight:600;margin:24px 0 12px 0;'>Thematic Focus Areas</h4><ul style='margin:12px 0;padding-left:24px;line-height:1.8;'><li style='margin:8px 0;color:#34495e;'><strong style='color:#2c3e50;'>USA:</strong> Applied AI, enterprise applications, machine learning infrastructure</li><li style='margin:8px 0;color:#34495e;'><strong style='color:#2c3e50;'>UK:</strong> AI ethics, policy frameworks, responsible AI development</li></ul><div style='background:#f8f9fa;border-left:4px solid #3498db;padding:16px;margin:20px 0;border-radius:4px;'><p style='margin:0;color:#2c3e50;font-weight:500;'>While the USA leads in conference quantity, UK events attract higher average attendance, suggesting more centralized, high-impact gatherings focused on strategic AI policy discussions.</p></div></div>"}}

Example 3 - BAD (echoing data structure):
{{"task_results":[{{"task_number":1,"tool_name":"search_events","result":{{"events":[{{"id":"evt_123","name":"Conference"}}]}}}}]}}
❌ This is WRONG - it's just copying the source data structure!

Example 4 - BAD (no styling, vague content):
{{"reasoning":"Found events","response_content":"<div><p>There are events in the database.</p></div>"}}
❌ This is WRONG - no styling, too vague, no structure, no specific numbers or insights!
</examples>

<final_instruction>
Now, following the Chain of Thought reasoning process above, analyze the source data and generate ONE LINE of JSON containing your synthesized narrative response. Remember: synthesize and interpret the data, don't echo it!</final_instruction>"""

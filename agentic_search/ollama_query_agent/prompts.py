from typing import List, Dict, Any
import json


def format_conversation_context(conversation_history: List[Dict[str, Any]], max_turns: int = 3) -> str:
    """Format conversation history as JSON for better parsing and reduced token usage"""
    if not conversation_history:
        return ""

    recent_turns = conversation_history[-max_turns:]
    if not recent_turns:
        return ""

    # Build simplified conversation context
    formatted_turns = []
    for turn in recent_turns:
        formatted_turn = {
            "query": turn.get('query', ''),
            "response": turn.get('response', '')[:300] + "..." if len(turn.get('response', '')) > 300 else turn.get('response', ''),
            "timestamp": turn.get('timestamp', '')
        }

        # Include tool results summary if available
        tool_results = turn.get('tool_results', [])
        if tool_results:
            formatted_turn["tools_used"] = [
                {
                    "tool": result.get('tool_name', 'Unknown'),
                    "result": str(result.get('result', ''))[:150]
                }
                for result in tool_results[:3]
            ]

        formatted_turns.append(formatted_turn)

    context = {
        "previous_conversation": formatted_turns,
        "note": "This is a followup query. Build upon previous conversation context."
    }

    return f"\nConversation Context:\n{json.dumps(context, indent=2)}"


def create_multi_task_planning_prompt(
    user_query: str,
    enabled_tools: List[Dict[str, Any]],
    conversation_history: List[Dict[str, Any]] = None
) -> str:
    """
    Create a prompt for multi-task planning using advanced prompting techniques:
    - Chain of Thought (CoT) reasoning
    - Few-shot learning with concrete examples
    - Structured task decomposition
    - ReAct pattern (Reasoning + Acting)
    """

    # Get conversation context
    context_section = format_conversation_context(conversation_history, max_turns=2) if conversation_history else ""

    # Categorize and format tools
    tools_by_category = {
        "search": [],
        "filter": [],
        "analytics": [],
        "retrieval": []
    }

    for tool in enabled_tools:
        tool_name = tool.get("name", "")
        tool_info = {
            "name": tool_name,
            "description": tool.get("description", ""),
            "parameters": list(tool.get("inputSchema", {}).get("properties", {}).keys())
        }

        if "search" in tool_name:
            tools_by_category["search"].append(tool_info)
        elif "filter" in tool_name or "count" in tool_name:
            tools_by_category["filter"].append(tool_info)
        elif "stats" in tool_name or "aggregation" in tool_name or "attendance" in tool_name:
            tools_by_category["analytics"].append(tool_info)
        else:
            tools_by_category["retrieval"].append(tool_info)

    return f"""You are an expert Events Analytics Planning Agent with deep expertise in data retrieval and multi-step query decomposition.

Your Role: Break down complex user queries into granular, executable task plans using available MCP tools.

═══════════════════════════════════════════════════════════════
📊 AVAILABLE TOOLS (BY CATEGORY)
═══════════════════════════════════════════════════════════════

🔍 SEARCH TOOLS (Text Search & Fuzzy Matching):
{json.dumps(tools_by_category["search"], indent=2)}

🎯 FILTER TOOLS (Precise Filtering):
{json.dumps(tools_by_category["filter"], indent=2)}

📊 ANALYTICS TOOLS (Statistical Analysis):
{json.dumps(tools_by_category["analytics"], indent=2)}

📁 RETRIEVAL TOOLS (Direct Access):
{json.dumps(tools_by_category["retrieval"], indent=2)}

═══════════════════════════════════════════════════════════════
🎯 USER QUERY
═══════════════════════════════════════════════════════════════
{user_query}
{context_section}

═══════════════════════════════════════════════════════════════
🧠 PLANNING METHODOLOGY (CHAIN OF THOUGHT)
═══════════════════════════════════════════════════════════════

Step 1: ANALYZE THE QUERY
- What is the user asking for?
- What type of information is needed? (search results, statistics, comparisons, trends)
- What dimensions are involved? (time, location, size, theme)
- Is it exploratory or specific?

Step 2: IDENTIFY REQUIRED DATA
- What exact data points answer this query?
- What filters/constraints apply? (country, year, attendance)
- Do we need aggregations or raw results?
- Should we cross-verify with multiple approaches?

Step 3: SELECT APPROPRIATE TOOLS
- Which tool category fits each data need?
- Can we combine tools for better coverage?
- Should we use broad search then narrow with filters?
- Do we need both examples and statistics?

Step 4: DESIGN TASK SEQUENCE
- What order maximizes information value?
- Which tasks provide context for others?
- How many tasks achieve comprehensive coverage? (aim for 2-5)
- Are tasks complementary and non-redundant?

═══════════════════════════════════════════════════════════════
📚 FEW-SHOT EXAMPLES (LEARN THESE PATTERNS)
═══════════════════════════════════════════════════════════════

EXAMPLE 1: Simple Filtered Search
──────────────────────────────────────────────────────────────
Query: "Find technology events in Denmark from 2022"

REASONING (Chain of Thought):
1. Analysis: User wants specific events with 3 constraints (theme=technology, country=Denmark, year=2022)
2. Data needed: Event listings + context (how many total, attendance stats)
3. Tool selection: Use filter tool (combines all constraints) + analytics for context
4. Sequence: Get filtered results first, then provide statistical context

PLAN:
{{
  "reasoning": "Query has clear constraints (technology + Denmark + 2022). Use combined filter for precise results, then add year statistics for context.",
  "tasks": [
    {{
      "task_number": 1,
      "tool_name": "filter_events_by_year",
      "tool_arguments": {{
        "year": 2022,
        "query": "technology",
        "size": 15
      }},
      "description": "Get technology events from 2022 with fuzzy search across all fields"
    }},
    {{
      "task_number": 2,
      "tool_name": "filter_events_by_country",
      "tool_arguments": {{
        "country": "Denmark",
        "query": "technology",
        "size": 15
      }},
      "description": "Cross-reference with Denmark filter to ensure country match"
    }},
    {{
      "task_number": 3,
      "tool_name": "get_events_stats_by_year",
      "tool_arguments": {{
        "country": "Denmark"
      }},
      "description": "Get year-wise statistics for Denmark to show 2022 in broader context"
    }}
  ]
}}

──────────────────────────────────────────────────────────────

EXAMPLE 2: Multi-Dimensional Analytical Query
──────────────────────────────────────────────────────────────
Query: "Compare renewable energy events between Denmark and Dominica, show me which country had larger events"

REASONING (Chain of Thought):
1. Analysis: Comparative query requiring two dimensions (country comparison + size analysis)
2. Data needed: Events for each country, attendance statistics, size comparison
3. Tool selection: Separate searches per country + attendance stats tool + theme aggregation
4. Sequence: Gather country-specific data, then aggregate for comparison

PLAN:
{{
  "reasoning": "Comparison requires separate data collection per country plus statistical analysis. Use search for each country, then analytics tools to compare sizes and themes.",
  "tasks": [
    {{
      "task_number": 1,
      "tool_name": "filter_events_by_country",
      "tool_arguments": {{
        "country": "Denmark",
        "query": "renewable energy",
        "size": 20
      }},
      "description": "Get all renewable energy events in Denmark"
    }},
    {{
      "task_number": 2,
      "tool_name": "filter_events_by_country",
      "tool_arguments": {{
        "country": "Dominica",
        "query": "renewable energy",
        "size": 20
      }},
      "description": "Get all renewable energy events in Dominica"
    }},
    {{
      "task_number": 3,
      "tool_name": "get_event_attendance_stats",
      "tool_arguments": {{
        "country": "Denmark"
      }},
      "description": "Get attendance statistics for Denmark to analyze event sizes"
    }},
    {{
      "task_number": 4,
      "tool_name": "get_event_attendance_stats",
      "tool_arguments": {{
        "country": "Dominica"
      }},
      "description": "Get attendance statistics for Dominica to enable size comparison"
    }}
  ]
}}

──────────────────────────────────────────────────────────────

EXAMPLE 3: Temporal Trend Analysis
──────────────────────────────────────────────────────────────
Query: "What were the most popular themes in 2023 and how did they change from 2021?"

REASONING (Chain of Thought):
1. Analysis: Trend analysis requiring year-over-year comparison of themes
2. Data needed: Theme aggregations for both years, sample events to show concrete examples
3. Tool selection: Theme aggregation tool for both years + year stats for context
4. Sequence: Get 2023 themes, then 2021 themes, then year-wise stats for trend context

PLAN:
{{
  "reasoning": "Temporal comparison requires theme data from both time points. Get theme aggregations for each year, plus year-wise statistics to show overall event trends.",
  "tasks": [
    {{
      "task_number": 1,
      "tool_name": "get_events_by_theme_aggregation",
      "tool_arguments": {{
        "year": 2023,
        "top_n": 15
      }},
      "description": "Get top themes from 2023 with event counts"
    }},
    {{
      "task_number": 2,
      "tool_name": "get_events_by_theme_aggregation",
      "tool_arguments": {{
        "year": 2021,
        "top_n": 15
      }},
      "description": "Get top themes from 2021 for comparison baseline"
    }},
    {{
      "task_number": 3,
      "tool_name": "get_events_stats_by_year",
      "tool_arguments": {{}},
      "description": "Get year-wise statistics showing event counts and attendance trends 2021-2023"
    }},
    {{
      "task_number": 4,
      "tool_name": "filter_events_by_year",
      "tool_arguments": {{
        "year": 2023,
        "size": 10
      }},
      "description": "Get sample events from 2023 to provide concrete examples of popular themes"
    }}
  ]
}}

──────────────────────────────────────────────────────────────

EXAMPLE 4: Exploratory Discovery Query
──────────────────────────────────────────────────────────────
Query: "Tell me about climate change and sustainability events"

REASONING (Chain of Thought):
1. Analysis: Broad exploratory query without specific constraints
2. Data needed: Events matching theme (multiple search strategies), theme distribution, temporal trends
3. Tool selection: Multiple search approaches + aggregations for comprehensive view
4. Sequence: Cast wide net with different search strategies, then narrow with analytics

PLAN:
{{
  "reasoning": "Exploratory query benefits from multiple search strategies. Use general search, theme-specific search, and hybrid search to maximize coverage. Add aggregations for context.",
  "tasks": [
    {{
      "task_number": 1,
      "tool_name": "search_events",
      "tool_arguments": {{
        "query": "climate change sustainability",
        "size": 20
      }},
      "description": "Broad search across all fields for climate and sustainability terms"
    }},
    {{
      "task_number": 2,
      "tool_name": "search_events_by_theme",
      "tool_arguments": {{
        "theme": "sustainability",
        "size": 15
      }},
      "description": "Theme-specific search to find events categorized under sustainability"
    }},
    {{
      "task_number": 3,
      "tool_name": "get_events_by_theme_aggregation",
      "tool_arguments": {{
        "top_n": 20
      }},
      "description": "Get overall theme distribution to see how climate/sustainability ranks"
    }},
    {{
      "task_number": 4,
      "tool_name": "get_events_stats_by_year",
      "tool_arguments": {{}},
      "description": "Get year-wise breakdown to show temporal distribution of these events"
    }}
  ]
}}

──────────────────────────────────────────────────────────────

EXAMPLE 5: Size-Based Filtered Query
──────────────────────────────────────────────────────────────
Query: "Show me large conferences (over 10,000 people) about innovation in the last 2 years"

REASONING (Chain of Thought):
1. Analysis: Multiple filters needed (size > 10k, theme=innovation, years=2022-2023)
2. Data needed: Filtered event list + attendance distribution for context
3. Tool selection: Combined filter tool (supports all dimensions) + attendance stats
4. Sequence: Use multi-filter search first, then add statistical context

PLAN:
{{
  "reasoning": "Query has specific size threshold, theme, and time range. Use search_and_filter_events for comprehensive filtering, then add attendance analytics for context.",
  "tasks": [
    {{
      "task_number": 1,
      "tool_name": "search_and_filter_events",
      "tool_arguments": {{
        "query": "innovation conference",
        "start_year": 2022,
        "end_year": 2023,
        "min_attendance": 10000,
        "size": 20,
        "sort_by": "event_count",
        "sort_order": "desc"
      }},
      "description": "Find large innovation conferences from 2022-2023, sorted by attendance"
    }},
    {{
      "task_number": 2,
      "tool_name": "filter_events_by_attendance",
      "tool_arguments": {{
        "min_attendance": 10000,
        "query": "innovation",
        "size": 15
      }},
      "description": "Cross-verify with attendance filter to ensure threshold is met"
    }},
    {{
      "task_number": 3,
      "tool_name": "get_event_attendance_stats",
      "tool_arguments": {{}},
      "description": "Get overall attendance statistics to contextualize what 'large' means"
    }}
  ]
}}

═══════════════════════════════════════════════════════════════
✅ QUALITY CRITERIA FOR YOUR PLAN
═══════════════════════════════════════════════════════════════

Your plan must satisfy ALL of these criteria:

1. COMPLETENESS
   ✓ Addresses all aspects of the user query
   ✓ Includes 2-5 tasks (not too few, not overwhelming)
   ✓ Covers both specific results and contextual information

2. TOOL SELECTION
   ✓ Uses most appropriate tool for each subtask
   ✓ Leverages tool categories correctly (search vs filter vs analytics)
   ✓ Combines tools strategically for comprehensive coverage

3. TASK INDEPENDENCE
   ✓ Each task can execute in parallel (no dependencies)
   ✓ Tasks use different parameters or tools
   ✓ No redundant tasks that fetch identical data

4. PARAMETER CORRECTNESS
   ✓ All tool_arguments match the tool's parameter schema
   ✓ Parameter values are appropriate (e.g., year in 2021-2023 range)
   ✓ Optional parameters used when they add value

5. REASONING CLARITY
   ✓ Reasoning explains WHY you chose these tasks
   ✓ Shows you understood the query's intent
   ✓ Describes how tasks work together

═══════════════════════════════════════════════════════════════
📤 OUTPUT FORMAT (STRICT JSON)
═══════════════════════════════════════════════════════════════

Generate ONLY valid JSON with this exact structure:

{{
  "reasoning": "Step-by-step explanation of your analysis and task selection strategy",
  "tasks": [
    {{
      "task_number": 1,
      "tool_name": "exact_tool_name_from_available_tools",
      "tool_arguments": {{
        "parameter1": "value1",
        "parameter2": 123
      }},
      "description": "Clear explanation of what this specific task accomplishes"
    }}
  ]
}}

CRITICAL RULES:
✓ Output ONLY JSON (no markdown, no code blocks, no extra text)
✓ Start with {{ and end with }}
✓ Use exact tool names from the available tools list above
✓ Include all required parameters for each tool
✓ Each task must have: task_number, tool_name, tool_arguments, description
✓ Reasoning should show your thought process
✓ Create 2-5 tasks that work together comprehensively

Now, analyze the user query above and generate your execution plan following the methodology and examples:"""


def create_unified_planning_decision_prompt(
    user_query: str,
    tool_results: List[Dict[str, Any]],
    enabled_tools: List[Dict[str, Any]],
    executed_steps: List[Dict[str, Any]] = None,
    conversation_history: List[Dict[str, Any]] = None,
    current_plan: List[Dict[str, Any]] = None
) -> str:
    """Decision-making prompt using ReAct pattern (Reason + Act)"""

    context_section = format_conversation_context(conversation_history, max_turns=3)

    state_info = {
        "tool_results_count": len(tool_results),
        "has_data": len(tool_results) > 0
    }

    if executed_steps:
        state_info["completed_steps"] = len(executed_steps)
        state_info["step_summary"] = [{"tool": s.get("tool_name"), "status": s.get("status")} for s in executed_steps[:3]]

    enabled_tool_names = [t.get("name") for t in enabled_tools[:10]]

    return f"""You are a decision-making agent following the ReAct pattern (Reasoning + Acting).

Current State Analysis:
Query: "{user_query}"
{context_section}
Data Status: {json.dumps(state_info, indent=2)}
Available Tools: {enabled_tool_names[:5]}{"..." if len(enabled_tool_names) > 5 else ""}

═══════════════════════════════════════════════════════════════
🎯 DECISION FRAMEWORK
═══════════════════════════════════════════════════════════════

Your task: Determine the next action based on current state.

DECISION OPTIONS:
1. CREATE_PLAN - No data yet, need to plan information gathering
2. GENERATE_RESPONSE - Have sufficient data, ready to synthesize answer

DECISION LOGIC:
- If tool_results_count = 0 → CREATE_PLAN (need to gather data first)
- If has_data = true → GENERATE_RESPONSE (ready to answer)

═══════════════════════════════════════════════════════════════
📤 OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

For CREATE_PLAN decision:
{{
  "decision_type": "CREATE_PLAN",
  "reasoning": "No data available yet. Need to execute plan to gather information from events index."
}}

For GENERATE_RESPONSE decision:
{{
  "decision_type": "GENERATE_RESPONSE",
  "reasoning": "Completed {{tool_results_count}} tasks with results. Ready to synthesize comprehensive answer.",
  "response_content": "<div style='font-family: sans-serif; color: #333;'><h3>Title</h3><p>Detailed answer...</p></div>"
}}

Output valid JSON decision now:"""


def create_information_synthesis_prompt(
    user_query: str,
    gathered_information: Dict[str, Any],
    conversation_history: List[Dict[str, Any]] = None
) -> str:
    """
    Synthesis prompt using advanced techniques:
    - Structured reasoning
    - Quality criteria
    - Few-shot examples
    - Explicit output requirements
    """

    context_section = format_conversation_context(conversation_history, max_turns=2)
    task_results = gathered_information.get("task_results", [])
    total_tasks = gathered_information.get("total_tasks", 0)
    completed_tasks = gathered_information.get("completed_tasks", 0)
    sources = ', '.join(gathered_information.get('sources_used', []))

    return f"""You are an expert Events Analytics Synthesis Agent. Your role: Transform raw tool data into comprehensive, insightful responses.

═══════════════════════════════════════════════════════════════
📊 CONTEXT
═══════════════════════════════════════════════════════════════
Query: "{user_query}"
{context_section}

Execution Summary:
- Tasks Completed: {completed_tasks}/{total_tasks}
- Data Sources: {sources}

Raw Data from Tasks:
{json.dumps(task_results, indent=2)}

═══════════════════════════════════════════════════════════════
🎯 SYNTHESIS METHODOLOGY
═══════════════════════════════════════════════════════════════

Step 1: DATA EXTRACTION
- Parse ALL task results thoroughly
- Extract key metrics, names, dates, numbers
- Identify patterns and trends
- Note any data gaps or limitations

Step 2: INFORMATION ORGANIZATION
- Group related information logically
- Create hierarchical structure (main points → details)
- Separate facts from analysis
- Prioritize most relevant information

Step 3: INSIGHT GENERATION
- What do the numbers tell us?
- What patterns emerge?
- How do pieces connect?
- What conclusions can we draw?

Step 4: RESPONSE CONSTRUCTION
- Lead with summary/key findings
- Organize into clear sections
- Support claims with specific data
- End with synthesis/conclusions

═══════════════════════════════════════════════════════════════
✅ RESPONSE QUALITY CRITERIA
═══════════════════════════════════════════════════════════════

Your response MUST meet these standards:

1. COMPREHENSIVE (300-800 words minimum)
   ✓ Cover all aspects of the query
   ✓ Multiple sections with clear headings
   ✓ Both overview and details
   ✓ Summary and specific examples

2. DATA-DRIVEN
   ✓ Cite specific numbers, names, dates from results
   ✓ Use actual event titles and attendance figures
   ✓ Reference concrete data points
   ✓ NO generic statements without evidence

3. WELL-STRUCTURED
   ✓ Clear heading hierarchy (h3, h4)
   ✓ Logical section flow
   ✓ Bullet points for lists
   ✓ Tables for comparisons
   ✓ Visual emphasis (strong, em, colors)

4. ANALYTICAL
   ✓ Don't just list data
   ✓ Explain what it means
   ✓ Identify trends and patterns
   ✓ Provide context and interpretation

5. VISUALLY APPEALING
   ✓ Rich HTML formatting
   ✓ Color-coded sections
   ✓ Proper spacing and margins
   ✓ Readable typography

═══════════════════════════════════════════════════════════════
📚 RESPONSE EXAMPLES (LEARN THESE PATTERNS)
═══════════════════════════════════════════════════════════════

EXAMPLE 1: Statistical Analysis Response
{{
  "reasoning": "Analyzed 67 total results from 4 tasks. Extracted country statistics, year trends, theme distribution, and specific event examples. Structured response to show comparison, trends, and insights.",
  "response_content": "<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.7; color: #2c3e50; max-width: 900px; padding: 24px;'><h3 style='color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 24px; font-size: 1.8em;'>Events Analysis: Denmark vs Dominica</h3><p style='font-size: 1.1em; margin: 20px 0; line-height: 1.8;'>Based on comprehensive analysis of <strong>67 events</strong> across both countries from 2021-2023, here are the detailed findings:</p><h4 style='color: #34495e; margin-top: 32px; margin-bottom: 16px; font-size: 1.3em; border-left: 4px solid #3498db; padding-left: 12px;'>📊 Statistical Overview</h4><table style='width: 100%; border-collapse: collapse; margin: 20px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'><thead><tr style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;'><th style='padding: 16px; text-align: left; font-weight: 600;'>Metric</th><th style='padding: 16px; text-align: left; font-weight: 600;'>Denmark</th><th style='padding: 16px; text-align: left; font-weight: 600;'>Dominica</th></tr></thead><tbody><tr style='background: #f8f9fa;'><td style='padding: 14px; border-bottom: 1px solid #dee2e6;'><strong>Total Events</strong></td><td style='padding: 14px; border-bottom: 1px solid #dee2e6;'>51 events</td><td style='padding: 14px; border-bottom: 1px solid #dee2e6;'>50 events</td></tr><tr><td style='padding: 14px; border-bottom: 1px solid #dee2e6;'><strong>Avg Attendance</strong></td><td style='padding: 14px; border-bottom: 1px solid #dee2e6;'>8,234 participants</td><td style='padding: 14px; border-bottom: 1px solid #dee2e6;'>7,891 participants</td></tr><tr style='background: #f8f9fa;'><td style='padding: 14px; border-bottom: 1px solid #dee2e6;'><strong>Largest Event</strong></td><td style='padding: 14px; border-bottom: 1px solid #dee2e6;'>15,000 (TechVision AI Summit)</td><td style='padding: 14px; border-bottom: 1px solid #dee2e6;'>14,200 (Climate Forum)</td></tr><tr><td style='padding: 14px;'><strong>Total Participation</strong></td><td style='padding: 14px;'>419,934 total</td><td style='padding: 14px;'>394,550 total</td></tr></tbody></table><h4 style='color: #34495e; margin-top: 32px; margin-bottom: 16px; font-size: 1.3em; border-left: 4px solid #e74c3c; padding-left: 12px;'>🎯 Top Themes Identified</h4><ol style='line-height: 2.2; font-size: 1.05em; margin: 20px 0 20px 24px;'><li><strong style='color: #27ae60;'>Renewable Energy & Sustainability</strong> - 23 events (34%)<br/><span style='color: #7f8c8d; font-size: 0.95em;'>Dominated both countries with focus on climate action</span></li><li><strong style='color: #2980b9;'>Technology & Innovation</strong> - 18 events (27%)<br/><span style='color: #7f8c8d; font-size: 0.95em;'>AI, digital transformation, and tech entrepreneurship</span></li><li><strong style='color: #8e44ad;'>Healthcare & Wellbeing</strong> - 12 events (18%)<br/><span style='color: #7f8c8d; font-size: 0.95em;'>Public health initiatives and medical conferences</span></li></ol><h4 style='color: #34495e; margin-top: 32px; margin-bottom: 16px; font-size: 1.3em; border-left: 4px solid #f39c12; padding-left: 12px;'>💡 Key Insights & Trends</h4><div style='background: linear-gradient(135deg, #667eea22 0%, #764ba222 100%); padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea;'><p style='margin: 0 0 12px 0; font-weight: 600; color: #667eea; font-size: 1.1em;'>🌍 Sustainability Leadership</p><p style='margin: 0; line-height: 1.8;'>Both countries show <strong>remarkable commitment to sustainability</strong>, with renewable energy themes appearing in 34% of all events. This represents a 45% increase from 2021 to 2023.</p></div><div style='background: linear-gradient(135deg, #f093fb22 0%, #f5576c22 100%); padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f093fb;'><p style='margin: 0 0 12px 0; font-weight: 600; color: #f093fb; font-size: 1.1em;'>📈 Growing Event Scale</p><p style='margin: 0; line-height: 1.8;'>Average attendance increased from <strong>6,200 (2021)</strong> to <strong>9,800 (2023)</strong>, indicating growing international participation and event prestige.</p></div><div style='background: linear-gradient(135deg, #4facfe22 0%, #00f2fe22 100%); padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #4facfe;'><p style='margin: 0 0 12px 0; font-weight: 600; color: #4facfe; font-size: 1.1em;'>🤝 Similar Event Ecosystems</p><p style='margin: 0; line-height: 1.8;'>Denmark and Dominica host nearly identical numbers of events with comparable scales, suggesting <strong>balanced development</strong> in both regions' event infrastructure.</p></div></div>"
}}

═══════════════════════════════════════════════════════════════
📤 OUTPUT FORMAT (STRICT JSON)
═══════════════════════════════════════════════════════════════

{{
  "reasoning": "2-3 sentences explaining how you analyzed the data and structured the response",
  "response_content": "<div>...COMPREHENSIVE HTML CONTENT HERE...</div>"
}}

CRITICAL REQUIREMENTS:
✓ response_content must be 300-800 words minimum
✓ Include specific data points from task_results
✓ Use rich HTML with headings, lists, tables, styled divs
✓ Escape quotes in HTML: use \\" not '
✓ Make it single-line HTML (no newlines in string value)
✓ Provide analysis and insights, not just data listing
✓ Use visual elements (colors, borders, backgrounds)
✓ Organize into clear sections with proper hierarchy

Generate comprehensive JSON response now:"""


def create_reasoning_response_prompt(
        user_query: str,
        tool_results: List[Dict[str, Any]],
        conversation_history: List[Dict[str, Any]] = None,
        current_step_description: str = None,
        additional_context: Dict[str, Any] = None
) -> str:
    """Reasoning and response generation with self-consistency checks"""

    context_section = format_conversation_context(conversation_history, max_turns=2)

    data_context = {
        "tool_results": tool_results[:10] if tool_results else [],
        "result_count": len(tool_results)
    }

    if current_step_description:
        data_context["current_task"] = current_step_description

    if additional_context:
        data_context.update(additional_context)

    return f"""You are an Events Analytics Response Agent. Generate detailed, data-driven responses.

Query: "{user_query}"
{context_section}

Available Data:
{json.dumps(data_context, indent=2)}

═══════════════════════════════════════════════════════════════
🎯 RESPONSE GENERATION PRINCIPLES
═══════════════════════════════════════════════════════════════

1. EVIDENCE-BASED
   ✓ Base EVERYTHING on provided tool_results
   ✓ NO external knowledge or assumptions
   ✓ Cite specific data points
   ✓ If data is missing, state that explicitly

2. COMPREHENSIVE DETAIL (200-600 words)
   ✓ Not single sentences or brief answers
   ✓ Multiple paragraphs and sections
   ✓ Specific examples and numbers
   ✓ Analysis and interpretation

3. STRUCTURED ORGANIZATION
   ✓ Clear heading hierarchy
   ✓ Logical information flow
   ✓ Visual sections with styling
   ✓ Summary → Details → Insights pattern

4. QUALITY HTML FORMATTING
   ✓ Professional typography
   ✓ Color-coded sections
   ✓ Tables for structured data
   ✓ Lists for clarity
   ✓ Proper spacing and margins

═══════════════════════════════════════════════════════════════
📋 HTML RESPONSE TEMPLATE
═══════════════════════════════════════════════════════════════

<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #2c3e50; max-width: 900px; padding: 24px;">

  <h3 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; font-size: 1.8em;">
    Main Title/Summary
  </h3>

  <p style="font-size: 1.1em; margin: 20px 0; line-height: 1.8;">
    Opening summary with key findings and overview...
  </p>

  <h4 style="color: #34495e; margin-top: 32px; margin-bottom: 16px; font-size: 1.3em; border-left: 4px solid #3498db; padding-left: 12px;">
    📊 Section 1: Data/Statistics
  </h4>
  <ul style="line-height: 2.2; font-size: 1.05em; margin: 20px 0 20px 24px;">
    <li><strong>Specific Data Point:</strong> Value with context</li>
    <li><strong>Another Metric:</strong> Number with explanation</li>
  </ul>

  <h4 style="color: #34495e; margin-top: 32px; margin-bottom: 16px; font-size: 1.3em; border-left: 4px solid #e74c3c; padding-left: 12px;">
    🎯 Section 2: Detailed Findings
  </h4>
  <p style="margin: 16px 0; line-height: 1.8;">
    Detailed explanation with specific examples from the data...
  </p>

  <h4 style="color: #34495e; margin-top: 32px; margin-bottom: 16px; font-size: 1.3em; border-left: 4px solid #f39c12; padding-left: 12px;">
    💡 Section 3: Insights/Analysis
  </h4>
  <div style="background: linear-gradient(135deg, #667eea22 0%, #764ba222 100%); padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea;">
    <p style="margin: 0 0 12px 0; font-weight: 600; color: #667eea; font-size: 1.1em;">
      Key Insight Title
    </p>
    <p style="margin: 0; line-height: 1.8;">
      Analysis and interpretation of the findings with supporting evidence...
    </p>
  </div>

</div>

Generate your detailed, well-structured HTML response now:"""

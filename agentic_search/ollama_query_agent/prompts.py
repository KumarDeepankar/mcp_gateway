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


def create_unified_planning_decision_prompt(
    user_query: str,
    tool_results: List[Dict[str, Any]],
    enabled_tools: List[Dict[str, Any]],
    executed_steps: List[Dict[str, Any]] = None,
    conversation_history: List[Dict[str, Any]] = None,
    current_plan: List[Dict[str, Any]] = None
) -> str:
    """Create a unified prompt for planning, decision-making, and response generation"""

    # Add conversation history context if available
    context_section = format_conversation_context(conversation_history, max_turns=3)

    # Build state context
    state_info = {
        "tool_results_count": len(tool_results)
    }

    if executed_steps:
        state_info["executed_steps"] = executed_steps[:5]  # Limit to recent steps

    if current_plan:
        # Convert PlanStep objects to dictionaries
        plan_dicts = []
        for step in current_plan:
            if hasattr(step, 'model_dump'):
                plan_dicts.append(step.model_dump())
            elif hasattr(step, '__dict__'):
                plan_dicts.append(step.__dict__)
            else:
                plan_dicts.append(step)
        state_info["remaining_steps"] = plan_dicts[:3]  # Show next 3 steps

    # Tool information (already filtered to enabled tools only)
    enabled_tool_info = [
        {
            "name": tool.get("name"),
            "description": tool.get("description", ""),
            "input_schema": tool.get("inputSchema", {})
        }
        for tool in enabled_tools
    ]

    return f"""You are a planning and decision agent. Decide the next action to take.

Query: {user_query}
{context_section}

Current State:
{json.dumps(state_info, indent=2)}

Available Tools:
{json.dumps(enabled_tool_info, indent=2)}

DECISION TYPES:
1. "PLAN_AND_EXECUTE" - Create plan with TOOL_CALL steps only
2. "GENERATE_RESPONSE" - Generate final response when you have sufficient information

CRITICAL REQUIREMENTS:
- Respond with valid JSON only
- ONLY use TOOL_CALL step type (NO reasoning steps, NO other types)
- Every step MUST have a tool_name from the available tools list
- Use tools before generating final response when possible
- Only choose GENERATE_RESPONSE when you have tool results that answer the query

Response format for planning (ONLY TOOL_CALL steps allowed):
{{
    "decision_type": "PLAN_AND_EXECUTE",
    "reasoning": "Need to gather information using tools",
    "plan": [
        {{
            "step_number": 1,
            "step_type": "TOOL_CALL",
            "description": "Search for information",
            "tool_name": "search_stories",
            "tool_arguments": {{"query": "search terms", "size": 10}}
        }},
        {{
            "step_number": 2,
            "step_type": "TOOL_CALL",
            "description": "Fetch additional data",
            "tool_name": "fetch_news",
            "tool_arguments": {{"topic": "AI"}}
        }}
    ]
}}

Response format for final answer:
{{
    "decision_type": "GENERATE_RESPONSE",
    "reasoning": "Have sufficient information from tools",
    "final_response": "<div style='font-family: sans-serif; color: #333;'><h3>Results</h3><p>Answer based on tool results...</p></div>"
}}

Generate valid JSON:"""


def create_reasoning_response_prompt(
        user_query: str,
        tool_results: List[Dict[str, Any]],
        conversation_history: List[Dict[str, Any]] = None,
        current_step_description: str = None,
        additional_context: Dict[str, Any] = None
) -> str:
    """Create a prompt for reasoning and response generation"""

    # Add conversation history context if available
    context_section = format_conversation_context(conversation_history, max_turns=2)

    # Prepare data context
    data_context = {
        "tool_results": tool_results[:5] if tool_results else []
    }

    if current_step_description:
        data_context["reasoning_task"] = current_step_description

    if additional_context:
        data_context["additional_context"] = additional_context

    return f"""You are an information assistant. Answer based on provided data only.

Query: {user_query}
{context_section}

Data:
{json.dumps(data_context, indent=2)}

REQUIREMENTS:
- Base response ONLY on tool results and conversation context
- Do NOT add external knowledge or assumptions
- If information is incomplete, state what is missing
- Use HTML formatting for response

HTML Response Format:
<div style="font-family: sans-serif; line-height: 1.6; color: #333; max-width: 800px;">
  <h3 style="color: #2c3e50;">Title</h3>
  <p>Key information from sources...</p>
  <ul>
    <li>Finding from tool results</li>
    <li>Additional information</li>
  </ul>
</div>

Generate HTML response based on the data above:"""

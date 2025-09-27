# himan_ai/agentic_assistant/gemini_query_agent/utils.py
import html
import json
from typing import List, Dict, Any
from .llm_models import UnifiedPlannerDecisionOutput, PlanStep  # Updated import


def create_fallback_response(output_model: type, messages: List[Dict[str, str]], error_context: str = ""):
    print(
        f"DEBUG_GEMINI_AGENT_UTILS (create_fallback_response): Fallback for {output_model.__name__}. Error: {error_context}")

    if output_model == UnifiedPlannerDecisionOutput:
        # Fallback for the unified node should be to respond directly with an error message.
        error_html = f"""<div class="response-container error-response">
<h2>Assistant Error</h2>
<p>I encountered an issue while processing your request: <strong>{html.escape(error_context) or 'An unexpected error occurred.'}</strong></p>
<p>Please try rephrasing your query, or try again later.</p>
</div>"""
        return UnifiedPlannerDecisionOutput(
            action_type="RESPOND_DIRECTLY",
            response_summary_html=error_html,
            decision_reasoning=f"Fallback triggered due to error: {error_context or 'Unified planner/decider LLM call failed or response malformed.'}",
            plan=None,
            overall_plan_reasoning=None
        )

    # Add other specific fallbacks if needed for other Pydantic models if they are introduced elsewhere
    print(
        f"DEBUG_GEMINI_AGENT_UTILS (create_fallback_response): No specific fallback logic for {output_model.__name__}, attempting default instantiation.")
    try:
        # For other models, try to return a default initialized model if possible
        # This might not always be meaningful, depending on the model's structure and required fields.
        return output_model()
    except Exception as e:
        print(
            f"DEBUG_GEMINI_AGENT_UTILS (create_fallback_response): Could not default-initialize {output_model.__name__}: {e}")
        return None  # Ultimate fallback if model cannot be default initialized


def format_tools_for_llm_prompt(tools: List[Dict[str, Any]]) -> str:
    if not tools:
        return "No tools available."
    return json.dumps(tools, indent=2)
# himan_ai/agentic_assistant/gemini_query_agent/state_definition.py
import operator
from typing import TypedDict, List, Tuple, Dict, Any, Optional, Annotated
from .llm_models import PlanStep  # Assuming PlanStep is in llm_models


class PlanExecuteAgentState(TypedDict):
    input: str
    conversation_id: Optional[str]
    user_query_history: Annotated[List[Dict[str, str]], operator.add]

    # NEW: Full conversation history across multiple turns
    conversation_history: Annotated[List[Dict[str, str]], operator.add]

    available_tools_for_planner: List[Dict[str, Any]]
    formatted_tools_for_planner_prompt: str

    user_selected_tools: List[str]
    user_selected_tool_definitions: List[Dict[str, Any]]

    original_plan: Optional[List[PlanStep]]
    plan: Optional[List[PlanStep]]

    current_step_to_execute: Optional[PlanStep]
    # MODIFIED: Changed from Tuple to Dict for richer step data
    past_steps: Annotated[List[Dict[str, Any]], operator.add]

    current_ai_response_text: Optional[str]
    final_response_generated_flag: Optional[bool]
    turn_sources: Optional[List[Dict[str, Any]]]
    turn_charts: Optional[List[Dict[str, Any]]]

    thinking_steps: Optional[List[str]]
    error_message: Optional[str]

    # New fields for iteration control and evaluation
    current_turn_iteration_count: int
    max_turn_iterations: int
    turn_start_time: float
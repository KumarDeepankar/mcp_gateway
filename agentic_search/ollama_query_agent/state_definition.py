from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel


class PlanStep(BaseModel):
    step_number: int
    step_type: str  # "TOOL_CALL" or "REASONING_STEP"
    description: str
    tool_name: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    reasoning_content: Optional[str] = None


class ConversationTurn(BaseModel):
    query: str
    response: str
    timestamp: str
    tool_results: Optional[List[Dict[str, Any]]] = None


class SearchAgentState(TypedDict):
    # Core input/output
    input: str
    conversation_id: str

    # Conversation history for followup queries
    conversation_history: List[ConversationTurn]
    is_followup_query: bool

    # Planning and execution
    plan: Optional[List[PlanStep]]
    current_step_to_execute: Optional[PlanStep]
    current_step_index: int

    # Tool management
    available_tools: List[Dict[str, Any]]
    enabled_tools: List[str]  # List of tool names that user has enabled

    # Response generation
    thinking_steps: List[str]
    final_response_generated_flag: bool
    final_response_content: Optional[str]  # Store final response as string instead

    # Error handling
    error_message: Optional[str]

    # Search results
    search_results: List[Dict[str, Any]]

    # Tool execution results
    tool_execution_results: List[Dict[str, Any]]

    # Iteration control to prevent infinite loops (matching agentic_assistant naming)
    current_turn_iteration_count: int
    max_turn_iterations: int
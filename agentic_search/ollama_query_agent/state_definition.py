from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel


class PlanStep(BaseModel):
    step_number: int
    step_type: str  # "TOOL_CALL" only
    description: str
    tool_name: str
    tool_arguments: Optional[Dict[str, Any]] = None


class ConversationTurn(BaseModel):
    query: str
    response: str


class SearchAgentState(TypedDict):
    # Core input/output
    input: str
    conversation_id: str

    # Conversation history for followup queries
    conversation_history: List[ConversationTurn]
    is_followup_query: bool

    # Planning and execution
    plan: Optional[List[PlanStep]]
    current_step_index: int

    # Tool management
    available_tools: List[Dict[str, Any]]
    enabled_tools: List[str]  # List of tool names that user has enabled

    # Response generation
    thinking_steps: List[str]
    final_response_generated_flag: bool
    final_response_content: Optional[str]

    # Error handling
    error_message: Optional[str]

    # Tool execution results
    tool_execution_results: List[Dict[str, Any]]

    # Iteration control to prevent infinite loops
    current_turn_iteration_count: int
    max_turn_iterations: int
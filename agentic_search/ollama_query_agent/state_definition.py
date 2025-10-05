from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Task(BaseModel):
    """Represents a single task in the execution plan"""
    task_number: int = Field(..., description="Sequential task number")
    tool_name: str = Field(..., description="Name of the tool to call")
    tool_arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool call")
    description: str = Field(..., description="Human-readable description of what this task does")
    status: str = Field(default="pending", description="Status: pending, executing, completed, failed")
    result: Optional[Any] = Field(default=None, description="Result from tool execution")


class ExecutionPlan(BaseModel):
    """Represents the complete execution plan with multiple tasks"""
    tasks: List[Task] = Field(default_factory=list, description="List of tasks to execute")
    reasoning: str = Field(..., description="Reasoning behind this plan")
    plan_created_at: Optional[str] = Field(default=None, description="Timestamp when plan was created")


class GatheredInformation(BaseModel):
    """Structured information gathered from all task executions"""
    task_results: List[Dict[str, Any]] = Field(default_factory=list, description="Results from each task")
    summary: Optional[str] = Field(default=None, description="Summary of all gathered information")
    sources_used: List[str] = Field(default_factory=list, description="List of tools/sources used")


class FinalResponse(BaseModel):
    """Structured final response to user"""
    response_content: str = Field(..., description="HTML formatted response content")
    reasoning: str = Field(..., description="Reasoning process for the response")
    information_used: Optional[GatheredInformation] = Field(default=None, description="Information used to create response")


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

    # Multi-task planning and execution
    execution_plan: Optional[ExecutionPlan]
    current_task_index: int
    gathered_information: Optional[GatheredInformation]

    # Tool management
    available_tools: List[Dict[str, Any]]
    enabled_tools: List[str]  # List of tool names that user has enabled

    # Response generation
    thinking_steps: List[str]
    final_response_generated_flag: bool
    final_response: Optional[FinalResponse]

    # Error handling
    error_message: Optional[str]

    # Iteration control to prevent infinite loops
    current_turn_iteration_count: int
    max_turn_iterations: int
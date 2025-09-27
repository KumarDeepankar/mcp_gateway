from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool_name: str = Field(
        # MODIFIED: Updated example tool names
        description="The name of the tool to be called (e.g., 'search_web', 'data_analyzer_and_visualizer', "
                    "'specific_graph_plotter').")
    arguments: Dict[str, Any] = Field(default_factory=dict,
                                      description="A valid JSON object for tool arguments. ALL keys and ALL string values MUST be double-quoted. Numeric/boolean values should NOT be quoted.")


class PlanStep(BaseModel):
    step_type: Literal["TOOL_CALL", "REASONING_STEP"] = Field(description="The type of this plan step.")
    description: str = Field(
        description="For REASONING_STEP, the detailed description of the action. For TOOL_CALL, a natural language description of *why* this tool is being called and what it's expected to achieve.")
    tool_call_details: Optional[ToolCall] = Field(default=None,
                                                  description="If step_type is TOOL_CALL, this field MUST contain the 'tool_name' and 'arguments' (as a JSON object) for the invocation. Otherwise, it should be null.")


class UnifiedPlannerDecisionOutput(BaseModel):
    action_type: Literal["PLAN_NEXT_STEPS", "RESPOND_DIRECTLY"] = Field(
        description="The primary action the agent should take: either formulate/continue a plan, or respond directly to the user."
    )
    plan: Optional[List[PlanStep]] = Field(
        default=None,
        description="A list of structured plan steps to achieve the objective. Required if action_type is 'PLAN_NEXT_STEPS'."
    )
    overall_plan_reasoning: Optional[str] = Field(
        default=None,
        description="Brief overall reasoning if a new plan is created or significantly updated."
    )
    response_summary_html: Optional[str] = Field(
        default=None,
        description="If action_type is 'RESPOND_DIRECTLY', this is the comprehensive final HTML response. Otherwise, null."
    )
    decision_reasoning: str = Field(
        description="Brief reasoning for the chosen action_type (PLAN_NEXT_STEPS or RESPOND_DIRECTLY) and the content of the plan or response."
    )

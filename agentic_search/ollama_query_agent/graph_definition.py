from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state_definition import SearchAgentState
from .nodes import (
    initialize_search_node,
    discover_tools_node,
    prepare_next_step_node,
    execute_tool_step_node,
    unified_planning_decision_node
)


# --- Conditional Edges ---

def route_after_unified_decision(state: SearchAgentState) -> str:
    """Route after unified planning and decision"""
    if state.get("error_message"):
        return "__end__"

    if state.get("final_response_generated_flag"):
        return "__end__"

    # If we have a plan, prepare the next step
    plan = state.get("plan", [])
    if plan:
        return "prepare_next_step_node"
    else:
        return "__end__"


def route_after_step_preparation(state: SearchAgentState) -> str:
    """Route after preparing the next step"""
    if state.get("error_message"):
        return "unified_planning_decision_node"

    current_step = state.get("current_step_to_execute")

    if not current_step:
        return "unified_planning_decision_node"

    # Both tool calls and reasoning steps are handled by execute_tool_step_node
    if current_step.step_type in ["TOOL_CALL", "REASONING_STEP"]:
        return "execute_tool_step_node"
    else:
        return "unified_planning_decision_node"


# --- Graph Definition ---
checkpointer = MemorySaver()
workflow = StateGraph(SearchAgentState)

# Add nodes
workflow.add_node("initialize_search_node", initialize_search_node)
workflow.add_node("discover_tools_node", discover_tools_node)
workflow.add_node("unified_planning_decision_node", unified_planning_decision_node)
workflow.add_node("prepare_next_step_node", prepare_next_step_node)
workflow.add_node("execute_tool_step_node", execute_tool_step_node)

# Define edges
workflow.set_entry_point("initialize_search_node")
workflow.add_edge("initialize_search_node", "discover_tools_node")
workflow.add_edge("discover_tools_node", "unified_planning_decision_node")

# Conditional routing after unified decision
workflow.add_conditional_edges(
    "unified_planning_decision_node",
    route_after_unified_decision,
    {
        "prepare_next_step_node": "prepare_next_step_node",
        "__end__": END
    }
)

# Route after step preparation
workflow.add_conditional_edges(
    "prepare_next_step_node",
    route_after_step_preparation,
    {
        "execute_tool_step_node": "execute_tool_step_node",
        "unified_planning_decision_node": "unified_planning_decision_node"
    }
)

# After execution, always go back to unified decision node
workflow.add_edge("execute_tool_step_node", "unified_planning_decision_node")

# Compile the agent
compiled_agent = workflow.compile(checkpointer=checkpointer)
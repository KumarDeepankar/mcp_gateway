from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state_definition import SearchAgentState
from .nodes import (
    initialize_search_node,
    discover_tools_node,
    execute_tool_step_node,
    unified_planning_decision_node
)


# --- Conditional Edges ---

def route_after_unified_decision(state: SearchAgentState) -> str:
    """Route after unified planning and decision"""
    if state.get("error_message") or state.get("final_response_generated_flag"):
        return "__end__"

    # If we have remaining steps in plan, execute next step
    plan = state.get("plan", [])
    current_index = state.get("current_step_index", 0)

    if plan and current_index < len(plan):
        return "execute_tool_step_node"
    else:
        return "__end__"


# --- Graph Definition ---
checkpointer = MemorySaver()
workflow = StateGraph(SearchAgentState)

# Add nodes
workflow.add_node("initialize_search_node", initialize_search_node)
workflow.add_node("discover_tools_node", discover_tools_node)
workflow.add_node("unified_planning_decision_node", unified_planning_decision_node)
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
        "execute_tool_step_node": "execute_tool_step_node",
        "__end__": END
    }
)

# After execution, go back to unified decision node
workflow.add_edge("execute_tool_step_node", "unified_planning_decision_node")

# Compile the agent
compiled_agent = workflow.compile(checkpointer=checkpointer)
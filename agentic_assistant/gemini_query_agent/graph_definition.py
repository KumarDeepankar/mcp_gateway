# agentic_assistant/gemini_query_agent/graph_definition.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state_definition import PlanExecuteAgentState
from .nodes import (
    initialize_and_update_history_node,
    discover_tools_and_agents_node,
    unified_planning_and_decision_node,
    prepare_current_step_for_execution_node,
    execute_tool_step_node,
    execute_reasoning_step_node
)


# --- Conditional Edges ---

def route_after_unified_planning_decision(state: PlanExecuteAgentState) -> str:
    if state.get("final_response_generated_flag"):
        return "__end__"

    if state.get("error_message"):
        return "__end__"

    current_plan = state.get("plan")
    if current_plan:
        return "prepare_current_step_node"
    else:
        state["error_message"] = state.get("error_message",
                                           "Unified node decided to plan but returned an empty plan, or failed to set "
                                           "final response flag.")
        return "__end__"


def route_step_execution_type(state: PlanExecuteAgentState) -> str:
    current_step = state.get("current_step_to_execute")

    if state.get("error_message"):
        return "unified_planning_and_decision_node"

    if not current_step:
        return "unified_planning_and_decision_node"

    if current_step.step_type == "TOOL_CALL":
        return "execute_tool_step_node"
    elif current_step.step_type == "REASONING_STEP":
        return "execute_reasoning_step_node"
    else:
        state["error_message"] = f"Unknown plan step type: {current_step.step_type}"
        return "unified_planning_and_decision_node"


# --- Graph Definition ---
checkpointer = MemorySaver()
workflow = StateGraph(PlanExecuteAgentState)

# Add nodes
workflow.add_node("initialize_and_update_history_node", initialize_and_update_history_node)
workflow.add_node("discover_tools_and_agents_node", discover_tools_and_agents_node)
workflow.add_node("unified_planning_and_decision_node", unified_planning_and_decision_node)
workflow.add_node("prepare_current_step_node", prepare_current_step_for_execution_node)
workflow.add_node("execute_tool_step_node", execute_tool_step_node)
workflow.add_node("execute_reasoning_step_node", execute_reasoning_step_node)

# Define edges
workflow.set_entry_point("initialize_and_update_history_node")
workflow.add_edge("initialize_and_update_history_node", "discover_tools_and_agents_node")
workflow.add_edge("discover_tools_and_agents_node", "unified_planning_and_decision_node")

# Conditional routing after the unified node makes its decision
workflow.add_conditional_edges(
    "unified_planning_and_decision_node",
    route_after_unified_planning_decision,
    {
        "prepare_current_step_node": "prepare_current_step_node",
        "__end__": END
    }
)

# Conditional routing after preparing a step
workflow.add_conditional_edges(
    "prepare_current_step_node",
    route_step_execution_type,
    {
        "execute_tool_step_node": "execute_tool_step_node",
        "execute_reasoning_step_node": "execute_reasoning_step_node",
        "unified_planning_and_decision_node": "unified_planning_and_decision_node"
    }
)

# After execution, always go back to the unified node to decide next action
workflow.add_edge("execute_tool_step_node", "unified_planning_and_decision_node")
workflow.add_edge("execute_reasoning_step_node", "unified_planning_and_decision_node")

compiled_agent = workflow.compile(checkpointer=checkpointer)
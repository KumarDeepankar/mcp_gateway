from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state_definition import SearchAgentState
from .nodes import (
    initialize_search_node,
    discover_tools_node,
    create_execution_plan_node,
    execute_all_tasks_parallel_node,
    gather_and_synthesize_node
)


# --- Conditional Edges ---

def route_after_plan_creation(state: SearchAgentState) -> str:
    """Route after creating execution plan"""
    if state.get("error_message") or not state.get("execution_plan"):
        return "__end__"

    # Start parallel execution of all tasks
    return "execute_all_tasks_parallel_node"


def route_after_parallel_execution(state: SearchAgentState) -> str:
    """Route after parallel task execution - always go to synthesis"""
    # All tasks executed in parallel, now synthesize
    return "gather_and_synthesize_node"


def route_after_synthesis(state: SearchAgentState) -> str:
    """Route after synthesis - always end"""
    return "__end__"


# --- Graph Definition ---
checkpointer = MemorySaver()
workflow = StateGraph(SearchAgentState)

# Add nodes for the parallel execution workflow
workflow.add_node("initialize_search_node", initialize_search_node)
workflow.add_node("discover_tools_node", discover_tools_node)
workflow.add_node("create_execution_plan_node", create_execution_plan_node)
workflow.add_node("execute_all_tasks_parallel_node", execute_all_tasks_parallel_node)
workflow.add_node("gather_and_synthesize_node", gather_and_synthesize_node)

# Define the workflow edges
workflow.set_entry_point("initialize_search_node")
workflow.add_edge("initialize_search_node", "discover_tools_node")
workflow.add_edge("discover_tools_node", "create_execution_plan_node")

# Conditional routing after plan creation
workflow.add_conditional_edges(
    "create_execution_plan_node",
    route_after_plan_creation,
    {
        "execute_all_tasks_parallel_node": "execute_all_tasks_parallel_node",
        "__end__": END
    }
)

# After parallel execution, always go to synthesis
workflow.add_conditional_edges(
    "execute_all_tasks_parallel_node",
    route_after_parallel_execution,
    {
        "gather_and_synthesize_node": "gather_and_synthesize_node"
    }
)

# After synthesis, always end
workflow.add_conditional_edges(
    "gather_and_synthesize_node",
    route_after_synthesis,
    {
        "__end__": END
    }
)

# Compile the agent
compiled_agent = workflow.compile(checkpointer=checkpointer)
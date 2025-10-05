# Agentic Search - Agent Flow Explanation

## Overview

The multi-task agentic search agent follows a structured workflow with **2 LLM calls per query** (in the typical case with 2-3 tasks).

## Workflow Diagram

```
User Query
    ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. initialize_search_node                                   │
│    - Initialize state variables                             │
│    - Set up conversation history                            │
│    - No LLM call                                            │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. discover_tools_node                                      │
│    - Fetch available tools from MCP registry (port 8021)   │
│    - Filter to enabled tools only                           │
│    - No LLM call                                            │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. create_execution_plan_node                               │
│    - ⚡ LLM CALL #1: Create multi-task plan                │
│    - Input: User query + Available tools                    │
│    - Output: ExecutionPlan with 2-3 tasks                   │
│    - Each task specifies: tool_name, tool_arguments         │
└────────────────────┬────────────────────────────────────────┘
                     ↓
         ┌───────────┴───────────┐
         ↓                       ↓
    ┌─────────────────────────────────────────┐
    │ 4. execute_task_node (Task 1)           │
    │    - Execute tool via MCP                │
    │    - Store result in task object         │
    │    - No LLM call (just tool execution)   │
    └────────────────┬─────────────────────────┘
                     ↓
    ┌─────────────────────────────────────────┐
    │ 4. execute_task_node (Task 2)           │
    │    - Execute tool via MCP                │
    │    - Store result in task object         │
    │    - No LLM call (just tool execution)   │
    └────────────────┬─────────────────────────┘
                     ↓
    ┌─────────────────────────────────────────┐
    │ 4. execute_task_node (Task 3)           │
    │    - Execute tool via MCP                │
    │    - Store result in task object         │
    │    - No LLM call (just tool execution)   │
    └────────────────┬─────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. gather_and_synthesize_node                               │
│    - Gather all task results                                │
│    - ⚡ LLM CALL #2: Synthesize information                │
│    - Input: User query + All task results                   │
│    - Output: FinalResponse with HTML content                │
└────────────────────┬────────────────────────────────────────┘
                     ↓
                  END
                   ↓
            Final Response to User
```

## Detailed Node Breakdown

### 1. **initialize_search_node**
**Purpose**: Set up the search session

**Operations**:
- Initialize state fields:
  - `thinking_steps = []`
  - `current_task_index = 0`
  - `final_response_generated_flag = False`
  - `execution_plan = None`
  - `gathered_information = None`
- Load conversation history (for follow-up queries)
- Set iteration limits

**LLM Calls**: 0
**Tool Calls**: 0

---

### 2. **discover_tools_node**
**Purpose**: Discover available tools from MCP registry

**Operations**:
- Call `mcp_tool_client.get_available_tools()` (HTTP to port 8021)
- Filter tools based on `enabled_tools` list
- Store in `state["available_tools"]`

**LLM Calls**: 0
**Tool Calls**: 0 (HTTP call to MCP registry)

---

### 3. **create_execution_plan_node** ⚡
**Purpose**: Create multi-task execution plan using LLM

**LLM Call Details**:
- **Prompt**: `create_multi_task_planning_prompt()`
  - User query
  - Available tools (name + parameters)
  - Simplified and concise format
- **System Prompt**: "JSON-only planning agent"
- **Expected Output**: JSON with `reasoning` and `tasks` array

**Example Output**:
```json
{
  "reasoning": "Need to search multiple aspects",
  "tasks": [
    {
      "task_number": 1,
      "tool_name": "search_stories",
      "tool_arguments": {"query": "upstream keyword", "size": 10},
      "description": "Search for upstream stories"
    },
    {
      "task_number": 2,
      "tool_name": "search_stories",
      "tool_arguments": {"query": "upstream tag:backend", "size": 5},
      "description": "Search backend stories with upstream"
    }
  ]
}
```

**Error Handling**:
- If JSON parsing fails → Creates fallback 1-task plan
- Uses first enabled tool with basic parameters

**LLM Calls**: 1
**Tool Calls**: 0

---

### 4. **execute_task_node** (Loops N times)
**Purpose**: Execute one task from the plan

**Operations** (per task):
1. Update task status: `pending` → `executing`
2. Call tool via MCP: `mcp_tool_client.call_tool(tool_name, arguments)`
3. Store result in task: `task.result = result`
4. Update task status: `executing` → `completed`
5. Add full result to thinking_steps (no truncation)
6. Increment `current_task_index`

**Routing Logic**:
- If `current_task_index < len(tasks)` → Loop back to execute next task
- If all tasks done → Go to `gather_and_synthesize_node`
- If error → Still go to synthesis (with partial results)

**Example Task Execution**:
```python
# Task 1
tool_name = "search_stories"
arguments = {"query": "upstream keyword", "size": 10}
result = await mcp_tool_client.call_tool(tool_name, arguments)
# result = {"jsonrpc": "2.0", "result": {"content": [...]}}
```

**LLM Calls**: 0 (per task)
**Tool Calls**: 1 (per task) via MCP

**Total executions**: N times (where N = number of tasks in plan, typically 2-3)

---

### 5. **gather_and_synthesize_node** ⚡
**Purpose**: Synthesize all task results into final response

**Operations**:

1. **Gather Information**:
   - Collect all completed task results
   - Extract `tool_name`, `result` from each task
   - Build `GatheredInformation` object

2. **LLM Call for Synthesis**:
   - **Prompt**: `create_information_synthesis_prompt()`
     - User query
     - Task results (first 2 tasks, 200 chars each)
     - Very compact format
   - **System Prompt**: "JSON-only response agent"
   - **Expected Output**: JSON with `reasoning` and `response_content`

**Example Input to LLM**:
```json
{
  "task_results": [
    {
      "tool": "search_stories",
      "result": "Found 12 stories matching 'upstream key'..."
    },
    {
      "tool": "search_stories",
      "result": "Found 5 backend stories with upstream..."
    }
  ]
}
```

**Example Output from LLM**:
```json
{
  "reasoning": "Analyzed search results from both queries",
  "response_content": "<div style=\"color:#333\"><h3>Upstream Stories Found</h3><p>Found 17 total stories containing 'upstream' keyword...</p></div>"
}
```

3. **Create FinalResponse**:
   - Parse JSON
   - Create `FinalResponse` object
   - Set `final_response_generated_flag = True`
   - Save to conversation history

**Error Handling**:
- If JSON parsing fails → Try HTML extraction with regex
- If that fails → Generate fallback error message

**LLM Calls**: 1
**Tool Calls**: 0

---

## LLM Call Summary

### Per Query (Typical Case with 2-3 tasks):

| Node | LLM Calls | Purpose |
|------|-----------|---------|
| initialize_search_node | 0 | Setup |
| discover_tools_node | 0 | Tool discovery |
| **create_execution_plan_node** | **1** | **Plan creation** |
| execute_task_node (×N) | 0 | Tool execution only |
| **gather_and_synthesize_node** | **1** | **Response synthesis** |
| **TOTAL** | **2** | |

### Tool Calls (MCP):

| Node | Tool Calls | Type |
|------|------------|------|
| execute_task_node (×N) | N | One per task (typically 2-3) |
| **TOTAL** | **2-3** | Via MCP registry |

## Example Complete Flow

**User Query**: "How many stories have the upstream keyword?"

### Step-by-Step Execution:

1. **Initialize** - Set up state
2. **Discover Tools** - Get `search_stories` tool
3. **Plan** (LLM Call #1):
   ```json
   {
     "tasks": [
       {"tool_name": "search_stories", "tool_arguments": {"query": "upstream", "size": 50}},
       {"tool_name": "search_stories", "tool_arguments": {"query": "upstream tag:*", "size": 50}}
     ]
   }
   ```
4. **Execute Task 1** (Tool Call #1):
   - Call `search_stories(query="upstream", size=50)`
   - Result: 12 stories found
5. **Execute Task 2** (Tool Call #2):
   - Call `search_stories(query="upstream tag:*", size=50)`
   - Result: 5 stories found
6. **Synthesize** (LLM Call #2):
   - Input: Both search results
   - Output: HTML response with total count and summary

**Final Response**: "Found 17 stories containing 'upstream' keyword across different categories..."

## Performance Characteristics

### Latency Breakdown (Approximate):

| Phase | Time | Notes |
|-------|------|-------|
| Initialize + Discover | <100ms | Fast, no LLM |
| Plan Creation (LLM #1) | 2-5s | Depends on Ollama model |
| Task Execution (×N) | 0.5-2s each | Depends on MCP tool speed |
| Synthesis (LLM #2) | 2-5s | Depends on Ollama model |
| **Total** | **5-15s** | For 2-3 tasks |

### Scaling with Tasks:

- **2 tasks**: 2 LLM calls, 2 tool calls (~5-10s)
- **3 tasks**: 2 LLM calls, 3 tool calls (~7-12s)
- **5 tasks**: 2 LLM calls, 5 tool calls (~10-18s)

**Note**: LLM calls are always 2, regardless of number of tasks!

## Advantages of This Design

1. **Fixed LLM Overhead**: Always 2 LLM calls, regardless of task count
2. **Parallel-Ready**: Tasks could be executed in parallel (future enhancement)
3. **Tool Reusability**: Same tool can be used multiple times with different parameters
4. **Comprehensive Synthesis**: All task results are analyzed together
5. **Structured Data**: Pydantic models ensure type safety
6. **Error Resilient**: Fallbacks at both planning and synthesis stages

## State Persistence

- Conversation history saved after synthesis
- Checkpointer stores state per `thread_id` (session_id)
- Follow-up queries load previous context
- Max 10 conversation turns kept in history

## Iteration Control

- `max_turn_iterations = 1` (default)
- Single pass through workflow
- No re-planning based on results (current implementation)
- Future: Could add dynamic re-planning based on task results

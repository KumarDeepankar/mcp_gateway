import html
from typing import List, Dict, Any, Tuple, Optional
from .llm_models import PlanStep


class PromptBuilder:
    """Handles the construction of clean, focused prompts."""

    def __init__(self):
        self.html_template = self._get_html_response_template()

    def _get_html_response_template(self) -> str:
        """Returns a clean HTML response template."""
        return """
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px;">
  <div style="margin-bottom: 24px;">
    <h3 style="color: #2c3e50; font-size: 1.2em; margin-bottom: 16px; font-weight: 600;">
      [Section Title]
    </h3>

    <p style="margin-bottom: 12px;">
      [Opening paragraph with key information]
    </p>

    <ul style="margin: 12px 0; padding-left: 20px;">
      <li style="margin-bottom: 8px;">[Key point with specific details]</li>
      <li style="margin-bottom: 8px;">[Another important finding]</li>
    </ul>

    <p style="margin-bottom: 16px;">
      [Connecting paragraph with synthesis]
    </p>
  </div>

  <div style="background: #f8f9fa; padding: 16px; border-radius: 6px; border-left: 3px solid #007bff; margin-bottom: 24px;">
    <h4 style="margin-top: 0; margin-bottom: 12px; color: #2c3e50; font-size: 1.1em;">Key Insights</h4>
    <ul style="margin: 10px 0 0 0; padding-left: 18px;">
      <li style="margin-bottom: 6px;">[Critical finding]</li>
      <li style="margin-bottom: 6px;">[Important implication]</li>
    </ul>
  </div>

  [IF_SOURCES_EXIST]
  <div style="margin-top: 24px;">
    <h3 style="color: #2c3e50; font-size: 1.1em; margin-bottom: 12px;">Sources</h3>
    <ul style="padding-left: 20px;">
      <li style="margin-bottom: 8px;">
        <strong>[Source Title]</strong> - [Brief description]
        <a href="[URL]" target="_blank" style="color: #007bff; margin-left: 8px;">🔗</a>
      </li>
    </ul>
  </div>
</div>"""


class ConversationAnalyzer:
    """Handles conversation history analysis with improved context building."""

    @staticmethod
    def extract_latest_user_message(conversation_history: List[Dict[str, str]]) -> str:
        """Extract the most recent user message."""
        for msg in reversed(conversation_history):
            if msg["role"] == "user":
                return msg["content"]
        return "No recent query found"

    @staticmethod
    def build_conversation_context(
            conversation_history: List[Dict[str, str]],
            max_turns: int = 3,
            max_chars_per_turn: int = 1500,  # Increased for richer context
            format_type: str = "xml"  # Changed to xml default for better LLM parsing
    ) -> str:
        """
        Build conversation context with improved structure and length.

        Args:
            conversation_history: List of conversation turns
            max_turns: Maximum number of recent turns to include
            max_chars_per_turn: Maximum characters per turn (0 for no limit)
            format_type: "structured", "xml", or "minimal"
        """
        if not conversation_history or len(conversation_history) <= 1:
            return ""

        # Get recent turns (pairs of user-assistant exchanges)
        recent_turns = conversation_history[-(max_turns * 2):]

        if format_type == "xml":
            return ConversationAnalyzer._build_xml_context(recent_turns, max_chars_per_turn)
        elif format_type == "structured":
            return ConversationAnalyzer._build_structured_context(recent_turns, max_chars_per_turn)
        else:  # minimal
            return ConversationAnalyzer._build_minimal_context(recent_turns, max_chars_per_turn)

    @staticmethod
    def _build_xml_context(turns: List[Dict[str, str]], max_chars: int) -> str:
        """Build XML-structured context - best for LLM parsing."""
        context_parts = ["\n<conversation_context>"]

        current_turn = []
        for msg in turns:
            if msg["role"] == "user":
                if current_turn:  # Complete previous turn
                    context_parts.append("</turn>")
                context_parts.append("<turn>")
                content = ConversationAnalyzer._truncate_content(msg["content"], max_chars)
                context_parts.append(f"<user_message>{html.escape(content)}</user_message>")
                current_turn = ["user"]
            elif msg["role"] == "assistant" and current_turn:
                content = ConversationAnalyzer._truncate_content(msg["content"], max_chars)
                context_parts.append(f"<assistant_response>{html.escape(content)}</assistant_response>")
                current_turn.append("assistant")

        if current_turn:
            context_parts.append("</turn>")

        context_parts.append("</conversation_context>")
        return "\n".join(context_parts)

    @staticmethod
    def _build_structured_context(turns: List[Dict[str, str]], max_chars: int) -> str:
        """Build clearly structured context with turn demarcation."""
        context_parts = ["\n=== RECENT CONVERSATION CONTEXT ==="]

        current_turn = []
        turn_number = 1

        for msg in turns:
            if msg["role"] == "user":
                if current_turn:  # Complete previous turn
                    context_parts.append("--- END TURN ---\n")
                context_parts.append(f"--- TURN {turn_number} ---")
                content = ConversationAnalyzer._truncate_content(msg["content"], max_chars)
                context_parts.append(f"USER: {content}")
                current_turn = ["user"]
            elif msg["role"] == "assistant" and current_turn:
                content = ConversationAnalyzer._truncate_content(msg["content"], max_chars)
                context_parts.append(f"ASSISTANT: {content}")
                current_turn.append("assistant")
                turn_number += 1

        if current_turn:
            context_parts.append("--- END TURN ---")

        context_parts.append("=== END CONVERSATION CONTEXT ===")
        return "\n".join(context_parts)

    @staticmethod
    def _build_minimal_context(turns: List[Dict[str, str]], max_chars: int) -> str:
        """Build minimal context - backward compatible."""
        context_parts = ["\nRECENT CONVERSATION CONTEXT:"]

        for i, turn in enumerate(turns, 1):
            role = "User" if turn['role'] == 'user' else "Assistant"
            content = ConversationAnalyzer._truncate_content(turn["content"], max_chars)
            context_parts.append(f"{i}. {role}: {content}")

        return "\n".join(context_parts)

    @staticmethod
    def _truncate_content(content: str, max_chars: int) -> str:
        """Intelligently truncate content."""
        if max_chars <= 0 or len(content) <= max_chars:
            return content

        # Try to truncate at sentence boundary
        truncated = content[:max_chars]
        last_sentence = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )

        if last_sentence > max_chars * 0.7:  # If we can keep 70% and end at sentence
            return truncated[:last_sentence + 1]
        else:
            return truncated + "..."

    @staticmethod
    def build_conversation_summary(
            conversation_history: List[Dict[str, str]],
            max_summary_length: int = 500
    ) -> str:
        """
        Build a condensed summary of the conversation for very long histories.
        Useful when you need to preserve context but reduce token usage.
        """
        if not conversation_history or len(conversation_history) <= 2:
            return ""

        # Extract key topics and user intents
        user_queries = [msg["content"] for msg in conversation_history if msg["role"] == "user"]

        if not user_queries:
            return ""

        summary_parts = ["\nCONVERSATION SUMMARY:"]

        # Summarize main topics
        if len(user_queries) == 1:
            query = ConversationAnalyzer._truncate_content(user_queries[0], max_summary_length)
            summary_parts.append(f"User is asking about: {query}")
        else:
            summary_parts.append("User has asked about:")
            for i, query in enumerate(user_queries[-3:], 1):  # Last 3 queries
                truncated = ConversationAnalyzer._truncate_content(query, max_summary_length // 3)
                summary_parts.append(f"{i}. {truncated}")

        return "\n".join(summary_parts)


class ContextBuilder:
    """Handles building context from various data sources."""

    @staticmethod
    def build_sources_summary(turn_sources: List[Dict[str, Any]]) -> str:
        """Build sources summary with complete content."""
        if not turn_sources:
            return ""
        summary_parts = [f"\nSOURCES GATHERED ({len(turn_sources)} total):"]
        for idx, src in enumerate(turn_sources, 1):
            title = html.escape(src.get('title', 'Untitled'))
            url = html.escape(src.get('url', 'No URL'))
            snippet = html.escape(str(src.get('snippet', 'No content')))
            summary_parts.extend([
                f"\nSOURCE {idx}:",
                f"Title: {title}",
                f"URL: {url}",
                f"Content: {snippet}",
                "=" * 50
            ])
        return "\n".join(summary_parts)

    @staticmethod
    def build_execution_summary(executed_steps: List[Dict[str, Any]]) -> str:
        """Build summary of executed steps."""
        if not executed_steps:
            return "No steps executed this turn."
        summary_parts = ["EXECUTED STEPS:"]
        # MODIFIED: Iterate over list of dictionaries instead of unpacking tuples
        for i, step in enumerate(executed_steps, 1):
            desc = step.get("description", "No description")
            result = step.get("result", "No result")
            summary_parts.append(f"{i}. {html.escape(desc[:100])}")
            summary_parts.append(f"   Result: {html.escape(str(result)[:300])}...")
        return "\n".join(summary_parts)


def create_unified_planner_decider_prompt(
        conversation_history: List[Dict[str, str]],
        executed_steps_this_turn: List[Dict[str, Any]],
        current_remaining_plan: Optional[List[PlanStep]],
        available_tools_info: str,
        turn_sources: List[Dict[str, Any]],
        turn_charts: List[Dict[str, Any]],
        current_iteration_count: int,
        max_iterations: int
) -> List[Dict[str, str]]:
    """Creates a unified prompt for planning and response generation with rich HTML support and improved decision logic."""
    analyzer = ConversationAnalyzer()
    context_builder = ContextBuilder()
    prompt_builder = PromptBuilder()

    latest_query = analyzer.extract_latest_user_message(conversation_history)

    # Use comprehensive context building with XML format for better LLM parsing
    conversation_context = analyzer.build_conversation_context(
        conversation_history,
        max_turns=3,
        max_chars_per_turn=1500,  # Rich context from v1
        format_type="xml"  # Better structure for LLM parsing
    )

    sources_summary = context_builder.build_sources_summary(turn_sources)
    execution_summary = context_builder.build_execution_summary(executed_steps_this_turn)

    remaining_plan = ""
    if current_remaining_plan:
        remaining_plan = "\nREMAINING PLAN:\n" + "\n".join(
            [f"- {step.step_type}: {step.description[:150]}..." for step in current_remaining_plan]
        )

    charts_summary = ""
    if turn_charts:
        charts_summary = f"\nCHARTS GENERATED: {len(turn_charts)} charts are available."

    system_content = f"""You are a powerful AI assistant that creates rich, comprehensive responses. Your job is to analyze user queries and decide to either plan tool use or respond directly.

**PRIMARY GOAL:** Fulfill the user's request accurately and efficiently with detailed, well-structured responses.

**CONTEXT**
- CURRENT QUERY: "{html.escape(latest_query)}"
{conversation_context}
- TOOLS:
{available_tools_info}
- CURRENT STATE:
{execution_summary}
{remaining_plan}
{sources_summary}
{charts_summary}
- ITERATION: {current_iteration_count}/{max_iterations}

**DECISION-MAKING RULES (IN ORDER OF PRIORITY):**
1.  **MANDATORY ITERATION LIMIT:** If `current_iteration_count >= {max_iterations}`, you MUST choose `RESPOND_DIRECTLY` regardless of any other factors. This is non-negotiable - provide the best comprehensive response possible with available information.
2.  **DATA & VISUALIZATION FIRST:** If the query involves plotting, charting, visualization, or analyzing specific data (e.g., "show sales," "plot this data," "make a bar chart") AND you haven't reached the iteration limit, YOU MUST CHOOSE `PLAN_NEXT_STEPS` and use available chart/visualization tools from the discovered tools list.
3.  **COMPLETE INFORMATION:** If you have already executed tools and have sufficient information (including text and charts) to fully answer the user's query with a comprehensive response, choose `RESPOND_DIRECTLY`.
4.  **GATHER MORE INFO:** If you lack the information to provide a complete, rich answer AND haven't reached the iteration limit, choose `PLAN_NEXT_STEPS` to use tools like `search_web` or other relevant tools.

**ADVANCED MULTI-QUERY SEARCH STRATEGY:**
For web search and news search queries, implement comprehensive multi-perspective coverage:

1. **ORIGINAL QUERY EXECUTION**: Always execute the user's original query exactly as provided first
2. **INTELLIGENT QUERY EXPANSION**: Generate 2-4 additional strategic search queries using:
   - **Semantic Diversification**: Synonyms, alternative terminology, domain-specific language
   - **Perspective Multiplexing**: Different stakeholder viewpoints (industry, academic, regulatory, consumer)
   - **Temporal Dimension**: Recent developments, trends, future projections
   - **Geographic Context**: Regional variations and global perspectives
   - **Technical Depth Variation**: Both overview and technical deep-dive queries

3. **STRATEGIC QUERY FORMULATION**:
   - **Specificity Gradient**: Mix broad conceptual with highly specific technical queries
   - **Controversy Detection**: Capture different sides of debated topics
   - **Trend Amplification**: Focus on latest developments and emerging patterns
   - **Expert Source Targeting**: Surface academic, industry, and expert perspectives
   - **Use Case Exploration**: Practical applications and real-world implementations

**MULTI-QUERY EXAMPLE:**
Original: "impact of AI on healthcare"
Expanded: "artificial intelligence medical diagnosis accuracy 2024", "AI healthcare implementation challenges hospitals", "machine learning patient outcomes clinical trials", "healthcare AI regulation FDA approval"

**CRITICAL TOOL USAGE RULES:**
-   **ADHERE TO SCHEMA**: You MUST strictly adhere to the `inputSchema` for each tool. The `arguments` object in your `tool_call_details` MUST contain all `required` fields and the values must match the specified `type`.
-   For general data analysis and visualization requests (e.g., "show sales data with a bar chart"), use available chart/visualization tools from the discovered tools list. The main argument for visualization tools should be the EXACT, UNCHANGED TEXT from the user's query.
-   When planning search queries, create multiple strategic variations for comprehensive coverage.
-   When planning, create a list of steps. You can use multiple tools in a plan.
-   For web information gathering: use `search_web`
-   For news and current events: use `search_news`
-   For data analysis: use available data analysis tools

**HTML RESPONSE REQUIREMENTS** (for RESPOND_DIRECTLY):
- Use the complete HTML template structure provided
- Include ALL relevant information from sources and analysis
- Create comprehensive, detailed content that utilizes every piece of available information
- Utilize the Key Insights section effectively with actionable findings
- Include proper source citations with links
- Make the response visually appealing, well-organized, and information-rich

**OUTPUT SCHEMA (Strictly follow this JSON format):**
```json
{{
  "action_type": "PLAN_NEXT_STEPS" or "RESPOND_DIRECTLY",
  "plan": [
    {{
      "step_type": "TOOL_CALL" or "REASONING_STEP",
      "description": "Natural language description of why this step is needed.",
      "tool_call_details": {{
        "tool_name": "Use actual tool names from the discovered tools list",
        "arguments": {{ "data": [{{ "category": "A", "value": 20 }}], "instructions": "Create a bar chart of the data." }}
      }}
    }}
  ] or null,
  "overall_plan_reasoning": "Brief overall reasoning for the plan." or null,
  "response_summary_html": "The final, comprehensive HTML response for the user using the full template." or null,
  "decision_reasoning": "Brief reasoning for choosing the action_type. If iteration limit reached, explicitly state this as the reason."
}}

**HTML RESPONSE TEMPLATE (for RESPOND_DIRECTLY):**
{prompt_builder.html_template}

**VALIDATION REQUIREMENTS:**
- action_type: Must be exactly "PLAN_NEXT_STEPS" or "RESPOND_DIRECTLY"
- If PLAN_NEXT_STEPS: plan must be non-empty array, response_summary_html must be null
- If RESPOND_DIRECTLY: plan must be null, response_summary_html must be comprehensive HTML
- For TOOL_CALL steps: tool_call_details must contain valid tool_name and arguments
- For REASONING_STEP steps: tool_call_details must be null
- decision_reasoning is always required and must explain the decision clearly
"""

    user_prompt = f"""Based on the current query, context, and your rules, generate the correct JSON output.
Query: "{html.escape(latest_query)}"

**CRITICAL ITERATION CHECK:**
Current iteration: {current_iteration_count}
Maximum iterations: {max_iterations}
Status: {"MUST RESPOND DIRECTLY - ITERATION LIMIT REACHED" if current_iteration_count >= max_iterations else "Can plan more steps"}

Remember: 
- If iteration limit is reached, you MUST choose "RESPOND_DIRECTLY" and provide comprehensive HTML response with all available information
- If this query is about data or charts AND iteration limit not reached, you must plan to use appropriate tools
- For search queries, use the multi-query expansion strategy for comprehensive coverage
- Always validate your JSON output matches the exact schema
"""
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt}
    ]


def create_search_expansion_prompt(original_query: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
    """Creates advanced search query expansion prompts with strategic variations."""

    system_content = f"""You are a search query expansion expert. Create 3-4 strategic search query variations for comprehensive coverage.

ORIGINAL QUERY: "{html.escape(original_query)}"

**ADVANCED EXPANSION STRATEGIES:**
1. **SEMANTIC DIVERSIFICATION**: Synonyms, alternative terminology, domain-specific language
2. **PERSPECTIVE MULTIPLEXING**: Different stakeholder viewpoints (industry, academic, regulatory, consumer)
3. **TEMPORAL DIMENSION**: Recent developments, trends, future projections
4. **GEOGRAPHIC CONTEXT**: Regional variations and global perspectives
5. **TECHNICAL DEPTH VARIATION**: Both overview and detailed technical queries

**STRATEGIC FORMULATION PRINCIPLES:**
- **Specificity Gradient**: Mix broad conceptual with highly specific technical queries
- **Controversy Detection**: Include queries that capture different sides of debated topics
- **Trend Amplification**: Add queries focused on latest developments and emerging patterns
- **Expert Source Targeting**: Frame queries to surface academic, industry, and expert perspectives
- **Use Case Exploration**: Include practical application and real-world implementation queries

OUTPUT FORMAT:
Return 3-4 search queries as a JSON list:
["query1", "query2", "query3", "query4"]

EXAMPLES:
Original: "AI impact healthcare"
Expanded: [
  "artificial intelligence medical diagnosis accuracy 2024", 
  "AI healthcare implementation challenges hospitals", 
  "machine learning patient outcomes clinical trials", 
  "healthcare AI regulation FDA approval"
]

Original: "renewable energy trends"
Expanded: [
  "renewable energy market growth 2024",
  "solar wind power adoption barriers",
  "clean energy investment opportunities",
  "renewable energy policy government incentives"
]"""

    user_prompt = f"Create comprehensive expanded search queries for: '{html.escape(original_query)}'"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt}
    ]


def create_reasoning_prompt(step_description: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
    """Creates a focused reasoning prompt with advanced multi-query search capabilities."""
    user_query = context.get("input", "")
    conversation_history = context.get("conversation_history", [])
    past_results = context.get("past_steps", [])
    sources = context.get("turn_sources", [])
    charts = context.get("turn_charts", [])

    context_parts = []
    if user_query:
        context_parts.append(f"ORIGINAL QUERY: {html.escape(user_query)}")

    if conversation_history:
        # Use improved conversation context building
        analyzer = ConversationAnalyzer()
        improved_context = analyzer.build_conversation_context(
            conversation_history,
            max_turns=2,  # Fewer turns for reasoning context
            max_chars_per_turn=800,  # Moderate length for reasoning
            format_type="xml"  # XML format for better LLM parsing
        )
        if improved_context:
            context_parts.append(improved_context)

    if past_results:
        context_parts.append("\nPREVIOUS RESULTS:")
        # MODIFIED: Iterate over list of dictionaries instead of unpacking tuples
        for i, step in enumerate(past_results[-3:], 1):
            desc = step.get("description", "No description")
            result = step.get("result", "No result")
            context_parts.append(f"{i}. {html.escape(desc)}")
            result_preview = html.escape(str(result)[:600]) if len(str(result)) > 600 else html.escape(str(result))
            context_parts.append(f"   Result: {result_preview}")

    if sources:
        context_parts.append(f"\nAVAILABLE SOURCES ({len(sources)} total):")
        for i, src in enumerate(sources, 1):
            title = html.escape(src.get('title', 'Untitled'))
            snippet = html.escape(str(src.get('snippet', '')))
            url = html.escape(src.get('url', ''))
            context_parts.append(f"\nSOURCE {i}: {title}")
            if url:
                context_parts.append(f"URL: {url}")
            # Show more content from sources
            if len(snippet) > 800:
                snippet = snippet[:800] + "..."
            context_parts.append(f"CONTENT: {snippet}")

    if charts:
        context_parts.append(f"\nCHARTS: {len(charts)} generated")

    context_str = "\n".join(context_parts) if context_parts else "No additional context available."

    system_content = f"""You are performing this reasoning task: "{html.escape(step_description)}"

CAPABILITIES:
- Analyze previous results and determine next steps
- Synthesize information from multiple sources
- Evaluate queries for clarity and context
- Generate strategic search query variations using advanced multi-query expansion
- Resolve references using conversation history
- Extract insights from complete source content

**ADVANCED MULTI-QUERY SEARCH STRATEGY:**
When refining search queries, create 2-4 strategic variations using:

**A. Semantic Diversification:**
- Use synonyms, alternative terminology, and domain-specific language
- Example: "AI impact on jobs" → "artificial intelligence employment displacement", "machine learning workforce automation"

**B. Perspective Multiplexing:**
- Search from different stakeholder viewpoints (industry, academic, regulatory, consumer)
- Example: "cryptocurrency regulation" → "crypto regulation banks perspective", "SEC cryptocurrency enforcement policy"

**C. Temporal Dimension Expansion:**
- Include recent developments, trends, and future projections
- Example: "renewable energy" → "renewable energy 2024 trends", "clean energy future projections"

**D. Geographic and Cultural Context:**
- Consider regional variations and global perspectives
- Example: "healthcare costs" → "US healthcare costs comparison", "global healthcare spending analysis"

**E. Technical Depth Variation:**
- Include both high-level overview and technical deep-dive queries
- Example: "quantum computing" → "quantum computing explained simply", "quantum algorithm implementation challenges"

**STRATEGIC QUERY FORMULATION PRINCIPLES:**
- **Specificity Gradient**: Mix broad conceptual queries with highly specific technical queries
- **Controversy Detection**: Include queries that capture different sides of debated topics
- **Trend Amplification**: Add queries focused on latest developments and emerging patterns
- **Expert Source Targeting**: Frame queries to surface academic, industry, and expert perspectives
- **Use Case Exploration**: Include practical application and real-world implementation queries

CONTEXT:
{context_str}

Provide focused analysis for: "{html.escape(step_description)}"

YOUR REASONING:"""

    return [{"role": "user", "content": system_content}]


# Legacy function for backward compatibility
def get_subtle_html_response_template() -> str:
    """Returns the HTML response template."""
    return PromptBuilder()._get_html_response_template()


# Additional utility functions for enhanced context management

def create_adaptive_context_prompt(
        conversation_history: List[Dict[str, str]],
        token_budget: int = 4000,
        priority_recent_turns: int = 2
) -> str:
    """
    Create adaptive context that adjusts based on available token budget.

    Args:
        conversation_history: Full conversation history
        token_budget: Approximate token budget for context (rough estimate: 1 token ~ 4 chars)
        priority_recent_turns: Number of recent turns to always include at full length
    """
    if not conversation_history:
        return ""

    analyzer = ConversationAnalyzer()
    char_budget = token_budget * 4  # Rough conversion

    # Always include recent priority turns at full length
    priority_chars = priority_recent_turns * 1500 * 2  # User + Assistant

    if len(conversation_history) <= priority_recent_turns * 2:
        # Short conversation, use structured format
        return analyzer.build_conversation_context(
            conversation_history,
            max_turns=priority_recent_turns,
            max_chars_per_turn=1500,
            format_type="structured"
        )

    remaining_budget = char_budget - priority_chars

    if remaining_budget > 0:
        # Include older turns with summary
        recent_context = analyzer.build_conversation_context(
            conversation_history[-(priority_recent_turns * 2):],
            max_turns=priority_recent_turns,
            max_chars_per_turn=1500,
            format_type="structured"
        )

        older_summary = analyzer.build_conversation_summary(
            conversation_history[:-(priority_recent_turns * 2)],
            max_summary_length=min(remaining_budget, 500)
        )

        return older_summary + "\n" + recent_context
    else:
        # Budget constrained, use minimal format
        return analyzer.build_conversation_context(
            conversation_history,
            max_turns=priority_recent_turns,
            max_chars_per_turn=min(800, char_budget // (priority_recent_turns * 2)),
            format_type="minimal"
        )

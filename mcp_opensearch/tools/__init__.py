#!/usr/bin/env python3
"""
MCPTools - OpenSearch tools for MCP Server
Provides 4 most sophisticated OpenSearch query capabilities
Designed for agentic_assistant plan-and-execute agent
"""
import logging
from typing import Dict, List, Any, Optional

from .http_client import OpenSearchHTTPClient
from .formatters import ResultFormatter
from .registry import ToolRegistry
from .handlers import SearchHandlers, FilterHandlers, AggregationHandlers, RetrievalHandlers

logger = logging.getLogger(__name__)


class MCPTools:
    """
    OpenSearch tools system for MCP server.
    Provides 4 most sophisticated tools for events index:
    1. search_events_hybrid - Advanced hybrid search
    2. search_and_filter_events - Multi-filter search with sorting
    3. get_event_attendance_stats - Comprehensive statistics
    4. list_all_events - Paginated event listing
    """

    def __init__(self, opensearch_url: str = "http://localhost:9200"):
        """
        Initialize MCP Tools.

        Args:
            opensearch_url: Base URL for OpenSearch server
        """
        self.opensearch_url = opensearch_url.rstrip("/")
        self.index_name = "events"

        # Initialize components
        self.http_client = OpenSearchHTTPClient(self.opensearch_url, self.index_name)
        self.formatter = ResultFormatter()
        self.registry = ToolRegistry()

        # Initialize handlers
        self.search_handlers = SearchHandlers(self.http_client, self.formatter)
        self.filter_handlers = FilterHandlers(self.http_client, self.formatter)
        self.aggregation_handlers = AggregationHandlers(self.http_client, self.formatter)
        self.retrieval_handlers = RetrievalHandlers(self.http_client)

        # Build tools registry
        self.tools_registry = {}
        self._register_events_tools()

        logger.info(f"MCPTools initialized with {len(self.tools_registry)} tools")
        logger.info(f"OpenSearch URL: {self.opensearch_url}")
        logger.info(f"Target Index: {self.index_name}")

    def _register_events_tools(self):
        """Register the 4 most sophisticated tools."""

        # Register the one search tool
        search_tools = self.registry.get_search_tools()
        self.tools_registry["search_events_hybrid"] = {
            "definition": search_tools["search_events_hybrid"],
            "handler": self.search_handlers.handle_hybrid_search
        }

        # Register the one filter tool
        filter_tools = self.registry.get_filter_tools()
        self.tools_registry["search_and_filter_events"] = {
            "definition": filter_tools["search_and_filter_events"],
            "handler": self.filter_handlers.handle_search_and_filter
        }

        # Register the one aggregation tool
        aggregation_tools = self.registry.get_aggregation_tools()
        self.tools_registry["get_event_attendance_stats"] = {
            "definition": aggregation_tools["get_event_attendance_stats"],
            "handler": self.aggregation_handlers.handle_attendance_stats
        }

        # Register the one retrieval tool
        retrieval_tools = self.registry.get_retrieval_tools()
        self.tools_registry["list_all_events"] = {
            "definition": retrieval_tools["list_all_events"],
            "handler": self.retrieval_handlers.handle_list_events
        }

        logger.info(f"Registered {len(self.tools_registry)} sophisticated event tools")

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get list of all tool definitions for tools/list response."""
        return [tool_info["definition"] for tool_info in self.tools_registry.values()]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a tool with given arguments. Returns content in MCP format."""
        if tool_name not in self.tools_registry:
            raise ValueError(f"Tool '{tool_name}' not found")

        tool_info = self.tools_registry[tool_name]
        handler = tool_info["handler"]

        try:
            logger.info(f"Executing tool '{tool_name}' with arguments: {arguments}")
            result = await handler(arguments)

            # Ensure result is in proper MCP content format
            if isinstance(result, str):
                return [{"type": "text", "text": result}]
            elif isinstance(result, list):
                return result
            else:
                return [{"type": "text", "text": str(result)}]

        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            raise

    # Dynamic tool registration methods (for compatibility)
    def register_tool(self, name: str, definition: Dict[str, Any], handler):
        """Register a new tool dynamically."""
        self.tools_registry[name] = {
            "definition": definition,
            "handler": handler
        }
        logger.info(f"Registered new tool: {name}")

    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self.tools_registry:
            del self.tools_registry[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        return False

    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific tool."""
        return self.tools_registry.get(name)

    def list_tool_names(self) -> List[str]:
        """Get list of all registered tool names."""
        return list(self.tools_registry.keys())


# Export main class
__all__ = ["MCPTools"]

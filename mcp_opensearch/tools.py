#!/usr/bin/env python3
"""
MCPTools - OpenSearch tools for MCP Server
Provides granular OpenSearch query capabilities for events index
Designed for agentic_assistant plan-and-execute agent
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import aiohttp

logger = logging.getLogger(__name__)


class MCPTools:
    """
    OpenSearch tools system for MCP server.
    Provides granular atomic capabilities for events index to support
    agentic assistants with plan-and-execute workflows.
    """

    def __init__(self, opensearch_url: str = "http://localhost:9200"):
        self.opensearch_url = opensearch_url.rstrip("/")
        self.index_name = "events"
        self.tools_registry = {}
        self._register_events_tools()
        logger.info(f"MCPTools initialized with {len(self.tools_registry)} tools")
        logger.info(f"OpenSearch URL: {self.opensearch_url}")
        logger.info(f"Target Index: {self.index_name}")

    def _register_events_tools(self):
        """Register all events-related tools with granular capabilities."""

        # ============================================================
        # SEARCH TOOLS - Different search strategies
        # ============================================================

        # Tool 1: Basic fuzzy search across all searchable fields
        self.tools_registry["search_events"] = {
            "definition": {
                "name": "search_events",
                "description": "Search events using fuzzy matching across title, theme, highlight, summary, and objective fields. Handles spelling mistakes automatically.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text (spelling mistakes are tolerated)"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 100)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            "handler": self._handle_search_events
        }

        # Tool 2: Search specifically in event titles
        self.tools_registry["search_events_by_title"] = {
            "definition": {
                "name": "search_events_by_title",
                "description": "Search events specifically in the event_title field with fuzzy matching",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for event titles"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 100)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            "handler": self._handle_search_by_title
        }

        # Tool 3: Search by theme
        self.tools_registry["search_events_by_theme"] = {
            "definition": {
                "name": "search_events_by_theme",
                "description": "Search events by theme/topic with fuzzy matching",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "theme": {
                            "type": "string",
                            "description": "Theme or topic to search for"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 100)",
                            "default": 10
                        }
                    },
                    "required": ["theme"]
                }
            },
            "handler": self._handle_search_by_theme
        }

        # Tool 4: Hybrid search (best for fuzzy matching)
        self.tools_registry["search_events_hybrid"] = {
            "definition": {
                "name": "search_events_hybrid",
                "description": "Advanced hybrid search combining standard and ngram analyzers for best fuzzy matching results",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 100)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            "handler": self._handle_hybrid_search
        }

        # Tool 5: Autocomplete search
        self.tools_registry["search_events_autocomplete"] = {
            "definition": {
                "name": "search_events_autocomplete",
                "description": "Autocomplete/prefix search for event titles and themes (search-as-you-type)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prefix": {
                            "type": "string",
                            "description": "Prefix text to autocomplete (minimum 2 characters)"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 50)",
                            "default": 10
                        }
                    },
                    "required": ["prefix"]
                }
            },
            "handler": self._handle_autocomplete_search
        }

        # ============================================================
        # FILTER TOOLS - Filtering by specific fields
        # ============================================================

        # Tool 6: Filter by country
        self.tools_registry["filter_events_by_country"] = {
            "definition": {
                "name": "filter_events_by_country",
                "description": "Filter events by country (Denmark or Dominica). Can optionally include search query.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "country": {
                            "type": "string",
                            "description": "Country name (e.g., 'Denmark' or 'Dominica')",
                            "enum": ["Denmark", "Dominica"]
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional search query to combine with country filter"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 100)",
                            "default": 10
                        }
                    },
                    "required": ["country"]
                }
            },
            "handler": self._handle_filter_by_country
        }

        # Tool 7: Filter by specific year
        self.tools_registry["filter_events_by_year"] = {
            "definition": {
                "name": "filter_events_by_year",
                "description": "Filter events by a specific year. Can optionally include search query.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "year": {
                            "type": "integer",
                            "description": "Year to filter (e.g., 2021, 2022, 2023)"
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional search query to combine with year filter"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 100)",
                            "default": 10
                        }
                    },
                    "required": ["year"]
                }
            },
            "handler": self._handle_filter_by_year
        }

        # Tool 8: Filter by year range
        self.tools_registry["filter_events_by_year_range"] = {
            "definition": {
                "name": "filter_events_by_year_range",
                "description": "Filter events by year range (from year to year). Can optionally include search query.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "start_year": {
                            "type": "integer",
                            "description": "Start year (inclusive)"
                        },
                        "end_year": {
                            "type": "integer",
                            "description": "End year (inclusive)"
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional search query to combine with year range filter"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 100)",
                            "default": 10
                        }
                    },
                    "required": ["start_year", "end_year"]
                }
            },
            "handler": self._handle_filter_by_year_range
        }

        # Tool 9: Filter by attendance (event_count)
        self.tools_registry["filter_events_by_attendance"] = {
            "definition": {
                "name": "filter_events_by_attendance",
                "description": "Filter events by attendance/participation count range",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "min_attendance": {
                            "type": "integer",
                            "description": "Minimum attendance count (optional)"
                        },
                        "max_attendance": {
                            "type": "integer",
                            "description": "Maximum attendance count (optional)"
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional search query to combine with attendance filter"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 100)",
                            "default": 10
                        }
                    }
                }
            },
            "handler": self._handle_filter_by_attendance
        }

        # Tool 10: Combined search with multiple filters
        self.tools_registry["search_and_filter_events"] = {
            "definition": {
                "name": "search_and_filter_events",
                "description": "Search events with multiple filters combined (country, year range, attendance). Best for complex queries.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text (optional)"
                        },
                        "country": {
                            "type": "string",
                            "description": "Country filter (optional)",
                            "enum": ["Denmark", "Dominica"]
                        },
                        "start_year": {
                            "type": "integer",
                            "description": "Start year for range filter (optional)"
                        },
                        "end_year": {
                            "type": "integer",
                            "description": "End year for range filter (optional)"
                        },
                        "min_attendance": {
                            "type": "integer",
                            "description": "Minimum attendance (optional)"
                        },
                        "max_attendance": {
                            "type": "integer",
                            "description": "Maximum attendance (optional)"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10, max: 100)",
                            "default": 10
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Sort field (year, event_count, or relevance)",
                            "enum": ["year", "event_count", "relevance"],
                            "default": "relevance"
                        },
                        "sort_order": {
                            "type": "string",
                            "description": "Sort order (asc or desc)",
                            "enum": ["asc", "desc"],
                            "default": "desc"
                        }
                    }
                }
            },
            "handler": self._handle_search_and_filter
        }

        # ============================================================
        # AGGREGATION/ANALYTICS TOOLS - Statistical analysis
        # ============================================================

        # Tool 11: Year-wise statistics
        self.tools_registry["get_events_stats_by_year"] = {
            "definition": {
                "name": "get_events_stats_by_year",
                "description": "Get year-wise statistics including event count and average attendance per year",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "country": {
                            "type": "string",
                            "description": "Optional country filter",
                            "enum": ["Denmark", "Dominica"]
                        }
                    }
                }
            },
            "handler": self._handle_stats_by_year
        }

        # Tool 12: Country-wise statistics
        self.tools_registry["get_events_stats_by_country"] = {
            "definition": {
                "name": "get_events_stats_by_country",
                "description": "Get country-wise statistics including event count and average attendance per country",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "year": {
                            "type": "integer",
                            "description": "Optional year filter"
                        }
                    }
                }
            },
            "handler": self._handle_stats_by_country
        }

        # Tool 13: Theme aggregation
        self.tools_registry["get_events_by_theme_aggregation"] = {
            "definition": {
                "name": "get_events_by_theme_aggregation",
                "description": "Get aggregated count of events by theme/topic",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "top_n": {
                            "type": "integer",
                            "description": "Number of top themes to return (default: 10, max: 50)",
                            "default": 10
                        },
                        "year": {
                            "type": "integer",
                            "description": "Optional year filter"
                        },
                        "country": {
                            "type": "string",
                            "description": "Optional country filter",
                            "enum": ["Denmark", "Dominica"]
                        }
                    }
                }
            },
            "handler": self._handle_theme_aggregation
        }

        # Tool 14: Attendance statistics
        self.tools_registry["get_event_attendance_stats"] = {
            "definition": {
                "name": "get_event_attendance_stats",
                "description": "Get statistical analysis of event attendance (min, max, average, sum, count)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "year": {
                            "type": "integer",
                            "description": "Optional year filter"
                        },
                        "country": {
                            "type": "string",
                            "description": "Optional country filter",
                            "enum": ["Denmark", "Dominica"]
                        }
                    }
                }
            },
            "handler": self._handle_attendance_stats
        }

        # ============================================================
        # RETRIEVAL TOOLS - Basic document retrieval
        # ============================================================

        # Tool 15: Get event by ID
        self.tools_registry["get_event_by_id"] = {
            "definition": {
                "name": "get_event_by_id",
                "description": "Retrieve a specific event by its document ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "event_id": {
                            "type": "string",
                            "description": "The document ID of the event to retrieve"
                        }
                    },
                    "required": ["event_id"]
                }
            },
            "handler": self._handle_get_event
        }

        # Tool 16: List all events
        self.tools_registry["list_all_events"] = {
            "definition": {
                "name": "list_all_events",
                "description": "List all events with pagination support",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "size": {
                            "type": "integer",
                            "description": "Number of events to return (default: 10, max: 100)",
                            "default": 10
                        },
                        "from": {
                            "type": "integer",
                            "description": "Offset for pagination (default: 0)",
                            "default": 0
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Sort field (year, event_count)",
                            "enum": ["year", "event_count"],
                            "default": "year"
                        },
                        "sort_order": {
                            "type": "string",
                            "description": "Sort order (asc or desc)",
                            "enum": ["asc", "desc"],
                            "default": "desc"
                        }
                    }
                }
            },
            "handler": self._handle_list_events
        }

        # Tool 17: Count events
        self.tools_registry["count_events"] = {
            "definition": {
                "name": "count_events",
                "description": "Get the total count of events in the index with optional filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "country": {
                            "type": "string",
                            "description": "Optional country filter",
                            "enum": ["Denmark", "Dominica"]
                        },
                        "year": {
                            "type": "integer",
                            "description": "Optional year filter"
                        }
                    }
                }
            },
            "handler": self._handle_count_events
        }

        logger.info(f"Registered {len(self.tools_registry)} granular event tools")

    # ============================================================
    # HELPER METHODS
    # ============================================================

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

    async def _http_request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to OpenSearch."""
        url = f"{self.opensearch_url}/{path}"

        try:
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            raise Exception(f"OpenSearch error ({response.status}): {error_text}")

                elif method == "POST":
                    headers = {"Content-Type": "application/json"}
                    async with session.post(url, json=body, headers=headers) as response:
                        if response.status in [200, 201]:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            raise Exception(f"OpenSearch error ({response.status}): {error_text}")

        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {e}")
            raise Exception(f"Failed to connect to OpenSearch at {self.opensearch_url}: {str(e)}")

    # ============================================================
    # SEARCH TOOL HANDLERS
    # ============================================================

    async def _handle_search_events(self, arguments: Dict[str, Any]) -> str:
        """Basic fuzzy search across all searchable fields."""
        query_text = arguments.get("query", "")
        size = min(arguments.get("size", 10), 100)

        if not query_text:
            return "Error: No query provided"

        search_body = {
            "query": {
                "multi_match": {
                    "query": query_text,
                    "fields": [
                        "event_title^3",
                        "event_theme^2.5",
                        "event_highlight^2",
                        "event_summary^1.5",
                        "event_object^1.2"
                    ],
                    "fuzziness": "AUTO",
                    "operator": "or"
                }
            },
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            return self._format_search_results(result, query_text)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"Error searching events: {str(e)}"

    async def _handle_search_by_title(self, arguments: Dict[str, Any]) -> str:
        """Search specifically in event titles."""
        query_text = arguments.get("query", "")
        size = min(arguments.get("size", 10), 100)

        if not query_text:
            return "Error: No query provided"

        search_body = {
            "query": {
                "match": {
                    "event_title": {
                        "query": query_text,
                        "fuzziness": "AUTO"
                    }
                }
            },
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            return self._format_search_results(result, f"title:'{query_text}'")
        except Exception as e:
            return f"Error searching by title: {str(e)}"

    async def _handle_search_by_theme(self, arguments: Dict[str, Any]) -> str:
        """Search by theme."""
        theme = arguments.get("theme", "")
        size = min(arguments.get("size", 10), 100)

        if not theme:
            return "Error: No theme provided"

        search_body = {
            "query": {
                "match": {
                    "event_theme": {
                        "query": theme,
                        "fuzziness": "AUTO"
                    }
                }
            },
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            return self._format_search_results(result, f"theme:'{theme}'")
        except Exception as e:
            return f"Error searching by theme: {str(e)}"

    async def _handle_hybrid_search(self, arguments: Dict[str, Any]) -> str:
        """Hybrid search combining standard and ngram analyzers."""
        query_text = arguments.get("query", "")
        size = min(arguments.get("size", 10), 100)

        if not query_text:
            return "Error: No query provided"

        search_body = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": ["event_title^3", "event_theme^2.5"],
                                "fuzziness": "AUTO",
                                "boost": 2
                            }
                        },
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": ["event_title.ngram", "event_theme.ngram"],
                                "boost": 1
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            return self._format_search_results(result, f"hybrid:'{query_text}'")
        except Exception as e:
            return f"Error in hybrid search: {str(e)}"

    async def _handle_autocomplete_search(self, arguments: Dict[str, Any]) -> str:
        """Autocomplete/prefix search."""
        prefix = arguments.get("prefix", "")
        size = min(arguments.get("size", 10), 50)

        if len(prefix) < 2:
            return "Error: Prefix must be at least 2 characters"

        search_body = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "match": {
                                "event_title.edge_ngram": {
                                    "query": prefix,
                                    "boost": 2
                                }
                            }
                        },
                        {
                            "match": {
                                "event_theme.ngram": prefix
                            }
                        }
                    ]
                }
            },
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            return self._format_search_results(result, f"autocomplete:'{prefix}'")
        except Exception as e:
            return f"Error in autocomplete search: {str(e)}"

    # ============================================================
    # FILTER TOOL HANDLERS
    # ============================================================

    async def _handle_filter_by_country(self, arguments: Dict[str, Any]) -> str:
        """Filter events by country."""
        country = arguments.get("country", "")
        query_text = arguments.get("query", "")
        size = min(arguments.get("size", 10), 100)

        if not country:
            return "Error: No country provided"

        # Build query
        bool_query = {
            "filter": [
                {"term": {"country": country}}
            ]
        }

        if query_text:
            bool_query["must"] = [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["event_title^3", "event_theme^2.5", "event_summary^1.5"],
                        "fuzziness": "AUTO"
                    }
                }
            ]

        search_body = {
            "query": {"bool": bool_query},
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            filter_desc = f"country={country}" + (f" AND query='{query_text}'" if query_text else "")
            return self._format_search_results(result, filter_desc)
        except Exception as e:
            return f"Error filtering by country: {str(e)}"

    async def _handle_filter_by_year(self, arguments: Dict[str, Any]) -> str:
        """Filter events by specific year."""
        year = arguments.get("year")
        query_text = arguments.get("query", "")
        size = min(arguments.get("size", 10), 100)

        if year is None:
            return "Error: No year provided"

        # Build query
        bool_query = {
            "filter": [
                {"term": {"year": year}}
            ]
        }

        if query_text:
            bool_query["must"] = [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["event_title^3", "event_theme^2.5", "event_summary^1.5"],
                        "fuzziness": "AUTO"
                    }
                }
            ]

        search_body = {
            "query": {"bool": bool_query},
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            filter_desc = f"year={year}" + (f" AND query='{query_text}'" if query_text else "")
            return self._format_search_results(result, filter_desc)
        except Exception as e:
            return f"Error filtering by year: {str(e)}"

    async def _handle_filter_by_year_range(self, arguments: Dict[str, Any]) -> str:
        """Filter events by year range."""
        start_year = arguments.get("start_year")
        end_year = arguments.get("end_year")
        query_text = arguments.get("query", "")
        size = min(arguments.get("size", 10), 100)

        if start_year is None or end_year is None:
            return "Error: Both start_year and end_year are required"

        # Build query
        bool_query = {
            "filter": [
                {
                    "range": {
                        "year": {
                            "gte": start_year,
                            "lte": end_year
                        }
                    }
                }
            ]
        }

        if query_text:
            bool_query["must"] = [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["event_title^3", "event_theme^2.5", "event_summary^1.5"],
                        "fuzziness": "AUTO"
                    }
                }
            ]

        search_body = {
            "query": {"bool": bool_query},
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            filter_desc = f"year_range=[{start_year}-{end_year}]" + (f" AND query='{query_text}'" if query_text else "")
            return self._format_search_results(result, filter_desc)
        except Exception as e:
            return f"Error filtering by year range: {str(e)}"

    async def _handle_filter_by_attendance(self, arguments: Dict[str, Any]) -> str:
        """Filter events by attendance range."""
        min_attendance = arguments.get("min_attendance")
        max_attendance = arguments.get("max_attendance")
        query_text = arguments.get("query", "")
        size = min(arguments.get("size", 10), 100)

        if min_attendance is None and max_attendance is None:
            return "Error: At least one of min_attendance or max_attendance is required"

        # Build range query
        range_query = {}
        if min_attendance is not None:
            range_query["gte"] = min_attendance
        if max_attendance is not None:
            range_query["lte"] = max_attendance

        bool_query = {
            "filter": [
                {"range": {"event_count": range_query}}
            ]
        }

        if query_text:
            bool_query["must"] = [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["event_title^3", "event_theme^2.5", "event_summary^1.5"],
                        "fuzziness": "AUTO"
                    }
                }
            ]

        search_body = {
            "query": {"bool": bool_query},
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            filter_desc = f"attendance=[{min_attendance or 'any'}-{max_attendance or 'any'}]"
            if query_text:
                filter_desc += f" AND query='{query_text}'"
            return self._format_search_results(result, filter_desc)
        except Exception as e:
            return f"Error filtering by attendance: {str(e)}"

    async def _handle_search_and_filter(self, arguments: Dict[str, Any]) -> str:
        """Combined search with multiple filters."""
        query_text = arguments.get("query", "")
        country = arguments.get("country")
        start_year = arguments.get("start_year")
        end_year = arguments.get("end_year")
        min_attendance = arguments.get("min_attendance")
        max_attendance = arguments.get("max_attendance")
        size = min(arguments.get("size", 10), 100)
        sort_by = arguments.get("sort_by", "relevance")
        sort_order = arguments.get("sort_order", "desc")

        # Build complex bool query
        bool_query = {"filter": []}

        # Add search query if provided
        if query_text:
            bool_query["must"] = [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["event_title^3", "event_theme^2.5", "event_summary^1.5"],
                        "fuzziness": "AUTO"
                    }
                }
            ]

        # Add filters
        if country:
            bool_query["filter"].append({"term": {"country": country}})

        if start_year and end_year:
            bool_query["filter"].append({
                "range": {"year": {"gte": start_year, "lte": end_year}}
            })
        elif start_year:
            bool_query["filter"].append({"range": {"year": {"gte": start_year}}})
        elif end_year:
            bool_query["filter"].append({"range": {"year": {"lte": end_year}}})

        if min_attendance or max_attendance:
            range_query = {}
            if min_attendance:
                range_query["gte"] = min_attendance
            if max_attendance:
                range_query["lte"] = max_attendance
            bool_query["filter"].append({"range": {"event_count": range_query}})

        search_body = {
            "query": {"bool": bool_query} if bool_query["filter"] or query_text else {"match_all": {}},
            "size": size
        }

        # Add sorting
        if sort_by != "relevance":
            search_body["sort"] = [{sort_by: {"order": sort_order}}]

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)

            # Build filter description
            filters = []
            if query_text:
                filters.append(f"query='{query_text}'")
            if country:
                filters.append(f"country={country}")
            if start_year or end_year:
                filters.append(f"year=[{start_year or 'any'}-{end_year or 'any'}]")
            if min_attendance or max_attendance:
                filters.append(f"attendance=[{min_attendance or 'any'}-{max_attendance or 'any'}]")

            filter_desc = " AND ".join(filters) if filters else "all events"
            return self._format_search_results(result, filter_desc)
        except Exception as e:
            return f"Error in combined search and filter: {str(e)}"

    # ============================================================
    # AGGREGATION TOOL HANDLERS
    # ============================================================

    async def _handle_stats_by_year(self, arguments: Dict[str, Any]) -> str:
        """Get year-wise statistics."""
        country = arguments.get("country")

        # Build query with optional country filter
        query = {"match_all": {}}
        if country:
            query = {"term": {"country": country}}

        search_body = {
            "size": 0,
            "query": query,
            "aggs": {
                "by_year": {
                    "terms": {
                        "field": "year",
                        "size": 50,
                        "order": {"_key": "asc"}
                    },
                    "aggs": {
                        "avg_attendance": {
                            "avg": {"field": "event_count"}
                        },
                        "total_attendance": {
                            "sum": {"field": "event_count"}
                        },
                        "min_attendance": {
                            "min": {"field": "event_count"}
                        },
                        "max_attendance": {
                            "max": {"field": "event_count"}
                        }
                    }
                }
            }
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            return self._format_year_stats(result, country)
        except Exception as e:
            return f"Error getting year-wise stats: {str(e)}"

    async def _handle_stats_by_country(self, arguments: Dict[str, Any]) -> str:
        """Get country-wise statistics."""
        year = arguments.get("year")

        # Build query with optional year filter
        query = {"match_all": {}}
        if year:
            query = {"term": {"year": year}}

        search_body = {
            "size": 0,
            "query": query,
            "aggs": {
                "by_country": {
                    "terms": {
                        "field": "country",
                        "size": 50
                    },
                    "aggs": {
                        "avg_attendance": {
                            "avg": {"field": "event_count"}
                        },
                        "total_attendance": {
                            "sum": {"field": "event_count"}
                        },
                        "min_attendance": {
                            "min": {"field": "event_count"}
                        },
                        "max_attendance": {
                            "max": {"field": "event_count"}
                        }
                    }
                }
            }
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            return self._format_country_stats(result, year)
        except Exception as e:
            return f"Error getting country-wise stats: {str(e)}"

    async def _handle_theme_aggregation(self, arguments: Dict[str, Any]) -> str:
        """Get theme aggregation."""
        top_n = min(arguments.get("top_n", 10), 50)
        year = arguments.get("year")
        country = arguments.get("country")

        # Build query with optional filters
        bool_query = {"filter": []}
        if year:
            bool_query["filter"].append({"term": {"year": year}})
        if country:
            bool_query["filter"].append({"term": {"country": country}})

        query = {"bool": bool_query} if bool_query["filter"] else {"match_all": {}}

        search_body = {
            "size": 0,
            "query": query,
            "aggs": {
                "by_theme": {
                    "terms": {
                        "field": "event_theme.keyword",
                        "size": top_n
                    }
                }
            }
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            return self._format_theme_aggregation(result, year, country)
        except Exception as e:
            return f"Error getting theme aggregation: {str(e)}"

    async def _handle_attendance_stats(self, arguments: Dict[str, Any]) -> str:
        """Get attendance statistics."""
        year = arguments.get("year")
        country = arguments.get("country")

        # Build query with optional filters
        bool_query = {"filter": []}
        if year:
            bool_query["filter"].append({"term": {"year": year}})
        if country:
            bool_query["filter"].append({"term": {"country": country}})

        query = {"bool": bool_query} if bool_query["filter"] else {"match_all": {}}

        search_body = {
            "size": 0,
            "query": query,
            "aggs": {
                "attendance_stats": {
                    "stats": {"field": "event_count"}
                }
            }
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
            return self._format_attendance_stats(result, year, country)
        except Exception as e:
            return f"Error getting attendance stats: {str(e)}"

    # ============================================================
    # RETRIEVAL TOOL HANDLERS
    # ============================================================

    async def _handle_get_event(self, arguments: Dict[str, Any]) -> str:
        """Get a specific event by ID."""
        event_id = arguments.get("event_id", "")

        if not event_id:
            return "Error: No event_id provided"

        try:
            result = await self._http_request("GET", f"{self.index_name}/_doc/{event_id}")

            if result.get("found"):
                event = {
                    "id": result.get("_id"),
                    "index": result.get("_index"),
                    "data": result.get("_source", {})
                }
                return f"Event found:\n\n{json.dumps(event, indent=2)}"
            else:
                return f"Event with ID '{event_id}' not found"

        except Exception as e:
            logger.error(f"Get event failed: {e}")
            return f"Error retrieving event: {str(e)}"

    async def _handle_list_events(self, arguments: Dict[str, Any]) -> str:
        """List all events with pagination."""
        size = min(arguments.get("size", 10), 100)
        from_offset = arguments.get("from", 0)
        sort_by = arguments.get("sort_by", "year")
        sort_order = arguments.get("sort_order", "desc")

        search_body = {
            "query": {"match_all": {}},
            "size": size,
            "from": from_offset,
            "sort": [{sort_by: {"order": sort_order}}]
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)

            hits = result.get("hits", {}).get("hits", [])
            total_hits = result.get("hits", {}).get("total", {}).get("value", 0)

            if not hits:
                return "No events found in the index"

            # Format results
            events = []
            for hit in hits:
                source = hit.get("_source", {})
                events.append({
                    "id": hit.get("_id"),
                    "year": source.get("year"),
                    "country": source.get("country"),
                    "title": source.get("event_title"),
                    "theme": source.get("event_theme"),
                    "attendance": source.get("event_count")
                })

            response = f"Total events: {total_hits}. Showing {len(hits)} events (offset: {from_offset}, sorted by {sort_by} {sort_order}):\n\n"
            response += json.dumps(events, indent=2)

            return response

        except Exception as e:
            logger.error(f"List events failed: {e}")
            return f"Error listing events: {str(e)}"

    async def _handle_count_events(self, arguments: Dict[str, Any]) -> str:
        """Count total number of events with optional filters."""
        country = arguments.get("country")
        year = arguments.get("year")

        # Build query with optional filters
        bool_query = {"filter": []}
        if country:
            bool_query["filter"].append({"term": {"country": country}})
        if year:
            bool_query["filter"].append({"term": {"year": year}})

        if bool_query["filter"]:
            # Use search with query for filtered count
            search_body = {
                "size": 0,
                "query": {"bool": bool_query}
            }
            try:
                result = await self._http_request("POST", f"{self.index_name}/_search", search_body)
                count = result.get("hits", {}).get("total", {}).get("value", 0)
            except Exception as e:
                return f"Error counting events: {str(e)}"
        else:
            # Use count API for total
            try:
                result = await self._http_request("GET", f"{self.index_name}/_count")
                count = result.get("count", 0)
            except Exception as e:
                logger.error(f"Count events failed: {e}")
                return f"Error counting events: {str(e)}"

        filter_desc = []
        if country:
            filter_desc.append(f"country={country}")
        if year:
            filter_desc.append(f"year={year}")

        filter_str = " AND ".join(filter_desc) if filter_desc else "all"
        return f"Total number of events ({filter_str}): {count}"

    # ============================================================
    # FORMATTING HELPER METHODS
    # ============================================================

    def _format_search_results(self, result: Dict[str, Any], query_desc: str) -> str:
        """Format search results in a consistent way."""
        hits = result.get("hits", {}).get("hits", [])
        total_hits = result.get("hits", {}).get("total", {}).get("value", 0)

        if not hits:
            return f"No events found matching {query_desc}"

        # Format results
        events = []
        for hit in hits:
            source = hit.get("_source", {})
            events.append({
                "id": hit.get("_id"),
                "score": hit.get("_score"),
                "year": source.get("year"),
                "country": source.get("country"),
                "title": source.get("event_title"),
                "theme": source.get("event_theme"),
                "attendance": source.get("event_count"),
                "highlight": source.get("event_highlight", "")[:200] if source.get("event_highlight") else ""
            })

        response = f"Found {total_hits} events matching {query_desc}. Showing top {len(hits)} results:\n\n"
        response += json.dumps(events, indent=2)

        return response

    def _format_year_stats(self, result: Dict[str, Any], country: Optional[str]) -> str:
        """Format year-wise statistics."""
        buckets = result.get("aggregations", {}).get("by_year", {}).get("buckets", [])

        if not buckets:
            return "No year-wise statistics available"

        stats = []
        for bucket in buckets:
            stats.append({
                "year": bucket["key"],
                "event_count": bucket["doc_count"],
                "avg_attendance": round(bucket["avg_attendance"]["value"], 2),
                "total_attendance": int(bucket["total_attendance"]["value"]),
                "min_attendance": int(bucket["min_attendance"]["value"]),
                "max_attendance": int(bucket["max_attendance"]["value"])
            })

        filter_str = f" (country={country})" if country else ""
        response = f"Year-wise statistics{filter_str}:\n\n"
        response += json.dumps(stats, indent=2)

        return response

    def _format_country_stats(self, result: Dict[str, Any], year: Optional[int]) -> str:
        """Format country-wise statistics."""
        buckets = result.get("aggregations", {}).get("by_country", {}).get("buckets", [])

        if not buckets:
            return "No country-wise statistics available"

        stats = []
        for bucket in buckets:
            stats.append({
                "country": bucket["key"],
                "event_count": bucket["doc_count"],
                "avg_attendance": round(bucket["avg_attendance"]["value"], 2),
                "total_attendance": int(bucket["total_attendance"]["value"]),
                "min_attendance": int(bucket["min_attendance"]["value"]),
                "max_attendance": int(bucket["max_attendance"]["value"])
            })

        filter_str = f" (year={year})" if year else ""
        response = f"Country-wise statistics{filter_str}:\n\n"
        response += json.dumps(stats, indent=2)

        return response

    def _format_theme_aggregation(self, result: Dict[str, Any], year: Optional[int], country: Optional[str]) -> str:
        """Format theme aggregation results."""
        buckets = result.get("aggregations", {}).get("by_theme", {}).get("buckets", [])

        if not buckets:
            return "No theme data available"

        themes = []
        for bucket in buckets:
            themes.append({
                "theme": bucket["key"],
                "event_count": bucket["doc_count"]
            })

        filters = []
        if year:
            filters.append(f"year={year}")
        if country:
            filters.append(f"country={country}")
        filter_str = f" ({', '.join(filters)})" if filters else ""

        response = f"Top themes by event count{filter_str}:\n\n"
        response += json.dumps(themes, indent=2)

        return response

    def _format_attendance_stats(self, result: Dict[str, Any], year: Optional[int], country: Optional[str]) -> str:
        """Format attendance statistics."""
        stats_data = result.get("aggregations", {}).get("attendance_stats", {})

        if not stats_data:
            return "No attendance statistics available"

        stats = {
            "count": int(stats_data.get("count", 0)),
            "min": int(stats_data.get("min", 0)),
            "max": int(stats_data.get("max", 0)),
            "avg": round(stats_data.get("avg", 0), 2),
            "sum": int(stats_data.get("sum", 0))
        }

        filters = []
        if year:
            filters.append(f"year={year}")
        if country:
            filters.append(f"country={country}")
        filter_str = f" ({', '.join(filters)})" if filters else ""

        response = f"Attendance statistics{filter_str}:\n\n"
        response += json.dumps(stats, indent=2)

        return response

    # ============================================================
    # DYNAMIC TOOL REGISTRATION
    # ============================================================

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

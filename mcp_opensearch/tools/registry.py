#!/usr/bin/env python3
"""
Tool Registry for MCP OpenSearch Tools
Contains the 4 most sophisticated tool definitions
"""
from typing import Dict, Any


class ToolRegistry:
    """Registry of all OpenSearch tool definitions."""

    @staticmethod
    def get_search_tools() -> Dict[str, Dict[str, Any]]:
        """Get search tool definition - keeping only the most sophisticated one."""
        return {
            "search_events_hybrid": {
                "name": "search_events_hybrid",
                "description": "Advanced hybrid search combining standard and ngram analyzers for best fuzzy matching results. Use this when you need the most robust fuzzy search that can handle misspellings, partial words, and variations better than standard search. Best for dealing with uncertain or incomplete search terms. Returns highest quality fuzzy matches.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text. Can include misspellings, partial words, or variations. Examples: 'clima sumit' (misspelled), 'tech innov' (partial), 'envronment' (misspelled)."
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return. Default: 10, minimum: 1, maximum: 100.",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["query"],
                    "examples": [
                        {"query": "clima sumit", "size": 10},
                        {"query": "tech innov", "size": 15}
                    ]
                }
            }
        }

    @staticmethod
    def get_filter_tools() -> Dict[str, Dict[str, Any]]:
        """Get filter tool definition - keeping only the most sophisticated one."""
        return {
            "search_and_filter_events": {
                "name": "search_and_filter_events",
                "description": "Search events with multiple filters combined (country, year range, attendance) and custom sorting. Best for complex queries requiring multiple criteria. Use this when you need to combine several filters together (e.g., technology events in Denmark from 2020-2023 with 100+ attendees). Returns precisely filtered and sorted results.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text (optional). Searches across all event fields. Examples: 'innovation', 'climate policy'. Leave empty if you only want to filter without search."
                        },
                        "country": {
                            "type": "string",
                            "description": "Country filter (optional). Must be exactly 'Denmark' or 'Dominica'. Omit to include all countries.",
                            "enum": ["Denmark", "Dominica"]
                        },
                        "start_year": {
                            "type": "integer",
                            "description": "Start year for range filter (optional). 4-digit year. Example: 2020. Omit for no start year limit."
                        },
                        "end_year": {
                            "type": "integer",
                            "description": "End year for range filter (optional). 4-digit year. Example: 2023. Omit for no end year limit."
                        },
                        "min_attendance": {
                            "type": "integer",
                            "description": "Minimum attendance (optional). Example: 50 for events with at least 50 attendees. Omit for no minimum."
                        },
                        "max_attendance": {
                            "type": "integer",
                            "description": "Maximum attendance (optional). Example: 1000 for events with up to 1000 attendees. Omit for no maximum."
                        },
                        "size": {
                            "type": "integer",
                            "description": "Number of results to return. Default: 10, minimum: 1, maximum: 100.",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Sort field. 'year' = sort by event year, 'event_count' = sort by attendance, 'relevance' = sort by search relevance (only works with query). Default: 'relevance'.",
                            "enum": ["year", "event_count", "relevance"],
                            "default": "relevance"
                        },
                        "sort_order": {
                            "type": "string",
                            "description": "Sort order. 'asc' = ascending (oldest/smallest first), 'desc' = descending (newest/largest first). Default: 'desc'.",
                            "enum": ["asc", "desc"],
                            "default": "desc"
                        }
                    },
                    "examples": [
                        {"query": "technology", "country": "Denmark", "start_year": 2020, "end_year": 2023, "min_attendance": 100, "size": 25, "sort_by": "year", "sort_order": "desc"},
                        {"country": "Dominica", "min_attendance": 50, "max_attendance": 500, "size": 20, "sort_by": "event_count", "sort_order": "asc"}
                    ]
                }
            }
        }

    @staticmethod
    def get_aggregation_tools() -> Dict[str, Dict[str, Any]]:
        """Get aggregation tool definition - keeping only the most sophisticated one."""
        return {
            "get_event_attendance_stats": {
                "name": "get_event_attendance_stats",
                "description": "Get statistical analysis of event attendance including min, max, average, sum, and count. Use this for attendance analysis, capacity planning, or understanding event size distribution. Returns comprehensive attendance metrics: minimum, maximum, average, total sum, and event count.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "year": {
                            "type": "integer",
                            "description": "Optional year filter. Use a 4-digit year to get attendance stats for a specific year. Omit to get stats across all years."
                        },
                        "country": {
                            "type": "string",
                            "description": "Optional country filter. Use 'Denmark' or 'Dominica' to get attendance stats for a specific country. Omit to get stats across all countries.",
                            "enum": ["Denmark", "Dominica"]
                        }
                    },
                    "examples": [
                        {},
                        {"year": 2023},
                        {"country": "Denmark", "year": 2022}
                    ]
                }
            }
        }

    @staticmethod
    def get_retrieval_tools() -> Dict[str, Dict[str, Any]]:
        """Get retrieval tool definition - keeping only the most sophisticated one."""
        return {
            "list_all_events": {
                "name": "list_all_events",
                "description": "List all events with pagination and sorting support. Use this to browse through all events in the index, get a sample of events, or retrieve events in a specific order. Perfect for data exploration or getting an overview. Returns paginated list of events with basic information (id, year, country, title, theme, attendance).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "size": {
                            "type": "integer",
                            "description": "Number of events to return per page. Default: 10, minimum: 1, maximum: 100. Use smaller values (10-20) for quick browsing, larger values (50-100) for bulk retrieval.",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "from": {
                            "type": "integer",
                            "description": "Offset for pagination (starting position). Default: 0. Use this for pagination - e.g., from=0 for page 1, from=10 for page 2 (with size=10), from=20 for page 3, etc.",
                            "default": 0,
                            "minimum": 0
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Sort field. 'year' = sort by event year, 'event_count' = sort by attendance count. Default: 'year'.",
                            "enum": ["year", "event_count"],
                            "default": "year"
                        },
                        "sort_order": {
                            "type": "string",
                            "description": "Sort order. 'asc' = ascending (oldest/smallest first), 'desc' = descending (newest/largest first). Default: 'desc'.",
                            "enum": ["asc", "desc"],
                            "default": "desc"
                        }
                    },
                    "examples": [
                        {"size": 20, "sort_by": "year", "sort_order": "desc"},
                        {"size": 50, "from": 0, "sort_by": "event_count", "sort_order": "desc"},
                        {"size": 10, "from": 20}
                    ]
                }
            }
        }

#!/usr/bin/env python3
"""
Filter Tool Handler for MCP OpenSearch Tools
Handles combined search and multi-filter operations
"""
import logging
from typing import Dict, Any
from ..http_client import OpenSearchHTTPClient
from ..formatters import ResultFormatter

logger = logging.getLogger(__name__)


class FilterHandlers:
    """Handler for combined search and filter tool."""

    def __init__(self, http_client: OpenSearchHTTPClient, formatter: ResultFormatter):
        """
        Initialize filter handler.

        Args:
            http_client: HTTP client for OpenSearch requests
            formatter: Result formatter instance
        """
        self.http_client = http_client
        self.formatter = formatter
        self.index_name = http_client.index_name

    async def handle_search_and_filter(self, arguments: Dict[str, Any]) -> str:
        """
        Combined search with multiple filters and custom sorting.

        This is the most sophisticated filter method that supports:
        - Optional text search across all fields
        - Country filtering (Denmark or Dominica)
        - Year range filtering (start_year to end_year)
        - Attendance range filtering (min/max attendance)
        - Custom sorting (by year, attendance, or relevance)
        - Custom sort order (ascending or descending)

        Args:
            arguments: Filter parameters including query, filters, and sorting options

        Returns:
            Formatted search results string
        """
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
            search_body["sort"] = [{
                sort_by: {
                    "order": sort_order,
                    "unmapped_type": "long"  # Handle mixed types gracefully
                }
            }]

        try:
            result = await self.http_client.request("POST", f"{self.index_name}/_search", search_body)

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
            return self.formatter.format_search_results(result, filter_desc)
        except Exception as e:
            return f"Error in combined search and filter: {str(e)}"

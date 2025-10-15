#!/usr/bin/env python3
"""
Aggregation Tool Handler for MCP OpenSearch Tools
Handles attendance statistics and analytics operations
"""
import logging
from typing import Dict, Any
from ..http_client import OpenSearchHTTPClient
from ..formatters import ResultFormatter

logger = logging.getLogger(__name__)


class AggregationHandlers:
    """Handler for attendance statistics aggregation tool."""

    def __init__(self, http_client: OpenSearchHTTPClient, formatter: ResultFormatter):
        """
        Initialize aggregation handler.

        Args:
            http_client: HTTP client for OpenSearch requests
            formatter: Result formatter instance
        """
        self.http_client = http_client
        self.formatter = formatter
        self.index_name = http_client.index_name

    async def handle_attendance_stats(self, arguments: Dict[str, Any]) -> str:
        """
        Get comprehensive attendance statistics.

        This method provides the most complete statistical analysis including:
        - Minimum attendance value
        - Maximum attendance value
        - Average attendance (mean)
        - Total sum of attendance
        - Count of events analyzed
        - Optional filtering by year and/or country

        Args:
            arguments: Parameters including optional year and country filters

        Returns:
            Formatted attendance statistics string
        """
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
            result = await self.http_client.request("POST", f"{self.index_name}/_search", search_body)
            return self.formatter.format_attendance_stats(result, year, country)
        except Exception as e:
            return f"Error getting attendance stats: {str(e)}"

#!/usr/bin/env python3
"""
Search Tool Handler for MCP OpenSearch Tools
Handles advanced hybrid search operations
"""
import logging
from typing import Dict, Any
from ..http_client import OpenSearchHTTPClient
from ..formatters import ResultFormatter

logger = logging.getLogger(__name__)


class SearchHandlers:
    """Handler for hybrid search tool."""

    def __init__(self, http_client: OpenSearchHTTPClient, formatter: ResultFormatter):
        """
        Initialize search handler.

        Args:
            http_client: HTTP client for OpenSearch requests
            formatter: Result formatter instance
        """
        self.http_client = http_client
        self.formatter = formatter
        self.index_name = http_client.index_name

    async def handle_hybrid_search(self, arguments: Dict[str, Any]) -> str:
        """
        Hybrid search combining standard and ngram analyzers.

        This is the most sophisticated search method that combines:
        - Standard fuzzy matching with AUTO fuzziness
        - Ngram-based matching for partial words and misspellings
        - Weighted boosting for optimal relevance ranking

        Args:
            arguments: Search parameters including query and size

        Returns:
            Formatted search results string
        """
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
            result = await self.http_client.request("POST", f"{self.index_name}/_search", search_body)
            return self.formatter.format_search_results(result, f"hybrid:'{query_text}'")
        except Exception as e:
            return f"Error in hybrid search: {str(e)}"

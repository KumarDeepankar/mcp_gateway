#!/usr/bin/env python3
"""
Retrieval Tool Handler for MCP OpenSearch Tools
Handles paginated event listing and browsing operations
"""
import json
import logging
from typing import Dict, Any
from ..http_client import OpenSearchHTTPClient

logger = logging.getLogger(__name__)


class RetrievalHandlers:
    """Handler for event listing and retrieval tool."""

    def __init__(self, http_client: OpenSearchHTTPClient):
        """
        Initialize retrieval handler.

        Args:
            http_client: HTTP client for OpenSearch requests
        """
        self.http_client = http_client
        self.index_name = http_client.index_name

    async def handle_list_events(self, arguments: Dict[str, Any]) -> str:
        """
        List all events with pagination and sorting support.

        This is the most sophisticated retrieval method that provides:
        - Pagination support (size and from parameters)
        - Custom sorting (by year or attendance count)
        - Custom sort order (ascending or descending)
        - Full document retrieval with all event details
        - Total count information

        Perfect for:
        - Browsing through all events
        - Getting a sample of events
        - Retrieving events in specific order
        - Data exploration and overview

        Args:
            arguments: Parameters including size, from, sort_by, and sort_order

        Returns:
            Formatted paginated list of events
        """
        size = min(arguments.get("size", 10), 100)
        from_offset = arguments.get("from", 0)
        sort_by = arguments.get("sort_by", "year")
        sort_order = arguments.get("sort_order", "desc")

        search_body = {
            "query": {"match_all": {}},
            "size": size,
            "from": from_offset,
            "sort": [{
                sort_by: {
                    "order": sort_order,
                    "unmapped_type": "long"  # Handle mixed types gracefully
                }
            }]
        }

        try:
            result = await self.http_client.request("POST", f"{self.index_name}/_search", search_body)

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

#!/usr/bin/env python3
"""
Simple MCP Autocomplete Server using FastMCP 2.0
Provides fuzzy entity matching and autocomplete
"""
import sys
import os
import re
import atexit
from typing import Any
from typing_extensions import TypedDict
import httpx

# # Python 3.11 compatibility patch for anyio type subscripting
# if sys.version_info < (3, 12):
#     import anyio
#
#     # Store the original function
#     _original_create_memory_object_stream = anyio.create_memory_object_stream
#
#
#     # Create a wrapper that allows subscripting but ignores the type parameter
#     class _MemoryObjectStreamWrapper:
#         def __init__(self, func):
#             self._func = func
#
#         def __call__(self, *args, **kwargs):
#             return self._func(*args, **kwargs)
#
#         def __getitem__(self, item):
#             # Return self to allow subscripting but ignore the type parameter
#             return self
#
#
#     # Apply the patch
#     anyio.create_memory_object_stream = _MemoryObjectStreamWrapper(_original_create_memory_object_stream)

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server with proper metadata
# Port configuration for SSE mode
port = int(os.getenv("PORT", "8002"))

mcp = FastMCP(
    name="autocomplete-server",
    instructions="Provides fuzzy autocomplete and entity validation for OpenSearch indices",
    port=port
)

# OpenSearch configuration
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
INDEX_NAME = os.getenv("INDEX_NAME", "events")

# HTTP client for OpenSearch
http_client = httpx.AsyncClient(timeout=30.0)


# Ensure cleanup on exit
def cleanup():
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(http_client.aclose())
        else:
            asyncio.run(http_client.aclose())
    except:
        pass


atexit.register(cleanup)


# Type definitions for structured output
class Suggestion(TypedDict):
    rank: int
    id: str
    title: str
    subtitle: str
    theme: str
    score: float
    highlight: str | None


class AutocompleteResult(TypedDict):
    query: str
    query_type: str
    total_matches: int
    count: int
    suggestions: list[Suggestion]


class EntityData(TypedDict):
    id: str
    title: str
    country: str
    year: str
    theme: str
    attendance: int


class ValidationResult(TypedDict):
    exists: bool
    entity_id: str
    entity: EntityData | None
    message: str | None


def detect_query_type(query: str) -> str:
    """Detect if query is numeric, ID, or text."""
    clean = query.strip()
    if re.match(r'^\d+$', clean):
        return "numeric"
    if len(clean) < 20 and re.search(r'\d', clean):
        return "id"
    return "text"


@mcp.tool()
async def fuzzy_autocomplete(query: str, size: int = 10) -> AutocompleteResult:
    """
    Intelligent fuzzy autocomplete with automatic query type detection.

    Args:
        query: Search query (partial ID, text, or misspelled input)
        size: Number of suggestions (1-50, default: 10)

    Returns:
        Autocomplete suggestions with highlights and scores
    """
    if not query:
        raise ValueError("Query cannot be empty")

    size = min(max(1, size), 50)
    query_type = detect_query_type(query)

    # Build OpenSearch query based on type
    if query_type == "numeric":
        # Numeric query - optimize for year/ID matching
        search_body = {
            "query": {
                "bool": {
                    "should": [
                        {"term": {"year": {"value": int(query), "boost": 10.0}}} if query.isdigit() and len(
                            query) == 4 else {},
                        {"wildcard": {"_id": {"value": f"*{query}*", "boost": 8.0}}},
                        {"match": {"event_title": {"query": query, "fuzziness": "AUTO", "boost": 6.0}}},
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": size,
            "_source": ["event_title", "country", "year", "event_theme", "event_count"],
            "highlight": {"fields": {"event_title": {}, "event_theme": {}}}
        }
        # Remove empty clauses
        search_body["query"]["bool"]["should"] = [s for s in search_body["query"]["bool"]["should"] if s]
    else:
        # Text query - optimize for fuzzy text matching
        search_body = {
            "query": {
                "bool": {
                    "should": [
                        {"match_phrase": {"event_title": {"query": query, "boost": 10.0}}},
                        {"match_phrase_prefix": {"event_title": {"query": query, "boost": 9.0}}},
                        {"match": {"event_title": {"query": query, "fuzziness": "AUTO", "boost": 7.0}}},
                        {"match": {"event_theme": {"query": query, "fuzziness": "AUTO", "boost": 5.0}}},
                    ]
                }
            },
            "size": size,
            "_source": ["event_title", "country", "year", "event_theme", "event_count"],
            "highlight": {"fields": {"event_title": {}, "event_theme": {}}, "pre_tags": ["<mark>"],
                          "post_tags": ["</mark>"]}
        }

    # Execute search
    try:
        response = await http_client.post(
            f"{OPENSEARCH_URL}/{INDEX_NAME}/_search",
            json=search_body
        )
        response.raise_for_status()
        result = response.json()

        # Format suggestions
        suggestions = []
        for rank, hit in enumerate(result["hits"]["hits"], 1):
            source = hit["_source"]
            highlight = hit.get("highlight", {})

            subtitle_parts = []
            if source.get("country"):
                subtitle_parts.append(source["country"])
            if source.get("year"):
                subtitle_parts.append(str(source["year"]))
            if source.get("event_count"):
                subtitle_parts.append(f"{source['event_count']} attendees")

            suggestion = {
                "rank": rank,
                "id": hit["_id"],
                "title": source.get("event_title", ""),
                "subtitle": " · ".join(subtitle_parts),
                "theme": source.get("event_theme", ""),
                "score": round(hit["_score"], 2),
                "highlight": highlight.get("event_title", [None])[0] or highlight.get("event_theme", [None])[0]
            }
            suggestions.append(suggestion)

        return {
            "query": query,
            "query_type": query_type,
            "total_matches": result["hits"]["total"]["value"],
            "count": len(suggestions),
            "suggestions": suggestions
        }

    except httpx.HTTPError as e:
        raise ValueError(f"OpenSearch request failed: {str(e)}")
    except Exception as e:
        raise ValueError(f"Autocomplete failed: {str(e)}")


@mcp.tool()
async def validate_entity(entity_id: str) -> ValidationResult:
    """
    Validate if an entity exists in the system.

    Args:
        entity_id: Entity ID to validate

    Returns:
        Validation result with entity details if found
    """
    if not entity_id:
        raise ValueError("Entity ID is required")

    # Try exact match
    search_body = {
        "query": {
            "bool": {
                "should": [
                    {"term": {"_id": entity_id}},
                    {"match_phrase": {"event_title": entity_id}}
                ]
            }
        },
        "size": 1
    }

    try:
        response = await http_client.post(
            f"{OPENSEARCH_URL}/{INDEX_NAME}/_search",
            json=search_body
        )
        response.raise_for_status()
        result = response.json()

        hits = result["hits"]["hits"]
        if hits:
            source = hits[0]["_source"]
            return ValidationResult(
                exists=True,
                entity_id=entity_id,
                entity=EntityData(
                    id=hits[0]["_id"],
                    title=source.get("event_title", ""),
                    country=source.get("country", ""),
                    year=str(source.get("year", "")),
                    theme=source.get("event_theme", ""),
                    attendance=source.get("event_count", 0)
                ),
                message=None
            )
        else:
            return ValidationResult(
                exists=False,
                entity_id=entity_id,
                entity=None,
                message=f"Entity '{entity_id}' not found"
            )

    except httpx.HTTPError as e:
        raise ValueError(f"OpenSearch request failed: {str(e)}")
    except Exception as e:
        raise ValueError(f"Validation failed: {str(e)}")


if __name__ == "__main__":
    import sys

    # Determine transport mode from command line or environment
    # Default to SSE transport for better compatibility
    # Use stdio only if explicitly requested via command line
    transport = "sse"  # Default to SSE

    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        transport = "stdio"

    # Run FastMCP server with selected transport
    mcp.run(transport=transport)

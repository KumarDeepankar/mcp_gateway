#!/usr/bin/env python3
"""
Autocomplete Tool Handler for MCP OpenSearch Tools
Handles fuzzy autocomplete with entity ID extraction and matching
"""
import logging
import re
from typing import Dict, Any, List, Optional
from ..http_client import OpenSearchHTTPClient

logger = logging.getLogger(__name__)


class AutocompleteHandlers:
    """Handler for fuzzy autocomplete operations."""

    def __init__(self, http_client: OpenSearchHTTPClient):
        """
        Initialize autocomplete handler.

        Args:
            http_client: HTTP client for OpenSearch requests
        """
        self.http_client = http_client
        self.index_name = http_client.index_name

    def _detect_query_type(self, query: str) -> str:
        """
        Detect if query is an ID pattern or descriptive text.

        Args:
            query: User input query

        Returns:
            Query type: "id", "numeric", or "text"
        """
        # Pattern 1: Looks like an ID (contains numbers, hyphens, short)
        if len(query) < 30 and re.search(r'\d', query):
            if re.match(r'^[\d\-]+$', query):
                return "numeric"  # Pure numeric or numeric with hyphens
            return "id"  # Mixed alphanumeric ID

        # Pattern 2: Descriptive text
        return "text"

    def _build_numeric_autocomplete_query(self, query: str, size: int) -> Dict[str, Any]:
        """
        Build optimized query for numeric ID autocomplete (e.g., "1000" -> "SOP-10000").

        Uses multiple strategies:
        1. Exact match on extracted numeric part
        2. Prefix match on numeric part
        3. Wildcard match in full ID
        4. Edge n-gram for partial matching
        """
        # Extract pure numeric part
        numeric_part = re.sub(r'[^\d]', '', query)

        return {
            "query": {
                "bool": {
                    "should": [
                        # Strategy 1: Exact match on year field (if numeric looks like year)
                        {
                            "term": {
                                "year": {
                                    "value": int(numeric_part) if numeric_part.isdigit() and len(numeric_part) == 4 else 0,
                                    "boost": 10.0
                                }
                            }
                        } if numeric_part.isdigit() and len(numeric_part) == 4 else {},
                        # Strategy 2: Wildcard match in event_id field (if exists)
                        {
                            "wildcard": {
                                "event_id.keyword": {
                                    "value": f"*{query}*",
                                    "boost": 8.0
                                }
                            }
                        },
                        # Strategy 3: Match in title with high boost
                        {
                            "match": {
                                "event_title": {
                                    "query": query,
                                    "fuzziness": "AUTO",
                                    "boost": 6.0
                                }
                            }
                        },
                        # Strategy 4: Prefix match on country
                        {
                            "prefix": {
                                "country.keyword": {
                                    "value": query.capitalize(),
                                    "boost": 5.0
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1,
                    # Filter out empty strategies
                    "filter": []
                }
            },
            "size": size,
            "_source": ["event_id", "event_title", "country", "year", "event_theme"],
            "highlight": {
                "fields": {
                    "event_title": {},
                    "event_theme": {},
                    "country": {}
                }
            }
        }

    def _build_text_autocomplete_query(self, query: str, size: int) -> Dict[str, Any]:
        """
        Build query for text-based autocomplete (e.g., "climate" -> "Climate Summit").

        Uses edge n-grams and fuzzy matching for best autocomplete experience.
        """
        return {
            "query": {
                "bool": {
                    "should": [
                        # Strategy 1: Exact phrase match (highest priority)
                        {
                            "match_phrase": {
                                "event_title": {
                                    "query": query,
                                    "boost": 10.0
                                }
                            }
                        },
                        # Strategy 2: Prefix match on title
                        {
                            "match_phrase_prefix": {
                                "event_title": {
                                    "query": query,
                                    "boost": 8.0
                                }
                            }
                        },
                        # Strategy 3: Fuzzy match on title
                        {
                            "match": {
                                "event_title": {
                                    "query": query,
                                    "fuzziness": "AUTO",
                                    "boost": 6.0
                                }
                            }
                        },
                        # Strategy 4: Prefix match on theme
                        {
                            "match_phrase_prefix": {
                                "event_theme": {
                                    "query": query,
                                    "boost": 5.0
                                }
                            }
                        },
                        # Strategy 5: Fuzzy match on theme
                        {
                            "match": {
                                "event_theme": {
                                    "query": query,
                                    "fuzziness": "AUTO",
                                    "boost": 4.0
                                }
                            }
                        },
                        # Strategy 6: N-gram matching for partial words
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["event_title.ngram", "event_theme.ngram"],
                                "boost": 3.0
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": size,
            "_source": ["event_id", "event_title", "country", "year", "event_theme"],
            "highlight": {
                "fields": {
                    "event_title": {},
                    "event_theme": {}
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"]
            }
        }

    def _build_completion_suggester_query(self, query: str, size: int) -> Dict[str, Any]:
        """
        Build completion suggester query (fastest, for short queries).

        Note: Requires completion field in index mapping.
        """
        return {
            "suggest": {
                "event-suggest": {
                    "prefix": query,
                    "completion": {
                        "field": "suggest",
                        "size": size,
                        "skip_duplicates": True,
                        "fuzzy": {
                            "fuzziness": "AUTO",
                            "min_length": 3
                        }
                    }
                }
            }
        }

    def _format_autocomplete_results(
        self,
        opensearch_result: Dict[str, Any],
        query: str,
        query_type: str
    ) -> str:
        """
        Format autocomplete results into user-friendly suggestions.

        Returns JSON string with structured suggestions.
        """
        suggestions = []

        # Handle regular search results
        if "hits" in opensearch_result:
            hits = opensearch_result["hits"]["hits"]
            total = opensearch_result["hits"]["total"]["value"]

            for hit in hits:
                source = hit.get("_source", {})
                highlight = hit.get("highlight", {})

                suggestion = {
                    "id": source.get("event_id", hit.get("_id")),
                    "title": source.get("event_title", ""),
                    "subtitle": f"{source.get('country', '')} · {source.get('year', '')}",
                    "theme": source.get("event_theme", ""),
                    "score": hit.get("_score", 0),
                    "highlight": None
                }

                # Add highlighted text if available
                if highlight:
                    if "event_title" in highlight:
                        suggestion["highlight"] = highlight["event_title"][0]
                    elif "event_theme" in highlight:
                        suggestion["highlight"] = highlight["event_theme"][0]

                suggestions.append(suggestion)

            result = {
                "query": query,
                "query_type": query_type,
                "total_matches": total,
                "suggestions": suggestions,
                "count": len(suggestions)
            }

        # Handle completion suggester results
        elif "suggest" in opensearch_result:
            for suggest_name, suggest_results in opensearch_result["suggest"].items():
                for suggestion_group in suggest_results:
                    for option in suggestion_group.get("options", []):
                        suggestions.append({
                            "text": option.get("text", ""),
                            "score": option.get("_score", 0),
                        })

            result = {
                "query": query,
                "query_type": "completion",
                "suggestions": suggestions,
                "count": len(suggestions)
            }

        else:
            result = {
                "query": query,
                "query_type": query_type,
                "suggestions": [],
                "count": 0,
                "message": "No suggestions found"
            }

        return self._format_json_output(result)

    def _format_json_output(self, data: Dict[str, Any]) -> str:
        """Format data as readable JSON string."""
        import json

        # Pretty print for readability
        formatted = json.dumps(data, indent=2, ensure_ascii=False)

        # Add summary header
        count = data.get("count", 0)
        query = data.get("query", "")
        total = data.get("total_matches", count)

        header = f"🔍 Autocomplete Results for '{query}'\n"
        header += f"Found {count} suggestions (Total matches: {total})\n"
        header += "=" * 60 + "\n\n"

        return header + formatted

    async def handle_fuzzy_autocomplete(self, arguments: Dict[str, Any]) -> str:
        """
        Fuzzy autocomplete with intelligent query type detection.

        Automatically chooses the best search strategy based on query pattern:
        - Numeric queries (e.g., "1000") → Optimized for ID/year matching
        - Text queries (e.g., "climate") → Optimized for title/theme matching

        Args:
            arguments: Autocomplete parameters including query and size

        Returns:
            Formatted autocomplete suggestions as JSON string
        """
        query = arguments.get("query", "").strip()
        size = min(arguments.get("size", 10), 50)  # Max 50 for autocomplete

        if not query:
            return self._format_json_output({
                "query": "",
                "suggestions": [],
                "count": 0,
                "error": "Query cannot be empty"
            })

        # Detect query type
        query_type = self._detect_query_type(query)

        logger.info(f"Autocomplete query: '{query}' (type: {query_type}, size: {size})")

        try:
            # Build appropriate query based on type
            if query_type == "numeric":
                search_body = self._build_numeric_autocomplete_query(query, size)
            elif query_type == "id":
                search_body = self._build_numeric_autocomplete_query(query, size)
            else:  # text
                search_body = self._build_text_autocomplete_query(query, size)

            # Execute search
            result = await self.http_client.request(
                "POST",
                f"{self.index_name}/_search",
                search_body
            )

            # Format and return results
            return self._format_autocomplete_results(result, query, query_type)

        except Exception as e:
            logger.error(f"Autocomplete error for query '{query}': {e}", exc_info=True)
            return self._format_json_output({
                "query": query,
                "query_type": query_type,
                "suggestions": [],
                "count": 0,
                "error": f"Autocomplete failed: {str(e)}"
            })

    async def handle_validate_entity(self, arguments: Dict[str, Any]) -> str:
        """
        Validate if an entity exists (exact match).

        Used after user selects from autocomplete to confirm selection.

        Args:
            arguments: Validation parameters including entity_id

        Returns:
            Validation result with entity details if found
        """
        entity_id = arguments.get("entity_id", "").strip()

        if not entity_id:
            return self._format_json_output({
                "exists": False,
                "error": "Entity ID is required"
            })

        try:
            # Try exact match on multiple fields
            search_body = {
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"event_id.keyword": entity_id}},
                            {"term": {"_id": entity_id}},
                            {"match_phrase": {"event_title": entity_id}}
                        ]
                    }
                },
                "size": 1
            }

            result = await self.http_client.request(
                "POST",
                f"{self.index_name}/_search",
                search_body
            )

            hits = result.get("hits", {}).get("hits", [])

            if hits:
                entity = hits[0]["_source"]
                return self._format_json_output({
                    "exists": True,
                    "entity_id": entity_id,
                    "entity": {
                        "id": entity.get("event_id", hits[0]["_id"]),
                        "title": entity.get("event_title", ""),
                        "country": entity.get("country", ""),
                        "year": entity.get("year", ""),
                        "theme": entity.get("event_theme", "")
                    }
                })
            else:
                return self._format_json_output({
                    "exists": False,
                    "entity_id": entity_id,
                    "message": f"Entity '{entity_id}' not found"
                })

        except Exception as e:
            logger.error(f"Entity validation error for '{entity_id}': {e}", exc_info=True)
            return self._format_json_output({
                "exists": False,
                "entity_id": entity_id,
                "error": f"Validation failed: {str(e)}"
            })

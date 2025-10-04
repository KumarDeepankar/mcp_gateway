#!/usr/bin/env python3
"""
MCPTools - OpenSearch tools for MCP Server
Provides OpenSearch query capabilities via HTTP
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
    Uses HTTP to interact with OpenSearch instead of the OpenSearch library.
    """

    def __init__(self, opensearch_url: str = "http://localhost:9200"):
        self.opensearch_url = opensearch_url.rstrip("/")
        self.index_name = "stories"
        self.tools_registry = {}
        self._register_opensearch_tools()
        logger.info(f"MCPTools initialized with {len(self.tools_registry)} tools")
        logger.info(f"OpenSearch URL: {self.opensearch_url}")

    def _register_opensearch_tools(self):
        """Register OpenSearch-related tools."""

        # Search stories tool
        self.tools_registry["search_stories"] = {
            "definition": {
                "name": "search_stories",
                "description": "Search for stories in the OpenSearch index using a query string",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text to match against stories"
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
            "handler": self._handle_search_stories
        }

        # Get story by ID tool
        self.tools_registry["get_story"] = {
            "definition": {
                "name": "get_story",
                "description": "Retrieve a specific story by its document ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "story_id": {
                            "type": "string",
                            "description": "The document ID of the story to retrieve"
                        }
                    },
                    "required": ["story_id"]
                }
            },
            "handler": self._handle_get_story
        }

        # List all stories tool
        self.tools_registry["list_stories"] = {
            "definition": {
                "name": "list_stories",
                "description": "List all stories from the index",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "size": {
                            "type": "integer",
                            "description": "Number of stories to return (default: 10, max: 100)",
                            "default": 10
                        },
                        "from": {
                            "type": "integer",
                            "description": "Offset for pagination (default: 0)",
                            "default": 0
                        }
                    }
                }
            },
            "handler": self._handle_list_stories
        }

        # Count stories tool
        self.tools_registry["count_stories"] = {
            "definition": {
                "name": "count_stories",
                "description": "Get the total count of stories in the index",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            },
            "handler": self._handle_count_stories
        }

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get list of all tool definitions for tools/list response.
        """
        return [tool_info["definition"] for tool_info in self.tools_registry.values()]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute a tool with given arguments.
        Returns content in MCP format.
        """
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

    # OpenSearch HTTP helper methods
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

    # Tool handlers
    async def _handle_search_stories(self, arguments: Dict[str, Any]) -> str:
        """Search stories using query string."""
        query_text = arguments.get("query", "")
        size = min(arguments.get("size", 10), 100)

        if not query_text:
            return "Error: No query provided"

        search_body = {
            "query": {
                "multi_match": {
                    "query": query_text,
                    "fields": ["*"]
                }
            },
            "size": size
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)

            hits = result.get("hits", {}).get("hits", [])
            total_hits = result.get("hits", {}).get("total", {}).get("value", 0)

            if not hits:
                return f"No stories found matching query: '{query_text}'"

            # Format results
            stories = []
            for hit in hits:
                source = hit.get("_source", {})
                stories.append({
                    "id": hit.get("_id"),
                    "score": hit.get("_score"),
                    "data": source
                })

            response = f"Found {total_hits} stories matching '{query_text}'. Showing {len(hits)} results:\n\n"
            response += json.dumps(stories, indent=2)

            return response

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"Error searching stories: {str(e)}"

    async def _handle_get_story(self, arguments: Dict[str, Any]) -> str:
        """Get a specific story by ID."""
        story_id = arguments.get("story_id", "")

        if not story_id:
            return "Error: No story_id provided"

        try:
            result = await self._http_request("GET", f"{self.index_name}/_doc/{story_id}")

            if result.get("found"):
                story = {
                    "id": result.get("_id"),
                    "index": result.get("_index"),
                    "data": result.get("_source", {})
                }
                return f"Story found:\n\n{json.dumps(story, indent=2)}"
            else:
                return f"Story with ID '{story_id}' not found"

        except Exception as e:
            logger.error(f"Get story failed: {e}")
            return f"Error retrieving story: {str(e)}"

    async def _handle_list_stories(self, arguments: Dict[str, Any]) -> str:
        """List all stories with pagination."""
        size = min(arguments.get("size", 10), 100)
        from_offset = arguments.get("from", 0)

        search_body = {
            "query": {
                "match_all": {}
            },
            "size": size,
            "from": from_offset
        }

        try:
            result = await self._http_request("POST", f"{self.index_name}/_search", search_body)

            hits = result.get("hits", {}).get("hits", [])
            total_hits = result.get("hits", {}).get("total", {}).get("value", 0)

            if not hits:
                return "No stories found in the index"

            # Format results
            stories = []
            for hit in hits:
                source = hit.get("_source", {})
                stories.append({
                    "id": hit.get("_id"),
                    "data": source
                })

            response = f"Total stories: {total_hits}. Showing {len(hits)} stories (offset: {from_offset}):\n\n"
            response += json.dumps(stories, indent=2)

            return response

        except Exception as e:
            logger.error(f"List stories failed: {e}")
            return f"Error listing stories: {str(e)}"

    async def _handle_count_stories(self, arguments: Dict[str, Any]) -> str:
        """Count total number of stories."""
        try:
            result = await self._http_request("GET", f"{self.index_name}/_count")

            count = result.get("count", 0)
            return f"Total number of stories in the index: {count}"

        except Exception as e:
            logger.error(f"Count stories failed: {e}")
            return f"Error counting stories: {str(e)}"

    def register_tool(self, name: str, definition: Dict[str, Any], handler):
        """
        Register a new tool dynamically.

        Args:
            name: Tool name
            definition: Tool definition following MCP schema
            handler: Async function to handle tool execution
        """
        self.tools_registry[name] = {
            "definition": definition,
            "handler": handler
        }
        logger.info(f"Registered new tool: {name}")

    def unregister_tool(self, name: str) -> bool:
        """
        Unregister a tool.

        Args:
            name: Tool name to remove

        Returns:
            True if tool was removed, False if not found
        """
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

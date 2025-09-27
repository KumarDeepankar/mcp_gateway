#!/usr/bin/env python3
"""
MCP OpenSearch Tools - OpenSearch integration for MCP Server
Provides OpenSearch search capabilities through MCP tools interface
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import aiohttp

logger = logging.getLogger(__name__)


class OpenSearchClient:
    """
    OpenSearch client for handling search operations using HTTP requests.
    """

    def __init__(self, hosts: List[str] = None, **kwargs):
        """Initialize OpenSearch client."""
        if hosts is None:
            hosts = ["localhost:9200"]

        self.hosts = hosts
        self.base_url = f"http://{hosts[0]}"
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def is_connected(self) -> bool:
        """Check if client is connected to OpenSearch."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/_cluster/health") as response:
                    return response.status == 200
        except Exception:
            return False

    async def search_stories_index(self, query: str, size: int = 10) -> Dict[str, Any]:
        """
        Search the 'stories' index in OpenSearch.

        Args:
            query: Search term
            size: Maximum number of results to return

        Returns:
            Dictionary containing search results
        """
        if not await self.is_connected():
            raise ConnectionError("Not connected to OpenSearch")

        try:
            # Search the 'stories' index specifically
            search_body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "type": "best_fields",
                        "fields": ["*"]
                    }
                },
                "size": size,
                "sort": [
                    {"_score": {"order": "desc"}}
                ]
            }

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/stories/_search",
                    json=search_body,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 404:
                        return {
                            "total_hits": 0,
                            "max_score": 0,
                            "hits": [],
                            "took": 0,
                            "timed_out": False,
                            "error": "Stories index not found"
                        }

                    response.raise_for_status()
                    result = await response.json()

                    return {
                        "total_hits": result["hits"]["total"]["value"] if isinstance(result["hits"]["total"], dict) else result["hits"]["total"],
                        "max_score": result["hits"]["max_score"],
                        "hits": result["hits"]["hits"],
                        "took": result["took"],
                        "timed_out": result["timed_out"]
                    }

        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                return {
                    "total_hits": 0,
                    "max_score": 0,
                    "hits": [],
                    "took": 0,
                    "timed_out": False,
                    "error": "Stories index not found"
                }
            else:
                logger.error(f"HTTP error: {e}")
                raise
        except Exception as e:
            logger.error(f"Search error: {e}")
            raise

    async def get_cluster_info(self) -> Dict[str, Any]:
        """Get OpenSearch cluster information."""
        if not await self.is_connected():
            raise ConnectionError("Not connected to OpenSearch")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Get cluster info
                async with session.get(f"{self.base_url}/") as response:
                    response.raise_for_status()
                    info = await response.json()

                # Get indices information
                async with session.get(f"{self.base_url}/_cat/indices?format=json") as response:
                    response.raise_for_status()
                    indices_response = await response.json()

                return {
                    "cluster_info": info,
                    "indices": indices_response if indices_response else []
                }

        except Exception as e:
            logger.error(f"Failed to get cluster info: {e}")
            raise


class MCPOpenSearchTools:
    """
    OpenSearch tools for MCP server.
    Provides OpenSearch search capabilities through MCP tools interface.
    """

    def __init__(self, opensearch_hosts: List[str] = None):
        self.tools_registry = {}
        self.opensearch_client = OpenSearchClient(hosts=opensearch_hosts)
        self._register_opensearch_tools()
        logger.info(f"MCPOpenSearchTools initialized with {len(self.tools_registry)} tools")

    def _register_opensearch_tools(self):
        """Register OpenSearch tools available in the MCP server."""

        # OpenSearch search tool
        self.tools_registry["opensearch_search"] = {
            "definition": {
                "name": "opensearch_search",
                "description": "Search the 'stories' index in OpenSearch for documents containing the specified term",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term or query string to search for in the stories index"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["query"]
                }
            },
            "handler": self._handle_opensearch_search
        }

        # OpenSearch cluster info tool
        self.tools_registry["opensearch_info"] = {
            "definition": {
                "name": "opensearch_info",
                "description": "Get OpenSearch cluster information and available indices",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            },
            "handler": self._handle_opensearch_info
        }

        # Connection status tool
        self.tools_registry["opensearch_status"] = {
            "definition": {
                "name": "opensearch_status",
                "description": "Check OpenSearch connection status",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            },
            "handler": self._handle_opensearch_status
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
            logger.info(f"Executing OpenSearch tool '{tool_name}' with arguments: {arguments}")
            result = await handler(arguments)

            # Ensure result is in proper MCP content format
            if isinstance(result, str):
                return [{"type": "text", "text": result}]
            elif isinstance(result, list):
                return result
            else:
                return [{"type": "text", "text": str(result)}]

        except Exception as e:
            logger.error(f"Error executing OpenSearch tool '{tool_name}': {e}", exc_info=True)
            raise

    # Tool handlers
    async def _handle_opensearch_search(self, arguments: Dict[str, Any]) -> str:
        """Handle OpenSearch search tool execution."""
        query = arguments.get("query", "")
        size = arguments.get("size", 10)

        if not query:
            return "Error: No search query provided"

        try:
            results = await self.opensearch_client.search_stories_index(query, size)

            if "error" in results:
                return f"Search error: {results['error']}"

            # Format search results
            output = []
            output.append(f"OpenSearch Stories Index Results for query: '{query}'")
            output.append(f"Total hits: {results['total_hits']}")
            output.append(f"Search took: {results['took']}ms")
            output.append(f"Max score: {results['max_score']}")
            output.append("")

            if results['hits']:
                for i, hit in enumerate(results['hits'], 1):
                    output.append(f"Result {i}:")
                    output.append(f"  Index: {hit['_index']}")
                    output.append(f"  Type: {hit.get('_type', 'N/A')}")
                    output.append(f"  ID: {hit['_id']}")
                    output.append(f"  Score: {hit['_score']}")

                    # Format source data
                    source = hit.get('_source', {})
                    if source:
                        output.append("  Source:")
                        for key, value in source.items():
                            # Truncate long values
                            str_value = str(value)
                            if len(str_value) > 200:
                                str_value = str_value[:200] + "..."
                            output.append(f"    {key}: {str_value}")

                    output.append("")
            else:
                output.append("No results found in the stories index.")

            return "\n".join(output)

        except ConnectionError as e:
            return f"Connection error: {str(e)}. Please ensure OpenSearch is running at localhost:9200"
        except Exception as e:
            return f"Search failed: {str(e)}"

    async def _handle_opensearch_info(self, arguments: Dict[str, Any]) -> str:
        """Handle OpenSearch cluster info tool execution."""
        try:
            info = await self.opensearch_client.get_cluster_info()

            output = []
            output.append("OpenSearch Cluster Information")
            output.append("=" * 35)

            cluster_info = info.get("cluster_info", {})
            output.append(f"Cluster Name: {cluster_info.get('cluster_name', 'N/A')}")
            output.append(f"Version: {cluster_info.get('version', {}).get('number', 'N/A')}")
            output.append(f"Node Name: {cluster_info.get('name', 'N/A')}")
            output.append("")

            indices = info.get("indices", [])
            if indices:
                output.append("Available Indices:")
                output.append("-" * 18)
                for index in indices:
                    index_name = index.get('index', 'N/A')
                    doc_count = index.get('docs.count', 'N/A')
                    store_size = index.get('store.size', 'N/A')
                    output.append(f"  {index_name}")
                    output.append(f"    Documents: {doc_count}")
                    output.append(f"    Size: {store_size}")
                    output.append("")
            else:
                output.append("No indices found or unable to retrieve index information.")

            return "\n".join(output)

        except ConnectionError as e:
            return f"Connection error: {str(e)}. Please ensure OpenSearch is running at localhost:9200"
        except Exception as e:
            return f"Failed to get cluster info: {str(e)}"

    async def _handle_opensearch_status(self, arguments: Dict[str, Any]) -> str:
        """Handle OpenSearch status check tool execution."""
        try:
            is_connected = await self.opensearch_client.is_connected()

            if is_connected:
                return "✅ OpenSearch connection: ACTIVE\nSuccessfully connected to OpenSearch cluster at localhost:9200"
            else:
                return "❌ OpenSearch connection: FAILED\nUnable to connect to OpenSearch at localhost:9200\nPlease ensure OpenSearch is running and accessible."

        except Exception as e:
            return f"❌ OpenSearch connection: ERROR\nFailed to check status: {str(e)}"

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
        logger.info(f"Registered new OpenSearch tool: {name}")

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
            logger.info(f"Unregistered OpenSearch tool: {name}")
            return True
        return False

    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific tool."""
        return self.tools_registry.get(name)

    def list_tool_names(self) -> List[str]:
        """Get list of all registered tool names."""
        return list(self.tools_registry.keys())
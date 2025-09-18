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
from opensearchpy import OpenSearch, exceptions as opensearch_exceptions

logger = logging.getLogger(__name__)


class OpenSearchClient:
    """
    OpenSearch client for handling search operations.
    """

    def __init__(self, hosts: List[str] = None, **kwargs):
        """Initialize OpenSearch client."""
        if hosts is None:
            hosts = ["localhost:9200"]

        self.hosts = hosts
        self.client = None
        self._connect()

    def _connect(self):
        """Establish connection to OpenSearch."""
        try:
            self.client = OpenSearch(
                hosts=self.hosts,
                http_compress=True,  # enables gzip compression for request/response bodies
                use_ssl=False,  # Disable SSL for localhost development
                verify_certs=False,
                ssl_assert_hostname=False,
                ssl_show_warn=False,
                timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )

            # Test connection
            info = self.client.info()
            logger.info(f"Connected to OpenSearch cluster: {info.get('cluster_name', 'unknown')}")

        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            self.client = None

    def is_connected(self) -> bool:
        """Check if client is connected to OpenSearch."""
        if not self.client:
            return False

        try:
            self.client.ping()
            return True
        except Exception:
            return False

    async def search_all_indices(self, query: str, size: int = 10) -> Dict[str, Any]:
        """
        Search across all indices in OpenSearch.

        Args:
            query: Search term
            size: Maximum number of results to return

        Returns:
            Dictionary containing search results
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to OpenSearch")

        try:
            # Search across all indices using _all
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

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.search(
                    index="_all",
                    body=search_body
                )
            )

            return {
                "total_hits": response["hits"]["total"]["value"],
                "max_score": response["hits"]["max_score"],
                "hits": response["hits"]["hits"],
                "took": response["took"],
                "timed_out": response["timed_out"]
            }

        except opensearch_exceptions.NotFoundError:
            return {
                "total_hits": 0,
                "max_score": 0,
                "hits": [],
                "took": 0,
                "timed_out": False,
                "error": "No indices found"
            }
        except Exception as e:
            logger.error(f"Search error: {e}")
            raise

    async def get_cluster_info(self) -> Dict[str, Any]:
        """Get OpenSearch cluster information."""
        if not self.is_connected():
            raise ConnectionError("Not connected to OpenSearch")

        try:
            info = await asyncio.get_event_loop().run_in_executor(
                None, self.client.info
            )

            # Get indices information
            indices_response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.client.cat.indices(format="json")
            )

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
                "description": "Search across all OpenSearch indices for documents containing the specified term",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term or query string to search for across all indices"
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
            results = await self.opensearch_client.search_all_indices(query, size)

            if "error" in results:
                return f"Search error: {results['error']}"

            # Format search results
            output = []
            output.append(f"OpenSearch Results for query: '{query}'")
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
                output.append("No results found.")

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
            is_connected = self.opensearch_client.is_connected()

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
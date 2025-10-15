#!/usr/bin/env python3
"""
HTTP Client for OpenSearch
Handles all HTTP requests to OpenSearch server
"""
import logging
from typing import Dict, Any, Optional
import aiohttp

logger = logging.getLogger(__name__)


class OpenSearchHTTPClient:
    """HTTP client for making requests to OpenSearch."""

    def __init__(self, opensearch_url: str, index_name: str):
        """
        Initialize OpenSearch HTTP client.

        Args:
            opensearch_url: Base URL for OpenSearch server
            index_name: Default index name for queries
        """
        self.opensearch_url = opensearch_url.rstrip("/")
        self.index_name = index_name
        logger.info(f"OpenSearch HTTP Client initialized - URL: {self.opensearch_url}, Index: {self.index_name}")

    async def request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to OpenSearch.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (relative to base URL)
            body: Optional request body for POST requests

        Returns:
            Response JSON as dictionary

        Raises:
            Exception: If request fails
        """
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

#!/usr/bin/env python3
"""
MCPTools - Modular tools system for MCP Server
Provides a clean interface for tool definitions and execution
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MCPTools:
    """
    Modular tools system for MCP server.
    Provides tool definitions and execution capabilities.
    """

    def __init__(self):
        self.tools_registry = {}
        self._register_default_tools()
        logger.info(f"MCPTools initialized with {len(self.tools_registry)} tools")

    def _register_default_tools(self):
        """Register default tools available in the MCP server."""

        # Echo tool
        self.tools_registry["echo"] = {
            "definition": {
                "name": "echo",
                "description": "Echo back the provided text",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to echo back"
                        }
                    },
                    "required": ["text"]
                }
            },
            "handler": self._handle_echo
        }

        # Get time tool
        self.tools_registry["get_time"] = {
            "definition": {
                "name": "get_time",
                "description": "Get the current server time",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            },
            "handler": self._handle_get_time
        }

        # Calculator tool
        self.tools_registry["calculate"] = {
            "definition": {
                "name": "calculate",
                "description": "Perform basic mathematical calculations",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')"
                        }
                    },
                    "required": ["expression"]
                }
            },
            "handler": self._handle_calculate
        }

        # Random number generator
        self.tools_registry["random_number"] = {
            "definition": {
                "name": "random_number",
                "description": "Generate a random number within a specified range",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "min": {
                            "type": "integer",
                            "description": "Minimum value (inclusive)",
                            "default": 1
                        },
                        "max": {
                            "type": "integer",
                            "description": "Maximum value (inclusive)",
                            "default": 100
                        }
                    }
                }
            },
            "handler": self._handle_random_number
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

    # Tool handlers
    async def _handle_echo(self, arguments: Dict[str, Any]) -> str:
        """Handle echo tool execution."""
        text = arguments.get("text", "")
        return f"Echo: {text}"

    async def _handle_get_time(self, arguments: Dict[str, Any]) -> str:
        """Handle get_time tool execution."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"Current server time: {current_time}"

    async def _handle_calculate(self, arguments: Dict[str, Any]) -> str:
        """Handle calculate tool execution."""
        expression = arguments.get("expression", "")

        if not expression:
            return "Error: No expression provided"

        try:
            # Safe evaluation - only allow basic math operations
            allowed_chars = set("0123456789+-*/().= ")
            if not all(c in allowed_chars for c in expression):
                return "Error: Invalid characters in expression. Only numbers and basic operators (+, -, *, /, parentheses) are allowed."

            # Replace common math symbols
            safe_expr = expression.replace("^", "**").replace("=", "")

            # Evaluate safely
            result = eval(safe_expr)
            return f"Result: {expression} = {result}"

        except ZeroDivisionError:
            return "Error: Division by zero"
        except Exception as e:
            return f"Error: Invalid expression - {str(e)}"

    async def _handle_random_number(self, arguments: Dict[str, Any]) -> str:
        """Handle random_number tool execution."""
        import random

        min_val = arguments.get("min", 1)
        max_val = arguments.get("max", 100)

        if min_val > max_val:
            return f"Error: min value ({min_val}) cannot be greater than max value ({max_val})"

        random_num = random.randint(min_val, max_val)
        return f"Random number between {min_val} and {max_val}: {random_num}"

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
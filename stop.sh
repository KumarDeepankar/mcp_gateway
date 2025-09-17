#!/bin/bash

# Stop MCP Gateway Services

echo "🛑 Stopping MCP Gateway Services..."
echo "=================================="

docker-compose down

echo ""
echo "✅ All services stopped"
echo "💡 To start again: ./start.sh"
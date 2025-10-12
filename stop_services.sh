#!/bin/bash
# Stop script for MCP Gateway Services

echo "🛑 Stopping MCP Gateway Services"
echo "================================"

# Check for .pids file
if [ -f .pids ]; then
    echo "📋 Reading PIDs from .pids file..."
    while read -r pid; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "   Killing process $pid..."
            kill $pid
        else
            echo "   Process $pid not running"
        fi
    done < .pids
    rm .pids
fi

# Kill by port (fallback)
if lsof -i :8021 > /dev/null 2>&1; then
    echo "📋 Stopping tools_gateway (Port 8021)..."
    lsof -ti :8021 | xargs kill -9
    echo "   ✅ Stopped"
fi

if lsof -i :8023 > /dev/null 2>&1; then
    echo "📋 Stopping agentic_search (Port 8023)..."
    lsof -ti :8023 | xargs kill -9
    echo "   ✅ Stopped"
fi

echo ""
echo "✅ All services stopped"

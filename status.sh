#!/bin/bash

# Check MCP Gateway Status

echo "📊 MCP Gateway Status"
echo "===================="
echo ""

# Check Docker containers
echo "🐳 Container Status:"
docker ps --filter "name=mcp" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""

# Check if services are responding
echo "🏥 Health Checks:"

# Check MCP Server
if curl -s http://localhost:8000 > /dev/null 2>&1; then
    echo "✅ MCP Server (port 8000) - Running"
else
    echo "❌ MCP Server (port 8000) - Not responding"
fi

# Check Registry Discovery
if curl -s http://localhost:8021 > /dev/null 2>&1; then
    echo "✅ Registry Discovery (port 8021) - Running"
else
    echo "❌ Registry Discovery (port 8021) - Not responding"
fi

# Check Ngrok
if curl -s http://localhost:4040 > /dev/null 2>&1; then
    echo "✅ Ngrok (port 4040) - Running"

    # Get current URL
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    if tunnels:
        print(tunnels[0]['public_url'])
    else:
        print('No tunnels found')
except:
    print('Error')
" 2>/dev/null)

    if [[ $NGROK_URL == *"ngrok"* ]]; then
        echo "   📡 Current URL: $NGROK_URL"
    fi
else
    echo "❌ Ngrok (port 4040) - Not responding"
fi

echo ""
echo "💡 Commands:"
echo "   ./start.sh    - Start all services"
echo "   ./stop.sh     - Stop all services"
echo "   ./get-url.sh  - Get current HTTPS URL"
echo "   ./logs.sh     - View service logs"
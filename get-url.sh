#!/bin/bash

# Get MCP Gateway HTTPS URL
# This script retrieves the current ngrok tunnel URL

echo "🌐 Getting MCP Gateway HTTPS endpoint..."

# Check if ngrok is running
if ! curl -s http://localhost:4040 > /dev/null 2>&1; then
    echo ""
    echo "❌ Ngrok is not running"
    echo ""
    echo "ℹ️  Ngrok is disabled by default (free tier limited to 3 tunnels)"
    echo ""
    echo "To start ngrok:"
    echo "  ./start-ngrok.sh"
    echo "  OR"
    echo "  make ngrok"
    echo ""
    echo "Note: You may need to edit ngrok/ngrok.yml to select 3 services"
    exit 1
fi

# Get the ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    if tunnels:
        print(tunnels[0]['public_url'])
    else:
        print('No tunnels found')
except Exception as e:
    print('Error getting tunnel info:', str(e))
")

if [[ $NGROK_URL == *"ngrok"* ]]; then
    echo ""
    echo "✅ Current HTTPS Endpoint:"
    echo "📡 $NGROK_URL"
    echo ""
    echo "🔗 Full MCP endpoint: $NGROK_URL/mcp"
    echo "🔧 Ngrok Dashboard: http://localhost:4040"

    # Test the endpoint
    echo ""
    echo "🧪 Testing endpoint..."
    if curl -s "$NGROK_URL" > /dev/null 2>&1; then
        echo "✅ Endpoint is responding"
    else
        echo "⚠️  Endpoint may not be fully ready yet"
    fi
else
    echo "❌ Could not retrieve ngrok URL. Error: $NGROK_URL"
    echo "💡 Try running: docker-compose logs ngrok"
fi
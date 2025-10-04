#!/bin/bash

# Start Ngrok Tunnel
# Note: Free ngrok accounts are limited to 3 tunnels
# You may need to choose which 3 services to expose

set -e

echo "🌐 Starting Ngrok Tunnels..."
echo "=================================="
echo ""
echo "⚠️  WARNING: Free ngrok accounts support max 3 tunnels"
echo "   Current services available:"
echo "   - mcp-server (8000)"
echo "   - mcp-opensearch (8001)"
echo "   - tools-gateway (8021)"
echo "   - agentic-search (8023)"
echo ""
echo "   Modify ngrok/ngrok.yml to select which 3 to expose"
echo ""

# Start ngrok
docker-compose --profile ngrok up -d ngrok

# Wait for ngrok to start
echo "Waiting for ngrok to start..."
sleep 5

# Check if ngrok is ready
max_attempts=10
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:4040 > /dev/null 2>&1; then
        echo "✅ Ngrok is ready"
        break
    fi
    echo "⏳ Waiting for ngrok... (attempt $attempt/$max_attempts)"
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ Ngrok failed to start"
    echo "   Check logs: docker-compose logs ngrok"
    exit 1
fi

# Get ngrok tunnels
echo ""
echo "🌐 Ngrok Tunnels:"
echo "=================================="

curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    if not tunnels:
        print('❌ No tunnels found - check ngrok logs')
        print('   docker-compose logs ngrok')
    else:
        for tunnel in tunnels:
            name = tunnel.get('name', 'unknown')
            url = tunnel.get('public_url', 'N/A')
            print(f'✅ {name}: {url}')
except Exception as e:
    print(f'❌ Error getting tunnel info: {e}')
"

echo ""
echo "🔧 Ngrok Dashboard: http://localhost:4040"
echo ""
echo "💡 To stop ngrok: docker-compose stop ngrok"

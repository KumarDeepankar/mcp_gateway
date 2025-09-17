#!/bin/bash

# MCP Gateway Startup Script
# Starts all services and displays the HTTPS endpoint

set -e

echo "🚀 Starting MCP Gateway Services..."
echo "=================================="

# Stop any existing containers
echo "Stopping existing containers..."
docker-compose down > /dev/null 2>&1 || true

# Start all services
echo "Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 5

# Function to check if a service is ready
check_service() {
    local service_name=$1
    local port=$2
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$port > /dev/null 2>&1; then
            echo "✅ $service_name is ready"
            return 0
        fi
        echo "⏳ Waiting for $service_name... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "❌ $service_name failed to start"
    return 1
}

# Check if MCP server is ready
check_service "MCP Server" 8000

# Check if ngrok is ready
check_service "Ngrok" 4040

# Get the ngrok URL
echo ""
echo "🌐 Getting HTTPS endpoint..."
sleep 2

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
    print('Error getting tunnel info')
")

echo ""
echo "🎉 MCP Gateway is running!"
echo "========================="
echo "📡 HTTPS Endpoint: $NGROK_URL"
echo "🔧 Ngrok Dashboard: http://localhost:4040"
echo "🏠 Local MCP Server: http://localhost:8000"
echo "📊 Registry Discovery: http://localhost:8021"
echo ""
echo "💡 To stop services: ./stop.sh"
echo "💡 To get URL again: ./get-url.sh"
echo "💡 To view logs: ./logs.sh"
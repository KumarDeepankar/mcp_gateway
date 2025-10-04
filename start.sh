#!/bin/bash

# MCP Gateway Startup Script
# Starts all services and displays the HTTPS endpoint

set -e

echo "🚀 Starting MCP Gateway Services..."
echo "=================================="

# Stop any existing containers
echo "Stopping existing containers..."
docker-compose down > /dev/null 2>&1 || true

# Start all services (excluding ngrok by default)
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

# Check if OpenSearch MCP is ready
check_service "OpenSearch MCP" 8001

# Check if Tools Gateway is ready
check_service "Tools Gateway" 8021

# Check if Agentic Search is ready
check_service "Agentic Search" 8023

echo ""
echo "🎉 MCP Gateway is running!"
echo "========================="
echo "🏠 MCP Server: http://localhost:8000"
echo "🔍 OpenSearch MCP: http://localhost:8001"
echo "🛠️  Tools Gateway: http://localhost:8021"
echo "🤖 Agentic Search: http://localhost:8023"
echo ""
echo "ℹ️  Ngrok is NOT started (free tier limited to 3 tunnels)"
echo "   To start ngrok: docker-compose --profile ngrok up -d ngrok"
echo ""
echo "💡 To stop services: ./stop.sh"
echo "💡 To view status: ./status.sh"
echo "💡 To view logs: ./logs.sh"
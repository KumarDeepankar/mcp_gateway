#!/bin/bash

# Kill all ngrok tunnels and processes

echo "🛑 Killing all ngrok tunnels..."
echo "================================"

# Stop ngrok container if running
echo "Stopping ngrok container..."
docker-compose stop ngrok 2>/dev/null || true
docker-compose rm -f ngrok 2>/dev/null || true

# Kill any ngrok processes
echo "Killing ngrok processes..."
pkill -9 ngrok 2>/dev/null || true

# Check for any remaining ngrok processes using pgrep
NGROK_PIDS=$(pgrep -f ngrok 2>/dev/null || true)
if [ ! -z "$NGROK_PIDS" ]; then
    echo "Found ngrok processes: $NGROK_PIDS"
    kill -9 $NGROK_PIDS 2>/dev/null || true
fi

# Wait a moment
sleep 1

# Verify everything is stopped
if pgrep ngrok > /dev/null 2>&1; then
    echo "⚠️  Warning: Some ngrok processes may still be running"
    pgrep -fl ngrok
else
    echo "✅ All ngrok processes killed"
fi

# Check port
if lsof -i :4040 > /dev/null 2>&1; then
    echo "⚠️  Port 4040 still in use:"
    lsof -i :4040
else
    echo "✅ Port 4040 is free"
fi

echo ""
echo "✅ Ngrok cleanup complete!"
echo ""
echo "Note: Tunnels are also terminated on ngrok's servers automatically"
echo "      when the client disconnects."

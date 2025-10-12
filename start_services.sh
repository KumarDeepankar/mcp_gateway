#!/bin/bash
# Startup script for RBAC & OAuth2 integrated services

echo "🚀 Starting MCP Gateway Services with RBAC & OAuth2"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if tools_gateway is running
if lsof -i :8021 > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 8021 already in use (tools_gateway may be running)${NC}"
    echo "   Kill existing process? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        lsof -ti :8021 | xargs kill -9
        echo "   ✅ Killed existing process on port 8021"
    fi
fi

# Check if agentic_search is running
if lsof -i :8023 > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 8023 already in use (agentic_search may be running)${NC}"
    echo "   Kill existing process? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        lsof -ti :8023 | xargs kill -9
        echo "   ✅ Killed existing process on port 8023"
    fi
fi

echo ""
echo -e "${BLUE}📋 Starting tools_gateway (Port 8021)...${NC}"
python -m uvicorn tools_gateway.main:app --port 8021 --reload > logs/tools_gateway.log 2>&1 &
GATEWAY_PID=$!

# Wait for tools_gateway to start
sleep 3

# Check if tools_gateway started successfully
if curl -s http://localhost:8021/health > /dev/null; then
    echo -e "${GREEN}   ✅ tools_gateway started successfully (PID: $GATEWAY_PID)${NC}"
    echo "      URL: http://localhost:8021"
else
    echo -e "${YELLOW}   ⚠️  tools_gateway may not have started. Check logs/tools_gateway.log${NC}"
fi

echo ""
echo -e "${BLUE}📋 Starting agentic_search (Port 8023)...${NC}"
(cd agentic_search && python server.py) > logs/agentic_search.log 2>&1 &
SEARCH_PID=$!

# Wait for agentic_search to start
sleep 3

# Check if agentic_search started successfully
if curl -s http://localhost:8023/health > /dev/null; then
    echo -e "${GREEN}   ✅ agentic_search started successfully (PID: $SEARCH_PID)${NC}"
    echo "      URL: http://localhost:8023"
else
    echo -e "${YELLOW}   ⚠️  agentic_search may not have started. Check logs/agentic_search.log${NC}"
fi

echo ""
echo "=================================================="
echo -e "${GREEN}🎉 Services Started!${NC}"
echo ""
echo "📝 Quick Test:"
echo "   1. Open: http://localhost:8023"
echo "   2. You'll be redirected to login page"
echo "   3. Click 'Login with Google' (or use admin login)"
echo ""
echo "🔑 Admin Login (tools_gateway):"
echo "   URL: http://localhost:8021"
echo "   Email: admin"
echo "   Password: admin"
echo ""
echo "📊 Monitoring:"
echo "   tools_gateway logs: tail -f logs/tools_gateway.log"
echo "   agentic_search logs: tail -f logs/agentic_search.log"
echo ""
echo "🛑 Stop Services:"
echo "   kill $GATEWAY_PID $SEARCH_PID"
echo "   Or run: ./stop_services.sh"
echo ""
echo "Process IDs saved to: .pids"
echo "$GATEWAY_PID" > .pids
echo "$SEARCH_PID" >> .pids

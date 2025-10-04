# MCP Gateway Management Commands

.PHONY: start start-local stop status logs help clean start-ngrok stop-ngrok

# Default target
help:
	@echo "🚀 MCP Gateway Commands"
	@echo "======================"
	@echo ""
	@echo "📋 Available commands:"
	@echo "  make start        - Start all services with ngrok tunnels"
	@echo "  make start-local  - Start services locally (no ngrok)"
	@echo "  make stop         - Stop all services including ngrok"
	@echo "  make stop-ngrok   - Stop only ngrok tunnels"
	@echo "  make status       - Check service status"
	@echo "  make logs         - View service logs"
	@echo "  make clean        - Stop services and clean up"
	@echo "  make help         - Show this help"
	@echo ""

# Start all services with ngrok (default behavior)
start:
	@echo "🚀 Starting MCP Gateway Services with Ngrok..."
	@echo "=================================="
	@echo ""
	@echo "Stopping existing containers..."
	@docker-compose down > /dev/null 2>&1 || true
	@echo "Starting all services including ngrok..."
	@docker-compose --profile ngrok up -d
	@echo ""
	@echo "Waiting for services to start..."
	@sleep 5
	@echo ""
	@$(MAKE) --no-print-directory _check-services
	@$(MAKE) --no-print-directory _show-urls

# Start services locally without ngrok
start-local:
	@echo "🚀 Starting MCP Gateway Services (Local Only)..."
	@echo "=================================="
	@echo ""
	@echo "Stopping existing containers..."
	@docker-compose down > /dev/null 2>&1 || true
	@echo "Starting services (excluding ngrok)..."
	@docker-compose up -d
	@echo ""
	@echo "Waiting for services to start..."
	@sleep 5
	@echo ""
	@$(MAKE) --no-print-directory _check-services
	@echo ""
	@echo "🎉 MCP Gateway is running (Local Only)!"
	@echo "========================="
	@echo "🏠 MCP Server: http://localhost:8000"
	@echo "🔍 OpenSearch MCP: http://localhost:8001"
	@echo "🛠️  Tools Gateway: http://localhost:8021"
	@echo "🤖 Agentic Search: http://localhost:8023"
	@echo ""
	@echo "💡 To start ngrok: make start-ngrok"
	@echo "💡 To stop services: make stop"

# Start ngrok tunnels only
start-ngrok:
	@echo "🌐 Starting Ngrok Tunnels..."
	@echo "=================================="
	@docker-compose --profile ngrok up -d ngrok
	@echo ""
	@echo "Waiting for ngrok to start..."
	@sleep 5
	@$(MAKE) --no-print-directory _show-ngrok-urls

# Stop ngrok only
stop-ngrok:
	@echo "🛑 Stopping Ngrok..."
	@docker-compose stop ngrok
	@docker-compose rm -f ngrok
	@echo "✅ Ngrok stopped"

# Stop services
stop:
	@echo "🛑 Stopping all services..."
	@docker-compose down
	@echo "✅ All services stopped"

# Check status
status:
	@echo "📊 Service Status:"
	@echo "=================="
	@docker-compose ps

# Internal target: Check if services are ready
_check-services:
	@echo "Checking service health..."
	@for port in 8000 8001 8021 8023; do \
		attempt=1; \
		max_attempts=30; \
		while [ $$attempt -le $$max_attempts ]; do \
			if curl -s http://localhost:$$port > /dev/null 2>&1; then \
				echo "✅ Port $$port is ready"; \
				break; \
			fi; \
			if [ $$attempt -eq $$max_attempts ]; then \
				echo "⚠️  Port $$port not responding"; \
			fi; \
			attempt=$$((attempt + 1)); \
			sleep 1; \
		done; \
	done

# Internal target: Show all URLs
_show-urls:
	@echo ""
	@echo "🎉 MCP Gateway is running!"
	@echo "========================="
	@echo ""
	@echo "📍 Local endpoints:"
	@echo "  🏠 MCP Server: http://localhost:8000"
	@echo "  🔍 OpenSearch MCP: http://localhost:8001"
	@echo "  🛠️  Tools Gateway: http://localhost:8021"
	@echo "  🤖 Agentic Search: http://localhost:8023"
	@echo ""
	@if curl -s http://localhost:4040 > /dev/null 2>&1; then \
		$(MAKE) --no-print-directory _show-ngrok-urls; \
	else \
		echo "⚠️  Ngrok did not start (check logs: make logs)"; \
	fi
	@echo ""
	@echo "💡 To stop services: make stop"
	@echo "💡 To view logs: make logs"

# Internal target: Show ngrok URLs
_show-ngrok-urls:
	@echo "🌐 Ngrok HTTPS endpoints:"
	@curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); [print(f\"  🔗 {t.get('name', 'unknown')}: {t.get('public_url', 'N/A')}\") for t in data.get('tunnels', [])] if data.get('tunnels') else print('  ❌ No tunnels found')" 2>/dev/null || echo "  ⏳ Ngrok tunnels starting..."
	@echo "  🔧 Dashboard: http://localhost:4040"

# View logs
logs:
	@./logs.sh

# Clean up everything
clean:
	@echo "🧹 Cleaning up MCP Gateway..."
	@docker-compose down
	@docker system prune -f
	@echo "✅ Cleanup complete"
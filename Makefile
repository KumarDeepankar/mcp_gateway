# MCP Gateway Management Commands

.PHONY: start stop status url logs help clean

# Default target
help:
	@echo "🚀 MCP Gateway Commands"
	@echo "======================"
	@echo ""
	@echo "📋 Available commands:"
	@echo "  make start   - Start all services and show HTTPS URL"
	@echo "  make stop    - Stop all services"
	@echo "  make status  - Check service status"
	@echo "  make url     - Get current HTTPS endpoint"
	@echo "  make logs    - View service logs"
	@echo "  make clean   - Stop services and clean up"
	@echo "  make help    - Show this help"
	@echo ""

# Start services and show URL
start:
	@./start.sh

# Stop services
stop:
	@./stop.sh

# Check status
status:
	@./status.sh

# Get current URL
url:
	@./get-url.sh

# View logs
logs:
	@./logs.sh

# Clean up everything
clean:
	@echo "🧹 Cleaning up MCP Gateway..."
	@docker-compose down
	@docker system prune -f
	@echo "✅ Cleanup complete"
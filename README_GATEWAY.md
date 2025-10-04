# MCP Gateway

Multi-service MCP (Model Context Protocol) Gateway with integrated tool registry, search capabilities, and ngrok tunneling.

## Quick Start

```bash
# Start all services with ngrok tunnels
make start

# Start services locally (no ngrok)
make start-local

# Stop all services
make stop

# View service status
make status
```

## Services

| Service | Port | Description | Ngrok |
|---------|------|-------------|-------|
| **MCP Server** | 8000 | Main MCP server | ✅ Yes |
| **OpenSearch MCP** | 8001 | OpenSearch integration | ❌ No (4th service) |
| **Tools Gateway** | 8021 | MCP tool registry | ✅ Yes |
| **Agentic Search** | 8023 | AI-powered search agent | ✅ Yes |

## Available Commands

```bash
make start        # Start with ngrok (default)
make start-local  # Start locally only
make start-ngrok  # Start ngrok only
make stop         # Stop all services
make stop-ngrok   # Stop ngrok only
make status       # Check service status
make logs         # View service logs
make clean        # Stop and clean up
make help         # Show available commands
```

## Endpoints

### Local (HTTP)
- http://localhost:8000 - MCP Server
- http://localhost:8001 - OpenSearch MCP
- http://localhost:8021 - Tools Gateway
- http://localhost:8023 - Agentic Search

### Public (HTTPS via Ngrok)
Run `make start` to see your ngrok URLs, or visit http://localhost:4040

**Note:** Free ngrok tier = 3 tunnels max. `mcp-opensearch` disabled by default.

## Documentation

- `README_GATEWAY.md` - This file (Quick reference)
- `STARTUP.md` - Detailed startup guide
- `CHANGES.md` - Recent changes summary

## Quick Troubleshooting

**Ngrok "max 3 endpoints" error:**
- Expected! Edit `ngrok/ngrok.yml` to choose 3 services

**Can't connect to localhost:8001 from tools-gateway:**
- Use container name: `http://mcp-opensearch:8001` not `localhost:8001`

**Service not starting:**
```bash
make logs                        # View all logs
docker-compose logs <service>    # View specific service
```

For detailed documentation, see `STARTUP.md`.

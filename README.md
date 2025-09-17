# MCP Gateway

A Docker-based MCP (Model Context Protocol) server with automatic HTTPS tunneling via ngrok.

## 🚀 Quick Start

### Option 1: Using Make (Recommended)
```bash
make start    # Start all services and get HTTPS URL
make url      # Get current HTTPS endpoint
make status   # Check service health
make stop     # Stop all services
```

### Option 2: Using Scripts
```bash
./start.sh    # Start services
./get-url.sh  # Get HTTPS URL
./status.sh   # Check status
./stop.sh     # Stop services
```

### Option 3: Manual Docker
```bash
docker-compose up -d
curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])"
```

## 📡 Endpoints

After starting, you'll get:
- **HTTPS MCP Endpoint**: `https://xxxxx.ngrok-free.app/mcp`
- **Local MCP Server**: `http://localhost:8000/mcp`
- **Ngrok Dashboard**: `http://localhost:4040`
- **Registry Discovery**: `http://localhost:8021`

## 🛠 Management Commands

| Command | Description |
|---------|-------------|
| `make start` | Start all services and display HTTPS URL |
| `make stop` | Stop all services |
| `make status` | Check health of all services |
| `make url` | Get current HTTPS endpoint |
| `make logs` | View service logs |
| `make clean` | Stop services and cleanup |

## 🔍 Troubleshooting

### Services not starting?
```bash
make status
make logs
```

### URL not working?
```bash
make url
docker-compose logs ngrok
```

### Reset everything:
```bash
make clean
make start
```

## 📋 Service Architecture

- **MCP Server**: Main protocol server (FastAPI)
- **Ngrok**: HTTPS tunnel provider
- **Registry Discovery**: Service discovery component

## 🔧 Configuration

- Ngrok auth token: Set in `docker-compose.yml`
- Server config: See `mcp_server_1/mcp_server.py`
- Docker config: See `docker-compose.yml`

## 📄 Protocol Compliance

This server is fully compliant with MCP Streamable HTTP protocol 2025-06-18:
- ✅ Origin header validation
- ✅ SSE streaming support
- ✅ Session management
- ✅ Event resumability
- ✅ Proper error handling
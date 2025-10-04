# MCP Gateway Startup Guide

## Quick Start (Without Ngrok)

Start all services locally:

```bash
./start.sh
```

This will start:
- ✅ MCP Server (http://localhost:8000)
- ✅ OpenSearch MCP (http://localhost:8001)
- ✅ Tools Gateway (http://localhost:8021)
- ✅ Agentic Search (http://localhost:8023)

**Note:** Ngrok is NOT started by default due to free tier limitations (max 3 tunnels, we have 4 services).

## Starting with Ngrok (Optional)

If you need public HTTPS endpoints via ngrok:

```bash
./start-ngrok.sh
```

⚠️ **Ngrok Free Tier Limitation:**
- Maximum 3 tunnels allowed
- You have 4 services available
- Edit `ngrok/ngrok.yml` to choose which 3 to expose
- Or upgrade to a paid ngrok plan

### Example: Selecting 3 Services for Ngrok

Edit `ngrok/ngrok.yml` and comment out one service:

```yaml
tunnels:
  mcp-server:
    proto: http
    addr: mcp-server:8000
    schemes: [https]

  # mcp-opensearch:  # Commented out
  #   proto: http
  #   addr: mcp-opensearch:8001
  #   schemes: [https]

  mcp-registry:
    proto: http
    addr: tools-gateway:8021
    schemes: [https]

  agentic-search:
    proto: http
    addr: agentic-search:8023
    schemes: [https]
```

## Service Endpoints

### Local Access

| Service | Port | URL | Description |
|---------|------|-----|-------------|
| MCP Server | 8000 | http://localhost:8000 | Main MCP server |
| OpenSearch MCP | 8001 | http://localhost:8001 | OpenSearch integration |
| Tools Gateway | 8021 | http://localhost:8021 | MCP tool registry |
| Agentic Search | 8023 | http://localhost:8023 | AI-powered search agent |

### Health Checks

```bash
# Check all services
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8021/health
curl http://localhost:8023/health
```

## Managing Services

### Start Services
```bash
./start.sh              # Start without ngrok
./start-ngrok.sh        # Start ngrok tunnels
```

### Stop Services
```bash
./stop.sh               # Stop all services
docker-compose stop ngrok  # Stop only ngrok
```

### View Status
```bash
./status.sh             # View service status
docker-compose ps       # Detailed container status
```

### View Logs
```bash
./logs.sh               # View all logs
docker-compose logs agentic-search  # Specific service
docker-compose logs -f  # Follow logs
```

## Manual Docker Compose Commands

### Start all services (no ngrok)
```bash
docker-compose up -d
```

### Start with ngrok
```bash
docker-compose --profile ngrok up -d
```

### Start specific services
```bash
docker-compose up -d mcp-server tools-gateway agentic-search
```

### Restart a service
```bash
docker-compose restart agentic-search
```

## Testing the Agentic Search Service

### Prerequisites
- Ollama must be running: `ollama serve`
- Required model: `ollama pull llama3.2:latest`

### Test the API

```bash
# Test health
curl http://localhost:8023/health

# Test search (requires Ollama)
curl -X POST http://localhost:8023/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what is artificial intelligence?",
    "enabled_tools": ["search_stories"],
    "session_id": "test-123"
  }'

# Access web UI
open http://localhost:8023
```

## Troubleshooting

### Ngrok fails to start
**Error:** "failed to start tunnel: Your account may not run more than 3 endpoints"

**Solution:**
1. Edit `ngrok/ngrok.yml` to enable only 3 tunnels
2. Or upgrade to ngrok paid plan
3. Or use local endpoints only

### Service not responding
```bash
# Check logs
docker-compose logs <service-name>

# Restart service
docker-compose restart <service-name>

# Rebuild and restart
docker-compose up -d --build <service-name>
```

### Agentic Search errors
**Error:** "Cannot connect to Ollama"

**Solution:**
```bash
# Start Ollama
ollama serve

# Pull required model
ollama pull llama3.2:latest
```

## Architecture

```
┌─────────────────────────────────────────┐
│  Docker Compose Network: mcp-network    │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────┐  ┌──────────────┐   │
│  │ MCP Server   │  │ OpenSearch   │   │
│  │ Port: 8000   │  │ Port: 8001   │   │
│  └──────────────┘  └──────────────┘   │
│                                         │
│  ┌──────────────┐  ┌──────────────┐   │
│  │ Tools        │  │ Agentic      │   │
│  │ Gateway      │  │ Search       │   │
│  │ Port: 8021   │  │ Port: 8023   │   │
│  └──────────────┘  └──────────────┘   │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ Ngrok (Optional - Profile)       │  │
│  │ Port: 4040 (Dashboard)           │  │
│  │ Max 3 tunnels on free tier       │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Recent Changes

### Version 2.0 - Ngrok Profile
- ✅ Ngrok moved to Docker Compose profile
- ✅ Services start without ngrok by default
- ✅ New `start-ngrok.sh` script for tunnel management
- ✅ Added Agentic Search service
- ✅ Cleaned up prompts (51% size reduction)
- ✅ Converted conversation history from XML to JSON

### Migration Notes
- Previous behavior: `./start.sh` started all services + ngrok
- New behavior: `./start.sh` starts services only (no ngrok)
- To get old behavior: Run `./start.sh && ./start-ngrok.sh`

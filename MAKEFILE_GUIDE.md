# MCP Gateway - Makefile Command Guide

Complete guide to managing MCP Gateway using `make` commands.

## Quick Reference

```bash
make start        # Start everything (services + ngrok)
make start-local  # Start without ngrok
make stop         # Stop everything
make status       # Check what's running
make help         # Show all commands
```

---

## All Available Commands

### Starting Services

#### `make start` (Default - Recommended)
Starts all services **including ngrok** tunnels.

```bash
make start
```

**What it does:**
1. Stops any existing containers
2. Starts all 4 services (mcp-server, mcp-opensearch, tools-gateway, agentic-search)
3. Starts ngrok with 3 HTTPS tunnels
4. Health checks all services
5. Displays local HTTP and HTTPS URLs

**Output:**
```
🎉 MCP Gateway is running!
=========================

📍 Local endpoints:
  🏠 MCP Server: http://localhost:8000
  🔍 OpenSearch MCP: http://localhost:8001
  🛠️  Tools Gateway: http://localhost:8021
  🤖 Agentic Search: http://localhost:8023

🌐 Ngrok HTTPS endpoints:
  🔗 mcp-registry: https://xxxxx.ngrok-free.app
  🔗 mcp-server: https://xxxxx.ngrok-free.app
  🔗 agentic-search: https://xxxxx.ngrok-free.app
  🔧 Dashboard: http://localhost:4040
```

---

#### `make start-local`
Starts services **without ngrok** (local development only).

```bash
make start-local
```

**Use when:**
- You don't need public HTTPS access
- Faster startup (no ngrok delays)
- Working locally only

**Output:**
```
🎉 MCP Gateway is running (Local Only)!
=========================
🏠 MCP Server: http://localhost:8000
🔍 OpenSearch MCP: http://localhost:8001
🛠️  Tools Gateway: http://localhost:8021
🤖 Agentic Search: http://localhost:8023

💡 To start ngrok: make start-ngrok
```

---

### Ngrok Management

#### `make start-ngrok`
Starts **only ngrok tunnels** (services must already be running).

```bash
# First start services
make start-local

# Then start ngrok
make start-ngrok
```

**Use when:**
- Services are already running
- You want to add HTTPS access later

---

#### `make stop-ngrok`
Stops **only ngrok** (keeps services running).

```bash
make stop-ngrok
```

**Use when:**
- You want to disable public access
- Keep services running locally

---

### Stopping Services

#### `make stop`
Stops **all services** including ngrok.

```bash
make stop
```

**Output:**
```
🛑 Stopping all services...
✅ All services stopped
```

---

### Monitoring

#### `make status`
Shows status of all containers.

```bash
make status
```

**Output:**
```
📊 Service Status:
==================
NAME                    STATUS              PORTS
agentic-search          Up 2 minutes        0.0.0.0:8023->8023/tcp
mcp-ngrok               Up 2 minutes        0.0.0.0:4040->4040/tcp
mcp-opensearch-server   Up 2 minutes        0.0.0.0:8001->8001/tcp
mcp-server-enhanced     Up 2 minutes        0.0.0.0:8000->8000/tcp
tools-gateway           Up 2 minutes        0.0.0.0:8021->8021/tcp
```

---

#### `make logs`
View logs from all services.

```bash
make logs

# Or view specific service
docker-compose logs agentic-search
docker-compose logs -f ngrok  # Follow logs
```

---

### Cleanup

#### `make clean`
Stops all services and cleans up Docker resources.

```bash
make clean
```

**Output:**
```
🧹 Cleaning up MCP Gateway...
✅ Cleanup complete
```

---

### Help

#### `make help`
Shows all available commands.

```bash
make help
```

---

## Common Workflows

### Workflow 1: Normal Development with Public Access

```bash
# Start everything (default)
make start

# Check if everything is running
make status

# View logs if needed
make logs

# Stop when done
make stop
```

---

### Workflow 2: Local Development Only

```bash
# Start without ngrok
make start-local

# Work locally...

# Add ngrok later if needed
make start-ngrok

# Stop everything
make stop
```

---

### Workflow 3: Restart Services

```bash
# Quick restart
make stop
make start

# Or restart specific service
docker-compose restart agentic-search
```

---

### Workflow 4: Check What's Running

```bash
# Quick status check
make status

# Detailed check
docker-compose ps

# Check specific service logs
docker-compose logs agentic-search
```

---

## Internal Commands (Advanced)

These are called automatically by other commands:

### `make _check-services`
Internal: Waits for services to be ready.

### `make _show-urls`
Internal: Displays local and ngrok URLs.

### `make _show-ngrok-urls`
Internal: Displays ngrok HTTPS URLs only.

---

## Troubleshooting

### Services Won't Start

```bash
# Check what's running
make status

# View logs
make logs

# Clean start
make clean
make start
```

### Ngrok Fails

```bash
# Check ngrok logs
docker-compose logs ngrok

# Common issue: Too many tunnels
# Solution: Edit ngrok/ngrok.yml to enable only 3 services

# Restart ngrok
make stop-ngrok
make start-ngrok
```

### Ports Already in Use

```bash
# Find what's using the port
lsof -i :8000
lsof -i :8001
lsof -i :8021
lsof -i :8023

# Stop everything
make stop

# Or kill specific process
kill -9 <PID>
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `Makefile` | All make commands and logic |
| `docker-compose.yml` | Service definitions |
| `ngrok/ngrok.yml` | Ngrok tunnel configuration |

---

## Tips

1. **Always use `make` commands** - Don't call scripts directly
2. **Check status first** - `make status` before starting
3. **View logs for errors** - `make logs` when something fails
4. **Use start-local for dev** - Faster than full start
5. **Edit ngrok.yml carefully** - Only enable 3 tunnels

---

## Migration from Scripts

**Old way:**
```bash
./start.sh
./start-ngrok.sh
./stop.sh
```

**New way:**
```bash
make start
# (ngrok included automatically)
make stop
```

---

## Summary

✅ **Default behavior:** `make start` includes ngrok
✅ **All operations:** Managed by make commands
✅ **No scripts needed:** Everything via Makefile
✅ **Clear output:** Shows URLs and status
✅ **Easy to use:** Simple, consistent commands

**Most common command:**
```bash
make start  # Does everything you need!
```

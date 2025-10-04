# MCP Gateway - Recent Changes Summary

## Overview
The MCP Gateway startup process has been updated to disable ngrok by default due to free tier limitations.

---

## What Changed

### 1. **Ngrok Disabled from Default Startup**

**Before:**
- `make start` or `./start.sh` would start all services **including ngrok**
- Ngrok would fail with "max 3 tunnels" error (we have 4 services)
- Startup would show errors and warnings

**After:**
- `make start` or `./start.sh` starts services **WITHOUT ngrok**
- Clean startup with no ngrok errors
- HTTPS URLs are NOT shown (only local HTTP URLs)
- Ngrok can be started separately when needed

---

## Current Behavior

### Starting Services

```bash
make start
# OR
./start.sh
```

**Output:**
```
🎉 MCP Gateway is running!
=========================
🏠 MCP Server: http://localhost:8000
🔍 OpenSearch MCP: http://localhost:8001
🛠️  Tools Gateway: http://localhost:8021
🤖 Agentic Search: http://localhost:8023

ℹ️  Ngrok is NOT started (free tier limited to 3 tunnels)
   To start ngrok: docker-compose --profile ngrok up -d ngrok

💡 To stop services: ./stop.sh
💡 To view status: ./status.sh
💡 To view logs: ./logs.sh
```

**Services Started:**
- ✅ MCP Server (port 8000)
- ✅ OpenSearch MCP (port 8001)
- ✅ Tools Gateway (port 8021)
- ✅ Agentic Search (port 8023)
- ❌ Ngrok (not started)

---

## Starting Ngrok (Optional)

If you need public HTTPS endpoints:

```bash
./start-ngrok.sh
# OR
make ngrok
```

**⚠️ Important:** Free ngrok tier allows max **3 tunnels**. You must choose which 3 services to expose.

### Configure Which Services to Expose

Edit `ngrok/ngrok.yml` and comment out one service:

```yaml
tunnels:
  mcp-server:
    proto: http
    addr: mcp-server:8000
    schemes: [https]

  # Comment out ONE of the services below:

  # mcp-opensearch:  # ← Disabled
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

---

## Available Commands

| Command | Description | Ngrok |
|---------|-------------|-------|
| `make start` | Start all services | ❌ No |
| `make ngrok` | Start ngrok tunnels | ✅ Yes |
| `make stop` | Stop all services | Stops both |
| `make status` | Check service status | - |
| `make logs` | View service logs | - |
| `make help` | Show available commands | - |
| `./start-ngrok.sh` | Start ngrok tunnels | ✅ Yes |
| `./kill-ngrok.sh` | Kill ngrok processes | - |
| `./get-url.sh` | Get ngrok URLs | Requires ngrok |

---

## Why This Change?

### Problem
1. Free ngrok tier supports **maximum 3 tunnels**
2. MCP Gateway has **4 services** (mcp-server, mcp-opensearch, tools-gateway, agentic-search)
3. Ngrok would fail on startup: `ERR_NGROK_324: Your account may not run more than 3 endpoints`

### Solution
1. Moved ngrok to Docker Compose **profile**
2. Default startup does not include ngrok
3. Ngrok can be started separately when needed
4. Users can choose which 3 services to expose

### Benefits
- ✅ Clean startup with no errors
- ✅ Faster development (no ngrok delays)
- ✅ Works immediately for local development
- ✅ Optional ngrok for production/public access
- ✅ Better control over exposed services

---

## Migration Guide

### If You Were Using Ngrok Before

**Old Way:**
```bash
make start  # Started everything including ngrok
```

**New Way:**
```bash
make start  # Start services (local only)
make ngrok  # Start ngrok tunnels (if needed)
```

### If You Only Used Local Endpoints

No changes needed! Everything works as before, just faster.

---

## Troubleshooting

### "make start not giving https url"

**This is expected behavior!** HTTPS URLs require ngrok, which is now optional.

**To get HTTPS URLs:**
1. Edit `ngrok/ngrok.yml` to select 3 services
2. Run `make ngrok` or `./start-ngrok.sh`
3. Check URLs with ngrok dashboard: http://localhost:4040

### "ngrok fails to start"

**Error:** `ERR_NGROK_324: max 3 endpoints`

**Solution:**
1. Edit `ngrok/ngrok.yml`
2. Comment out one service (you have 4, need to choose 3)
3. Restart ngrok: `make ngrok`

### "Cannot connect to localhost:8001 from tools-gateway"

**Solution:** Use container names instead of localhost:
- ❌ Wrong: `http://localhost:8001`
- ✅ Correct: `http://mcp-opensearch:8001`

---

## Technical Details

### Docker Compose Profiles

Ngrok is now in a profile:
```yaml
ngrok:
  profiles:
    - ngrok  # Only starts with --profile ngrok
```

**Start without ngrok:**
```bash
docker-compose up -d
```

**Start with ngrok:**
```bash
docker-compose --profile ngrok up -d
```

### Container Networking

All containers are on `mcp_gateway_mcp-network`:
- `mcp-server:8000` (172.19.0.3)
- `mcp-opensearch:8001` (172.19.0.4)
- `tools-gateway:8021` (172.19.0.2)
- `agentic-search:8023` (172.19.0.5)

**Access from host:** Use `localhost:<port>`
**Access from containers:** Use `<container-name>:<port>`

---

## File Changes

### Modified Files
- `docker-compose.yml` - Added ngrok profile
- `start.sh` - Removed ngrok startup
- `Makefile` - Updated help text, added `make ngrok`
- `get-url.sh` - Added warning about ngrok being disabled

### New Files
- `start-ngrok.sh` - Dedicated ngrok startup script
- `kill-ngrok.sh` - Ngrok cleanup script
- `STARTUP.md` - Comprehensive startup guide
- `CHANGES.md` - This file

---

## Summary

🎯 **Main Change:** Ngrok is now **optional** and **disabled by default**

✅ **Benefits:**
- Clean startup with no errors
- Works for local development immediately
- Faster startup time
- Optional ngrok when needed

📝 **Action Required:**
- No action needed for local development
- If you need HTTPS: run `make ngrok` after `make start`
- If using ngrok: edit `ngrok.yml` to select 3 services

---

Last Updated: 2025-10-04

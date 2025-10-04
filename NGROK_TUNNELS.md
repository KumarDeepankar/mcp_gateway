# Ngrok Tunnel Configuration

## Current Configuration

### Active Tunnels (3/3)

| Service | Local Port | HTTPS URL | Status |
|---------|-----------|-----------|--------|
| **mcp-server** | 8000 | https://xxxxx.ngrok-free.app | ✅ Active |
| **mcp-opensearch** | 8001 | https://xxxxx.ngrok-free.app | ✅ Active |
| **mcp-registry** | 8021 | https://xxxxx.ngrok-free.app | ✅ Active |

### Disabled Tunnels

| Service | Local Port | HTTPS URL | Status |
|---------|-----------|-----------|--------|
| **agentic-search** | 8023 | - | ❌ Disabled |

## Why Only 3 Tunnels?

Free ngrok accounts support **maximum 3 simultaneous tunnels**.

MCP Gateway has **4 services**, so you must choose which 3 to expose publicly.

## How to Change Which Services Are Exposed

### Option 1: Use Makefile Commands

```bash
# 1. Edit the configuration
nano ngrok/ngrok.yml

# 2. Restart ngrok
make stop-ngrok
make start-ngrok
```

### Option 2: Quick Service Swap

**Current Setup (mcp-opensearch enabled):**
- ✅ mcp-server
- ✅ mcp-opensearch
- ✅ mcp-registry
- ❌ agentic-search

**To Enable agentic-search Instead:**

Edit `ngrok/ngrok.yml`:

```yaml
tunnels:
  mcp-server:
    proto: http
    addr: mcp-server:8000
    schemes: [https]

  # mcp-opensearch:  # Disable this
  #   proto: http
  #   addr: mcp-opensearch:8001
  #   schemes: [https]

  mcp-registry:
    proto: http
    addr: tools-gateway:8021
    schemes: [https]

  agentic-search:    # Enable this
    proto: http
    addr: agentic-search:8023
    schemes: [https]
```

Then restart:
```bash
make stop-ngrok && make start-ngrok
```

## Recommended Configurations

### Configuration A: Development (Default)
**Best for:** General development and testing

```yaml
✅ mcp-server        # Main MCP server
✅ mcp-opensearch    # Search functionality
✅ mcp-registry      # Tool management
❌ agentic-search    # AI search (use locally)
```

### Configuration B: AI Focus
**Best for:** Working with AI search features

```yaml
✅ mcp-server        # Main MCP server
❌ mcp-opensearch    # Search (use locally)
✅ mcp-registry      # Tool management
✅ agentic-search    # AI search (public)
```

### Configuration C: Minimal
**Best for:** Basic MCP functionality

```yaml
✅ mcp-server        # Main MCP server
❌ mcp-opensearch    # Search (use locally)
✅ mcp-registry      # Tool management
❌ agentic-search    # AI search (use locally)
# Add one more service of your choice
```

## Checking Current Tunnels

### Via Dashboard
Open: http://localhost:4040

### Via Command Line

```bash
# Show all tunnels
curl -s http://localhost:4040/api/tunnels | python3 -m json.tool

# Quick view
make status
```

### Via Makefile (when starting)

```bash
make start
# Will display all active HTTPS URLs
```

## Troubleshooting

### Error: "max 3 endpoints"

**Full Error:**
```
ERR_NGROK_324: Your account may not run more than 3 endpoints
```

**Cause:** You have 4 services enabled in `ngrok.yml`

**Solution:**
1. Edit `ngrok/ngrok.yml`
2. Comment out one service (add `#` at the start of lines)
3. Restart: `make stop-ngrok && make start-ngrok`

### Tunnel Not Appearing

**Check:**
1. Is the service enabled in `ngrok.yml`? (not commented out)
2. Did you restart ngrok after editing? `make stop-ngrok && make start-ngrok`
3. Is ngrok running? `docker-compose ps | grep ngrok`

**Fix:**
```bash
# Restart ngrok
make stop-ngrok
make start-ngrok

# Check dashboard
open http://localhost:4040
```

### All Tunnels Show Same URL

**Cause:** Ngrok is still starting up

**Solution:** Wait 5-10 seconds, then check again:
```bash
sleep 10
curl -s http://localhost:4040/api/tunnels | python3 -m json.tool
```

## Upgrading Ngrok

If you need all 4 services with HTTPS:

### Ngrok Paid Plans

| Plan | Tunnels | Price |
|------|---------|-------|
| Free | 3 | $0 |
| Personal | 10 | $8/month |
| Pro | 50 | $20/month |

Visit: https://dashboard.ngrok.com/billing/choose-a-plan

### After Upgrading

1. Edit `ngrok/ngrok.yml` - enable all 4 services
2. Restart: `make stop-ngrok && make start-ngrok`
3. All services will have HTTPS URLs

## Quick Reference

```bash
# View current configuration
cat ngrok/ngrok.yml

# Edit configuration
nano ngrok/ngrok.yml

# Apply changes
make stop-ngrok && make start-ngrok

# Check what's running
curl -s http://localhost:4040/api/tunnels | python3 -m json.tool

# View dashboard
open http://localhost:4040
```

## Current Status

Run this command to see your current tunnel configuration:

```bash
curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('\nActive HTTPS Tunnels:')
print('=' * 60)
for t in data.get('tunnels', []):
    print(f'{t[\"name\"]}: {t[\"public_url\"]}')
print('=' * 60)
"
```

---

**Last Updated:** Configuration changed to enable mcp-opensearch HTTPS URL
**Active Tunnels:** mcp-server, mcp-opensearch, mcp-registry
**Disabled:** agentic-search (can be re-enabled by disabling another service)

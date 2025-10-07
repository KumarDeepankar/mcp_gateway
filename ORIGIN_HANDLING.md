# Dynamic Origin Handling - Quick Reference

## How It Works

### Client Side (agentic_search/ollama_query_agent/mcp_tool_client.py)

The MCP Tool Client now supports **dynamic origin configuration** with the following priority:

```python
1. Explicit parameter:     MCPToolClient(origin="https://custom.com")
2. Environment variable:   AGENTIC_SEARCH_ORIGIN
3. Inferred from:          AGENTIC_SEARCH_URL
4. Gateway URL fallback:   MCP_GATEWAY_URL
```

**Example Usage:**

```bash
# Option 1: Environment variables (Recommended)
export MCP_GATEWAY_URL=https://gateway.your-domain.com
export AGENTIC_SEARCH_ORIGIN=https://search.your-domain.com

# Option 2: AGENTIC_SEARCH_URL (will be used as origin)
export MCP_GATEWAY_URL=https://gateway.your-domain.com
export AGENTIC_SEARCH_URL=https://search.your-domain.com
```

### Server Side (tools_gateway/main.py)

The Tools Gateway now extracts origin from multiple sources:

```python
def extract_origin_from_request(request):
    1. Origin header              # Standard browser header
    2. X-Forwarded-Host + Proto   # Load balancer forwarded
    3. X-Original-Host            # Alternative forwarding
    4. Referer header             # Fallback
```

**Load Balancer Requirements:**

Your load balancer MUST forward these headers:
- `X-Forwarded-Host`
- `X-Forwarded-Proto`
- `X-Forwarded-For`
- `X-Original-Host` (optional)

## Deployment Scenarios

### Scenario 1: Local Development (Same Machine)

```bash
# .env file
MCP_GATEWAY_URL=http://localhost:8021
AGENTIC_SEARCH_ORIGIN=http://localhost:8023
```

Gateway config: Default (`localhost` already allowed)

### Scenario 2: Docker Compose (Internal Network)

```yaml
# docker-compose.yml
services:
  agentic-search:
    environment:
      - MCP_GATEWAY_URL=http://tools-gateway:8021
      - AGENTIC_SEARCH_ORIGIN=http://agentic-search:8023

  tools-gateway:
    # No special config needed
```

Gateway config: Add `agentic-search` to allowed origins
```bash
curl -X POST http://tools-gateway:8021/config/origin/add \
  -d '{"origin": "agentic-search"}'
```

### Scenario 3: Separate Machines (Direct Connection)

**Machine A (Agentic Search):**
```bash
MCP_GATEWAY_URL=http://machine-b:8021
AGENTIC_SEARCH_ORIGIN=http://machine-a:8023
```

**Machine B (Tools Gateway):**
```bash
# Add machine-a to allowed origins
curl -X POST http://localhost:8021/config/origin/add \
  -d '{"origin": "machine-a"}'
```

### Scenario 4: Behind Load Balancer (Production)

**Machine A (Agentic Search):**
```bash
# Internal gateway URL
MCP_GATEWAY_URL=http://gateway-internal:8021
# Public facing URL (what browser/LB sees)
AGENTIC_SEARCH_ORIGIN=https://search.your-domain.com
```

**Machine B (Tools Gateway):**
```bash
# Enable HTTPS origins (recommended for LB setups)
curl -X POST http://localhost:8021/config/origin \
  -H "Content-Type: application/json" \
  -d '{"allow_https": true}'

# Or add specific domain
curl -X POST http://localhost:8021/config/origin/add \
  -d '{"origin": "search.your-domain.com"}'
```

**Load Balancer (Nginx):**
```nginx
location / {
    proxy_pass http://backend;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### Scenario 5: Multiple Agentic Search Instances

**All Instances:**
```bash
MCP_GATEWAY_URL=http://gateway-lb:8021
AGENTIC_SEARCH_ORIGIN=https://search.your-domain.com  # Same public URL
```

**Gateway:**
```bash
# Only needs to allow one origin (the public one)
curl -X POST http://gateway:8021/config/origin/add \
  -d '{"origin": "search.your-domain.com"}'
```

## Configuration Commands

### View Current Configuration

```bash
# Get all gateway config
curl http://gateway-url:8021/config

# View just origin config
curl http://gateway-url:8021/config | jq '.origin'
```

### Add Allowed Origin

```bash
curl -X POST http://gateway-url:8021/config/origin/add \
  -H "Content-Type: application/json" \
  -d '{"origin": "new-domain.com"}'
```

### Remove Allowed Origin

```bash
curl -X POST http://gateway-url:8021/config/origin/remove \
  -H "Content-Type: application/json" \
  -d '{"origin": "old-domain.com"}'
```

### Enable All HTTPS Origins

```bash
# Useful for load balancer deployments
curl -X POST http://gateway-url:8021/config/origin \
  -H "Content-Type: application/json" \
  -d '{"allow_https": true}'
```

### Enable ngrok Domains

```bash
curl -X POST http://gateway-url:8021/config/origin \
  -H "Content-Type: application/json" \
  -d '{"allow_ngrok": true}'
```

## Testing

### Test Origin Extraction

```bash
# Test with direct Origin header
curl -X POST http://gateway-url:8021/mcp \
  -H "Origin: https://search.your-domain.com" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":"test","params":{"protocolVersion":"2025-06-18","clientInfo":{"name":"test","version":"1.0"}}}'

# Test with forwarded headers (simulating load balancer)
curl -X POST http://gateway-url:8021/mcp \
  -H "X-Forwarded-Host: search.your-domain.com" \
  -H "X-Forwarded-Proto: https" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":"test","params":{"protocolVersion":"2025-06-18","clientInfo":{"name":"test","version":"1.0"}}}'
```

### Debug Origin Issues

Check gateway logs for:
```
INFO - POST endpoint - Extracted origin: https://search.your-domain.com
DEBUG - Origin validation: hostname=search.your-domain.com, allowed={'localhost', 'search.your-domain.com'}
```

If you see:
```
WARNING - Origin validation failed for: None
```

This means origin extraction failed. Check:
1. Load balancer is forwarding headers
2. Origin header is being sent by client
3. Client has AGENTIC_SEARCH_ORIGIN set

## Migration Path

### From Hardcoded to Dynamic

**Before (hardcoded):**
```python
mcp_tool_client = MCPToolClient(
    registry_base_url="http://localhost:8021",
    origin="http://localhost:8021"
)
```

**After (dynamic):**
```python
# Uses environment variables automatically
mcp_tool_client = MCPToolClient()
```

Set environment variables:
```bash
export MCP_GATEWAY_URL=http://gateway:8021
export AGENTIC_SEARCH_ORIGIN=https://search.domain.com
```

### Zero-Downtime Migration

1. **Pre-deployment:** Add new origin to gateway
   ```bash
   curl -X POST http://gateway:8021/config/origin/add \
     -d '{"origin": "new-search.domain.com"}'
   ```

2. **Deploy:** Update agentic search with new AGENTIC_SEARCH_ORIGIN

3. **Verify:** Check logs for successful origin validation

4. **Cleanup:** Remove old origin (optional)
   ```bash
   curl -X POST http://gateway:8021/config/origin/remove \
     -d '{"origin": "old-search.domain.com"}'
   ```

## Best Practices

### Development
- Use `localhost` or `127.0.0.1` (already allowed by default)
- Keep `allow_https: false` for security

### Staging
- Add specific staging domains to allowed origins
- Test load balancer header forwarding
- Verify origin extraction in logs

### Production
- **Option A (Strict):** Explicitly list all allowed origins
  ```bash
  # Add each origin
  curl -X POST http://gateway/config/origin/add -d '{"origin": "prod.com"}'
  ```

- **Option B (Flexible):** Enable HTTPS origins for load balancers
  ```bash
  curl -X POST http://gateway/config/origin -d '{"allow_https": true}'
  ```

### Multi-Region
- Use same public domain across regions: `search.your-domain.com`
- Different internal gateway URLs per region
- Single origin configuration works for all regions

## Troubleshooting Flow

```
┌─────────────────────────────────────┐
│ Getting 403 Forbidden?              │
└──────────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ Check client logs        │
    │ MCPToolClient initialized│
    │ with gateway=? origin=?  │
    └──────────┬───────────────┘
               │
               ▼
    ┌─────────────────────────────────┐
    │ Is origin set correctly?        │
    ├─────────────────────────────────┤
    │ Should match public URL         │
    │ visible to browser/load balancer│
    └──────────┬──────────────────────┘
               │ Yes
               ▼
    ┌─────────────────────────────────┐
    │ Check gateway logs              │
    │ "Extracted origin: ..."         │
    └──────────┬──────────────────────┘
               │
               ▼
    ┌─────────────────────────────────┐
    │ Is origin extracted correctly?  │
    ├─────────────────────────────────┤
    │ NO: Load balancer not forwarding│
    │     headers properly             │
    │ YES: Continue to next step      │
    └──────────┬──────────────────────┘
               │ YES
               ▼
    ┌─────────────────────────────────┐
    │ Check allowed origins           │
    │ curl gateway/config | jq .origin│
    └──────────┬──────────────────────┘
               │
               ▼
    ┌─────────────────────────────────┐
    │ Is this origin in allowed list? │
    ├─────────────────────────────────┤
    │ NO: Add it with /config/origin/ │
    │     add endpoint                 │
    │ YES: Check allow_https setting  │
    └─────────────────────────────────┘
```

## Summary

**Key Points:**
1. Client sends origin based on environment variables (priority order applies)
2. Gateway extracts origin from headers (supports load balancers)
3. Gateway validates against allowed list or policies (HTTPS/ngrok)
4. Configuration is persistent and can be updated dynamically
5. Zero-downtime origin management via API

**Most Common Setup:**
```bash
# Client (Agentic Search)
export AGENTIC_SEARCH_ORIGIN=https://search.your-domain.com
export MCP_GATEWAY_URL=http://gateway-internal:8021

# Gateway (Tools Gateway)
curl -X POST http://gateway:8021/config/origin \
  -d '{"allow_https": true}'  # For production with load balancers
```

This configuration works for most distributed deployments with load balancers.

# Simple Deployment Guide

## Overview

Deploy MCP Gateway and Agentic Search with load balancer in 3 easy steps.

```
        Load Balancer (aertkhkkg.xyz.com)
                    ↓
        ┌───────────┴────────────┐
        ↓                        ↓
  Machine A                 Machine B
  Agentic Search          Tools Gateway
  Port: 8023              Port: 8021
```

---

## Step 1: Machine B (Tools Gateway)

### Start the Gateway

```bash
cd /path/to/mcp_gateway/tools_gateway
python main.py
```

### Add Your Domain

**Option A: Using Portal** (Recommended)
1. Open browser: `http://machine-b-ip:8021`
2. Go to **Configuration** tab
3. Add origin: `aertkhkkg.xyz.com`
4. Done! ✓

**Option B: Using Command**
```bash
curl -X POST http://localhost:8021/config/origin/add \
  -H "Content-Type: application/json" \
  -d '{"origin": "aertkhkkg.xyz.com"}'
```

### Verify

```bash
curl http://localhost:8021/config
# Should show "aertkhkkg.xyz.com" in allowed_origins
```

---

## Step 2: Machine A (Agentic Search)

### Edit .env File

```bash
cd /path/to/mcp_gateway/agentic_search
nano .env
```

Update these values:
```bash
MCP_GATEWAY_URL=http://machine-b-ip:8021
AGENTIC_SEARCH_ORIGIN=https://aertkhkkg.xyz.com
HOST=0.0.0.0
PORT=8023
```

### Start the Service

```bash
python server.py
```

---

## Step 3: Load Balancer (aertkhkkg.xyz.com)

### Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name aertkhkkg.xyz.com;

    ssl_certificate /etc/letsencrypt/live/aertkhkkg.xyz.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/aertkhkkg.xyz.com/privkey.pem;

    location / {
        proxy_pass http://machine-a-ip:8023;

        # Required headers
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Streaming support
        proxy_buffering off;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name aertkhkkg.xyz.com;
    return 301 https://$host$request_uri;
}
```

### Apply Configuration

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Get SSL Certificate

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d aertkhkkg.xyz.com
```

---

## Testing

### 1. Test DNS
```bash
nslookup aertkhkkg.xyz.com
# Should return load balancer IP
```

### 2. Test Service
```bash
curl https://aertkhkkg.xyz.com/health
# Should return {"status": "healthy"}
```

### 3. Check Gateway Logs
```bash
# On Machine B
tail -f /path/to/gateway.log | grep Origin

# Should see:
# ✓ Origin allowed (whitelist): https://aertkhkkg.xyz.com
```

---

## Configuration Summary

| Component | Configuration |
|-----------|--------------|
| **Machine A** | Edit `.env` → Run `python server.py` |
| **Machine B** | Add origin via portal or API |
| **Load Balancer** | Nginx config with SSL + headers |
| **DNS** | Point `aertkhkkg.xyz.com` to LB |

---

## Environment Files

### Machine A: `.env`
```bash
MCP_GATEWAY_URL=http://machine-b-ip:8021
AGENTIC_SEARCH_ORIGIN=https://aertkhkkg.xyz.com
HOST=0.0.0.0
PORT=8023
OLLAMA_HOST=http://localhost:11434
```

### Machine B: No file needed
Configuration stored in `gateway_config.pkl` (managed via portal/API)

---

## Troubleshooting

### 403 Forbidden Error

**Check origin is added:**
```bash
curl http://machine-b:8021/config | grep aertkhkkg
```

**Add if missing:**
```bash
curl -X POST http://machine-b:8021/config/origin/add \
  -d '{"origin": "aertkhkkg.xyz.com"}'
```

### Origin Not Detected

**Check nginx forwards headers:**
```nginx
# Must have these lines:
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
```

### Connection Refused

**Check services are running:**
```bash
# Machine A
curl http://localhost:8023/health

# Machine B
curl http://localhost:8021/health/servers
```

**Check firewall:**
```bash
# Allow ports on machines
sudo ufw allow 8023  # Machine A
sudo ufw allow 8021  # Machine B
```

---

## Docker Deployment

### Using Docker Compose

**docker-compose.yml**
```yaml
version: '3.8'

services:
  agentic-search:
    build: ./agentic_search
    ports:
      - "8023:8023"
    environment:
      - MCP_GATEWAY_URL=http://tools-gateway:8021
      - AGENTIC_SEARCH_ORIGIN=https://aertkhkkg.xyz.com
      - HOST=0.0.0.0
      - PORT=8023
    networks:
      - mcp-network

  tools-gateway:
    build: ./tools_gateway
    ports:
      - "8021:8021"
    environment:
      - HOST=0.0.0.0
      - PORT=8021
    networks:
      - mcp-network

networks:
  mcp-network:
    driver: bridge
```

**Deploy:**
```bash
docker-compose up -d
```

**Add origin:**
```bash
curl -X POST http://localhost:8021/config/origin/add \
  -d '{"origin": "aertkhkkg.xyz.com"}'
```

---

## Production Hardening

Once everything works, secure it:

```bash
# On Machine B
curl -X POST http://localhost:8021/config/origin \
  -H "Content-Type: application/json" \
  -d '{"allow_https": false, "allow_ngrok": false}'
```

This ensures only `aertkhkkg.xyz.com` is allowed (no blanket HTTPS acceptance).

---

## Quick Commands Reference

```bash
# Start services
python server.py                    # Agentic Search
python main.py                      # Tools Gateway

# Add origin
curl -X POST http://localhost:8021/config/origin/add \
  -d '{"origin": "aertkhkkg.xyz.com"}'

# Check config
curl http://localhost:8021/config

# View logs
tail -f gateway.log | grep Origin

# Reload nginx
sudo systemctl reload nginx

# Test deployment
curl https://aertkhkkg.xyz.com/health
```

---

## That's It!

Three simple steps:
1. ✅ Start gateway + add domain
2. ✅ Edit .env + start service
3. ✅ Configure load balancer

No code changes, no compilation, just configuration! 🚀

---

## Support

- **Full details**: See `DEPLOYMENT.md`
- **Security guide**: See `SECURITY.md`
- **Troubleshooting**: See `ORIGIN_HANDLING.md`
- **Test results**: See `TEST_RESULTS.md`

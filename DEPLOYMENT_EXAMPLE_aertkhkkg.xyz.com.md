# Deployment Configuration for aertkhkkg.xyz.com

## Your Architecture

```
                    ┌─────────────────────────┐
                    │  Load Balancer (LB)     │
                    │  aertkhkkg.xyz.com      │
                    │  (HTTPS/443)            │
                    └──────────┬──────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            │                                     │
    ┌───────▼────────┐                  ┌────────▼───────┐
    │ Agentic Search │                  │ Tools Gateway  │
    │  (Machine A)   │─────────────────→│  (Machine B)   │
    │  Port: 8023    │   Internal       │  Port: 8021    │
    └────────────────┘   Network         └────────────────┘
```

## Step-by-Step Configuration

### Step 1: Machine B (Tools Gateway) - Configure First

#### 1.1 Add Your Domain to Allowed Origins

```bash
# SSH to Machine B (Tools Gateway)
ssh user@machine-b

# Option A: Add specific subdomain (RECOMMENDED)
curl -X POST http://localhost:8021/config/origin/add \
  -H "Content-Type: application/json" \
  -d '{"origin": "aertkhkkg.xyz.com"}'

# Option B: If you have multiple subdomains, add them all
curl -X POST http://localhost:8021/config/origin/add \
  -H "Content-Type: application/json" \
  -d '{"origin": "search.aertkhkkg.xyz.com"}'

curl -X POST http://localhost:8021/config/origin/add \
  -H "Content-Type: application/json" \
  -d '{"origin": "api.aertkhkkg.xyz.com"}'

# Option C: For flexible deployment (recommended during initial setup)
curl -X POST http://localhost:8021/config/origin \
  -H "Content-Type: application/json" \
  -d '{"allow_https": true}'
```

#### 1.2 Verify Configuration

```bash
curl -s http://localhost:8021/config | grep -A 5 "origin"
```

Expected output:
```json
"origin": {
  "allowed_origins": ["localhost", "127.0.0.1", "0.0.0.0", "aertkhkkg.xyz.com"],
  "allow_ngrok": true,
  "allow_https": true
}
```

#### 1.3 Restart Gateway (if needed)

```bash
# If gateway is running as systemd service
sudo systemctl restart tools-gateway

# If running with screen/tmux
# Stop existing: Ctrl+C
# Restart:
cd /path/to/mcp_gateway/tools_gateway
python main.py
```

---

### Step 2: Machine A (Agentic Search) - Configure Environment Variables

#### 2.1 Create/Edit Environment File

```bash
# SSH to Machine A (Agentic Search)
ssh user@machine-a

# Navigate to agentic_search directory
cd /path/to/mcp_gateway/agentic_search

# Create .env file
cat > .env << 'EOF'
# Internal gateway URL (Machine B)
MCP_GATEWAY_URL=http://machine-b-internal-ip:8021
# Or if gateway is behind internal LB:
# MCP_GATEWAY_URL=http://gateway-internal.local:8021

# Public URL for origin validation
AGENTIC_SEARCH_ORIGIN=https://aertkhkkg.xyz.com

# Service binding
HOST=0.0.0.0
PORT=8023
EOF
```

#### 2.2 Alternative: Export Environment Variables

```bash
# If not using .env file, export directly
export MCP_GATEWAY_URL=http://machine-b-ip:8021
export AGENTIC_SEARCH_ORIGIN=https://aertkhkkg.xyz.com
export HOST=0.0.0.0
export PORT=8023
```

#### 2.3 Verify Configuration

```bash
# Check environment variables are loaded
echo "Gateway URL: $MCP_GATEWAY_URL"
echo "Origin: $AGENTIC_SEARCH_ORIGIN"
```

#### 2.4 Restart Agentic Search Service

```bash
# If running as systemd service
sudo systemctl restart agentic-search

# If running with screen/tmux
# Stop existing: Ctrl+C
# Restart:
cd /path/to/mcp_gateway/agentic_search
python server.py
```

---

### Step 3: Load Balancer Configuration

#### 3.1 Nginx Configuration

Create/edit your nginx config on the load balancer:

```nginx
# /etc/nginx/sites-available/aertkhkkg.xyz.com.conf

# Upstream for agentic search
upstream agentic_search_backend {
    server machine-a-ip:8023;
    # Add more instances for load balancing:
    # server machine-a2-ip:8023;
    # server machine-a3-ip:8023;
}

# Upstream for tools gateway
upstream tools_gateway_backend {
    server machine-b-ip:8021;
    # Add more instances for load balancing:
    # server machine-b2-ip:8021;
}

# Main application server
server {
    listen 443 ssl http2;
    server_name aertkhkkg.xyz.com;

    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/aertkhkkg.xyz.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/aertkhkkg.xyz.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Main application (agentic search)
    location / {
        proxy_pass http://agentic_search_backend;

        # CRITICAL: Forward these headers for origin validation
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Streaming support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # Optional: Separate path for gateway (if you want direct access)
    location /gateway/ {
        proxy_pass http://tools_gateway_backend/;

        # CRITICAL: Forward headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;

        # SSE support for MCP
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name aertkhkkg.xyz.com;
    return 301 https://$server_name$request_uri;
}
```

Enable the configuration:

```bash
# On load balancer machine
sudo ln -s /etc/nginx/sites-available/aertkhkkg.xyz.com.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 3.2 Alternative: AWS ALB Configuration

If using AWS Application Load Balancer:

**Target Groups:**
1. `agentic-search-tg`
   - Target: Machine A:8023
   - Protocol: HTTP
   - Health check: `/health`

2. `tools-gateway-tg`
   - Target: Machine B:8021
   - Protocol: HTTP
   - Health check: `/health/servers`

**Listener Rules:**

HTTPS:443 → aertkhkkg.xyz.com
- Default action: Forward to `agentic-search-tg`
- Stickiness: Enabled (for session persistence)

**Important ALB Settings:**
- ✅ Enable: "Preserve Host header"
- ✅ Enable: HTTP/2
- ✅ Connection idle timeout: 300 seconds
- ✅ Enable: X-Forwarded headers

---

### Step 4: DNS Configuration

Configure your DNS records:

```
# A Record
aertkhkkg.xyz.com.    A    <load-balancer-public-ip>

# Or CNAME (if using cloud LB)
aertkhkkg.xyz.com.    CNAME    your-alb-address.elb.amazonaws.com
```

---

### Step 5: SSL/TLS Certificate Setup

#### Option A: Let's Encrypt (Free)

```bash
# On load balancer machine
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d aertkhkkg.xyz.com

# Auto-renewal is configured automatically
```

#### Option B: Your Own Certificate

```bash
# Copy certificate files to load balancer
scp fullchain.pem user@load-balancer:/etc/ssl/certs/aertkhkkg.xyz.com.crt
scp privkey.pem user@load-balancer:/etc/ssl/private/aertkhkkg.xyz.com.key

# Update nginx config with paths
```

---

## Configuration Summary for aertkhkkg.xyz.com

### Machine A (Agentic Search) - Environment Variables
```bash
MCP_GATEWAY_URL=http://machine-b-ip:8021
AGENTIC_SEARCH_ORIGIN=https://aertkhkkg.xyz.com
HOST=0.0.0.0
PORT=8023
```

### Machine B (Tools Gateway) - Allowed Origins
```bash
# Add via API:
curl -X POST http://localhost:8021/config/origin/add \
  -d '{"origin": "aertkhkkg.xyz.com"}'

# Or enable all HTTPS:
curl -X POST http://localhost:8021/config/origin \
  -d '{"allow_https": true}'
```

### Load Balancer - Key Headers
```nginx
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

---

## Testing Your Deployment

### Test 1: Check DNS Resolution

```bash
nslookup aertkhkkg.xyz.com
# Should return your load balancer IP
```

### Test 2: Test SSL Certificate

```bash
curl -I https://aertkhkkg.xyz.com
# Should return 200 OK with valid SSL
```

### Test 3: Test Origin Validation

```bash
# From any machine with internet access
curl -X POST https://aertkhkkg.xyz.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test search", "session_id": "test-123"}'

# Should return search results, not 403
```

### Test 4: Check Gateway Logs

```bash
# On Machine B (Tools Gateway)
tail -f /path/to/gateway.log | grep "Origin"

# You should see:
# POST endpoint - Extracted origin: https://aertkhkkg.xyz.com
# ✓ Origin allowed (whitelist): https://aertkhkkg.xyz.com
```

### Test 5: Check Agentic Search Logs

```bash
# On Machine A (Agentic Search)
tail -f /path/to/search.log | grep "MCPToolClient"

# You should see:
# MCPToolClient initialized: gateway=http://machine-b:8021, origin=https://aertkhkkg.xyz.com
```

---

## Troubleshooting

### Issue: 403 Forbidden from Gateway

**Cause**: Origin not allowed

**Solution**:
```bash
# On Machine B
curl http://localhost:8021/config | grep allowed_origins

# If aertkhkkg.xyz.com not in list, add it:
curl -X POST http://localhost:8021/config/origin/add \
  -d '{"origin": "aertkhkkg.xyz.com"}'
```

### Issue: Origin Extracted as None

**Cause**: Load balancer not forwarding headers

**Solution**: Check nginx config has these lines:
```nginx
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
```

### Issue: SSL Certificate Errors

**Cause**: Certificate doesn't match domain

**Solution**:
```bash
# Check certificate
openssl s_client -connect aertkhkkg.xyz.com:443 -servername aertkhkkg.xyz.com | grep subject

# Should show: CN=aertkhkkg.xyz.com
```

### Issue: Connection Timeout

**Cause**: Network/firewall blocking

**Solution**:
```bash
# Check if services are accessible
curl http://machine-a-ip:8023/health
curl http://machine-b-ip:8021/health/servers

# Check firewall
sudo iptables -L -n | grep -E "8021|8023"
```

---

## Production Hardening (IMPORTANT)

Once deployed and tested, harden your security:

```bash
# On Machine B (Tools Gateway)

# 1. Disable permissive HTTPS (CRITICAL)
curl -X POST http://localhost:8021/config/origin \
  -d '{"allow_https": false}'

# 2. Disable ngrok (not needed in production)
curl -X POST http://localhost:8021/config/origin \
  -d '{"allow_ngrok": false}'

# 3. Verify only aertkhkkg.xyz.com is allowed
curl http://localhost:8021/config | grep allowed_origins

# Should show ONLY:
# ["localhost", "127.0.0.1", "0.0.0.0", "aertkhkkg.xyz.com"]
```

---

## Quick Reference Commands

### Add Your Domain
```bash
curl -X POST http://localhost:8021/config/origin/add \
  -d '{"origin": "aertkhkkg.xyz.com"}'
```

### Check Configuration
```bash
curl http://localhost:8021/config
```

### View Gateway Logs
```bash
tail -f /path/to/gateway.log | grep "Origin"
```

### Restart Services
```bash
# Agentic Search
sudo systemctl restart agentic-search

# Tools Gateway
sudo systemctl restart tools-gateway

# Nginx
sudo systemctl reload nginx
```

---

## Files to Update

### On Machine A (Agentic Search)
- ✏️ `.env` or environment variables
- ✏️ Systemd service file (if using systemd)

### On Machine B (Tools Gateway)
- ✏️ Gateway configuration (via API, no file changes needed)
- ✏️ Systemd service file (if using systemd)

### On Load Balancer
- ✏️ `/etc/nginx/sites-available/aertkhkkg.xyz.com.conf`
- ✏️ SSL certificates in `/etc/letsencrypt/live/`

---

## Success Checklist

- [ ] DNS points to load balancer IP
- [ ] SSL certificate installed and valid
- [ ] Nginx/ALB configured with X-Forwarded-* headers
- [ ] Machine A has `AGENTIC_SEARCH_ORIGIN=https://aertkhkkg.xyz.com`
- [ ] Machine B has `aertkhkkg.xyz.com` in allowed origins
- [ ] Both services can reach each other internally
- [ ] Test request returns 200, not 403
- [ ] Gateway logs show origin validation success
- [ ] Production hardening applied (allow_https: false)

---

## Support

If you encounter issues:
1. Check gateway logs: `grep "Origin" /path/to/gateway.log`
2. Verify configuration: `curl http://localhost:8021/config`
3. Test with curl: `curl -v https://aertkhkkg.xyz.com`
4. Review `SECURITY.md` for additional guidance

# Distributed Deployment Guide

## Overview

This guide explains how to deploy the MCP Gateway and Agentic Search services in a distributed environment with load balancers and across different machines.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Load Balancer (LB)                      │
│              https://your-domain.com                        │
└──────────────────┬──────────────────────┬───────────────────┘
                   │                      │
        ┌──────────▼──────────┐  ┌────────▼──────────┐
        │  Agentic Search     │  │  Tools Gateway    │
        │  (Machine A)        │  │  (Machine B)      │
        │  Port: 8023         │  │  Port: 8021       │
        └─────────────────────┘  └───────────────────┘
                   │                      │
                   └──────────┬───────────┘
                              │
                    ┌─────────▼──────────┐
                    │   MCP Tool Servers │
                    │  (Various Machines) │
                    └────────────────────┘
```

## Configuration

### 1. Agentic Search Service Configuration

The Agentic Search service needs to know:
- Where the Tools Gateway is located
- What its own public URL is (for origin validation)

#### Environment Variables

Create a `.env` file or set these environment variables on Machine A:

```bash
# Location of the Tools Gateway
MCP_GATEWAY_URL=http://machine-b:8021
# Or if gateway is behind load balancer:
# MCP_GATEWAY_URL=https://gateway.your-domain.com

# Public URL of Agentic Search (for origin validation)
AGENTIC_SEARCH_URL=https://search.your-domain.com
# Alternative: Explicitly set origin header
AGENTIC_SEARCH_ORIGIN=https://search.your-domain.com

# Service binding
HOST=0.0.0.0
PORT=8023
```

#### Docker Compose Example

```yaml
version: '3.8'
services:
  agentic-search:
    build: ./agentic_search
    environment:
      - MCP_GATEWAY_URL=http://tools-gateway:8021
      - AGENTIC_SEARCH_URL=https://search.your-domain.com
      - HOST=0.0.0.0
      - PORT=8023
    ports:
      - "8023:8023"
    networks:
      - mcp-network

networks:
  mcp-network:
    driver: bridge
```

### 2. Tools Gateway Configuration

The Tools Gateway needs to know which origins to accept.

#### Environment Variables

Create a `.env` file or set these environment variables on Machine B:

```bash
# Service binding
HOST=0.0.0.0
PORT=8021
```

#### Adding Allowed Origins

The gateway supports multiple ways to allow origins:

##### Option A: Via Configuration API (Recommended for Dynamic Setup)

```bash
# Add specific allowed origin
curl -X POST https://gateway.your-domain.com/config/origin/add \
  -H "Content-Type: application/json" \
  -d '{"origin": "search.your-domain.com"}'

# Enable all HTTPS origins (for load balancer deployments)
curl -X POST https://gateway.your-domain.com/config/origin \
  -H "Content-Type: application/json" \
  -d '{"allow_https": true}'

# Enable ngrok domains
curl -X POST https://gateway.your-domain.com/config/origin \
  -H "Content-Type: application/json" \
  -d '{"allow_ngrok": true}'
```

##### Option B: Pre-configure in config.py

Edit `/tools_gateway/config.py`:

```python
class OriginConfig(BaseModel):
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "search.your-domain.com",  # Add your domains
            "api.your-domain.com"
        ],
        description="List of allowed origins/hostnames"
    )
    allow_ngrok: bool = Field(default=True)
    allow_https: bool = Field(default=True)  # Allow all HTTPS for LB
```

### 3. Load Balancer Configuration

#### Nginx Configuration

```nginx
# Agentic Search upstream
upstream agentic_search {
    server machine-a:8023;
    # Add more instances for load balancing:
    # server machine-a2:8023;
    # server machine-a3:8023;
}

# Tools Gateway upstream
upstream tools_gateway {
    server machine-b:8021;
    # Add more instances for load balancing:
    # server machine-b2:8021;
}

# Agentic Search
server {
    listen 443 ssl http2;
    server_name search.your-domain.com;

    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;

    location / {
        proxy_pass http://agentic_search;

        # Important: Forward origin headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Original-Host $host;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Streaming support
        proxy_buffering off;
        proxy_cache off;
    }
}

# Tools Gateway
server {
    listen 443 ssl http2;
    server_name gateway.your-domain.com;

    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;

    location / {
        proxy_pass http://tools_gateway;

        # Important: Forward origin headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Original-Host $host;

        # SSE support
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

#### AWS Application Load Balancer (ALB)

**Target Groups:**
- `agentic-search-tg`: Points to Machine A:8023
- `tools-gateway-tg`: Points to Machine B:8021

**Listener Rules:**

1. HTTPS:443 - Host: search.your-domain.com
   - Forward to: agentic-search-tg
   - Stickiness: Enabled (for session persistence)

2. HTTPS:443 - Host: gateway.your-domain.com
   - Forward to: tools-gateway-tg
   - Stickiness: Enabled (for MCP sessions)

**Important ALB Settings:**
- Enable HTTP/2
- Connection idle timeout: 300s (for long-polling/SSE)
- Preserve Host header: Enabled

### 4. Kubernetes Deployment

#### ConfigMap for Environment Variables

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-config
data:
  MCP_GATEWAY_URL: "http://tools-gateway-service:8021"
  AGENTIC_SEARCH_URL: "https://search.your-domain.com"
```

#### Agentic Search Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentic-search
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentic-search
  template:
    metadata:
      labels:
        app: agentic-search
    spec:
      containers:
      - name: agentic-search
        image: your-registry/agentic-search:latest
        ports:
        - containerPort: 8023
        envFrom:
        - configMapRef:
            name: mcp-config
        env:
        - name: HOST
          value: "0.0.0.0"
        - name: PORT
          value: "8023"
---
apiVersion: v1
kind: Service
metadata:
  name: agentic-search-service
spec:
  selector:
    app: agentic-search
  ports:
  - protocol: TCP
    port: 8023
    targetPort: 8023
  type: ClusterIP
```

#### Tools Gateway Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tools-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: tools-gateway
  template:
    metadata:
      labels:
        app: tools-gateway
    spec:
      containers:
      - name: tools-gateway
        image: your-registry/tools-gateway:latest
        ports:
        - containerPort: 8021
        env:
        - name: HOST
          value: "0.0.0.0"
        - name: PORT
          value: "8021"
---
apiVersion: v1
kind: Service
metadata:
  name: tools-gateway-service
spec:
  selector:
    app: tools-gateway
  ports:
  - protocol: TCP
    port: 8021
    targetPort: 8021
  type: ClusterIP
```

#### Ingress Configuration

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-buffering: "off"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "86400"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - search.your-domain.com
    - gateway.your-domain.com
    secretName: mcp-tls-secret
  rules:
  - host: search.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: agentic-search-service
            port:
              number: 8023
  - host: gateway.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: tools-gateway-service
            port:
              number: 8021
```

## Origin Validation Flow

### How It Works

1. **Client Request**: Browser/Client sends request to Agentic Search
   ```
   GET https://search.your-domain.com/search
   ```

2. **Agentic Search → Tools Gateway**: Makes MCP request with Origin header
   ```http
   POST http://machine-b:8021/mcp
   Origin: https://search.your-domain.com
   Content-Type: application/json
   ```

3. **Load Balancer → Gateway**: If gateway is behind LB, headers are forwarded
   ```http
   POST /mcp
   X-Forwarded-Host: gateway.your-domain.com
   X-Forwarded-Proto: https
   X-Original-Host: gateway.your-domain.com
   Origin: https://search.your-domain.com
   ```

4. **Gateway Validation**: Gateway extracts and validates origin
   - Checks `Origin` header first
   - Falls back to `X-Forwarded-Host` + `X-Forwarded-Proto`
   - Validates against allowed origins list
   - If `allow_https=true`, accepts any HTTPS origin

### Dynamic Origin Registration

For truly dynamic environments where origins change frequently:

```python
# In your deployment script or init container
import requests

# Register origin after deployment
response = requests.post(
    "https://gateway.your-domain.com/config/origin/add",
    json={"origin": "new-instance.your-domain.com"}
)
```

## Testing

### 1. Test Origin Validation

```bash
# Should succeed (valid origin)
curl -X POST https://gateway.your-domain.com/mcp \
  -H "Origin: https://search.your-domain.com" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":"test"}'

# Should fail (invalid origin)
curl -X POST https://gateway.your-domain.com/mcp \
  -H "Origin: https://malicious-site.com" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 2. Check Configuration

```bash
# Get current gateway configuration
curl https://gateway.your-domain.com/config

# Get server health status
curl https://gateway.your-domain.com/health/servers
```

### 3. Test End-to-End

```bash
# Test from agentic search
curl -X POST https://search.your-domain.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test search", "session_id": "test-123"}'
```

## Monitoring

### Key Metrics to Monitor

1. **Origin Validation Failures**
   - Log pattern: `"Origin validation failed for:"`
   - Alert if rate exceeds threshold

2. **Gateway Health**
   ```bash
   curl https://gateway.your-domain.com/health/servers
   ```

3. **MCP Session Activity**
   - Monitor session creation/termination
   - Track active sessions count

### Logging

Both services log origin validation:

```
INFO - MCPToolClient initialized: gateway=https://gateway.your-domain.com, origin=https://search.your-domain.com
INFO - POST endpoint - Extracted origin: https://search.your-domain.com
DEBUG - Origin validation: hostname=search.your-domain.com, allowed={'localhost', '127.0.0.1', 'search.your-domain.com'}
```

## Security Best Practices

1. **Restrict allowed_origins in production**
   - Don't use `allow_https: true` if you can enumerate origins
   - Explicitly list allowed domains

2. **Use HTTPS everywhere**
   - Enforce TLS/SSL on load balancers
   - Set `allow_https: true` only if necessary

3. **Network Isolation**
   - Keep MCP Tool Servers in private network
   - Only expose Gateway and Search services publicly

4. **Rate Limiting**
   - Implement rate limiting at load balancer level
   - Monitor for abuse patterns

5. **Regular Origin Audit**
   ```bash
   # Review allowed origins
   curl https://gateway.your-domain.com/config | jq '.origin'
   ```

## Troubleshooting

### Issue: 403 Forbidden Errors

**Symptoms**: Agentic Search gets 403 when calling gateway

**Solutions**:
1. Check origin is set correctly:
   ```bash
   # In agentic search container
   echo $AGENTIC_SEARCH_ORIGIN
   ```

2. Verify origin is allowed in gateway:
   ```bash
   curl https://gateway.your-domain.com/config | jq '.origin.allowed_origins'
   ```

3. Check load balancer is forwarding headers:
   - Enable X-Forwarded-* headers
   - Verify Origin header is preserved

4. Enable debug logging:
   ```python
   # In tools_gateway/main.py
   logging.basicConfig(level=logging.DEBUG)
   ```

### Issue: Origin Not Detected Behind Load Balancer

**Symptoms**: Gateway logs show "Origin validation failed" with `None` origin

**Solutions**:
1. Configure load balancer to forward headers:
   - `X-Forwarded-Host`
   - `X-Forwarded-Proto`
   - `X-Forwarded-For`

2. Check Nginx configuration includes:
   ```nginx
   proxy_set_header X-Forwarded-Host $host;
   proxy_set_header X-Forwarded-Proto $scheme;
   ```

3. For ALB, enable "Preserve Host header"

### Issue: Environment Variables Not Loading

**Symptoms**: Client uses default localhost URLs

**Solutions**:
1. Verify `.env` file location (same directory as script)
2. Use explicit environment variables in Docker/K8s
3. Check variable names match exactly (case-sensitive)
4. Restart services after changing environment variables

## Migration Checklist

- [ ] Set up load balancer with SSL certificates
- [ ] Configure DNS for search.your-domain.com and gateway.your-domain.com
- [ ] Deploy Tools Gateway with environment variables
- [ ] Add allowed origins to gateway configuration
- [ ] Deploy Agentic Search with MCP_GATEWAY_URL and AGENTIC_SEARCH_URL
- [ ] Configure load balancer to forward X-Forwarded-* headers
- [ ] Test origin validation end-to-end
- [ ] Set up monitoring and alerting
- [ ] Document your specific origin list for team reference
- [ ] Create runbook for adding/removing origins dynamically

## Support

For issues or questions:
1. Check logs for origin validation messages
2. Verify configuration with `/config` endpoint
3. Test with curl commands from this guide
4. Review security settings if using `allow_https: true`

# Security Guide - MCP Gateway

## ⚠️ Current Security Posture

### Development Mode (CURRENT)
The gateway is currently configured for **MAXIMUM FLEXIBILITY** for development/testing:

```python
allow_ngrok: bool = True   # ⚠️ Any ngrok domain accepted
allow_https: bool = True   # ⚠️ ANY HTTPS origin accepted
```

**⚠️ WARNING**: This configuration is **NOT PRODUCTION READY**

---

## 🔒 Production Security Hardening

### Critical: Disable Permissive Modes

#### Step 1: Disable allow_https

```bash
# Disable blanket HTTPS acceptance
curl -X POST http://gateway:8021/config/origin \
  -H "Content-Type: application/json" \
  -d '{"allow_https": false}'
```

**Why**: `allow_https: true` means **ANY** HTTPS domain (including attacker-owned) can access your gateway.

**Attack Example**:
```bash
# Attacker registers evil-domain.com and gets HTTPS cert
curl -X POST https://your-gateway.com/mcp \
  -H "Origin: https://evil-domain.com" \
  # ✓ Would be accepted with allow_https: true!
```

#### Step 2: Disable allow_ngrok (Production Only)

```bash
# Disable ngrok domains
curl -X POST http://gateway:8021/config/origin \
  -H "Content-Type: application/json" \
  -d '{"allow_ngrok": false}'
```

**Why**: Free ngrok tunnels can be created by anyone. An attacker could:
1. Create free ngrok tunnel
2. Point it to their malicious service
3. Use that ngrok domain as Origin

**When to Keep Enabled**: Development, staging, demo environments with ngrok

#### Step 3: Explicit Allowlist

```bash
# Add only YOUR domains
curl -X POST http://gateway:8021/config/origin/add \
  -H "Content-Type: application/json" \
  -d '{"origin": "search.your-domain.com"}'

curl -X POST http://gateway:8021/config/origin/add \
  -H "Content-Type: application/json" \
  -d '{"origin": "api.your-domain.com"}'
```

### Security Validation Added

✅ **Input Sanitization** (`config.py:115-144`)
- Length validation (max 253 chars - DNS limit)
- Character whitelist (alphanumeric, dots, hyphens only)
- Injection pattern detection
- Normalization to lowercase

✅ **Origin Extraction Hardening** (`main.py:227-265`)
- URL parsing validation
- Scheme restriction (http/https only)
- Hostname extraction and validation
- Clean reconstruction (strips path/query)

✅ **Security Logging** (`main.py:302-351`)
- All validation decisions logged with severity
- ✓ Whitelist matches logged as INFO
- ⚠ Permissive matches logged as WARNING
- ✗ Rejections logged as ERROR

✅ **Removed Referer Fallback** (`main.py:267-300`)
- Referer header is trivially spoofed
- Not used for origin extraction anymore

---

## 🎯 Security Configurations by Environment

### Local Development
```bash
# Default settings work fine
# allow_ngrok: true ✓ (for testing)
# allow_https: true ✓ (for testing)
# allowed_origins: [localhost, 127.0.0.1]
```

### Staging/QA
```bash
# Disable blanket HTTPS
curl -X POST https://gateway-staging.com/config/origin \
  -d '{"allow_https": false}'

# Keep ngrok enabled for demo/testing
curl -X POST https://gateway-staging.com/config/origin \
  -d '{"allow_ngrok": true}'

# Add staging domains
curl -X POST https://gateway-staging.com/config/origin/add \
  -d '{"origin": "search-staging.your-domain.com"}'
```

### Production
```bash
# CRITICAL: Disable all permissive modes
curl -X POST https://gateway.your-domain.com/config/origin \
  -d '{"allow_https": false, "allow_ngrok": false}'

# Add ONLY production domains
curl -X POST https://gateway.your-domain.com/config/origin/add \
  -d '{"origin": "search.your-domain.com"}'

curl -X POST https://gateway.your-domain.com/config/origin/add \
  -d '{"origin": "api.your-domain.com"}'

# Verify configuration
curl https://gateway.your-domain.com/config | jq '.origin'
```

**Expected Output**:
```json
{
  "allowed_origins": ["localhost", "127.0.0.1", "search.your-domain.com", "api.your-domain.com"],
  "allow_ngrok": false,
  "allow_https": false
}
```

---

## 🛡️ Attack Scenarios & Mitigations

### 1. DNS Rebinding Attack

**Attack**:
1. Attacker controls `evil.com`
2. DNS initially points to attacker's IP
3. User visits evil.com, which makes request to your gateway
4. Attacker changes DNS to point to internal IP (e.g., 192.168.1.1)
5. Browser reuses connection, now targeting internal service

**Mitigation**: ✅ Origin validation prevents this
- Even if DNS changes, Origin header stays `evil.com`
- Gateway rejects because `evil.com` not in allowlist

### 2. Origin Spoofing via Proxy

**Attack**:
1. Attacker sets up malicious proxy
2. Proxy adds fake `Origin` header
3. Attempts to bypass validation

**Mitigation**: ✅ Multiple layers
- Only accept requests from trusted load balancers
- Use TLS/mTLS between services
- Validate X-Forwarded-* headers source

**Production Setup**:
```nginx
# In nginx (trusted LB)
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Proto $scheme;

# Block direct access to gateway
server {
    listen 8021;
    deny all;  # Only accessible from internal network
}
```

### 3. Wildcard HTTPS Acceptance

**Attack** (when `allow_https: true`):
1. Attacker gets free HTTPS cert from Let's Encrypt
2. Uses their domain with your gateway
3. Gateway accepts because "it's HTTPS"

**Mitigation**: ✅ Disable `allow_https` in production
```bash
curl -X POST http://gateway/config/origin -d '{"allow_https": false}'
```

### 4. Ngrok Tunnel Abuse

**Attack** (when `allow_ngrok: true`):
1. Attacker creates free ngrok tunnel: `abc123.ngrok-free.app`
2. Uses as Origin header
3. Gateway accepts because ngrok is allowed

**Mitigation**: ✅ Disable `allow_ngrok` in production
```bash
curl -X POST http://gateway/config/origin -d '{"allow_ngrok": false}'
```

### 5. Origin Injection

**Attack**:
```bash
curl -X POST http://gateway/config/origin/add \
  -d '{"origin": "evil.com; DROP TABLE users;--"}'
```

**Mitigation**: ✅ Input validation (`config.py:115-144`)
- Character whitelist blocks special characters
- Pattern detection blocks SQL-like syntax
- Length limits prevent buffer attacks

### 6. Header Injection via Load Balancer

**Attack**:
1. Attacker sends malicious `X-Forwarded-Host` header
2. Misconfigured LB forwards it
3. Gateway trusts it

**Mitigation**: ✅ Multiple protections
- Origin sanitization validates URL format
- Scheme validation (http/https only)
- Hostname length limits
- Network isolation (gateway not public)

**Production LB Config**:
```nginx
# Strip any X-Forwarded-* from client
proxy_set_header X-Forwarded-Host $host;  # Overwrite, don't append
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $remote_addr;
```

---

## 🔍 Security Monitoring

### Critical Logs to Monitor

#### 1. Permissive Origin Warnings
```
⚠ Allowing HTTPS origin (SECURITY: any HTTPS domain accepted): https://unknown.com
⚠ Allowing ngrok origin (SECURITY: disable for production): https://xyz.ngrok-free.app
```

**Action**: If seen in production → immediate security incident
```bash
# Emergency: Disable permissive modes
curl -X POST http://gateway/config/origin \
  -d '{"allow_https": false, "allow_ngrok": false}'
```

#### 2. Origin Rejections
```
✗ Origin REJECTED: https://evil.com (hostname: evil.com)
```

**Action**: Investigate if rate increases
- Could be attack attempt
- Could be misconfigured client

#### 3. Invalid Origin Formats
```
Origin validation failed: No hostname in javascript://alert(1)
Rejected invalid origin format: ../../../etc/passwd
```

**Action**: Security alert - likely attack attempt

### Monitoring Setup

**Prometheus/Grafana**:
```python
# Add to main.py
from prometheus_client import Counter

origin_rejected = Counter('origin_rejected_total', 'Origins rejected')
origin_allowed_permissive = Counter('origin_allowed_permissive_total', 'Origins allowed via permissive rules')

# In validate_origin_header():
if allow_https and parsed.scheme == 'https':
    origin_allowed_permissive.inc()
```

**Alert Rules**:
```yaml
# alerts.yml
- alert: PermissiveOriginInProduction
  expr: origin_allowed_permissive_total > 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Production gateway accepting permissive origins"

- alert: HighOriginRejectionRate
  expr: rate(origin_rejected_total[5m]) > 10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High rate of origin rejections - possible attack"
```

---

## 🔐 Additional Security Measures

### 1. Network-Level Security

**Internal Gateway** (Recommended):
```yaml
# Docker network isolation
networks:
  frontend:
    # Public-facing services
  backend:
    internal: true  # Gateway only accessible from backend network

services:
  agentic-search:
    networks:
      - frontend
      - backend

  tools-gateway:
    networks:
      - backend  # Not exposed to internet
```

**Firewall Rules**:
```bash
# Only allow gateway access from known IPs
iptables -A INPUT -p tcp --dport 8021 -s 10.0.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 8021 -j DROP
```

### 2. Rate Limiting

```python
# Add to main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/mcp")
@limiter.limit("100/minute")  # 100 requests per minute per IP
async def mcp_post_endpoint(...):
    ...
```

### 3. Authentication (Future Enhancement)

For additional security, consider adding:
```python
# API key authentication
@app.post("/mcp")
async def mcp_post_endpoint(
    request: Request,
    x_api_key: str = Header(None)
):
    if not verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
```

### 4. TLS/mTLS Between Services

```yaml
# Mutual TLS between agentic_search and gateway
agentic_search:
  environment:
    - MCP_GATEWAY_URL=https://gateway:8021
    - MCP_CLIENT_CERT=/certs/client.crt
    - MCP_CLIENT_KEY=/certs/client.key
    - MCP_CA_CERT=/certs/ca.crt
```

### 5. Request Size Limits

```python
# Add to main.py
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["gateway.your-domain.com", "localhost"]
)

# Limit request body size
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 1_000_000:  # 1MB
        raise HTTPException(status_code=413, detail="Request too large")
    return await call_next(request)
```

---

## ✅ Security Checklist

### Pre-Production Checklist

- [ ] `allow_https: false` configured
- [ ] `allow_ngrok: false` configured
- [ ] Only production domains in allowed_origins
- [ ] Gateway not directly accessible from internet
- [ ] Load balancer configured to strip client X-Forwarded-* headers
- [ ] Load balancer configured to set X-Forwarded-* headers
- [ ] TLS/HTTPS enabled on all public endpoints
- [ ] Rate limiting configured
- [ ] Monitoring/alerting set up for origin rejections
- [ ] Firewall rules restrict gateway access
- [ ] Security logs reviewed and understood
- [ ] Incident response plan documented

### Regular Security Review

**Weekly**:
- [ ] Review origin rejection logs
- [ ] Check for permissive origin warnings
- [ ] Verify allowed_origins list is current

**Monthly**:
- [ ] Review and prune allowed_origins
- [ ] Test origin validation with malicious inputs
- [ ] Verify security configuration hasn't drifted

**Quarterly**:
- [ ] Penetration testing
- [ ] Security audit of origin validation logic
- [ ] Review and update incident response plan

---

## 🚨 Incident Response

### If Suspicious Origins Detected

1. **Immediate**:
   ```bash
   # Review current config
   curl http://gateway/config

   # Check recent logs
   journalctl -u tools-gateway -n 1000 | grep "Origin"
   ```

2. **If Compromised**:
   ```bash
   # Emergency lockdown
   curl -X POST http://gateway/config/origin \
     -d '{"allow_https": false, "allow_ngrok": false}'

   # Clear all origins except localhost
   curl http://gateway/config | jq '.origin.allowed_origins[]' | while read origin; do
     if [[ "$origin" != "localhost" && "$origin" != "127.0.0.1" ]]; then
       curl -X POST http://gateway/config/origin/remove -d "{\"origin\": $origin}"
     fi
   done
   ```

3. **Investigation**:
   - Review all gateway access logs
   - Check for unauthorized MCP tool executions
   - Review recent configuration changes
   - Identify compromised credentials/tokens

4. **Recovery**:
   - Rotate all API keys/secrets
   - Re-add legitimate origins one by one
   - Deploy patched version
   - Resume normal operations

---

## 📖 Security Best Practices Summary

### DO ✅
- Keep `allow_https: false` in production
- Keep `allow_ngrok: false` in production
- Use explicit origin allowlist
- Monitor origin rejection logs
- Isolate gateway network access
- Use TLS everywhere
- Implement rate limiting
- Regular security reviews

### DON'T ❌
- Don't use `allow_https: true` in production
- Don't expose gateway directly to internet
- Don't trust Referer header
- Don't skip origin validation
- Don't ignore security warnings in logs
- Don't add origins without validation
- Don't reuse development config in production

---

## 🔗 Related Documentation

- `DEPLOYMENT.md` - Deployment configurations
- `ORIGIN_HANDLING.md` - Origin handling mechanics
- `CHANGES_SUMMARY.md` - Implementation details

## 📞 Security Contact

For security issues:
1. Review this document
2. Check logs for details
3. Follow incident response procedures
4. Document findings and remediations

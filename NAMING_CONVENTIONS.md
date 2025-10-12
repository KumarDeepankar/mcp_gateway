# Authentication Naming Conventions

This document describes the naming conventions used in the authentication system to clearly distinguish between modern (RS256/JWKS) and legacy (HS256) implementations.

## Naming Philosophy

Function and variable names should clearly indicate:
1. **Algorithm**: RS256 (asymmetric) vs HS256 (symmetric)
2. **Purpose**: What the function does
3. **Status**: Modern vs Legacy/Deprecated

## Global Variables

### Modern (RS256/JWKS)
```python
_JWKS_CACHE: Dict[str, Any]  # Cache for JWKS public keys
```
- Clear purpose: JWKS caching
- Industry standard approach

### Legacy (HS256 - Deprecated)
```python
_LEGACY_HS256_CONFIG: Dict[str, Any]  # Legacy symmetric key config
```
- Clearly marked as "legacy"
- Indicates HS256 algorithm
- Deprecated status obvious

## Functions

### Modern (RS256/JWKS)

#### agentic_search/auth.py
```python
fetch_jwks_from_gateway()  # Fetch JWKS public keys
_jwks_to_public_key()      # Convert JWKS to PEM format
```
- Clear that they work with JWKS
- No confusion with legacy functions

#### tools_gateway/config.py
```python
generate_rsa_keys()  # Generate RSA key pair
get_jwks()           # Get JWKS formatted public keys
```
- RSA/JWKS clearly indicated in name

#### tools_gateway/auth.py
```python
_initialize_jwt_manager()  # Initialize JWT manager (auto-detects RS256 or HS256)
```
- Descriptive name: "initialize" instead of generic "get"
- Automatically selects algorithm based on config

### Legacy (HS256 - Deprecated)

#### agentic_search/auth.py
```python
fetch_legacy_hs256_config()  # Fetch legacy HS256 symmetric secret
_get_legacy_hs256_config()   # Get legacy HS256 config with fallback
```
- "legacy" clearly indicates deprecated status
- "hs256" indicates algorithm
- Easy to identify for future removal

### Algorithm-Agnostic (Used by both)

```python
validate_jwt(token)          # Validates any JWT (tries RS256 first, falls back to HS256)
get_jwt_token(request)       # Extracts JWT from request (algorithm-agnostic)
create_session(user, token)  # Session management (algorithm-agnostic)
```
- Generic names for functions that work with any JWT
- Internal implementation handles both algorithms

## Comments and Docstrings

### Modern Functions
```python
def fetch_jwks_from_gateway():
    """
    Fetch JWKS (JSON Web Key Set) from tools_gateway.
    This is the industry-standard way to get public keys for JWT validation (RS256).
    """
```
- Emphasis on "industry standard"
- Reference to RS256

### Legacy Functions
```python
def fetch_legacy_hs256_config():
    """
    Fetch legacy HS256 JWT configuration from tools_gateway.

    DEPRECATED: This is for backward compatibility with HS256 symmetric keys.
    New implementations should use fetch_jwks_from_gateway() for RS256.
    """
```
- "DEPRECATED" prominently displayed
- Suggests modern alternative
- Clear about backward compatibility purpose

## Configuration Endpoints

### Modern (RS256/JWKS)
```
GET  /.well-known/jwks.json          # Industry standard JWKS endpoint
POST /config/jwt/generate-rsa-keys   # Generate new RSA key pair
```
- Standard JWKS path (RFC 7517)
- "rsa" in endpoint name

### Legacy (HS256)
```
GET /config/jwt  # Legacy JWT config (marked as deprecated in response)
```
- Generic path (predates JWKS implementation)
- Returns deprecation warning in JSON response

## Log Messages

### Modern
```
"Fetching JWKS from gateway..."
"✓ JWKS fetched successfully (RS256 ready)"
"Token validated successfully with RS256 (kid: {kid})"
```
- Mentions JWKS or RS256
- Indicates kid (key ID)

### Legacy
```
"Fetching legacy HS256 config from gateway..."
"Falling back to HS256 validation (legacy)"
"JWTManager using HS256 (deprecated)"
```
- "legacy" or "deprecated" in message
- Clear about HS256 usage

## Migration Path

The naming makes it easy to:
1. **Identify legacy code**: Search for "legacy" or "hs256" in function names
2. **Find modern equivalents**: Clear pairing (e.g., `fetch_legacy_hs256_config` vs `fetch_jwks_from_gateway`)
3. **Plan removal**: All legacy functions clearly marked for future deprecation

## Examples

### Good Naming
```python
# Clear what algorithm is being used
fetch_jwks_from_gateway()           # RS256
fetch_legacy_hs256_config()         # HS256

# Clear about purpose
_jwks_to_public_key()               # Converts JWKS to PEM
_initialize_jwt_manager()           # Creates JWT manager
```

### Avoid (Old Pattern)
```python
# Ambiguous - which algorithm?
fetch_jwt_config()     # ❌ Unclear
get_jwt_manager()      # ❌ Generic

# Better
fetch_legacy_hs256_config()  # ✅ Clear
_initialize_jwt_manager()    # ✅ Descriptive
```

## Summary

| Aspect | Modern (RS256/JWKS) | Legacy (HS256) |
|--------|---------------------|----------------|
| **Variables** | `_JWKS_CACHE` | `_LEGACY_HS256_CONFIG` |
| **Functions** | `fetch_jwks_from_gateway()` | `fetch_legacy_hs256_config()` |
| **Endpoints** | `/.well-known/jwks.json` | `/config/jwt` (deprecated) |
| **Keywords** | "jwks", "rs256", "rsa" | "legacy", "hs256", "deprecated" |
| **Status** | Active, recommended | Backward compatibility only |

This naming convention makes the codebase self-documenting and easier to maintain!

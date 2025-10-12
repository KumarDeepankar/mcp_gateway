#!/usr/bin/env python3
"""
Test RS256-only JWT implementation (legacy HS256 removed)
"""
import sys
import httpx
import json
from jose import jwt
from datetime import datetime, timedelta


def test_1_jwks_endpoint():
    """Test 1: Verify JWKS endpoint returns valid RS256 public key"""
    print("\n" + "="*60)
    print("TEST 1: JWKS Endpoint")
    print("="*60)

    try:
        response = httpx.get("http://localhost:8021/.well-known/jwks.json", timeout=5.0)

        if response.status_code == 200:
            jwks = response.json()

            # Validate JWKS structure
            assert "keys" in jwks, "JWKS missing 'keys' field"
            assert len(jwks["keys"]) > 0, "JWKS has no keys"

            key = jwks["keys"][0]

            # Validate key structure
            assert key["kty"] == "RSA", f"Expected RSA key, got {key['kty']}"
            assert key["use"] == "sig", f"Expected 'sig' use, got {key['use']}"
            assert key["alg"] == "RS256", f"Expected RS256, got {key['alg']}"
            assert "kid" in key, "Key missing 'kid' field"
            assert "n" in key, "Key missing 'n' (modulus)"
            assert "e" in key, "Key missing 'e' (exponent)"

            print(f"✓ JWKS endpoint working correctly")
            print(f"  - Key ID (kid): {key['kid']}")
            print(f"  - Algorithm: {key['alg']}")
            print(f"  - Key Type: {key['kty']}")
            print(f"  - Use: {key['use']}")

            return True, key["kid"]
        else:
            print(f"✗ JWKS endpoint returned {response.status_code}")
            return False, None

    except Exception as e:
        print(f"✗ JWKS endpoint test failed: {e}")
        return False, None


def test_2_create_rs256_token():
    """Test 2: Create RS256 JWT token and verify kid header"""
    print("\n" + "="*60)
    print("TEST 2: Create RS256 Token")
    print("="*60)

    try:
        # Login to get token using local auth
        response = httpx.post(
            "http://localhost:8021/auth/login/local",
            json={"email": "admin", "password": "admin"},
            timeout=5.0
        )

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")

            if not token:
                print("✗ No access_token in response")
                return False, None

            # Decode header without verification
            header = jwt.get_unverified_header(token)
            payload = jwt.get_unverified_claims(token)

            # Verify RS256 algorithm
            assert header.get("alg") == "RS256", f"Expected RS256, got {header.get('alg')}"
            assert "kid" in header, "Token missing 'kid' header (required for JWKS)"

            print(f"✓ RS256 token created successfully")
            print(f"  - Algorithm: {header['alg']}")
            print(f"  - Key ID (kid): {header['kid']}")
            print(f"  - Subject: {payload.get('sub')}")
            print(f"  - Email: {payload.get('email')}")
            print(f"  - Provider: {payload.get('provider')}")
            print(f"  - Expires: {datetime.fromtimestamp(payload.get('exp')).isoformat()}")

            return True, token
        else:
            print(f"✗ Login failed with status {response.status_code}")
            return False, None

    except Exception as e:
        print(f"✗ Token creation test failed: {e}")
        return False, None


def test_3_agentic_search_validation():
    """Test 3: Verify agentic_search can validate RS256 token using JWKS"""
    print("\n" + "="*60)
    print("TEST 3: Agentic Search Token Validation")
    print("="*60)

    try:
        # Import agentic_search auth module
        sys.path.insert(0, '/Users/deepankar/Documents/mcp_gateway')
        from agentic_search.auth import validate_jwt, fetch_jwks_from_gateway

        # Fetch JWKS
        print("  Fetching JWKS from gateway...")
        jwks_success = fetch_jwks_from_gateway()

        if not jwks_success:
            print("✗ Failed to fetch JWKS")
            return False

        print("  ✓ JWKS fetched successfully")

        # Get token using local auth
        response = httpx.post(
            "http://localhost:8021/auth/login/local",
            json={"email": "admin", "password": "admin"},
            timeout=5.0
        )

        if response.status_code != 200:
            print(f"✗ Login failed with status {response.status_code}")
            return False

        token = response.json().get("access_token")

        # Validate token
        print("  Validating RS256 token...")
        payload = validate_jwt(token)

        if payload:
            print(f"✓ Token validated successfully")
            print(f"  - Email: {payload.get('email')}")
            print(f"  - Provider: {payload.get('provider')}")
            print(f"  - Subject: {payload.get('sub')}")
            return True
        else:
            print("✗ Token validation failed")
            return False

    except Exception as e:
        print(f"✗ Agentic search validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_no_legacy_hs256():
    """Test 4: Verify no legacy HS256 support exists"""
    print("\n" + "="*60)
    print("TEST 4: Verify Legacy HS256 Removed")
    print("="*60)

    try:
        # Check if deprecated /config/jwt endpoint exists
        response = httpx.get("http://localhost:8021/config/jwt", timeout=5.0)

        if response.status_code == 404:
            print("✓ Deprecated /config/jwt endpoint removed (404)")
        else:
            print(f"✗ Deprecated /config/jwt endpoint still exists (status: {response.status_code})")
            return False

        # Check if config has removed legacy fields
        response = httpx.get("http://localhost:8021/config/system", timeout=5.0)

        if response.status_code == 200:
            config = response.json()

            # Verify RS256 fields exist
            assert "rsa_private_key" in config, "Missing rsa_private_key"
            assert config.get("rsa_private_key") == "***HIDDEN***", "RSA private key should be hidden"
            assert "rsa_public_key" in config, "Missing rsa_public_key"
            assert "jwt_key_id" in config, "Missing jwt_key_id"

            print("✓ RS256 fields present in config")
            print(f"  - Key ID: {config.get('jwt_key_id')}")
            print(f"  - RSA private key: ***HIDDEN*** (secure)")
            print(f"  - RSA public key: {config.get('rsa_public_key')[:50]}...")

            return True
        else:
            print(f"✗ Failed to get system config (status: {response.status_code})")
            return False

    except Exception as e:
        print(f"✗ Legacy check test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("RS256-Only Implementation Test Suite")
    print("Testing after legacy HS256 removal")
    print("="*60)

    results = []

    # Test 1: JWKS endpoint
    success, kid = test_1_jwks_endpoint()
    results.append(("JWKS Endpoint", success))

    # Test 2: Create RS256 token
    success, token = test_2_create_rs256_token()
    results.append(("RS256 Token Creation", success))

    # Test 3: Agentic search validation
    success = test_3_agentic_search_validation()
    results.append(("Agentic Search Validation", success))

    # Test 4: No legacy HS256
    success = test_4_no_legacy_hs256()
    results.append(("Legacy HS256 Removed", success))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(success for _, success in results)

    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - RS256-only implementation working!")
    else:
        print("⚠️  SOME TESTS FAILED - Check output above")
    print("="*60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

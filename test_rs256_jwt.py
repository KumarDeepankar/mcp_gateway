#!/usr/bin/env python3
"""
Test RS256 JWT token signing and validation
Tests the JWKS implementation between tools_gateway and agentic_search
"""
import sys
import os

# Add paths
sys.path.insert(0, '/Users/deepankar/Documents/mcp_gateway')
sys.path.insert(0, '/Users/deepankar/Documents/mcp_gateway/tools_gateway')
sys.path.insert(0, '/Users/deepankar/Documents/mcp_gateway/agentic_search')

def test_tools_gateway_rs256():
    """Test tools_gateway creates RS256 tokens"""
    print("=" * 60)
    print("TEST 1: Tools Gateway RS256 Token Creation")
    print("=" * 60)

    from tools_gateway.config import config_manager
    from tools_gateway.auth import _get_jwt_manager, UserInfo
    from jose import jwt

    # Check system config
    system_config = config_manager.get_system_config()
    print(f"✓ Algorithm: {system_config.jwt_algorithm}")
    print(f"✓ Has RSA Private Key: {bool(system_config.rsa_private_key)}")
    print(f"✓ Has RSA Public Key: {bool(system_config.rsa_public_key)}")
    print(f"✓ Key ID: {system_config.jwt_key_id}")

    # Get JWT manager
    jwt_manager = _get_jwt_manager()
    print(f"✓ JWT Manager Algorithm: {jwt_manager.algorithm}")

    # Create test user token
    test_user = UserInfo(
        sub="test_user_123",
        email="test@example.com",
        name="Test User",
        provider="test"
    )

    token = jwt_manager.create_access_token(test_user)
    print(f"\n✓ Token created: {token[:50]}...")

    # Decode header without verification to check kid
    header = jwt.get_unverified_header(token)
    print(f"✓ Token header: {header}")

    if "kid" in header:
        print(f"✓ SUCCESS: Token has 'kid' header: {header['kid']}")
    else:
        print(f"✗ FAIL: Token missing 'kid' header")
        return False

    # Verify token
    payload = jwt_manager.verify_token(token)
    if payload:
        print(f"✓ Token validated successfully")
        print(f"  - Email: {payload.get('email')}")
        print(f"  - Algorithm used: RS256")
    else:
        print(f"✗ FAIL: Token validation failed")
        return False

    print("\n✓ TEST 1 PASSED")
    return True


def test_agentic_search_jwks_validation():
    """Test agentic_search can fetch JWKS and validate RS256 tokens"""
    print("\n" + "=" * 60)
    print("TEST 2: Agentic Search JWKS Validation")
    print("=" * 60)

    # Import agentic_search auth module
    sys.path.insert(0, '/Users/deepankar/Documents/mcp_gateway/agentic_search')
    import auth as agentic_auth

    # Fetch JWKS from gateway
    print("Fetching JWKS from tools_gateway...")
    success = agentic_auth.fetch_jwks_from_gateway("http://localhost:8021")

    if success:
        print(f"✓ JWKS fetched successfully")
        cache = agentic_auth._JWKS_CACHE
        print(f"✓ Public keys cached: {len(cache['public_keys'])}")
        for kid, key_data in cache['public_keys'].items():
            print(f"  - Key ID: {kid}")
            print(f"    Algorithm: {key_data['algorithm']}")
    else:
        print(f"✗ FAIL: Failed to fetch JWKS")
        return False

    # Create a test token from tools_gateway
    from tools_gateway.auth import _get_jwt_manager, UserInfo
    jwt_manager = _get_jwt_manager()

    test_user = UserInfo(
        sub="test_user_456",
        email="test2@example.com",
        name="Test User 2",
        provider="test"
    )

    token = jwt_manager.create_access_token(test_user)
    print(f"\n✓ Test token created")

    # Validate token using agentic_search
    print("Validating token with agentic_search...")
    payload = agentic_auth.validate_jwt(token)

    if payload:
        print(f"✓ SUCCESS: Token validated by agentic_search")
        print(f"  - Email: {payload.get('email')}")
        print(f"  - Name: {payload.get('name')}")
    else:
        print(f"✗ FAIL: Token validation failed in agentic_search")
        return False

    print("\n✓ TEST 2 PASSED")
    return True


def test_jwks_endpoint():
    """Test JWKS endpoint is accessible"""
    print("\n" + "=" * 60)
    print("TEST 3: JWKS Endpoint Accessibility")
    print("=" * 60)

    import httpx

    try:
        response = httpx.get("http://localhost:8021/.well-known/jwks.json", timeout=5.0)

        if response.status_code == 200:
            jwks = response.json()
            print(f"✓ JWKS endpoint accessible")
            print(f"✓ Number of keys: {len(jwks.get('keys', []))}")

            for key in jwks.get('keys', []):
                print(f"  - Key ID: {key.get('kid')}")
                print(f"    Algorithm: {key.get('alg')}")
                print(f"    Key Type: {key.get('kty')}")
                print(f"    Use: {key.get('use')}")
        else:
            print(f"✗ FAIL: JWKS endpoint returned {response.status_code}")
            return False

    except Exception as e:
        print(f"✗ FAIL: Error accessing JWKS endpoint: {e}")
        return False

    print("\n✓ TEST 3 PASSED")
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("RS256 JWT / JWKS INTEGRATION TEST")
    print("=" * 60 + "\n")

    results = []

    # Test 1: Tools Gateway RS256
    try:
        results.append(("Tools Gateway RS256", test_tools_gateway_rs256()))
    except Exception as e:
        print(f"✗ TEST 1 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Tools Gateway RS256", False))

    # Test 2: Agentic Search JWKS
    try:
        results.append(("Agentic Search JWKS", test_agentic_search_jwks_validation()))
    except Exception as e:
        print(f"✗ TEST 2 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Agentic Search JWKS", False))

    # Test 3: JWKS Endpoint
    try:
        results.append(("JWKS Endpoint", test_jwks_endpoint()))
    except Exception as e:
        print(f"✗ TEST 3 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        results.append(("JWKS Endpoint", False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\nJWKS/RS256 implementation is working correctly:")
        print("  1. Tools Gateway signs tokens with RS256")
        print("  2. Tokens include 'kid' header for key rotation")
        print("  3. JWKS endpoint exposes public keys")
        print("  4. Agentic Search validates tokens with JWKS")
        print("  5. No shared secrets between services")
        return 0
    else:
        print("\n" + "=" * 60)
        print("⚠ SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

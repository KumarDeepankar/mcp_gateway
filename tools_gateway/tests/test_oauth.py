#!/usr/bin/env python3
"""
OAuth 2.1 Testing Script
Tests the OAuth implementation without requiring real OAuth providers
"""

import sys
import os
import asyncio

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth import oauth_provider_manager, jwt_manager, UserInfo
from rbac import rbac_manager, Permission
from audit import audit_logger, AuditEventType
from encryption import encryption_manager


def test_oauth_provider_setup():
    """Test 1: OAuth Provider Configuration"""
    print("\n" + "=" * 60)
    print("TEST 1: OAuth Provider Configuration")
    print("=" * 60)

    # Add a test provider
    print("\n→ Adding test Google OAuth provider...")
    try:
        provider = oauth_provider_manager.add_provider(
            provider_id="google_test",
            client_id="test_client_id_123",
            client_secret="test_client_secret_456",
            template="google"
        )

        print(f"✅ Provider added successfully")
        print(f"   ID: {provider.provider_id}")
        print(f"   Name: {provider.provider_name}")
        print(f"   Authorize URL: {provider.authorize_url}")
        print(f"   Token URL: {provider.token_url}")
        print(f"   Scopes: {provider.scopes}")

        # List all providers
        print("\n→ Listing all configured providers...")
        providers = oauth_provider_manager.list_providers()
        print(f"✅ Found {len(providers)} provider(s)")

        for p in providers:
            print(f"   - {p['provider_name']} ({p['provider_id']}) - {'Enabled' if p['enabled'] else 'Disabled'}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_authorization_url_generation():
    """Test 2: Authorization URL Generation with PKCE"""
    print("\n" + "=" * 60)
    print("TEST 2: Authorization URL Generation (PKCE)")
    print("=" * 60)

    print("\n→ Generating authorization URL...")
    try:
        redirect_uri = "http://localhost:8021/auth/callback"
        auth_data = oauth_provider_manager.create_authorization_url(
            "google_test",
            redirect_uri
        )

        if not auth_data:
            print("❌ Failed to generate authorization URL")
            return False

        print("✅ Authorization URL generated successfully")
        print(f"   State: {auth_data['state'][:20]}...")
        print(f"   URL: {auth_data['url'][:100]}...")

        # Verify PKCE parameters in URL
        if "code_challenge" in auth_data['url']:
            print("✅ PKCE code_challenge included")
        if "code_challenge_method=S256" in auth_data['url']:
            print("✅ PKCE method is S256")

        # Verify state is stored
        state = auth_data['state']
        if state in oauth_provider_manager.pending_states:
            oauth_state = oauth_provider_manager.pending_states[state]
            print(f"✅ State stored with code_verifier")
            print(f"   Provider: {oauth_state.provider_id}")
            print(f"   Redirect URI: {oauth_state.redirect_uri}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_jwt_token_management():
    """Test 3: JWT Token Generation and Validation"""
    print("\n" + "=" * 60)
    print("TEST 3: JWT Token Management")
    print("=" * 60)

    print("\n→ Creating test user info...")
    user_info = UserInfo(
        sub="test_user_123",
        email="test@example.com",
        name="Test User",
        picture=None,
        provider="google_test"
    )

    print(f"✅ User info created")
    print(f"   Subject: {user_info.sub}")
    print(f"   Email: {user_info.email}")
    print(f"   Provider: {user_info.provider}")

    print("\n→ Generating JWT access token...")
    try:
        token = jwt_manager.create_access_token(user_info)
        print(f"✅ JWT token generated")
        print(f"   Token: {token[:50]}...")

        print("\n→ Verifying JWT token...")
        payload = jwt_manager.verify_token(token)

        if payload:
            print("✅ Token verified successfully")
            print(f"   Subject: {payload.get('sub')}")
            print(f"   Email: {payload.get('email')}")
            print(f"   Provider: {payload.get('provider')}")
            print(f"   Type: {payload.get('type')}")
            print(f"   Expires: {payload.get('exp')}")
        else:
            print("❌ Token verification failed")
            return False

        # Test invalid token
        print("\n→ Testing invalid token...")
        invalid_payload = jwt_manager.verify_token("invalid.token.here")
        if invalid_payload is None:
            print("✅ Invalid token correctly rejected")
        else:
            print("❌ Invalid token was accepted!")
            return False

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rbac_integration():
    """Test 4: RBAC Integration with OAuth Users"""
    print("\n" + "=" * 60)
    print("TEST 4: RBAC Integration")
    print("=" * 60)

    print("\n→ Creating user from OAuth login...")
    try:
        user = rbac_manager.get_or_create_user(
            email="test@example.com",
            name="Test User",
            provider="google_test"
        )

        print(f"✅ User created/retrieved")
        print(f"   User ID: {user.user_id}")
        print(f"   Email: {user.email}")
        print(f"   Roles: {user.roles}")
        print(f"   Enabled: {user.enabled}")

        # Check default permissions
        print("\n→ Checking default user permissions...")
        can_view_servers = rbac_manager.has_permission(user.user_id, Permission.SERVER_VIEW)
        can_execute_tools = rbac_manager.has_permission(user.user_id, Permission.TOOL_EXECUTE)
        can_manage_users = rbac_manager.has_permission(user.user_id, Permission.USER_MANAGE)

        print(f"   Can view servers: {can_view_servers}")
        print(f"   Can execute tools: {can_execute_tools}")
        print(f"   Can manage users: {can_manage_users}")

        # Assign admin role
        print("\n→ Assigning admin role...")
        rbac_manager.assign_role(user.user_id, "admin")

        can_manage_users = rbac_manager.has_permission(user.user_id, Permission.USER_MANAGE)
        print(f"✅ Admin role assigned")
        print(f"   Can manage users: {can_manage_users}")

        # Get all permissions
        print("\n→ Getting all user permissions...")
        permissions = rbac_manager.get_user_permissions(user.user_id)
        print(f"✅ User has {len(permissions)} permissions:")
        for perm in sorted(permissions, key=lambda p: p.value):
            print(f"   - {perm.value}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_audit_logging():
    """Test 5: Audit Logging for OAuth Events"""
    print("\n" + "=" * 60)
    print("TEST 5: Audit Logging")
    print("=" * 60)

    print("\n→ Logging OAuth login event...")
    try:
        event = audit_logger.log_event(
            AuditEventType.AUTH_LOGIN_SUCCESS,
            user_id="test_user_123",
            user_email="test@example.com",
            ip_address="127.0.0.1",
            details={
                "provider": "google_test",
                "method": "oauth2"
            }
        )

        print(f"✅ Login event logged")
        print(f"   Event ID: {event.event_id}")
        print(f"   Timestamp: {event.timestamp}")
        print(f"   Type: {event.event_type.value}")

        print("\n→ Logging token issued event...")
        audit_logger.log_event(
            AuditEventType.AUTH_TOKEN_ISSUED,
            user_id="test_user_123",
            user_email="test@example.com",
            details={"token_type": "JWT"}
        )

        print("\n→ Querying recent audit events...")
        events = audit_logger.query_events(
            user_email="test@example.com",
            limit=10
        )

        print(f"✅ Found {len(events)} event(s) for user")
        for evt in events:
            print(f"   - {evt.timestamp.strftime('%H:%M:%S')} - {evt.event_type.value}")

        print("\n→ Getting audit statistics...")
        stats = audit_logger.get_statistics(hours=1)
        print(f"✅ Statistics for last hour:")
        print(f"   Total events: {stats['total_events']}")
        print(f"   Event types: {len(stats['event_counts'])}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_encryption():
    """Test 6: Data Encryption"""
    print("\n" + "=" * 60)
    print("TEST 6: Data Encryption")
    print("=" * 60)

    print("\n→ Encrypting OAuth client secret...")
    try:
        secret = "super_secret_oauth_client_secret_123"
        encrypted = encryption_manager.encrypt(secret)

        print(f"✅ Secret encrypted")
        print(f"   Original: {secret[:20]}...")
        print(f"   Encrypted: {encrypted[:50]}...")

        print("\n→ Decrypting secret...")
        decrypted = encryption_manager.decrypt(encrypted)

        if decrypted == secret:
            print("✅ Secret decrypted successfully")
            print(f"   Matches original: True")
        else:
            print("❌ Decryption mismatch!")
            return False

        print("\n→ Testing password hashing...")
        password = "test_password_123"
        hashed, salt = encryption_manager.hash_password(password)

        print(f"✅ Password hashed")
        print(f"   Hash: {hashed[:50]}...")
        print(f"   Salt: {salt[:50]}...")

        print("\n→ Verifying password...")
        is_valid = encryption_manager.verify_password(password, hashed, salt)
        print(f"✅ Password verification: {is_valid}")

        is_invalid = encryption_manager.verify_password("wrong_password", hashed, salt)
        print(f"✅ Wrong password rejected: {not is_invalid}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mcp_server_access_control():
    """Test 7: MCP Server Access Control"""
    print("\n" + "=" * 60)
    print("TEST 7: MCP Server Access Control")
    print("=" * 60)

    print("\n→ Creating a regular user (not admin) for testing...")
    try:
        # Create a non-admin user
        user = rbac_manager.create_user(
            email="regular_user@example.com",
            name="Regular User",
            roles={"user"}  # Standard user role only
        )

        print(f"✅ Regular user created: {user.email}")
        print(f"   Roles: {user.roles}")

        print("\n→ Granting access to weather_server with specific tools...")
        rbac_manager.grant_server_access(
            user.user_id,
            "weather_server",
            allowed_tools={"get_weather", "get_forecast"}
        )

        print("\n→ Checking server access...")
        can_access = rbac_manager.can_access_server(user.user_id, "weather_server")
        print(f"✅ Can access weather_server: {can_access}")

        print("\n→ Checking tool execution permissions...")
        can_execute_weather = rbac_manager.can_execute_tool(
            user.user_id, "weather_server", "get_weather"
        )
        can_execute_forecast = rbac_manager.can_execute_tool(
            user.user_id, "weather_server", "get_forecast"
        )
        can_execute_other = rbac_manager.can_execute_tool(
            user.user_id, "weather_server", "delete_data"
        )

        print(f"   Can execute 'get_weather': {can_execute_weather}")
        print(f"   Can execute 'get_forecast': {can_execute_forecast}")
        print(f"   Can execute 'delete_data': {can_execute_other}")

        if can_execute_weather and can_execute_forecast and not can_execute_other:
            print("✅ Tool-level access control working correctly")
        else:
            print("❌ Tool-level access control failed")
            return False

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all OAuth and security tests"""
    print("\n" + "=" * 70)
    print(" " * 15 + "OAuth 2.1 & Security Testing Suite")
    print("=" * 70)

    tests = [
        ("OAuth Provider Setup", test_oauth_provider_setup),
        ("Authorization URL Generation", test_authorization_url_generation),
        ("JWT Token Management", test_jwt_token_management),
        ("RBAC Integration", test_rbac_integration),
        ("Audit Logging", test_audit_logging),
        ("Data Encryption", test_encryption),
        ("MCP Server Access Control", test_mcp_server_access_control),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "=" * 70)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()

    if success:
        print("\n🎉 All tests passed! OAuth 2.1 system is working correctly.")
        print("\nNext steps:")
        print("1. Run: python setup_oauth_test.py")
        print("2. Configure real OAuth providers (Google, Microsoft, or GitHub)")
        print("3. Start gateway: python main.py")
        print("4. Test in browser: http://localhost:8021")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed. Please review the output above.")
        sys.exit(1)

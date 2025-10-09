#!/usr/bin/env python3
"""
OAuth Provider Setup Script
Sets up OAuth providers for testing
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth import oauth_provider_manager

def setup_google_oauth():
    """Setup Google OAuth provider"""
    print("\n=== Setting up Google OAuth Provider ===\n")

    print("To get Google OAuth credentials:")
    print("1. Go to https://console.cloud.google.com/")
    print("2. Create a new project or select existing")
    print("3. Enable Google+ API")
    print("4. Go to Credentials → Create Credentials → OAuth 2.0 Client ID")
    print("5. Application type: Web application")
    print("6. Authorized redirect URIs: http://localhost:8021/auth/callback")
    print("7. Copy Client ID and Client Secret\n")

    client_id = input("Enter Google Client ID (or press Enter to skip): ").strip()

    if not client_id:
        print("⚠ Skipping Google OAuth setup")
        return False

    client_secret = input("Enter Google Client Secret: ").strip()

    if not client_secret:
        print("❌ Client Secret required")
        return False

    try:
        provider = oauth_provider_manager.add_provider(
            provider_id="google",
            client_id=client_id,
            client_secret=client_secret,
            template="google"
        )

        print(f"\n✅ Google OAuth provider configured successfully!")
        print(f"   Provider ID: {provider.provider_id}")
        print(f"   Provider Name: {provider.provider_name}")
        print(f"   Scopes: {', '.join(provider.scopes)}")
        return True

    except Exception as e:
        print(f"❌ Error setting up Google OAuth: {e}")
        return False


def setup_microsoft_oauth():
    """Setup Microsoft OAuth provider"""
    print("\n=== Setting up Microsoft OAuth Provider ===\n")

    print("To get Microsoft OAuth credentials:")
    print("1. Go to https://portal.azure.com/")
    print("2. Register a new application")
    print("3. Add redirect URI: http://localhost:8021/auth/callback")
    print("4. Create a client secret")
    print("5. Copy Application (client) ID and Client Secret\n")

    client_id = input("Enter Microsoft Client ID (or press Enter to skip): ").strip()

    if not client_id:
        print("⚠ Skipping Microsoft OAuth setup")
        return False

    client_secret = input("Enter Microsoft Client Secret: ").strip()

    if not client_secret:
        print("❌ Client Secret required")
        return False

    try:
        provider = oauth_provider_manager.add_provider(
            provider_id="microsoft",
            client_id=client_id,
            client_secret=client_secret,
            template="microsoft"
        )

        print(f"\n✅ Microsoft OAuth provider configured successfully!")
        print(f"   Provider ID: {provider.provider_id}")
        print(f"   Provider Name: {provider.provider_name}")
        return True

    except Exception as e:
        print(f"❌ Error setting up Microsoft OAuth: {e}")
        return False


def setup_github_oauth():
    """Setup GitHub OAuth provider"""
    print("\n=== Setting up GitHub OAuth Provider ===\n")

    print("To get GitHub OAuth credentials:")
    print("1. Go to GitHub Settings → Developer settings → OAuth Apps")
    print("2. Create a new OAuth App")
    print("3. Authorization callback URL: http://localhost:8021/auth/callback")
    print("4. Copy Client ID and Client Secret\n")

    client_id = input("Enter GitHub Client ID (or press Enter to skip): ").strip()

    if not client_id:
        print("⚠ Skipping GitHub OAuth setup")
        return False

    client_secret = input("Enter GitHub Client Secret: ").strip()

    if not client_secret:
        print("❌ Client Secret required")
        return False

    try:
        provider = oauth_provider_manager.add_provider(
            provider_id="github",
            client_id=client_id,
            client_secret=client_secret,
            template="github"
        )

        print(f"\n✅ GitHub OAuth provider configured successfully!")
        print(f"   Provider ID: {provider.provider_id}")
        print(f"   Provider Name: {provider.provider_name}")
        return True

    except Exception as e:
        print(f"❌ Error setting up GitHub OAuth: {e}")
        return False


def list_configured_providers():
    """List all configured OAuth providers"""
    providers = oauth_provider_manager.list_providers()

    if not providers:
        print("\n⚠ No OAuth providers configured yet")
        return

    print(f"\n=== Configured OAuth Providers ({len(providers)}) ===\n")

    for provider in providers:
        status = "✅ Enabled" if provider['enabled'] else "❌ Disabled"
        print(f"{status} {provider['provider_name']} ({provider['provider_id']})")
        print(f"   Scopes: {', '.join(provider['scopes'])}")
        print()


def main():
    print("=" * 60)
    print("OAuth Provider Setup - Tools Gateway")
    print("=" * 60)

    # Check existing providers
    list_configured_providers()

    # Setup menu
    while True:
        print("\nSetup Options:")
        print("1. Add Google OAuth")
        print("2. Add Microsoft OAuth")
        print("3. Add GitHub OAuth")
        print("4. List configured providers")
        print("5. Exit")

        choice = input("\nSelect option (1-5): ").strip()

        if choice == "1":
            setup_google_oauth()
        elif choice == "2":
            setup_microsoft_oauth()
        elif choice == "3":
            setup_github_oauth()
        elif choice == "4":
            list_configured_providers()
        elif choice == "5":
            print("\n✅ Setup complete!")
            list_configured_providers()
            print("\nNext steps:")
            print("1. Start the gateway: python main.py")
            print("2. Open browser: http://localhost:8021")
            print("3. Click 'Sign in with [Provider]'")
            break
        else:
            print("Invalid option")


if __name__ == "__main__":
    main()

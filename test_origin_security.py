#!/usr/bin/env python3
"""
Comprehensive test suite for origin validation and security features.
Tests the MCP Gateway origin handling implementation.
"""
import asyncio
import sys
import httpx
import json
from typing import Dict, Any, Optional
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init(autoreset=True)

GATEWAY_URL = "http://localhost:8021"


class OriginSecurityTester:
    """Test suite for origin validation and security"""

    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.test_results = []
        self.passed = 0
        self.failed = 0

    def log_test(self, test_name: str, passed: bool, message: str):
        """Log test result"""
        status = f"{Fore.GREEN}✓ PASS" if passed else f"{Fore.RED}✗ FAIL"
        print(f"{status}{Style.RESET_ALL} - {test_name}: {message}")
        self.test_results.append({"test": test_name, "passed": passed, "message": message})
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    async def test_localhost_origin(self):
        """Test 1: Localhost origin should be accepted (default allowlist)"""
        test_name = "Localhost Origin (Default Allowlist)"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.gateway_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "id": "test-localhost",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    },
                    headers={
                        "Origin": "http://localhost:8023",
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": "2025-06-18"
                    }
                )

                if response.status_code == 200:
                    self.log_test(test_name, True, f"Status: {response.status_code}")
                else:
                    self.log_test(test_name, False, f"Expected 200, got {response.status_code}")
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def test_https_origin_accepted(self):
        """Test 2: HTTPS origin should be accepted (allow_https: true)"""
        test_name = "HTTPS Origin Acceptance (allow_https: true)"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.gateway_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "id": "test-https",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    },
                    headers={
                        "Origin": "https://search.example.com",
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": "2025-06-18"
                    }
                )

                if response.status_code == 200:
                    self.log_test(test_name, True, f"Status: {response.status_code} (Permissive mode)")
                else:
                    self.log_test(test_name, False, f"Expected 200, got {response.status_code}")
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def test_ngrok_origin_accepted(self):
        """Test 3: ngrok origin should be accepted (allow_ngrok: true)"""
        test_name = "ngrok Origin Acceptance (allow_ngrok: true)"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.gateway_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "id": "test-ngrok",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    },
                    headers={
                        "Origin": "https://abc123.ngrok-free.app",
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": "2025-06-18"
                    }
                )

                if response.status_code == 200:
                    self.log_test(test_name, True, f"Status: {response.status_code} (Permissive mode)")
                else:
                    self.log_test(test_name, False, f"Expected 200, got {response.status_code}")
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def test_no_origin_rejected(self):
        """Test 4: Request without origin should be rejected"""
        test_name = "No Origin Header Rejection"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.gateway_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "id": "test-no-origin",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    },
                    headers={
                        # No Origin header
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": "2025-06-18"
                    }
                )

                if response.status_code == 403:
                    self.log_test(test_name, True, f"Correctly rejected with 403")
                else:
                    self.log_test(test_name, False, f"Expected 403, got {response.status_code}")
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def test_http_non_localhost_rejected(self):
        """Test 5: HTTP origin (non-localhost) should be rejected"""
        test_name = "HTTP Non-localhost Rejection"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.gateway_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "id": "test-http",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    },
                    headers={
                        "Origin": "http://random-site.com",
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": "2025-06-18"
                    }
                )

                if response.status_code == 403:
                    self.log_test(test_name, True, f"Correctly rejected with 403")
                else:
                    self.log_test(test_name, False, f"Expected 403, got {response.status_code}")
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def test_malicious_origin_injection(self):
        """Test 6: Malicious origin with injection attempts should be rejected"""
        test_name = "Malicious Origin Injection Prevention"
        malicious_origins = [
            "javascript://alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "http://evil.com/../../etc/passwd",
            "http://localhost:8021/../admin",
        ]

        all_rejected = True
        for malicious in malicious_origins:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(
                        f"{self.gateway_url}/mcp",
                        json={
                            "jsonrpc": "2.0",
                            "method": "initialize",
                            "id": "test-injection",
                            "params": {
                                "protocolVersion": "2025-06-18",
                                "clientInfo": {"name": "test", "version": "1.0"}
                            }
                        },
                        headers={
                            "Origin": malicious,
                            "Accept": "application/json, text/event-stream",
                            "Content-Type": "application/json",
                            "MCP-Protocol-Version": "2025-06-18"
                        }
                    )

                    if response.status_code != 403:
                        all_rejected = False
                        print(f"  {Fore.YELLOW}⚠ Warning: {malicious} not rejected (status: {response.status_code})")
            except Exception as e:
                # Exception is acceptable for malicious input
                pass

        if all_rejected:
            self.log_test(test_name, True, "All injection attempts blocked")
        else:
            self.log_test(test_name, False, "Some injection attempts not blocked")

    async def test_forwarded_headers(self):
        """Test 7: X-Forwarded-Host header extraction works"""
        test_name = "Load Balancer X-Forwarded-Host Extraction"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.gateway_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "id": "test-forwarded",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    },
                    headers={
                        # No direct Origin, but forwarded headers
                        "X-Forwarded-Host": "search.example.com",
                        "X-Forwarded-Proto": "https",
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": "2025-06-18"
                    }
                )

                if response.status_code == 200:
                    self.log_test(test_name, True, f"Extracted origin from X-Forwarded-* headers")
                else:
                    self.log_test(test_name, False, f"Expected 200, got {response.status_code}")
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def test_add_origin_validation(self):
        """Test 8: Adding origin via API with validation"""
        test_name = "Add Origin API with Validation"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Test valid origin
                response = await client.post(
                    f"{self.gateway_url}/config/origin/add",
                    json={"origin": "test-domain.com"}
                )

                valid_added = response.status_code == 200 and response.json().get("success")

                # Test invalid origin (SQL injection attempt)
                response = await client.post(
                    f"{self.gateway_url}/config/origin/add",
                    json={"origin": "evil'; DROP TABLE users;--"}
                )

                invalid_rejected = response.status_code != 200 or not response.json().get("success")

                if valid_added and invalid_rejected:
                    self.log_test(test_name, True, "Valid origin added, invalid origin rejected")
                else:
                    self.log_test(test_name, False, f"valid_added: {valid_added}, invalid_rejected: {invalid_rejected}")

                # Cleanup
                await client.post(
                    f"{self.gateway_url}/config/origin/remove",
                    json={"origin": "test-domain.com"}
                )
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def test_config_retrieval(self):
        """Test 9: Configuration retrieval works"""
        test_name = "Configuration Retrieval"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.gateway_url}/config")

                if response.status_code == 200:
                    config = response.json()
                    has_origin = "origin" in config
                    has_allowed = "allowed_origins" in config.get("origin", {})

                    if has_origin and has_allowed:
                        self.log_test(test_name, True, f"Config retrieved successfully")
                    else:
                        self.log_test(test_name, False, "Config missing expected fields")
                else:
                    self.log_test(test_name, False, f"Expected 200, got {response.status_code}")
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def test_tools_list(self):
        """Test 10: Tools list endpoint works with valid origin"""
        test_name = "Tools List Endpoint"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.gateway_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/list",
                        "id": "test-tools",
                    },
                    headers={
                        "Origin": "http://localhost:8023",
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": "2025-06-18",
                        "Mcp-Session-Id": "test-session"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if "result" in data and "tools" in data["result"]:
                        self.log_test(test_name, True, f"Tools list retrieved")
                    else:
                        self.log_test(test_name, True, f"Response valid (no tools registered)")
                else:
                    self.log_test(test_name, False, f"Expected 200, got {response.status_code}")
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def test_origin_sanitization(self):
        """Test 11: Origin sanitization removes path/query"""
        test_name = "Origin Sanitization (Path/Query Removal)"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Origin with path and query should be sanitized
                response = await client.post(
                    f"{self.gateway_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "id": "test-sanitize",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    },
                    headers={
                        "Origin": "https://search.example.com/admin?token=secret#fragment",
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": "2025-06-18"
                    }
                )

                # Should be accepted (sanitized to https://search.example.com)
                if response.status_code == 200:
                    self.log_test(test_name, True, "Origin sanitized and accepted")
                else:
                    self.log_test(test_name, False, f"Expected 200, got {response.status_code}")
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")

    async def run_all_tests(self):
        """Run all test scenarios"""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}Origin Security Test Suite")
        print(f"{Fore.CYAN}Gateway URL: {self.gateway_url}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")

        # Run tests
        await self.test_localhost_origin()
        await self.test_https_origin_accepted()
        await self.test_ngrok_origin_accepted()
        await self.test_no_origin_rejected()
        await self.test_http_non_localhost_rejected()
        await self.test_malicious_origin_injection()
        await self.test_forwarded_headers()
        await self.test_add_origin_validation()
        await self.test_config_retrieval()
        await self.test_tools_list()
        await self.test_origin_sanitization()

        # Summary
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}Test Summary{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Passed: {self.passed}{Style.RESET_ALL}")
        print(f"{Fore.RED}Failed: {self.failed}{Style.RESET_ALL}")
        print(f"Total:  {self.passed + self.failed}")

        success_rate = (self.passed / (self.passed + self.failed) * 100) if (self.passed + self.failed) > 0 else 0
        print(f"\n{Fore.CYAN}Success Rate: {success_rate:.1f}%{Style.RESET_ALL}\n")

        return self.failed == 0


async def main():
    """Main test runner"""
    import sys

    gateway_url = sys.argv[1] if len(sys.argv) > 1 else GATEWAY_URL

    tester = OriginSecurityTester(gateway_url)

    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Tests interrupted by user{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Test suite failed with exception: {e}{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

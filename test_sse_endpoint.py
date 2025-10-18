#!/usr/bin/env python3
"""
Test script for SSE endpoint
"""
import requests
import json
import time

def test_sse_endpoint():
    """Test the SSE endpoint by establishing a connection"""
    url = "http://localhost:8021/sse"

    print("Testing SSE endpoint...")
    print(f"Connecting to {url}")

    try:
        # Create a streaming connection
        with requests.get(url, headers={"Accept": "text/event-stream"}, stream=True, timeout=5) as response:
            print(f"Response Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")

            if response.status_code == 200:
                print("\n✓ SSE connection established successfully!")
                print("\nReceiving events...")

                # Read first few events
                event_count = 0
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        print(f"  {decoded_line}")

                        # Parse endpoint event
                        if 'data:' in decoded_line:
                            try:
                                data = json.loads(decoded_line.split('data: ', 1)[1])
                                if data.get('method') == 'endpoint':
                                    session_id = data['params']['endpoint'].split('session_id=')[1]
                                    print(f"\n✓ Session created: {session_id}")
                                    return session_id
                            except:
                                pass

                        event_count += 1
                        if event_count > 5:
                            break
            else:
                print(f"\n✗ Failed to establish SSE connection. Status: {response.status_code}")
                return None

    except requests.exceptions.Timeout:
        print("\n✗ Connection timed out")
        return None
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return None

def test_messages_endpoint(session_id):
    """Test sending a message via the /messages endpoint"""
    if not session_id:
        print("\n✗ Cannot test messages endpoint without session ID")
        return

    url = f"http://localhost:8021/messages?session_id={session_id}"

    print(f"\n\nTesting messages endpoint with session {session_id}...")

    # Test initialize message
    message = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        },
        "id": "test-init"
    }

    try:
        response = requests.post(url, json=message, timeout=5)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.json()}")

        if response.status_code == 200:
            print("\n✓ Message endpoint working correctly!")
        else:
            print(f"\n✗ Message endpoint returned error: {response.status_code}")

    except Exception as e:
        print(f"\n✗ Error testing messages endpoint: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("SSE Endpoint Test Suite")
    print("=" * 60)

    session_id = test_sse_endpoint()

    if session_id:
        time.sleep(1)  # Give server a moment
        test_messages_endpoint(session_id)

    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)

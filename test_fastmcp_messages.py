#!/usr/bin/env python3
"""
Test if FastMCP properly responds to POSTed messages via SSE
"""
import requests
import json
import threading
import time
import queue

def test_fastmcp_message_response():
    """Test if FastMCP sends responses back via SSE"""

    print("=" * 60)
    print("Testing FastMCP Message Response via SSE")
    print("=" * 60)

    # Step 1: Establish SSE connection
    print("\n1. Establishing SSE connection...")
    event_queue = queue.Queue()
    session_id = None

    def sse_listener():
        nonlocal session_id
        try:
            with requests.get("http://localhost:8002/sse", stream=True, timeout=60) as response:
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        print(f"   SSE: {decoded}")

                        if decoded.startswith('event:'):
                            event_type = decoded.split(': ', 1)[1]
                        elif decoded.startswith('data:'):
                            data = decoded.split(': ', 1)[1]

                            # Parse session from endpoint event
                            if 'session_id=' in data:
                                session_id = data.split('session_id=')[1]
                                print(f"   ✓ Session ID: {session_id}")
                            else:
                                # Queue other events
                                event_queue.put(data)
        except Exception as e:
            print(f"   SSE Error: {e}")

    # Start SSE listener in background
    listener_thread = threading.Thread(target=sse_listener, daemon=True)
    listener_thread.start()

    # Wait for session establishment
    time.sleep(2)

    if not session_id:
        print("✗ Failed to establish session")
        return

    # Step 2: Send initialize message
    print(f"\n2. Sending initialize message to session {session_id}...")
    init_message = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        },
        "id": "test-init-1"
    }

    response = requests.post(
        f"http://localhost:8002/messages?session_id={session_id}",
        json=init_message
    )
    print(f"   POST response status: {response.status_code}")
    print(f"   POST response body: {response.text}")

    # Step 3: Wait for response via SSE
    print("\n3. Waiting for response via SSE (10 seconds)...")
    start_time = time.time()
    while time.time() - start_time < 10:
        try:
            event = event_queue.get(timeout=1)
            print(f"   ✓ Received SSE event: {event}")
            try:
                parsed = json.loads(event)
                if parsed.get('id') == 'test-init-1':
                    print("   ✓ SUCCESS: Received matching response!")
                    return
            except:
                pass
        except queue.Empty:
            continue

    print("   ✗ TIMEOUT: No response received via SSE")
    print("\n" + "=" * 60)
    print("CONCLUSION: FastMCP doesn't send responses via SSE")
    print("=" * 60)

if __name__ == "__main__":
    test_fastmcp_message_response()

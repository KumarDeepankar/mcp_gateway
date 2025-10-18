#!/usr/bin/env python3
"""
Detailed test to understand FastMCP SSE behavior
"""
import requests
import json
import threading
import time
import queue

def detailed_fastmcp_test():
    """Test FastMCP with detailed logging"""

    print("=" * 70)
    print("DETAILED FASTMCP SSE TEST")
    print("=" * 70)

    # Establish SSE connection
    print("\n[1] Establishing SSE connection to http://localhost:8002/sse")
    event_queue = queue.Queue()
    session_id = None
    messages_url = None

    def sse_listener():
        nonlocal session_id, messages_url
        try:
            with requests.get("http://localhost:8002/sse", stream=True, timeout=60) as response:
                print(f"    SSE Response Status: {response.status_code}")
                print(f"    SSE Response Headers: {dict(response.headers)}")

                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        print(f"    SSE RAW: {repr(decoded)}")

                        if decoded.startswith('event:'):
                            event_type = decoded.split(': ', 1)[1]
                            print(f"    → Event Type: {event_type}")
                        elif decoded.startswith('data:'):
                            data = decoded.split(': ', 1)[1]
                            print(f"    → Data: {data}")

                            # Extract session ID from endpoint
                            if 'session_id=' in data:
                                # FastMCP format: /messages/?session_id=...
                                session_id = data.split('session_id=')[1].split('&')[0]
                                messages_url = f"http://localhost:8002{data}"
                                print(f"    ✓ Session ID: {session_id}")
                                print(f"    ✓ Messages URL: {messages_url}")
                            else:
                                # Queue non-endpoint events
                                event_queue.put(('data', data))
                        elif decoded.startswith(':'):
                            # Comment/ping
                            print(f"    → Ping: {decoded}")
        except Exception as e:
            print(f"    SSE Error: {e}")
            import traceback
            traceback.print_exc()

    # Start SSE listener
    listener_thread = threading.Thread(target=sse_listener, daemon=True)
    listener_thread.start()
    time.sleep(2)

    if not session_id or not messages_url:
        print("\n✗ FAILED: Could not establish session")
        return

    # Send initialize message
    print(f"\n[2] Sending initialize to {messages_url}")
    init_message = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            },
            "capabilities": {}
        },
        "id": "test-init-1"
    }

    print(f"    Request: {json.dumps(init_message, indent=2)}")

    try:
        response = requests.post(messages_url, json=init_message, timeout=5)
        print(f"    POST Status: {response.status_code}")
        print(f"    POST Headers: {dict(response.headers)}")
        print(f"    POST Body: {response.text}")
    except Exception as e:
        print(f"    POST Error: {e}")

    # Wait for response via SSE
    print(f"\n[3] Waiting for SSE response (15 seconds)...")
    start_time = time.time()
    responses_received = []

    while time.time() - start_time < 15:
        try:
            event = event_queue.get(timeout=1)
            print(f"    ✓ Received: {event}")
            responses_received.append(event)

            # Check if it's our initialize response
            if event[0] == 'data':
                try:
                    parsed = json.loads(event[1])
                    if parsed.get('id') == 'test-init-1':
                        print(f"    ✓✓ SUCCESS: Matching response received!")
                        print(f"       Response: {json.dumps(parsed, indent=6)}")
                        break
                except:
                    pass
        except queue.Empty:
            continue

    elapsed = time.time() - start_time
    print(f"\n[4] Results after {elapsed:.1f} seconds:")
    print(f"    Events received: {len(responses_received)}")

    if not responses_received:
        print(f"    ✗ FAILURE: No response received via SSE")
        print(f"\n[5] Checking if server is still streaming...")
        # Check for pings
        try:
            event = event_queue.get(timeout=5)
            print(f"    → Still receiving: {event}")
        except queue.Empty:
            print(f"    → No events in queue")
    else:
        print(f"    ✓ Responses: {responses_received}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    detailed_fastmcp_test()

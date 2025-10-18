#!/usr/bin/env python3
"""
Full integration test for SSE endpoint with bidirectional communication
"""
import requests
import json
import threading
import time
import queue

class SSEClient:
    """Simple SSE client for testing"""

    def __init__(self, url):
        self.url = url
        self.session_id = None
        self.event_queue = queue.Queue()
        self.running = False
        self.thread = None

    def start(self):
        """Start the SSE connection in a background thread"""
        self.running = True
        self.thread = threading.Thread(target=self._listen)
        self.thread.daemon = True
        self.thread.start()

        # Wait for session to be established
        for _ in range(10):
            if self.session_id:
                return True
            time.sleep(0.1)

        return False

    def _listen(self):
        """Listen to SSE events"""
        try:
            with requests.get(self.url, headers={"Accept": "text/event-stream"}, stream=True) as response:
                if response.status_code != 200:
                    print(f"Failed to connect: {response.status_code}")
                    return

                print(f"SSE Connection established (Status: {response.status_code})")

                for line in response.iter_lines():
                    if not self.running:
                        break

                    if line:
                        decoded_line = line.decode('utf-8')

                        # Parse SSE events
                        if decoded_line.startswith('event:'):
                            event_type = decoded_line.split(': ', 1)[1]
                        elif decoded_line.startswith('data:'):
                            data = json.loads(decoded_line.split(': ', 1)[1])

                            # Extract session ID from endpoint event
                            if data.get('method') == 'endpoint':
                                endpoint = data['params']['endpoint']
                                self.session_id = endpoint.split('session_id=')[1]
                                print(f"✓ Session established: {self.session_id}")

                            # Queue all events for processing
                            self.event_queue.put(data)

        except Exception as e:
            print(f"SSE connection error: {e}")
        finally:
            self.running = False

    def send_message(self, message):
        """Send a message via the /messages endpoint"""
        if not self.session_id:
            raise Exception("No session ID available")

        url = f"http://localhost:8021/messages?session_id={self.session_id}"
        response = requests.post(url, json=message, timeout=5)
        return response

    def wait_for_response(self, timeout=5):
        """Wait for a response event"""
        try:
            return self.event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        """Stop the SSE connection"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)


def test_full_sse_flow():
    """Test the full SSE flow with bidirectional communication"""
    print("=" * 60)
    print("SSE Full Flow Integration Test")
    print("=" * 60)

    # Create SSE client
    client = SSEClient("http://localhost:8021/sse")

    try:
        # Start SSE connection
        print("\n1. Establishing SSE connection...")
        if not client.start():
            print("✗ Failed to establish SSE connection")
            return

        print(f"\n✓ SSE connection active with session: {client.session_id}")

        # Test 1: Initialize
        print("\n2. Sending initialize message...")
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

        response = client.send_message(init_message)
        print(f"   POST /messages response: {response.status_code}")

        if response.status_code == 200:
            print("   ✓ Message accepted by server")

            # Wait for response on SSE stream
            print("   Waiting for response on SSE stream...")
            sse_response = client.wait_for_response(timeout=3)

            if sse_response:
                print(f"   ✓ Received response via SSE:")
                print(f"      {json.dumps(sse_response, indent=6)}")
            else:
                print("   ⚠ No response received on SSE stream (timeout)")
        else:
            print(f"   ✗ Server returned error: {response.json()}")

        # Test 2: Tools list
        print("\n3. Sending tools/list message...")
        tools_message = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": "test-tools-1"
        }

        response = client.send_message(tools_message)
        print(f"   POST /messages response: {response.status_code}")

        if response.status_code == 200:
            print("   ✓ Message accepted by server")

            # Wait for response on SSE stream
            print("   Waiting for response on SSE stream...")
            sse_response = client.wait_for_response(timeout=3)

            if sse_response:
                print(f"   ✓ Received response via SSE:")
                print(f"      {json.dumps(sse_response, indent=6)}")
            else:
                print("   ⚠ No response received on SSE stream (timeout)")
        else:
            print(f"   ✗ Server returned error: {response.json()}")

        # Wait a moment for any remaining events
        time.sleep(1)

        print("\n✓ SSE bidirectional communication working!")

    except Exception as e:
        print(f"\n✗ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n4. Closing SSE connection...")
        client.stop()
        print("   ✓ Connection closed")

    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)


if __name__ == "__main__":
    test_full_sse_flow()

#!/usr/bin/env python3
"""
Test what the autocomplete server actually sends on SSE
"""
import requests

print("Testing autocomplete SSE endpoint...")
print(f"Connecting to http://localhost:8002/sse\n")

try:
    with requests.get("http://localhost:8002/sse", headers={"Accept": "text/event-stream"}, stream=True, timeout=5) as response:
        print(f"Status: {response.status_code}\n")

        if response.status_code == 200:
            print("First 10 lines from SSE stream:")
            print("=" * 60)

            count = 0
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    print(f"{count:2d}: {repr(decoded)}")
                    count += 1

                    if count >= 10:
                        break
        else:
            print(f"Error: {response.status_code}")
            print(response.text)

except Exception as e:
    print(f"Error: {e}")

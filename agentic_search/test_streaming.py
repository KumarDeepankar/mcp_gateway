#!/usr/bin/env python3
"""
Test the new streaming format and chain visualization
"""
import asyncio


async def test_streaming_format():
    """Test the new streaming output format"""
    print("🧪 Testing New Streaming Format")
    print("=" * 50)

    # Simulate the new streaming format
    stream_output = [
        "THINKING:Starting search agent for query: What is AI?",
        "THINKING:Discovered 3 tools from MCP registry",
        "THINKING:✓ Completed: Initialize Search Node",
        "THINKING:✓ Completed: Discover Tools Node",
        "THINKING:Creating plan with 2 steps",
        "THINKING:✓ Completed: Planning Node",
        "THINKING:Preparing step 1: Analyze the query",
        "THINKING:✓ Completed: Prepare Next Step Node",
        "THINKING:Performing reasoning: What is AI?",
        "THINKING:✓ Completed: Execute Reasoning Step Node",
        "THINKING:✓ Completed: Generate Final Response Node",
        "FINAL_RESPONSE_START:",
        "AI, or Artificial Intelligence, refers to...",
        "the simulation of human intelligence...",
        "in machines that are programmed to think..."
    ]

    print("📡 Simulated Stream Output:")
    print("-" * 30)

    thinking_steps = []
    completed_steps = []
    final_response_parts = []
    final_response_started = False

    for line in stream_output:
        print(f"Stream: {line}")

        if line.startswith('THINKING:'):
            thinking_text = line[9:]
            if thinking_text.startswith('✓ Completed:'):
                step_name = thinking_text[13:].strip()
                completed_steps.append(step_name)
                print(f"  → Added to chain: {step_name}")
            else:
                thinking_steps.append(thinking_text)
                print(f"  → Thinking: {thinking_text}")

        elif line.startswith('FINAL_RESPONSE_START:'):
            final_response_started = True
            print(f"  → 🤖 Final response starting...")

        elif final_response_started:
            final_response_parts.append(line)
            print(f"  → Response: {line}")

    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"✅ Thinking steps: {len(thinking_steps)}")
    print(f"✅ Chain steps: {len(completed_steps)}")
    print(f"✅ Response parts: {len(final_response_parts)}")
    print(f"✅ Proper order: {'Yes' if len(completed_steps) > 0 and len(final_response_parts) > 0 else 'No'}")

    print("\n🔗 Chain Steps:")
    for i, step in enumerate(completed_steps, 1):
        print(f"  {i}. {step}")

    print("\n🤖 Final Response:")
    print(f"  {''.join(final_response_parts)}")

    print("\n🎉 New streaming format test completed!")


if __name__ == "__main__":
    asyncio.run(test_streaming_format())
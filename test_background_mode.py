#!/usr/bin/env python3
"""
Test OpenAI's background mode (deep research) basic functionality.
"""

import os
import time
from openai import OpenAI

def test_basic_background_mode():
    """Test basic background mode execution and polling."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("TEST 1: Basic Background Mode")
    print("=" * 80)

    # Start a background task
    print("\n1. Creating background response...")
    resp = client.responses.create(
        model="gpt-5.2",
        input="Write a detailed analysis of how distributed systems handle consistency. Include CAP theorem, eventual consistency, and practical examples.",
        background=True,
    )

    print(f"Response ID: {resp.id}")
    print(f"Initial status: {resp.status}")
    print(f"Response object keys: {list(resp.__dict__.keys())}")

    # Poll for completion
    print("\n2. Polling for completion...")
    start_time = time.time()
    poll_count = 0

    while resp.status in {"queued", "in_progress"}:
        poll_count += 1
        elapsed = time.time() - start_time
        print(f"Poll #{poll_count} - Status: {resp.status} (elapsed: {elapsed:.1f}s)")
        time.sleep(2)
        resp = client.responses.retrieve(resp.id)

    total_time = time.time() - start_time
    print(f"\n3. Final status: {resp.status}")
    print(f"Total time: {total_time:.1f}s")
    print(f"Total polls: {poll_count}")

    # Print response details
    if hasattr(resp, 'output_text') and resp.output_text:
        print(f"\n4. Output text (first 200 chars):\n{resp.output_text[:200]}...")

    if hasattr(resp, 'error'):
        print(f"\nError: {resp.error}")

    return resp


def test_background_streaming():
    """Test background mode with streaming enabled."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 2: Background Mode with Streaming")
    print("=" * 80)

    print("\n1. Creating background response with streaming...")
    stream = client.responses.create(
        model="gpt-5.2",
        input="Explain the concept of zero-knowledge proofs in cryptography with a simple example.",
        background=True,
        stream=True,
    )

    print("2. Streaming events:")
    cursor = None
    event_count = 0

    try:
        for event in stream:
            event_count += 1
            cursor = getattr(event, 'sequence_number', None)

            # Print first few events in detail, then just count
            if event_count <= 5:
                print(f"Event #{event_count}: {event}")
            elif event_count % 10 == 0:
                print(f"Event #{event_count} (cursor: {cursor})")

    except Exception as e:
        print(f"\nStream error: {e}")

    print(f"\n3. Stream completed. Total events: {event_count}")
    print(f"Final cursor: {cursor}")


def test_cancellation():
    """Test cancelling a background response."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 3: Background Response Cancellation")
    print("=" * 80)

    # Start a background task
    print("\n1. Creating background response...")
    resp = client.responses.create(
        model="gpt-5.2",
        input="Write a comprehensive 10,000 word essay on the history of computing.",
        background=True,
    )

    print(f"Response ID: {resp.id}")
    print(f"Initial status: {resp.status}")

    # Wait a moment, then cancel
    print("\n2. Waiting 5 seconds before cancellation...")
    time.sleep(5)

    print("3. Cancelling response...")
    cancelled_resp = client.responses.cancel(resp.id)
    print(f"Status after cancellation: {cancelled_resp.status}")

    # Try cancelling again (should be idempotent)
    print("\n4. Attempting second cancellation (should be idempotent)...")
    cancelled_resp2 = client.responses.cancel(resp.id)
    print(f"Status after second cancellation: {cancelled_resp2.status}")

    return cancelled_resp


if __name__ == "__main__":
    try:
        # Test 1: Basic background mode
        result1 = test_basic_background_mode()

        # Test 2: Background streaming
        test_background_streaming()

        # Test 3: Cancellation
        result3 = test_cancellation()

        print("\n" + "=" * 80)
        print("All tests completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

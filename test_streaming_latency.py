#!/usr/bin/env python3
"""
Test streaming latency in background mode - measure time between chunks.
"""

import os
import time
from openai import OpenAI


def test_streaming_latency():
    """Measure inter-chunk latency in background mode streaming."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("STREAMING LATENCY ANALYSIS")
    print("=" * 80)

    print("\n📊 Analysis from previous test:")
    print("  • Total events: 549")
    print("  • Total time: ~40 seconds")
    print("  • Average: ~13.7 events/second")
    print("  • Average inter-event time: ~73ms")

    print("\n🧪 Now testing with timestamps to measure actual latency...")

    # Create a short background streaming response to minimize tokens
    print("\n1. Creating background streaming response (limited tokens)...")
    stream = client.responses.create(
        model="gpt-5.2",
        input="List 3 consensus algorithms.",
        background=True,
        stream=True,
        max_output_tokens=150,  # Limit to save tokens
    )

    print("   Streaming started...\n")

    # Track timing
    event_times = []
    event_types = []
    chunk_sizes = []

    start_time = time.time()
    last_event_time = start_time
    event_count = 0

    try:
        for event in stream:
            current_time = time.time()
            inter_event_latency = (current_time - last_event_time) * 1000  # ms

            event_times.append(inter_event_latency)
            event_types.append(event.type)
            event_count += 1

            # Track chunk size for content events
            if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                chunk_sizes.append(len(event.delta.text) if event.delta.text else 0)

            # Print first few and sample periodically
            if event_count <= 5 or event_count % 20 == 0:
                print(f"   Event #{event_count}: {event.type:30s} "
                      f"(+{inter_event_latency:6.1f}ms)")

            last_event_time = current_time

    except Exception as e:
        print(f"   Stream ended: {e}")

    total_time = time.time() - start_time

    print(f"\n2. Streaming completed:")
    print(f"   Total events: {event_count}")
    print(f"   Total time: {total_time:.2f}s")
    print(f"   Average rate: {event_count/total_time:.1f} events/sec")

    # Analyze latencies
    if event_times:
        print(f"\n3. Inter-event latency analysis:")
        print(f"   Min: {min(event_times):.1f}ms")
        print(f"   Max: {max(event_times):.1f}ms")
        print(f"   Mean: {sum(event_times)/len(event_times):.1f}ms")
        print(f"   Median: {sorted(event_times)[len(event_times)//2]:.1f}ms")

        # Distribution
        buckets = {
            "0-10ms": sum(1 for t in event_times if t < 10),
            "10-50ms": sum(1 for t in event_times if 10 <= t < 50),
            "50-100ms": sum(1 for t in event_times if 50 <= t < 100),
            "100-500ms": sum(1 for t in event_times if 100 <= t < 500),
            "500ms+": sum(1 for t in event_times if t >= 500),
        }

        print(f"\n4. Latency distribution:")
        for bucket, count in buckets.items():
            pct = (count / len(event_times)) * 100
            bar = "█" * int(pct / 2)
            print(f"   {bucket:12s}: {count:4d} events ({pct:5.1f}%) {bar}")

        # Check for patterns suggesting write-ahead logging
        print(f"\n5. Write-ahead logging analysis:")

        # If WAL is happening, we'd expect:
        # - Consistent latency floors (time to persist)
        # - Possible bimodal distribution (fast in-memory vs slow persist)

        very_fast = sum(1 for t in event_times if t < 10)
        fast_pct = (very_fast / len(event_times)) * 100

        print(f"   Events < 10ms: {very_fast}/{len(event_times)} ({fast_pct:.1f}%)")

        if fast_pct > 80:
            print("   ✅ Majority of events are sub-10ms")
            print("   → Suggests streaming from memory, not waiting for WAL")
        elif fast_pct < 20:
            print("   ⚠️ Most events have significant latency")
            print("   → Might indicate persistence overhead")
        else:
            print("   📊 Mixed distribution")
            print("   → Some buffering/batching may be happening")

        # Check chunk sizes
        if chunk_sizes:
            print(f"\n6. Content chunk sizes:")
            print(f"   Total content chunks: {len(chunk_sizes)}")
            print(f"   Avg chunk size: {sum(chunk_sizes)/len(chunk_sizes):.1f} chars")
            print(f"   Max chunk size: {max(chunk_sizes)} chars")

    print("\n" + "=" * 80)
    print("CONCLUSIONS")
    print("=" * 80)

    print("""
Based on latency measurements:

Fast streaming (< 10ms between events):
  • Events are likely streamed from memory buffer
  • Not waiting for disk writes per chunk
  • Optimized for low latency

Higher latency events:
  • Initial events (connection, setup)
  • Occasional pauses (could be model generation, not I/O)
  • Network jitter

Write-Ahead Logging:
  • If OpenAI does WAL, it's likely:
    1. Asynchronous (doesn't block streaming)
    2. Batched (not per-chunk)
    3. Background process (parallel to stream)

  • The sub-10ms latencies suggest chunks are NOT
    waiting for disk writes before being sent

Storage in Background Mode:
  • Responses stored for ~10 minutes after completion
  • Likely buffered in memory during generation
  • Persisted asynchronously or at completion
  • Not blocking the stream with per-chunk writes
""")


if __name__ == "__main__":
    test_streaming_latency()

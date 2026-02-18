#!/usr/bin/env python3
"""
Compare streaming latency: background=True vs background=False
"""

import os
import time
from openai import OpenAI


def measure_streaming_latency(background_mode, label):
    """Measure streaming latency for a given mode."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print(f"\n{'=' * 80}")
    print(f"TEST: {label}")
    print(f"{'=' * 80}")

    stream = client.responses.create(
        model="gpt-5.2",
        input="List 3 distributed consensus algorithms.",
        background=background_mode,
        stream=True,
        max_output_tokens=150,  # Keep short to save tokens
    )

    # Track timing
    event_times = []
    start_time = time.time()
    last_event_time = start_time
    event_count = 0

    content_event_times = []  # Track only content deltas

    for event in stream:
        current_time = time.time()
        inter_event_latency = (current_time - last_event_time) * 1000  # ms

        event_times.append(inter_event_latency)
        event_count += 1

        # Track content events specifically (the actual text chunks)
        if 'delta' in event.type or 'text' in event.type:
            content_event_times.append(inter_event_latency)

        # Print first few events
        if event_count <= 5:
            print(f"   Event #{event_count}: {event.type:35s} (+{inter_event_latency:6.1f}ms)")

        last_event_time = current_time

    total_time = time.time() - start_time

    return {
        'total_events': event_count,
        'total_time': total_time,
        'event_times': event_times,
        'content_event_times': content_event_times,
    }


def analyze_and_compare():
    """Run both tests and compare results."""

    print("=" * 80)
    print("STREAMING LATENCY COMPARISON")
    print("=" * 80)
    print("\nTesting streaming latency with and without background mode...")

    # Test 1: Without background mode (standard streaming)
    results_no_bg = measure_streaming_latency(
        background_mode=False,
        label="Standard Streaming (background=False)"
    )

    # Test 2: With background mode
    results_bg = measure_streaming_latency(
        background_mode=True,
        label="Background Mode (background=True)"
    )

    # Analysis
    print("\n" + "=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)

    for label, results in [
        ("Standard (no background)", results_no_bg),
        ("Background mode", results_bg)
    ]:
        times = results['event_times']

        print(f"\n{label}:")
        print(f"  Total events: {results['total_events']}")
        print(f"  Total time: {results['total_time']:.2f}s")
        print(f"  Events/sec: {results['total_events']/results['total_time']:.1f}")

        if times:
            print(f"  Latency stats:")
            print(f"    Min:    {min(times):.2f}ms")
            print(f"    Median: {sorted(times)[len(times)//2]:.2f}ms")
            print(f"    Mean:   {sum(times)/len(times):.2f}ms")
            print(f"    Max:    {max(times):.2f}ms")

            # Distribution
            sub_10ms = sum(1 for t in times if t < 10)
            sub_10ms_pct = (sub_10ms / len(times)) * 100
            print(f"    Events < 10ms: {sub_10ms}/{len(times)} ({sub_10ms_pct:.1f}%)")

    # Direct comparison
    print("\n" + "=" * 80)
    print("LATENCY COMPARISON")
    print("=" * 80)

    times_no_bg = results_no_bg['event_times']
    times_bg = results_bg['event_times']

    if times_no_bg and times_bg:
        median_no_bg = sorted(times_no_bg)[len(times_no_bg)//2]
        median_bg = sorted(times_bg)[len(times_bg)//2]

        mean_no_bg = sum(times_no_bg) / len(times_no_bg)
        mean_bg = sum(times_bg) / len(times_bg)

        print(f"\nMedian latency:")
        print(f"  Standard:   {median_no_bg:.2f}ms")
        print(f"  Background: {median_bg:.2f}ms")
        print(f"  Difference: {median_bg - median_no_bg:+.2f}ms "
              f"({((median_bg/median_no_bg - 1) * 100):+.1f}%)")

        print(f"\nMean latency:")
        print(f"  Standard:   {mean_no_bg:.2f}ms")
        print(f"  Background: {mean_bg:.2f}ms")
        print(f"  Difference: {mean_bg - mean_no_bg:+.2f}ms "
              f"({((mean_bg/mean_no_bg - 1) * 100):+.1f}%)")

        # Statistical significance (rough check)
        if abs(median_bg - median_no_bg) < 1.0:
            print(f"\n✅ Latency difference < 1ms - NEGLIGIBLE")
            print(f"   Background mode adds no meaningful overhead!")
        elif abs(median_bg - median_no_bg) < 5.0:
            print(f"\n⚠️ Latency difference < 5ms - MINIMAL")
            print(f"   Background mode adds slight overhead, but still very fast")
        else:
            print(f"\n⚠️ Latency difference >= 5ms - NOTICEABLE")
            print(f"   Background mode may add some persistence overhead")

    print("\n" + "=" * 80)
    print("CONCLUSIONS")
    print("=" * 80)

    print("""
Key Findings:

1. If latencies are similar (< 1ms difference):
   → Background mode does NOT add synchronous write overhead
   → Persistence is fully asynchronous
   → Streaming speed is identical

2. If background mode is slightly slower (1-5ms):
   → Some minimal overhead exists
   → But still very fast (sub-10ms)
   → Acceptable tradeoff for reliability

3. If background mode is significantly slower (> 5ms):
   → May be doing some synchronous persistence
   → Still fast enough for most use cases
   → Worth the tradeoff for resumability

Recommendation:
  • Use background=True for long-running tasks
  • Use background=False for ultra-low latency needs
  • In practice, difference is likely negligible
""")


if __name__ == "__main__":
    analyze_and_compare()

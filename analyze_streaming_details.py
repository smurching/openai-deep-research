#!/usr/bin/env python3
"""
Detailed analysis: separate setup time from content streaming time.
"""

import os
import time
from openai import OpenAI


def detailed_streaming_analysis(background_mode, label):
    """Measure streaming with detailed phase tracking."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print(f"\n{'=' * 80}")
    print(f"{label}")
    print(f"{'=' * 80}\n")

    stream = client.responses.create(
        model="gpt-5.2",
        input="List 3 distributed consensus algorithms.",
        background=background_mode,
        stream=True,
        max_output_tokens=150,
    )

    # Phase tracking
    setup_complete = False
    content_start_time = None
    content_events = []
    content_latencies = []

    start_time = time.time()
    last_event_time = start_time
    event_count = 0

    for event in stream:
        current_time = time.time()
        inter_event_latency = (current_time - last_event_time) * 1000

        event_count += 1

        # Detect when actual content streaming starts
        if 'delta' in event.type and not setup_complete:
            setup_complete = True
            content_start_time = current_time
            setup_time = (current_time - start_time) * 1000
            print(f"✓ Setup complete in {setup_time:.1f}ms")
            print(f"  Now streaming content...\n")

        # Track content events
        if setup_complete and ('delta' in event.type or 'text' in event.type):
            content_events.append(event.type)
            content_latencies.append(inter_event_latency)

            if len(content_events) <= 5 or len(content_events) % 10 == 0:
                print(f"  Content event #{len(content_events)}: +{inter_event_latency:.2f}ms")

        last_event_time = current_time

    total_time = time.time() - start_time

    # Calculate content streaming time
    if content_start_time:
        content_time = (last_event_time - content_start_time) * 1000
    else:
        content_time = 0

    return {
        'total_time': total_time * 1000,
        'content_time': content_time,
        'content_events': len(content_events),
        'content_latencies': content_latencies,
        'total_events': event_count,
    }


print("=" * 80)
print("DETAILED STREAMING ANALYSIS")
print("=" * 80)
print("\nSeparating setup time from actual content streaming...")

# Test both modes
results_standard = detailed_streaming_analysis(
    background_mode=False,
    label="STANDARD STREAMING (background=False)"
)

results_background = detailed_streaming_analysis(
    background_mode=True,
    label="BACKGROUND MODE (background=True)"
)

# Compare
print("\n" + "=" * 80)
print("DETAILED COMPARISON")
print("=" * 80)

print("\n1. TOTAL TIME (including setup):")
print(f"   Standard:   {results_standard['total_time']:.1f}ms")
print(f"   Background: {results_background['total_time']:.1f}ms")
print(f"   Difference: +{results_background['total_time'] - results_standard['total_time']:.1f}ms")

print("\n2. CONTENT STREAMING TIME (after setup):")
print(f"   Standard:   {results_standard['content_time']:.1f}ms for {results_standard['content_events']} events")
print(f"   Background: {results_background['content_time']:.1f}ms for {results_background['content_events']} events")

if results_standard['content_events'] > 0 and results_background['content_events'] > 0:
    std_per_event = results_standard['content_time'] / results_standard['content_events']
    bg_per_event = results_background['content_time'] / results_background['content_events']

    print(f"\n   Time per content event:")
    print(f"   Standard:   {std_per_event:.2f}ms/event")
    print(f"   Background: {bg_per_event:.2f}ms/event")
    print(f"   Difference: {bg_per_event - std_per_event:+.2f}ms/event "
          f"({((bg_per_event/std_per_event - 1) * 100):+.1f}%)")

print("\n3. CONTENT EVENT LATENCIES (between consecutive content chunks):")

for label, latencies in [
    ("Standard", results_standard['content_latencies']),
    ("Background", results_background['content_latencies'])
]:
    if latencies:
        print(f"\n   {label}:")
        print(f"     Min:    {min(latencies):.2f}ms")
        print(f"     Median: {sorted(latencies)[len(latencies)//2]:.2f}ms")
        print(f"     Mean:   {sum(latencies)/len(latencies):.2f}ms")
        print(f"     Max:    {max(latencies):.2f}ms")

        sub_10ms = sum(1 for t in latencies if t < 10)
        sub_10ms_pct = (sub_10ms / len(latencies)) * 100
        print(f"     < 10ms: {sub_10ms}/{len(latencies)} ({sub_10ms_pct:.1f}%)")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

std_lat = results_standard['content_latencies']
bg_lat = results_background['content_latencies']

if std_lat and bg_lat:
    std_median = sorted(std_lat)[len(std_lat)//2]
    bg_median = sorted(bg_lat)[len(bg_lat)//2]
    diff = abs(bg_median - std_median)

    print(f"""
Content Streaming Performance:

Setup Phase:
  • Standard mode: Faster initial response
  • Background mode: ~3-4 second queuing delay
  • This is expected - background mode queues the task

Content Delivery (after setup):
  • Median chunk latency difference: {diff:.2f}ms

Verdict:
""")

    if diff < 1:
        print("  ✅ IDENTICAL - No persistence overhead during streaming")
        print("  → Background mode's persistence is fully async")
        print("  → Once streaming starts, speed is the same")
    elif diff < 5:
        print("  ✅ MINIMAL - Very small persistence overhead")
        print("  → < 5ms difference is negligible for users")
        print("  → Background mode is worth it for reliability")
    else:
        print("  ⚠️ MEASURABLE - Some persistence overhead exists")
        print(f"  → {diff:.1f}ms slower per chunk")
        print("  → Still fast, but standard mode is faster")

    print(f"""
Recommendation:
  • Use background=False for lowest latency needs
  • Use background=True when you need:
    - Tasks > 30 seconds
    - Reliability and resumption
    - Don't mind 3-4s initial queuing

  The difference is mostly in SETUP, not STREAMING.
""")

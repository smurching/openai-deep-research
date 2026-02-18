#!/usr/bin/env python3
"""
Test streaming update frequency for deep research-style requests.

Uses o3 + web_search_preview tool in background mode to approximate
deep research behavior, and measures how often streaming events arrive.
"""

import os
import time
from openai import OpenAI


def test_deep_research_streaming():
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 70)
    print("TEST: Deep Research Streaming Event Frequency")
    print("=" * 70)
    print("\nPrompt: short research question with web search tool")
    print("Model: o3 + web_search_preview, background=True, stream=True\n")

    events = []  # (timestamp, event_type, detail)
    start_time = time.time()

    stream = client.responses.create(
        model="o3",
        input="What is the current version of Python? Just the version number.",
        background=True,
        stream=True,
        tools=[{"type": "web_search_preview"}],
        max_output_tokens=200,
    )

    last_time = start_time
    for event in stream:
        now = time.time()
        gap_ms = (now - last_time) * 1000
        elapsed = now - start_time

        event_type = type(event).__name__

        # Extract useful detail depending on event type
        detail = ""
        if hasattr(event, "delta") and isinstance(event.delta, str):
            detail = repr(event.delta[:40])
        elif hasattr(event, "type"):
            detail = event.type

        events.append((elapsed, gap_ms, event_type, detail))
        last_time = now

    total_time = time.time() - start_time

    # Print all events
    print(f"{'Elapsed':>8}  {'Gap':>8}  Event type / detail")
    print("-" * 70)
    for elapsed, gap, etype, detail in events:
        print(f"{elapsed:7.2f}s  {gap:7.1f}ms  {etype}  {detail}")

    print()
    print(f"Total time: {total_time:.1f}s")
    print(f"Total events: {len(events)}")

    # Categorize events
    text_deltas = [(e, g, d) for (e, g, et, d) in events if et == "ResponseTextDeltaEvent" or (et != "ResponseTextDeltaEvent" and "delta" in et.lower())]
    delta_events = [(e, g, et, d) for (e, g, et, d) in events if hasattr(et, '__contains__') and "delta" in et.lower()]

    # Find text deltas specifically
    text_delta_events = [(e, g, et, d) for (e, g, et, d) in events if "delta" in et.lower() or "text" in et.lower()]

    # Gap analysis: gaps > 1 second (likely waiting for tool/reasoning)
    big_gaps = [(e, g, et, d) for (e, g, et, d) in events if g > 1000]
    print(f"\nGaps > 1 second: {len(big_gaps)}")
    for elapsed, gap, etype, detail in big_gaps:
        print(f"  @ {elapsed:.2f}s: {gap/1000:.1f}s gap before {etype}  {detail}")

    # Summary by event type
    from collections import Counter
    type_counts = Counter(et for (_, _, et, _) in events)
    print("\nEvent type counts:")
    for etype, count in type_counts.most_common():
        print(f"  {count:4d}  {etype}")


if __name__ == "__main__":
    test_deep_research_streaming()

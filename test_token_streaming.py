#!/usr/bin/env python3
"""
Test the granularity and latency of streaming tokens in background mode.

Key question: Does text arrive token-by-token or in larger buffered chunks?
"""

import os
import time
from openai import OpenAI


def test_token_streaming():
    """Measure chunk sizes and inter-chunk timing for output_text.delta events."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 70)
    print("TEST: Token Streaming Granularity in Background Mode")
    print("=" * 70)
    print("\nStreaming a short response to measure chunk sizes...\n")

    deltas = []  # (timestamp, text)
    last_time = None
    start_time = time.time()
    first_delta_time = None

    stream = client.responses.create(
        model="gpt-4o-mini",
        input="List 5 fruits, one per line, nothing else.",
        background=True,
        stream=True,
        max_output_tokens=60,
    )

    for event in stream:
        now = time.time()
        event_type = type(event).__name__

        # Capture output_text.delta events (the actual text chunks)
        if hasattr(event, "delta") and isinstance(event.delta, str):
            if first_delta_time is None:
                first_delta_time = now
            gap_ms = (now - last_time) * 1000 if last_time else 0
            deltas.append((now, event.delta, gap_ms))
            last_time = now
        elif last_time is None:
            last_time = now

    total_time = time.time() - start_time

    if not deltas:
        print("No text deltas captured. Check event types.")
        return

    # Analysis
    texts = [d[1] for d in deltas]
    gaps = [d[2] for d in deltas[1:]]  # skip first (no prior event)
    sizes = [len(t) for t in texts]

    full_text = "".join(texts)

    print(f"Full output: {repr(full_text)}\n")
    print(f"Total time: {total_time:.2f}s")
    print(f"Time to first delta: {(first_delta_time - start_time):.2f}s" if first_delta_time else "")
    print(f"Number of delta events: {len(deltas)}")
    print(f"Total characters: {len(full_text)}")
    print()

    print("--- Delta chunk sizes ---")
    print(f"  Min:    {min(sizes)} chars")
    print(f"  Max:    {max(sizes)} chars")
    print(f"  Median: {sorted(sizes)[len(sizes)//2]} chars")
    print(f"  Mean:   {sum(sizes)/len(sizes):.1f} chars")
    print()

    if gaps:
        print("--- Inter-delta latency (ms) ---")
        print(f"  Min:    {min(gaps):.1f}ms")
        print(f"  Max:    {max(gaps):.1f}ms")
        print(f"  Median: {sorted(gaps)[len(gaps)//2]:.1f}ms")
        print(f"  Mean:   {sum(gaps)/len(gaps):.1f}ms")
        print()

    print("--- First 20 deltas (text | chars | gap_ms) ---")
    for i, (ts, text, gap) in enumerate(deltas[:20]):
        print(f"  [{i:2d}] {repr(text):20s}  {len(text):3d} chars  {gap:6.1f}ms")

    # Classify: token-by-token vs buffered
    avg_size = sum(sizes) / len(sizes)
    print()
    if avg_size <= 5:
        verdict = "TOKEN-BY-TOKEN (avg ~1-2 tokens per chunk)"
    elif avg_size <= 20:
        verdict = "SMALL CHUNKS (a few words per chunk)"
    else:
        verdict = "BUFFERED CHUNKS (larger blocks of text)"

    print(f"==> Verdict: {verdict} (avg {avg_size:.1f} chars/chunk)")


if __name__ == "__main__":
    test_token_streaming()

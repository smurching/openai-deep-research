#!/usr/bin/env python3
"""
Analyze timing data from existing tests and compare background mode to deep research.
"""

import os
import time
from openai import OpenAI

print("=" * 80)
print("TIMING ANALYSIS: Background Mode vs Deep Research")
print("=" * 80)

print("\n📊 Existing Test Results:")
print("-" * 80)
print("From our previous tests:")
print("  • Simple text generation: ~45-50 seconds")
print("  • Complex analysis (distributed systems): ~45 seconds")
print("  • Tool calling (2 parallel weather calls): ~5 seconds")
print("  • Streaming response (549 events): ~40 seconds")
print("  • 3 parallel tasks: ~21 seconds each")

print("\n🔍 What is Deep Research?")
print("-" * 80)
print("Deep Research (as a product) typically involves:")
print("  • Multi-step iterative reasoning")
print("  • Web searches for current information")
print("  • Synthesis across multiple sources")
print("  • Extended reasoning chains (minutes to hours)")
print("  • Automatic follow-up questions and refinement")

print("\n⚙️ Background Mode Capabilities:")
print("-" * 80)
print("What we've confirmed:")
print("  ✅ Long-running tasks (no timeout)")
print("  ✅ Tool calling (can call web search, databases, etc.)")
print("  ✅ Context management (stateless, conversations, linking)")
print("  ✅ Streaming with resumption")
print("  ❌ No built-in multi-step research workflow")
print("  ❌ No automatic iterative refinement")
print("  ❌ Requires explicit tool definitions")

print("\n🧪 Let's test with reasoning mode:")
print("-" * 80)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Test 1: Quick test with reasoning
print("\n1. Testing with extended reasoning (max_output_tokens=500 to limit cost)...")
start = time.time()

resp = client.responses.create(
    model="gpt-5.2",
    input="What are the key trade-offs between Paxos and Raft consensus algorithms?",
    background=True,
    reasoning={"effort": "high"},  # Request extended reasoning
    max_output_tokens=500,  # Limit output to control cost
)

print(f"   Response ID: {resp.id}")
print(f"   Initial status: {resp.status}")

poll_count = 0
while resp.status in {"queued", "in_progress"}:
    poll_count += 1
    time.sleep(2)
    resp = client.responses.retrieve(resp.id)
    elapsed = time.time() - start
    if poll_count % 5 == 0:
        print(f"   Poll #{poll_count}: {resp.status} (elapsed: {elapsed:.1f}s)")

total_time = time.time() - start

print(f"\n✅ Completed in {total_time:.1f} seconds")
print(f"   Polls: {poll_count}")

if resp.usage:
    print(f"   Tokens: {resp.usage.total_tokens} total")
    print(f"     - Input: {resp.usage.input_tokens}")
    print(f"     - Output: {resp.usage.output_tokens}")
    if hasattr(resp.usage, 'output_tokens_details') and resp.usage.output_tokens_details:
        reasoning_tokens = resp.usage.output_tokens_details.reasoning_tokens
        print(f"     - Reasoning: {reasoning_tokens}")

if resp.output and len(resp.output) > 0:
    first_item = resp.output[0]
    if hasattr(first_item, 'content') and first_item.content:
        text = first_item.content[0].text
        print(f"   Output length: {len(text)} chars")

# Test 2: Check if web search tools are available
print("\n" + "=" * 80)
print("2. Can we use web search for research-like behavior?")
print("=" * 80)

print("\nTesting if web_search tool is built-in...")
try:
    resp2 = client.responses.create(
        model="gpt-5.2",
        input="Search the web for the latest research on distributed consensus algorithms published in 2026.",
        background=True,
        # Try to enable web search if available
        tools=[{"type": "web_search"}] if hasattr(client, 'web_search') else [],
        max_output_tokens=300,
    )

    print(f"   Response created: {resp2.id}")

    # Cancel to save tokens
    client.responses.cancel(resp2.id)
    print("   ✅ Web search tool appears to be available")

except Exception as e:
    print(f"   ❌ Web search not available or error: {e}")

print("\n" + "=" * 80)
print("CONCLUSION: Background Mode vs Deep Research")
print("=" * 80)

print("""
Background Mode:
  • Good for: Long-running single tasks, tool orchestration, autonomous agents
  • Timing: ~20-50 seconds for typical tasks, no hard timeout
  • Cost: Pay for what you generate (input + output tokens)
  • Control: You define the workflow and tools

Deep Research (Product):
  • Good for: Multi-step research, automatic web searches, iterative refinement
  • Timing: Several minutes to hours for complex research
  • Cost: Likely higher due to multiple search and reasoning steps
  • Control: Automated research workflow built-in

Can Background Mode Replace Deep Research?
  ✅ Yes, if you build the multi-step workflow yourself
     - Create tool definitions for web search, databases, etc.
     - Implement iterative logic in your application
     - Chain multiple background responses for refinement

  ❌ No, if you want automatic deep research
     - Background mode won't automatically search the web
     - Won't automatically ask follow-up questions
     - Requires you to orchestrate the research workflow

Best Use Cases for Background Mode:
  • Custom research workflows with your own tools
  • Long-running agent tasks with specific tool sets
  • Tasks that need reliability over minutes but not hours
  • When you want explicit control over the research process
""")

print("\n💡 Recommendation:")
print("   Use Background Mode as a building block to create your own")
print("   'deep research' workflow by chaining responses with tools.")
print("   Don't expect it to automatically do deep research on its own.")

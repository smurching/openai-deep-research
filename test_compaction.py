#!/usr/bin/env python3
"""
Test conversations API with compaction feature.
Questions:
1. Does compaction permanently mutate the conversation?
2. Or is it one-time compaction?
"""

import os
import time
import json
from openai import OpenAI


def test_compaction_mutation():
    """Test whether compaction mutates the conversation."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("TEST: Does Compaction Mutate the Conversation?")
    print("=" * 80)

    # Step 1: Create a conversation with initial context
    print("\n1. Creating conversation with initial items...")
    conversation = client.conversations.create(
        metadata={"topic": "compaction-test"},
        items=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "What is Paxos consensus?"}]
            }
        ]
    )

    print(f"   ✅ Conversation created: {conversation.id}")

    # Step 2: Add first response to build up history
    print("\n2. Adding first response to conversation...")
    resp1 = client.responses.create(
        model="gpt-5.2",
        input="Explain Paxos briefly.",
        background=True,
        conversation=conversation.id,
        max_output_tokens=200,  # Keep short
    )

    while resp1.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp1 = client.responses.retrieve(resp1.id)

    print(f"   ✅ Response 1 completed: {resp1.id}")
    print(f"   Output length: {len(resp1.output[0].content[0].text)} chars")

    # Step 3: Add second response
    print("\n3. Adding second response to conversation...")
    resp2 = client.responses.create(
        model="gpt-5.2",
        input="Now explain Raft briefly.",
        background=True,
        conversation=conversation.id,
        max_output_tokens=200,
    )

    while resp2.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp2 = client.responses.retrieve(resp2.id)

    print(f"   ✅ Response 2 completed: {resp2.id}")
    print(f"   Output length: {len(resp2.output[0].content[0].text)} chars")

    # Step 4: Build conversation history for compaction
    print("\n4. Building conversation history for compaction...")

    # Collect all items from the conversation
    conversation_items = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "What is Paxos consensus?"}]
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Explain Paxos briefly."}]
        },
    ]

    # Add resp1 output
    if resp1.output:
        resp1_item = {
            "type": "message",
            "role": "assistant",
            "content": resp1.output[0].content
        }
        conversation_items.append(resp1_item)

    # Add resp2 input
    conversation_items.append({
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "Now explain Raft briefly."}]
    })

    # Add resp2 output
    if resp2.output:
        resp2_item = {
            "type": "message",
            "role": "assistant",
            "content": resp2.output[0].content
        }
        conversation_items.append(resp2_item)

    print(f"   Conversation has {len(conversation_items)} items")

    # Step 5: Perform compaction
    print("\n5. Performing compaction...")
    try:
        compacted = client.responses.compact(
            model="gpt-5.2",
            input=conversation_items,
        )

        print(f"   ✅ Compaction completed!")
        print(f"   Compacted output items: {len(compacted.output)}")

        # Show compacted output structure
        if compacted.output:
            for i, item in enumerate(compacted.output):
                print(f"   Item {i}: {item.type if hasattr(item, 'type') else type(item)}")

        # Check token usage
        if compacted.usage:
            print(f"\n   Token usage:")
            print(f"   - Input: {compacted.usage.input_tokens}")
            print(f"   - Output: {compacted.usage.output_tokens}")
            print(f"   - Total: {compacted.usage.total_tokens}")

    except Exception as e:
        print(f"   ❌ Compaction failed: {e}")
        import traceback
        traceback.print_exc()
        return None

    # Step 6: Check if original conversation was mutated
    print("\n6. Checking if original conversation was mutated...")
    try:
        # Retrieve the conversation again
        retrieved_conv = client.conversations.retrieve(conversation.id)
        print(f"   ✅ Retrieved conversation: {retrieved_conv.id}")

        # Try to add a new response to the original conversation
        print("\n7. Testing if original conversation still works...")
        resp3 = client.responses.create(
            model="gpt-5.2",
            input="Compare Paxos and Raft.",
            background=True,
            conversation=conversation.id,
            max_output_tokens=200,
        )

        while resp3.status in {"queued", "in_progress"}:
            time.sleep(2)
            resp3 = client.responses.retrieve(resp3.id)

        print(f"   ✅ Response 3 completed: {resp3.id}")

        # Check if resp3 has context from previous messages
        if resp3.output and len(resp3.output) > 0:
            text = resp3.output[0].content[0].text
            print(f"\n   Response 3 output (first 200 chars):")
            print(f"   {text[:200]}...")

            # Check for context awareness
            if any(keyword in text.lower() for keyword in ['paxos', 'raft', 'both', 'comparison']):
                print(f"\n   ✅ Response 3 has context from original conversation!")
                print(f"   → Compaction did NOT mutate the original conversation")
            else:
                print(f"\n   ⚠️ Response 3 may not have full context")

    except Exception as e:
        print(f"   ❌ Error checking original conversation: {e}")

    return compacted


def test_compaction_output_format():
    """Test the format of compacted output."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST: Compacted Output Format")
    print("=" * 80)

    print("\n1. Creating a simple conversation history...")
    items = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Hello!"}]
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Hi! How can I help you today?"}]
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Tell me about consensus algorithms."}]
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Consensus algorithms like Paxos and Raft help distributed systems agree on values despite failures."}]
        },
    ]

    print(f"   Original items: {len(items)}")

    print("\n2. Compacting...")
    try:
        compacted = client.responses.compact(
            model="gpt-5.2",
            input=items,
        )

        print(f"   ✅ Compaction successful!")
        print(f"   Compacted output items: {len(compacted.output)}")

        print("\n3. Examining compacted output structure:")
        for i, item in enumerate(compacted.output):
            print(f"\n   Item {i}:")
            item_dict = item.model_dump() if hasattr(item, 'model_dump') else item.__dict__
            print(f"   {json.dumps(item_dict, indent=4, default=str)[:300]}...")

        # Test using compacted output as input to next request
        print("\n4. Using compacted output as input to new request...")
        resp = client.responses.create(
            model="gpt-5.2",
            input=compacted.output,  # Pass compacted output directly
            background=True,
            max_output_tokens=100,
        )

        while resp.status in {"queued", "in_progress"}:
            time.sleep(2)
            resp = client.responses.retrieve(resp.id)

        print(f"   ✅ New response created with compacted input!")
        print(f"   Response: {resp.id}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("COMPACTION TESTING")
    print("=" * 80)

    # Test 1: Does compaction mutate the conversation?
    compacted = test_compaction_mutation()

    # Test 2: What's the format of compacted output?
    test_compaction_output_format()

    print("\n" + "=" * 80)
    print("CONCLUSIONS")
    print("=" * 80)

    print("""
Key Questions Answered:

1. Does compaction permanently mutate the conversation?
   → Testing by adding new responses after compaction...

2. What's the format of compacted output?
   → Examining the structure and testing reusability...

3. How do you use compacted output?
   → Passing compacted.output as input to next request...

The tests above should reveal:
- Whether original conversation retains full history
- If compaction is one-time (functional) or mutating
- The structure of compacted output
- How to use compacted output in subsequent requests
""")

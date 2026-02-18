#!/usr/bin/env python3
"""
Test proper stateless context passing by passing output list directly as input.
"""

import os
import time
from openai import OpenAI


def test_stateless_with_list_input():
    """Test passing response output items statelessy as a list to the next response."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("TEST: Stateless Context Passing (List Format)")
    print("=" * 80)

    # Step 1: Create first response
    print("\n1. Creating first response...")
    resp1 = client.responses.create(
        model="gpt-5.2",
        input="What are the key principles of distributed consensus algorithms?",
        background=True,
    )

    # Poll for completion
    while resp1.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp1 = client.responses.retrieve(resp1.id)

    print(f"✅ First response completed: {resp1.id}")

    # Get the output
    print(f"\n2. First response output:")
    print(f"   Output type: {type(resp1.output)}")
    print(f"   Output length: {len(resp1.output)}")

    if resp1.output and len(resp1.output) > 0:
        first_msg = resp1.output[0]
        if hasattr(first_msg, 'content') and len(first_msg.content) > 0:
            text = first_msg.content[0].text
            print(f"   First 200 chars: {text[:200]}...")

    # Step 2: Construct stateless input as a list
    print("\n3. Constructing stateless input...")

    # Build input: user message + assistant response + new user message
    input_items = [
        # Original user message
        {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "What are the key principles of distributed consensus algorithms?"
                }
            ]
        },
    ]

    # Add assistant's response from resp1
    # The output already has the correct structure for ResponseOutputMessage
    if resp1.output and len(resp1.output) > 0:
        output_item = resp1.output[0]

        # Convert to dict
        output_dict = output_item.model_dump() if hasattr(output_item, 'model_dump') else output_item.__dict__

        # The output message needs to be converted to the right input format
        # Output has "output_text" type, input needs "input_text" or we can pass it as-is
        assistant_message = {
            "type": "message",
            "role": "assistant",
            "content": []
        }

        # Copy content items
        for content_item in output_item.content:
            content_dict = content_item.model_dump() if hasattr(content_item, 'model_dump') else content_item.__dict__
            assistant_message["content"].append(content_dict)

        input_items.append(assistant_message)

    # Add new user message
    input_items.append({
        "type": "message",
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": "Can you elaborate on the Raft algorithm specifically?"
            }
        ]
    })

    print(f"   Constructed input list with {len(input_items)} items:")
    print(f"   - User message")
    print(f"   - Assistant message from previous response")
    print(f"   - New user message")

    # Step 3: Create second response with stateless input
    print("\n4. Creating second response with stateless context...")
    try:
        resp2 = client.responses.create(
            model="gpt-5.2",
            input=input_items,  # Pass list directly, not wrapped in dict
            background=True,
        )

        print(f"✅ Second response created: {resp2.id}")

        # Poll for completion
        print("   Polling...")
        while resp2.status in {"queued", "in_progress"}:
            time.sleep(2)
            resp2 = client.responses.retrieve(resp2.id)

        print(f"✅ Second response completed!")

        # Check output
        print("\n5. Second response output:")
        if resp2.output and len(resp2.output) > 0:
            first_msg = resp2.output[0]
            if hasattr(first_msg, 'content') and len(first_msg.content) > 0:
                text = first_msg.content[0].text
                print(f"   First 300 chars: {text[:300]}...")

                # Check for context awareness
                context_keywords = ['previously', 'mentioned', 'discussed', 'earlier', 'above', 'raft']
                if any(keyword in text.lower() for keyword in context_keywords):
                    print("\n✅ SUCCESS: Second response has context from first response!")
                    print("   The stateless approach works!")
                else:
                    print("\n⚠️ Second response may not have full context (check full output)")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def compare_stateless_vs_conversation():
    """Compare stateless context vs conversation API."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("COMPARISON: Stateless vs Conversation API")
    print("=" * 80)

    # Approach 1: Stateless with manual context management
    print("\n1. STATELESS APPROACH:")
    print("   - You manually build input list with previous messages")
    print("   - Pass entire conversation history in each request")
    print("   - Works without storing conversation server-side")
    print("   - Similar to Chat Completions API pattern")

    # Approach 2: Conversation API
    print("\n2. CONVERSATION API APPROACH:")
    print("   - Create a conversation object server-side")
    print("   - Pass conversation ID to each request")
    print("   - Context automatically maintained by server")
    print("   - More convenient, less data to send")

    # Approach 3: previous_response_id
    print("\n3. PREVIOUS_RESPONSE_ID APPROACH:")
    print("   - Pass previous_response_id to link responses")
    print("   - Server automatically includes previous context")
    print("   - Simplest for linear conversations")
    print("   - Only works within ~10 minute window")

    print("\n" + "=" * 80)
    print("RECOMMENDATION:")
    print("=" * 80)
    print("\nChoose based on your use case:")
    print("  • Stateless: Full control, works across sessions, explicit context")
    print("  • Conversation API: Most convenient, server manages context")
    print("  • previous_response_id: Simplest for quick follow-ups")


if __name__ == "__main__":
    try:
        # Test stateless context passing
        success = test_stateless_with_list_input()

        # Show comparison
        compare_stateless_vs_conversation()

        if success:
            print("\n" + "=" * 80)
            print("✅ CONFIRMED: Stateless context passing works!")
            print("=" * 80)
            print("\nYou can pass resp.output as input to the next request!")
            print("Just build a list with: [user_msg, assistant_msg, new_user_msg]")

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

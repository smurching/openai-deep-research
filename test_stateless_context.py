#!/usr/bin/env python3
"""
Test if response outputs can be passed statelessly as input to next response.
"""

import os
import time
import json
from openai import OpenAI


def test_stateless_context_passing():
    """Test passing response output as input to next response."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("TEST 1: Stateless Context Passing with Items")
    print("=" * 80)

    # First response
    print("\n1. Creating first response...")
    resp1 = client.responses.create(
        model="gpt-5.2",
        input="What are the key principles of distributed consensus algorithms?",
        background=True,
    )

    # Poll for completion
    print("   Polling...")
    while resp1.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp1 = client.responses.retrieve(resp1.id)

    print(f"✅ First response completed: {resp1.id}")

    # Examine the output structure
    print("\n2. Examining output structure...")
    print(f"Output type: {type(resp1.output)}")
    print(f"Output length: {len(resp1.output)}")

    if resp1.output and len(resp1.output) > 0:
        first_item = resp1.output[0]
        print(f"First item type: {type(first_item)}")
        print(f"First item: {first_item}")

        # Try to serialize it
        item_dict = first_item.model_dump() if hasattr(first_item, 'model_dump') else first_item.__dict__
        print(f"\nSerialized item (first 500 chars):")
        print(json.dumps(item_dict, indent=2, default=str)[:500])

    # Now try to construct input with the previous output
    print("\n3. Attempting to pass output items as input to next response...")

    # Build input items list - user message + assistant response + new user message
    try:
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
            # Assistant's response from resp1
            # We'll need to convert the output format
        ]

        # Add the assistant's response
        if resp1.output and len(resp1.output) > 0:
            output_item = resp1.output[0]
            output_dict = output_item.model_dump() if hasattr(output_item, 'model_dump') else output_item.__dict__

            # Check if it's already in the right format
            print(f"\nOutput item structure:")
            print(f"  Keys: {list(output_dict.keys())}")

            # Try to add it directly
            input_items.append(output_dict)

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

        print(f"\nConstructed input with {len(input_items)} items")

        # Create second response with this input
        resp2 = client.responses.create(
            model="gpt-5.2",
            input={"items": input_items},
            background=True,
        )

        print(f"✅ Second response created: {resp2.id}")

        # Poll for completion
        print("   Polling...")
        while resp2.status in {"queued", "in_progress"}:
            time.sleep(2)
            resp2 = client.responses.retrieve(resp2.id)

        print(f"✅ Second response completed!")

        # Check if it has context
        if resp2.output and len(resp2.output) > 0:
            first_msg = resp2.output[0]
            if hasattr(first_msg, 'content') and len(first_msg.content) > 0:
                text = first_msg.content[0].text
                print(f"\nSecond response output (first 300 chars):")
                print(text[:300])

                # Check for context awareness
                if any(keyword in text.lower() for keyword in ['previously', 'mentioned', 'discussed', 'earlier', 'above']):
                    print("\n✅ Second response appears to reference previous context!")
                else:
                    print("\n⚠️ Second response may not reference previous context")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_input_parameter_formats():
    """Test what formats the input parameter accepts."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 2: Input Parameter Format Testing")
    print("=" * 80)

    # Test 1: String input (already know this works)
    print("\n1. Testing string input...")
    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input="Simple string input",
            background=True,
        )
        print(f"   ✅ String input accepted: {resp.id}")
        client.responses.cancel(resp.id)
    except Exception as e:
        print(f"   ❌ String input failed: {e}")

    # Test 2: Dict with items
    print("\n2. Testing dict with items...")
    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input={
                "items": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Test message"
                            }
                        ]
                    }
                ]
            },
            background=True,
        )
        print(f"   ✅ Dict with items accepted: {resp.id}")
        client.responses.cancel(resp.id)
    except Exception as e:
        print(f"   ❌ Dict with items failed: {e}")

    # Test 3: List of items directly
    print("\n3. Testing list of items directly...")
    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Test message"
                        }
                    ]
                }
            ],
            background=True,
        )
        print(f"   ✅ List of items accepted: {resp.id}")
        client.responses.cancel(resp.id)
    except Exception as e:
        print(f"   ❌ List of items failed: {e}")


def test_using_previous_response_id():
    """Test using previous_response_id vs stateless context."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 3: previous_response_id vs Stateless Context")
    print("=" * 80)

    # Create first response
    print("\n1. Creating first response...")
    resp1 = client.responses.create(
        model="gpt-5.2",
        input="What are the key principles of distributed consensus algorithms?",
        background=True,
    )

    while resp1.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp1 = client.responses.retrieve(resp1.id)

    print(f"✅ First response completed: {resp1.id}")

    # Create follow-up using previous_response_id
    print("\n2. Creating follow-up with previous_response_id...")
    resp2 = client.responses.create(
        model="gpt-5.2",
        input="Can you elaborate on the Raft algorithm specifically?",
        background=True,
        previous_response_id=resp1.id,
    )

    while resp2.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp2 = client.responses.retrieve(resp2.id)

    print(f"✅ Follow-up completed: {resp2.id}")

    # Check if it has context
    if resp2.output and len(resp2.output) > 0:
        first_msg = resp2.output[0]
        if hasattr(first_msg, 'content') and len(first_msg.content) > 0:
            text = first_msg.content[0].text
            print(f"\nFollow-up output (first 300 chars):")
            print(text[:300])

            if any(keyword in text.lower() for keyword in ['previously', 'mentioned', 'discussed', 'earlier', 'raft']):
                print("\n✅ Follow-up with previous_response_id has context!")
            else:
                print("\n⚠️ Follow-up may not have context")


if __name__ == "__main__":
    try:
        # Test 1: Stateless context passing
        result1 = test_stateless_context_passing()

        # Test 2: Input format testing
        test_input_parameter_formats()

        # Test 3: previous_response_id
        test_using_previous_response_id()

        print("\n" + "=" * 80)
        print("All stateless context tests completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

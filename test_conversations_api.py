#!/usr/bin/env python3
"""
Test conversations API integration with background mode.
"""

import os
import time
import json
from openai import OpenAI


def test_background_with_conversation_id():
    """Test if background mode can be used with conversation parameter."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("TEST 1: Background Mode with conversation parameter")
    print("=" * 80)

    try:
        # First, try to create a conversation (if the API supports it)
        print("\n1. Attempting to create or use a conversation...")

        # Create a background response with conversation parameter
        resp = client.responses.create(
            model="gpt-5.2",
            input="What are the key principles of distributed consensus algorithms?",
            background=True,
            conversation="test-conv-001",  # Using correct parameter name
        )

        print(f"Response ID: {resp.id}")
        print(f"Initial status: {resp.status}")

        # Check if conversation is in the response
        resp_dict = resp.model_dump() if hasattr(resp, 'model_dump') else resp.__dict__
        if 'conversation' in resp_dict:
            print(f"Conversation: {resp_dict['conversation']}")
        else:
            print("No conversation in response")

        # Poll for completion
        print("\n2. Polling for completion...")
        while resp.status in {"queued", "in_progress"}:
            time.sleep(2)
            resp = client.responses.retrieve(resp.id)
            print(f"Status: {resp.status}")

        print(f"\n3. Final status: {resp.status}")

        # Print full response structure to understand state
        print("\n4. Final response structure (first 1000 chars):")
        final_dict = resp.model_dump() if hasattr(resp, 'model_dump') else resp.__dict__
        print(json.dumps(final_dict, indent=2, default=str)[:1000])

        # Check for conversation field
        if 'conversation' in final_dict:
            print(f"\n   ✅ Conversation field found: {final_dict['conversation']}")
        else:
            print(f"\n   ❌ No conversation field in response")
            print(f"   Available keys: {list(final_dict.keys())}")

        # Try to continue the conversation
        print("\n5. Attempting to continue conversation...")
        if 'conversation' in final_dict and final_dict['conversation']:
            resp2 = client.responses.create(
                model="gpt-5.2",
                input="Can you elaborate on the Raft algorithm specifically?",
                conversation=final_dict['conversation'],
                background=True,
            )
            print(f"Follow-up response ID: {resp2.id}")

            while resp2.status in {"queued", "in_progress"}:
                time.sleep(2)
                resp2 = client.responses.retrieve(resp2.id)

            print(f"Follow-up final status: {resp2.status}")

            # Check if the follow-up response references the same conversation
            resp2_dict = resp2.model_dump() if hasattr(resp2, 'model_dump') else resp2.__dict__
            if 'conversation' in resp2_dict:
                print(f"Follow-up conversation: {resp2_dict['conversation']}")
                if resp2_dict['conversation'] == final_dict['conversation']:
                    print("✅ Conversation threading confirmed!")
                else:
                    print("⚠️ Different conversation ID in follow-up")

        else:
            print("Cannot continue conversation - no conversation field found or it's None")

        return resp

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_conversation_state_after_completion():
    """Test what the conversation state looks like after background task completes."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 2: Conversation State After Background Completion")
    print("=" * 80)

    try:
        print("\n1. Creating background response...")
        resp = client.responses.create(
            model="gpt-5.2",
            input="Explain the Byzantine Generals Problem and how it relates to blockchain consensus.",
            background=True,
        )

        print(f"Response ID: {resp.id}")

        # Wait for completion
        print("\n2. Waiting for completion...")
        while resp.status in {"queued", "in_progress"}:
            time.sleep(2)
            resp = client.responses.retrieve(resp.id)

        print(f"Status: {resp.status}")

        # Examine the completed state
        print("\n3. Examining completed conversation state:")
        resp_dict = resp.model_dump() if hasattr(resp, 'model_dump') else resp.__dict__

        print(f"Available fields: {list(resp_dict.keys())}")

        # Print key state information
        for key in ['id', 'status', 'created_at', 'completed_at', 'conversation_id',
                    'store', 'metadata', 'usage']:
            if key in resp_dict:
                print(f"  {key}: {resp_dict[key]}")

        # Check if we can retrieve the response again after completion
        print("\n4. Retrieving completed response again...")
        retrieved = client.responses.retrieve(resp.id)
        print(f"Retrieved status: {retrieved.status}")
        print(f"Can retrieve after completion: True")

        # Check how long data persists
        print("\n5. Response data persistence:")
        print("  According to docs: ~10 minutes")
        print(f"  Response ID to test later: {resp.id}")

        return resp

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_multiple_background_conversations():
    """Test running multiple background conversations in parallel."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 3: Multiple Parallel Background Conversations")
    print("=" * 80)

    try:
        tasks = [
            "Explain Paxos consensus algorithm",
            "Explain Raft consensus algorithm",
            "Explain PBFT consensus algorithm"
        ]

        print("\n1. Starting multiple background tasks...")
        responses = []
        for i, task in enumerate(tasks):
            resp = client.responses.create(
                model="gpt-5.2",
                input=task,
                background=True,
            )
            responses.append(resp)
            print(f"Task {i+1} - ID: {resp.id}, Status: {resp.status}")

        # Poll all tasks
        print("\n2. Polling all tasks...")
        all_complete = False
        iteration = 0

        while not all_complete and iteration < 60:
            iteration += 1
            time.sleep(3)

            statuses = []
            for i, resp in enumerate(responses):
                responses[i] = client.responses.retrieve(resp.id)
                statuses.append(responses[i].status)

            print(f"Iteration {iteration}: {statuses}")
            all_complete = all(s not in {"queued", "in_progress"} for s in statuses)

        print("\n3. Final statuses:")
        for i, resp in enumerate(responses):
            print(f"Task {i+1}: {resp.status}")

        return responses

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_store_requirement():
    """Test the requirement that background mode needs store=true."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 4: Store Requirement for Background Mode")
    print("=" * 80)

    print("\n1. Testing with store=False (should fail per docs)...")
    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input="Quick test message",
            background=True,
            store=False,
        )
        print(f"Response created: {resp.id} (unexpected - should have failed)")
        print(f"Status: {resp.status}")

    except Exception as e:
        print(f"Expected error occurred: {e}")

    print("\n2. Testing with store=True (should work)...")
    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input="Quick test message",
            background=True,
            store=True,
        )
        print(f"Response created: {resp.id}")
        print(f"Status: {resp.status}")

        # Cancel it to save resources
        client.responses.cancel(resp.id)
        print("Cancelled to save resources")

    except Exception as e:
        print(f"Unexpected error: {e}")

    print("\n3. Testing default behavior (no store param)...")
    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input="Quick test message",
            background=True,
        )
        print(f"Response created: {resp.id}")
        print(f"Status: {resp.status}")

        # Check if store is true by default
        resp_dict = resp.model_dump() if hasattr(resp, 'model_dump') else resp.__dict__
        if 'store' in resp_dict:
            print(f"Store value: {resp_dict['store']}")

        # Cancel it
        client.responses.cancel(resp.id)
        print("Cancelled to save resources")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    try:
        # Test 1: Background with conversation ID
        result1 = test_background_with_conversation_id()

        # Test 2: Conversation state after completion
        result2 = test_conversation_state_after_completion()

        # Test 3: Multiple parallel conversations
        result3 = test_multiple_background_conversations()

        # Test 4: Store requirement
        test_store_requirement()

        print("\n" + "=" * 80)
        print("All conversation API tests completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

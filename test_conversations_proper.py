#!/usr/bin/env python3
"""
Test conversations API with proper flow:
1. Create a conversation
2. Add responses to that conversation
3. Test threading
"""

import os
import time
import json
from openai import OpenAI


def test_conversation_creation():
    """Test creating a conversation."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("TEST 1: Create and Use a Conversation")
    print("=" * 80)

    # Step 1: Create a conversation
    print("\n1. Creating a conversation...")
    conversation = client.conversations.create(
        metadata={"purpose": "testing-deep-research"}
    )

    print(f"✅ Conversation created!")
    print(f"Conversation ID: {conversation.id}")
    print(f"Conversation object: {conversation}")

    # Step 2: Create a response in this conversation
    print("\n2. Creating first response in conversation...")
    resp1 = client.responses.create(
        model="gpt-5.2",
        input="What are the key principles of distributed consensus algorithms?",
        background=True,
        conversation=conversation.id,
    )

    print(f"Response 1 ID: {resp1.id}")
    print(f"Response 1 status: {resp1.status}")

    # Check if conversation is in response
    if hasattr(resp1, 'conversation'):
        print(f"Response 1 conversation: {resp1.conversation}")
    else:
        print("No conversation attribute in response")

    # Poll for completion
    print("\n3. Polling first response...")
    while resp1.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp1 = client.responses.retrieve(resp1.id)
        print(f"   Status: {resp1.status}")

    print(f"✅ Response 1 completed!")

    # Print first part of output
    if resp1.output and len(resp1.output) > 0:
        first_msg = resp1.output[0]
        if hasattr(first_msg, 'content') and len(first_msg.content) > 0:
            text = first_msg.content[0].text
            print(f"\nOutput (first 200 chars): {text[:200]}...")

    # Step 3: Create follow-up response in same conversation
    print("\n4. Creating follow-up response in same conversation...")
    resp2 = client.responses.create(
        model="gpt-5.2",
        input="Can you elaborate on the Raft algorithm specifically?",
        background=True,
        conversation=conversation.id,
    )

    print(f"Response 2 ID: {resp2.id}")
    print(f"Response 2 status: {resp2.status}")

    # Poll for completion
    print("\n5. Polling follow-up response...")
    while resp2.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp2 = client.responses.retrieve(resp2.id)
        print(f"   Status: {resp2.status}")

    print(f"✅ Response 2 completed!")

    # Check if follow-up references context from first response
    if resp2.output and len(resp2.output) > 0:
        first_msg = resp2.output[0]
        if hasattr(first_msg, 'content') and len(first_msg.content) > 0:
            text = first_msg.content[0].text
            print(f"\nFollow-up output (first 300 chars): {text[:300]}...")

            # Check if it references previous context
            if any(keyword in text.lower() for keyword in ['previously', 'mentioned', 'discussed', 'as i', 'earlier']):
                print("\n✅ Follow-up appears to reference previous context!")
            else:
                print("\n⚠️ Follow-up may not reference previous context (but check full output)")

    return conversation


def test_conversation_with_initial_items():
    """Test creating conversation with initial items."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 2: Create Conversation with Initial Items")
    print("=" * 80)

    # Create conversation with initial context
    print("\n1. Creating conversation with initial items...")
    conversation = client.conversations.create(
        items=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "I'm building a distributed database."
                    }
                ]
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "That's great! Distributed databases require careful consideration of consistency, availability, and partition tolerance."
                    }
                ]
            }
        ],
        metadata={"purpose": "with-context"}
    )

    print(f"✅ Conversation created with initial context: {conversation.id}")

    # Create response that should leverage this context
    print("\n2. Creating response that should use initial context...")
    resp = client.responses.create(
        model="gpt-5.2",
        input="Which consensus algorithm would you recommend for my use case?",
        background=True,
        conversation=conversation.id,
    )

    print(f"Response ID: {resp.id}")

    # Poll for completion
    print("\n3. Polling response...")
    while resp.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp = client.responses.retrieve(resp.id)

    print(f"✅ Response completed!")

    # Check if response references the distributed database context
    if resp.output and len(resp.output) > 0:
        first_msg = resp.output[0]
        if hasattr(first_msg, 'content') and len(first_msg.content) > 0:
            text = first_msg.content[0].text
            print(f"\nOutput (first 300 chars): {text[:300]}...")

            if 'database' in text.lower() or 'distributed' in text.lower():
                print("\n✅ Response references the distributed database context!")
            else:
                print("\n⚠️ Response may not reference context (check full output)")

    return conversation


def test_conversation_retrieval():
    """Test retrieving a conversation."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 3: Retrieve Conversation")
    print("=" * 80)

    # Create a conversation
    print("\n1. Creating conversation...")
    conversation = client.conversations.create()
    print(f"Created: {conversation.id}")

    # Add a response to it
    print("\n2. Adding response to conversation...")
    resp = client.responses.create(
        model="gpt-5.2",
        input="Hello, this is a test message.",
        background=True,
        conversation=conversation.id,
    )

    # Wait for completion
    while resp.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp = client.responses.retrieve(resp.id)

    print(f"Response completed: {resp.id}")

    # Retrieve the conversation
    print("\n3. Retrieving conversation...")
    if hasattr(client.conversations, 'retrieve'):
        retrieved = client.conversations.retrieve(conversation.id)
        print(f"✅ Retrieved conversation: {retrieved.id}")
        print(f"Conversation details: {retrieved}")
    else:
        print("❌ No retrieve method on conversations")

    # List conversations if possible
    print("\n4. Checking if conversations can be listed...")
    if hasattr(client.conversations, 'list'):
        print("✅ List method exists")
        conversations = client.conversations.list(limit=5)
        print(f"Found {len(list(conversations))} conversations")
    else:
        print("❌ No list method on conversations")


def test_conversation_structure():
    """Examine the structure of a conversation object."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 4: Conversation Object Structure")
    print("=" * 80)

    conversation = client.conversations.create(
        metadata={"test": "structure"}
    )

    print("\n1. Conversation attributes:")
    conv_dict = conversation.model_dump() if hasattr(conversation, 'model_dump') else conversation.__dict__
    print(json.dumps(conv_dict, indent=2, default=str))

    print("\n2. Available methods:")
    methods = [m for m in dir(conversation) if not m.startswith('_')]
    print(methods)


if __name__ == "__main__":
    try:
        # Test 1: Basic conversation flow
        conv1 = test_conversation_creation()

        # Test 2: Conversation with initial items
        conv2 = test_conversation_with_initial_items()

        # Test 3: Retrieve conversation
        test_conversation_retrieval()

        # Test 4: Examine structure
        test_conversation_structure()

        print("\n" + "=" * 80)
        print("All conversation tests completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

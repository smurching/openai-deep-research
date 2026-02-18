#!/usr/bin/env python3
"""
Test listing items in a conversation.
"""

import os
import time
from openai import OpenAI


def test_list_conversation_items():
    """Test listing items from a conversation."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("TEST: Listing Conversation Items")
    print("=" * 80)

    # Step 1: Create a conversation with initial items
    print("\n1. Creating conversation with initial items...")
    conversation = client.conversations.create(
        metadata={"purpose": "test-listing"},
        items=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello!"}]
            }
        ]
    )

    print(f"   ✅ Conversation created: {conversation.id}")

    # Step 2: Add some responses to build history
    print("\n2. Adding responses to build history...")

    for i, prompt in enumerate(["What is Paxos?", "What is Raft?"], 1):
        resp = client.responses.create(
            model="gpt-5.2",
            input=prompt,
            background=True,
            conversation=conversation.id,
            max_output_tokens=100,  # Keep short
        )

        while resp.status in {"queued", "in_progress"}:
            time.sleep(2)
            resp = client.responses.retrieve(resp.id)

        print(f"   ✅ Response {i} completed")

    # Step 3: List conversation items
    print("\n3. Listing conversation items...")
    try:
        items = client.conversations.items.list(conversation.id, limit=10)

        print(f"   ✅ Retrieved items!")
        print(f"   Number of items: {len(items.data)}")

        print("\n4. Examining items:")
        for i, item in enumerate(items.data):
            print(f"\n   Item {i}:")
            print(f"   - ID: {item.id if hasattr(item, 'id') else 'N/A'}")
            print(f"   - Type: {item.type if hasattr(item, 'type') else type(item)}")
            print(f"   - Role: {item.role if hasattr(item, 'role') else 'N/A'}")

            # Show content preview
            if hasattr(item, 'content') and item.content:
                if len(item.content) > 0:
                    first_content = item.content[0]
                    if hasattr(first_content, 'text'):
                        text = first_content.text
                        preview = text[:100] + "..." if len(text) > 100 else text
                        print(f"   - Content preview: {preview}")

        # Check if there's pagination
        print("\n5. Pagination info:")
        if hasattr(items, 'has_more'):
            print(f"   Has more: {items.has_more}")
        if hasattr(items, 'first_id'):
            print(f"   First ID: {items.first_id}")
        if hasattr(items, 'last_id'):
            print(f"   Last ID: {items.last_id}")

        return items

    except Exception as e:
        print(f"   ❌ Error listing items: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    items = test_list_conversation_items()

    print("\n" + "=" * 80)
    print("FINDINGS")
    print("=" * 80)

    print("""
The conversations.items.list() API allows you to:
✅ Retrieve all items in a conversation
✅ See the full history (user messages, assistant responses, etc.)
✅ Use pagination with limit parameter
✅ Access item metadata (id, type, role, content)

This is useful for:
- Debugging conversation state
- Understanding what context is preserved
- Implementing custom compaction logic
- Monitoring conversation growth
""")

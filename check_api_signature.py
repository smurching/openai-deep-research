#!/usr/bin/env python3
"""
Check the API signatures for responses.create and conversations API.
"""

import inspect
from openai import OpenAI

client = OpenAI()

print("=" * 80)
print("RESPONSES.CREATE SIGNATURE")
print("=" * 80)

# Get the signature
sig = inspect.signature(client.responses.create)
print(f"\nSignature:\n{sig}\n")

# Get docstring
print("Docstring:")
print(client.responses.create.__doc__)

print("\n" + "=" * 80)
print("CHECKING FOR CONVERSATIONS API")
print("=" * 80)

# Check if conversations API exists
if hasattr(client, 'conversations'):
    print("\n✅ client.conversations exists!")

    # Check for create method
    if hasattr(client.conversations, 'create'):
        print("✅ client.conversations.create exists!")

        sig = inspect.signature(client.conversations.create)
        print(f"\nSignature:\n{sig}\n")

        print("Docstring:")
        print(client.conversations.create.__doc__)
    else:
        print("❌ client.conversations.create does NOT exist")
        print(f"Available methods: {dir(client.conversations)}")
else:
    print("❌ client.conversations does NOT exist")
    print(f"\nAvailable client attributes: {[a for a in dir(client) if not a.startswith('_')]}")

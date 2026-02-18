#!/usr/bin/env python3
"""
Test context size limits and strategies for managing context accumulation.
"""

import os
import json
from openai import OpenAI


def test_context_limit_behavior():
    """Test what happens when context size is too large."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("TEST 1: Understanding Context Limits")
    print("=" * 80)

    print("\n📏 Model Context Window:")
    print("   gpt-5.2: Unknown exact limit (likely 128K+ tokens)")
    print("   Chat models typically have documented context windows")
    print("   Let's test the behavior...")

    # Test 1: Try to get error information from a moderately large context
    print("\n1. Testing with artificially large context...")

    # Create a conversation history with repeated content to simulate large context
    # But keep it reasonable to not burn tokens
    large_context = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Tell me about consensus algorithms."}]
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": "Here's a very long explanation... " + "X" * 50000  # ~50K chars
            }]
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Continue."}]
        }
    ]

    print(f"   Context size: ~{len(json.dumps(large_context))} characters")

    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input=large_context,
            background=True,
            max_output_tokens=100,  # Limit output to save tokens
        )
        print(f"   ✅ Request accepted: {resp.id}")
        print(f"   Status: {resp.status}")

        # Cancel immediately to save tokens
        client.responses.cancel(resp.id)
        print("   Cancelled to save tokens")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        error_str = str(e)
        if "context" in error_str.lower() or "token" in error_str.lower():
            print("   → This is a context/token limit error")
        if "maximum" in error_str.lower():
            print("   → Error mentions maximum limit")


def test_token_counting():
    """Show how to estimate token usage before making request."""

    print("\n" + "=" * 80)
    print("TEST 2: Estimating Token Usage")
    print("=" * 80)

    print("\n💡 Token Estimation Strategies:")
    print("   1. Rule of thumb: ~4 characters per token (English)")
    print("   2. Use tiktoken library for accurate counting")
    print("   3. Check usage in response after completion")

    print("\n📦 Installing tiktoken for accurate token counting...")
    import subprocess
    try:
        subprocess.run(["pip", "install", "-q", "tiktoken"], check=True)
        print("   ✅ tiktoken installed")
    except:
        print("   ⚠️ Could not install tiktoken automatically")

    try:
        import tiktoken

        print("\n   Testing token counting with tiktoken:")

        # Get encoding for the model
        # Note: gpt-5.2 might not have a specific encoding, using gpt-4 as proxy
        encoding = tiktoken.encoding_for_model("gpt-4")

        sample_text = "What are the key principles of distributed consensus algorithms?"
        tokens = encoding.encode(sample_text)

        print(f"   Text: '{sample_text}'")
        print(f"   Characters: {len(sample_text)}")
        print(f"   Tokens: {len(tokens)}")
        print(f"   Ratio: {len(sample_text) / len(tokens):.2f} chars/token")

    except ImportError:
        print("\n   ⚠️ tiktoken not available, using approximation")
        print("   Use ~4 characters per token as rough estimate")


def context_management_strategies():
    """Document strategies for managing context accumulation."""

    print("\n" + "=" * 80)
    print("STRATEGIES: Managing Context Accumulation")
    print("=" * 80)

    print("""
1. 🎯 SLIDING WINDOW (Most Common)
   Keep only the most recent N messages:

   ```python
   MAX_MESSAGES = 10
   conversation_history = conversation_history[-MAX_MESSAGES:]
   ```

   Pros: Simple, predictable size
   Cons: Loses older context

2. 📊 TOKEN-BASED TRUNCATION
   Track token count and truncate when approaching limit:

   ```python
   import tiktoken

   def truncate_to_tokens(messages, max_tokens=100000):
       encoding = tiktoken.encoding_for_model("gpt-4")
       total_tokens = 0
       truncated = []

       # Process messages in reverse (keep most recent)
       for msg in reversed(messages):
           msg_text = json.dumps(msg)
           msg_tokens = len(encoding.encode(msg_text))

           if total_tokens + msg_tokens > max_tokens:
               break

           truncated.insert(0, msg)
           total_tokens += msg_tokens

       return truncated
   ```

3. 📝 SUMMARIZATION (Intelligent)
   Summarize older context into a condensed version:

   ```python
   async def summarize_old_context(old_messages):
       summary_resp = await client.responses.create(
           model="gpt-5.2",
           input=[
               {"type": "message", "role": "user", "content": [{
                   "type": "input_text",
                   "text": f"Summarize this conversation: {old_messages}"
               }]}
           ],
           background=True,
           max_output_tokens=500,
       )

       # Replace old messages with summary
       return [{
           "type": "message",
           "role": "assistant",
           "content": [{"type": "output_text", "text": summary_resp.output[0].content[0].text}]
       }]
   ```

4. 🎭 SELECTIVE RETENTION
   Keep important messages, drop routine ones:

   ```python
   def filter_important_messages(messages):
       important = []
       for msg in messages:
           # Keep system messages, user questions, key decisions
           if (msg.get("role") == "user" or
               "important" in msg.get("metadata", {}) or
               len(important) < 2):  # Always keep first few
               important.append(msg)
       return important
   ```

5. 🗂️ HIERARCHICAL CONTEXT
   Store full history externally, send only relevant parts:

   ```python
   class ContextManager:
       def __init__(self):
           self.full_history = []
           self.db = Database()  # Your storage

       def add_message(self, message):
           self.full_history.append(message)
           self.db.store(message)

       def get_relevant_context(self, query, max_messages=10):
           # Use embeddings/search to find relevant past messages
           relevant = self.db.search_similar(query, limit=5)
           recent = self.full_history[-5:]
           return relevant + recent
   ```

6. 🔄 CONVERSATION API (Server-Managed)
   Let OpenAI manage context:

   ```python
   # Create conversation once
   conv = client.conversations.create()

   # Keep using same conversation - server manages context
   for user_input in user_inputs:
       resp = client.responses.create(
           model="gpt-5.2",
           input=user_input,
           background=True,
           conversation=conv.id,  # Server handles context
       )
   ```

   Note: Limited to ~10 minute response retention

7. 🎨 HYBRID APPROACH
   Combine strategies:

   ```python
   def prepare_context(full_history, current_query, max_tokens=100000):
       # 1. Always keep first message (system prompt)
       context = [full_history[0]]

       # 2. Summarize middle if history is long
       if len(full_history) > 20:
           middle = full_history[1:-10]
           summary = summarize_messages(middle)
           context.append(summary)
           recent = full_history[-10:]
       else:
           recent = full_history[1:]

       # 3. Add recent messages
       context.extend(recent)

       # 4. Truncate to token limit if needed
       return truncate_to_tokens(context, max_tokens)
   ```
""")


def test_with_max_output_tokens():
    """Test using max_output_tokens to control response size."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 3: Controlling Output Size")
    print("=" * 80)

    print("\n🎛️ Use max_output_tokens to control response size:")

    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input="Write a comprehensive guide to distributed systems.",
            background=True,
            max_output_tokens=200,  # Limit response size
        )

        print(f"   ✅ Request created: {resp.id}")
        print(f"   max_output_tokens: 200")

        # Cancel to save tokens
        client.responses.cancel(resp.id)
        print("   Cancelled to save tokens")

        print("\n   This prevents responses from consuming too much context")
        print("   when they're added back to conversation history")

    except Exception as e:
        print(f"   ❌ Error: {e}")


def best_practices():
    """Document best practices for context management."""

    print("\n" + "=" * 80)
    print("BEST PRACTICES")
    print("=" * 80)

    print("""
✅ DO:
  • Monitor token usage in response.usage
  • Set max_output_tokens for responses that will be added to context
  • Use sliding window for simple cases
  • Implement token counting before API calls
  • Consider Conversations API for server-managed context
  • Store full history externally for auditability

❌ DON'T:
  • Accumulate context indefinitely without limits
  • Assume character count = token count
  • Ignore response.usage statistics
  • Send full history when recent context would suffice

🎯 RECOMMENDED APPROACH:
  1. Start with sliding window (10-20 messages)
  2. Add token counting when you need precision
  3. Use summarization for long-running agents
  4. Monitor usage.total_tokens in responses
  5. Set max_output_tokens to prevent runaway responses

📊 EXAMPLE MONITORING:

```python
class ConversationManager:
    def __init__(self, max_tokens=100000):
        self.history = []
        self.total_tokens = 0
        self.max_tokens = max_tokens

    def add_message(self, message, tokens_used):
        self.history.append(message)
        self.total_tokens += tokens_used

        # Trigger cleanup if approaching limit
        if self.total_tokens > self.max_tokens * 0.8:
            self.cleanup()

    def cleanup(self):
        # Keep recent messages, summarize or drop old ones
        self.history = self.history[-10:]
        # Recalculate tokens...
```
""")


if __name__ == "__main__":
    try:
        test_context_limit_behavior()
        test_token_counting()
        context_management_strategies()
        test_with_max_output_tokens()
        best_practices()

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("""
When you exceed context limits:
  • The API will return an error (not fail silently)
  • Error will indicate token/context limit exceeded
  • No partial responses - the request fails

For agents accumulating context:
  • Use sliding window (simplest)
  • Implement token counting (accurate)
  • Consider summarization (intelligent)
  • Monitor response.usage.total_tokens
  • Set max_output_tokens to control growth

Choose based on your needs:
  • Short sessions: Simple sliding window
  • Long sessions: Summarization + recent messages
  • Complex agents: Hybrid with external storage
  • Want simplicity: Use Conversations API (server manages)
""")

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

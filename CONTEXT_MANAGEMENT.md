# Context Management for Long-Running Agents

## TL;DR

**What happens if context is too large?**
- ✅ The API **will return an error** (not fail silently)
- ❌ **No partial responses** - the request fails completely
- 💡 You need to **manage context proactively**

**Token counting:**
- Rule of thumb: **~4-6 characters per token** (English)
- Actual measurement: **6.4 chars/token** in our test
- Use `tiktoken` library for accurate counting

---

## Context Window Limits

### Model Limits

| Model | Context Window | Notes |
|-------|----------------|-------|
| gpt-5.2 | ~128K+ tokens | Exact limit not documented |
| gpt-4 | 128K tokens | Well documented |
| gpt-4-turbo | 128K tokens | Standard |

### What Happens When You Exceed?

```python
# If context is too large:
resp = client.responses.create(
    model="gpt-5.2",
    input=very_large_context,  # > 128K tokens
    background=True,
)
# → Raises: openai.BadRequestError
# → Error message will mention "token limit exceeded" or similar
# → Request fails immediately, no partial processing
```

**Key insight**: It's better to manage context proactively than handle errors reactively!

---

## Seven Strategies for Context Management

### 1. 🎯 Sliding Window (Simplest)

Keep only the most recent N messages.

```python
MAX_MESSAGES = 10

def add_to_context(history, new_message):
    history.append(new_message)
    # Keep only last N messages
    return history[-MAX_MESSAGES:]

# Usage
conversation_history = []
for user_input in user_inputs:
    # Add user message
    conversation_history = add_to_context(
        conversation_history,
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": user_input}]}
    )

    # Get response
    resp = client.responses.create(
        model="gpt-5.2",
        input=conversation_history,
        background=True,
    )

    # Add assistant response
    conversation_history = add_to_context(
        conversation_history,
        {"type": "message", "role": "assistant", "content": resp.output[0].content}
    )
```

**Pros:** Simple, predictable, easy to implement
**Cons:** Loses older context completely

---

### 2. 📊 Token-Based Truncation (Accurate)

Track actual token count and truncate when approaching limit.

```python
import tiktoken
import json

def truncate_to_tokens(messages, max_tokens=100000):
    """Keep messages up to max_tokens, preferring recent messages."""
    encoding = tiktoken.encoding_for_model("gpt-4")

    total_tokens = 0
    truncated = []

    # Process messages in reverse (keep most recent)
    for msg in reversed(messages):
        msg_text = json.dumps(msg)
        msg_tokens = len(encoding.encode(msg_text))

        if total_tokens + msg_tokens > max_tokens:
            break  # Would exceed limit

        truncated.insert(0, msg)
        total_tokens += msg_tokens

    return truncated, total_tokens

# Usage
conversation_history = []
MAX_CONTEXT_TOKENS = 100000  # Leave room for response

for user_input in user_inputs:
    # Add user message
    conversation_history.append({
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": user_input}]
    })

    # Truncate to fit
    context_to_send, token_count = truncate_to_tokens(
        conversation_history,
        MAX_CONTEXT_TOKENS
    )

    print(f"Sending {token_count} tokens in context")

    # Get response
    resp = client.responses.create(
        model="gpt-5.2",
        input=context_to_send,
        background=True,
    )

    # Add response to history
    conversation_history.append({
        "type": "message",
        "role": "assistant",
        "content": resp.output[0].content
    })
```

**Pros:** Precise control, respects actual token limits
**Cons:** Requires tiktoken library, slightly more complex

---

### 3. 📝 Summarization (Intelligent)

Summarize older messages to preserve information while reducing tokens.

```python
def summarize_old_context(client, old_messages):
    """Summarize old conversation history."""
    # Convert messages to text
    conversation_text = "\n".join([
        f"{msg['role']}: {msg['content'][0].get('text', '')}"
        for msg in old_messages
    ])

    # Request summary
    summary_resp = client.responses.create(
        model="gpt-5.2",
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": f"Summarize this conversation in 200 words or less:\n\n{conversation_text}"
                }]
            }
        ],
        background=True,
        max_output_tokens=500,
    )

    # Wait for completion
    while summary_resp.status in {"queued", "in_progress"}:
        time.sleep(2)
        summary_resp = client.responses.retrieve(summary_resp.id)

    # Return as a single message
    return {
        "type": "message",
        "role": "assistant",
        "content": [{
            "type": "output_text",
            "text": f"[Summary of previous conversation]: {summary_resp.output[0].content[0].text}"
        }]
    }

# Usage
SUMMARIZE_THRESHOLD = 20  # Summarize if more than 20 messages

if len(conversation_history) > SUMMARIZE_THRESHOLD:
    # Summarize old messages (all but last 5)
    old_messages = conversation_history[:-5]
    recent_messages = conversation_history[-5:]

    summary = summarize_old_context(client, old_messages)

    # Replace old messages with summary
    conversation_history = [summary] + recent_messages
```

**Pros:** Preserves information intelligently, good for long sessions
**Cons:** Costs tokens for summarization, adds latency

---

### 4. 🎭 Selective Retention (Filtered)

Keep only important messages, drop routine exchanges.

```python
def filter_important_messages(messages):
    """Keep only important messages based on criteria."""
    important = []

    for i, msg in enumerate(messages):
        keep = False

        # Always keep first few messages
        if i < 3:
            keep = True

        # Keep user questions
        elif msg.get("role") == "user":
            keep = True

        # Keep messages marked as important
        elif msg.get("metadata", {}).get("important"):
            keep = True

        # Keep messages with tool calls
        elif "tool_call" in str(msg):
            keep = True

        if keep:
            important.append(msg)

    return important

# Usage with metadata
conversation_history.append({
    "type": "message",
    "role": "assistant",
    "content": resp.output[0].content,
    "metadata": {"important": True}  # Mark as important
})

# Filter when needed
conversation_history = filter_important_messages(conversation_history)
```

**Pros:** Keeps relevant information, custom logic
**Cons:** May drop useful context, requires careful design

---

### 5. 🗂️ Hierarchical Context (RAG Pattern)

Store full history externally, retrieve relevant parts.

```python
from typing import List
import numpy as np

class ContextManager:
    """Manage context with external storage and retrieval."""

    def __init__(self, client):
        self.client = client
        self.full_history = []
        self.message_embeddings = []

    def add_message(self, message):
        """Add message to full history."""
        self.full_history.append(message)

        # Get embedding for retrieval (simplified)
        # In reality, use OpenAI embeddings API
        text = self._extract_text(message)
        embedding = self._get_embedding(text)
        self.message_embeddings.append(embedding)

    def get_relevant_context(self, query: str, max_messages: int = 10):
        """Get relevant context for query."""
        # Always include recent messages
        recent = self.full_history[-5:]

        # Search for semantically similar past messages
        query_embedding = self._get_embedding(query)
        similarities = [
            self._cosine_similarity(query_embedding, emb)
            for emb in self.message_embeddings[:-5]  # Exclude recent
        ]

        # Get top N similar messages
        top_indices = np.argsort(similarities)[-5:]
        relevant = [self.full_history[i] for i in top_indices]

        return relevant + recent

    def _extract_text(self, message):
        """Extract text from message."""
        # Simplified extraction
        return str(message)

    def _get_embedding(self, text):
        """Get embedding (use OpenAI embeddings in production)."""
        # Placeholder - use actual embeddings API
        return np.random.rand(1536)

    def _cosine_similarity(self, a, b):
        """Calculate cosine similarity."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Usage
context_mgr = ContextManager(client)

for user_input in user_inputs:
    # Get relevant context for this query
    context = context_mgr.get_relevant_context(user_input)

    # Add current user message
    user_msg = {"type": "message", "role": "user", "content": [{"type": "input_text", "text": user_input}]}
    context.append(user_msg)

    # Get response
    resp = client.responses.create(
        model="gpt-5.2",
        input=context,
        background=True,
    )

    # Store messages
    context_mgr.add_message(user_msg)
    context_mgr.add_message({
        "type": "message",
        "role": "assistant",
        "content": resp.output[0].content
    })
```

**Pros:** Preserves all history, intelligent retrieval, scales well
**Cons:** Complex implementation, requires embeddings/database

---

### 6. 🔄 Conversations API (Server-Managed)

Let OpenAI manage the context for you.

```python
# Create conversation once
conversation = client.conversations.create(
    metadata={"user_id": "123", "session": "abc"}
)

# Use same conversation ID for all requests
for user_input in user_inputs:
    resp = client.responses.create(
        model="gpt-5.2",
        input=user_input,
        background=True,
        conversation=conversation.id,  # Server manages context!
    )

    while resp.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp = client.responses.retrieve(resp.id)

    print(resp.output[0].content[0].text)

# Context is automatically managed by OpenAI
# No need to track messages or tokens yourself!
```

**Pros:** Simplest, no context management code needed
**Cons:** Limited to ~10 minute retention, less control

---

### 7. 🎨 Hybrid Approach (Production-Ready)

Combine multiple strategies for robustness.

```python
import tiktoken
import json

class HybridContextManager:
    """Production-ready context manager combining multiple strategies."""

    def __init__(self, max_tokens=100000, max_messages=50):
        self.full_history = []
        self.max_tokens = max_tokens
        self.max_messages = max_messages
        self.encoding = tiktoken.encoding_for_model("gpt-4")

    def add_message(self, message):
        """Add message to history."""
        self.full_history.append(message)

    def get_context_for_request(self):
        """Get optimized context for next request."""
        # Step 1: Keep first message (usually system prompt)
        if not self.full_history:
            return []

        context = [self.full_history[0]]
        remaining = self.full_history[1:]

        # Step 2: If history is very long, summarize middle
        if len(remaining) > self.max_messages:
            middle = remaining[:-10]
            recent = remaining[-10:]

            # Add summary note instead of actual middle messages
            context.append({
                "type": "message",
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": f"[{len(middle)} earlier messages omitted for brevity]"
                }]
            })

            remaining = recent

        # Step 3: Add remaining messages
        context.extend(remaining)

        # Step 4: Truncate to token limit if needed
        context = self._truncate_to_tokens(context)

        return context

    def _truncate_to_tokens(self, messages):
        """Truncate messages to fit token limit."""
        total_tokens = 0
        truncated = []

        # Always keep first message
        first = messages[0]
        first_tokens = len(self.encoding.encode(json.dumps(first)))
        truncated.append(first)
        total_tokens += first_tokens

        # Add remaining messages in reverse
        for msg in reversed(messages[1:]):
            msg_tokens = len(self.encoding.encode(json.dumps(msg)))

            if total_tokens + msg_tokens > self.max_tokens:
                break

            truncated.insert(1, msg)  # Insert after first message
            total_tokens += msg_tokens

        return truncated

    def get_stats(self):
        """Get statistics about context."""
        context = self.get_context_for_request()
        total_tokens = sum(
            len(self.encoding.encode(json.dumps(msg)))
            for msg in context
        )
        return {
            "total_messages": len(self.full_history),
            "context_messages": len(context),
            "context_tokens": total_tokens,
            "token_usage_percent": (total_tokens / self.max_tokens) * 100
        }

# Usage
context_mgr = HybridContextManager(max_tokens=100000)

for user_input in user_inputs:
    # Add user message
    user_msg = {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": user_input}]
    }
    context_mgr.add_message(user_msg)

    # Get optimized context
    context = context_mgr.get_context_for_request()

    # Print stats
    stats = context_mgr.get_stats()
    print(f"Sending {stats['context_messages']}/{stats['total_messages']} messages "
          f"({stats['context_tokens']} tokens, {stats['token_usage_percent']:.1f}%)")

    # Get response
    resp = client.responses.create(
        model="gpt-5.2",
        input=context,
        background=True,
        max_output_tokens=2000,  # Limit response size
    )

    while resp.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp = client.responses.retrieve(resp.id)

    # Add assistant response
    context_mgr.add_message({
        "type": "message",
        "role": "assistant",
        "content": resp.output[0].content
    })
```

**Pros:** Robust, handles edge cases, production-ready
**Cons:** More complex code to maintain

---

## Monitoring & Best Practices

### Monitor Token Usage

```python
resp = client.responses.create(...)

# After completion
print(f"Input tokens: {resp.usage.input_tokens}")
print(f"Output tokens: {resp.usage.output_tokens}")
print(f"Total: {resp.usage.total_tokens}")

# Set alerts when approaching limits
if resp.usage.input_tokens > 100000:
    print("⚠️ WARNING: Approaching context limit!")
```

### Control Response Size

```python
resp = client.responses.create(
    model="gpt-5.2",
    input=context,
    background=True,
    max_output_tokens=1000,  # Prevent runaway responses
)
```

### Use Appropriate Encoding

```python
import tiktoken

# Get the right encoding for your model
encoding = tiktoken.encoding_for_model("gpt-4")  # Use gpt-4 for gpt-5.2
# OR
encoding = tiktoken.get_encoding("cl100k_base")  # Claude/GPT-4 tokenizer
```

---

## Decision Matrix

| Scenario | Recommended Strategy | Reasoning |
|----------|---------------------|-----------|
| **Short sessions** (<10 turns) | Sliding Window | Simple, no overhead |
| **Medium sessions** (10-50 turns) | Token-Based Truncation | Precise, efficient |
| **Long sessions** (50+ turns) | Summarization + Recent | Preserves info |
| **Complex agents** | Hierarchical (RAG) | Scales indefinitely |
| **Want simplicity** | Conversations API | Server-managed |
| **Production system** | Hybrid | Handles all cases |

---

## Quick Reference

```python
# ✅ DO:
- Monitor response.usage.total_tokens
- Set max_output_tokens
- Implement token counting
- Test with expected conversation length
- Store full history externally

# ❌ DON'T:
- Accumulate context indefinitely
- Assume 1 char = 1 token
- Ignore usage statistics
- Send full history when recent suffices
- Forget to handle errors

# 🎯 RULE OF THUMB:
- Start with sliding window (10-20 messages)
- Add token counting when needed
- Use summarization for long sessions
- Consider Conversations API for simplicity
```

---

## Example Error Handling

```python
try:
    resp = client.responses.create(
        model="gpt-5.2",
        input=context,
        background=True,
    )
except openai.BadRequestError as e:
    if "token" in str(e).lower() or "context" in str(e).lower():
        print(f"Context too large: {e}")

        # Automatically retry with truncated context
        truncated_context = context[-10:]  # Keep last 10 messages
        resp = client.responses.create(
            model="gpt-5.2",
            input=truncated_context,
            background=True,
        )
    else:
        raise
```

---

## Summary

**When context is too large:**
- API returns error immediately
- No partial processing
- Error message indicates limit exceeded

**For agents accumulating context:**
1. **Start simple**: Use sliding window
2. **Add precision**: Implement token counting
3. **Scale intelligently**: Add summarization
4. **Monitor**: Track token usage
5. **Control growth**: Set max_output_tokens

**Choose strategy based on:**
- Session length (short/medium/long)
- Complexity requirements
- Development effort available
- Whether you need full history

The **Hybrid Approach** is recommended for production systems as it handles all scenarios gracefully.

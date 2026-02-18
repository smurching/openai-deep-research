# OpenAI Deep Research API Testing

Testing scripts and findings for OpenAI's background mode (deep research) API with conversation management.

## 🎯 Key Findings

### ✅ **Three Ways to Manage Context**

OpenAI's Responses API supports **three different approaches** for maintaining conversation context:

1. **Stateless Context Passing** ⭐ NEW!
   - Pass `resp.output` directly as `input` to next request
   - Full control over conversation history
   - Works across sessions (no time limits)
   - Similar to Chat Completions API pattern

2. **Conversations API** (SDK v2.15.0+)
   - Create conversation objects server-side
   - Pass conversation ID to each request
   - Server manages context automatically
   - Most convenient for multi-turn workflows

3. **previous_response_id**
   - Link responses in a chain
   - Simplest approach for linear follow-ups
   - Works within ~10 minute window

### ✅ **Tool Calling Works**

- Tools execute automatically in background mode
- No MCP authentication prompting (auth must be pre-configured)
- No tool confirmation (autonomous execution)
- Tool errors explained conversationally, not with structured codes

### ✅ **Background Mode Features**

- Reliable polling for long-running tasks (>30s)
- Streaming with resumption support
- Parallel execution of multiple tasks
- Status tracking: `queued` → `in_progress` → `completed`
- 10-minute retrieval window after completion

## 📋 Requirements

```bash
pip install openai>=2.15.0
```

**Important**: SDK v2.15.0+ required for Conversations API support. Older versions don't support the `conversation` parameter.

## 🚀 Quick Start

### Stateless Context (Full Control)

```python
from openai import OpenAI
import time

client = OpenAI()

# First request
resp1 = client.responses.create(
    model="gpt-5.2",
    input="Explain Paxos consensus.",
    background=True,
)

# Wait for completion
while resp1.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp1 = client.responses.retrieve(resp1.id)

# Build conversation history
history = [
    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Explain Paxos consensus."}]},
    {"type": "message", "role": "assistant", "content": resp1.output[0].content},
    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "How does it compare to Raft?"}]}
]

# Second request with context
resp2 = client.responses.create(
    model="gpt-5.2",
    input=history,  # Pass list directly!
    background=True,
)
```

### Conversations API (Convenient)

```python
# Create conversation
conversation = client.conversations.create(
    metadata={"purpose": "research"}
)

# First response
resp1 = client.responses.create(
    model="gpt-5.2",
    input="Explain Paxos consensus.",
    background=True,
    conversation=conversation.id,
)

# Follow-up (context automatic!)
resp2 = client.responses.create(
    model="gpt-5.2",
    input="How does it compare to Raft?",
    background=True,
    conversation=conversation.id,
)
```

### previous_response_id (Simple)

```python
# First response
resp1 = client.responses.create(
    model="gpt-5.2",
    input="Explain Paxos consensus.",
    background=True,
)

# Follow-up (context automatic!)
resp2 = client.responses.create(
    model="gpt-5.2",
    input="How does it compare to Raft?",
    background=True,
    previous_response_id=resp1.id,
)
```

## 📊 When to Use Each Approach

| Use Case | Recommended Approach |
|----------|---------------------|
| Long sessions (hours/days) | **Stateless** |
| Need full control over context | **Stateless** |
| Multi-turn workflows within 10 min | **Conversations API** |
| Simple linear follow-ups | **previous_response_id** |
| Want server to manage context | **Conversations API** |
| Need to branch conversations | **Stateless** or **Conversations API** |

## 🧪 Testing Scripts

Run the tests to see each approach in action:

```bash
# Upgrade SDK first
pip install --upgrade openai

# Set API key
export OPENAI_API_KEY=your_key_here

# Run tests
python test_background_mode.py          # Basic functionality
python test_tool_calling.py             # Tool calling tests
python test_conversations_proper.py     # Conversations API
python test_stateless_proper.py         # Stateless context ⭐
```

## 📖 Documentation

- **[FINDINGS.md](FINDINGS.md)** - Complete detailed findings with all test results
- **[DEEP_RESEARCH_COMPARISON.md](DEEP_RESEARCH_COMPARISON.md)** - Can Background Mode replace Deep Research?
- **[STREAMING_PERFORMANCE.md](STREAMING_PERFORMANCE.md)** - Streaming latency analysis and persistence strategy
- **[COMPACTION_FINDINGS.md](COMPACTION_FINDINGS.md)** - Conversations API and compaction (context compression)
- **[test_*.py](.)** - Runnable test scripts demonstrating each feature

## 🔑 Key Discoveries

1. **Stateless context passing works** - You can pass `output` as `input`!
2. **Three context management options** - Choose based on your use case
3. **Compaction is functional (non-mutating)** - Compresses history without changing original conversation
4. **Streaming has ~25ms per-chunk overhead** - Background mode adds persistence coordination
5. **No synchronous disk writes** - Persistence is async/batched, not per-chunk
6. **No MCP auth prompting** - Authentication must be handled before API call
7. **No tool confirmation** - Tools execute autonomously (no `requires_action` state)
8. **Conversations API requires SDK v2.15.0+** - Upgrade if using older version

## ❓ Can Background Mode Replace Deep Research?

**Short answer**: Background Mode is a **toolkit for building** research workflows, not a drop-in replacement.

### Timing Results

Our tests showed:
- **Simple tasks**: 14-50 seconds
- **With reasoning**: 14-18 seconds (243-273 reasoning tokens)
- **Token usage**: ~500-900 tokens per task (very efficient!)

### Key Differences

| Feature | Background Mode | Deep Research |
|---------|----------------|---------------|
| Duration | Seconds to ~1 minute | Minutes to hours |
| Automation | Manual orchestration | Automatic |
| Web search | Define tools yourself | Built-in |
| Cost | You control | Automatic (likely higher) |

**Use Background Mode when:**
- You want full control over the workflow
- You have custom tools/data sources
- Tasks complete in minutes, not hours
- Cost optimization matters

**See [DEEP_RESEARCH_COMPARISON.md](DEEP_RESEARCH_COMPARISON.md) for detailed analysis and code examples.**

---

## ⚡ Streaming Performance

**Question**: Does background mode write each chunk to storage before returning it?

**Answer**: NO - but it does ~25ms of coordination work per chunk.

### Comparison

| Mode | Chunk Latency | Speed | Persistence |
|------|--------------|-------|-------------|
| **Standard** (background=False) | 0.10ms | ⚡⚡⚡ Instant | None |
| **Background** (background=True) | 24.68ms | ⚡⚡ Fast | Async/batched |

### Key Findings

1. **Standard mode**: Pure memory streaming (0.1ms per chunk)
2. **Background mode**: +24.6ms coordination overhead per chunk
3. **NOT waiting for disk**: 25ms is too fast for sync writes
4. **Likely buffering**: Adding to in-memory WAL buffer
5. **Actual writes**: Batched asynchronously (~5-10 writes per response, not 549!)

### Verdict

✅ Background mode does NOT do synchronous disk writes per chunk
✅ Adds ~25ms coordination overhead for persistence tracking
✅ Still fast enough for real-time streaming (~40 chunks/second)
❌ Standard mode is faster if you don't need persistence

**See [STREAMING_PERFORMANCE.md](STREAMING_PERFORMANCE.md) for detailed latency analysis.**

---

## 🗜️ Conversation Compaction

**Question**: Does compaction permanently mutate the conversation?

**Answer**: NO - compaction is a **one-time, functional operation** that creates a compressed copy.

### Key Findings

```python
# 1. Create conversation and build history
conversation = client.conversations.create(metadata={"test": "compaction"})

# 2. Add responses to build history...

# 3. Compact the conversation
items = client.conversations.items.list(conversation.id)
compacted = client.responses.compact(
    model="gpt-5.2",
    input=items.data,
)

# 4. Original conversation still works!
resp = client.responses.create(
    model="gpt-5.2",
    input="Continue conversation",
    conversation=conversation.id,  # Still has full history!
)
```

### Test Results

| Aspect | Result |
|--------|--------|
| **Mutates original?** | ❌ NO - Original conversation unchanged |
| **Token reduction** | ✅ 530 tokens → 464 tokens (12.5% savings) |
| **Lossless** | ✅ YES - Full context preserved |
| **Reusable** | ✅ YES - Pass `compacted.output` to next request |
| **Format** | Plaintext recent messages + encrypted old history |

### Compacted Output Structure

```python
compacted.output = [
    # Recent messages (plaintext)
    {"type": "message", "role": "user", "content": "..."},
    {"type": "message", "role": "user", "content": "..."},

    # Compressed history
    {
        "type": "compaction",
        "encrypted_content": "gAAAAABpfOA40bRAr...",  # Token-efficient
    }
]
```

### When to Use

✅ **Use compaction for:**
- Long conversations (> 20 messages)
- Cost optimization
- Archiving conversations
- Approaching context limits

❌ **Don't use for:**
- Short conversations (< 10 messages)
- Debugging (need readable history)
- Very frequent requests (overhead)

**See [COMPACTION_FINDINGS.md](COMPACTION_FINDINGS.md) for detailed analysis and patterns.**

---

## 📝 Summary

OpenAI's Background Responses API provides flexible context management with three distinct approaches. The newly discovered **stateless context passing** gives you full control similar to Chat Completions, while the **Conversations API** provides convenience with server-managed context.

Background Mode is excellent for building **custom research workflows** where you control the multi-step logic, but it's not a replacement for fully automated deep research products.

For complete details, see [FINDINGS.md](FINDINGS.md).

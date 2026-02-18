# Quick Summary: Background Mode Testing Results

## ✅ Key Discoveries

### 1. Stateless Context Passing Works!
You can pass `resp.output` directly as `input` to the next request - just like Chat Completions API!

### 2. Three Context Management Options
- **Stateless**: Full control, works across sessions
- **Conversations API**: Server-managed (requires SDK v2.15.0+)
- **previous_response_id**: Simplest for linear follow-ups

### 3. Performance is Fast
- Most tasks: **14-50 seconds**
- With reasoning: **14-18 seconds** (only 243-273 reasoning tokens)
- Tool calling: **~5 seconds**

### 4. Background Mode ≠ Deep Research
- Background Mode: Building blocks for custom workflows (seconds to minutes)
- Deep Research: Automated multi-step research (minutes to hours)

## 📊 Can It Replace Deep Research?

**Not directly, but you can build your own!**

✅ **Use Background Mode when:**
- You want full control over the research workflow
- You have custom tools (databases, APIs, etc.)
- Tasks complete in minutes
- Cost optimization matters

❌ **Don't expect:**
- Automatic web searches
- Self-guided exploration
- Multi-step iteration without your code

## 🔧 Tool Calling & MCP

✅ **Works**: Tools execute autonomously
✅ **Web search**: Available as a tool type
❌ **No auth prompting**: Must pre-configure authentication
❌ **No confirmation**: No human-in-the-loop approval

## 💰 Cost

Very reasonable! Our tests:
- Reasoning task: **521 tokens** (~$0.003)
- Simple generation: **900 tokens** (~$0.005)
- Tool calling: **111 tokens** (~$0.001)

## 📚 Files Created

1. **FINDINGS.md** - Complete detailed findings (all test results)
2. **DEEP_RESEARCH_COMPARISON.md** - Background Mode vs Deep Research
3. **README.md** - Quick start guide
4. **test_*.py** - Working test scripts for all features

## 🚀 Quick Start

```python
from openai import OpenAI
client = OpenAI()

# Option 1: Stateless (full control)
resp1 = client.responses.create(
    model="gpt-5.2",
    input="Explain Paxos.",
    background=True,
)

# Build context manually
context = [
    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Explain Paxos."}]},
    {"type": "message", "role": "assistant", "content": resp1.output[0].content},
    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Compare to Raft."}]}
]

resp2 = client.responses.create(
    model="gpt-5.2",
    input=context,  # Stateless!
    background=True,
)

# Option 2: Conversations API (convenient)
conv = client.conversations.create()
resp3 = client.responses.create(
    model="gpt-5.2",
    input="Explain Paxos.",
    background=True,
    conversation=conv.id,
)

# Option 3: Simple linking
resp4 = client.responses.create(
    model="gpt-5.2",
    input="Compare to Raft.",
    background=True,
    previous_response_id=resp3.id,
)
```

## 🎯 Bottom Line

Background Mode is **powerful and flexible** for building custom workflows, but requires you to write the orchestration logic. It's perfect when you need:
- Reliable long-running tasks
- Custom tools and data sources
- Full control over cost and workflow
- Tasks that complete in seconds to minutes

For automatic deep research with web searches and iterative refinement, you'd need to build that workflow yourself or use a dedicated deep research product.

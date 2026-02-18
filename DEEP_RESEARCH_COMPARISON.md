# Can Background Mode Replace Deep Research?

## TL;DR

**Background Mode can be used as a building block for deep research workflows, but it's NOT a drop-in replacement for OpenAI's Deep Research product.**

- ✅ Use it to **build your own** multi-step research workflow
- ❌ Don't expect **automatic** deep research behavior out of the box

---

## Timing Comparison

### Background Mode Performance

From our tests:

| Task Type | Time | Tokens | Notes |
|-----------|------|--------|-------|
| Simple text generation | ~45-50s | ~900 | Complex technical explanation |
| With reasoning (high effort) | ~14-18s | ~521 | 243-273 reasoning tokens |
| Tool calling (2 parallel calls) | ~5s | ~111 | Weather lookups |
| Streaming response | ~40s | ~924 | 549 streaming events |
| 3 parallel tasks | ~21s each | ~1000 each | Run simultaneously |

**Key observation**: Background mode tasks complete in **seconds to ~1 minute**, not hours.

### Deep Research (Product) Performance

Typical characteristics:
- **Duration**: Several minutes to hours
- **Workflow**: Multi-step iterative research
- **Automation**: Automatic web searches, follow-up questions
- **Cost**: Higher due to multiple search/reasoning cycles

---

## Feature Comparison

### What Background Mode HAS ✅

1. **Extended reasoning** (`reasoning={"effort": "high"}`)
   - Uses reasoning tokens for deeper analysis
   - Completed in ~14-18 seconds in our test
   - Cost-effective (243-273 reasoning tokens)

2. **Tool calling**
   - Can define custom tools (databases, APIs, etc.)
   - Web search tool appears to be available
   - Tools execute autonomously in background

3. **Long-running reliability**
   - No timeout issues
   - Polling-based status tracking
   - Can handle tasks lasting minutes

4. **Context management**
   - Three options: stateless, conversations, previous_response_id
   - Can chain multiple responses for iterative refinement

### What Background Mode LACKS ❌

1. **Automatic multi-step research**
   - Won't automatically break down research questions
   - Doesn't automatically search multiple sources
   - No built-in iterative refinement loop

2. **Automatic web search orchestration**
   - Won't automatically decide when to search
   - Won't synthesize results across searches
   - Requires explicit tool definitions and logic

3. **Self-guided exploration**
   - Doesn't autonomously ask follow-up questions
   - Won't automatically refine based on findings
   - Requires you to orchestrate the workflow

---

## Can You Build Deep Research with Background Mode?

### Yes! Here's How:

```python
from openai import OpenAI
import time

client = OpenAI()

def deep_research_workflow(topic):
    """Implement deep research using background mode as building blocks."""

    results = []

    # Step 1: Initial analysis with reasoning
    print("Step 1: Analyzing topic...")
    resp1 = client.responses.create(
        model="gpt-5.2",
        input=f"Analyze this topic and identify 3 key research questions: {topic}",
        background=True,
        reasoning={"effort": "high"},
    )

    # Poll for completion
    while resp1.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp1 = client.responses.retrieve(resp1.id)

    results.append(resp1)

    # Step 2: For each research question, do web search
    # (You would define web_search tool and parse questions)
    print("Step 2: Researching questions...")
    resp2 = client.responses.create(
        model="gpt-5.2",
        input="Use web search to find recent information on [question from resp1]",
        background=True,
        tools=[{"type": "web_search"}],
        previous_response_id=resp1.id,  # Include context
    )

    while resp2.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp2 = client.responses.retrieve(resp2.id)

    results.append(resp2)

    # Step 3: Synthesize findings
    print("Step 3: Synthesizing findings...")

    # Build conversation history
    history = []
    for resp in results:
        if resp.output:
            history.append({
                "type": "message",
                "role": "assistant",
                "content": resp.output[0].content
            })

    history.append({
        "type": "message",
        "role": "user",
        "content": [{
            "type": "input_text",
            "text": "Synthesize all findings into a comprehensive research report."
        }]
    })

    resp3 = client.responses.create(
        model="gpt-5.2",
        input=history,  # Stateless context passing
        background=True,
        reasoning={"effort": "high"},
    )

    while resp3.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp3 = client.responses.retrieve(resp3.id)

    return resp3


# Use it
report = deep_research_workflow("Distributed consensus algorithms")
```

### What You Need to Build:

1. **Multi-step orchestration logic** in your application
2. **Tool definitions** for web search, databases, etc.
3. **Iteration logic** for follow-up questions
4. **Synthesis logic** to combine findings
5. **Error handling** for failed searches/tools

---

## When to Use Each

### Use Background Mode When:

✅ You want **control** over the research workflow
✅ You have **custom tools** (proprietary databases, APIs)
✅ You need **specific orchestration** logic
✅ Tasks complete in **minutes, not hours**
✅ You want to **minimize cost** by controlling iteration

### Use Deep Research Product When:

✅ You want **automatic** research out of the box
✅ You need **web-wide** information gathering
✅ Research can take **hours** if needed
✅ You want **minimal code** - just ask a question
✅ You're okay with **higher cost** for automation

---

## Cost Comparison

### Background Mode (DIY Research)

**Example 3-step research workflow:**
```
Step 1: Initial analysis (500 tokens) = ~$0.003
Step 2: Web searches (1000 tokens)   = ~$0.006
Step 3: Synthesis (800 tokens)       = ~$0.005
Total: ~2300 tokens                   = ~$0.014
```

You control the cost by:
- Limiting max_output_tokens
- Choosing when to iterate
- Selecting which sources to search

### Deep Research Product

- Cost likely **higher** due to automatic iteration
- Multiple searches and refinement steps
- But saves **development time**

---

## Recommendation

**Background Mode is NOT a replacement for Deep Research - it's a toolkit for building your own research workflows.**

**Choose Background Mode if:**
- You need custom research logic
- You want full control and transparency
- You have specific tools/data sources
- Cost optimization is important

**Choose Deep Research Product if:**
- You want turnkey research capability
- Web-wide information gathering is critical
- You value convenience over cost
- Development time is more expensive than API costs

**Use Both Together:**
- Use Deep Research for initial exploration
- Use Background Mode for refined analysis with custom tools
- Combine general research with proprietary data

---

## Example: Hybrid Approach

```python
# Use Deep Research for initial exploration (hypothetical - assuming it exists)
initial_findings = deep_research_api.research(
    "Latest trends in distributed systems"
)

# Use Background Mode for custom analysis with your tools
custom_analysis = client.responses.create(
    model="gpt-5.2",
    input=f"""
    Based on this research:
    {initial_findings}

    Now analyze our proprietary database to see how our system
    compares to these trends.
    """,
    background=True,
    tools=[{"type": "function", "name": "query_proprietary_db", ...}],
    reasoning={"effort": "high"},
)
```

---

## Summary

| Aspect | Background Mode | Deep Research |
|--------|----------------|---------------|
| **Automation** | Manual orchestration | Automatic |
| **Duration** | Seconds to minutes | Minutes to hours |
| **Control** | Full control | Limited control |
| **Tools** | Custom definitions | Built-in web search |
| **Cost** | You optimize | Automatic (likely higher) |
| **Effort** | High dev effort | Low dev effort |
| **Best for** | Custom workflows | General research |

**Bottom line**: Background Mode gives you the **primitives** to build research workflows, but you need to write the **orchestration code** yourself. It's powerful and flexible, but not a drop-in replacement for automated deep research.

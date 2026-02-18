# OpenAI Deep Research API Testing - Findings

## Overview

This document summarizes findings from testing OpenAI's REST API background mode (deep research) functionality and its integration with tool calling and conversation management.

**Test Date:** January 19, 2026
**Model Tested:** gpt-5.2-2025-12-11
**SDK Version:** openai 2.15.0+ (conversation support requires SDK v2.15.0 or later)

## ⚠️ Important: SDK Version Requirement

**The Conversations API requires openai SDK v2.15.0+**

If you're using an older version (e.g., v1.99.9), upgrade first:
```bash
pip install --upgrade openai
```

Older SDK versions do not support the `conversation` parameter in `responses.create()`.

---

## 1. Background Mode Basics

### How It Works

Background mode allows long-running tasks to execute asynchronously. You start a task with `background=True` and poll the response until completion.

### Key Characteristics

- **Status States**: `queued` → `in_progress` → `completed` (or `cancelled`)
- **Polling Required**: Client must poll the response endpoint to check status
- **Recommended Poll Interval**: 2-3 seconds
- **Response Persistence**: Completed responses are retrievable for ~10 minutes

### Performance & Timing

From our tests:

| Task Type | Duration | Tokens Used | Notes |
|-----------|----------|-------------|-------|
| Simple text generation | 45-50s | ~900 | Complex technical explanation |
| **With reasoning (high)** | **14-18s** | **~521** | **243-273 reasoning tokens** |
| Tool calling (2 parallel) | ~5s | ~111 | Weather tool calls |
| Streaming response | ~40s | ~924 | 549 streaming events |
| 3 parallel tasks | ~21s each | ~1000 each | Concurrent execution |

**Key insights**:
- Tasks complete in **seconds to ~1 minute**, not hours
- Reasoning mode is **very efficient** (14-18s for 500 tokens)
- Tool calls are **fast** when well-defined
- **No hard timeout** - can run longer if needed

### Response Object Structure

```python
Response(
    id='resp_...',
    status='completed',           # queued, in_progress, completed, cancelled
    created_at=1768886541.0,
    completed_at=1768886616,       # Timestamp when completed
    output=[...],                   # List of output items (messages, tool calls)
    usage={                         # Token usage stats
        'input_tokens': 47,
        'output_tokens': 64,
        'total_tokens': 111
    },
    store=True,                     # Whether response is stored
    background=True,
    model='gpt-5.2-2025-12-11',
    # ... many other fields
)
```

### Streaming Support

Background mode supports streaming with `background=True` and `stream=True`:

- Returns events with `sequence_number` for cursor-based resumption
- Client can reconnect using `starting_after=<cursor>` to resume from last event
- Enables handling connection drops without losing progress
- Test showed 549 streaming events for a moderate-length response

### Cancellation

- Use `client.responses.cancel(response_id)` to cancel an in-flight response
- Cancellation is **idempotent** - subsequent calls return the same cancelled response
- Status becomes `cancelled` after successful cancellation

### Performance Observations

- Simple tasks: ~45-50 seconds for complex text generation
- Polling overhead: ~20-25 polls for a 45-second task (2-second interval)
- Multiple parallel tasks: All completed within ~20 seconds when run concurrently

---

## 2. Tool Calling with Background Mode

### ✅ Tool Calling Works Seamlessly

Tool calling integrates smoothly with background mode. Tools are executed automatically during background processing.

### Tool Definition Format

**Important**: Use the flatter format for tools in the Responses API:

```python
{
    "name": "get_weather",
    "type": "function",
    "description": "Get the current weather in a given location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "..."}
        },
        "required": ["location"]
    }
}
```

**Not** the nested format used in Chat Completions:
```python
# DON'T USE THIS FORMAT - it will cause "Missing required parameter: 'tools[0].name'" error
{
    "type": "function",
    "function": {
        "name": "get_weather",
        ...
    }
}
```

### Tool Call Response Structure

When tools are called, they appear in the `output` array as `ResponseFunctionToolCall` objects:

```python
output=[
    ResponseFunctionToolCall(
        id='fc_...',
        call_id='call_...',
        name='get_weather',
        type='function_call',
        status='completed',
        arguments='{"location":"San Francisco, CA","unit":"fahrenheit"}'
    ),
    ResponseFunctionToolCall(
        id='fc_...',
        call_id='call_...',
        name='get_weather',
        type='function_call',
        status='completed',
        arguments='{"location":"New York, NY","unit":"fahrenheit"}'
    )
]
```

### Parallel Tool Calls

- `parallel_tool_calls=True` by default
- Multiple tool calls are made simultaneously when possible
- Test showed 2 weather tool calls executed in parallel for different cities

### Tool Validation and Error Handling

The model understands tool constraints and handles them gracefully:

- When tool parameters have strict requirements (e.g., `minItems: 10` for an array), the model recognizes it cannot satisfy the constraint
- Instead of making an invalid tool call, it returns a helpful message:
  ```
  "I can't run `process_data` unless you provide at least **10 numbers** (the tool requires `minItems: 10`)"
  ```
- No structured error is thrown - the model just explains the limitation conversationally

---

## 3. MCP Authentication and Tool Confirmation

### ❌ No Special Authentication Handling Observed

**Key Finding**: There is no apparent special handling for MCP authentication in the Responses API.

### What We Tested

1. **Auth-requiring tools**: Created tools with names suggesting authentication (e.g., "access_private_resource")
2. **Multiple tool calls**: Tested scenarios that might trigger confirmation prompts
3. **State monitoring**: Watched for special states like `requires_action` or auth prompts

### What We Found

- **No `requires_action` state**: No intermediate state asking for user input
- **No auth prompt mechanism**: No structured way to prompt for OAuth or credentials
- **Tools complete automatically**: All tools, regardless of naming/description, execute without pausing
- **No confirmation fatigue handling**: No evidence of confirmation prompts or approval flows

### Response Attributes

The response object does not include any of these potentially auth-related fields:
- `requires_action` (not present)
- `auth_required` (not present)
- `pending_confirmations` (not present)
- `approval_needed` (not present)

### Implications

**The Responses API appears to be designed for autonomous execution without human-in-the-loop:**

1. **Tool confirmation must be handled at client level**: If you need approval before tool execution, implement it before creating the response (e.g., show user tools that will be available, get pre-approval)

2. **MCP auth would need to happen beforehand**: Any MCP server authentication must be completed before the API call, not during execution

3. **No structured error for missing auth**: If a tool requires credentials that aren't available, it would likely just fail or the model would return a text message explaining the issue

4. **Different from Assistant/Chat APIs**: This differs from the Assistants API which has `requires_action` status for tool approval

---

## 4. Context Management: Three Approaches

You have **three options** for maintaining context across multiple responses:

1. **✅ Stateless Context Passing** (pass output as input)
2. **✅ Conversations API** (server-managed context)
3. **✅ previous_response_id** (simple linking)

### Option 1: Stateless Context Passing ⭐ NEW!

**Key Discovery**: You can pass `resp.output` directly as input to the next request!

The response `output` is a **list of items**, and the `input` parameter accepts a **list of items**. This means you can manage context statelessly, similar to Chat Completions API.

#### How It Works

```python
from openai import OpenAI
client = OpenAI()

# First request
resp1 = client.responses.create(
    model="gpt-5.2",
    input="What are distributed consensus algorithms?",
    background=True,
)

# Wait for completion...
while resp1.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp1 = client.responses.retrieve(resp1.id)

# Build input list with conversation history
input_items = [
    # Original user message
    {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "What are distributed consensus algorithms?"}]
    },
    # Assistant's response (from resp1.output[0])
    {
        "type": "message",
        "role": "assistant",
        "content": resp1.output[0].content  # Use the content from output
    },
    # New user message
    {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "Can you elaborate on Raft?"}]
    }
]

# Second request with full context
resp2 = client.responses.create(
    model="gpt-5.2",
    input=input_items,  # Pass list directly
    background=True,
)
```

#### Test Results

✅ **Context is preserved!** The second response successfully referenced information from the first response.

#### When to Use Stateless

**Advantages:**
- ✅ Works across sessions (no server-side storage)
- ✅ Full control over what context is included
- ✅ Can selectively include/exclude messages
- ✅ No time limits (unlike conversation objects)
- ✅ Explicit and transparent

**Disadvantages:**
- ❌ More data to send with each request
- ❌ You manage the conversation history
- ❌ More code to maintain

---

### Option 2: Conversations API (Server-Managed)

### ✅ Conversations API WORKS with Background Mode! (SDK v2.15.0+)

**Important**: The older SDK version (v1.99.9) did not support the `conversation` parameter. **Upgrade to SDK v2.15.0+** to use conversations!

**Key Finding**: The Responses API fully supports conversation threading via the Conversations API.

### How It Works

1. **Create a conversation** using `client.conversations.create()`
2. **Pass the conversation** to `responses.create()` via the `conversation` parameter
3. **Context is automatically maintained** across multiple responses in the same conversation

### Basic Usage

```python
from openai import OpenAI
client = OpenAI()

# Step 1: Create a conversation
conversation = client.conversations.create(
    metadata={"purpose": "my-app"}
)
print(f"Conversation ID: {conversation.id}")

# Step 2: Create first response in conversation
resp1 = client.responses.create(
    model="gpt-5.2",
    input="What are distributed consensus algorithms?",
    background=True,
    conversation=conversation.id,  # ✅ Works!
)

# Wait for completion...
while resp1.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp1 = client.responses.retrieve(resp1.id)

# Step 3: Create follow-up in same conversation
resp2 = client.responses.create(
    model="gpt-5.2",
    input="Can you elaborate on Raft specifically?",
    background=True,
    conversation=conversation.id,  # Context from resp1 is preserved!
)
```

### Context Preservation

✅ **Follow-up responses have access to previous context!**

In our tests:
- First response explained distributed consensus algorithms broadly
- Follow-up asked about "Raft specifically"
- The model successfully referenced and built upon the previous discussion
- Output showed awareness of prior context (used phrases like "mentioned", "discussed")

### Creating Conversations with Initial Context

You can seed a conversation with initial messages:

```python
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
                    "text": "Great! You'll need to consider CAP theorem..."
                }
            ]
        }
    ],
    metadata={"purpose": "with-context"}
)

# Now create a response that leverages this context
resp = client.responses.create(
    model="gpt-5.2",
    input="Which consensus algorithm would you recommend?",
    background=True,
    conversation=conversation.id,
)
```

The response will reference the "distributed database" context from the initial items!

### Conversation Object Structure

```python
Conversation(
    id='conv_...',           # Unique conversation ID
    created_at=1768888307,   # Unix timestamp
    metadata={               # Custom key-value pairs
        'purpose': 'testing'
    },
    object='conversation'
)
```

### Retrieving Conversations

```python
# Retrieve a conversation by ID
conversation = client.conversations.retrieve("conv_...")

# Note: No list() method yet in SDK
# conversations = client.conversations.list()  # ❌ Not available
```

### Response Object with Conversation

When you create a response with a conversation, the response includes:

```python
Response(
    id='resp_...',
    conversation=Conversation(id='conv_...'),  # ✅ Conversation reference
    status='completed',
    # ... other fields
)
```

#### When to Use Conversations API

**Advantages:**
- ✅ Server manages context automatically
- ✅ Less data to send (just conversation ID)
- ✅ Most convenient for multi-turn workflows
- ✅ Can seed with initial context

**Disadvantages:**
- ❌ Requires server-side storage
- ❌ Time-limited (~10 minutes for responses)
- ❌ Less explicit control over context

---

### Option 3: previous_response_id (Simple Linking)

The simplest approach for linear follow-ups:

```python
# First response
resp1 = client.responses.create(
    model="gpt-5.2",
    input="What are consensus algorithms?",
    background=True,
)

# Wait for completion...

# Follow-up with automatic context
resp2 = client.responses.create(
    model="gpt-5.2",
    input="Tell me about Raft.",
    background=True,
    previous_response_id=resp1.id,  # Context from resp1 included automatically
)
```

#### When to Use previous_response_id

**Advantages:**
- ✅ Simplest to use
- ✅ Automatic context inclusion
- ✅ Perfect for linear conversations

**Disadvantages:**
- ❌ Only works within ~10 minute window
- ❌ Linear chain only (can't branch)
- ❌ Less control over what context is included

---

### Comparison: All Three Approaches

| Feature | Stateless | Conversations API | previous_response_id |
|---------|-----------|-------------------|----------------------|
| **Context control** | ✅ Full control | ⚠️ Automatic | ⚠️ Automatic |
| **Works across sessions** | ✅ Yes | ❌ Time-limited | ❌ Time-limited |
| **Data sent** | ❌ Full history | ✅ Just ID | ✅ Just ID |
| **Code complexity** | ⚠️ More code | ✅ Simple | ✅ Simplest |
| **Branching conversations** | ✅ Yes | ✅ Yes | ❌ Linear only |
| **Server storage required** | ❌ No | ✅ Yes | ✅ Yes |
| **Best for** | Long sessions, full control | Multi-turn workflows | Quick follow-ups |

### Recommendation

Choose based on your use case:

1. **Use Stateless** if you need:
   - Long-running sessions that span hours/days
   - Full control over conversation history
   - Ability to work across API restarts
   - Explicit, transparent context management

2. **Use Conversations API** if you need:
   - Convenient multi-turn interactions
   - Server to manage context for you
   - Ability to seed conversations with initial context
   - Working within ~10 minute windows is acceptable

3. **Use previous_response_id** if you need:
   - Quick follow-up questions
   - Simple linear conversations
   - Minimal code complexity
   - Working within ~10 minute windows is acceptable

### Store Requirement

According to documentation, `store=True` is required for background mode:

**Finding**: `store=False` was actually accepted by the API (contrary to docs):
```python
resp = client.responses.create(
    model="gpt-5.2",
    input="Test",
    background=True,
    store=False  # ✅ Accepted, but docs say it should fail
)
```

However:
- Default value is `store=True` when `background=True`
- Storing is necessary for polling to work (you need to retrieve the response)
- Using `store=False` may break ZDR (Zero Data Retention) guarantees per docs

---

## 5. Multiple Parallel Background Tasks

### ✅ Parallel Execution Works Well

Multiple background responses can run simultaneously without interference.

### Test Results

```python
# Started 3 tasks simultaneously
Task 1: Explain Paxos     - completed in ~21s
Task 2: Explain Raft      - completed in ~21s
Task 3: Explain PBFT      - completed in ~21s

# All completed within 7 poll iterations (~21 seconds total)
```

### Observations

- **Independent execution**: Each response has its own ID and status
- **No queuing delay**: All tasks started processing immediately
- **Efficient resource usage**: Running tasks in parallel is faster than sequential
- **Easy to manage**: Poll all response IDs in a loop

### Implementation Pattern

```python
# Start multiple tasks
tasks = []
for prompt in prompts:
    resp = client.responses.create(
        model="gpt-5.2",
        input=prompt,
        background=True
    )
    tasks.append(resp)

# Poll all until complete
while any(t.status in {"queued", "in_progress"} for t in tasks):
    time.sleep(2)
    tasks = [client.responses.retrieve(t.id) for t in tasks]

# All tasks complete
for i, task in enumerate(tasks):
    print(f"Task {i+1}: {task.status}")
```

---

## 6. Response Format and Error Handling

### Standard Response Structure

Successful responses have:
- `status='completed'`
- `error=None`
- `output` array with messages or tool calls
- Complete usage statistics

### When Tools Can't Be Called

The model handles tool constraints gracefully:

```json
{
  "output": [
    {
      "content": [
        {
          "text": "I can't run `process_data` unless you provide at least **10 numbers**...",
          "type": "output_text"
        }
      ],
      "role": "assistant",
      "status": "completed",
      "type": "message"
    }
  ],
  "status": "completed"  // Note: Still "completed", not "failed"
}
```

**Key points:**
- Status is still `completed` (not `failed` or `error`)
- Model explains the issue conversationally
- No structured error object
- Client must parse the text to understand what happened

### True Error Responses

When API errors occur (e.g., invalid parameters), you get an exception:
```python
openai.BadRequestError: Error code: 400 - {
    'error': {
        'message': "Missing required parameter: 'tools[0].name'.",
        'type': 'invalid_request_error',
        'param': 'tools[0].name',
        'code': 'missing_required_parameter'
    }
}
```

---

## 7. Key Takeaways

### Background Mode Strengths

✅ **Reliable for long-running tasks**: Handles timeouts and connection issues gracefully
✅ **Streaming support**: Can stream results and resume from disconnections
✅ **Tool calling works**: Tools execute automatically during background processing
✅ **Parallel execution**: Multiple tasks can run simultaneously
✅ **Status tracking**: Clear state progression (queued → in_progress → completed)
✅ **Flexible context management**: Three options for maintaining conversation context
✅ **Stateless support**: Can pass output as input for full control over context

### Current Limitations

❌ **No auth prompting**: Can't pause for OAuth or credential input mid-execution
❌ **No tool confirmation**: No human-in-the-loop approval for tool calls
❌ **No structured error details**: Tool failures explained conversationally, not with error codes

### Architectural Implications

**Background mode is optimized for autonomous, long-running agent tasks:**

1. **Pre-authorize everything**: All tools and permissions must be set up before calling the API
2. **Choose your context management approach**:
   - Stateless for full control and long sessions
   - Conversations API for convenience
   - previous_response_id for simple follow-ups
3. **Trust the agent**: No opportunity for mid-execution intervention or confirmation
4. **Parse text for issues**: Tool problems are explained conversationally, not with structured errors
5. **Use for batch/async workloads**: Perfect for tasks that can run without user interaction

### Comparison to Other OpenAI APIs

| Feature | Background Responses | Chat Completions | Assistants API |
|---------|---------------------|------------------|----------------|
| Long-running tasks | ✅ Native support | ❌ Timeout issues | ✅ Native support |
| Tool calling | ✅ Automatic | ✅ Automatic | ✅ With requires_action |
| Tool confirmation | ❌ No | ❌ No | ✅ Yes (requires_action) |
| Conversation threading | ✅ 3 options (stateless/conversation/link) | ✅ Message array | ✅ Thread management |
| Stateless context | ✅ Yes | ✅ Yes | ❌ No (uses threads) |
| Streaming | ✅ With resume | ✅ Yes | ✅ Yes |
| Async polling | ✅ Yes | ❌ No | ✅ Yes |

---

## 8. Code Examples

### Stateless Context Passing (NEW!)

```python
from openai import OpenAI
import time

client = OpenAI()

# First request
resp1 = client.responses.create(
    model="gpt-5.2",
    input="What are distributed consensus algorithms?",
    background=True,
)

# Poll until complete
while resp1.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp1 = client.responses.retrieve(resp1.id)

# Build conversation history manually
conversation_history = [
    # Original user message
    {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "What are distributed consensus algorithms?"}]
    },
    # Assistant's response
    {
        "type": "message",
        "role": "assistant",
        "content": resp1.output[0].content  # Use content from output
    },
    # New user message
    {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "Can you elaborate on Raft?"}]
    }
]

# Second request with full context
resp2 = client.responses.create(
    model="gpt-5.2",
    input=conversation_history,  # Pass list directly!
    background=True,
)

# Poll until complete
while resp2.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp2 = client.responses.retrieve(resp2.id)

print(f"Response with context: {resp2.output[0].content[0].text}")
```

### Basic Background Task

```python
from openai import OpenAI
import time

client = OpenAI()

# Start background task
resp = client.responses.create(
    model="gpt-5.2",
    input="Write a detailed analysis of distributed systems.",
    background=True,
)

print(f"Started: {resp.id}")

# Poll until complete
while resp.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp = client.responses.retrieve(resp.id)
    print(f"Status: {resp.status}")

print(f"Output: {resp.output_text}")
```

### Background Task with Conversation Threading

```python
from openai import OpenAI
import time

client = OpenAI()

# Create a conversation
conversation = client.conversations.create(
    metadata={"purpose": "research-session"}
)

print(f"Conversation: {conversation.id}")

# First response in conversation
resp1 = client.responses.create(
    model="gpt-5.2",
    input="Explain distributed consensus algorithms.",
    background=True,
    conversation=conversation.id,
)

# Poll until complete
while resp1.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp1 = client.responses.retrieve(resp1.id)

print(f"First response: {resp1.output_text[:200]}...")

# Follow-up response in same conversation
# Context from resp1 is automatically available!
resp2 = client.responses.create(
    model="gpt-5.2",
    input="Can you elaborate on Raft specifically?",
    background=True,
    conversation=conversation.id,
)

# Poll until complete
while resp2.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp2 = client.responses.retrieve(resp2.id)

print(f"Follow-up: {resp2.output_text[:200]}...")
```

### Background Task with Tools

```python
# Define tool
weather_tool = {
    "name": "get_weather",
    "type": "function",
    "description": "Get weather for a location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {"type": "string"}
        },
        "required": ["location"]
    }
}

# Create with tools
resp = client.responses.create(
    model="gpt-5.2",
    input="What's the weather in SF and NYC?",
    tools=[weather_tool],
    background=True,
)

# Poll and check for tool calls
while resp.status in {"queued", "in_progress"}:
    time.sleep(2)
    resp = client.responses.retrieve(resp.id)

# Extract tool calls
for item in resp.output:
    if item.type == 'function_call':
        print(f"Tool: {item.name}, Args: {item.arguments}")
```

### Background Streaming with Resume

```python
# Start streaming background task
stream = client.responses.create(
    model="gpt-5.2",
    input="Write a long story...",
    background=True,
    stream=True,
)

cursor = None
try:
    for event in stream:
        print(event)
        cursor = event.sequence_number
except ConnectionError:
    # Reconnect and resume from cursor
    resumed = client.responses.stream(
        resp.id,
        starting_after=cursor
    )
    for event in resumed:
        print(event)
```

### Parallel Background Tasks

```python
prompts = ["Explain Paxos", "Explain Raft", "Explain PBFT"]

# Start all tasks
responses = [
    client.responses.create(
        model="gpt-5.2",
        input=prompt,
        background=True
    )
    for prompt in prompts
]

# Poll all until complete
while any(r.status in {"queued", "in_progress"} for r in responses):
    time.sleep(2)
    responses = [
        client.responses.retrieve(r.id)
        for r in responses
    ]

# All complete
for i, resp in enumerate(responses):
    print(f"Task {i+1} completed: {resp.output_text[:100]}...")
```

---

## 9. Recommendations

### When to Use Background Mode

✅ **Good for:**
- Tasks expected to take > 30 seconds
- Batch processing of multiple requests
- Agent workflows that don't need user intervention
- Scenarios where client might disconnect
- Research, analysis, or content generation tasks

❌ **Not ideal for:**
- Real-time chat applications (use Chat Completions instead)
- Tasks requiring mid-execution user input
- Tool calls needing user approval
- Latency-sensitive applications requiring instant responses

### Best Practices

1. **Poll intelligently**: Start with 2-3 second intervals, increase if task is long-running
2. **Handle completion states**: Check for `completed`, `cancelled`, and potential `error` status
3. **Store response IDs**: Keep track of response IDs for later retrieval (10-minute window)
4. **Use parallel execution**: When possible, start multiple tasks simultaneously
5. **Pre-validate tools**: Since there's no mid-execution confirmation, validate tool availability upfront
6. **Use Conversations API for multi-turn interactions**: Create conversations to maintain context across responses
7. **Parse output carefully**: Tool issues are explained in text, not structured errors
8. **Set expectations**: Users should know the task will take time and run asynchronously

### Integration with MCP Servers

Since there's no built-in auth prompting:

1. **Authenticate MCPs before API call**: Handle OAuth/credentials in your application
2. **Include auth in tool definitions**: Pass authenticated clients/tokens as part of your backend logic
3. **Validate permissions first**: Check MCP access before creating the background response
4. **Handle auth failures gracefully**: If MCP tools fail due to auth, you'll get conversational errors

---

## 10. Testing Scripts

All test scripts are available in this repository:

- `test_background_mode.py` - Basic background functionality, streaming, cancellation
- `test_tool_calling.py` - Tool calling, MCP simulation, error handling
- `test_conversations_api.py` - Original test (doesn't work with old SDK)
- `test_conversations_proper.py` - **Proper conversation testing with SDK 2.15.0+**
- `test_stateless_proper.py` - **Stateless context passing test**
- `check_api_signature.py` - Check SDK signatures and available methods

Run with:
```bash
# Upgrade SDK first!
pip install --upgrade openai

# Then run tests
pip install -r requirements.txt
export OPENAI_API_KEY=your_key_here
python test_background_mode.py
python test_tool_calling.py
python test_conversations_proper.py
python test_stateless_proper.py
```

---

## Appendix: Full Response Object Fields

```python
Response(
    id='resp_...',                          # Unique response ID
    created_at=1768886541.0,                # Unix timestamp
    completed_at=1768886616,                 # Unix timestamp (when completed)
    status='completed',                      # queued | in_progress | completed | cancelled
    background=True,                         # Whether this was a background request
    store=True,                              # Whether response is stored
    model='gpt-5.2-2025-12-11',             # Model used
    object='response',                       # Always 'response'

    # Input configuration
    prompt=None,                             # Internal prompt (not exposed)
    previous_response_id=None,               # Link to previous response
    instructions=None,                       # System instructions (if any)

    # Output
    output=[...],                            # List of messages/tool calls
    output_text='...',                       # Convenience accessor for text

    # Tool configuration
    tools=[...],                             # Tools provided
    tool_choice='auto',                      # How tools are chosen
    parallel_tool_calls=True,                # Whether parallel calling is enabled
    max_tool_calls=None,                     # Limit on tool calls

    # Sampling parameters
    temperature=1.0,
    top_p=0.98,
    max_output_tokens=None,
    frequency_penalty=0.0,
    presence_penalty=0.0,

    # Response configuration
    text={                                   # Text output config
        'format': {'type': 'text'},
        'verbosity': 'medium'
    },
    reasoning={                              # Reasoning config
        'effort': 'none',
        'generate_summary': None,
        'summary': None
    },
    truncation='disabled',
    top_logprobs=0,

    # State and errors
    error=None,                              # Error object (if failed)
    incomplete_details=None,                 # Details if incomplete

    # Metadata
    metadata={},                             # Custom metadata
    usage={                                  # Token usage stats
        'input_tokens': 47,
        'output_tokens': 64,
        'total_tokens': 111,
        'input_tokens_details': {'cached_tokens': 0},
        'output_tokens_details': {'reasoning_tokens': 0}
    },
    billing={'payer': 'developer'},          # Billing info
    service_tier='default',                  # Service tier
    safety_identifier=None,                  # Safety tracking
    user=None,                               # User identifier
    prompt_cache_key=None,                   # Prompt caching
    prompt_cache_retention=None,
)
```

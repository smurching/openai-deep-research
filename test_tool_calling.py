#!/usr/bin/env python3
"""
Test tool calling with background mode and MCP authentication scenarios.
"""

import os
import time
import json
from openai import OpenAI

# Define test tools - using flatter format for responses API
WEATHER_TOOL = {
    "name": "get_weather",
    "type": "function",
    "description": "Get the current weather in a given location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state, e.g. San Francisco, CA"
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "The temperature unit"
            }
        },
        "required": ["location"]
    }
}

DATABASE_TOOL = {
    "name": "query_database",
    "type": "function",
    "description": "Query a database that requires authentication. This simulates an MCP tool that needs auth.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The SQL query to execute"
            }
        },
        "required": ["query"]
    }
}


def test_tool_calling_background():
    """Test tool calling in background mode."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("=" * 80)
    print("TEST 1: Tool Calling in Background Mode")
    print("=" * 80)

    print("\n1. Creating background response with tools...")
    resp = client.responses.create(
        model="gpt-5.2",
        input="What's the weather like in San Francisco and New York? Please use the weather tool to get current data.",
        background=True,
        tools=[WEATHER_TOOL],
    )

    print(f"Response ID: {resp.id}")
    print(f"Initial status: {resp.status}")

    # Poll for completion
    print("\n2. Polling for completion...")
    while resp.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp = client.responses.retrieve(resp.id)
        print(f"Status: {resp.status}")

        # Check for tool calls
        if hasattr(resp, 'tool_calls') and resp.tool_calls:
            print(f"Tool calls detected: {len(resp.tool_calls)}")
            for i, tool_call in enumerate(resp.tool_calls):
                print(f"  Tool call #{i+1}: {tool_call}")

    print(f"\n3. Final status: {resp.status}")
    print(f"Full response object: {resp}")

    return resp


def test_tool_confirmation_handling():
    """Test how tool confirmation is handled in background mode."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 2: Tool Confirmation Handling")
    print("=" * 80)

    print("\n1. Testing with multiple tool calls that might require confirmation...")
    resp = client.responses.create(
        model="gpt-5.2",
        input="Use the database tool to: 1) SELECT all users, 2) DELETE old records, 3) UPDATE preferences. Query the database three times.",
        background=True,
        tools=[DATABASE_TOOL],
    )

    print(f"Response ID: {resp.id}")

    # Poll and observe what happens
    print("\n2. Observing response behavior...")
    prev_status = None

    while resp.status in {"queued", "in_progress"}:
        resp = client.responses.retrieve(resp.id)

        if resp.status != prev_status:
            print(f"\nStatus changed to: {resp.status}")
            prev_status = resp.status

            # Print full response to see structure
            print(f"Response attributes: {dir(resp)}")

            # Look for any confirmation-related fields
            for attr in ['requires_action', 'tool_calls', 'error', 'metadata']:
                if hasattr(resp, attr):
                    val = getattr(resp, attr)
                    if val:
                        print(f"{attr}: {val}")

        time.sleep(2)

    print(f"\n3. Final status: {resp.status}")
    return resp


def test_mcp_auth_simulation():
    """
    Simulate MCP authentication scenarios by observing how the API
    handles tools that might require authentication.
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 3: MCP Authentication Scenarios")
    print("=" * 80)

    # Tool that might simulate MCP server requiring auth
    auth_required_tool = {
        "name": "access_private_resource",
        "type": "function",
        "description": "Access a private resource that requires OAuth authentication",
        "parameters": {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "The ID of the private resource"
                }
            },
            "required": ["resource_id"]
        }
    }

    print("\n1. Creating request with auth-requiring tool...")
    resp = client.responses.create(
        model="gpt-5.2",
        input="Please access private resource 'user-calendar-2024' using the access_private_resource tool.",
        background=True,
        tools=[auth_required_tool],
    )

    print(f"Response ID: {resp.id}")

    # Monitor response carefully
    print("\n2. Monitoring response for auth-related states...")
    iteration = 0

    while resp.status in {"queued", "in_progress"} and iteration < 30:
        iteration += 1
        resp = client.responses.retrieve(resp.id)

        print(f"\nIteration {iteration}:")
        print(f"  Status: {resp.status}")

        # Dump the entire response structure to see what fields exist
        resp_dict = resp.model_dump() if hasattr(resp, 'model_dump') else resp.__dict__
        print(f"  Response structure: {json.dumps(resp_dict, indent=2, default=str)[:500]}...")

        time.sleep(2)

    print(f"\n3. Final status: {resp.status}")
    return resp


def test_structured_error_responses():
    """Test what error responses look like when tools fail."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print("\n" + "=" * 80)
    print("TEST 4: Structured Error Responses")
    print("=" * 80)

    # Tool with strict schema that will likely cause issues
    strict_tool = {
        "name": "process_data",
        "type": "function",
        "description": "Process data with strict requirements",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 10
                }
            },
            "required": ["data"]
        }
    }

    print("\n1. Creating request that might trigger errors...")
    resp = client.responses.create(
        model="gpt-5.2",
        input="Process some data using the process_data tool, but I won't give you enough numbers.",
        background=True,
        tools=[strict_tool],
    )

    print(f"Response ID: {resp.id}")

    # Poll and check for error structures
    print("\n2. Checking for error structures...")
    while resp.status in {"queued", "in_progress"}:
        time.sleep(2)
        resp = client.responses.retrieve(resp.id)
        print(f"Status: {resp.status}")

    print(f"\n3. Final response:")
    resp_dict = resp.model_dump() if hasattr(resp, 'model_dump') else resp.__dict__
    print(json.dumps(resp_dict, indent=2, default=str))

    return resp


if __name__ == "__main__":
    try:
        # Test 1: Basic tool calling in background mode
        result1 = test_tool_calling_background()

        # Test 2: Tool confirmation handling
        result2 = test_tool_confirmation_handling()

        # Test 3: MCP auth simulation
        result3 = test_mcp_auth_simulation()

        # Test 4: Error response structures
        result4 = test_structured_error_responses()

        print("\n" + "=" * 80)
        print("All tool calling tests completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

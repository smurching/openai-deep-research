#!/usr/bin/env python3
"""
Test conversation parameter using raw REST API calls.
"""

import os
import time
import json
import requests


def test_conversation_with_rest_api():
    """Test conversation parameter using raw REST API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = "https://api.openai.com/v1"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print("=" * 80)
    print("TEST: Conversation parameter via REST API")
    print("=" * 80)

    # Test 1: Create response with conversation parameter
    print("\n1. Creating response with conversation='test-conv-001'...")
    payload = {
        "model": "gpt-5.2",
        "input": "What are the key principles of distributed consensus?",
        "background": True,
        "conversation": "test-conv-001"
    }

    try:
        response = requests.post(
            f"{base_url}/responses",
            headers=headers,
            json=payload
        )

        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Request accepted!")
            print(f"Response ID: {data.get('id')}")
            print(f"Status: {data.get('status')}")

            # Check if conversation field is in response
            if 'conversation' in data:
                print(f"Conversation in response: {data['conversation']}")
            else:
                print("No conversation field in response")

            print(f"\nAll response keys: {list(data.keys())}")

            # Poll for completion
            resp_id = data['id']
            print(f"\n2. Polling response {resp_id}...")

            for i in range(30):
                time.sleep(2)
                poll_resp = requests.get(
                    f"{base_url}/responses/{resp_id}",
                    headers=headers
                )

                if poll_resp.status_code == 200:
                    poll_data = poll_resp.json()
                    status = poll_data.get('status')
                    print(f"   Poll {i+1}: {status}")

                    if status not in {'queued', 'in_progress'}:
                        print(f"\n3. Final status: {status}")

                        # Check for conversation field in completed response
                        if 'conversation' in poll_data:
                            conv_value = poll_data['conversation']
                            print(f"✅ Conversation field present: {conv_value}")

                            # Test 2: Create follow-up in same conversation
                            print(f"\n4. Creating follow-up response in same conversation...")
                            followup_payload = {
                                "model": "gpt-5.2",
                                "input": "Can you elaborate on Raft specifically?",
                                "background": True,
                                "conversation": conv_value
                            }

                            followup_resp = requests.post(
                                f"{base_url}/responses",
                                headers=headers,
                                json=followup_payload
                            )

                            if followup_resp.status_code == 200:
                                followup_data = followup_resp.json()
                                print(f"✅ Follow-up created: {followup_data['id']}")

                                if 'conversation' in followup_data:
                                    print(f"Follow-up conversation: {followup_data['conversation']}")

                                    if followup_data['conversation'] == conv_value:
                                        print("✅ CONVERSATION THREADING CONFIRMED!")
                                    else:
                                        print("⚠️ Different conversation value")

                                # Wait for follow-up to complete
                                print("\n5. Waiting for follow-up to complete...")
                                followup_id = followup_data['id']

                                for j in range(30):
                                    time.sleep(2)
                                    followup_poll = requests.get(
                                        f"{base_url}/responses/{followup_id}",
                                        headers=headers
                                    )

                                    if followup_poll.status_code == 200:
                                        followup_poll_data = followup_poll.json()
                                        followup_status = followup_poll_data.get('status')

                                        if followup_status not in {'queued', 'in_progress'}:
                                            print(f"Follow-up completed with status: {followup_status}")

                                            # Print output to see if it references context
                                            output = followup_poll_data.get('output', [])
                                            if output and len(output) > 0:
                                                first_output = output[0]
                                                if 'content' in first_output and len(first_output['content']) > 0:
                                                    text = first_output['content'][0].get('text', '')
                                                    print(f"\nFollow-up output (first 200 chars):")
                                                    print(text[:200])
                                            break
                            else:
                                print(f"❌ Follow-up failed: {followup_resp.status_code}")
                                print(followup_resp.text)

                        else:
                            print("❌ No conversation field in completed response")
                            print(f"Available keys: {list(poll_data.keys())}")

                        break
                else:
                    print(f"Poll error: {poll_resp.status_code}")
                    break

        else:
            print(f"❌ Request failed: {response.status_code}")
            print(f"Error: {response.text}")

            # Try to parse error details
            try:
                error_data = response.json()
                print(f"\nError details: {json.dumps(error_data, indent=2)}")
            except:
                pass

    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()


def test_conversation_without_parameter():
    """Test if conversation is auto-generated when not provided."""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = "https://api.openai.com/v1"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print("\n" + "=" * 80)
    print("TEST: Response without conversation parameter")
    print("=" * 80)

    print("\n1. Creating response WITHOUT conversation parameter...")
    payload = {
        "model": "gpt-5.2",
        "input": "Quick test",
        "background": True
    }

    response = requests.post(
        f"{base_url}/responses",
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Request accepted: {data['id']}")

        if 'conversation' in data:
            print(f"Auto-generated conversation: {data['conversation']}")
        else:
            print("No conversation field (not auto-generated)")

        # Cancel to save resources
        cancel_resp = requests.post(
            f"{base_url}/responses/{data['id']}/cancel",
            headers=headers
        )
        print(f"Cancelled to save resources")
    else:
        print(f"Request failed: {response.status_code}")


if __name__ == "__main__":
    test_conversation_with_rest_api()
    test_conversation_without_parameter()

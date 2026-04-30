"""
Test StreamableHTTP (HTTP + SSE) Client
"""
import requests
import json
import sseclient  # pip install sseclient-py
import threading
import time

SERVER_URL = "http://localhost:8001"

def listen_to_sse(session_id):
    """Listen to SSE stream in separate thread"""
    print(f"\n📡 SSE Listener started for session {session_id}")
    
    sse_url = f"{SERVER_URL}/sse/{session_id}"
    response = requests.get(sse_url, stream=True)
    client = sseclient.SSEClient(response)
    
    for event in client.events():
        if event.event == "connected":
            print(f"✅ SSE Connected: {event.data}")
        elif event.event == "progress":
            try:
                data = json.loads(event.data)
                progress = int(data['progress'] * 100)
                message = data['message']
                print(f"🔄 Progress: {progress}% - {message}")
            except json.JSONDecodeError:
                continue  # Skip malformed events

def test_streamable_http():
    print("🧪 Testing StreamableHTTP (HTTP + SSE)\n")
    
    # Step 1: Create session
    print("="*60)
    print("STEP 1: Create Session")
    print("="*60)
    
    response = requests.post(f"{SERVER_URL}/session")
    session_data = response.json()
    session_id = session_data["session_id"]
    
    print(f"✅ Session created: {session_id}")
    print(f"📡 SSE URL: {session_data['sse_url']}")
    
    # Step 2: Start SSE listener in background thread
    print("\n" + "="*60)
    print("STEP 2: Connect to SSE Stream")
    print("="*60)
    
    sse_thread = threading.Thread(target=listen_to_sse, args=(session_id,), daemon=True)
    sse_thread.start()
    
    # Give SSE time to connect
    time.sleep(2)
    
    # Step 3: Call tool via HTTP (with progress via SSE)
    print("\n" + "="*60)
    print("STEP 3: Call Tool (Progress via SSE)")
    print("="*60)
    
    payload = {
        "jsonrpc": "2.0",
        "id": "test-sse-123",
        "method": "tools/call",
        "params": {
            "name": "jira_search_issues",
            "arguments": {
                "jql": "project = SCRUM",
                "max_results": 7,
                "response_format": "concise"
            }
        }
    }
    
    print(f"Calling jira_search_issues...")
    print("(Watch for progress updates above via SSE)\n")
    
    response = requests.post(f"{SERVER_URL}/mcp/{session_id}", json=payload)
    result = response.json()
    
    print(f"\n✅ Tool execution completed!")
    print(f"Response ID: {result.get('id')}")
    print(f"Result preview: {str(result.get('result', {}))[:150]}...")
    
    # Wait a bit to see all SSE messages
    time.sleep(1)
    
    print("\n" + "="*60)
    print("✅ StreamableHTTP Test Complete!")
    print("="*60)
    print("\nYou should have seen:")
    print("  1. Session created")
    print("  2. SSE connection established")
    print("  3. Progress updates in real-time (0%, 30%, 60%, 80%, 100%)")
    print("  4. Final HTTP response with results")

if __name__ == "__main__":
    # Install sseclient-py first
    try:
        import sseclient
    except ImportError:
        print("Installing sseclient-py...")
        import subprocess
        subprocess.check_call(["pip", "install", "sseclient-py"])
        import sseclient
    
    test_streamable_http()
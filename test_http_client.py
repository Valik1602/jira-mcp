"""
Test HTTP MCP Client
"""
import requests
import json

SERVER_URL = "http://localhost:8000"

def test_health_check():
    """Test 1: Health check"""
    print("="*60)
    print("TEST 1: Health Check")
    print("="*60)
    
    response = requests.get(f"{SERVER_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_list_tools():
    """Test 2: List available tools"""
    print("\n" + "="*60)
    print("TEST 2: List Tools")
    print("="*60)
    
    response = requests.get(f"{SERVER_URL}/tools")
    tools = response.json()["tools"]
    print(f"Found {len(tools)} tools:")
    for tool in tools[:3]:  # Show first 3
        print(f"  - {tool['name']}")

def test_call_tool():
    """Test 3: Call jira_search_issues via HTTP"""
    print("\n" + "="*60)
    print("TEST 3: Call Tool via HTTP (JSON-RPC)")
    print("="*60)
    
    # JSON-RPC 2.0 request
    payload = {
        "jsonrpc": "2.0",
        "id": "test-123",
        "method": "tools/call",
        "params": {
            "name": "jira_search_issues",
            "arguments": {
                "jql": "project = SCRUM",
                "max_results": 5,
                "response_format": "concise"
            }
        }
    }
    
    print(f"Request: {json.dumps(payload, indent=2)}")
    
    response = requests.post(f"{SERVER_URL}/mcp", json=payload)
    
    print(f"\nStatus: {response.status_code}")
    result = response.json()
    print(f"Response ID: {result.get('id')}")
    print(f"Result preview: {str(result.get('result', {}))[:200]}...")

if __name__ == "__main__":
    print("🧪 Testing HTTP MCP Transport\n")
    
    test_health_check()
    test_list_tools()
    test_call_tool()
    
    print("\n" + "="*60)
    print("✅ All HTTP tests completed!")
    print("="*60)
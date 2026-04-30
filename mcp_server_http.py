"""
MCP Server with HTTP Transport
Production-ready stateless server
"""
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import uvicorn

# Import existing tools
from mcp_server import (
    jira_search_issues,
    jira_create_issue,
    jira_update_status,
    jira_add_comment,
    jira_assign_issue,
    jira_add_issues_to_sprint,
    jira_analyze_issues_with_ai,
    jira_read_export_file
)

load_dotenv()

# Create FastAPI app
app = FastAPI(title="Jira MCP Server (HTTP)")

# Available tools registry
TOOLS = {
    "jira_search_issues": jira_search_issues,
    "jira_create_issue": jira_create_issue,
    "jira_update_status": jira_update_status,
    "jira_add_comment": jira_add_comment,
    "jira_assign_issue": jira_assign_issue,
    "jira_add_issues_to_sprint": jira_add_issues_to_sprint,
    "jira_analyze_issues_with_ai": jira_analyze_issues_with_ai,
    "jira_read_export_file": jira_read_export_file
}

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Jira MCP Server",
        "transport": "HTTP",
        "status": "online",
        "tools_available": len(TOOLS)
    }

@app.get("/tools")
async def list_tools():
    """List available MCP tools"""
    return {
        "tools": [
            {
                "name": name,
                "description": tool.__doc__ or "No description"
            }
            for name, tool in TOOLS.items()
        ]
    }

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """
    Main MCP endpoint - handles tool calls via HTTP
    
    Request format (JSON-RPC 2.0):
    {
        "jsonrpc": "2.0",
        "id": "123",
        "method": "tools/call",
        "params": {
            "name": "jira_search_issues",
            "arguments": {
                "jql": "project = SCRUM",
                "max_results": 10
            }
        }
    }
    """
    try:
        body = await request.json()
        
        # Validate JSON-RPC format
        if body.get("jsonrpc") != "2.0":
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request - must be JSON-RPC 2.0"
                    }
                }
            )
        
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        # Handle tools/call method
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name not in TOOLS:
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Tool not found: {tool_name}",
                            "data": {"available_tools": list(TOOLS.keys())}
                        }
                    }
                )
            
            # Call the tool
            tool_func = TOOLS[tool_name]
            
            # Check if tool is async
            import inspect
            if inspect.iscoroutinefunction(tool_func):
                result = await tool_func(**arguments)
            else:
                result = tool_func(**arguments)
            
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                            }
                        ]
                    }
                }
            )
        
        else:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                        "data": {"supported_methods": ["tools/call"]}
                    }
                }
            )
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": body.get("id") if 'body' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
        )

if __name__ == "__main__":
    print("🚀 Starting Jira MCP Server (HTTP Transport)")
    print("📍 Server will be available at: http://localhost:8000")
    print("📋 Tools endpoint: http://localhost:8000/tools")
    print("🔌 MCP endpoint: http://localhost:8000/mcp")
    print("\nPress Ctrl+C to stop\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
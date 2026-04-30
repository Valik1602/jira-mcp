"""
MCP Server with StreamableHTTP (HTTP + SSE)
Bidirectional communication: Client→Server (HTTP) + Server→Client (SSE)
"""
import json
import os
import asyncio
import uuid
from typing import Dict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
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

app = FastAPI(title="Jira MCP Server (StreamableHTTP)")

# Session management: stores SSE queues for each client
sessions: Dict[str, asyncio.Queue] = {}

# Available tools
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

class SSEContext:
    """Context object that supports progress reporting via SSE"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.roots = [r"C:\Users\ValentynZelinskyi\Desktop\jira-exports"]
    
    async def report_progress(self, progress: float, message: str):
        if self.session_id in sessions:
         event_data = {
            "event": "progress",
            "data": json.dumps({
                "progress": progress,
                "message": message
            })
        }
        await sessions[self.session_id].put(event_data)
        # Small delay to ensure event is sent
        await asyncio.sleep(0.1)

@app.get("/")
async def root():
    """Health check"""
    return {
        "service": "Jira MCP Server",
        "transport": "StreamableHTTP (HTTP + SSE)",
        "status": "online",
        "active_sessions": len(sessions)
    }

@app.post("/session")
async def create_session():
    """Create a new SSE session"""
    session_id = str(uuid.uuid4())
    sessions[session_id] = asyncio.Queue()
    
    return {
        "session_id": session_id,
        "sse_url": f"/sse/{session_id}"
    }

@app.get("/sse/{session_id}")
async def sse_stream(session_id: str):
    """
    SSE endpoint - Server pushes messages to Client
    
    Client connects here and listens for:
    - Progress updates
    - Notifications
    - Sampling requests
    """
    if session_id not in sessions:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found"}
        )
    
    async def event_generator():
        """Generate SSE events from queue"""
        queue = sessions[session_id]
        
        try:
            # Send initial connection message
            yield {
                "event": "connected",
                "data": f"Session {session_id} connected"
            }
            
            while True:
                # Wait for messages from server
                message = await queue.get()
                
                if message.get("event") == "close":
                    break
                
                yield message
        
        finally:
            # Cleanup session
            if session_id in sessions:
                del sessions[session_id]
    
    return EventSourceResponse(event_generator())

@app.post("/mcp/{session_id}")
async def handle_mcp_request(session_id: str, request: Request):
    """
    Main MCP endpoint with session support
    
    Request format (JSON-RPC 2.0):
    {
        "jsonrpc": "2.0",
        "id": "123",
        "method": "tools/call",
        "params": {
            "name": "jira_search_issues",
            "arguments": {"jql": "project = SCRUM"}
        }
    }
    """
    if session_id not in sessions:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found. Create session first via POST /session"}
        )
    
    try:
        body = await request.json()
        
        # Validate JSON-RPC
        if body.get("jsonrpc") != "2.0":
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request"
                    }
                }
            )
        
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
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
                            "message": f"Tool not found: {tool_name}"
                        }
                    }
                )
            
            # Create SSE context for progress reporting
            ctx = SSEContext(session_id)
            
            # Call tool with context
            tool_func = TOOLS[tool_name]
            
            import inspect
            if inspect.iscoroutinefunction(tool_func):
                # Pass context if tool accepts it
                sig = inspect.signature(tool_func)
                if 'ctx' in sig.parameters:
                    result = await tool_func(**arguments, ctx=ctx)
                else:
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
                        "message": f"Method not found: {method}"
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
    print("🚀 Starting Jira MCP Server (StreamableHTTP)")
    print("📍 Server: http://localhost:8001")
    print("🔌 Create session: POST http://localhost:8001/session")
    print("📡 SSE stream: GET http://localhost:8001/sse/{session_id}")
    print("🔧 MCP endpoint: POST http://localhost:8001/mcp/{session_id}")
    print("\nPress Ctrl+C to stop\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
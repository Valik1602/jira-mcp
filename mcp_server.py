import os
import requests
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from dotenv import load_dotenv
import base64
from typing import Literal

load_dotenv()

# Конфигурация
JIRA_URL = os.getenv("JIRA_URL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")

# Создаём MCP сервер
mcp = FastMCP("Jira MCP Server")

def get_headers():
    """Generate authentication headers for Jira API"""
    auth_string = f"{JIRA_EMAIL}:{JIRA_TOKEN}"
    auth_bytes = base64.b64encode(auth_string.encode()).decode()
    return {
        "Authorization": f"Basic {auth_bytes}",
        "Content-Type": "application/json"
    }

@mcp.tool(
    name="jira_search_issues",
    description="""Search for Jira issues using JQL (Jira Query Language). Returns COMPLETE issue details by default.
    
    This is the PRIMARY tool for retrieving issue information. Use it for:
    - Finding all issues in a project or sprint
    - Getting issues by status, assignee, priority, or type
    - Analyzing sprint or project health
    - Finding unassigned or blocked issues
    
    By default, returns DETAILED information (summary, status, assignee, priority, dates, reporter).
    This eliminates the need for follow-up calls to get individual issue details.
    
    Common JQL examples:
    - All project issues: jql="project = TEST"
    - Issues in progress: jql="project = TEST AND status = 'In Progress'"
    - Unassigned issues: jql="project = TEST AND assignee is EMPTY"
    - High priority bugs: jql="project = TEST AND type = Bug AND priority = High"
    - My issues: jql="project = TEST AND assignee = currentUser()"
    
    IMPORTANT: Always start with a project filter (e.g., "project = TEST"), then add conditions."""
)
def jira_search_issues(
    jql: str = Field(description="JQL query string (e.g., 'project = TEST AND status = \"In Progress\"')"),
    max_results: int = Field(
        default=50,
        description="Maximum number of results to return (1-100). Default 50."
    ),
    response_format: Literal["detailed", "concise"] = Field(
        default="detailed",
        description="'detailed' (DEFAULT) returns full metadata including priority, dates, reporter, and account IDs. 'concise' returns only summary fields. Use detailed unless you need a quick overview."
    )
):
    """Search issues using JQL with detailed information by default"""
    
    if max_results < 1 or max_results > 100:
        return "❌ max_results must be between 1 and 100. Tip: Use 20-50 for typical searches."
    
    url = f"{JIRA_URL}/rest/api/3/search/jql"
    params = {
        "jql": jql,
        "maxResults": max_results,
        "fields": "summary,status,assignee,issuetype,priority,created,updated,reporter,description"
    }
    
    try:
        response = requests.get(url, params=params, headers=get_headers(), timeout=15)
        
        if response.status_code == 400:
            error_msg = response.json().get("errorMessages", ["Invalid JQL"])[0]
            return f"""❌ Invalid JQL syntax: {error_msg}

Common JQL syntax tips:
- Use quotes for values with spaces: status = "In Progress"
- Project key is case-sensitive: project = TEST (not test)
- Use AND/OR for multiple conditions: project = TEST AND status = Done
- Check field names: assignee (not assigned_to), issuetype (not type)

Example valid JQL: project = TEST AND status = "In Progress" """
        
        if response.status_code != 200:
            return f"❌ Search failed: HTTP {response.status_code}"
        
        data = response.json()
        issues = data.get("issues", [])
        
        # Новый API не возвращает total, считаем из issues
        total = len(issues)
        if not data.get("isLast", True):
            total_str = f"{total}+ (more available)"
        else:
            total_str = str(total)
        
        if total == 0:
            return f"✅ No issues found matching: {jql}\n\nTip: Try broadening your search criteria."
        
        # Format results based on response_format
        results = []
        
        for issue in issues:
            fields = issue["fields"]
            
            if response_format == "detailed":
                # Full details including IDs for follow-up actions
                results.append({
                    "key": issue["key"],
                    "id": issue["id"],
                    "summary": fields["summary"],
                    "description": fields.get("description", "No description"),
                    "status": fields["status"]["name"],
                    "assignee": {
                        "name": fields["assignee"]["displayName"] if fields.get("assignee") else "Unassigned",
                        "accountId": fields["assignee"]["accountId"] if fields.get("assignee") else None
                    },
                    "type": fields["issuetype"]["name"],
                    "priority": fields.get("priority", {}).get("name", "None"),
                    "created": fields["created"],
                    "updated": fields["updated"],
                    "reporter": fields["reporter"]["displayName"] if fields.get("reporter") else "Unknown"
                })
            else:  # concise
                # Summary only
                results.append({
                    "key": issue["key"],
                    "summary": fields["summary"],
                    "status": fields["status"]["name"],
                    "assignee": fields["assignee"]["displayName"] if fields.get("assignee") else "Unassigned",
                    "type": fields["issuetype"]["name"]
                })
        
        # Add helpful summary
        summary = f"✅ Found {len(results)} matching issues"
        if not data.get("isLast", True):
            summary += " (more results available - increase max_results to see more)"
        
        return {
            "summary": summary,
            "jql": jql,
            "total_found": total_str,
            "returned": len(results),
            "issues": results
        }
    
    except requests.exceptions.Timeout:
        return "❌ Search timed out. Try:\n- Reducing max_results\n- Adding more specific filters to JQL\n- Checking Jira server status"
    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"


@mcp.tool(
    name="jira_create_issue",
    description="""Create a new issue in a Jira project.
    
    Use this when you need to:
    - Create a new task, bug, story, or epic
    - Add work items to a sprint or backlog
    - Track new feature requests or issues
    
    Required: project_key (e.g., TEST) and summary (issue title)
    Optional: issue_type (defaults to Task), description
    
    Example: Create a bug with project_key="TEST", summary="Login button broken", issue_type="Bug"
    
    Returns the newly created issue key (e.g., TEST-42)"""
)
def jira_create_issue(
    project_key: str = Field(description="Project key where issue will be created (e.g., TEST, PROJ)"),
    summary: str = Field(description="Brief title/summary of the issue (e.g., 'Fix login bug')"),
    issue_type: Literal["Task", "Bug", "Story", "Epic"] = Field(
        default="Task",
        description="Type of issue to create. Use 'Task' for general work, 'Bug' for defects, 'Story' for user stories, 'Epic' for large initiatives."
    ),
    description: str = Field(default="", description="Detailed description of the issue (optional)")
):
    """Create a new Jira issue"""
    url = f"{JIRA_URL}/rest/api/3/issue"
    
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description or "No description provided"}]
                    }
                ]
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        
        if response.status_code == 400:
            error_detail = response.json().get("errors", {})
            return f"❌ Invalid request. Common issues:\n- Project '{project_key}' doesn't exist\n- Issue type '{issue_type}' not valid for this project\nDetails: {error_detail}"
        
        if response.status_code == 201:
            data = response.json()
            return f"✅ Successfully created issue: {data['key']}"
        else:
            return f"❌ Failed to create issue: HTTP {response.status_code}"
    
    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"


@mcp.tool(
    name="jira_update_status",
    description="""Transition a Jira issue to a new status (e.g., move from 'To Do' to 'In Progress').
    
    Use this when you need to:
    - Start work on an issue (To Do → In Progress)
    - Complete an issue (In Progress → Done)
    - Move issues through your workflow
    
    The tool automatically finds available transitions for the issue and applies the requested one.
    If the status isn't available, you'll get a list of valid options.
    
    Example: Move TEST-7 to 'In Progress' with issue_key="TEST-7", new_status="In Progress"
    
    Common statuses: To Do, In Progress, Done, Blocked, In Review"""
)
def jira_update_status(
    issue_key: str = Field(description="Issue key to update (e.g., TEST-7)"),
    new_status: str = Field(description="Target status name (e.g., 'In Progress', 'Done'). Status names are case-insensitive.")
):
    """Change issue status by finding and applying the correct workflow transition"""
    
    # Get available transitions
    transitions_url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions"
    
    try:
        response = requests.get(transitions_url, headers=get_headers(), timeout=10)
        
        if response.status_code == 404:
            return f"❌ Issue '{issue_key}' not found. Verify the issue key is correct."
        
        if response.status_code != 200:
            return f"❌ Could not get transitions: HTTP {response.status_code}"
        
        transitions = response.json()["transitions"]
        
        # Find matching transition
        transition_id = None
        for t in transitions:
            if t["name"].lower() == new_status.lower():
                transition_id = t["id"]
                break
        
        if not transition_id:
            available = [t["name"] for t in transitions]
            return f"❌ Status '{new_status}' is not a valid transition from current state.\n\n✅ Available transitions: {', '.join(available)}\n\nTip: Use one of the available transitions listed above."
        
        # Apply transition
        payload = {"transition": {"id": transition_id}}
        response = requests.post(transitions_url, json=payload, headers=get_headers(), timeout=10)
        
        if response.status_code == 204:
            return f"✅ Successfully changed status to: {new_status}"
        else:
            return f"❌ Failed to update status: HTTP {response.status_code}"
    
    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"


@mcp.tool(
    name="jira_add_comment",
    description="""Add a comment to an existing Jira issue.
    
    Use this when you need to:
    - Provide updates on issue progress
    - Ask questions or clarify requirements
    - Document decisions or solutions
    - Communicate with team members
    
    Example: Add progress update to TEST-7 with issue_key="TEST-7", comment_text="Fixed the authentication bug"
    
    Comments are visible to all team members with access to the issue."""
)
def jira_add_comment(
    issue_key: str = Field(description="Issue key to comment on (e.g., TEST-7)"),
    comment_text: str = Field(description="The comment text to add")
):
    """Add a comment to a Jira issue"""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"
    
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": comment_text}]
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        
        if response.status_code == 404:
            return f"❌ Issue '{issue_key}' not found."
        
        if response.status_code == 201:
            return f"✅ Comment added successfully to {issue_key}"
        else:
            return f"❌ Failed to add comment: HTTP {response.status_code}"
    
    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"


@mcp.tool(
    name="jira_assign_issue",
    description="""Assign a Jira issue to a team member.
    
    Use this when you need to:
    - Assign work to a specific person
    - Reassign issues when workload changes
    - Take ownership of an issue
    
    Important: Use the person's Jira account ID (not email). 
    You can get account IDs from jira_search_issues results (they're included in the 'detailed' format).
    
    Example: Assign to user with assignee_account_id="5d5f6f7e8e9d4c0d0e8f7e6d"
    
    To unassign an issue, use assignee_account_id="null" """
)
def jira_assign_issue(
    issue_key: str = Field(description="Issue key to assign (e.g., TEST-7)"),
    assignee_account_id: str = Field(description="Jira account ID of the assignee. Use 'null' to unassign.")
):
    """Assign issue to a user by account ID"""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/assignee"
    
    payload = {
        "accountId": None if assignee_account_id == "null" else assignee_account_id
    }
    
    try:
        response = requests.put(url, json=payload, headers=get_headers(), timeout=10)
        
        if response.status_code == 404:
            return f"❌ Issue '{issue_key}' not found."
        
        if response.status_code == 400:
            return f"❌ Invalid account ID. Tip: Get valid account IDs from jira_search_issues with response_format='detailed'"
        
        if response.status_code == 204:
            action = "Unassigned" if assignee_account_id == "null" else f"Assigned to account {assignee_account_id}"
            return f"✅ {action} successfully"
        else:
            return f"❌ Failed to assign: HTTP {response.status_code}"
    
    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"
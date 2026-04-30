import os
import requests
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from dotenv import load_dotenv
import base64
from typing import Literal, Optional

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
    - All project issues: jql="project = SCRUM"
    - Issues in progress: jql="project = SCRUM AND status = 'In Progress'"
    - Unassigned issues: jql="project = SCRUM AND assignee is EMPTY"
    - High priority bugs: jql="project = SCRUM AND type = Bug AND priority = High"
    - My issues: jql="project = SCRUM AND assignee = currentUser()"
    
    IMPORTANT: Always start with a project filter (e.g., "project = SCRUM"), then add conditions."""
)
async def jira_search_issues(
    jql: str = Field(description="JQL query string (e.g., 'project = SCRUM AND status = \"In Progress\"')"),
    max_results: int = Field(
        default=50,
        description="Maximum number of results to return (1-100). Default 50."
    ),
    response_format: Literal["detailed", "concise"] = Field(
        default="detailed",
        description="'detailed' (DEFAULT) returns full metadata including priority, dates, reporter, and account IDs. 'concise' returns only summary fields. Use detailed unless you need a quick overview."
    ),
    ctx: Optional[object] = None
):
    """Search issues using JQL with progress reporting"""
    
    # Report progress: Starting
    if ctx:
        await ctx.report_progress(0.0, "Starting search...")
    
    if max_results < 1 or max_results > 100:
        return "❌ max_results must be between 1 and 100. Tip: Use 20-50 for typical searches."
    
    url = f"{JIRA_URL}/rest/api/3/search/jql"
    params = {
        "jql": jql,
        "maxResults": max_results,
        "fields": "summary,status,assignee,issuetype,priority,created,updated,reporter,description"
    }
    
    # Report progress: Executing query
    if ctx:
        await ctx.report_progress(0.3, "Executing JQL query...")
    
    try:
        response = requests.get(url, params=params, headers=get_headers(), timeout=15)
        
        if response.status_code == 400:
            error_msg = response.json().get("errorMessages", ["Invalid JQL"])[0]
            return f"""❌ Invalid JQL syntax: {error_msg}

Common JQL syntax tips:
- Use quotes for values with spaces: status = "In Progress"
- Project key is case-sensitive: project = SCRUM (not scrum)
- Use AND/OR for multiple conditions: project = SCRUM AND status = Done
- Check field names: assignee (not assigned_to), issuetype (not type)

Example valid JQL: project = SCRUM AND status = "In Progress" """
        
        if response.status_code != 200:
            return f"❌ Search failed: HTTP {response.status_code}"
        
        # Report progress: Processing results
        if ctx:
            await ctx.report_progress(0.6, "Processing results...")
        
        data = response.json()
        issues = data.get("issues", [])
        
        # Новый API не возвращает total, считаем из issues
        total = len(issues)
        if not data.get("isLast", True):
            total_str = f"{total}+ (more available)"
        else:
            total_str = str(total)
        
        if total == 0:
            if ctx:
                await ctx.report_progress(1.0, "No issues found")
            return f"✅ No issues found matching: {jql}\n\nTip: Try broadening your search criteria."
        
        # Report progress: Formatting
        if ctx:
            await ctx.report_progress(0.8, f"Formatting {len(issues)} issues...")
        
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
                    "priority": fields["priority"]["name"] if fields.get("priority") else "None",
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
        
        # Report progress: Complete
        if ctx:
            await ctx.report_progress(1.0, f"Found {len(issues)} issues!")
        
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
    
    Required: project_key (e.g., SCRUM) and summary (issue title)
    Optional: issue_type (defaults to Task), description
    
    Example: Create a bug with project_key="SCRUM", summary="Login button broken", issue_type="Bug"
    
    Returns the newly created issue key (e.g., SCRUM-42)"""
)
def jira_create_issue(
    project_key: str = Field(description="Project key where issue will be created (e.g., SCRUM, PROJ)"),
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
    
    Example: Move SCRUM-7 to 'In Progress' with issue_key="SCRUM-7", new_status="In Progress"
    
    Common statuses: To Do, In Progress, Done, Blocked, In Review"""
)
def jira_update_status(
    issue_key: str = Field(description="Issue key to update (e.g., SCRUM-7)"),
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
    
    Example: Add progress update to SCRUM-7 with issue_key="SCRUM-7", comment_text="Fixed the authentication bug"
    
    Comments are visible to all team members with access to the issue."""
)
def jira_add_comment(
    issue_key: str = Field(description="Issue key to comment on (e.g., SCRUM-7)"),
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
    issue_key: str = Field(description="Issue key to assign (e.g., SCRUM-7)"),
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
    
@mcp.tool(
    name="jira_add_issues_to_sprint",
    description="""Add one or multiple issues to an active sprint.
    
    Use this when you need to:
    - Move issues from backlog to current sprint
    - Add newly created issues to sprint
    - Reorganize sprint scope
    
    You can add issues by providing:
    - Single issue key (e.g., "SCRUM-5")
    - Multiple issue keys separated by commas (e.g., "SCRUM-5,SCRUM-6,SCRUM-7")
    - Or a list of issue keys from jira_search_issues results
    
    Example: Add backlog items to sprint with sprint_id=1, issue_keys="SCRUM-10,SCRUM-11,SCRUM-12"
    
    Returns confirmation of which issues were added successfully."""
)
def jira_add_issues_to_sprint(
    sprint_id: int = Field(description="Sprint ID to add issues to (numeric ID, not sprint name)"),
    issue_keys: str = Field(description="Comma-separated list of issue keys to add (e.g., 'SCRUM-1,SCRUM-2,SCRUM-3')")
):
    """Add multiple issues to a sprint"""
    
    # Parse issue keys
    keys = [k.strip() for k in issue_keys.split(",") if k.strip()]
    
    if not keys:
        return "❌ No valid issue keys provided. Use comma-separated format like: SCRUM-1,SCRUM-2,SCRUM-3"
    
    url = f"{JIRA_URL}/rest/agile/1.0/sprint/{sprint_id}/issue"
    payload = {"issues": keys}
    
    try:
        response = requests.post(url, json=payload, headers=get_headers(), timeout=15)
        
        if response.status_code == 404:
            return f"❌ Sprint {sprint_id} not found. Verify the sprint ID is correct.\n\nTip: You can find sprint IDs using Jira board or API."
        
        if response.status_code == 400:
            error_detail = response.json()
            return f"❌ Invalid request. Common issues:\n- One or more issue keys don't exist\n- Issues already in another sprint\n- Sprint is closed\nDetails: {error_detail}"
        
        if response.status_code == 204:
            return f"✅ Successfully added {len(keys)} issue(s) to sprint {sprint_id}:\n{', '.join(keys)}"
        else:
            return f"❌ Failed to add issues: HTTP {response.status_code}\nResponse: {response.text[:200]}"
    
    except requests.exceptions.Timeout:
        return "❌ Request timed out. Sprint might have too many issues or server is slow."
    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {str(e)}"
    
@mcp.tool(
    name="jira_analyze_issues_with_ai",
    description="""Analyze Jira issues using AI to extract insights, patterns, and recommendations.
    
    Use this when you need to:
    - Summarize a large number of issues
    - Find patterns in issue descriptions
    - Get AI-powered insights about project health
    - Identify common problems or themes
    
    This tool fetches issues via JQL and uses AI (Claude) to analyze them.
    
    Example: Analyze all bugs with jql="project = SCRUM AND type = Bug"
    
    Returns an AI-generated summary with insights and recommendations."""
)
async def jira_analyze_issues_with_ai(
    jql: str = Field(description="JQL query to find issues to analyze"),
    max_results: int = Field(default=20, description="Maximum issues to analyze (1-50)"),
    ctx: Optional[object] = None
):
    """Use AI sampling to analyze Jira issues"""
    
    if ctx is None:
        return "❌ This tool requires MCP context with sampling capability"
    
    # Step 1: Fetch issues
    if hasattr(ctx, 'report_progress'):
        await ctx.report_progress(0.0, "Fetching issues from Jira...")
    
    # Reuse existing search
    search_result = await jira_search_issues(
        jql=jql,
        max_results=min(max_results, 50),
        response_format="detailed",
        ctx=None  # Don't report progress here
    )
    
    if isinstance(search_result, str) and search_result.startswith("❌"):
        return search_result
    
    issues = search_result.get("issues", [])
    
    if not issues:
        return "No issues found to analyze"
    
    # Step 2: Prepare data for AI
    if hasattr(ctx, 'report_progress'):
        await ctx.report_progress(0.3, f"Preparing {len(issues)} issues for AI analysis...")
    
    issues_text = f"Found {len(issues)} issues matching '{jql}':\n\n"
    for issue in issues:
        issues_text += f"- {issue['key']}: {issue['summary']}\n"
        issues_text += f"  Status: {issue['status']}, Type: {issue['type']}, Priority: {issue['priority']}\n"
        issues_text += f"  Assignee: {issue['assignee']['name']}\n"
        if issue.get('description'):
            desc = issue['description'][:200]  # First 200 chars
            issues_text += f"  Description: {desc}...\n"
        issues_text += "\n"
    
    # Step 3: Request AI analysis via sampling
    if hasattr(ctx, 'report_progress'):
        await ctx.report_progress(0.5, "Requesting AI analysis...")
    
    try:
        # Use sampling to ask Claude to analyze
        sample_request = {
            "messages": [
                {
                    "role": "user",
                    "content": f"""Analyze these Jira issues and provide:

1. **Summary**: Brief overview of what these issues represent
2. **Patterns**: Common themes or patterns you notice
3. **Insights**: Key observations about project health
4. **Recommendations**: 2-3 actionable recommendations

Issues:
{issues_text}

Provide a concise, actionable analysis."""
                }
            ],
            "maxTokens": 1000
        }
        
        if hasattr(ctx, 'report_progress'):
            await ctx.report_progress(0.7, "AI is analyzing...")
        
        # Call sampling
        if not hasattr(ctx, 'sample'):
            return "❌ Sampling not available in this MCP client"
        
        sample_result = await ctx.sample(sample_request)
        
        if hasattr(ctx, 'report_progress'):
            await ctx.report_progress(1.0, "Analysis complete!")
        
        # Extract AI response
        ai_response = sample_result.get("content", [{}])[0].get("text", "No response")
        
        return f"""# AI Analysis of {len(issues)} Issues

**Query:** {jql}

{ai_response}

---
*Analysis powered by Claude via MCP Sampling*
"""
    
    except Exception as e:
        return f"❌ AI analysis failed: {str(e)}\n\nNote: Sampling requires MCP client support and Claude API access."
    
@mcp.tool(
    name="jira_read_export_file",
    description="""Read contents of exported Jira reports or data files.
    
    Use this when you need to:
    - Read previously exported sprint reports
    - Access saved Jira data exports
    - Load configuration or template files
    
    Security: Only files in allowed directories (roots) can be accessed.
    
    Example: Read sprint report with file_path="sprint-report.txt"
    
    Returns the file contents as text."""
)
async def jira_read_export_file(
    file_path: str = Field(description="Relative path to file (e.g., 'sprint-report.txt' or 'reports/q1-summary.csv')"),
    ctx: Optional[object] = None
):
    """Read file from allowed roots with security boundaries"""
    
    import os
    
    # Check if roots are available from context
    if ctx and hasattr(ctx, 'roots'):
        allowed_roots = ctx.roots
    else:
        # Default fallback root (for testing)
        allowed_roots = [r"C:\Users\ValentynZelinskyi\Desktop\jira-exports"]
    
    if not allowed_roots:
        return "❌ No file access roots configured. Client must specify allowed directories."
    
    # Try to find file in allowed roots
    file_found = None
    for root in allowed_roots:
        potential_path = os.path.join(root, file_path)
        
        # Security check: ensure resolved path is still within root
        real_root = os.path.realpath(root)
        real_path = os.path.realpath(potential_path)
        
        if not real_path.startswith(real_root):
            continue  # Path escape attempt - skip
        
        if os.path.exists(real_path) and os.path.isfile(real_path):
            file_found = real_path
            break
    
    if not file_found:
        return f"""❌ File not found: {file_path}

Searched in allowed roots:
{chr(10).join(f'  - {root}' for root in allowed_roots)}

Security note: Only files within configured roots can be accessed."""
    
    # Read file
    try:
        with open(file_found, 'r', encoding='utf-8') as f:
            content = f.read()
        
        file_size = len(content)
        
        return f"""✅ File: {file_path}
📂 Location: {file_found}
📊 Size: {file_size} characters

--- CONTENT ---
{content}
--- END ---"""
    
    except UnicodeDecodeError:
        return f"❌ File is not text format (binary file): {file_path}"
    except PermissionError:
        return f"❌ Permission denied: {file_path}"
    except Exception as e:
        return f"❌ Error reading file: {str(e)}"
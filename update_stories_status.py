import os, requests, base64
from dotenv import load_dotenv
load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")

auth_string = f"{JIRA_EMAIL}:{JIRA_TOKEN}"
auth_bytes = base64.b64encode(auth_string.encode()).decode()
headers = {
    "Authorization": f"Basic {auth_bytes}",
    "Content-Type": "application/json"
}

def get_all_stories():
    stories = []
    next_page_token = None
    while True:
        params = {
            "jql": "project = TEST AND issuetype = Story",
            "maxResults": 50,
            "fields": "summary,status"
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token
        response = requests.get(f"{JIRA_URL}/rest/api/3/search/jql", headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error fetching stories: {response.status_code} - {response.text}")
            break
        data = response.json()
        issues = data.get("issues", [])
        # Fetch full details for each issue since new API returns minimal data
        for issue in issues:
            detail = requests.get(f"{JIRA_URL}/rest/api/3/issue/{issue['id']}?fields=summary,status", headers=headers)
            if detail.status_code == 200:
                stories.append(detail.json())
        if data.get("isLast", True):
            break
        next_page_token = data.get("nextPageToken")
    return stories

def get_transition_id(issue_key, target_status):
    response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions", headers=headers)
    if response.status_code != 200:
        return None, f"Error getting transitions: {response.text}"
    transitions = response.json()["transitions"]
    for t in transitions:
        if t["name"].lower() == target_status.lower():
            return t["id"], None
    available = [t["name"] for t in transitions]
    return None, f"Status not found. Available: {available}"

def transition_issue(issue_key, transition_id):
    response = requests.post(
        f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions",
        json={"transition": {"id": transition_id}},
        headers=headers
    )
    return response.status_code == 204

stories = get_all_stories()
print(f"Found {len(stories)} stories in TEST project.\n")

success = 0
skipped = 0
failed = 0

for story in stories:
    key = story["key"]
    summary = story["fields"]["summary"]
    current_status = story["fields"]["status"]["name"]

    if current_status == "In Progress":
        print(f"  SKIP  {key} - already In Progress: {summary}")
        skipped += 1
        continue

    transition_id, error = get_transition_id(key, "In Progress")
    if not transition_id:
        print(f"  FAIL  {key} - {error}: {summary}")
        failed += 1
        continue

    if transition_issue(key, transition_id):
        print(f"  OK    {key} - '{current_status}' -> 'In Progress': {summary}")
        success += 1
    else:
        print(f"  FAIL  {key} - transition failed: {summary}")
        failed += 1

print(f"\nDone. Updated: {success} | Skipped (already In Progress): {skipped} | Failed: {failed}")

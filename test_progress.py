"""
Quick test for Progress Notifications
"""
import asyncio
from mcp_server import jira_search_issues

class MockContext:
    """Mock context object to capture progress reports"""
    def __init__(self):
        self.progress_reports = []
    
    async def report_progress(self, progress, message):
        self.progress_reports.append({
            "progress": progress,
            "message": message
        })
        print(f"🔄 Progress: {int(progress * 100)}% - {message}")

async def test_progress():
    print("Testing Progress Notifications...\n")
    
    ctx = MockContext()
    
    # Call search with context
    result = await jira_search_issues(
        jql="project = SCRUM",
        max_results=10,
        response_format="concise",
        ctx=ctx
    )
    
    print(f"\n✅ Search completed!")
    print(f"\nProgress reports captured: {len(ctx.progress_reports)}")
    for report in ctx.progress_reports:
        print(f"  {int(report['progress'] * 100)}%: {report['message']}")

if __name__ == "__main__":
    asyncio.run(test_progress())
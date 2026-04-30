"""
Test Sampling feature
"""
import asyncio

class MockSamplingContext:
    """Mock context with sampling support"""
    def __init__(self):
        self.progress_reports = []
        self.sample_called = False
    
    async def report_progress(self, progress, message):
        self.progress_reports.append({"progress": progress, "message": message})
        print(f"🔄 {int(progress * 100)}% - {message}")
    
    async def sample(self, request):
        """Mock sampling - simulate Claude response"""
        self.sample_called = True
        print(f"\n🤖 Sampling called!")
        print(f"   Messages: {len(request['messages'])}")
        print(f"   Max tokens: {request['maxTokens']}")
        
        # Simulate Claude's response
        return {
            "content": [{
                "text": """**Summary**: 7 issues in the SCRUM project, mostly unassigned tasks and tests.

**Patterns**: 
- All 7 issues are unassigned, indicating a resource allocation problem
- Mix of tasks (Test_1, Test_2, Test_4) and subtasks
- Issues are in "To Do" or "In Review" status

**Insights**:
- No ownership assigned to any work items
- Two issues (Task 2, Task 3) are in review but unassigned
- Testing-focused work items suggest QA phase

**Recommendations**:
1. Assign owners to all 7 issues immediately to prevent bottlenecks
2. Review why tasks are in "In Review" without assignees
3. Consider creating an assignment policy for new issues"""
            }]
        }

async def test_sampling():
    print("Testing Sampling feature...\n")
    
    # Import after server is defined
    from mcp_server import jira_analyze_issues_with_ai
    
    ctx = MockSamplingContext()
    
    result = await jira_analyze_issues_with_ai(
        jql="project = SCRUM",
        max_results=10,
        ctx=ctx
    )
    
    print(f"\n{'='*60}")
    print("RESULT:")
    print(f"{'='*60}")
    print(result)
    
    print(f"\n{'='*60}")
    print("SAMPLING VERIFICATION:")
    print(f"{'='*60}")
    print(f"✅ Sampling was called: {ctx.sample_called}")
    print(f"✅ Progress reports: {len(ctx.progress_reports)}")

if __name__ == "__main__":
    asyncio.run(test_sampling())
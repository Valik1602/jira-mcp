"""
Test Roots-based File Access
"""
import asyncio

class MockRootsContext:
    """Mock context with roots configuration"""
    def __init__(self, roots):
        self.roots = roots
    
    async def report_progress(self, progress, message):
        print(f"🔄 {int(progress * 100)}% - {message}")

async def test_file_access():
    print("Testing Roots-based File Access...\n")
    
    from mcp_server import jira_read_export_file
    
    # Test 1: Read allowed file
    print("="*60)
    print("TEST 1: Reading file from allowed root")
    print("="*60)
    
    ctx = MockRootsContext(roots=[r"C:\Users\ValentynZelinskyi\Desktop\jira-exports"])
    
    result = await jira_read_export_file(
        file_path="sprint-report.txt",
        ctx=ctx
    )
    
    print(result)
    
    # Test 2: Try to access file outside roots (security test)
    print(f"\n{'='*60}")
    print("TEST 2: Trying to access file OUTSIDE allowed root (security)")
    print("="*60)
    
    result2 = await jira_read_export_file(
        file_path="../../../Windows/System32/drivers/etc/hosts",  # Path traversal attempt
        ctx=ctx
    )
    
    print(result2)
    
    # Test 3: File not found
    print(f"\n{'='*60}")
    print("TEST 3: Non-existent file")
    print("="*60)
    
    result3 = await jira_read_export_file(
        file_path="missing-file.txt",
        ctx=ctx
    )
    
    print(result3)

if __name__ == "__main__":
    asyncio.run(test_file_access())
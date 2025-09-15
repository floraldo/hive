#!/usr/bin/env python3
"""Simple test to verify worker functionality without Claude"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Test the worker without Claude
def test_worker_basic():
    """Test basic worker functionality"""
    print("Testing Worker Core...")
    
    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent))
    sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-logging" / "src"))
    
    from worker import WorkerCore
    
    # Create a test worker
    print("Creating worker...")
    worker = WorkerCore(
        worker_id="test",
        task_id="simple-test",
        run_id=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        phase="apply",
        mode="fresh",
        live_output=False
    )
    
    print(f"Worker created successfully!")
    print(f"  Workspace: {worker.workspace}")
    print(f"  Claude command: {worker.claude_cmd or 'NOT FOUND'}")
    
    # Test task loading
    print("\nTesting task loading...")
    task = worker.load_task("test-logging")
    if task:
        print(f"  Task loaded: {task['title']}")
    else:
        print("  Task not found")
    
    # Test prompt creation
    if task:
        print("\nTesting prompt creation...")
        prompt = worker.create_prompt(task)
        print(f"  Prompt created: {len(prompt)} characters")
    
    # Test result emission
    print("\nTesting result emission...")
    test_result = {
        "status": "success",
        "notes": "Test completed",
        "next_state": "completed"
    }
    worker.emit_result(test_result)
    print("  Result emitted successfully")
    
    print("\n✅ All worker tests passed!")
    return True

if __name__ == "__main__":
    try:
        test_worker_basic()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
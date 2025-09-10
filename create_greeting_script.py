#!/usr/bin/env python3
"""
Simple test script to demonstrate cc_worker file creation verification.
Creates a greeting script and tests the worker's ability to detect newly created files.
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone

def create_greeting_script():
    """Create a simple greeting script to test file creation detection"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Creating greeting script...")
    
    # Create a simple Python greeting script
    greeting_content = '''#!/usr/bin/env python3
"""
Simple greeting script for testing cc_worker file creation detection.
"""

import sys
from datetime import datetime

def main():
    """Main greeting function"""
    if len(sys.argv) > 1:
        name = " ".join(sys.argv[1:])
    else:
        name = "World"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Hello, {name}! Created at {timestamp}")
    print("This script was generated to test cc_worker file creation detection.")

if __name__ == "__main__":
    main()
'''
    
    # Write the greeting script
    script_path = Path("hello_greeting.py")
    with open(script_path, "w") as f:
        f.write(greeting_content)
    
    # Make it executable (on Unix-like systems)
    if hasattr(os, 'chmod'):
        os.chmod(script_path, 0o755)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Created: {script_path}")
    
    # Test the script
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Testing the greeting script...")
    os.system(f"python {script_path} Hive Worker")
    
    # Create a task file to demonstrate the worker's task loading
    task_data = {
        "id": "hello_greeting_test",
        "title": "Create Greeting Script Test",
        "description": "Test script to verify cc_worker can detect file creation",
        "acceptance": [
            "Creates hello_greeting.py file",
            "Script runs without errors",
            "File appears in created_files list"
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "create_greeting_script.py"
    }
    
    tasks_dir = Path("hive/tasks")
    tasks_dir.mkdir(parents=True, exist_ok=True)
    
    task_file = tasks_dir / "hello_greeting_test.json"
    with open(task_file, "w") as f:
        json.dump(task_data, f, indent=2)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Created task file: {task_file}")
    
    print(f"\n[SUCCESS] Test setup complete!")
    print(f"- Greeting script: {script_path}")
    print(f"- Task definition: {task_file}")
    print(f"\nTo test with cc_worker, run:")
    print(f"python cc_worker.py backend --one-shot --task-id hello_greeting_test")

if __name__ == "__main__":
    create_greeting_script()
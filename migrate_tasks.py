#!/usr/bin/env python3
"""
Migrate from single tasks.json to per-task file structure
One-time migration script to convert existing task data
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

def migrate_tasks():
    """Migrate from tasks.json to per-task files"""
    root = Path.cwd()
    hive_dir = root / "hive"
    
    # Old structure
    old_tasks_file = hive_dir / "bus" / "tasks.json"
    
    # New structure
    tasks_dir = hive_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    
    if not old_tasks_file.exists():
        print("No tasks.json found to migrate")
        return
    
    print(f"Migrating tasks from {old_tasks_file}")
    
    # Load old tasks
    with open(old_tasks_file, "r") as f:
        old_data = json.load(f)
    
    tasks = old_data.get("tasks", [])
    task_counter = old_data.get("task_counter", 0)
    settings = old_data.get("settings", {})
    
    print(f"Found {len(tasks)} tasks to migrate")
    
    # Create index for queue order
    queue = []
    
    # Migrate each task to its own file
    for task in tasks:
        task_id = task["id"]
        
        # Add to queue if not completed
        if task.get("status") not in ["completed", "failed"]:
            queue.append(task_id)
        
        # Save individual task file
        task_file = tasks_dir / f"{task_id}.json"
        with open(task_file, "w") as f:
            json.dump(task, f, indent=2)
        
        print(f"  Migrated: {task_id} ({task.get('status', 'unknown')})")
    
    # Save queue index
    index_data = {
        "queue": queue,
        "task_counter": task_counter,
        "settings": settings,
        "migrated_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    index_file = tasks_dir / "index.json"
    with open(index_file, "w") as f:
        json.dump(index_data, f, indent=2)
    
    print(f"\nCreated index with {len(queue)} queued tasks")
    
    # Backup old file
    backup_file = old_tasks_file.with_suffix(".json.backup")
    shutil.copy2(old_tasks_file, backup_file)
    print(f"\nBacked up old file to: {backup_file}")
    
    # Migrate results if they exist
    old_results = hive_dir / "bus" / "results"
    new_results = hive_dir / "results"
    
    if old_results.exists() and not new_results.exists():
        shutil.move(old_results, new_results)
        print(f"Migrated results directory")
    
    # Create sample task for testing
    sample_task = {
        "id": "sample_001",
        "title": "Sample task for testing new architecture",
        "description": "Test the new Queen orchestrator with a simple task",
        "tags": ["backend", "test"],
        "status": "queued",
        "priority": "low",
        "acceptance": [
            "Create a simple hello.py file",
            "File should print 'Hello from new architecture'"
        ],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    sample_file = tasks_dir / "sample_001.json"
    if not sample_file.exists():
        with open(sample_file, "w") as f:
            json.dump(sample_task, f, indent=2)
        
        # Add to queue
        queue.insert(0, "sample_001")
        index_data["queue"] = queue
        with open(index_file, "w") as f:
            json.dump(index_data, f, indent=2)
        
        print("\nAdded sample_001 task for testing")
    
    print("\nMigration complete!")
    print("\nNew structure:")
    print(f"  Tasks: {tasks_dir}/")
    print(f"  Index: {index_file}")
    print(f"  Results: {new_results}/")
    print("\nTo start the new system:")
    print("  1. Run: python queen_orchestrator.py")
    print("  2. In another terminal: python hive_status.py")

def verify_migration():
    """Verify the migration was successful"""
    root = Path.cwd()
    hive_dir = root / "hive"
    tasks_dir = hive_dir / "tasks"
    
    if not tasks_dir.exists():
        print("Tasks directory not found - migration not run yet")
        return False
    
    # Count task files
    task_files = list(tasks_dir.glob("*.json"))
    task_count = len(task_files) - 1  # Exclude index.json
    
    # Load index
    index_file = tasks_dir / "index.json"
    if index_file.exists():
        with open(index_file, "r") as f:
            index_data = json.load(f)
        queue_count = len(index_data.get("queue", []))
        
        print(f"Migration verified:")
        print(f"  Total tasks: {task_count}")
        print(f"  Queued tasks: {queue_count}")
        print(f"  Task files: {', '.join(sorted([f.stem for f in task_files if f.stem != 'index'])[:5])}...")
        return True
    
    return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        if verify_migration():
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        migrate_tasks()
        print("\nVerifying migration...")
        verify_migration()
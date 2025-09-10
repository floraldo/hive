#!/usr/bin/env python3
"""Simple status monitor for CC MAS"""

import json
from pathlib import Path
from datetime import datetime

def show_status():
    """Show current MAS status"""
    print("\n" + "="*60)
    print("CC MAS Status - " + datetime.now().strftime("%H:%M:%S"))
    print("="*60)
    
    # Check tasks
    tasks_file = Path("hive/bus/tasks.json")
    if tasks_file.exists():
        with open(tasks_file, "r") as f:
            data = json.load(f)
        
        tasks = data.get("tasks", [])
        queued = [t for t in tasks if t.get("status") == "queued"]
        in_progress = [t for t in tasks if t.get("status") in ["assigned", "in_progress"]]
        completed = [t for t in tasks if t.get("status") == "completed"]
        failed = [t for t in tasks if t.get("status") == "failed"]
        
        print("\nTASKS:")
        print(f"  Queued:      {len(queued)}")
        print(f"  In Progress: {len(in_progress)}")
        print(f"  Completed:   {len(completed)}")
        print(f"  Failed:      {len(failed)}")
        print(f"  Total:       {len(tasks)}")
        
        if queued:
            print("\nQUEUED TASKS:")
            for task in queued[:3]:  # Show first 3
                print(f"  - {task['id'][:20]}... {task['title']}")
        
        if in_progress:
            print("\nIN PROGRESS:")
            for task in in_progress:
                print(f"  - {task['id'][:20]}... {task['title']} (by {task.get('assignee', 'unknown')})")
    
    # Check workers
    print("\nWORKERS:")
    workers_dir = Path("hive/workers")
    for worker_id in ["backend", "frontend", "infra"]:
        worker_file = workers_dir / f"{worker_id}.json"
        if worker_file.exists():
            with open(worker_file, "r") as f:
                worker = json.load(f)
            
            status = worker.get("status", "unknown")
            current = worker.get("current_task")
            completed = worker.get("total_tasks_completed", 0)
            
            status_icon = "🟢" if status == "idle" else "🟡" if status == "working" else "🔴"
            print(f"  {status_icon} {worker_id:10} {status:10} (completed: {completed})")
            if current:
                print(f"                    Working on: {current[:30]}...")
    
    print("\n" + "="*60)
    print("Use: python cc_worker.py <worker_id> <seconds> to start workers")
    print("="*60)

if __name__ == "__main__":
    show_status()
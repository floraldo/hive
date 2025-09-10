#!/usr/bin/env python3
"""
HiveCore - Streamlined Hive Manager
Unified task management with built-in cleanup and configuration
"""

import json
import os
import shutil
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

class HiveCore:
    """Streamlined hive task manager with unified operations"""
    
    def __init__(self, root_dir: Optional[Path] = None):
        # Core paths
        self.root = root_dir or Path.cwd()
        self.hive_dir = self.root / "hive"
        self.tasks_dir = self.hive_dir / "tasks"
        self.results_dir = self.hive_dir / "results"
        self.bus_dir = self.hive_dir / "bus"
        self.worktrees_dir = self.root / ".worktrees"
        
        # Configuration
        self.config = {
            "max_parallel_per_role": {"backend": 2, "frontend": 2, "infra": 1},
            "worker_timeout_minutes": 30,
            "zombie_detection_minutes": 5,
            "fresh_cleanup_enabled": True
        }
        
        # Ensure directories exist
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create all required directories"""
        dirs = [self.hive_dir, self.tasks_dir, self.results_dir, self.bus_dir, self.worktrees_dir]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def timestamp(self) -> str:
        """Current timestamp for logging"""
        return datetime.now().strftime("%H:%M:%S")
    
    def load_task_queue(self) -> List[str]:
        """Load task queue from index.json"""
        index_file = self.tasks_dir / "index.json"
        if not index_file.exists():
            return []
        
        try:
            with open(index_file, "r") as f:
                data = json.load(f)
            return data.get("queue", [])
        except Exception as e:
            print(f"[{self.timestamp()}] Error loading queue: {e}")
            return []
    
    def save_task_queue(self, queue: List[str]):
        """Save task queue to index.json"""
        index_file = self.tasks_dir / "index.json"
        data = {
            "queue": queue,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            with open(index_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[{self.timestamp()}] Error saving queue: {e}")
    
    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load task data by ID"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if not task_file.exists():
            return None
        
        try:
            with open(task_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[{self.timestamp()}] Error loading task {task_id}: {e}")
            return None
    
    def save_task(self, task: Dict[str, Any]):
        """Save task data"""
        task_id = task.get("id")
        if not task_id:
            print(f"[{self.timestamp()}] Error: task missing ID")
            return
        
        task_file = self.tasks_dir / f"{task_id}.json"
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        try:
            with open(task_file, "w") as f:
                json.dump(task, f, indent=2)
        except Exception as e:
            print(f"[{self.timestamp()}] Error saving task {task_id}: {e}")
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks with their current status"""
        tasks = []
        for task_file in self.tasks_dir.glob("*.json"):
            if task_file.name == "index.json":
                continue
            
            task = self.load_task(task_file.stem)
            if task:
                tasks.append(task)
        
        return tasks
    
    def clean_fresh_environment(self):
        """Clean all state for fresh environment testing"""
        print(f"[{self.timestamp()}] Cleaning fresh environment...")
        
        # Reset all task statuses to queued
        reset_count = 0
        for task_file in self.tasks_dir.glob("*.json"):
            if task_file.name == "index.json":
                continue
                
            task = self.load_task(task_file.stem)
            if task:
                # Reset task state
                task["status"] = "queued"
                task["current_phase"] = "plan"
                
                # Remove assignment details - ALWAYS clear worktree in fresh mode
                for key in ["assignee", "assigned_at", "started_at", "worktree", "workspace_type"]:
                    if key in task:
                        del task[key]
                
                self.save_task(task)
                reset_count += 1
        
        # Clear all results
        if self.results_dir.exists():
            for result_file in self.results_dir.rglob("*"):
                if result_file.is_file():
                    try:
                        result_file.unlink()
                    except Exception as e:
                        print(f"[{self.timestamp()}] Error removing result {result_file}: {e}")
        
        # Clear fresh worktrees
        fresh_worktrees = self.worktrees_dir / "fresh"
        if fresh_worktrees.exists():
            try:
                shutil.rmtree(fresh_worktrees)
                print(f"[{self.timestamp()}] Cleared fresh worktrees")
            except Exception as e:
                print(f"[{self.timestamp()}] Error clearing fresh worktrees: {e}")
        
        print(f"[{self.timestamp()}] Fresh environment ready - reset {reset_count} tasks")
    
    def get_task_stats(self) -> Dict[str, int]:
        """Get current task statistics"""
        stats = {
            "queued": 0,
            "assigned": 0, 
            "in_progress": 0,
            "completed": 0,
            "failed": 0,
            "total": 0
        }
        
        for task in self.get_all_tasks():
            status = task.get("status", "unknown")
            if status in stats:
                stats[status] += 1
            stats["total"] += 1
        
        return stats
    
    def emit_event(self, event_type: str, **data):
        """Emit event to bus for tracking"""
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data
        }
        
        # Write to daily events file
        events_file = self.bus_dir / f"events_{datetime.now().strftime('%Y%m%d')}.jsonl"
        try:
            with open(events_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"[{self.timestamp()}] Error emitting event: {e}")


def cmd_init(args, core: HiveCore):
    """Initialize hive environment"""
    print("Initializing Hive environment...")
    core.ensure_directories()
    
    # Create empty queue if none exists
    if not core.load_task_queue():
        core.save_task_queue([])
        print("Created empty task queue")
    
    print("Hive initialized successfully")

def cmd_clean(args, core: HiveCore):
    """Clean fresh environment"""
    if args.fresh_env:
        core.clean_fresh_environment()
    else:
        print("Use --fresh-env flag to clean environment")

def cmd_status(args, core: HiveCore):
    """Show hive status"""
    stats = core.get_task_stats()
    queue = core.load_task_queue()
    
    print(f"\n=== HIVE STATUS ===")
    print(f"Queue Length: {len(queue)}")
    print(f"Total Tasks: {stats['total']}")
    print(f"  Queued: {stats['queued']}")
    print(f"  Assigned: {stats['assigned']}")
    print(f"  In Progress: {stats['in_progress']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Failed: {stats['failed']}")
    
    if args.verbose:
        print(f"\n=== TASK DETAILS ===")
        for task in core.get_all_tasks():
            status = task.get("status", "unknown")
            assignee = task.get("assignee", "unassigned")
            print(f"  {task['id']}: {status} ({assignee})")

def cmd_queue(args, core: HiveCore):
    """Add task to queue"""
    task_id = args.task_id
    task_file = core.tasks_dir / f"{task_id}.json"
    
    if not task_file.exists():
        print(f"Error: Task {task_id} not found")
        return
    
    queue = core.load_task_queue()
    if task_id not in queue:
        queue.append(task_id)
        core.save_task_queue(queue)
        print(f"Added {task_id} to queue")
    else:
        print(f"Task {task_id} already in queue")

def cmd_logs(args, core: HiveCore):
    """Show task logs"""
    task_id = args.task_id
    logs_dir = core.root / "hive" / "logs" / task_id
    
    if not logs_dir.exists():
        print(f"No logs found for task {task_id}")
        return
    
    log_files = sorted(logs_dir.glob("*.log"))
    if not log_files:
        print(f"No log files found for task {task_id}")
        return
    
    if args.latest:
        log_files = [log_files[-1]]
    
    for log_file in log_files:
        print(f"\n=== LOG: {log_file.name} ===")
        with open(log_file, "r", encoding="utf-8") as f:
            if args.tail:
                lines = f.readlines()
                print("".join(lines[-args.tail:]))
            else:
                print(f.read())

def cmd_list(args, core: HiveCore):
    """List all tasks"""
    tasks = core.get_all_tasks()
    
    if args.status:
        tasks = [t for t in tasks if t.get("status") == args.status]
    
    print(f"\n=== TASKS ({len(tasks)} total) ===")
    for task in tasks:
        status = task.get("status", "unknown")
        title = task.get("title", task["id"])
        print(f"  [{status:12}] {task['id']:30} - {title}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="HiveCore - Streamlined Hive Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize hive environment")
    init_parser.set_defaults(func=cmd_init)
    
    # Clean command  
    clean_parser = subparsers.add_parser("clean", help="Clean environment")
    clean_parser.add_argument("--fresh-env", action="store_true", help="Clean fresh environment")
    clean_parser.set_defaults(func=cmd_clean)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show hive status")
    status_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    status_parser.set_defaults(func=cmd_status)
    
    # Queue command
    queue_parser = subparsers.add_parser("queue", help="Add task to queue")
    queue_parser.add_argument("task_id", help="Task ID to queue")
    queue_parser.set_defaults(func=cmd_queue)
    
    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show task logs")
    logs_parser.add_argument("task_id", help="Task ID to show logs for")
    logs_parser.add_argument("--latest", action="store_true", help="Show only latest log")
    logs_parser.add_argument("--tail", type=int, help="Show last N lines")
    logs_parser.set_defaults(func=cmd_logs)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all tasks")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.set_defaults(func=cmd_list)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create HiveCore instance
    core = HiveCore()
    
    # Execute command
    args.func(args, core)

if __name__ == "__main__":
    main()
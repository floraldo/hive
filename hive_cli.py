#!/usr/bin/env python3
"""
Hive CLI - Command Line Interface for Headless MAS
Provides easy control and monitoring of the autonomous development system
"""

import json
import argparse
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import time

class HiveCLI:
    """Command line interface for Hive headless MAS"""
    
    def __init__(self, root_dir: str = "."):
        self.root = pathlib.Path(root_dir).resolve()
        self.hive_dir = self.root / "hive"
        self.bus_dir = self.hive_dir / "bus"
        self.workers_dir = self.hive_dir / "workers"
        self.logs_dir = self.hive_dir / "logs"
        
        # Core files
        self.tasks_file = self.bus_dir / "tasks.json"
        self.events_file = self.bus_dir / "events.jsonl"
        
        # Ensure directories exist
        self.hive_dir.mkdir(exist_ok=True)
        self.bus_dir.mkdir(exist_ok=True)
        self.workers_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
    
    def load_tasks(self) -> Dict[str, Any]:
        """Load tasks from tasks.json"""
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"tasks": [], "task_counter": 0, "settings": {}}
    
    def save_tasks(self, tasks_data: Dict[str, Any]):
        """Save tasks to tasks.json"""
        tasks_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(self.tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks_data, f, indent=2)
    
    def load_worker_config(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Load worker configuration"""
        worker_file = self.workers_dir / f"{worker_id}.json"
        try:
            with open(worker_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def create_task(self, args):
        """Create a new task"""
        tasks_data = self.load_tasks()
        
        # Generate unique task ID
        task_id = f"tsk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(tasks_data['tasks']):03d}"
        
        # Parse tags
        tags = [tag.strip() for tag in args.tags.split(",")] if args.tags else []
        
        # Parse acceptance criteria
        criteria = [c.strip() for c in args.criteria.split(";")] if args.criteria else []
        
        task = {
            "id": task_id,
            "title": args.title,
            "description": args.description or "",
            "tags": tags,
            "priority": args.priority,
            "status": "queued",
            "assignee": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "acceptance_criteria": criteria,
            "estimated_effort": args.effort or "unknown",
            "dependencies": []
        }
        
        tasks_data["tasks"].append(task)
        tasks_data["task_counter"] = tasks_data.get("task_counter", 0) + 1
        self.save_tasks(tasks_data)
        
        print(f"✅ Created task {task_id}: {args.title}")
        print(f"   Priority: {args.priority}")
        print(f"   Tags: {', '.join(tags) if tags else 'none'}")
        print(f"   Status: queued")
        
    def list_tasks(self, args):
        """List tasks with optional filtering"""
        tasks_data = self.load_tasks()
        tasks = tasks_data.get("tasks", [])
        
        # Apply filters
        if args.status:
            tasks = [t for t in tasks if t["status"] == args.status]
        if args.assignee:
            tasks = [t for t in tasks if t.get("assignee") == args.assignee]
        if args.priority:
            tasks = [t for t in tasks if t.get("priority") == args.priority]
        if args.tags:
            filter_tags = [tag.strip() for tag in args.tags.split(",")]
            tasks = [t for t in tasks if any(tag in t.get("tags", []) for tag in filter_tags)]
        
        if not tasks:
            print("No tasks found matching criteria")
            return
        
        # Display format
        if args.json:
            print(json.dumps(tasks, indent=2))
        else:
            print(f"\n📋 Tasks ({len(tasks)} found)")
            print("=" * 80)
            
            for task in sorted(tasks, key=lambda t: t.get("created_at", "")):
                status_emoji = {
                    "queued": "⏳",
                    "assigned": "🎯", 
                    "in_progress": "🔄",
                    "ready_for_review": "✅",
                    "completed": "🎉",
                    "failed": "❌",
                    "blocked": "🚫"
                }.get(task["status"], "❓")
                
                priority_emoji = {
                    "critical": "🔴",
                    "high": "🟡", 
                    "normal": "🟢",
                    "low": "🔵"
                }.get(task.get("priority", "normal"), "⚪")
                
                print(f"\n{status_emoji} {priority_emoji} {task['id']} - {task['title']}")
                print(f"   Status: {task['status']}")
                if task.get("assignee"):
                    print(f"   Assigned: {task['assignee']}")
                if task.get("tags"):
                    print(f"   Tags: {', '.join(task['tags'])}")
                if task.get("description"):
                    desc = task["description"][:100] + "..." if len(task["description"]) > 100 else task["description"]
                    print(f"   Description: {desc}")
                    
                # Show acceptance criteria if detailed view
                if args.detailed and task.get("acceptance_criteria"):
                    print(f"   Acceptance Criteria:")
                    for criteria in task["acceptance_criteria"]:
                        print(f"     • {criteria}")
    
    def show_task(self, args):
        """Show detailed information about a specific task"""
        tasks_data = self.load_tasks()
        tasks = tasks_data.get("tasks", [])
        
        task = next((t for t in tasks if t["id"] == args.task_id), None)
        if not task:
            print(f"❌ Task {args.task_id} not found")
            return
        
        if args.json:
            print(json.dumps(task, indent=2))
        else:
            status_emoji = {
                "queued": "⏳",
                "assigned": "🎯",
                "in_progress": "🔄", 
                "ready_for_review": "✅",
                "completed": "🎉",
                "failed": "❌",
                "blocked": "🚫"
            }.get(task["status"], "❓")
            
            print(f"\n{status_emoji} Task Details: {task['id']}")
            print("=" * 50)
            print(f"Title: {task['title']}")
            print(f"Status: {task['status']}")
            print(f"Priority: {task.get('priority', 'normal')}")
            print(f"Created: {task.get('created_at', 'unknown')}")
            if task.get("assignee"):
                print(f"Assigned to: {task['assignee']}")
            if task.get("tags"):
                print(f"Tags: {', '.join(task['tags'])}")
            if task.get("estimated_effort"):
                print(f"Effort: {task['estimated_effort']}")
            
            print(f"\nDescription:")
            print(task.get("description", "No description provided"))
            
            if task.get("acceptance_criteria"):
                print(f"\nAcceptance Criteria:")
                for criteria in task["acceptance_criteria"]:
                    print(f"  • {criteria}")
            
            # Show execution details if available
            if task.get("execution_log"):
                print(f"\nExecution Log: {task['execution_log']}")
            if task.get("failure_reason"):
                print(f"\nFailure Reason: {task['failure_reason']}")
    
    def update_task(self, args):
        """Update task properties"""
        tasks_data = self.load_tasks()
        tasks = tasks_data.get("tasks", [])
        
        task = next((t for t in tasks if t["id"] == args.task_id), None)
        if not task:
            print(f"❌ Task {args.task_id} not found")
            return
        
        # Update fields
        updated = False
        if args.status:
            task["status"] = args.status
            updated = True
        if args.priority:
            task["priority"] = args.priority  
            updated = True
        if args.assignee:
            task["assignee"] = args.assignee
            updated = True
        if args.title:
            task["title"] = args.title
            updated = True
        
        if updated:
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.save_tasks(tasks_data)
            print(f"✅ Updated task {args.task_id}")
        else:
            print("No updates specified")
    
    def worker_status(self, args):
        """Show worker status information"""
        worker_configs = {}
        for worker_file in self.workers_dir.glob("*.json"):
            config = self.load_worker_config(worker_file.stem)
            if config:
                worker_configs[worker_file.stem] = config
        
        if not worker_configs:
            print("No workers configured")
            return
        
        if args.json:
            print(json.dumps(worker_configs, indent=2))
        else:
            print(f"\n🤖 Worker Status")
            print("=" * 60)
            
            for worker_id, config in worker_configs.items():
                status_emoji = {
                    "idle": "💤",
                    "working": "🔄",
                    "assigned": "🎯",
                    "offline": "⚫"
                }.get(config.get("status", "unknown"), "❓")
                
                role = config.get("role", "unknown").replace("_", " ").title()
                
                print(f"\n{status_emoji} {worker_id.upper()} ({role})")
                print(f"   Status: {config.get('status', 'unknown')}")
                if config.get("current_task"):
                    print(f"   Current Task: {config['current_task']}")
                print(f"   Branch: {config.get('branch', 'unknown')}")
                print(f"   Completed: {config.get('total_tasks_completed', 0)} tasks")
                print(f"   Enabled: {'Yes' if config.get('is_enabled') else 'No'}")
                if config.get("last_heartbeat"):
                    print(f"   Last Heartbeat: {config['last_heartbeat']}")
                
                # Show capabilities
                capabilities = config.get("capabilities", [])
                if capabilities:
                    print(f"   Capabilities: {', '.join(capabilities)}")
    
    def system_status(self, args):
        """Show overall system status"""
        tasks_data = self.load_tasks()
        tasks = tasks_data.get("tasks", [])
        
        # Task statistics
        status_counts = {}
        priority_counts = {}
        for task in tasks:
            status = task["status"]
            priority = task.get("priority", "normal")
            status_counts[status] = status_counts.get(status, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        # Worker statistics
        worker_status = {}
        for worker_file in self.workers_dir.glob("*.json"):
            config = self.load_worker_config(worker_file.stem)
            if config:
                status = config.get("status", "unknown")
                worker_status[status] = worker_status.get(status, 0) + 1
        
        if args.json:
            data = {
                "tasks": {
                    "total": len(tasks),
                    "by_status": status_counts,
                    "by_priority": priority_counts
                },
                "workers": worker_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            print(json.dumps(data, indent=2))
        else:
            print(f"\n🚀 Hive System Status")
            print("=" * 40)
            
            print(f"\n📋 Tasks ({len(tasks)} total)")
            for status, count in status_counts.items():
                emoji = {
                    "queued": "⏳", "assigned": "🎯", "in_progress": "🔄",
                    "ready_for_review": "✅", "completed": "🎉", "failed": "❌", "blocked": "🚫"
                }.get(status, "❓")
                print(f"   {emoji} {status}: {count}")
            
            print(f"\n🤖 Workers")
            for status, count in worker_status.items():
                emoji = {"idle": "💤", "working": "🔄", "assigned": "🎯", "offline": "⚫"}.get(status, "❓")
                print(f"   {emoji} {status}: {count}")
            
            print(f"\n📊 Priority Distribution")
            for priority, count in priority_counts.items():
                emoji = {"critical": "🔴", "high": "🟡", "normal": "🟢", "low": "🔵"}.get(priority, "⚪")
                print(f"   {emoji} {priority}: {count}")
    
    def start_orchestrator(self, args):
        """Start the orchestrator process"""
        print("🚀 Starting Hive Orchestrator...")
        try:
            if args.background:
                # Start in background
                subprocess.Popen([
                    sys.executable, "orchestrator.py"
                ], cwd=str(self.root))
                print("✅ Orchestrator started in background")
            else:
                # Start in foreground
                subprocess.run([
                    sys.executable, "orchestrator.py"
                ], cwd=str(self.root))
        except KeyboardInterrupt:
            print("\n🛑 Orchestrator stopped by user")
        except Exception as e:
            print(f"❌ Failed to start orchestrator: {e}")
    
    def start_worker(self, args):
        """Start a specific worker process"""
        print(f"🤖 Starting {args.worker_id} worker...")
        try:
            if args.background:
                subprocess.Popen([
                    sys.executable, "headless_workers.py", args.worker_id,
                    "--interval", str(args.interval)
                ], cwd=str(self.root))
                print(f"✅ Worker {args.worker_id} started in background")
            else:
                subprocess.run([
                    sys.executable, "headless_workers.py", args.worker_id,
                    "--interval", str(args.interval)
                ], cwd=str(self.root))
        except KeyboardInterrupt:
            print(f"\n🛑 Worker {args.worker_id} stopped by user")
        except Exception as e:
            print(f"❌ Failed to start worker {args.worker_id}: {e}")
    
    def logs(self, args):
        """Show recent log entries"""
        if args.events:
            # Show event log
            if not self.events_file.exists():
                print("No events found")
                return
                
            with open(self.events_file, "r", encoding="utf-8") as f:
                events = [json.loads(line.strip()) for line in f if line.strip()]
            
            # Filter and limit
            if args.worker:
                events = [e for e in events if e.get("worker") == args.worker]
            
            events = events[-args.limit:]
            
            if args.json:
                print(json.dumps(events, indent=2))
            else:
                print(f"\n📝 Recent Events ({len(events)})")
                print("=" * 60)
                for event in events:
                    timestamp = event.get("timestamp", "unknown")[:19]
                    event_type = event.get("type", "unknown")
                    worker = event.get("worker", "system")
                    data = event.get("data", {})
                    
                    print(f"{timestamp} | {worker:>10} | {event_type}")
                    if args.detailed:
                        for key, value in data.items():
                            print(f"  {key}: {value}")
        else:
            # Show worker logs
            if args.worker:
                log_file = self.logs_dir / f"{args.worker}.log"
                if log_file.exists():
                    subprocess.run(["tail", "-n", str(args.limit), str(log_file)])
                else:
                    print(f"No log file found for {args.worker}")
            else:
                print("Available log files:")
                for log_file in self.logs_dir.glob("*.log"):
                    print(f"  {log_file.name}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Hive Headless MAS CLI")
    parser.add_argument("--root", default=".", help="Root directory")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Task management commands
    task_create = subparsers.add_parser("create-task", help="Create a new task")
    task_create.add_argument("title", help="Task title")
    task_create.add_argument("--description", help="Task description")
    task_create.add_argument("--tags", help="Comma-separated tags")
    task_create.add_argument("--priority", choices=["critical", "high", "normal", "low"], default="normal")
    task_create.add_argument("--criteria", help="Semicolon-separated acceptance criteria")
    task_create.add_argument("--effort", help="Estimated effort (e.g., 2h, 1d)")
    
    task_list = subparsers.add_parser("list-tasks", help="List tasks")
    task_list.add_argument("--status", help="Filter by status")
    task_list.add_argument("--assignee", help="Filter by assignee")
    task_list.add_argument("--priority", help="Filter by priority")
    task_list.add_argument("--tags", help="Filter by tags (comma-separated)")
    task_list.add_argument("--json", action="store_true", help="Output as JSON")
    task_list.add_argument("--detailed", action="store_true", help="Show detailed information")
    
    task_show = subparsers.add_parser("show-task", help="Show task details")
    task_show.add_argument("task_id", help="Task ID")
    task_show.add_argument("--json", action="store_true", help="Output as JSON")
    
    task_update = subparsers.add_parser("update-task", help="Update task")
    task_update.add_argument("task_id", help="Task ID")
    task_update.add_argument("--status", help="New status")
    task_update.add_argument("--priority", help="New priority")
    task_update.add_argument("--assignee", help="New assignee")
    task_update.add_argument("--title", help="New title")
    
    # System status commands
    status = subparsers.add_parser("status", help="Show system status")
    status.add_argument("--json", action="store_true", help="Output as JSON")
    
    workers = subparsers.add_parser("workers", help="Show worker status")
    workers.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Process management
    start_orch = subparsers.add_parser("start-orchestrator", help="Start orchestrator")
    start_orch.add_argument("--background", action="store_true", help="Start in background")
    
    start_work = subparsers.add_parser("start-worker", help="Start worker")
    start_work.add_argument("worker_id", choices=["queen", "frontend", "backend", "infra"])
    start_work.add_argument("--interval", type=int, default=15, help="Cycle interval in seconds")
    start_work.add_argument("--background", action="store_true", help="Start in background")
    
    # Logging
    logs_cmd = subparsers.add_parser("logs", help="Show logs")
    logs_cmd.add_argument("--worker", help="Specific worker logs")
    logs_cmd.add_argument("--events", action="store_true", help="Show event log instead")
    logs_cmd.add_argument("--limit", type=int, default=50, help="Number of entries to show")
    logs_cmd.add_argument("--json", action="store_true", help="Output as JSON")
    logs_cmd.add_argument("--detailed", action="store_true", help="Show detailed event data")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = HiveCLI(args.root)
    
    # Route to appropriate handler
    if args.command == "create-task":
        cli.create_task(args)
    elif args.command == "list-tasks":
        cli.list_tasks(args)
    elif args.command == "show-task":
        cli.show_task(args)
    elif args.command == "update-task":
        cli.update_task(args)
    elif args.command == "status":
        cli.system_status(args)
    elif args.command == "workers":
        cli.worker_status(args)
    elif args.command == "start-orchestrator":
        cli.start_orchestrator(args)
    elif args.command == "start-worker":
        cli.start_worker(args)
    elif args.command == "logs":
        cli.logs(args)

if __name__ == "__main__":
    main()
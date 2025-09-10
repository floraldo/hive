#!/usr/bin/env python3
"""
Hive Status Dashboard - Real-time monitoring for the MAS
Tails the event bus and shows live worker status, tasks, and PRs
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any
from collections import defaultdict

class HiveStatus:
    """Real-time status dashboard for Hive MAS"""
    
    def __init__(self):
        self.root = Path.cwd()
        self.hive_dir = self.root / "hive"
        self.events_file = self.hive_dir / "bus" / "events.jsonl"
        self.tasks_file = self.hive_dir / "bus" / "tasks.json"
        self.workers_dir = self.hive_dir / "workers"
        
        # Track state
        self.worker_status = {}
        self.task_status = {}
        self.recent_events = []
        self.prs = []
        
    def load_workers(self) -> Dict[str, Any]:
        """Load worker configurations"""
        workers = {}
        if self.workers_dir.exists():
            for worker_file in self.workers_dir.glob("*.json"):
                try:
                    with open(worker_file, "r") as f:
                        data = json.load(f)
                        workers[data["worker_id"]] = data
                except:
                    pass
        return workers
    
    def load_tasks(self) -> List[Dict[str, Any]]:
        """Load current tasks"""
        try:
            if self.tasks_file.exists():
                with open(self.tasks_file, "r") as f:
                    return json.load(f).get("tasks", [])
        except:
            pass
        return []
    
    def tail_events(self, last_pos: int = 0) -> tuple[List[Dict], int]:
        """Tail new events from the event bus"""
        events = []
        try:
            if self.events_file.exists():
                with open(self.events_file, "r") as f:
                    f.seek(last_pos)
                    for line in f:
                        try:
                            events.append(json.loads(line))
                        except:
                            pass
                    last_pos = f.tell()
        except:
            pass
        return events, last_pos
    
    def format_time_ago(self, iso_time: str) -> str:
        """Format ISO time as 'X ago'"""
        try:
            dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - dt
            
            if delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600}h ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60}m ago"
            else:
                return f"{delta.seconds}s ago"
        except:
            return "unknown"
    
    def print_dashboard(self):
        """Print the status dashboard"""
        # Clear screen (works on most terminals)
        print("\033[2J\033[H")
        
        print("=" * 80)
        print("HIVE FLEET COMMAND - LIVE STATUS DASHBOARD")
        print("=" * 80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Workers section
        workers = self.load_workers()
        print("🤖 WORKERS")
        print("-" * 40)
        for wid, w in workers.items():
            status = w.get("status", "unknown")
            heartbeat = self.format_time_ago(w.get("last_heartbeat", ""))
            task = w.get("current_task", "idle")
            completed = w.get("total_tasks_completed", 0)
            
            status_icon = "🟢" if status == "working" else "⚪"
            print(f"{status_icon} {wid:10} | {status:8} | Task: {task:20} | Done: {completed:3} | HB: {heartbeat}")
        
        print()
        
        # Tasks section
        tasks = self.load_tasks()
        task_counts = defaultdict(int)
        for t in tasks:
            task_counts[t.get("status", "unknown")] += 1
        
        print("📋 TASK QUEUE")
        print("-" * 40)
        print(f"Queued: {task_counts['queued']:3} | Assigned: {task_counts['assigned']:3} | "
              f"In Progress: {task_counts['in_progress']:3} | Completed: {task_counts['completed']:3} | "
              f"Failed: {task_counts['failed']:3}")
        
        # Show active tasks
        active_tasks = [t for t in tasks if t.get("status") in ["assigned", "in_progress"]]
        if active_tasks:
            print("\nActive Tasks:")
            for t in active_tasks[:5]:  # Show max 5
                assignee = t.get("assignee", "unassigned")
                print(f"  [{t['id']}] {t['title'][:40]:40} | {assignee:10} | {t.get('status', '')}")
        
        print()
        
        # Recent events
        if self.recent_events:
            print("📡 RECENT EVENTS")
            print("-" * 40)
            for evt in self.recent_events[-10:]:  # Last 10 events
                evt_type = evt.get("type", "unknown")
                worker = evt.get("worker", "system")
                task_id = evt.get("task_id", "")
                ts = self.format_time_ago(evt.get("ts", ""))
                
                # Format based on event type
                if evt_type == "task_claim":
                    print(f"  🎯 {worker} claimed {task_id} ({ts})")
                elif evt_type == "task_start":
                    print(f"  🚀 {worker} started {task_id} ({ts})")
                elif evt_type == "task_update":
                    state = evt.get("state", "")
                    pr = evt.get("pr", "")
                    if pr:
                        print(f"  ✅ {worker} {state} {task_id} PR: {pr} ({ts})")
                    else:
                        print(f"  ✅ {worker} {state} {task_id} ({ts})")
                elif evt_type == "task_failed":
                    print(f"  ❌ {worker} failed {task_id} ({ts})")
                elif evt_type == "heartbeat":
                    print(f"  💗 {worker} heartbeat ({ts})")
                else:
                    print(f"  📌 {evt_type} from {worker} ({ts})")
        
        print()
        
        # PRs section
        prs = [t for t in tasks if t.get("pr")]
        if prs:
            print("🔗 PULL REQUESTS")
            print("-" * 40)
            for t in prs[-5:]:  # Last 5 PRs
                print(f"  {t.get('pr', 'N/A'):50} | {t['title'][:30]}")
        
        print()
        print("Press Ctrl+C to exit | Updates every 2 seconds")
        print("=" * 80)
    
    def run(self, refresh_seconds: int = 2):
        """Run the dashboard with periodic refresh"""
        last_pos = 0
        
        try:
            while True:
                # Get new events
                new_events, last_pos = self.tail_events(last_pos)
                self.recent_events.extend(new_events)
                
                # Keep only last 100 events
                if len(self.recent_events) > 100:
                    self.recent_events = self.recent_events[-100:]
                
                # Print dashboard
                self.print_dashboard()
                
                # Wait before refresh
                time.sleep(refresh_seconds)
                
        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")

def main():
    """Main entry point"""
    print("Starting Hive Status Dashboard...")
    dashboard = HiveStatus()
    dashboard.run()

if __name__ == "__main__":
    main()
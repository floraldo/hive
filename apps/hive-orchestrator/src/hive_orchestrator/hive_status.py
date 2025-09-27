#!/usr/bin/env python3
"""
Hive Status Dashboard - Read-only viewer for new architecture
Shows tasks, active workers, results, and events without any scheduling logic
"""

import json
import time
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Windows console color support
if sys.platform == "win32":
    os.system("color")

class HiveStatus:
    """Pure read-only status viewer for Hive MAS"""
    
    def __init__(self):
        self.root = Path.cwd()
        self.hive_dir = self.root / "hive"
        self.tasks_dir = self.hive_dir / "tasks"
        self.results_dir = self.hive_dir / "results"
        self.events_file = self.get_events_file()
        
        # Track state for display
        self.recent_events = []
        self.last_event_pos = 0
        
        # Colors for terminal (ANSI codes)
        self.colors = {
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "blue": "\033[94m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "reset": "\033[0m",
            "bold": "\033[1m"
        }
        
        # Emoji toggle for Windows compatibility
        self.use_emoji = os.getenv("HIVE_EMOJI", "1") != "0"
    
    def get_events_file(self) -> Path:
        """Get today's events file"""
        date_suffix = datetime.now().strftime("%Y%m%d")
        return self.hive_dir / "bus" / f"events_{date_suffix}.jsonl"
    
    def color(self, text: str, color_name: str) -> str:
        """Add color to text for terminal display"""
        if color_name in self.colors:
            return f"{self.colors[color_name]}{text}{self.colors['reset']}"
        return text
    
    def load_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Load all tasks from per-task files"""
        tasks = {}
        
        if not self.tasks_dir.exists():
            return tasks
        
        for task_file in self.tasks_dir.glob("*.json"):
            if task_file.stem == "index":
                continue
            
            try:
                with open(task_file, "r") as f:
                    task = json.load(f)
                    tasks[task["id"]] = task
            except (json.JSONDecodeError, KeyError, IOError) as e:
                # Silently skip corrupted task files
                pass
        
        return tasks
    
    def load_queue(self) -> List[str]:
        """Load task queue order"""
        index_file = self.tasks_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r") as f:
                    data = json.load(f)
                    return data.get("queue", [])
            except (json.JSONDecodeError, IOError) as e:
                # Silently skip if queue file not readable
                pass
        return []
    
    def load_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load latest result for a task"""
        results_dir = self.results_dir / task_id
        
        if not results_dir.exists():
            return None
        
        # Get latest result
        result_files = sorted(results_dir.glob("*.json"))
        if result_files:
            try:
                with open(result_files[-1], "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError, IndexError) as e:
                # Silently skip if result file not readable
                pass
        
        return None
    
    def tail_events(self) -> List[Dict[str, Any]]:
        """Tail new events from the event bus"""
        events = []
        
        # Check if we need to switch to new day's file
        current_file = self.get_events_file()
        if current_file != self.events_file:
            self.events_file = current_file
            self.last_event_pos = 0
        
        if not self.events_file.exists():
            return events
        
        try:
            with open(self.events_file, "r") as f:
                f.seek(self.last_event_pos)
                for line in f:
                    try:
                        events.append(json.loads(line))
                    except (json.JSONDecodeError, ValueError) as e:
                        # Skip malformed event lines
                        pass
                self.last_event_pos = f.tell()
        except (IOError, OSError) as e:
            # Event file not accessible
            pass
        
        return events
    
    def format_time_ago(self, iso_time: str) -> str:
        """Format ISO time as 'X ago'"""
        try:
            dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - dt
            
            if delta.days > 0:
                return f"{delta.days}d"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600}h"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60}m"
            else:
                return f"{delta.seconds}s"
        except (ValueError, TypeError, AttributeError) as e:
            return "?"
    
    def format_duration(self, ms: int) -> str:
        """Format duration in milliseconds"""
        if ms < 1000:
            return f"{ms}ms"
        elif ms < 60000:
            return f"{ms / 1000:.1f}s"
        else:
            return f"{ms / 60000:.1f}m"
    
    def get_status_icon(self, status: str) -> str:
        """Get colored status icon with emoji/ASCII fallback"""
        if self.use_emoji:
            icons = {
                "queued": self.color("⏳", "white"),
                "assigned": self.color("📋", "cyan"),
                "in_progress": self.color("🔄", "yellow"),
                "testing": self.color("🧪", "blue"),
                "reviewing": self.color("👀", "blue"),
                "pr_open": self.color("🔗", "cyan"),
                "completed": self.color("✅", "green"),
                "failed": self.color("❌", "red"),
                "blocked": self.color("🚫", "red")
            }
        else:
            icons = {
                "queued": self.color("Q", "white"),
                "assigned": self.color("A", "cyan"),
                "in_progress": self.color("IP", "yellow"),
                "testing": self.color("T", "blue"),
                "reviewing": self.color("R", "blue"),
                "pr_open": self.color("PR", "cyan"),
                "completed": self.color("OK", "green"),
                "failed": self.color("X", "red"),
                "blocked": self.color("BLK", "red")
            }
        return icons.get(status, "?")
    
    def get_border_char(self, char_type: str) -> str:
        """Get border character with ASCII fallback"""
        if self.use_emoji:
            borders = {"double": "═", "single": "─"}
        else:
            borders = {"double": "=", "single": "-"}
        return borders.get(char_type, "-")
    
    def print_dashboard(self):
        """Print the status dashboard"""
        # Clear screen
        print("\033[2J\033[H", end="")
        
        # Header
        print(self.color(self.get_border_char("double") * 80, "cyan"))
        print(self.color("HIVE FLEET STATUS - READ-ONLY VIEWER", "bold"))
        print(self.color(self.get_border_char("double") * 80, "cyan"))
        print(f"Time: {datetime.now().strftime('%H:%M:%S')} | Events: {self.events_file.name}")
        print()
        
        # Load data
        tasks = self.load_tasks()
        queue = self.load_queue()
        
        # Task statistics
        stats = defaultdict(int)
        for task in tasks.values():
            stats[task.get("status", "unknown")] += 1
        
        # Status bar
        print(self.color("TASK PIPELINE", "bold"))
        print(self.get_border_char("single") * 40)
        status_line = (
            f"Queued: {self.color(str(stats['queued']), 'white'):>3} | "
            f"Assigned: {self.color(str(stats['assigned']), 'cyan'):>3} | "
            f"In Progress: {self.color(str(stats['in_progress']), 'yellow'):>3} | "
            f"Testing: {self.color(str(stats['testing']), 'blue'):>3} | "
            f"PR Open: {self.color(str(stats['pr_open']), 'cyan'):>3} | "
            f"Completed: {self.color(str(stats['completed']), 'green'):>3} | "
            f"Failed: {self.color(str(stats['failed']), 'red'):>3}"
        )
        print(status_line)
        print()
        
        # Active tasks
        active_tasks = [
            t for t in tasks.values() 
            if t.get("status") in ["assigned", "in_progress", "testing", "reviewing"]
        ]
        
        if active_tasks:
            print(self.color("ACTIVE TASKS", "bold"))
            print(self.get_border_char("single") * 40)
            for task in sorted(active_tasks, key=lambda t: t.get("started_at", ""))[:5]:
                status = task.get("status", "unknown")
                icon = self.get_status_icon(status)
                assignee = task.get("assignee", "?")
                started = task.get("started_at", "")
                ago = self.format_time_ago(started) if started else "?"
                
                # Check for result
                result = self.load_results(task["id"])
                if result:
                    duration = self.format_duration(result.get("duration_ms", 0))
                    notes = result.get("notes", "")[:30]
                else:
                    duration = ago
                    notes = ""
                
                print(f"{icon} [{task['id']}] {task.get('title', '')[:35]:35} | "
                      f"{assignee:8} | {duration:6} | {notes}")
            print()
        
        # Recent completions
        completed = [
            t for t in tasks.values()
            if t.get("status") in ["completed", "pr_open"]
        ]
        
        if completed:
            print(self.color("RECENT COMPLETIONS", "bold"))
            print(self.get_border_char("single") * 40)
            for task in sorted(completed, key=lambda t: t.get("completed_at", ""), reverse=True)[:3]:
                icon = self.get_status_icon(task.get("status"))
                pr = task.get("pr", "")
                
                result = self.load_results(task["id"])
                if result:
                    duration = self.format_duration(result.get("duration_ms", 0))
                else:
                    duration = "?"
                
                if pr:
                    pr_short = pr.split("/")[-1] if "/" in pr else pr[:20]
                    print(f"{icon} [{task['id']}] {task.get('title', '')[:30]:30} | "
                          f"{duration:6} | PR: {self.color(pr_short, 'cyan')}")
                else:
                    print(f"{icon} [{task['id']}] {task.get('title', '')[:30]:30} | {duration:6}")
            print()
        
        # Recent failures
        failed = [
            t for t in tasks.values()
            if t.get("status") in ["failed", "blocked"]
        ]
        
        if failed:
            print(self.color("FAILURES & BLOCKS", "bold"))
            print(self.get_border_char("single") * 40)
            for task in sorted(failed, key=lambda t: t.get("failed_at", ""), reverse=True)[:3]:
                icon = self.get_status_icon(task.get("status"))
                reason = task.get("failure_reason", "Unknown")[:40]
                
                # Check if inspector task created
                fix_task_id = f"fix_{task['id']}"
                has_fix = fix_task_id in tasks
                
                if has_fix:
                    print(f"{icon} [{task['id']}] {reason} | "
                          f"Fix: {self.color(fix_task_id, 'yellow')}")
                else:
                    print(f"{icon} [{task['id']}] {reason}")
            print()
        
        # Recent events
        if self.recent_events:
            print(self.color("EVENT STREAM", "bold"))
            print(self.get_border_char("single") * 40)
            
            for event in self.recent_events[-8:]:
                evt_type = event.get("type", "")
                worker = event.get("worker", event.get("component", "?"))
                task_id = event.get("task_id", "")
                ts = self.format_time_ago(event.get("ts", ""))
                
                # Format by type
                if evt_type == "worker_spawned":
                    rocket = "🚀" if self.use_emoji else ">"
                    print(f"  {rocket} {self.color(worker, 'cyan')} spawned for {task_id} ({ts} ago)")
                elif evt_type == "task_execution_complete":
                    status = event.get("status", "?")
                    color = "green" if status == "success" else "red"
                    check = "✓" if self.use_emoji else "+"
                    print(f"  {check} {self.color(worker, 'cyan')} {self.color(status, color)} {task_id} ({ts} ago)")
                elif evt_type == "task_complete":
                    check = "✅" if self.use_emoji else "OK"
                    print(f"  {check} {task_id} completed ({ts} ago)")
                elif evt_type == "task_failed":
                    x = "❌" if self.use_emoji else "X"
                    print(f"  {x} {task_id} failed: {event.get('notes', '')[:30]} ({ts} ago)")
                elif evt_type == "inspector_task_created":
                    tool = "🔧" if self.use_emoji else "FIX"
                    print(f"  {tool} Inspector {self.color(event.get('inspector', '?'), 'yellow')} "
                          f"for {event.get('parent_task', '?')} ({ts} ago)")
                elif evt_type == "queen_started":
                    crown = "👑" if self.use_emoji else "Q"
                    print(f"  {crown} Queen orchestrator started ({ts} ago)")
                elif evt_type == "queen_stopped":
                    crown = "👑" if self.use_emoji else "Q"
                    print(f"  {crown} Queen orchestrator stopped ({ts} ago)")
                else:
                    print(f"  • {evt_type} from {worker} ({ts} ago)")
            print()
        
        # Footer
        print(self.get_border_char("single") * 80)
        print("Press Ctrl+C to exit | Updates every 2 seconds | Read-only viewer")
    
    def run(self, refresh_seconds: int = 2):
        """Run the dashboard with periodic refresh"""
        print("Starting Hive Status Dashboard v2...")
        
        try:
            while True:
                # Get new events
                new_events = self.tail_events()
                self.recent_events.extend(new_events)
                
                # Keep only last 100 events
                if len(self.recent_events) > 100:
                    self.recent_events = self.recent_events[-100:]
                
                # Print dashboard
                self.print_dashboard()
                
                # Wait
                time.sleep(refresh_seconds)
                
        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")

def main():
    """Main entry point"""
    dashboard = HiveStatus()
    dashboard.run()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
hivectl - Control interface for Hive Fleet Command
Interrupt, resume, attach, label, and nudge tasks
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

class HiveCtl:
    """Control interface for live steering of Hive system"""
    
    def __init__(self):
        self.root = Path.cwd()
        self.hive_dir = self.root / "hive"
        self.tasks_dir = self.hive_dir / "tasks"
        self.operator_dir = self.hive_dir / "operator"
        self.interrupts_dir = self.operator_dir / "interrupts"
        self.hints_dir = self.operator_dir / "hints"
        
        # Ensure directories
        self.interrupts_dir.mkdir(parents=True, exist_ok=True)
        self.hints_dir.mkdir(parents=True, exist_ok=True)
    
    def interrupt(self, task_id: str, reason: str = "User interrupt"):
        """Interrupt a running task"""
        interrupt_file = self.interrupts_dir / f"{task_id}.json"
        data = {
            "task_id": task_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": os.environ.get("USER", "operator")
        }
        
        with open(interrupt_file, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"✋ Interrupted {task_id}: {reason}")
        print(f"   Task will stop at next epoch boundary")
    
    def resume(self, task_id: str):
        """Resume an interrupted task"""
        # Remove interrupt file
        interrupt_file = self.interrupts_dir / f"{task_id}.json"
        if interrupt_file.exists():
            interrupt_file.unlink()
            print(f"▶️  Resumed {task_id}")
        
        # Update task status back to queued
        task_file = self.tasks_dir / f"{task_id}.json"
        if task_file.exists():
            with open(task_file, "r") as f:
                task = json.load(f)
            
            if task.get("status") == "blocked":
                task["status"] = "queued"
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
                
                with open(task_file, "w") as f:
                    json.dump(task, f, indent=2)
                
                print(f"   Task status: blocked → queued")
    
    def attach(self, task_id: str):
        """Attach to task's worktree for live observation"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if not task_file.exists():
            print(f"❌ Task {task_id} not found")
            return
        
        with open(task_file, "r") as f:
            task = json.load(f)
        
        worktree = task.get("worktree")
        if not worktree:
            print(f"❌ No worktree for {task_id}")
            return
        
        print(f"📂 Attaching to {task_id} worktree:")
        print(f"   {worktree}")
        print(f"   Branch: {task.get('branch', 'unknown')}")
        print()
        print("You can now:")
        print(f"  cd {worktree}")
        print(f"  git status")
        print(f"  tail -f {self.hive_dir}/results/{task_id}/*.json")
    
    def nudge(self, task_id: str, hint: str):
        """Add a hint for the worker to consider"""
        hint_file = self.hints_dir / f"{task_id}.md"
        
        # Append hint with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(hint_file, "a") as f:
            f.write(f"\n\n---\n**Operator Hint ({timestamp})**\n\n{hint}\n")
        
        print(f"💡 Added hint for {task_id}")
        print(f"   Worker will see this on next phase")
    
    def label(self, pr_url: str, label: str = "auto-merge-ok"):
        """Add label to PR (typically auto-merge-ok)"""
        try:
            result = subprocess.run(
                ["gh", "pr", "edit", pr_url, "--add-label", label],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"🏷️  Added '{label}' to {pr_url}")
            else:
                print(f"❌ Failed to add label: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def cleanup(self, task_id: str):
        """Clean up worktree and branch for completed task"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if not task_file.exists():
            print(f"❌ Task {task_id} not found")
            return
        
        with open(task_file, "r") as f:
            task = json.load(f)
        
        worktree = task.get("worktree")
        branch = task.get("branch")
        
        cleaned = []
        
        # Remove worktree
        if worktree and Path(worktree).exists():
            try:
                subprocess.run(
                    ["git", "worktree", "remove", worktree, "--force"],
                    check=True,
                    capture_output=True
                )
                cleaned.append(f"Removed worktree: {worktree}")
            except:
                pass
        
        # Delete branch
        if branch:
            try:
                subprocess.run(
                    ["git", "branch", "-D", branch],
                    check=True,
                    capture_output=True
                )
                cleaned.append(f"Deleted branch: {branch}")
            except:
                pass
        
        # Clean up hints and interrupts
        for f in [
            self.hints_dir / f"{task_id}.md",
            self.interrupts_dir / f"{task_id}.json"
        ]:
            if f.exists():
                f.unlink()
                cleaned.append(f"Removed {f.name}")
        
        if cleaned:
            print(f"🧹 Cleaned up {task_id}:")
            for item in cleaned:
                print(f"   - {item}")
        else:
            print(f"   Nothing to clean for {task_id}")
    
    def status(self, task_id: str):
        """Show detailed status of a task"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if not task_file.exists():
            print(f"❌ Task {task_id} not found")
            return
        
        with open(task_file, "r") as f:
            task = json.load(f)
        
        print(f"📋 Task: {task_id}")
        print(f"   Title: {task.get('title', 'Unknown')}")
        print(f"   Status: {task.get('status', 'unknown')}")
        print(f"   Phase: {task.get('current_phase', 'none')}")
        print(f"   Assignee: {task.get('assignee', 'unassigned')}")
        print(f"   Branch: {task.get('branch', 'none')}")
        print(f"   PR: {task.get('pr', 'none')}")
        
        # Check for results
        results_dir = self.hive_dir / "results" / task_id
        if results_dir.exists():
            results = sorted(results_dir.glob("*.json"))
            if results:
                print(f"   Results: {len(results)} runs")
                
                # Show latest result
                with open(results[-1], "r") as f:
                    result = json.load(f)
                print(f"   Latest: {result.get('status', '?')} - {result.get('notes', '')[:50]}")
    
    def list_tasks(self, status_filter: Optional[str] = None):
        """List tasks with optional status filter"""
        tasks = []
        
        for task_file in self.tasks_dir.glob("*.json"):
            if task_file.stem == "index":
                continue
            
            try:
                with open(task_file, "r") as f:
                    task = json.load(f)
                    
                if not status_filter or task.get("status") == status_filter:
                    tasks.append(task)
            except:
                pass
        
        if not tasks:
            print("No tasks found")
            return
        
        # Sort by created_at
        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        
        print(f"Found {len(tasks)} tasks:")
        for task in tasks[:20]:  # Show max 20
            status = task.get("status", "unknown")
            icon = {
                "queued": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌",
                "blocked": "🚫",
                "pr_open": "🔗"
            }.get(status, "❓")
            
            print(f"{icon} [{task['id']}] {task.get('title', '')[:40]:40} | {status:12}")

def main():
    """Main CLI interface"""
    import os
    
    if len(sys.argv) < 2:
        print("Usage: hivectl <command> [args]")
        print()
        print("Commands:")
        print("  interrupt <task_id> [reason]  - Interrupt a running task")
        print("  resume <task_id>              - Resume an interrupted task")
        print("  attach <task_id>              - Attach to task's worktree")
        print("  nudge <task_id> <hint>        - Add hint for worker")
        print("  label <pr_url> [label]        - Add label to PR")
        print("  cleanup <task_id>             - Clean up worktree/branch")
        print("  status <task_id>              - Show task details")
        print("  list [status]                 - List tasks")
        sys.exit(1)
    
    ctl = HiveCtl()
    cmd = sys.argv[1]
    
    if cmd == "interrupt" and len(sys.argv) >= 3:
        task_id = sys.argv[2]
        reason = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "User interrupt"
        ctl.interrupt(task_id, reason)
        
    elif cmd == "resume" and len(sys.argv) >= 3:
        ctl.resume(sys.argv[2])
        
    elif cmd == "attach" and len(sys.argv) >= 3:
        ctl.attach(sys.argv[2])
        
    elif cmd == "nudge" and len(sys.argv) >= 4:
        task_id = sys.argv[2]
        hint = " ".join(sys.argv[3:])
        ctl.nudge(task_id, hint)
        
    elif cmd == "label" and len(sys.argv) >= 3:
        pr_url = sys.argv[2]
        label = sys.argv[3] if len(sys.argv) > 3 else "auto-merge-ok"
        ctl.label(pr_url, label)
        
    elif cmd == "cleanup" and len(sys.argv) >= 3:
        ctl.cleanup(sys.argv[2])
        
    elif cmd == "status" and len(sys.argv) >= 3:
        ctl.status(sys.argv[2])
        
    elif cmd == "list":
        status_filter = sys.argv[2] if len(sys.argv) > 2 else None
        ctl.list_tasks(status_filter)
        
    else:
        print(f"Unknown command or missing arguments: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
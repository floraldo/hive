#!/usr/bin/env python3
"""
Queen Orchestrator - Single-writer task state manager
Spawns one-shot workers, manages worktrees, and advances task state
"""

import json
import subprocess
import sys
import time
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from collections import defaultdict

class QueenOrchestrator:
    """Single orchestrator that manages all task state mutations"""
    
    def __init__(self):
        self.root = Path.cwd()
        self.hive_dir = self.root / "hive"
        self.tasks_dir = self.hive_dir / "tasks"
        self.results_dir = self.hive_dir / "results"
        self.events_file = self.get_events_file()
        self.worktrees_dir = self.root / ".worktrees"
        
        # Ensure directories exist
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        
        # Load subagent mapping
        self.subagents = self.load_subagents()
        
        # Track active spawns
        self.active_workers: Dict[str, subprocess.Popen] = {}
        
        # Status for display
        self.last_status_print = time.time()
        
        print(f"[{self.timestamp()}] Queen Orchestrator initialized")
        self.emit_event(type="queen_started")
    
    def timestamp(self) -> str:
        """Get current timestamp for logging"""
        return datetime.now().strftime("%H:%M:%S")
    
    def get_events_file(self) -> Path:
        """Get daily-rotated events file"""
        date_suffix = datetime.now().strftime("%Y%m%d")
        return self.hive_dir / "bus" / f"events_{date_suffix}.jsonl"
    
    def emit_event(self, **kwargs):
        """Emit event to the event bus"""
        try:
            kwargs.setdefault("ts", datetime.now(timezone.utc).isoformat())
            kwargs.setdefault("component", "queen")
            
            # Check rotation
            current_file = self.get_events_file()
            if current_file != self.events_file:
                self.events_file = current_file
            
            self.events_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(kwargs) + "\n")
                f.flush()
        except Exception as e:
            print(f"[{self.timestamp()}] Failed to emit event: {e}")
    
    def load_subagents(self) -> Dict[str, Any]:
        """Load subagent mapping for inspector assignment"""
        subagents_file = self.root / "SUBAGENTS.json"
        if subagents_file.exists():
            try:
                with open(subagents_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def load_task_index(self) -> List[str]:
        """Load task queue order"""
        index_file = self.tasks_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r") as f:
                    data = json.load(f)
                    return data.get("queue", [])
            except:
                pass
        return []
    
    def save_task_index(self, queue: List[str]):
        """Save task queue order"""
        index_file = self.tasks_dir / "index.json"
        data = {
            "queue": queue,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        with open(index_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load individual task"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if task_file.exists():
            try:
                with open(task_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def save_task(self, task: Dict[str, Any]):
        """Save individual task (Queen is the only writer)"""
        task_id = task["id"]
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        task_file = self.tasks_dir / f"{task_id}.json"
        with open(task_file, "w") as f:
            json.dump(task, f, indent=2)
    
    def create_worktree(self, worker: str, task_id: str) -> Path:
        """Create isolated git worktree for task"""
        branch = f"agent/{worker}/{task_id}"
        worktree_path = self.worktrees_dir / worker / task_id
        
        try:
            # Fetch latest
            subprocess.run(["git", "fetch", "origin"], check=False, capture_output=True)
            
            # Remove worktree if it exists
            if worktree_path.exists():
                subprocess.run(["git", "worktree", "remove", str(worktree_path), "--force"], 
                             check=False, capture_output=True)
            
            # Create new branch from main
            subprocess.run(["git", "branch", "-f", branch, "origin/main"], 
                         check=False, capture_output=True)
            
            # Add worktree
            result = subprocess.run(
                ["git", "worktree", "add", "-B", branch, str(worktree_path), branch],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                print(f"[{self.timestamp()}] Created worktree: {worktree_path}")
                return worktree_path
            else:
                print(f"[{self.timestamp()}] Failed to create worktree: {result.stderr}")
                
        except Exception as e:
            print(f"[{self.timestamp()}] Worktree error: {e}")
        
        # Fallback to regular workspace
        return self.root / "workspaces" / worker
    
    def spawn_worker(self, task: Dict[str, Any], worker: str) -> Optional[subprocess.Popen]:
        """Spawn one-shot worker for task"""
        task_id = task["id"]
        run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-1"
        
        # Create worktree
        workspace = self.create_worktree(worker, task_id)
        
        # Build command
        cmd = [
            sys.executable,
            "cc_worker.py",
            worker,
            "--one-shot",  # New flag for single task execution
            "--task-id", task_id,
            "--run-id", run_id,
            "--workspace", str(workspace)
        ]
        
        try:
            # Spawn worker process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            print(f"[{self.timestamp()}] Spawned {worker} for {task_id} (PID: {process.pid})")
            self.emit_event(
                type="worker_spawned",
                worker=worker,
                task_id=task_id,
                run_id=run_id,
                pid=process.pid,
                workspace=str(workspace)
            )
            
            return process
            
        except Exception as e:
            print(f"[{self.timestamp()}] Failed to spawn worker: {e}")
            return None
    
    def check_worker_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Check for worker results"""
        results_dir = self.results_dir / task_id
        if not results_dir.exists():
            return None
        
        # Get latest result file
        result_files = sorted(results_dir.glob("*.json"))
        if not result_files:
            return None
        
        latest = result_files[-1]
        try:
            with open(latest, "r") as f:
                return json.load(f)
        except:
            return None
    
    def advance_task_state(self, task: Dict[str, Any], result: Dict[str, Any]):
        """Advance task state based on worker result"""
        task_id = task["id"]
        next_state = result.get("next_state", "failed")
        
        # Normalize state
        state_map = {
            "success": "completed",
            "done": "completed",
            "error": "failed",
            "fail": "failed"
        }
        next_state = state_map.get(next_state, next_state)
        
        # Update task
        task["status"] = next_state
        task["result"] = result
        
        if next_state == "completed":
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
        elif next_state == "pr_open":
            task["pr"] = result.get("pr", "")
            task["pr_opened_at"] = datetime.now(timezone.utc).isoformat()
        elif next_state == "failed":
            task["failed_at"] = datetime.now(timezone.utc).isoformat()
            task["failure_reason"] = result.get("notes", "Unknown")
        
        self.save_task(task)
        
        self.emit_event(
            type=f"task_{next_state}",
            task_id=task_id,
            notes=result.get("notes", ""),
            pr=result.get("pr", "")
        )
        
        # Handle failure - create inspector task if needed
        if next_state in ["failed", "blocked"]:
            self.create_inspector_task(task, result)
    
    def create_inspector_task(self, failed_task: Dict[str, Any], result: Dict[str, Any]):
        """Create inspector task for failed work"""
        # Determine inspector type
        tags = failed_task.get("tags", [])
        inspector = None
        
        for tag in tags:
            tag_lower = tag.lower()
            if "backend" in tag_lower or "python" in tag_lower:
                inspector = "backend-debugger"
                break
            elif "frontend" in tag_lower or "react" in tag_lower:
                inspector = "ui-troubleshooter"
                break
            elif "docker" in tag_lower or "infra" in tag_lower:
                inspector = "infra-doctor"
                break
        
        if not inspector:
            return
        
        # Create fix task
        fix_task = {
            "id": f"fix_{failed_task['id']}",
            "title": f"Fix: {failed_task['title']}",
            "description": f"Debug and fix failure: {result.get('notes', 'Unknown error')}",
            "tags": failed_task.get("tags", []) + ["inspector", inspector],
            "status": "queued",
            "priority": "high",
            "parent_task": failed_task["id"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        self.save_task(fix_task)
        
        # Add to queue
        queue = self.load_task_index()
        queue.insert(0, fix_task["id"])  # High priority
        self.save_task_index(queue)
        
        print(f"[{self.timestamp()}] Created inspector task: {fix_task['id']}")
        self.emit_event(
            type="inspector_task_created",
            task_id=fix_task["id"],
            parent_task=failed_task["id"],
            inspector=inspector
        )
    
    def assign_task(self, task: Dict[str, Any]) -> Optional[str]:
        """Determine which worker should handle task"""
        tags = set(tag.lower() for tag in task.get("tags", []))
        
        # Check inspector tasks first
        if "inspector" in tags:
            # Inspector tasks handled by specialized agents
            for tag in tags:
                if tag in self.subagents:
                    return tag
        
        # Regular task assignment
        if tags & {"backend", "python", "api", "flask", "fastapi"}:
            return "backend"
        elif tags & {"frontend", "react", "ui", "javascript"}:
            return "frontend"
        elif tags & {"docker", "infra", "deployment", "kubernetes"}:
            return "infra"
        elif tags & {"planning", "architecture", "coordination"}:
            return "queen"
        
        return None
    
    def process_queue(self):
        """Process task queue and spawn workers"""
        queue = self.load_task_index()
        
        for task_id in queue[:]:  # Copy to allow modification
            # Skip if already has active worker
            if task_id in self.active_workers:
                continue
            
            task = self.load_task(task_id)
            if not task:
                queue.remove(task_id)
                continue
            
            # Skip non-queued tasks
            if task.get("status") != "queued":
                continue
            
            # Assign worker
            worker = self.assign_task(task)
            if not worker:
                print(f"[{self.timestamp()}] No worker available for {task_id}")
                continue
            
            # Update task status
            task["status"] = "assigned"
            task["assignee"] = worker
            task["assigned_at"] = datetime.now(timezone.utc).isoformat()
            self.save_task(task)
            
            # Spawn worker
            process = self.spawn_worker(task, worker)
            if process:
                self.active_workers[task_id] = process
                
                # Update to in_progress
                task["status"] = "in_progress"
                task["started_at"] = datetime.now(timezone.utc).isoformat()
                self.save_task(task)
        
        # Save updated queue
        self.save_task_index(queue)
    
    def monitor_workers(self):
        """Monitor active workers and collect results"""
        completed = []
        
        for task_id, process in list(self.active_workers.items()):
            # Check if process is still running
            poll = process.poll()
            
            if poll is not None:
                # Worker finished
                print(f"[{self.timestamp()}] Worker for {task_id} finished (exit: {poll})")
                
                # Check for results
                result = self.check_worker_results(task_id)
                if result:
                    task = self.load_task(task_id)
                    if task:
                        self.advance_task_state(task, result)
                
                completed.append(task_id)
        
        # Remove completed workers
        for task_id in completed:
            del self.active_workers[task_id]
    
    def print_status(self):
        """Print status table every 5-10 seconds"""
        now = time.time()
        if now - self.last_status_print < 5:
            return
        
        self.last_status_print = now
        
        # Gather stats
        all_tasks = list(self.tasks_dir.glob("*.json"))
        stats = defaultdict(int)
        
        for task_file in all_tasks:
            try:
                with open(task_file, "r") as f:
                    task = json.load(f)
                    stats[task.get("status", "unknown")] += 1
            except:
                pass
        
        # Print table
        print(f"\n[{self.timestamp()}] QUEEN STATUS")
        print("-" * 50)
        print(f"Active Workers: {len(self.active_workers)}")
        print(f"Queued: {stats['queued']:3} | Assigned: {stats['assigned']:3} | "
              f"In Progress: {stats['in_progress']:3} | Completed: {stats['completed']:3} | "
              f"Failed: {stats['failed']:3}")
        
        if self.active_workers:
            print("\nActive Tasks:")
            for task_id in list(self.active_workers.keys())[:5]:
                print(f"  - {task_id}")
        print()
    
    def run_forever(self):
        """Main orchestration loop"""
        print(f"[{self.timestamp()}] Queen Orchestrator starting...")
        print("="*50)
        
        try:
            while True:
                # Process queue
                self.process_queue()
                
                # Monitor workers
                self.monitor_workers()
                
                # Print status
                self.print_status()
                
                # Brief sleep
                time.sleep(2)
                
        except KeyboardInterrupt:
            print(f"\n[{self.timestamp()}] Queen shutting down...")
            
            # Terminate active workers
            for task_id, process in self.active_workers.items():
                print(f"[{self.timestamp()}] Terminating worker for {task_id}")
                process.terminate()
            
            # Wait for cleanup
            time.sleep(1)
            
            self.emit_event(type="queen_stopped")
            print(f"[{self.timestamp()}] Queen stopped")

def main():
    """Main entry point"""
    queen = QueenOrchestrator()
    queen.run_forever()

if __name__ == "__main__":
    main()
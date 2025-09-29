#!/usr/bin/env python3
"""
Queen Orchestrator - Epoch-based single-writer with interrupt/resume
Spawns one-shot workers in phases, manages worktrees, enables live steering
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Phase(Enum):
    """Task execution phases for epochs"""

    PLAN = "plan"
    APPLY = "apply"
    TEST = "test"


class QueenOrchestrator:
    """Epoch-based orchestrator with interrupt/resume capability"""

    def __init__(self, fresh_env: bool = False):
        self.root = Path.cwd()
        self.hive_dir = self.root / "hive"
        self.tasks_dir = self.hive_dir / "tasks"
        self.results_dir = self.hive_dir / "results"
        self.operator_dir = self.hive_dir / "operator"
        self.hints_dir = self.operator_dir / "hints"
        self.interrupts_dir = self.operator_dir / "interrupts"
        self.events_file = self.get_events_file()
        self.worktrees_dir = self.root / ".worktrees"

        # Fresh environment mode
        self.fresh_env = fresh_env
        if self.fresh_env:
            self.clean_fresh_environment()

        # Streaming and retry configuration
        self.max_retries = 3
        self.streaming_buffers = {}  # task_id -> output buffer
        self.retry_counts = {}  # task_id -> attempt count
        self.learning_patterns = []  # Store failure patterns for learning

        # Ensure directories exist
        for d in [self.tasks_dir, self.results_dir, self.hints_dir, self.interrupts_dir, self.worktrees_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Load subagents
        self.subagents = self.load_subagents()

        # Track active spawns with metadata (task_id -> {process, run_id, phase})
        self.active_workers: Dict[str, Dict[str, Any]] = {}

        # Concurrency limits
        self.max_parallel = 4
        self.max_parallel_per_role = {"backend": 2, "frontend": 2, "infra": 1}

        # Recursion guard for fix_* tasks
        self.max_fix_depth = int(os.getenv("HIVE_MAX_FIX_DEPTH", "1"))

        # Round-robin tracking
        self.last_assigned_worker = None
        self.worker_rotation = ["backend", "frontend", "infra"]

        # Status display
        self.last_status_print = time.time()

        print(f"[{self.timestamp()}] Queen Orchestrator initialized (epoch-based)")
        self.emit_event(type="queen_started", mode="epoch-based")

    def timestamp(self) -> str:
        """Current timestamp for logging"""
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
        """Load subagent inspector mapping"""
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
        data = {"queue": queue, "updated_at": datetime.now(timezone.utc).isoformat()}
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

    def slugify(self, text: str) -> str:
        """Convert text to branch-safe format"""
        # Replace non-alphanumeric with hyphens
        text = re.sub(r"[^\w\s-]", "", text.lower())
        text = re.sub(r"[-\s]+", "-", text)
        return text[:50]  # Limit length

    def create_worktree(self, worker: str, task_id: str) -> Optional[Path]:
        """Create isolated git worktree for task"""
        safe_task_id = self.slugify(task_id)
        branch = f"agent/{worker}/{safe_task_id}"
        worktree_path = self.worktrees_dir / worker / safe_task_id

        # Get base branch from environment or use default
        base_ref = os.environ.get("HIVE_GIT_BASE", "origin/main")

        try:
            # Fetch latest
            subprocess.run(["git", "fetch", "origin"], check=False, capture_output=True)

            # Clean up existing worktree if present
            if worktree_path.exists():
                subprocess.run(
                    ["git", "worktree", "remove", str(worktree_path), "--force"], check=False, capture_output=True
                )

            # Create branch from base ref
            subprocess.run(["git", "branch", "-f", branch, base_ref], check=False, capture_output=True)

            # Add worktree
            result = subprocess.run(
                ["git", "worktree", "add", "-B", branch, str(worktree_path), branch], capture_output=True, text=True
            )

            if result.returncode == 0:
                print(f"[{self.timestamp()}] Created worktree: {worktree_path}")
                return worktree_path
            else:
                print(f"[{self.timestamp()}] Worktree failed: {result.stderr}")

        except Exception as e:
            print(f"[{self.timestamp()}] Worktree error: {e}")

        # Fallback
        fallback = self.root / ".worktrees" / worker
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def create_fresh_workspace(self, worker: str, task_id: str) -> Path:
        """Create fresh isolated workspace for testing (no git history)"""
        safe_task_id = self.slugify(task_id)
        workspace_path = self.worktrees_dir / "fresh" / worker / safe_task_id

        # Clean existing workspace
        if workspace_path.exists():
            import shutil

            shutil.rmtree(workspace_path)

        # Create fresh directory
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Add basic .gitignore for cleanliness
        gitignore_content = """# Fresh workspace - auto-generated
__pycache__/
*.pyc
*.pyo
.DS_Store
node_modules/
*.log
.env
"""
        gitignore_path = workspace_path / ".gitignore"
        with open(gitignore_path, "w") as f:
            f.write(gitignore_content)

        # Add worker-specific template files
        self.setup_fresh_template(workspace_path, worker)

        print(f"[{self.timestamp()}] Created fresh workspace: {workspace_path}")
        return workspace_path

    def setup_fresh_template(self, workspace_path: Path, worker: str):
        """Setup basic template files for fresh workspace"""
        if worker == "backend":
            # Create minimal Python structure
            readme_content = """# Backend Worker Test Environment
Fresh isolated workspace for Python development.

## Files created by worker will appear here.
"""

        elif worker == "frontend":
            # Create minimal frontend structure
            readme_content = """# Frontend Worker Test Environment
Fresh isolated workspace for web development.

## Files created by worker will appear here.
"""

        elif worker == "infra":
            # Create minimal infrastructure structure
            readme_content = """# Infrastructure Worker Test Environment
Fresh isolated workspace for Docker/K8s development.

## Files created by worker will appear here.
"""
        else:
            readme_content = f"""# {worker.title()} Worker Test Environment
Fresh isolated workspace for development.

## Files created by worker will appear here.
"""

        readme_path = workspace_path / "README.md"
        with open(readme_path, "w") as f:
            f.write(readme_content)

    def check_interrupt(self, task_id: str) -> Optional[str]:
        """Check if task has been interrupted"""
        interrupt_file = self.interrupts_dir / f"{task_id}.json"
        if interrupt_file.exists():
            try:
                with open(interrupt_file, "r") as f:
                    data = json.load(f)
                    return data.get("reason", "User interrupt")
            except:
                pass
        return None

    def check_hint(self, task_id: str) -> Optional[str]:
        """Check for operator hints"""
        hint_file = self.hints_dir / f"{task_id}.md"
        if hint_file.exists():
            try:
                with open(hint_file, "r") as f:
                    return f.read()
            except:
                pass
        return None

    def clean_fresh_environment(self):
        """Clean all state for fresh environment testing"""
        print(f"[{self.timestamp()}] Cleaning fresh environment...")

        # 1. Reset all task statuses to queued
        for task_file in self.tasks_dir.glob("*.json"):
            if task_file.name == "index.json":
                continue

            try:
                with open(task_file, "r") as f:
                    task = json.load(f)

                # Reset task state for fresh start
                if task.get("status") != "queued":
                    task["status"] = "queued"
                    task["current_phase"] = "plan"

                    # Remove assignment details
                    for key in ["assignee", "assigned_at", "started_at", "worktree", "workspace_type"]:
                        if key in task:
                            del task[key]

                    task["updated_at"] = datetime.now(timezone.utc).isoformat()

                    with open(task_file, "w") as f:
                        json.dump(task, f, indent=2)

                    print(f"[{self.timestamp()}] Reset task: {task['id']}")

            except Exception as e:
                print(f"[{self.timestamp()}] Error resetting task {task_file.name}: {e}")

        # 2. Clear all results
        if self.results_dir.exists():
            for result_file in self.results_dir.rglob("*"):
                if result_file.is_file():
                    try:
                        result_file.unlink()
                    except Exception as e:
                        print(f"[{self.timestamp()}] Error removing result {result_file}: {e}")

        # 3. Clear fresh worktrees
        fresh_worktrees = self.worktrees_dir / "fresh"
        if fresh_worktrees.exists():
            import shutil

            try:
                shutil.rmtree(fresh_worktrees)
                print(f"[{self.timestamp()}] Cleared fresh worktrees")
            except Exception as e:
                print(f"[{self.timestamp()}] Error clearing fresh worktrees: {e}")

        # 4. Clear events (optional - keep for debugging if needed)
        # Keeping events for now to track Queen behavior

        print(f"[{self.timestamp()}] Fresh environment ready")

    def determine_next_phase(self, task: Dict[str, Any], result: Dict[str, Any]) -> Optional[Phase]:
        """Determine next phase based on current state and result"""
        current_phase = task.get("current_phase")
        status = result.get("status", "failed")

        if status == "failed" or status == "blocked":
            return None  # No next phase on failure

        if current_phase == Phase.PLAN.value:
            return Phase.APPLY
        elif current_phase == Phase.APPLY.value:
            return Phase.TEST
        else:
            return None  # Completed all phases

    def spawn_worker(self, task: Dict[str, Any], worker: str, phase: Phase) -> Optional[Tuple[subprocess.Popen, str]]:
        """Spawn one-shot worker for specific phase, returns (process, run_id)"""
        task_id = task["id"]
        run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{phase.value}"

        # Get or create workspace (fresh or git worktree)
        if not task.get("worktree"):
            if self.fresh_env:
                worktree = self.create_fresh_workspace(worker, task_id)
                task["worktree"] = str(worktree)
                task["workspace_type"] = "fresh"
            else:
                worktree = self.create_worktree(worker, task_id)
                task["worktree"] = str(worktree)
                task["branch"] = f"agent/{worker}/{self.slugify(task_id)}"
                task["workspace_type"] = "git_worktree"
            self.save_task(task)
        else:
            worktree = Path(task["worktree"])

        # Check for hints
        hint = self.check_hint(task_id)

        # Build command
        cmd = [
            sys.executable,
            "cc_worker.py",
            worker,
            "--one-shot",
            "--task-id",
            task_id,
            "--run-id",
            run_id,
            "--workspace",
            str(worktree),
            "--phase",
            phase.value,
        ]

        if hint:
            # Save hint to file for worker to read
            hint_path = worktree / ".hint.md"
            with open(hint_path, "w") as f:
                f.write(hint)

        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

            print(f"[{self.timestamp()}] Spawned {worker} for {task_id} phase:{phase.value} (PID: {process.pid})")

            self.emit_event(
                type="spawn",
                task_id=task_id,
                run_id=run_id,
                phase=phase.value,
                worker=worker,
                branch=task.get("branch", ""),
                workspace=str(worktree),
                pid=process.pid,
            )

            return process, run_id

        except Exception as e:
            print(f"[{self.timestamp()}] Spawn failed: {e}")
            return None

    def check_worker_result(self, task_id: str, run_id: str = None) -> Optional[Dict[str, Any]]:
        """Check for specific worker result by run_id, or latest if not specified"""
        results_dir = self.results_dir / task_id
        if not results_dir.exists():
            return None

        if run_id:
            # Read specific run_id result
            result_file = results_dir / f"{run_id}.json"
            if result_file.exists():
                try:
                    with open(result_file, "r") as f:
                        return json.load(f)
                except:
                    return None
        else:
            # Fallback to latest result (for backward compatibility)
            result_files = sorted(results_dir.glob("*.json"))
            if not result_files:
                return None

            try:
                with open(result_files[-1], "r") as f:
                    return json.load(f)
            except:
                return None

        return None

    def advance_task_state(self, task: Dict[str, Any], result: Dict[str, Any], phase: Phase):
        """Advance task state based on phase result"""
        task_id = task["id"]
        next_state = result.get("next_state", "failed")

        # Check if we should continue to next phase
        next_phase = self.determine_next_phase(task, result)

        if next_phase:
            # Continue to next phase
            task["current_phase"] = next_phase.value
            task["status"] = "in_progress"
            self.save_task(task)

            print(f"[{self.timestamp()}] Task {task_id} advancing to phase: {next_phase.value}")
            self.emit_event(type="phase_advance", task_id=task_id, from_phase=phase.value, to_phase=next_phase.value)
        else:
            # Task complete or failed
            if next_state in ["completed", "pr_open", "done"]:
                task["status"] = "completed"
                task["completed_at"] = datetime.now(timezone.utc).isoformat()

                # Check if we should open PR
                if phase == Phase.TEST and result.get("status") == "success":
                    pr_url = self.create_pr(task, result)
                    if pr_url:
                        task["pr"] = pr_url
                        task["status"] = "pr_open"

                        # Add auto-merge label if appropriate
                        if self.should_auto_merge(task, result):
                            # Wait for checks to pass before adding label
                            if self.wait_for_checks_green(pr_url):
                                self.add_auto_merge_label(pr_url)
                            else:
                                print(f"[{self.timestamp()}] Skipping auto-merge label - checks not green")

            elif next_state in ["failed", "blocked"]:
                # Check if we should retry the task
                if self.should_retry_task(task, result):
                    self.learn_from_failure(task, result)
                    self.retry_task(task)
                    return  # Don't mark as failed, retry instead

                # Task has failed after all retries
                task["status"] = next_state
                task["failed_at"] = datetime.now(timezone.utc).isoformat()
                task["failure_reason"] = result.get("notes", "Unknown")

                # Learn from final failure
                self.learn_from_failure(task, result)

                # Create inspector task
                self.create_inspector_task(task, result)

            self.save_task(task)

            self.emit_event(
                type=f"task_{task['status']}",
                task_id=task_id,
                phase=phase.value,
                notes=result.get("notes", ""),
                pr=task.get("pr", ""),
            )

    def should_auto_merge(self, task: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """Determine if task qualifies for auto-merge"""
        # Check risk level
        if task.get("risk", "low") == "high":
            return False

        # Check diff size
        diff_stats = result.get("diff_stats", {})
        if diff_stats.get("files_changed", 0) > 10 or diff_stats.get("insertions", 0) > 200:
            return False

        # Check if tests passed
        if result.get("tests_pass", False):
            return True

        return False

    def create_pr(self, task: Dict[str, Any], result: Dict[str, Any]) -> Optional[str]:
        """Create GitHub PR for completed task"""
        # Allow disabling PR creation for testing
        if os.environ.get("HIVE_DISABLE_PR") == "1":
            print(f"[{self.timestamp()}] PR creation disabled (HIVE_DISABLE_PR=1)")
            return None

        try:
            branch = task.get("branch")
            if not branch:
                return None

            # Push branch
            worktree = Path(task.get("worktree", ""))
            if worktree.exists():
                subprocess.run(["git", "push", "-u", "origin", branch], cwd=worktree, check=True, capture_output=True)

            # Create PR
            title = f"[{task['id']}] {task.get('title', 'Task')}"
            body = f"""## Summary
{result.get('notes', 'Task completed')}

## Task ID
{task['id']}

## Test Results
{result.get('test_summary', 'Tests passed')}

---
Generated by Hive Fleet Command
"""

            pr_result = subprocess.run(
                ["gh", "pr", "create", "--title", title, "--body", body, "--base", "main", "--head", branch],
                capture_output=True,
                text=True,
            )

            if pr_result.returncode == 0:
                pr_url = pr_result.stdout.strip()
                print(f"[{self.timestamp()}] Created PR: {pr_url}")
                return pr_url

        except Exception as e:
            print(f"[{self.timestamp()}] PR creation failed: {e}")

        return None

    def wait_for_checks_green(self, pr_url: str, timeout: int = 600) -> bool:
        """Wait for PR checks to pass before adding auto-merge label"""
        import time

        start = time.time()

        print(f"[{self.timestamp()}] Waiting for PR checks to pass: {pr_url}")

        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    ["gh", "pr", "checks", pr_url, "--json", "status,conclusion"], capture_output=True, text=True
                )

                if result.returncode == 0:
                    output = result.stdout
                    # Check if all checks are completed and successful
                    if '"status":"COMPLETED"' in output:
                        if '"conclusion":"SUCCESS"' in output.upper():
                            print(f"[{self.timestamp()}] PR checks passed for {pr_url}")
                            return True
                        elif '"conclusion":"FAILURE"' in output.upper():
                            print(f"[{self.timestamp()}] PR checks failed for {pr_url}")
                            return False
            except Exception as e:
                print(f"[{self.timestamp()}] Error checking PR status: {e}")

            # Wait before next check
            time.sleep(10)

        print(f"[{self.timestamp()}] Timeout waiting for PR checks: {pr_url}")
        return False

    def add_auto_merge_label(self, pr_url: str):
        """Add auto-merge label to PR"""
        try:
            subprocess.run(
                ["gh", "pr", "edit", pr_url, "--add-label", "auto-merge-ok"], check=True, capture_output=True
            )
            print(f"[{self.timestamp()}] Added auto-merge-ok label to {pr_url}")
        except:
            pass

    def create_inspector_task(self, failed_task: Dict[str, Any], result: Dict[str, Any]):
        """Create inspector task for failed work"""
        # Prevent infinite recursion - don't create inspectors for inspectors
        if failed_task["id"].startswith("fix_") or "inspector" in failed_task.get("tags", []):
            self.emit_event(type="inspector_skipped", task_id=failed_task["id"], reason="already_inspector")
            return

        # Don't create inspectors for environment/setup failures
        notes = (result.get("notes") or "").lower()
        env_signals = (
            "cli not available",
            "winerror 193",
            "file not found",
            "no such file or directory",
            "system cannot find the file",
        )
        if any(sig in notes for sig in env_signals):
            self.emit_event(type="inspector_skipped", task_id=failed_task["id"], reason="environment_failure")
            return

        tags = failed_task.get("tags", [])
        inspector = None

        # Match inspector based on tags
        for tag in tags:
            tag_lower = tag.lower()
            for inspector_id, config in self.subagents.items():
                if tag_lower in config.get("trigger", []):
                    inspector = inspector_id
                    break
            if inspector:
                break

        if not inspector:
            return

        fix_task = {
            "id": f"fix_{failed_task['id']}",
            "title": f"Fix: {failed_task['title']}",
            "description": f"Debug and fix: {result.get('notes', 'Unknown')}",
            "tags": failed_task.get("tags", []) + ["inspector", inspector],
            "status": "queued",
            "priority": "P1",
            "risk": "low",
            "parent_task": failed_task["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.save_task(fix_task)

        # Add to front of queue
        queue = self.load_task_index()
        queue.insert(0, fix_task["id"])
        self.save_task_index(queue)

        print(f"[{self.timestamp()}] Created inspector task: {fix_task['id']} ({inspector})")
        self.emit_event(
            type="inspector_task_created", task_id=fix_task["id"], parent_task=failed_task["id"], inspector=inspector
        )

    def assign_worker(self, task: Dict[str, Any]) -> Optional[str]:
        """Determine which worker should handle task"""
        tags = set(tag.lower() for tag in task.get("tags", []))

        # Check for inspector
        if "inspector" in tags:
            for tag in tags:
                if tag in self.subagents:
                    return "backend"  # Inspectors run as backend for now

        # Regular assignment
        if tags & {"backend", "python", "api", "flask", "fastapi"}:
            return "backend"
        elif tags & {"frontend", "react", "ui", "javascript"}:
            return "frontend"
        elif tags & {"docker", "infra", "deployment", "kubernetes"}:
            return "infra"

        return None

    def process_queue(self):
        """Process task queue with epoch-based execution"""
        queue = self.load_task_index()

        # Count active workers per role
        active_per_role = defaultdict(int)
        for task_id in self.active_workers:
            task = self.load_task(task_id)
            if task:
                worker = task.get("assignee", "unknown")
                active_per_role[worker] += 1

        # Check global limit
        if len(self.active_workers) >= self.max_parallel:
            return

        for task_id in queue[:]:
            if task_id in self.active_workers:
                continue

            task = self.load_task(task_id)
            if not task:
                queue.remove(task_id)
                continue

            # Check for stale in-progress tasks (30 minutes)
            if task.get("status") in ["assigned", "in_progress"]:
                started_at = task.get("started_at") or task.get("assigned_at")
                if started_at:
                    try:
                        start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                        age_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60
                        if age_minutes > 30:
                            print(f"[{self.timestamp()}] Task {task_id} stale after {age_minutes:.1f} minutes")
                            task["status"] = "failed"
                            task["failure_reason"] = f"Stale task - no completion after {age_minutes:.0f} minutes"
                            task["failed_at"] = datetime.now(timezone.utc).isoformat()
                            self.save_task(task)
                            self.emit_event(type="task_stale", task_id=task_id, age_minutes=age_minutes)
                            continue
                    except Exception as e:
                        print(f"[{self.timestamp()}] Error checking task age: {e}")

            # Recursion guard for fix_* tasks
            tid = task["id"]
            fix_depth = tid.count("fix_")
            if fix_depth > self.max_fix_depth:
                task["status"] = "blocked"
                task["failure_reason"] = f"recursion_guard: fix-depth>{self.max_fix_depth}"
                self.save_task(task)
                self.emit_event(type="recursion_guard", task_id=tid, depth=fix_depth)
                continue

            # Check for interrupt
            interrupt_reason = self.check_interrupt(task_id)
            if interrupt_reason:
                print(f"[{self.timestamp()}] Task {task_id} interrupted: {interrupt_reason}")
                task["status"] = "blocked"
                task["failure_reason"] = f"Interrupted: {interrupt_reason}"
                self.save_task(task)

                # Clean up interrupt file
                (self.interrupts_dir / f"{task_id}.json").unlink(missing_ok=True)
                continue

            if task.get("status") != "queued":
                continue

            # Assign worker
            worker = self.assign_worker(task)
            if not worker:
                continue

            # Check per-role limit
            if active_per_role[worker] >= self.max_parallel_per_role.get(worker, 1):
                continue

            # Start first phase - skip planning for test tasks, go directly to apply
            current_phase = Phase.APPLY if (task_id.endswith("_test") or task_id == "hello_hive") else Phase.PLAN
            task["status"] = "assigned"
            task["assignee"] = worker
            task["assigned_at"] = datetime.now(timezone.utc).isoformat()
            task["current_phase"] = current_phase.value
            self.save_task(task)

            # Spawn worker for first phase
            result = self.spawn_worker(task, worker, current_phase)
            if result:
                process, run_id = result
                self.active_workers[task_id] = {"process": process, "run_id": run_id, "phase": current_phase.value}
                task["status"] = "in_progress"
                task["started_at"] = datetime.now(timezone.utc).isoformat()
                self.save_task(task)
                print(f"[{self.timestamp()}] Successfully spawned {worker} for {task_id} (PID: {process.pid})")
            else:
                # Spawn failed - revert task to queued status
                print(f"[{self.timestamp()}] Failed to spawn {worker} for {task_id} - reverting to queued")
                task["status"] = "queued"
                # Remove assignment details to allow reassignment
                for key in ["assignee", "assigned_at", "current_phase"]:
                    if key in task:
                        del task[key]
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.save_task(task)

        self.save_task_index(queue)

    def recover_zombie_tasks(self):
        """Detect and recover tasks stuck in 'in_progress' state without active workers"""
        # Find all in_progress tasks
        for task_file in self.tasks_dir.glob("*.json"):
            if task_file.name == "index.json":
                continue

            try:
                with open(task_file, "r") as f:
                    task = json.load(f)

                task_id = task.get("id")
                status = task.get("status")

                # Check for zombie: in_progress but no active worker
                if status == "in_progress" and task_id not in self.active_workers:
                    started_at = task.get("started_at")
                    if started_at:
                        start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                        age_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60

                        # Only recover if task has been zombie for >5 minutes (prevent race conditions)
                        if age_minutes > 5:
                            print(
                                f"[{self.timestamp()}] Recovering zombie task: {task_id} (stale for {age_minutes:.1f} minutes)"
                            )

                            # Reset to queued for retry
                            task["status"] = "queued"
                            task["current_phase"] = "plan"

                            # Remove assignment details to allow reassignment
                            for key in ["assignee", "assigned_at", "started_at", "worktree", "workspace_type"]:
                                if key in task:
                                    del task[key]

                            task["updated_at"] = datetime.now(timezone.utc).isoformat()

                            with open(task_file, "w") as f:
                                json.dump(task, f, indent=2)

                            # Emit event for tracking
                            self.emit_event(type="zombie_task_recovered", task_id=task_id, age_minutes=age_minutes)

            except Exception as e:
                print(f"[{self.timestamp()}] Error checking zombie task {task_file.name}: {e}")

    def monitor_workers(self):
        """Monitor active workers and handle phase transitions"""
        # First, detect and recover zombie tasks
        self.recover_zombie_tasks()

        completed = []

        for task_id, metadata in list(self.active_workers.items()):
            process = metadata["process"]
            run_id = metadata["run_id"]
            poll = process.poll()

            if poll is not None:
                # Worker finished
                task = self.load_task(task_id)
                if not task:
                    completed.append(task_id)
                    continue

                current_phase = Phase(task.get("current_phase", Phase.PLAN.value))

                # Check if worker failed (non-zero exit code)
                if poll != 0:
                    print(f"[{self.timestamp()}] Worker failed for {task_id} (exit: {poll}) - reverting to queued")
                    # Revert task to queued status for retry
                    task["status"] = "queued"
                    # Remove assignment details to allow reassignment
                    if "assignee" in task:
                        del task["assignee"]
                    if "assigned_at" in task:
                        del task["assigned_at"]
                    if "worktree" in task:
                        del task["worktree"]
                    if "workspace_type" in task:
                        del task["workspace_type"]
                    if "started_at" in task:
                        del task["started_at"]
                    self.save_task(task)
                    completed.append(task_id)
                    continue

                # Check result with specific run_id
                result = self.check_worker_result(task_id, run_id)
                if result:
                    self.advance_task_state(task, result, current_phase)

                    # Check if we need to spawn next phase
                    task = self.load_task(task_id)  # Reload after update
                    if task and task.get("status") == "in_progress":
                        next_phase = Phase(task.get("current_phase"))
                        worker = task.get("assignee")

                        # Spawn next phase
                        spawn_result = self.spawn_worker(task, worker, next_phase)
                        if spawn_result:
                            new_process, new_run_id = spawn_result
                            self.active_workers[task_id] = {
                                "process": new_process,
                                "run_id": new_run_id,
                                "phase": next_phase.value,
                            }
                            continue

                completed.append(task_id)

        # Remove completed
        for task_id in completed:
            del self.active_workers[task_id]

        # Stream output for active workers
        self.stream_worker_output()

    def stream_worker_output(self):
        """Stream output from active workers for real-time monitoring"""
        for task_id, metadata in self.active_workers.items():
            process = metadata["process"]

            # Initialize buffer for new tasks
            if task_id not in self.streaming_buffers:
                self.streaming_buffers[task_id] = ""

            # Read available output without blocking
            try:
                import select

                if hasattr(select, "select"):  # Unix-like systems
                    if select.select([process.stdout], [], [], 0)[0]:
                        output = process.stdout.read(1024).decode("utf-8", errors="replace")
                        if output:
                            self.streaming_buffers[task_id] += output
                            # Print new output with task prefix
                            for line in output.splitlines():
                                if line.strip():
                                    print(f"[{task_id}] {line}")
                else:
                    # Windows - use polling approach
                    import msvcrt

                    if process.stdout and hasattr(process.stdout, "peek"):
                        try:
                            output = process.stdout.read(1024)
                            if output:
                                decoded = output.decode("utf-8", errors="replace")
                                self.streaming_buffers[task_id] += decoded
                                for line in decoded.splitlines():
                                    if line.strip():
                                        print(f"[{task_id}] {line}")
                        except:
                            pass
            except Exception as e:
                pass  # Silently ignore streaming errors

    def should_retry_task(self, task: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """Determine if a failed task should be retried"""
        task_id = task["id"]

        # Don't retry inspector tasks
        if "inspector" in task.get("tags", []):
            return False

        # Check retry count
        current_retries = self.retry_counts.get(task_id, 0)
        if current_retries >= self.max_retries:
            return False

        # Don't retry certain failure types
        failure_reason = result.get("notes", "").lower()
        no_retry_patterns = ["compilation error", "syntax error", "permission denied", "file not found"]

        if any(pattern in failure_reason for pattern in no_retry_patterns):
            return False

        return True

    def learn_from_failure(self, task: Dict[str, Any], result: Dict[str, Any]):
        """Learn patterns from task failures to improve future success"""
        failure_pattern = {
            "task_type": task.get("tags", []),
            "worker": task.get("assignee"),
            "failure_reason": result.get("notes", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.learning_patterns.append(failure_pattern)

        # Keep only recent patterns (last 100)
        if len(self.learning_patterns) > 100:
            self.learning_patterns = self.learning_patterns[-100:]

        # Analyze patterns for common issues
        similar_failures = [p for p in self.learning_patterns if p["worker"] == failure_pattern["worker"]]

        if len(similar_failures) >= 3:
            print(f"[{self.timestamp()}] Learning: Detected pattern in {failure_pattern['worker']} failures")
            self.emit_event(
                type="learning_pattern_detected",
                worker=failure_pattern["worker"],
                pattern_count=len(similar_failures),
                recent_failure=failure_pattern["failure_reason"],
            )

    def retry_task(self, task: Dict[str, Any]):
        """Retry a failed task with exponential backoff"""
        task_id = task["id"]

        # Increment retry count
        self.retry_counts[task_id] = self.retry_counts.get(task_id, 0) + 1
        retry_count = self.retry_counts[task_id]

        # Reset task status for retry
        task["status"] = "queued"
        task["current_phase"] = Phase.PLAN.value
        task["retry_count"] = retry_count
        task["retried_at"] = datetime.now(timezone.utc).isoformat()

        # Clear previous failure info
        task.pop("failed_at", None)
        task.pop("failure_reason", None)

        self.save_task(task)

        print(f"[{self.timestamp()}] Retrying task {task_id} (attempt {retry_count}/{self.max_retries})")
        self.emit_event(type="task_retry", task_id=task_id, retry_count=retry_count, max_retries=self.max_retries)

    def print_status(self):
        """Print periodic status update"""
        now = time.time()
        if now - self.last_status_print < 5:
            return

        self.last_status_print = now

        # Gather stats
        all_tasks = list(self.tasks_dir.glob("*.json"))
        stats = defaultdict(int)

        for task_file in all_tasks:
            if task_file.stem == "index":
                continue
            try:
                with open(task_file, "r") as f:
                    task = json.load(f)
                    stats[task.get("status", "unknown")] += 1
            except:
                pass

        # Single-line status update - only show active count
        print(
            f"[{self.timestamp()}] Active: {len(self.active_workers)} | "
            f"Q: {stats['queued']} | A: {stats['assigned']} | "
            f"IP: {stats['in_progress']} | PR: {stats['pr_open']} | "
            f"C: {stats['completed']} | F: {stats['failed']}"
        )

    def run_forever(self):
        """Main orchestration loop"""
        print(f"[{self.timestamp()}] Queen Orchestrator v2 starting...")
        print("Epoch-based execution with interrupt/resume capability")
        print("=" * 50)

        try:
            while True:
                self.process_queue()
                self.monitor_workers()
                self.print_status()
                time.sleep(2)

        except KeyboardInterrupt:
            print(f"\n[{self.timestamp()}] Queen shutting down...")

            # Terminate workers
            for task_id, process in self.active_workers.items():
                print(f"[{self.timestamp()}] Terminating {task_id}")
                process.terminate()

            time.sleep(1)
            self.emit_event(type="queen_stopped")
            print(f"[{self.timestamp()}] Queen stopped")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Queen Orchestrator - Multi-Agent Task Manager")
    parser.add_argument(
        "--fresh-env", action="store_true", help="Use fresh isolated environments instead of git worktrees"
    )
    parser.add_argument("--worktree-mode", action="store_true", help="Use full git worktrees with branches (default)")

    args = parser.parse_args()

    # Determine environment mode
    fresh_env = args.fresh_env
    if args.worktree_mode and args.fresh_env:
        print("Error: Cannot use both --fresh-env and --worktree-mode")
        sys.exit(1)

    print(f"Starting Queen Orchestrator in {'FRESH ENVIRONMENT' if fresh_env else 'WORKTREE'} mode")
    queen = QueenOrchestrator(fresh_env=fresh_env)
    queen.run_forever()


if __name__ == "__main__":
    main()

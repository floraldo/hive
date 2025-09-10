#!/usr/bin/env python3
"""
Claude Code Worker - Results-only mode
Workers write only results + events; Queen handles all state mutations
"""

import json
import subprocess
import sys
import time
import shutil
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

class CCWorker:
    """Simplified worker that only writes results and events"""
    
    def __init__(self, worker_id: str, task_id: str = None, run_id: str = None, workspace: str = None, phase: str = None):
        self.worker_id = worker_id
        self.task_id = task_id
        self.run_id = run_id or self.generate_run_id(task_id)
        self.phase = phase or "apply"  # Default to apply phase
        self.root = Path.cwd()
        self.hive_dir = self.root / "hive"
        self.results_dir = self.hive_dir / "results"
        self.tasks_dir = self.hive_dir / "tasks"
        self.operator_dir = self.hive_dir / "operator"
        self.hints_dir = self.operator_dir / "hints"
        self.events_file = self.get_events_file()
        
        # Workspace (worktree or regular)
        if workspace:
            self.workspace = Path(workspace)
        else:
            self.workspace = self.root / "workspaces" / worker_id
        
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Find claude command
        self.claude_cmd = self.find_claude_command()
        
        # Log startup
        self.print_status("INITIALIZED", f"Worker {worker_id} ready")
        if task_id:
            self.print_info(f"Task: {task_id}")
            self.print_info(f"Run ID: {run_id}")
            self.print_info(f"Phase: {self.phase}")
        self.print_info(f"Workspace: {self.workspace}")
        self.print_info(f"Claude: {self.claude_cmd if self.claude_cmd else 'SIMULATION MODE'}")
        
        # Emit startup event
        self.emit_event(type="worker_started", role=f"{worker_id}_developer")
    
    def generate_run_id(self, task_id: str) -> str:
        """Generate run ID for this execution"""
        if not task_id:
            return f"adhoc-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        return f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-1"
    
    def get_events_file(self) -> Path:
        """Get daily-rotated events file"""
        date_suffix = datetime.now().strftime("%Y%m%d")
        return self.hive_dir / "bus" / f"events_{date_suffix}.jsonl"
    
    def print_status(self, status: str, message: str):
        """Print formatted status message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        try:
            print(f"[{timestamp}] [{status}] {message}")
        except UnicodeEncodeError:
            safe_msg = message.encode('ascii', 'replace').decode('ascii')
            print(f"[{timestamp}] [{status}] {safe_msg}")
        sys.stdout.flush()
    
    def print_info(self, message: str):
        """Print info message"""
        try:
            print(f"         [INFO] {message}")
        except UnicodeEncodeError:
            safe_msg = message.encode('ascii', 'replace').decode('ascii')
            print(f"         [INFO] {safe_msg}")
        sys.stdout.flush()
    
    def print_error(self, message: str):
        """Print error message"""
        try:
            print(f"         [ERROR] {message}")
        except UnicodeEncodeError:
            safe_msg = message.encode('ascii', 'replace').decode('ascii')
            print(f"         [ERROR] {safe_msg}")
        sys.stdout.flush()
    
    def emit_event(self, **kwargs):
        """Emit event to the event bus"""
        try:
            kwargs.setdefault("ts", datetime.now(timezone.utc).isoformat())
            kwargs.setdefault("worker", self.worker_id)
            kwargs.setdefault("run_id", self.run_id)
            
            # Check rotation
            current_file = self.get_events_file()
            if current_file != self.events_file:
                self.events_file = current_file
            
            self.events_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(kwargs) + "\n")
                f.flush()
        except Exception as e:
            self.print_error(f"Failed to emit event: {e}")
    
    def save_result(self, task_id: str, result: Dict[str, Any]):
        """Save task result to results directory"""
        try:
            # Add metadata
            result["run_id"] = self.run_id
            result["worker"] = self.worker_id
            result["workspace"] = str(self.workspace)
            result["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # Determine branch and commit if in git
            try:
                branch_result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True
                )
                if branch_result.returncode == 0:
                    result["branch"] = branch_result.stdout.strip()
                
                commit_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True
                )
                if commit_result.returncode == 0:
                    result["commit_sha"] = commit_result.stdout.strip()[:8]
            except:
                pass
            
            # Save result file
            result_dir = self.results_dir / task_id
            result_dir.mkdir(parents=True, exist_ok=True)
            
            result_file = result_dir / f"{self.run_id}.json"
            with open(result_file, "w") as f:
                json.dump(result, f, indent=2)
            
            self.print_info(f"Saved result: {result_file}")
            
        except Exception as e:
            self.print_error(f"Failed to save result: {e}")
    
    def find_claude_command(self) -> Optional[str]:
        """Find the claude command"""
        # Check environment override
        if os.environ.get("CLAUDE_BIN"):
            return os.environ["CLAUDE_BIN"]
        
        # Check local files
        for claude_file in ["claude.bat", "claude.sh", "claude"]:
            local_claude = self.root / claude_file
            if local_claude.exists():
                return str(local_claude.resolve())
        
        # Windows: prefer .cmd/.bat launchers to avoid WinError 193
        if os.name == "nt":
            for name in ("claude.cmd", "claude.bat", "claude.exe", "claude.ps1"):
                cmd_path = shutil.which(name)
                if cmd_path:
                    return cmd_path
        
        # Check system PATH (unix or fallback)
        claude_cmd = shutil.which("claude")
        if claude_cmd:
            return claude_cmd
        
        return None
    
    def read_hints(self, task_id: str) -> Optional[str]:
        """Read operator hints for this task"""
        hint_file = self.hints_dir / f"{task_id}.md"
        if hint_file.exists():
            try:
                with open(hint_file, "r") as f:
                    return f.read()
            except:
                pass
        return None
    
    def get_git_diff_stats(self) -> Dict[str, Any]:
        """Get git diff statistics for changes"""
        stats = {
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
            "diff_summary": ""
        }
        
        try:
            # Get diff stats
            diff_result = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=self.workspace,
                capture_output=True,
                text=True
            )
            
            if diff_result.returncode == 0 and diff_result.stdout:
                lines = diff_result.stdout.strip().split("\n")
                if lines:
                    # Parse the summary line (e.g., "3 files changed, 42 insertions(+), 5 deletions(-)")
                    summary = lines[-1]
                    stats["diff_summary"] = summary
                    
                    # Extract numbers
                    import re
                    files_match = re.search(r'(\d+) files? changed', summary)
                    if files_match:
                        stats["files_changed"] = int(files_match.group(1))
                    
                    insertions_match = re.search(r'(\d+) insertions?\(\+\)', summary)
                    if insertions_match:
                        stats["insertions"] = int(insertions_match.group(1))
                    
                    deletions_match = re.search(r'(\d+) deletions?\(-\)', summary)
                    if deletions_match:
                        stats["deletions"] = int(deletions_match.group(1))
        except:
            pass
        
        return stats
    
    def verify_tests_pass(self) -> bool:
        """Verify that tests pass based on worker type"""
        test_cmd = None
        
        if self.worker_id == "backend":
            # Try pytest
            if (self.workspace / "pytest.ini").exists() or (self.workspace / "setup.cfg").exists():
                test_cmd = ["pytest", "-v"]
            elif (self.workspace / "tests").exists():
                test_cmd = ["python", "-m", "pytest", "tests", "-v"]
        
        elif self.worker_id == "frontend":
            # Try npm test or jest
            if (self.workspace / "package.json").exists():
                test_cmd = ["npm", "test"]
        
        elif self.worker_id == "infra":
            # Try docker or terraform validate
            if (self.workspace / "Dockerfile").exists():
                test_cmd = ["docker", "build", "--dry-run", "."]
        
        if not test_cmd:
            self.print_info("No test command determined for this worker type")
            return True  # Pass if no tests configured
        
        try:
            self.print_info(f"Running tests: {' '.join(test_cmd)}")
            test_result = subprocess.run(
                test_cmd,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for tests
            )
            
            if test_result.returncode == 0:
                self.print_status("TESTS PASSED", "All tests successful")
                return True
            else:
                self.print_error(f"Tests failed with exit code {test_result.returncode}")
                if test_result.stderr:
                    self.print_error(test_result.stderr[:500])
                return False
                
        except subprocess.TimeoutExpired:
            self.print_error("Test execution timeout (5 minutes)")
            return False
        except Exception as e:
            self.print_error(f"Failed to run tests: {e}")
            return False
    
    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load task from per-task file"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if task_file.exists():
            try:
                with open(task_file, "r") as f:
                    return json.load(f)
            except:
                pass
        
        # Fallback to old format
        old_tasks_file = self.hive_dir / "bus" / "tasks.json"
        if old_tasks_file.exists():
            try:
                with open(old_tasks_file, "r") as f:
                    data = json.load(f)
                    for task in data.get("tasks", []):
                        if task["id"] == task_id:
                            return task
            except:
                pass
        
        return None
    
    def create_prompt(self, task: Dict[str, Any]) -> str:
        """Create prompt with phase-specific instructions"""
        role = f"{self.worker_id}_developer"
        task_id = task.get("id", "unknown")
        title = task.get("title", "Task")
        description = task.get("description", "")
        acceptance = task.get("acceptance", task.get("acceptance_criteria", []))
        
        # Read any operator hints
        hints = self.read_hints(task_id)
        hint_section = ""
        if hints:
            hint_section = f"\n\nOPERATOR HINTS:\n{hints}\n"
        
        # Phase-specific instructions
        phase_instructions = ""
        if self.phase == "plan":
            phase_instructions = """\nPHASE: PLANNING
You are in the PLANNING phase. Focus on:
1. Understanding the requirements deeply
2. Identifying technical approach and architecture
3. Breaking down into implementation steps
4. Identifying potential risks or blockers
5. DO NOT write actual code yet - just plan
"""
        elif self.phase == "test":
            phase_instructions = """\nPHASE: TESTING
You are in the TESTING phase. Focus on:
1. Writing comprehensive test cases
2. Running all existing tests
3. Validating acceptance criteria
4. Checking edge cases
5. Ensuring code quality and coverage
"""
        else:  # apply phase (default)
            phase_instructions = """\nPHASE: APPLY
You are in the APPLY phase. Focus on:
1. Implementing the actual solution
2. Writing minimal tests for new code
3. Ensuring tests pass
4. Making focused, minimal changes
"""
        
        prompt = f"""You are a {role} working on the Hive system.

TASK: {title} (ID: {task_id})
DESCRIPTION: {description}
{phase_instructions}
ACCEPTANCE CRITERIA:
{chr(10).join('- ' + c for c in acceptance)}
{hint_section}
You MUST:
1. Follow the phase-specific focus above
2. Create actual working code/configuration (in APPLY phase)
3. Write or update tests as appropriate for the phase
4. Run tests locally to verify they pass
5. If tests fail, attempt ONE minimal fix
6. If still failing after one fix, stop and report blocked
7. Keep changes focused and minimal
8. Commit with message including task ID: {task_id}

IMPORTANT: At the very end, print EXACTLY ONE LINE prefixed by 'FINAL_JSON: ':
FINAL_JSON: {{"status":"success|failed|blocked","notes":"<brief summary>","pr":"<PR URL or empty>","next_state":"completed|testing|reviewing|pr_open|failed|blocked"}}
"""
        return prompt
    
    def parse_final_json(self, lines: List[str]) -> Dict[str, Any]:
        """Parse FINAL_JSON marker output"""
        for line in reversed(lines[-200:] if len(lines) > 200 else lines):
            s = line.strip()
            if s.startswith("FINAL_JSON:"):
                try:
                    return json.loads(s.split("FINAL_JSON:", 1)[1].strip())
                except:
                    self.print_error(f"Failed to parse: {s}")
        return {}
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with Claude"""
        self.print_status("EXECUTING", f"Task: {task['title']}")
        
        if not self.claude_cmd:
            # Simulation mode
            self.print_info("Simulating execution (Claude not found)")
            time.sleep(2)
            return {
                "status": "blocked",
                "notes": "Claude CLI not available",
                "next_state": "blocked"
            }
        
        # Build command
        prompt = self.create_prompt(task)
        cmd = [
            self.claude_cmd,
            "--output-format", "stream-json",
            "--add-dir", str(self.workspace),
            "-p", prompt
        ]
        
        # Add role-specific tool restrictions
        if self.worker_id == "backend":
            cmd.extend(["--allowedTools", 
                       "Bash(python,pip,pytest,git,cat,ls,mkdir,echo),Read(*),Write(*),Edit(*),MultiEdit(*)"])
        elif self.worker_id == "frontend":
            cmd.extend(["--allowedTools",
                       "Bash(npm,node,jest,git,cat,ls,mkdir,echo),Read(*),Write(*),Edit(*),MultiEdit(*)"])
        elif self.worker_id == "infra":
            cmd.extend(["--allowedTools",
                       "Bash(docker,kubectl,helm,git,cat,ls,mkdir,echo,sh),Read(*),Write(*),Edit(*),MultiEdit(*)"])
        
        self.print_status("RUNNING", "Claude is working...")
        self.print_info(f"Workspace: {self.workspace}")
        
        # Execute
        lines = []
        start_time = datetime.now(timezone.utc)
        
        try:
            with subprocess.Popen(
                cmd,
                cwd=str(self.workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            ) as process:
                
                for line in process.stdout:
                    lines.append(line)
                    # Echo key lines
                    if any(x in line for x in ["FINAL_JSON:", "ERROR", "Failed"]):
                        self.print_info(line.strip()[:150])
                
                rc = process.wait(timeout=600)  # 10 min timeout
            
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            # Parse result
            result = self.parse_final_json(lines)
            if not result:
                result = {
                    "status": "failed",
                    "notes": f"No FINAL_JSON found (exit: {rc})",
                    "next_state": "failed"
                }
            
            result["duration_ms"] = duration_ms
            result["exit_code"] = rc
            result["phase"] = self.phase
            
            # If successful and in apply/test phase, verify tests and collect diff stats
            if result.get("status") == "success" and self.phase in ["apply", "test"]:
                # Verify tests pass
                if self.phase == "test" or self.phase == "apply":
                    tests_pass = self.verify_tests_pass()
                    result["tests_pass"] = tests_pass
                    if not tests_pass and self.phase == "test":
                        result["status"] = "failed"
                        result["notes"] = "Tests failed during test phase"
                        result["next_state"] = "failed"
                
                # Collect git diff stats
                diff_stats = self.get_git_diff_stats()
                result["diff_stats"] = diff_stats
                self.print_info(f"Changes: {diff_stats.get('diff_summary', 'No changes')}")
            
            # Log outcome
            if result.get("status") == "success":
                self.print_status("SUCCESS", result.get("notes", "Task completed"))
            else:
                self.print_error(result.get("notes", "Task failed"))
            
            return result
            
        except subprocess.TimeoutExpired:
            self.print_error("Execution timeout (10 minutes)")
            return {
                "status": "failed",
                "notes": "Execution timeout",
                "next_state": "failed",
                "duration_ms": 600000
            }
        except Exception as e:
            self.print_error(f"Execution error: {e}")
            return {
                "status": "failed", 
                "notes": str(e),
                "next_state": "failed"
            }
    
    def run_one_shot(self):
        """Run single task and exit (for Queen spawning)"""
        if not self.task_id:
            self.print_error("No task ID provided for one-shot mode")
            return 1
        
        # Load task
        task = self.load_task(self.task_id)
        if not task:
            self.print_error(f"Task {self.task_id} not found")
            return 1
        
        # Emit start event
        self.emit_event(
            type="task_execution_start",
            task_id=self.task_id,
            title=task.get("title", "")
        )
        
        # Execute
        result = self.execute_task(task)
        
        # Save result
        self.save_result(self.task_id, result)
        
        # Emit completion event
        self.emit_event(
            type="task_execution_complete",
            task_id=self.task_id,
            status=result.get("status"),
            notes=result.get("notes", ""),
            duration_ms=result.get("duration_ms", 0)
        )
        
        # Exit with appropriate code
        return 0 if result.get("status") == "success" else 1

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Claude Code Worker")
    parser.add_argument("worker_id", help="Worker ID (backend, frontend, infra)")
    parser.add_argument("--one-shot", action="store_true", help="Run single task and exit")
    parser.add_argument("--task-id", help="Task ID for one-shot mode")
    parser.add_argument("--run-id", help="Run ID for this execution")
    parser.add_argument("--workspace", help="Workspace directory (worktree)")
    parser.add_argument("--phase", choices=["plan", "apply", "test"], default="apply",
                       help="Execution phase (plan, apply, test)")
    
    args = parser.parse_args()
    
    # Create worker
    worker = CCWorker(
        worker_id=args.worker_id,
        task_id=args.task_id,
        run_id=args.run_id,
        workspace=args.workspace,
        phase=args.phase
    )
    
    # Run mode
    if args.one_shot:
        sys.exit(worker.run_one_shot())
    else:
        print("Continuous mode not supported - use Queen orchestrator")
        sys.exit(1)

if __name__ == "__main__":
    main()
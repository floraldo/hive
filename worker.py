#!/usr/bin/env python3
"""
WorkerCore - Streamlined Worker
Preserves path duplication fix while simplifying architecture
"""

import json
import os
import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

class WorkerCore:
    """Streamlined worker with preserved path fix"""
    
    def __init__(self, worker_id: str, task_id: str = None, run_id: str = None, 
                 workspace: str = None, phase: str = None, mode: str = None):
        self.worker_id = worker_id
        self.task_id = task_id
        self.run_id = run_id
        self.phase = phase or "apply"
        self.mode = mode or "fresh"
        
        # Core paths (deterministic, independent of shell cwd)
        self.root = Path(__file__).resolve().parent  # .../hive
        self.hive_dir = self.root / "hive"
        self.tasks_dir = self.hive_dir / "tasks"
        self.results_dir = self.hive_dir / "results"
        self.logs_dir = self.hive_dir / "logs"
        
        # Workspace creation based on mode
        if workspace:
            # Use provided workspace path - normalize to absolute path
            self.workspace = Path(workspace).resolve()
            self.workspace.mkdir(parents=True, exist_ok=True)
        else:
            # Create workspace based on mode
            self.workspace = self._create_workspace()
        
        # Ensure process-level cwd is the workspace (safe even if you also set cwd in Popen)
        try:
            os.chdir(self.workspace)
        except Exception as e:
            print(f"[{self.timestamp()}] [WARN] Could not chdir to workspace: {e}")
        
        # Pre-flight invariant checks to ensure workspace isolation
        self._verify_workspace_isolation()
        
        # Find Claude command
        self.claude_cmd = self.find_claude_cmd()
        
        # Logging
        print(f"[{self.timestamp()}] [INITIALIZED] Worker {worker_id} ready")
        if self.task_id:
            print(f"         [INFO] Task: {self.task_id}")
            print(f"         [INFO] Run ID: {self.run_id}")
            print(f"         [INFO] Phase: {self.phase}")
        print(f"         [INFO] Workspace: {self.workspace}")
        print(f"         [INFO] Claude: {self.claude_cmd or 'SIMULATION MODE'}")
    
    def timestamp(self) -> str:
        """Current timestamp for logging"""
        return datetime.now().strftime("%H:%M:%S")
    
    def _create_workspace(self) -> Path:
        """Create workspace based on mode (fresh or repo)"""
        # Determine workspace path
        if self.task_id:
            workspace_path = self.root / ".worktrees" / self.worker_id / self.task_id
        else:
            workspace_path = self.root / ".worktrees" / self.worker_id
        
        if self.mode == "fresh":
            # Fresh mode: create empty directory
            workspace_path.mkdir(parents=True, exist_ok=True)
            print(f"[{self.timestamp()}] Created fresh workspace: {workspace_path}")
            return workspace_path
            
        elif self.mode == "repo":
            # Repo mode: create git worktree
            return self._create_git_worktree(workspace_path)
        
        else:
            raise ValueError(f"Unknown mode: {self.mode}")
    
    def _create_git_worktree(self, workspace_path: Path) -> Path:
        """Create git worktree for repo mode"""
        # Create branch name
        safe_task_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.task_id)
        branch = f"agent/{self.worker_id}/{safe_task_id}"
        
        # If worktree already exists and is valid, reuse it
        if workspace_path.exists():
            git_file = workspace_path / ".git"
            if git_file.exists():
                print(f"[{self.timestamp()}] Reusing existing git worktree: {workspace_path}")
                return workspace_path
            else:
                # Directory exists but not a git worktree - remove it
                import shutil
                shutil.rmtree(workspace_path)
        
        # Create git worktree with branch from HEAD - fail fast on errors
        result = subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(workspace_path), "HEAD"],
            cwd=str(self.root),
            capture_output=True, text=True, check=True  # check=True raises CalledProcessError on failure
        )
        
        # Validate that worktree was created properly
        git_file = workspace_path / ".git"
        if not git_file.exists():
            raise RuntimeError(f"Git worktree created but missing .git file: {workspace_path}")
            
        print(f"[{self.timestamp()}] Created git worktree: {workspace_path} (branch: {branch})")
        return workspace_path
    
    def find_claude_cmd(self) -> Optional[str]:
        """Find Claude command with fallbacks"""
        # Check environment variable first
        if os.getenv("CLAUDE_BIN"):
            claude_path = Path(os.getenv("CLAUDE_BIN"))
            if claude_path.exists():
                print(f"[INFO] Using Claude from CLAUDE_BIN: {claude_path}")
                return str(claude_path)
        
        # Check common paths
        possible_paths = [
            Path.home() / ".npm-global" / "claude.CMD",
            Path.home() / ".npm-global" / "bin" / "claude",
            Path("claude.CMD"),
            Path("claude")
        ]
        
        for path in possible_paths:
            if path.exists():
                print(f"[INFO] Using Claude from PATH: {path}")
                return str(path)
        
        # Try which/where command
        try:
            result = subprocess.run(
                ["where" if os.name == "nt" else "which", "claude"],
                capture_output=True, text=True, check=True
            )
            claude_path = result.stdout.strip().split('\n')[0]
            if claude_path:
                print(f"[INFO] Using Claude from system PATH: {claude_path}")
                return claude_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        print("[WARN] Claude command not found - running in simulation mode")
        return None
    
    
    def _verify_workspace_isolation(self):
        """Pre-flight invariant checks to ensure workspace isolation."""
        if os.getenv("HIVE_DEBUG") != "1":
            return
        
        print(f"[{self.timestamp()}] [ISOLATION] Verifying workspace isolation...")
        workspace_resolved = self.workspace.resolve()
        
        # Check 1: Process cwd MUST match the workspace for git to work reliably.
        current_cwd = Path.cwd().resolve()
        if current_cwd == workspace_resolved:
            print(f"[{self.timestamp()}] [OK] Process cwd matches workspace: {current_cwd}")
        else:
            # This is a critical failure condition for the KISS approach.
            print(f"[{self.timestamp()}] [CRITICAL] Process cwd mismatch: {current_cwd} != {workspace_resolved}")

        # Check 2: Verify git can naturally operate within this directory.
        if self.mode == "repo":
            try:
                # A lightweight command like 'git rev-parse --git-dir' is better than 'git status'.
                result = subprocess.run(
                    ["git", "rev-parse", "--git-dir"],
                    capture_output=True, text=True, cwd=str(self.workspace), check=True
                )
                if result.stdout.strip():
                    print(f"[{self.timestamp()}] [OK] Git context successfully detected in workspace.")
                else:
                    print(f"[{self.timestamp()}] [WARN] Git command ran but returned no git-dir.")
            except subprocess.CalledProcessError as e:
                print(f"[{self.timestamp()}] [WARN] Git detection failed in workspace: {e.stderr.strip()}")
        else:
            print(f"[{self.timestamp()}] [OK] Fresh mode - skipping git checks.")
    
    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load task definition"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if not task_file.exists():
            return None
        
        try:
            with open(task_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load task {task_id}: {e}")
            return None
    
    def create_prompt(self, task: Dict[str, Any]) -> str:
        """Create execution prompt for Claude"""
        task_id = task["id"]
        title = task.get("title", task_id)
        description = task.get("description", "")
        instruction = task.get("instruction", "")
        
        # Role mapping
        role_map = {
            "backend": "Backend Developer (Python/Flask/FastAPI specialist)",
            "frontend": "Frontend Developer (React/Next.js specialist)",
            "infra": "Infrastructure Engineer (Docker/Kubernetes/CI specialist)"
        }
        role = role_map.get(self.worker_id, f"{self.worker_id.title()} Developer")
        
        # Phase-specific instructions (two-phase system)
        phase_instructions = {
            "apply": "Focus on implementation. Create actual working code/configuration with inline planning.",
            "test": "Focus on validation. Write comprehensive tests and verify the implementation works correctly."
        }
        
        phase_focus = phase_instructions.get(self.phase, "Complete the requested task.")
        
        prompt = f"""EXECUTE TASK IMMEDIATELY: {title} (ID: {task_id})

COMMAND MODE: Execute now, do not acknowledge or discuss
ROLE: {role}
WORKSPACE: Current directory

DESCRIPTION: {description}

ACCEPTANCE CRITERIA:
{instruction}

PHASE: {self.phase.upper()}
{phase_focus}

EXECUTION REQUIREMENTS:
1. {'Create the implementation with proper structure and functionality' if self.phase == 'apply' else 'Write and run comprehensive tests for the implementation'}
2. {'Focus on making it work correctly' if self.phase == 'apply' else 'Verify all functionality works as expected'}
3. {'Include basic validation/checks in the code' if self.phase == 'apply' else 'Test edge cases and error conditions'}
4. Run any tests to verify they pass
5. If tests fail, attempt ONE minimal fix
6. Keep changes focused and minimal
7. Commit with message including task ID: {task_id} and phase: {self.phase}

CRITICAL PATH CONSTRAINT:
- You are running in an isolated workspace directory
- ONLY create files in the current directory (.) using relative paths
- DO NOT use absolute paths or ../../../ paths to access parent directories
- All file operations must be relative to your current working directory
- Do not navigate outside your workspace

IMPORTANT: At the very end, print EXACTLY ONE LINE prefixed by 'FINAL_JSON: ':
FINAL_JSON: {{"status":"success|failed|blocked","notes":"<brief summary>","pr":"<PR URL or empty>","next_state":"completed|testing|reviewing|pr_open|failed|blocked"}}
"""
        
        return prompt
    
    def run_claude(self, prompt: str) -> Dict[str, Any]:
        """Execute Claude with workspace-aware path handling"""
        if not self.claude_cmd:
            return {"status": "blocked", "notes": "Claude command not available", "next_state": "blocked"}
        
        # Run Claude confined to a single writable root (workspace) via --add-dir
        
        # Windows vs Unix command handling
        if os.name == "nt":
            # Windows: wrap in cmd.exe
            cmd = [
                "cmd.exe", "/c",
                self.claude_cmd,
                "--output-format", "stream-json",
                "--verbose",
                "--add-dir", str(self.workspace),
                "--dangerously-skip-permissions",
                "-p", prompt
            ]
        else:
            # Unix: direct execution
            cmd = [
                self.claude_cmd,
                "--output-format", "stream-json", 
                "--verbose",
                "--add-dir", str(self.workspace),
                "--dangerously-skip-permissions",
                "-p", prompt
            ]
        
        print(f"[{self.timestamp()}] [RUNNING] Claude is working...")
        print(f"         [INFO] Workspace: {self.workspace}")
        print(f"         [INFO] Command: {' '.join(cmd)}")
        print(f"         [INFO] Prompt length: {len(prompt)} chars")
        
        # Create log file for this run
        log_file = None
        if self.task_id and self.run_id:
            log_dir = self.logs_dir / self.task_id
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{self.run_id}.log"
            print(f"         [INFO] Logging to: {log_file}")
        
        try:
            # Create isolated environment for workspace
            env = os.environ.copy()
            env.update({
                "CLAUDE_PROJECT_ROOT": str(self.workspace),
                "CLAUDE_WORKSPACE_ROOT": str(self.workspace),
                "PWD": str(self.workspace),
                "WORKSPACE": str(self.workspace),
                # Prevent repo-root climbing; treat workspace as the ceiling
                "GIT_CEILING_DIRECTORIES": str(self.workspace),
            })
            
            # KISS approach: trust git's native worktree detection
            if self.mode == "repo":
                print(f"[{self.timestamp()}] [INFO] Using standard git context detection within worktree")
            
            # Run from workspace directory (Claude will create files here)
            log_fp = open(log_file, "a", encoding="utf-8") if log_file else None
            try:
                with subprocess.Popen(
                    cmd,
                    cwd=str(self.workspace),  # Claude runs from workspace
                    env=env,  # Isolated environment
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                ) as process:
                    
                    output_lines = []
                    final_json = None
                    
                    # Stream output and look for final JSON
                    for line in process.stdout:
                        output_lines.append(line.rstrip())
                        if log_fp:
                            log_fp.write(line)
                        
                        if line.strip().startswith("FINAL_JSON:"):
                            try:
                                json_str = line.strip()[11:].strip()  # Remove "FINAL_JSON:" prefix
                                final_json = json.loads(json_str)
                            except json.JSONDecodeError:
                                print(f"[ERROR] Invalid final JSON: {line.strip()}")
                    
                    # Wait for completion
                    exit_code = process.wait()
                    
                    # Save final status to log
                    if log_fp:
                        log_fp.write(f"\n\n=== EXIT CODE: {exit_code} ===\n")
                        if final_json:
                            log_fp.write(f"=== FINAL JSON: {json.dumps(final_json, indent=2)} ===\n")
            finally:
                if log_fp:
                    log_fp.close()
                
                # Handle results
                if exit_code == 0 and final_json:
                    print(f"[{self.timestamp()}] [SUCCESS] Task completed successfully")
                    return final_json
                elif exit_code == 0:
                    print(f"[{self.timestamp()}] [WARNING] Task completed but no final JSON found")
                    return {"status": "success", "notes": "Completed but missing final status", "next_state": "completed"}
                else:
                    print(f"[{self.timestamp()}] [ERROR] Claude failed with exit code {exit_code}")
                    # Show last few lines for debugging
                    if len(output_lines) > 10:
                        print(f"         [ERROR] Last 10 lines of output:")
                        for line in output_lines[-10:]:
                            print(f"         [ERROR]   {line}")
                    
                    return {"status": "failed", "notes": f"Claude exit code {exit_code}", "next_state": "failed"}
        
        except Exception as e:
            print(f"[{self.timestamp()}] [ERROR] Claude execution failed: {e}")
            return {"status": "failed", "notes": f"Execution error: {str(e)}", "next_state": "failed"}
    
    def emit_result(self, result: Dict[str, Any]):
        """Save execution result"""
        if not self.task_id or not self.run_id:
            print("[ERROR] Cannot emit result - missing task_id or run_id")
            return
        
        # Prepare result data
        result_data = {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "worker": self.worker_id,
            "phase": self.phase,
            "workspace": str(self.workspace),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **result
        }
        
        # Save result to file
        results_dir = self.results_dir / self.task_id
        results_dir.mkdir(parents=True, exist_ok=True)
        
        result_file = results_dir / f"{self.run_id}.json"
        try:
            with open(result_file, "w") as f:
                json.dump(result_data, f, indent=2)
            
            print(f"[{self.timestamp()}] [RESULT] Saved to {result_file}")
            
        except Exception as e:
            print(f"[{self.timestamp()}] [ERROR] Failed to save result: {e}")
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with streamlined workflow"""
        task_id = task["id"]
        title = task.get("title", task_id)
        
        print(f"[{self.timestamp()}] [EXECUTING] Task: {title}")
        
        # Create prompt
        prompt = self.create_prompt(task)
        print(f"         [INFO] Using inline prompt")
        
        # Run Claude
        result = self.run_claude(prompt)
        
        # Emit result
        self.emit_result(result)
        
        return result
    
    def run_one_shot(self):
        """Run in one-shot mode (called by Queen)"""
        if not self.task_id:
            print("[ERROR] One-shot mode requires task_id")
            return {"status": "failed", "notes": "Missing task_id", "next_state": "failed"}
        
        # Load task
        task = self.load_task(self.task_id)
        if not task:
            error_msg = f"Task {self.task_id} not found"
            print(f"[ERROR] {error_msg}")
            return {"status": "failed", "notes": error_msg, "next_state": "failed"}
        
        # Execute task
        return self.execute_task(task)

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="WorkerCore - Streamlined Worker")
    parser.add_argument("worker_id", help="Worker ID (backend, frontend, infra)")
    parser.add_argument("--one-shot", action="store_true", help="One-shot mode for Queen")
    parser.add_argument("--local", action="store_true", 
                       help="Local development mode - run task directly without Queen")
    parser.add_argument("--task-id", help="Task ID (required for one-shot and local modes)")
    parser.add_argument("--run-id", help="Run ID for this execution (auto-generated in local mode)")
    parser.add_argument("--workspace", help="Workspace directory")
    parser.add_argument("--phase", choices=["plan", "apply", "test"], default="apply",
                       help="Execution phase")
    parser.add_argument("--mode", choices=["fresh", "repo"], default="fresh",
                       help="Workspace mode: fresh (empty directory) or repo (git worktree)")
    
    args = parser.parse_args()
    
    # Validate local mode arguments
    if args.local:
        if not args.task_id:
            print("[ERROR] Local mode requires --task-id to be specified")
            print("\nUsage example:")
            print("  python worker.py backend --local --task-id hello_hive --phase apply")
            sys.exit(1)
        
        # Generate run_id if not provided in local mode
        if not args.run_id:
            args.run_id = f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"[INFO] Generated run_id for local mode: {args.run_id}")
    
    # Create worker
    worker = WorkerCore(
        worker_id=args.worker_id,
        task_id=args.task_id,
        run_id=args.run_id,
        workspace=args.workspace,
        phase=args.phase,
        mode=args.mode
    )
    
    if args.one_shot or args.local:
        # One-shot execution for Queen or local development
        if args.local:
            print(f"[INFO] Running in LOCAL DEVELOPMENT MODE")
            print(f"[INFO] Task: {args.task_id}, Phase: {args.phase}")
        
        result = worker.run_one_shot()
        sys.exit(0 if result.get("status") == "success" else 1)
    else:
        print("Interactive mode not implemented - use --one-shot or --local")
        sys.exit(1)

if __name__ == "__main__":
    main()
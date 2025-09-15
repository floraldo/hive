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
from typing import Dict, Any, Optional, List

# Hive logging system (with local dev fallback for import path)
try:
    from hive_logging import setup_logging, get_logger
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent / "packages" / "hive-logging" / "src"))
    from hive_logging import setup_logging, get_logger

class WorkerCore:
    """Streamlined worker with preserved path fix"""
    
    def __init__(self, worker_id: str, task_id: str = None, run_id: str = None, 
                 workspace: str = None, phase: str = None, mode: str = None, 
                 live_output: bool = False):
        self.worker_id = worker_id
        self.task_id = task_id
        self.run_id = run_id
        self.phase = phase or "apply"
        self.mode = mode or "fresh"
        self.live_output = live_output
        
        # Initialize logger
        self.log = get_logger(__name__)
        
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
            self.log.warning(f"Could not chdir to workspace: {e}")
        
        # Pre-flight invariant checks to ensure workspace isolation
        self._verify_workspace_isolation()
        
        # Find Claude command
        self.claude_cmd = self.find_claude_cmd()
        
        # Logging
        self.log.info(f"Worker {worker_id} ready")
        if self.task_id:
            print(f"         [INFO] Task: {self.task_id}")
            print(f"         [INFO] Run ID: {self.run_id}")
            print(f"         [INFO] Phase: {self.phase}")
        print(f"         [INFO] Workspace: {self.workspace}")
        print(f"         [INFO] Claude: {self.claude_cmd or 'SIMULATION MODE'}")
    

    
    def _create_workspace(self) -> Path:
        """Create or reuse workspace based on mode (fresh or repo)"""
        # Determine workspace path
        if self.task_id:
            workspace_path = self.root / ".worktrees" / self.worker_id / self.task_id
        else:
            workspace_path = self.root / ".worktrees" / self.worker_id
        
        if self.mode == "fresh":
            # Fresh mode: always start clean (remove existing, create new)
            if workspace_path.exists():
                import shutil
                try:
                    shutil.rmtree(workspace_path)
                    self.log.info(f"Cleaned existing workspace: {workspace_path}")
                except PermissionError:
                    # Windows file locking issue - just continue, mkdir will handle it
                    self.log.warning(f"Could not clean workspace (file in use), continuing anyway")
            workspace_path.mkdir(parents=True, exist_ok=True)
            self.log.info(f"Created fresh workspace: {workspace_path}")
            return workspace_path
            
        elif self.mode == "repo":
            # Repo mode: create or reuse git worktree
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
                self.log.info(f"Reusing existing git worktree: {workspace_path}")
                return workspace_path
            else:
                # Directory exists but not a git worktree - remove it
                import shutil
                try:
                    shutil.rmtree(workspace_path)
                except PermissionError:
                    # Windows file locking issue - just continue
                    self.log.warning(f"Could not clean non-git directory (file in use), continuing anyway")
        
        # Prune stale worktrees
        subprocess.run(["git", "worktree", "prune"], cwd=str(self.root), capture_output=True, text=True)

        # Does the branch already exist?
        branch_exists = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", branch],
            cwd=str(self.root), capture_output=True, text=True
        ).returncode == 0

        try:
            if branch_exists:
                # Add existing branch
                self.log.info(f"Attaching worktree to existing branch: {branch}")
                subprocess.run(
                    ["git", "worktree", "add", str(workspace_path), branch],
                    cwd=str(self.root), capture_output=True, text=True, check=True
                )
            else:
                # Create new branch from HEAD
                self.log.info(f"Creating worktree with new branch: {branch}")
                subprocess.run(
                    ["git", "worktree", "add", "-b", branch, str(workspace_path), "HEAD"],
                    cwd=str(self.root), capture_output=True, text=True, check=True
                )
        except subprocess.CalledProcessError as e:
            # Helpful diagnostics
            error_message = e.stderr.strip() if e.stderr else str(e)
            self.log.error(f"git worktree add failed: {error_message}")
            raise RuntimeError(f"Could not create or attach git worktree: {error_message}") from e
            
        # Validate that worktree was created properly
        git_file = workspace_path / ".git"
        if not git_file.exists():
            raise RuntimeError(f"Git worktree created but missing .git file: {workspace_path}")
            
        self.log.info(f"Created git worktree: {workspace_path} (branch: {branch})")
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
        
        self.log.info("[ISOLATION] Verifying workspace isolation...")
        workspace_resolved = self.workspace.resolve()
        
        # Check 1: Process cwd MUST match the workspace for git to work reliably.
        current_cwd = Path.cwd().resolve()
        if current_cwd == workspace_resolved:
            self.log.info(f"[OK] Process cwd matches workspace: {current_cwd}")
        else:
            # This is a critical failure condition for the KISS approach.
            self.log.error(f"[CRITICAL] Process cwd mismatch: {current_cwd} != {workspace_resolved}")

        # Check 2: Verify git can naturally operate within this directory.
        if self.mode == "repo":
            try:
                # A lightweight command like 'git rev-parse --git-dir' is better than 'git status'.
                result = subprocess.run(
                    ["git", "rev-parse", "--git-dir"],
                    capture_output=True, text=True, cwd=str(self.workspace), check=True
                )
                if result.stdout.strip():
                    self.log.info("[OK] Git context successfully detected in workspace.")
                else:
                    self.log.warning("[WARN] Git command ran but returned no git-dir.")
            except subprocess.CalledProcessError as e:
                self.log.warning(f"[WARN] Git detection failed in workspace: {e.stderr.strip()}")
        else:
            self.log.info("[OK] Fresh mode - skipping git checks.")
    
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
    
    def _load_context_from_tasks(self, context_from: List[str]) -> str:
        """Load context from previous task results"""
        if not context_from:
            return ""
        
        context_sections = []
        for prev_task_id in context_from:
            # Load the most recent result for the referenced task
            results_dir = self.results_dir / prev_task_id
            if not results_dir.exists():
                context_sections.append(f"[Context from {prev_task_id}: No results found]")
                continue
            
            result_files = list(results_dir.glob("*.json"))
            if not result_files:
                context_sections.append(f"[Context from {prev_task_id}: No results found]")
                continue
            
            # Get the most recent result
            latest = max(result_files, key=lambda f: f.stat().st_mtime)
            try:
                with open(latest, "r") as f:
                    result = json.load(f)
                
                # Extract relevant context
                context_text = f"CONTEXT FROM TASK '{prev_task_id}':\n"
                context_text += f"- Status: {result.get('status', 'unknown')}\n"
                context_text += f"- Notes: {result.get('notes', 'N/A')}\n"
                
                # Include file information if available
                files = result.get("files", {})
                if files.get("created"):
                    context_text += f"- Files created: {', '.join(files['created'][:5])}"
                    if len(files['created']) > 5:
                        context_text += f" (+{len(files['created'])-5} more)"
                    context_text += "\n"
                if files.get("modified"):
                    context_text += f"- Files modified: {', '.join(files['modified'][:5])}"
                    if len(files['modified']) > 5:
                        context_text += f" (+{len(files['modified'])-5} more)"
                    context_text += "\n"
                
                # Include any additional context hints
                if "context_hints" in result:
                    context_text += f"- Key insights: {result['context_hints']}\n"
                
                context_sections.append(context_text)
                
            except Exception as e:
                context_sections.append(f"[Context from {prev_task_id}: Error loading - {e}]")
        
        if context_sections:
            return "\n".join(context_sections) + "\n"
        return ""
    
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
        
        # Load context from referenced tasks
        context_from = task.get("context_from", [])
        context_section = ""
        if context_from:
            context_section = self._load_context_from_tasks(context_from)
        
        prompt = f"""EXECUTE TASK IMMEDIATELY: {title} (ID: {task_id})

COMMAND MODE: Execute now, do not acknowledge or discuss
ROLE: {role}
WORKSPACE: Current directory

DESCRIPTION: {description}

{context_section}ACCEPTANCE CRITERIA:
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
"""
        
        return prompt
    
    def _get_workspace_files(self) -> Dict[str, List[str]]:
        """Get list of files created/modified in workspace"""
        created_files = []
        modified_files = []
        
        if self.workspace.exists():
            # For repo mode, use git to track changes
            if self.mode == "repo":
                try:
                    # If we have a baseline, diff against it; else fallback to HEAD
                    baseline = getattr(self, "_baseline_commit", None)
                    if baseline:
                        diff_target = f"{baseline}..HEAD"
                    else:
                        diff_target = "HEAD"

                    # Files changed in commits since baseline
                    res = subprocess.run(
                        ["git", "diff", "--name-only", diff_target],
                        cwd=str(self.workspace), capture_output=True, text=True
                    )
                    if res.returncode == 0:
                        modified_files = [f for f in res.stdout.strip().split("\n") if f]

                    # Untracked files (never committed)
                    result = subprocess.run(
                        ["git", "ls-files", "--others", "--exclude-standard"],
                        cwd=str(self.workspace),
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        created_files = [f for f in result.stdout.strip().split("\n") if f]
                except Exception as e:
                    self.log.warning(f"[WARN] Could not get git file status: {e}")
            else:
                # For fresh mode, all files are considered created
                try:
                    for file_path in self.workspace.rglob("*"):
                        if file_path.is_file():
                            relative_path = str(file_path.relative_to(self.workspace))
                            created_files.append(relative_path)
                except Exception as e:
                    self.log.warning(f"[WARN] Could not scan workspace files: {e}")
        
        return {
            "created": created_files,
            "modified": modified_files
        }
    
    def _format_live_output(self, line: str) -> Optional[str]:
        """Format line for live output - shows Claude messages, commands, and results with worker ID"""
        if not self.live_output:
            return None
        
        # Worker identification with color coding
        worker_colors = {
            "backend": "\033[94m",    # Blue
            "frontend": "\033[92m",   # Green  
            "infra": "\033[93m",      # Yellow
            "test": "\033[95m"        # Magenta
        }
        reset_color = "\033[0m"
        color = worker_colors.get(self.worker_id, "\033[97m")  # White default
        worker_prefix = f"{color}[{self.worker_id.upper()}]{reset_color}"
        
        try:
            # Try to parse as JSON
            data = json.loads(line)
            
            # Claude's text messages
            if data.get("type") == "assistant" and "message" in data:
                content = data["message"].get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            text = item.get("text", "").strip()
                            if text:
                                return f"{worker_prefix} 🤖 {text}"
                        elif item.get("type") == "tool_use":
                            tool_name = item.get("name", "")
                            if tool_name == "Bash":
                                cmd = item.get("input", {}).get("command", "")
                                desc = item.get("input", {}).get("description", "")
                                if desc:
                                    return f"{worker_prefix} 💻 $ {cmd}  # {desc}"
                                else:
                                    return f"{worker_prefix} 💻 $ {cmd}"
                            elif tool_name in ["Write", "Edit", "MultiEdit"]:
                                file_path = item.get("input", {}).get("file_path", "")
                                return f"{worker_prefix} 📝 {tool_name} {file_path}"
                            elif tool_name == "Read":
                                file_path = item.get("input", {}).get("target_file", "")
                                return f"{worker_prefix} 📖 Read {file_path}"
                            else:
                                return f"{worker_prefix} 🔧 {tool_name}()"
            
            # Command results and responses
            elif data.get("type") == "user" and "content" in data:
                content = data["content"]
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "tool_result":
                            result = item.get("content", "")
                            is_error = item.get("is_error", False)
                            
                            if is_error:
                                return f"{worker_prefix} ❌ {result}"
                            else:
                                # Truncate long outputs but keep them readable
                                if len(result) > 200:
                                    lines = result.split('\n')
                                    if len(lines) > 10:
                                        result = '\n'.join(lines[:8]) + f"\n... ({len(lines)-8} more lines)"
                                    else:
                                        result = result[:200] + "..."
                                return f"{worker_prefix} 📤 {result}"
            
        except json.JSONDecodeError:
            # Not JSON - could be system messages or other output
            # Only show if it looks like important output
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith('{"type":"system"'):
                return f"{worker_prefix} {line_stripped}"
        
        return None
    
    def run_claude(self, prompt: str) -> Dict[str, Any]:
        """Execute Claude with workspace-aware path handling"""
        if not self.claude_cmd:
            return {"status": "blocked", "notes": "Claude command not available", "next_state": "blocked"}
        
        # Build base command
        cmd = [
            self.claude_cmd,
            "--output-format", "stream-json",
            "--verbose",
            "--add-dir", str(self.workspace),
            "--dangerously-skip-permissions",
            "-p", prompt
        ]
        
        # Windows: wrap in cmd.exe
        if os.name == "nt":
            cmd = ["cmd.exe", "/c"] + cmd
        
        self.log.info("[RUNNING] Claude is working...")
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
                self.log.info("[INFO] Using standard git context detection within worktree")
                # Capture baseline commit before run
                try:
                    base = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=str(self.workspace), capture_output=True, text=True, check=True
                    )
                    self._baseline_commit = base.stdout.strip()
                except Exception:
                    self._baseline_commit = None
            
            # Run from workspace directory (Claude will create files here)
            log_fp = open(log_file, "a", encoding="utf-8") if log_file else None
            exit_code = None
            output_lines = []
            claude_completed = False
            last_assistant_message = None
            
            try:
                with subprocess.Popen(
                    cmd,
                    cwd=str(self.workspace),  # Claude runs from workspace
                    env=env,  # Isolated environment
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,  # Prevent interactive input
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # Hide console window on Windows
                ) as process:
                    
                    # Stream output and analyze Claude's responses
                    for line in process.stdout:
                        output_lines.append(line.rstrip())
                        if log_fp:
                            log_fp.write(line)
                            log_fp.flush()  # Ensure immediate write
                        
                        # Live output to terminal if enabled
                        if self.live_output:
                            formatted = self._format_live_output(line)
                            if formatted:
                                print(formatted)
                        
                        # Parse JSON messages to track Claude's state
                        try:
                            data = json.loads(line)
                            if data.get("type") == "assistant":
                                last_assistant_message = data
                            elif data.get("type") == "result":
                                claude_completed = True
                                if data.get("subtype") == "success":
                                    # Extract the result text as our output
                                    result_text = data.get("result", "")
                                    self.log.info(f"[CLAUDE] Completed with result: {result_text[:100]}...")
                        except json.JSONDecodeError:
                            pass  # Not JSON, that's fine
                    
                    # Wait for completion with timeout (10 minutes max)
                    try:
                        exit_code = process.wait(timeout=600)
                    except subprocess.TimeoutExpired:
                        self.log.error("[ERROR] Claude timed out after 10 minutes")
                        try:
                            # Try graceful termination first
                            process.terminate()
                            try:
                                exit_code = process.wait(timeout=30)
                            except subprocess.TimeoutExpired:
                                # Force kill if terminate didn't work
                                process.kill()
                                exit_code = -1
                        except Exception as e:
                            self.log.error(f"[ERROR] Failed to terminate process: {e}")
                            process.kill()
                            exit_code = -1
                    
                    # Save final status to log
                    if log_fp:
                        log_fp.write(f"\n\n=== EXIT CODE: {exit_code} ===\n")
            finally:
                if log_fp:
                    log_fp.close()
                
                # Get file changes after execution
                files_changed = self._get_workspace_files()
                
                # Determine success based on multiple factors
                success = False
                status_notes = ""
                
                if exit_code == 0 and claude_completed:
                    # Claude completed successfully
                    success = True
                    status_notes = "Claude completed successfully"
                    self.log.info("[SUCCESS] Task completed successfully")
                elif exit_code == 0 and not claude_completed:
                    # Claude exited cleanly but didn't send completion
                    # Check if files were created as a success indicator
                    if files_changed.get("created") or files_changed.get("modified"):
                        success = True
                        status_notes = f"Created {len(files_changed.get('created', []))} files, modified {len(files_changed.get('modified', []))} files"
                        self.log.info(f"[SUCCESS] Task likely succeeded - files were created/modified")
                    else:
                        success = False
                        status_notes = "Claude exited without creating files"
                        self.log.warning("[WARNING] Claude exited but no files created")
                elif exit_code == -1:
                    # Timeout
                    success = False
                    status_notes = "Claude timed out after 5 minutes"
                    self.log.error("[ERROR] Claude timed out")
                else:
                    # Non-zero exit code
                    success = False
                    status_notes = f"Claude exit code {exit_code}"
                    self.log.error(f"[ERROR] Claude failed with exit code {exit_code}")
                
                # Build result from what we observed
                return {
                    "status": "success" if success else "failed",
                    "notes": status_notes,
                    "next_state": "completed" if success else "failed",
                    "files": files_changed,
                    "claude_completed": claude_completed,
                    "exit_code": exit_code,
                    "output_lines": len(output_lines)
                }
        
        except Exception as e:
            self.log.error(f"[ERROR] Claude execution failed: {e}")
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
            # Atomic write: write to temp file then rename with retry for Windows
            tmp_file = result_file.with_suffix(".json.tmp")
            with open(tmp_file, "w") as f:
                json.dump(result_data, f, indent=2)
            
            # Windows-safe atomic rename with retry
            import time
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    tmp_file.replace(result_file)
                    break
                except (PermissionError, OSError) as e:
                    if attempt < max_retries - 1:
                        self.log.warning(f"Atomic rename failed (attempt {attempt + 1}/{max_retries}): {e}")
                        time.sleep(0.1 * (attempt + 1))  # Progressive backoff
                        continue
                    else:
                        # Final attempt failed - fallback to direct write
                        self.log.warning(f"Atomic rename failed, using fallback write: {e}")
                        with open(result_file, "w") as f:
                            json.dump(result_data, f, indent=2)
                        # Clean up temp file
                        try:
                            tmp_file.unlink()
                        except:
                            pass
                        break
            
            self.log.info(f"[RESULT] Saved to {result_file}")
            
        except Exception as e:
            self.log.error(f"[ERROR] Failed to save result: {e}")
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with streamlined workflow"""
        task_id = task["id"]
        title = task.get("title", task_id)
        
        self.log.info(f"Executing task: {title}")
        
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
    parser.add_argument("--live", action="store_true",
                       help="Enable live streaming output to terminal (shows Claude messages, commands, and results)")
    
    args = parser.parse_args()
    
    # Configure logging based on worker ID and task
    log_name = f"worker-{args.worker_id}"
    if args.task_id:
        log_name += f"-{args.task_id}"
    
    # Make log path absolute + centralized (before any chdir operations)
    repo_root = Path(__file__).resolve().parent
    centralized_log = repo_root / "hive" / "logs" / f"{log_name}.log"
    centralized_log = centralized_log.resolve()  # Make fully absolute before chdir
    setup_logging(
        name=log_name,
        log_to_file=True,
        log_file_path=str(centralized_log)
    )
    log = get_logger(__name__)
    
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
        mode=args.mode,
        live_output=args.live
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
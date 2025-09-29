#!/usr/bin/env python3
"""
WorkerCore - Streamlined Worker
Preserves path duplication fix while simplifying architecture
"""
from __future__ import annotations


import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Hive utilities for path management
from hive_config.paths import (
    LOGS_DIR
    PROJECT_ROOT
    WORKTREES_DIR
    ensure_directory
    get_task_log_dir
    get_worker_workspace_dir
)

# Hive logging system
from hive_logging import get_logger, setup_logging

# Hive database system - use orchestrator's core layer
from hive_orchestrator.core import db as hive_core_db


class WorkerCore:
    """Streamlined worker with preserved path fix and DI support"""

    def __init__(
        self
        worker_id: str
        task_id: str = None
        run_id: str = None
        workspace: str = None
        phase: str = None
        mode: str = None
        live_output: bool = False
        async_mode: bool = False
        config: Optional[Dict[str, Any]] = None
    ):
        self.worker_id = worker_id
        self.task_id = task_id
        self.run_id = run_id
        self.phase = phase or "apply"
        self.mode = mode or "fresh"
        self.live_output = live_output
        self.async_mode = async_mode
        self.config = config or {}

        # Initialize async worker if async mode enabled
        self._async_worker = None

        # Initialize logger
        self.log = get_logger(__name__)

        # Use authoritative paths from singleton
        self.project_root = PROJECT_ROOT
        self.logs_dir = LOGS_DIR
        self.root = PROJECT_ROOT  # For git operations
        self.tasks_dir = PROJECT_ROOT / "tasks"  # Legacy fallback

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
            logger.info(f"         [INFO] Task: {self.task_id}")
            logger.info(f"         [INFO] Run ID: {self.run_id}")
            logger.info(f"         [INFO] Phase: {self.phase}")
        logger.info(f"         [INFO] Workspace: {self.workspace}")
        logger.info(f"         [INFO] Claude: {self.claude_cmd or 'SIMULATION MODE'}")

    def _create_workspace(self) -> Path:
        """Create or reuse workspace based on mode (fresh or repo)"""
        # Use the authoritative workspace path from singleton
        workspace_path = get_worker_workspace_dir(self.worker_id, self.task_id)

        if self.mode == "fresh":
            # Fresh mode: clean only on 'apply' phase, preserve for 'test' phase
            if self.phase == "apply" and workspace_path.exists():
                import shutil

                try:
                    shutil.rmtree(workspace_path)
                    self.log.info(f"Cleaned existing workspace for apply phase: {workspace_path}")
                except PermissionError:
                    # Windows file locking issue - just continue, mkdir will handle it
                    self.log.warning(f"Could not clean workspace (file in use), continuing anyway")

            workspace_path.mkdir(parents=True, exist_ok=True)
            if self.phase == "test" and any(workspace_path.iterdir()):
                self.log.info(f"Reusing existing workspace for test phase: {workspace_path}")
            else:
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
        subprocess.run(
            ["git", "worktree", "prune"]
            cwd=str(self.root)
            capture_output=True
            text=True
        )

        # Does the branch already exist?
        branch_exists = (
            subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", branch]
                cwd=str(self.root)
                capture_output=True
                text=True
            ).returncode
            == 0
        )

        try:
            if branch_exists:
                # Add existing branch
                self.log.info(f"Attaching worktree to existing branch: {branch}")
                subprocess.run(
                    ["git", "worktree", "add", str(workspace_path), branch]
                    cwd=str(self.root)
                    capture_output=True
                    text=True
                    check=True
                )
            else:
                # Create new branch from HEAD
                self.log.info(f"Creating worktree with new branch: {branch}")
                subprocess.run(
                    [
                        "git"
                        "worktree"
                        "add"
                        "-b"
                        branch
                        str(workspace_path)
                        "HEAD"
                    ]
                    cwd=str(self.root)
                    capture_output=True
                    text=True
                    check=True
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

    def find_claude_cmd(self) -> str | None:
        """Find Claude command with fallbacks"""
        # Check config for claude binary path
        claude_bin = self.config.get("claude_bin")
        if claude_bin:
            claude_path = Path(claude_bin)
            if claude_path.exists():
                logger.info(f"[INFO] Using Claude from CLAUDE_BIN: {claude_path}")
                return str(claude_path)

        # Check common paths (case-sensitive on Windows)
        possible_paths = [
            Path.home() / ".npm-global" / "claude.cmd",  # lowercase .cmd (actual file)
            Path.home() / ".npm-global" / "claude.CMD",  # uppercase .CMD (fallback)
            Path.home() / ".npm-global" / "bin" / "claude"
            Path("claude.cmd")
            Path("claude.CMD")
            Path("claude")
        ]

        for path in possible_paths:
            if path.exists():
                logger.info(f"[INFO] Using Claude from PATH: {path}")
                return str(path)

        # Try which/where command
        try:
            result = subprocess.run(
                ["where" if os.name == "nt" else "which", "claude"]
                capture_output=True
                text=True
                check=True
            )
            claude_path = result.stdout.strip().split("\n")[0]
            if claude_path:
                logger.info(f"[INFO] Using Claude from system PATH: {claude_path}")
                return claude_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        logger.warning("[WARN] Claude command not found - running in simulation mode")
        return None

    def _verify_workspace_isolation(self) -> None:
        """Pre-flight invariant checks to ensure workspace isolation."""
        if not self.config.get("debug_mode", False):
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
                    ["git", "rev-parse", "--git-dir"]
                    capture_output=True
                    text=True
                    cwd=str(self.workspace)
                    check=True
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
        """Load task definition from database"""
        try:
            # Initialize database if not already done
            hive_core_db.init_db()
            # Get task from database
            task = hive_core_db.get_task(task_id)
            if not task:
                # Fallback to file system for legacy support
                task_file = self.tasks_dir / f"{task_id}.json"
                if task_file.exists():
                    with open(task_file, "r") as f:
                        return json.load(f)
                return None
            return task
        except Exception as e:
            logger.error(f"[ERROR] Failed to load task {task_id}: {e}")
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
                    if len(files["created"]) > 5:
                        context_text += f" (+{len(files['created'])-5} more)"
                    context_text += "\n"
                if files.get("modified"):
                    context_text += f"- Files modified: {', '.join(files['modified'][:5])}"
                    if len(files["modified"]) > 5:
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
            "backend": "Backend Developer (Python/Flask/FastAPI specialist)"
            "frontend": "Frontend Developer (React/Next.js specialist)"
            "infra": "Infrastructure Engineer (Docker/Kubernetes/CI specialist)"
        }
        role = role_map.get(self.worker_id, f"{self.worker_id.title()} Developer")

        # Phase-specific instructions (two-phase system)
        phase_instructions = {
            "apply": "Focus on implementation. Create actual working code/configuration with inline planning."
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
                        ["git", "diff", "--name-only", diff_target]
                        cwd=str(self.workspace)
                        capture_output=True
                        text=True
                    )
                    if res.returncode == 0:
                        modified_files = [f for f in res.stdout.strip().split("\n") if f]

                    # Untracked files (never committed)
                    result = subprocess.run(
                        ["git", "ls-files", "--others", "--exclude-standard"]
                        cwd=str(self.workspace)
                        capture_output=True
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

        return {"created": created_files, "modified": modified_files}

    def _format_live_output(self, line: str) -> str | None:
        """Format line for live output - shows Claude messages, commands, and results with worker ID"""
        if not self.live_output:
            return None

        # Worker identification with color coding
        worker_colors = {
            "backend": "\033[94m",  # Blue
            "frontend": "\033[92m",  # Green
            "infra": "\033[93m",  # Yellow
            "test": "\033[95m",  # Magenta
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
                                    lines = result.split("\n")
                                    if len(lines) > 10:
                                        result = "\n".join(lines[:8]) + f"\n... ({len(lines)-8} more lines)"
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
            return {
                "status": "blocked"
                "notes": "Claude command not available"
                "next_state": "blocked"
            }

        # Build base command
        cmd = [
            self.claude_cmd
            "--output-format"
            "stream-json"
            "--verbose"
            "--add-dir"
            str(self.workspace)
            "--dangerously-skip-permissions"
            "-p"
            prompt
        ]

        self.log.info("[RUNNING] Claude is working...")
        logger.info(f"         [INFO] Workspace: {self.workspace}")
        logger.info(f"         [INFO] Command: {' '.join(cmd)}")
        logger.info(f"         [INFO] Prompt length: {len(prompt)} chars")

        # Create log file for this run
        log_file = None
        if self.task_id and self.run_id:
            log_dir = get_task_log_dir(self.task_id)
            ensure_directory(log_dir)
            log_file = log_dir / f"{self.run_id}.log"
            logger.info(f"         [INFO] Logging to: {log_file}")

        try:
            # Create isolated environment for workspace
            # Pass environment variables from config if provided
            env_base = self.config.get("env_vars", {})
            if not env_base:
                # Fallback to current environment for backwards compatibility
                import os

                env_base = os.environ.copy()
            env = env_base.copy()
            env.update(
                {
                    "CLAUDE_PROJECT_ROOT": str(self.workspace)
                    "CLAUDE_WORKSPACE_ROOT": str(self.workspace)
                    "PWD": str(self.workspace)
                    "WORKSPACE": str(self.workspace)
                    # Prevent repo-root climbing; treat workspace as the ceiling
                    "GIT_CEILING_DIRECTORIES": str(self.workspace)
                }
            )

            # KISS approach: trust git's native worktree detection
            if self.mode == "repo":
                self.log.info("[INFO] Using standard git context detection within worktree")
                # Capture baseline commit before run
                try:
                    base = subprocess.run(
                        ["git", "rev-parse", "HEAD"]
                        cwd=str(self.workspace)
                        capture_output=True
                        text=True
                        check=True
                    )
                    self._baseline_commit = base.stdout.strip()
                except Exception as e:
                    self._baseline_commit = None

            # Windows-specific fix: pipes cause Claude CLI to hang due to buffering deadlock
            # Claude blocks waiting for pipe buffer space, but worker never reads pipes properly
            # Solution: Let Claude write directly to console/file instead of pipes
            if platform.system() == "Windows":
                # On Windows, avoid pipes to prevent Claude CLI deadlock
                stdout_pipe = subprocess.DEVNULL
                stderr_pipe = subprocess.DEVNULL
                self.log.info(f"[DEBUG] Windows detected: using stdout=DEVNULL, stderr=DEVNULL")
            else:
                # On Unix, pipes work fine and provide better monitoring
                stdout_pipe = subprocess.PIPE
                stderr_pipe = subprocess.PIPE
                self.log.info(f"[DEBUG] Unix detected: using stdout=PIPE, stderr=PIPE")

            # Run from workspace directory (Claude will create files here)
            log_fp = open(log_file, "a", encoding="utf-8") if log_file else None
            exit_code = None
            output_lines = []
            transcript_lines = []  # Capture full transcript for database storage
            claude_completed = False
            last_assistant_message = None

            # ENHANCED DEBUG LOGGING FOR FINAL BUG HUNT
            self.log.info("=" * 80)
            self.log.info("[CLAUDE EXECUTION DEBUG] Starting detailed diagnostics")
            self.log.info("=" * 80)

            # Log the exact command
            self.log.info(f"[DEBUG] Full command array:")
            for i, arg in enumerate(cmd):
                self.log.info(f"  [{i}] = '{arg}'")

            # Log command as string (what would be executed in shell)
            cmd_string = " ".join(cmd)
            self.log.info(f"[DEBUG] Command string: {cmd_string}")

            # Log working directory
            self.log.info(f"[DEBUG] Current Working Directory: {self.workspace}")
            self.log.info(f"[DEBUG] CWD exists: {os.path.exists(self.workspace)}")
            self.log.info(f"[DEBUG] CWD is directory: {os.path.isdir(self.workspace)}")

            # Log critical environment variables
            self.log.info(f"[DEBUG] Environment variables:")
            self.log.info(f"  CLAUDE_BIN = {env.get('CLAUDE_BIN', 'NOT SET')}")
            self.log.info(f"  CLAUDE_PROJECT_ROOT = {env.get('CLAUDE_PROJECT_ROOT', 'NOT SET')}")
            self.log.info(f"  CLAUDE_WORKSPACE_ROOT = {env.get('CLAUDE_WORKSPACE_ROOT', 'NOT SET')}")
            self.log.info(f"  PWD = {env.get('PWD', 'NOT SET')}")
            self.log.info(f"  WORKSPACE = {env.get('WORKSPACE', 'NOT SET')}")
            self.log.info(f"  GIT_CEILING_DIRECTORIES = {env.get('GIT_CEILING_DIRECTORIES', 'NOT SET')}")

            # Log PATH (first 500 chars to see more)
            path_env = env.get("PATH", "NOT SET")
            self.log.info(f"[DEBUG] PATH (first 500 chars): {path_env[:500]}")

            # Check if claude command exists and is accessible
            import shutil

            claude_path = shutil.which(self.claude_cmd, path=path_env)
            self.log.info(f"[DEBUG] Claude command resolved to: {claude_path}")
            if claude_path:
                self.log.info(f"[DEBUG] Claude exists at resolved path: {os.path.exists(claude_path)}")
                self.log.info(f"[DEBUG] Claude is file: {os.path.isfile(claude_path)}")

            # Log prompt details
            self.log.info(f"[DEBUG] Prompt length: {len(prompt)} characters")
            self.log.info(f"[DEBUG] Prompt preview (first 200 chars):")
            self.log.info(f"  {prompt[:200]}...")

            self.log.info("=" * 80)

            try:
                process = subprocess.Popen(
                    cmd
                    cwd=str(self.workspace),  # Claude runs from workspace
                    env=env,  # Isolated environment
                    stdout=stdout_pipe
                    stderr=stderr_pipe
                    stdin=subprocess.DEVNULL,  # Prevent hanging on input
                    text=True
                    bufsize=1
                )
                self.log.info(f"[DEBUG] Subprocess started with PID: {process.pid}")
                self.log.info(f"[DEBUG] Process poll status: {process.poll()}")

                # Give process a moment to fail if it's going to fail immediately
                import time

                time.sleep(0.5)
                initial_poll = process.poll()
                if initial_poll is not None:
                    self.log.error(f"[ERROR] Process died immediately with exit code: {initial_poll}")
                    # Try to capture any error output
                    if is_real_pipe and process.stderr:
                        stderr_output = process.stderr.read()
                        self.log.error(f"[ERROR] Stderr output: {stderr_output}")
                else:
                    self.log.info(f"[DEBUG] Process still alive after 0.5s")

                # Stream output and analyze Claude's responses
                # Handle both piped (stdout=PIPE) and non-piped (stdout=DEVNULL) modes
                self.log.info(f"[DEBUG] process.stdout = {process.stdout}")

                # Check if we have a real pipe (not DEVNULL)
                # On Windows, stdout will be None when using DEVNULL
                is_real_pipe = process.stdout is not None and hasattr(process.stdout, "readline")

                self.log.info(f"[DEBUG] is_real_pipe = {is_real_pipe}")

                if is_real_pipe:
                    # Read output for monitoring and JSON parsing
                    while True:
                        line = process.stdout.readline()
                        if not line:
                            # Check if process has exited
                            poll_result = process.poll()
                            if poll_result is not None:
                                exit_code = poll_result
                                self.log.info(f"[DEBUG] Process exited with code: {exit_code}")
                                break
                            # No more output but process still running, wait a bit
                            import time

                            time.sleep(0.1)
                            continue

                        output_lines.append(line.rstrip())
                        transcript_lines.append(line.rstrip())  # Capture for database
                        if log_fp:
                            log_fp.write(line)
                            log_fp.flush()  # Ensure immediate write

                        # Live output to terminal if enabled
                        if self.live_output:
                            formatted = self._format_live_output(line)
                            if formatted:
                                logger.info(formatted)

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
                else:
                    # Non-piped mode (Windows with DEVNULL): just wait for process completion
                    self.log.info(f"[DEBUG] Non-piped mode: monitoring process completion only")
                    import time

                    while True:
                        poll_result = process.poll()
                        if poll_result is not None:
                            exit_code = poll_result
                            self.log.info(f"[DEBUG] Process exited with code: {exit_code}")
                            break
                        time.sleep(0.5)  # Check every 500ms

                # Process should have already exited in the loop above
                if exit_code is None:
                    # Wait for completion with timeout (10 minutes max)
                    self.log.info(f"[DEBUG] Process still running, waiting for exit...")
                    try:
                        exit_code = process.wait(timeout=600)
                        self.log.info(f"[DEBUG] Process completed with exit code: {exit_code}")
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

                # Temp file handling removed - using pipes now

                # Save final status to log and transcript
                exit_status_line = f"\n\n=== EXIT CODE: {exit_code} ==="
                transcript_lines.append(exit_status_line)
                if log_fp:
                    log_fp.write(f"{exit_status_line}\n")
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
                    "status": "success" if success else "failed"
                    "notes": status_notes
                    "next_state": "completed" if success else "failed"
                    "files": files_changed
                    "claude_completed": claude_completed
                    "exit_code": exit_code
                    "output_lines": len(output_lines)
                    "transcript": "\n".join(transcript_lines),  # Include full transcript for database
                }

        except Exception as e:
            self.log.error(f"[ERROR] Claude execution failed: {e}")
            return {
                "status": "failed"
                "notes": f"Execution error: {str(e)}"
                "next_state": "failed"
            }

    def emit_result(self, result: Dict[str, Any]) -> None:
        """Save execution result"""
        if not self.task_id or not self.run_id:
            logger.error("[ERROR] Cannot emit result - missing task_id or run_id")
            return

        # Extract transcript before adding to result_data
        transcript = result.pop("transcript", None)  # Remove from result to avoid duplication

        # Prepare result data
        result_data = {
            "task_id": self.task_id
            "run_id": self.run_id
            "worker": self.worker_id
            "phase": self.phase
            "workspace": str(self.workspace)
            "timestamp": datetime.now(timezone.utc).isoformat()
            **result
        }

        # Save result to database
        status = result.get("status", "unknown")
        error_message = result.get("error") if status == "failed" else None

        try:
            success = hive_core_db.log_run_result(
                run_id=self.run_id
                status=status
                result_data=result_data
                error_message=error_message
                transcript=transcript,  # Pass transcript to database
            )

            if success:
                self.log.info(f"[RESULT] Saved to database: run_id={self.run_id}, status={status}")
            else:
                self.log.error(f"[ERROR] Failed to save result to database: run_id={self.run_id}")

        except Exception as e:
            self.log.error(f"[ERROR] Database save failed: {e}")

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with streamlined workflow"""
        task_id = task["id"]
        title = task.get("title", task_id)

        self.log.info(f"Executing task: {title}")

        # Create prompt
        prompt = self.create_prompt(task)
        logger.info(f"         [INFO] Using inline prompt")

        # Run Claude
        result = self.run_claude(prompt)

        # Emit result
        self.emit_result(result)

        return result

    def run_one_shot(self) -> None:
        """Run in one-shot mode (called by Queen)"""
        if not self.task_id:
            logger.error("[ERROR] One-shot mode requires task_id")
            return {
                "status": "failed"
                "notes": "Missing task_id"
                "next_state": "failed"
            }

        # Load task
        task = self.load_task(self.task_id)
        if not task:
            error_msg = f"Task {self.task_id} not found"
            logger.error(f"[ERROR] {error_msg}")
            return {"status": "failed", "notes": error_msg, "next_state": "failed"}

        # Execute task
        return self.execute_task(task)

    async def run_one_shot_async(self) -> None:
        """Run in async one-shot mode for 3-5x performance improvement"""
        if not self.task_id:
            logger.error("[ERROR] Async one-shot mode requires task_id")
            return {
                "status": "failed"
                "notes": "Missing task_id"
                "next_state": "failed"
            }

        # Initialize async worker if not already done
        if self._async_worker is None:
            try:
                # Import AsyncWorkerCore dynamically to avoid import issues
                from scripts.async_worker import AsyncWorkerCore

                self._async_worker = AsyncWorkerCore(self.worker_id)
                await self._async_worker.initialize()
                self.log.info("[ASYNC] Async worker initialized successfully")
            except ImportError as e:
                self.log.error(f"[ERROR] AsyncWorkerCore not available: {e}")
                # Fall back to sync execution
                self.log.info("[FALLBACK] Falling back to sync execution")
                return self.run_one_shot()
            except Exception as e:
                self.log.error(f"[ERROR] Failed to initialize async worker: {e}")
                # Fall back to sync execution
                return self.run_one_shot()

        # Execute task asynchronously
        try:
            result = await self._async_worker.process_task(self.task_id, self.run_id)
            self.log.info(f"[ASYNC] Task completed with status: {result.get('status')}")
            return result
        except Exception as e:
            self.log.error(f"[ERROR] Async task execution failed: {e}")
            return {
                "status": "failed"
                "notes": f"Async execution error: {str(e)}"
                "next_state": "failed"
            }


def main() -> None:
    """Main CLI entry point"""

    parser = argparse.ArgumentParser(description="WorkerCore - Streamlined Worker")
    parser.add_argument("worker_id", help="Worker ID (backend, frontend, infra)")
    parser.add_argument("--one-shot", action="store_true", help="One-shot mode for Queen")
    parser.add_argument(
        "--local"
        action="store_true"
        help="Local development mode - run task directly without Queen"
    )
    parser.add_argument("--task-id", help="Task ID (required for one-shot and local modes)")
    parser.add_argument("--run-id", help="Run ID for this execution (auto-generated in local mode)")
    parser.add_argument("--async", action="store_true", help="Enable async processing for 3-5x performance improvement")
    parser.add_argument("--workspace", help="Workspace directory")
    parser.add_argument(
        "--phase"
        choices=["plan", "apply", "test"]
        default="apply"
        help="Execution phase"
    )
    parser.add_argument(
        "--mode"
        choices=["fresh", "repo"]
        default="fresh"
        help="Workspace mode: fresh (empty directory) or repo (git worktree)"
    )
    parser.add_argument(
        "--live"
        action="store_true"
        help="Enable live streaming output to terminal (shows Claude messages, commands, and results)"
    )

    args = parser.parse_args()

    # Configure logging based on worker ID and task
    log_name = f"worker-{args.worker_id}"
    if args.task_id:
        log_name += f"-{args.task_id}"

    # Make log path absolute + centralized (before any chdir operations)
    centralized_log = LOGS_DIR / f"{log_name}.log"
    ensure_directory(LOGS_DIR)  # Ensure logs directory exists
    setup_logging(name=log_name, log_to_file=True, log_file_path=str(centralized_log))
    log = get_logger(__name__)

    # Validate local mode arguments
    if args.local:
        if not args.task_id:
            logger.error("[ERROR] Local mode requires --task-id to be specified")
            logger.info("\nUsage example:")
            logger.info("  python worker.py backend --local --task-id hello_hive --phase apply")
            sys.exit(1)

        # Generate run_id if not provided in local mode
        if not args.run_id:
            args.run_id = f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"[INFO] Generated run_id for local mode: {args.run_id}")

    # Create worker with error handling
    try:
        worker = WorkerCore(
            worker_id=args.worker_id
            task_id=args.task_id
            run_id=args.run_id
            workspace=args.workspace
            phase=args.phase
            mode=args.mode
            live_output=args.live
            async_mode=getattr(args, "async", False)
        )
        log.info(f"Worker {args.worker_id} initialized successfully for task {args.task_id}")
    except Exception as e:
        log.error(f"Failed to initialize worker: {e}")
        log.error(f"Worker ID: {args.worker_id}, Task ID: {args.task_id}")
        log.error(f"Mode: {args.mode}, Phase: {args.phase}")
        import traceback

        log.error(traceback.format_exc())
        sys.exit(2)

    if args.one_shot or args.local:
        # One-shot execution for Queen or local development
        if args.local:
            logger.info(f"[INFO] Running in LOCAL DEVELOPMENT MODE")
            logger.info(f"[INFO] Task: {args.task_id}, Phase: {args.phase}")

        # Check if async mode is enabled
        if getattr(args, "async", False):
            logger.info(f"[INFO] Running in ASYNC MODE for 3-5x performance improvement")
            # Run async version
            result = asyncio.run(worker.run_one_shot_async())
        else:
            # Run sync version
            result = worker.run_one_shot()

        sys.exit(0 if result.get("status") == "success" else 1)
    else:
        logger.info("Interactive mode not implemented - use --one-shot or --local")
        sys.exit(1)


if __name__ == "__main__":
    main()

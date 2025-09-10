#!/usr/bin/env python3
"""
Claude Code Worker - Production-Ready Headless MAS
Robust worker with atomic operations, stale lock recovery, and deterministic parsing
"""

import json
import subprocess
import sys
import time
import shutil
import traceback
import os
import errno
import signal
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Set

# Allowed task states (normalized lifecycle)
ALLOWED_STATES = {
    "queued",        # Initial state, waiting for assignment
    "assigned",      # Claimed by worker
    "in_progress",   # Worker actively executing
    "testing",       # Running tests
    "reviewing",     # Code review phase
    "pr_open",       # Pull request created
    "completed",     # Successfully done
    "failed",        # Task failed
    "blocked",       # Task blocked by external dependency
}

# Capability mapping for proper routing
CAPABILITY_MAP = {
    "backend": {"backend", "python", "flask", "fastapi", "api", "sqlalchemy", "pytest", "database"},
    "frontend": {"frontend", "react", "javascript", "ui", "ui_components", "nextjs", "typescript"},
    "infra": {"infra", "docker", "deployment", "monitoring", "kubernetes", "cicd", "infrastructure"},
    "queen": {"planning", "architecture", "coordination", "orchestration"}
}

class CCWorker:
    """Production-ready worker with robust error handling and atomic operations"""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.root = Path.cwd()
        self.hive_dir = self.root / "hive"
        self.workers_dir = self.hive_dir / "workers"
        self.tasks_file = self.hive_dir / "bus" / "tasks.json"
        self.worker_file = self.workers_dir / f"{worker_id}.json"
        self.logs_dir = self.hive_dir / "logs"
        self.locks_dir = self.hive_dir / "bus" / "locks"
        self.events_file = self.get_events_file()
        
        # Task execution state
        self.current_task_id: Optional[str] = None
        self.task_start_time: Optional[datetime] = None
        
        # Ensure directories exist
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.events_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load/create worker configuration
        self.config = self.load_or_create_config()
        
        # Find claude command (allow env override)
        self.claude_cmd = self.find_claude_command()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._graceful_shutdown)
        signal.signal(signal.SIGINT, self._graceful_shutdown)
        
        # Clean up any stale locks from previous runs
        self.cleanup_stale_locks()
        
        # Status output
        self.print_status("INITIALIZED", f"Worker {worker_id} ready")
        self.print_info(f"Role: {self.config.get('role', 'general')}")
        self.print_info(f"Capabilities: {', '.join(self.config.get('capabilities', []))}")
        self.print_info(f"Claude: {self.claude_cmd if self.claude_cmd else 'SIMULATION MODE'}")
        
        # Emit startup event
        self.emit_event(type="worker_started", role=self.config.get('role'))
    
    def get_events_file(self) -> Path:
        """Get events file with daily rotation"""
        date_suffix = datetime.now().strftime("%Y%m%d")
        return self.hive_dir / "bus" / f"events_{date_suffix}.jsonl"
    
    def _graceful_shutdown(self, signum, frame):
        """Handle graceful shutdown on SIGTERM/SIGINT"""
        self.print_status("SHUTDOWN", f"Received signal {signum}, shutting down gracefully")
        
        # Release current task lock if held
        if self.current_task_id:
            self.release_task_lock(self.current_task_id)
            self.emit_event(type="task_abandoned", task_id=self.current_task_id, reason="worker_shutdown")
        
        # Emit shutdown event
        self.emit_event(type="worker_stopped", total_tasks=self.config.get('total_tasks_completed', 0))
        
        # Update worker status
        self.config["status"] = "stopped"
        self.save_config()
        
        sys.exit(0)
    
    def print_status(self, status: str, message: str):
        """Print formatted status message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        try:
            print(f"[{timestamp}] [{status}] {message}")
        except UnicodeEncodeError:
            # Fallback for Windows console that can't handle Unicode
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            print(f"[{timestamp}] [{status}] {safe_message}")
        sys.stdout.flush()
    
    def print_info(self, message: str):
        """Print info message"""
        try:
            print(f"         [INFO] {message}")
        except UnicodeEncodeError:
            # Fallback for Windows console
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            print(f"         [INFO] {safe_message}")
        sys.stdout.flush()
    
    def print_error(self, message: str):
        """Print error message"""
        try:
            print(f"         [ERROR] {message}")
        except UnicodeEncodeError:
            # Fallback for Windows console
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            print(f"         [ERROR] {safe_message}")
        sys.stdout.flush()
    
    def atomic_write_json(self, path: Path, obj: dict):
        """Atomically write JSON to prevent race conditions"""
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(str(tmp), str(path))  # Atomic on POSIX & modern Windows
        except Exception as e:
            # Clean up temp file on error
            tmp.unlink(missing_ok=True)
            raise e
    
    def emit_event(self, **kwargs):
        """Emit event to the event bus with rotation support"""
        try:
            kwargs.setdefault("ts", datetime.now(timezone.utc).isoformat())
            kwargs.setdefault("worker", self.worker_id)
            
            # Check if we need to rotate (new day)
            current_events_file = self.get_events_file()
            if current_events_file != self.events_file:
                self.events_file = current_events_file
            
            with open(self.events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(kwargs) + "\n")
                f.flush()
        except Exception as e:
            self.print_error(f"Failed to emit event: {e}")
    
    def cleanup_stale_locks(self):
        """Clean up stale locks older than 30 minutes"""
        try:
            stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=30)
            
            for lock_file in self.locks_dir.glob("*.lock"):
                try:
                    # Read lock content to check ownership and timestamp
                    with open(lock_file, "r", encoding="utf-8") as f:
                        lock_data = json.load(f)
                    
                    lock_ts = datetime.fromisoformat(lock_data.get("ts", "1970-01-01T00:00:00+00:00"))
                    
                    # Clean up if stale
                    if lock_ts < stale_threshold:
                        self.print_info(f"Cleaning stale lock: {lock_file.name} (owned by {lock_data.get('worker', 'unknown')})")
                        lock_file.unlink(missing_ok=True)
                        
                except Exception:
                    # If we can't parse the lock, check file modification time
                    mtime = datetime.fromtimestamp(lock_file.stat().st_mtime, tz=timezone.utc)
                    if mtime < stale_threshold:
                        self.print_info(f"Cleaning stale lock (old format): {lock_file.name}")
                        lock_file.unlink(missing_ok=True)
                        
        except Exception as e:
            self.print_error(f"Error during stale lock cleanup: {e}")
    
    def claim_task_lock(self, task_id: str) -> bool:
        """Atomically claim a task lock with metadata"""
        lock_file = self.locks_dir / f"{task_id}.lock"
        
        try:
            # Try to create lock file exclusively
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            
            # Write lock metadata
            lock_data = {
                "worker": self.worker_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid()
            }
            os.write(fd, json.dumps(lock_data).encode())
            os.close(fd)
            
            self.current_task_id = task_id
            return True
            
        except OSError as e:
            if e.errno == errno.EEXIST:
                # Lock exists, check if stale
                try:
                    with open(lock_file, "r", encoding="utf-8") as f:
                        lock_data = json.load(f)
                    
                    lock_ts = datetime.fromisoformat(lock_data.get("ts", "1970-01-01T00:00:00+00:00"))
                    
                    # If lock is stale (>30 min), try to claim it
                    if datetime.now(timezone.utc) - lock_ts > timedelta(minutes=30):
                        self.print_info(f"Attempting to claim stale lock for task {task_id}")
                        lock_file.unlink(missing_ok=True)
                        return self.claim_task_lock(task_id)  # Recursive retry
                        
                except Exception:
                    pass
                
                return False
            raise
    
    def release_task_lock(self, task_id: str):
        """Release task lock"""
        try:
            (self.locks_dir / f"{task_id}.lock").unlink(missing_ok=True)
            if self.current_task_id == task_id:
                self.current_task_id = None
        except Exception:
            pass
    
    def parse_final_json(self, lines: List[str]) -> Dict[str, Any]:
        """Parse the final JSON output using FINAL_JSON: marker"""
        # Look for FINAL_JSON: marker in last 200 lines
        for line in reversed(lines[-200:] if len(lines) > 200 else lines):
            s = line.strip()
            if s.startswith("FINAL_JSON:"):
                try:
                    return json.loads(s.split("FINAL_JSON:", 1)[1].strip())
                except Exception:
                    self.print_error(f"Failed to parse JSON after FINAL_JSON marker: {s}")
                    return {}
        
        # Fallback for old format (temporary compatibility)
        self.print_info("No FINAL_JSON marker found, attempting legacy parsing")
        for line in reversed(lines[-50:] if len(lines) > 50 else lines):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except:
                    pass
        
        return {}
    
    def find_claude_command(self) -> Optional[str]:
        """Find the claude command - check env, local, then system"""
        try:
            # Check environment variable override
            if os.environ.get("CLAUDE_BIN"):
                claude_cmd = os.environ["CLAUDE_BIN"]
                if Path(claude_cmd).exists() or shutil.which(claude_cmd):
                    return claude_cmd
            
            # Check for local claude files
            for claude_file in ["claude.bat", "claude.sh", "claude"]:
                local_claude = self.root / claude_file
                if local_claude.exists():
                    return str(local_claude.resolve())
            
            # Check system PATH
            claude_cmd = shutil.which("claude")
            if claude_cmd:
                return claude_cmd
            
            self.print_error("Claude CLI not found - will simulate execution")
            return None
            
        except Exception as e:
            self.print_error(f"Error finding Claude: {e}")
            return None
    
    def get_normalized_capabilities(self) -> Set[str]:
        """Get normalized capability set for matching"""
        capabilities = set()
        for cap in self.config.get("capabilities", []):
            cap_lower = cap.lower()
            # Add the capability itself
            capabilities.add(cap_lower)
            # Add any mapped capabilities
            for role, mapped_caps in CAPABILITY_MAP.items():
                if cap_lower == role or cap_lower in mapped_caps:
                    capabilities.update(mapped_caps)
        return capabilities
    
    def load_or_create_config(self) -> Dict[str, Any]:
        """Load or create worker configuration"""
        try:
            if self.worker_file.exists():
                with open(self.worker_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    # Ensure capabilities list exists
                    if "capabilities" not in config:
                        config["capabilities"] = CAPABILITY_MAP.get(self.worker_id, [self.worker_id])
                    return config
            else:
                # Create default config based on worker type
                config = {
                    "worker_id": self.worker_id,
                    "role": f"{self.worker_id}_developer",
                    "status": "idle",
                    "current_task": None,
                    "capabilities": list(CAPABILITY_MAP.get(self.worker_id, [self.worker_id])),
                    "is_enabled": True,
                    "total_tasks_completed": 0,
                    "workdir": f"./workspaces/{self.worker_id}",
                    "config": {
                        "claude_args": self.get_claude_args_for_role()
                    }
                }
                
                self.save_config(config)
                return config
                
        except Exception as e:
            self.print_error(f"Config error: {e}")
            # Return minimal config on error
            return {
                "worker_id": self.worker_id,
                "capabilities": list(CAPABILITY_MAP.get(self.worker_id, [self.worker_id])),
                "is_enabled": True,
                "config": {}
            }
    
    def get_claude_args_for_role(self) -> List[str]:
        """Get appropriate Claude args based on worker role"""
        base_args = ["--output-format", "stream-json"]
        
        # Role-specific tool restrictions
        tool_configs = {
            "backend": [
                "--allowedTools",
                "Bash(python,pip,pytest,git,cat,ls,mkdir,echo),Read(*),Write(*),Edit(*),MultiEdit(*)"
            ],
            "frontend": [
                "--allowedTools",
                "Bash(npm,node,jest,git,cat,ls,mkdir,echo),Read(*),Write(*),Edit(*),MultiEdit(*)"
            ],
            "infra": [
                "--allowedTools",
                "Bash(docker,kubectl,helm,git,cat,ls,mkdir,echo,sh),Read(*),Write(*),Edit(*),MultiEdit(*)"
            ],
            "queen": [
                # Queen gets broader access for orchestration
                "--dangerously-skip-permissions"
            ]
        }
        
        return base_args + tool_configs.get(self.worker_id, ["--dangerously-skip-permissions"])
    
    def save_config(self, config: Dict[str, Any] = None):
        """Save worker configuration atomically"""
        try:
            if config:
                self.config = config
            
            self.config["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
            
            # Ensure directory exists
            self.workers_dir.mkdir(parents=True, exist_ok=True)
            
            # Use atomic write
            self.atomic_write_json(self.worker_file, self.config)
                
        except Exception as e:
            self.print_error(f"Failed to save config: {e}")
    
    def load_tasks(self) -> Dict[str, Any]:
        """Load task queue with error handling"""
        try:
            if not self.tasks_file.exists():
                return {"tasks": [], "task_counter": 0}
            
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                return json.load(f)
                
        except Exception as e:
            self.print_error(f"Failed to load tasks: {e}")
            return {"tasks": [], "task_counter": 0}
    
    def save_tasks(self, task_data: Dict[str, Any]):
        """Save task queue atomically"""
        try:
            task_data["last_updated"] = datetime.now(timezone.utc).isoformat()
            
            # Ensure directory exists
            self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Use atomic write
            self.atomic_write_json(self.tasks_file, task_data)
                
        except Exception as e:
            self.print_error(f"Failed to save tasks: {e}")
    
    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """Get next available task - resume in-progress or claim new"""
        try:
            task_data = self.load_tasks()
            my_capabilities = self.get_normalized_capabilities()
            
            # First, check for tasks we were already working on (resume on restart)
            for task in task_data.get("tasks", []):
                if (task.get("status") in ("assigned", "in_progress") and
                    task.get("assignee") == self.worker_id):
                    self.print_info(f"Resuming task {task['id']} that was already assigned to us")
                    return task
            
            # Then look for new queued tasks matching our capabilities
            for task in task_data.get("tasks", []):
                if task.get("status") == "queued":
                    task_tags = set(tag.lower() for tag in task.get("tags", []))
                    
                    # Check if any of our capabilities match any task tag
                    if my_capabilities & task_tags:
                        return task
            
            return None
            
        except Exception as e:
            self.print_error(f"Error getting task: {e}")
            return None
    
    def advance_task_state(self, task_id: str, summary: Dict[str, Any]):
        """Advance task to next state based on summary"""
        next_state = summary.get("next_state", "")
        
        # Validate and normalize state
        if next_state not in ALLOWED_STATES:
            # Map common variations
            state_map = {
                "success": "completed",
                "done": "completed",
                "error": "failed",
                "fail": "failed"
            }
            next_state = state_map.get(next_state, "failed")
        
        # Update task with new state
        self.update_task_status(
            task_id,
            next_state,
            result=summary,
            pr=summary.get("pr", ""),
            notes=summary.get("notes", "")
        )
        
        # Emit appropriate event
        event_data = {
            "type": f"task_{next_state}",
            "task_id": task_id,
            "pr": summary.get("pr", "")
        }
        
        if next_state == "completed":
            event_data["duration_ms"] = int((datetime.now(timezone.utc) - self.task_start_time).total_seconds() * 1000) if self.task_start_time else 0
        elif next_state == "failed":
            event_data["reason"] = summary.get("notes", "Unknown reason")
        
        self.emit_event(**event_data)
    
    def update_task_status(self, task_id: str, status: str, **kwargs):
        """Update task status atomically"""
        try:
            task_data = self.load_tasks()
            
            for i, t in enumerate(task_data["tasks"]):
                if t["id"] == task_id:
                    task_data["tasks"][i]["status"] = status
                    task_data["tasks"][i]["updated_at"] = datetime.now(timezone.utc).isoformat()
                    
                    # Add any additional fields
                    for key, value in kwargs.items():
                        if value is not None:  # Only add non-None values
                            task_data["tasks"][i][key] = value
                    
                    # Add timestamp fields for specific states
                    if status == "completed":
                        task_data["tasks"][i]["completed_at"] = datetime.now(timezone.utc).isoformat()
                    elif status == "failed":
                        task_data["tasks"][i]["failed_at"] = datetime.now(timezone.utc).isoformat()
                    elif status == "in_progress" and "started_at" not in task_data["tasks"][i]:
                        task_data["tasks"][i]["started_at"] = datetime.now(timezone.utc).isoformat()
                    
                    break
            
            self.save_tasks(task_data)
            
        except Exception as e:
            self.print_error(f"Failed to update task status: {e}")
    
    def create_task_prompt(self, task: Dict[str, Any]) -> str:
        """Create a prompt for Claude with FINAL_JSON protocol"""
        role = self.config.get("role", "developer")
        
        # Verbose logging of task details
        self.print_status("PROMPT", "Creating Claude prompt")
        self.print_info(f"Task ID: {task.get('id', 'unknown')}")
        self.print_info(f"Title: {task['title']}")
        self.print_info(f"Description: {task.get('description', 'No description')}")
        self.print_info("Acceptance Criteria:")
        acceptance = task.get('acceptance') or task.get('acceptance_criteria') or ['Complete the task']
        for criteria in acceptance:
            self.print_info(f"  ✓ {criteria}")
        
        prompt = f"""You are a {role} working headlessly on the Hive system.

TASK: {task['title']} (ID: {task.get('id', 'unknown')})
DESCRIPTION: {task.get('description', 'No description')}

ACCEPTANCE:
{chr(10).join('- ' + c for c in acceptance)}

Rules:
- Create actual working code/configuration files
- Keep diffs small and coherent
- Write/update tests to meet acceptance criteria
- Commit with a clear message including task ID: {task.get('id', 'unknown')}
- If appropriate, create a PR using GitHub CLI and include its URL

IMPORTANT: At the very end of your response, print EXACTLY ONE LINE prefixed by 'FINAL_JSON: ':
FINAL_JSON: {{"status":"success|failed|blocked","notes":"<brief summary>","pr":"<PR URL or empty>","next_state":"completed|testing|reviewing|pr_open|failed|blocked"}}
"""
        
        return prompt
    
    def execute_with_claude(self, task: Dict[str, Any], retry_count: int = 0) -> Dict[str, Any]:
        """Execute task using Claude with robust error handling"""
        try:
            self.print_status("EXECUTING", f"🎯 Task: {task['title']}")
            
            # Track execution time
            if retry_count == 0:
                self.task_start_time = datetime.now(timezone.utc)
            
            # Check if we've exceeded max execution time (20 minutes)
            if self.task_start_time and (datetime.now(timezone.utc) - self.task_start_time) > timedelta(minutes=20):
                self.print_error("⏱️ Task exceeded 20 minute time limit")
                return {
                    "status": "blocked",
                    "message": "Task timeout - exceeded 20 minute limit",
                    "summary": {"status": "blocked", "notes": "Task timeout after 20 minutes", "next_state": "blocked"}
                }
            
            # Create workspace directory
            workspace = Path(self.config.get("workdir", f"workspaces/{self.worker_id}"))
            if not workspace.is_absolute():
                workspace = self.root / workspace
            workspace.mkdir(parents=True, exist_ok=True)
            
            if not self.claude_cmd:
                # Simulation mode with proper JSON output
                self.print_info("📦 Simulating Claude execution (CLI not found)")
                time.sleep(3)
                
                simulated_json = {
                    "status": "blocked",
                    "notes": "[SIMULATED] CLI missing - cannot execute task",
                    "pr": "",
                    "next_state": "blocked"
                }
                
                return {
                    "status": "blocked",
                    "message": "Claude CLI not available",
                    "summary": simulated_json
                }
            
            # Build Claude command with appropriate args
            prompt = self.create_task_prompt(task)
            
            # Get Claude args from config or use defaults
            claude_args = self.config.get("config", {}).get("claude_args", self.get_claude_args_for_role())
            
            cmd = [self.claude_cmd] + claude_args + [
                "--add-dir", str(workspace),
                "-p", prompt
            ]
            
            self.print_status("COMMAND", "Executing Claude in headless mode")
            self.print_info(f"📂 Workspace: {workspace}")
            self.print_info(f"⏱️  Started: {datetime.now().strftime('%H:%M:%S')}")
            if retry_count > 0:
                self.print_info(f"🔄 Retry attempt: {retry_count}")
            
            # Log file for output
            log_file = self.logs_dir / f"{self.worker_id}_{task['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            lines: List[str] = []
            
            # Execute with streaming output
            self.print_status("RUNNING", "Claude is working...")
            self.emit_event(type="task_execution_start", task_id=task["id"], retry=retry_count, workspace=str(workspace))
            
            with subprocess.Popen(
                cmd,
                cwd=str(workspace),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            ) as process, open(log_file, "w", encoding="utf-8") as lf:
                
                # Stream and log output
                for line in process.stdout:
                    lf.write(line)
                    lf.flush()
                    lines.append(line)
                    
                    # Echo relevant lines to console for monitoring
                    if any(x in line for x in ['"type":"tool"', '"status"', '"error"', 'ERROR', 'Failed', 'FINAL_JSON:']):
                        self.print_info(f"   📝 {line.strip()[:150]}")
                
                # Wait for completion with timeout
                rc = process.wait(timeout=600)  # 10 minute timeout
            
            self.print_info(f"⏱️  Completed: {datetime.now().strftime('%H:%M:%S')}")
            
            # Parse the final JSON output
            summary = self.parse_final_json(lines)
            
            # Determine success based on return code and JSON
            if rc == 0 and summary.get("status") in ["success", "blocked"]:
                self.print_status("SUCCESS", f"✅ {summary.get('notes', 'Task completed')}")
                if summary.get("pr"):
                    self.print_info(f"🔗 PR created: {summary['pr']}")
                
                return {
                    "status": summary.get("status", "success"),
                    "message": summary.get("notes", "Task completed"),
                    "summary": summary
                }
            else:
                msg = summary.get("notes") or f"Claude exited with code {rc}"
                self.print_error(f"❌ {msg}")
                
                # Check if we should retry
                if retry_count < 2:  # Max 3 attempts
                    wait_time = 15 * (2 ** retry_count)  # Exponential backoff: 15s, 30s
                    self.print_info(f"⏳ Retrying in {wait_time} seconds...")
                    self.emit_event(type="retry_scheduled", task_id=task["id"], wait_seconds=wait_time, attempt=retry_count+2)
                    time.sleep(wait_time)
                    return self.execute_with_claude(task, retry_count + 1)
                
                return {
                    "status": "failed",
                    "message": msg,
                    "summary": summary or {"status": "failed", "notes": msg, "next_state": "failed"}
                }
                
        except subprocess.TimeoutExpired:
            self.print_error("⏱️ Claude execution timeout (10 minutes)")
            self.emit_event(type="task_timeout", task_id=task["id"], duration_seconds=600)
            
            if retry_count < 1:  # One retry for timeouts
                self.print_info("⏳ Retrying after timeout...")
                time.sleep(30)
                return self.execute_with_claude(task, retry_count + 1)
            
            return {
                "status": "failed",
                "message": "Execution timeout after retries",
                "summary": {"status": "failed", "notes": "Execution timeout", "next_state": "failed"}
            }
            
        except Exception as e:
            self.print_error(f"💥 Execution error: {e}")
            self.emit_event(type="task_error", task_id=task["id"], error=str(e))
            return {
                "status": "failed",
                "message": str(e),
                "summary": {"status": "failed", "notes": str(e), "next_state": "failed"}
            }
    
    def work_cycle(self):
        """Single work cycle with full error handling"""
        try:
            # Update heartbeat
            self.config["status"] = "idle"
            self.save_config()
            
            # Emit heartbeat event periodically
            self.emit_event(type="heartbeat", status="idle")
            
            # Look for task
            task = self.get_next_task()
            
            if task:
                # Check if we need to reclaim lock (for resumed tasks)
                if task.get("status") in ("assigned", "in_progress") and task.get("assignee") == self.worker_id:
                    # Re-claim lock if it doesn't exist (after restart)
                    if not (self.locks_dir / f"{task['id']}.lock").exists():
                        if not self.claim_task_lock(task["id"]):
                            self.print_error(f"Failed to reclaim lock for resumed task {task['id']}")
                            return
                else:
                    # Try to atomically claim new task
                    if not self.claim_task_lock(task["id"]):
                        self.print_info(f"🔒 Task {task['id']} already claimed by another worker")
                        return
               
                try:
                    self.print_status("TASK FOUND", f"🎯 {task['id']}: {task['title']}")
                    self.print_info(f"Priority: {task.get('priority', 'normal')}")
                    self.print_info(f"Tags: {', '.join(task.get('tags', []))}")
                    self.print_info(f"Estimated effort: {task.get('estimated_effort', 'unknown')}")
                    
                    # Emit claim event
                    self.emit_event(type="task_claim", task_id=task["id"], title=task["title"])
                    
                    # Assign task if not already assigned
                    if task.get("status") == "queued":
                        self.print_status("ASSIGNING", f"Claiming task {task['id']} for {self.worker_id}")
                        self.update_task_status(task["id"], "assigned", assignee=self.worker_id)
                        self.emit_event(type="task_assign", task_id=task["id"], assignee=self.worker_id)
                        self.print_info("✅ Task successfully assigned")
                    
                except Exception as e:
                    self.print_error(f"Failed to assign task: {e}")
                    self.release_task_lock(task["id"])
                    return
                
                # Update worker status
                self.config["status"] = "working"
                self.config["current_task"] = task["id"]
                self.save_config()
                
                # Update task to in_progress
                self.update_task_status(task["id"], "in_progress")
                self.emit_event(type="task_in_progress", task_id=task["id"])
                
                # Execute
                result = self.execute_with_claude(task)
                
                # Update based on result using normalized state transitions
                if "summary" in result:
                    self.advance_task_state(task["id"], result["summary"])
                else:
                    # Fallback for missing summary
                    if result["status"] == "success":
                        self.update_task_status(task["id"], "completed", result=result.get("message", ""))
                        self.emit_event(type="task_complete", task_id=task["id"])
                    else:
                        self.update_task_status(task["id"], "failed", failure_reason=result.get("message", "Unknown"))
                        self.emit_event(type="task_fail", task_id=task["id"], reason=result.get("message", "Unknown"))
                
                # Update completion stats
                if result["status"] == "success":
                    self.config["total_tasks_completed"] = self.config.get("total_tasks_completed", 0) + 1
                    self.print_status("COMPLETED", f"🎆 Successfully completed task {task['id']}!")
                    self.print_info(f"📋 Total tasks completed by this worker: {self.config['total_tasks_completed']}")
                else:
                    self.print_status("FAILED", f"❌ Task {task['id']} failed")
                    self.print_info(f"Failure reason: {result.get('message', 'Unknown')}")
                
                self.print_info("="*60)
                
                # Release lock
                self.release_task_lock(task["id"])
                
                # Reset worker
                self.config["status"] = "idle"
                self.config["current_task"] = None
                self.save_config()
                
            else:
                caps = list(self.get_normalized_capabilities())[:5]  # Show first 5 capabilities
                self.print_info(f"🔍 No tasks available for capabilities: {', '.join(caps)}...")
                
        except Exception as e:
            self.print_error(f"Work cycle error: {e}")
            self.emit_event(type="worker_error", error=str(e))
            
            # Release lock if held
            if self.current_task_id:
                self.release_task_lock(self.current_task_id)
            
            # Reset worker status on error
            try:
                self.config["status"] = "idle"
                self.config["current_task"] = None
                self.save_config()
            except:
                pass
    
    def run_forever(self, cycle_seconds: int = 10):
        """Run forever with error recovery"""
        self.print_status("STARTING", f"Worker {self.worker_id} - checking every {cycle_seconds}s")
        print("="*60)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                self.print_status(f"CYCLE {cycle_count}", datetime.now().strftime('%H:%M:%S'))
                
                # Run work cycle
                self.work_cycle()
                
                # Wait for next cycle
                self.print_info(f"Next check in {cycle_seconds} seconds...")
                time.sleep(cycle_seconds)
                
            except KeyboardInterrupt:
                self.print_status("SHUTDOWN", "User requested stop")
                break
                
            except Exception as e:
                # Catch ANY error and continue running
                self.print_error(f"Unexpected error: {e}")
                self.emit_event(type="worker_error", error=str(e), traceback=traceback.format_exc())
                self.print_info(f"Recovering... next check in {cycle_seconds} seconds")
                time.sleep(cycle_seconds)
        
        # Final status
        self.print_status("STOPPED", f"Worker {self.worker_id} shut down")
        self.print_info(f"Total tasks completed: {self.config.get('total_tasks_completed', 0)}")

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python cc_worker.py <worker_id> [cycle_seconds]")
        print("  worker_id: backend, frontend, infra, or queen")
        print("  cycle_seconds: How often to check for tasks (default: 10)")
        print("\nWorker will run continuously until stopped with Ctrl+C")
        sys.exit(1)
    
    worker_id = sys.argv[1]
    cycle = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    # Allow environment override
    if os.environ.get("WORKER_CYCLE_SECONDS"):
        cycle = int(os.environ["WORKER_CYCLE_SECONDS"])
    
    print("="*60)
    print(f"Claude Code Worker - {worker_id.upper()}")
    print("="*60)
    
    try:
        worker = CCWorker(worker_id)
        worker.run_forever(cycle)
    except Exception as e:
        print(f"[FATAL] Failed to start worker: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
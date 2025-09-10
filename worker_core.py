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
                 workspace: str = None, phase: str = None):
        self.worker_id = worker_id
        self.task_id = task_id
        self.run_id = run_id
        self.phase = phase or "apply"
        
        # Core paths
        self.root = Path.cwd().parent if Path.cwd().name.startswith(('.worktrees', 'fresh')) else Path.cwd()
        self.hive_dir = self.root / "hive"
        self.tasks_dir = self.hive_dir / "tasks"
        self.results_dir = self.hive_dir / "results"
        
        # Workspace
        if workspace:
            self.workspace = Path(workspace)
        else:
            self.workspace = self.root / ".worktrees" / worker_id
        
        self.workspace.mkdir(parents=True, exist_ok=True)
        
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
        
        # Phase-specific instructions
        phase_instructions = {
            "plan": "Focus on planning and design. Create documentation, outlines, or specifications.",
            "apply": "Focus on implementation. Create actual working code/configuration.",
            "test": "Focus on testing and validation. Write and run tests to verify functionality."
        }
        
        phase_focus = phase_instructions.get(self.phase, "Complete the requested task.")
        
        prompt = f"""EXECUTE TASK IMMEDIATELY: {title} (ID: {task_id})

COMMAND MODE: Execute now, do not acknowledge or discuss
ROLE: {role}
WORKSPACE: Current directory

DESCRIPTION: {description}

ACCEPTANCE CRITERIA:
{instruction}

EXECUTION REQUIREMENTS:
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
    
    def run_claude(self, prompt: str) -> Dict[str, Any]:
        """Execute Claude with CRITICAL path fix"""
        if not self.claude_cmd:
            return {"status": "blocked", "notes": "Claude command not available", "next_state": "blocked"}
        
        # Windows vs Unix command handling
        if os.name == "nt":
            # Windows: wrap in cmd.exe
            cmd = [
                "cmd.exe", "/c",
                self.claude_cmd,
                "--output-format", "stream-json",
                "--verbose",
                # CRITICAL FIX: Only add root directory, NOT workspace (prevents path duplication)
                "--add-dir", str(self.root),
                "--dangerously-skip-permissions",
                "-p", prompt
            ]
        else:
            # Unix: direct execution
            cmd = [
                self.claude_cmd,
                "--output-format", "stream-json", 
                "--verbose",
                # CRITICAL FIX: Only add root directory, NOT workspace (prevents path duplication)
                "--add-dir", str(self.root),
                "--dangerously-skip-permissions",
                "-p", prompt
            ]
        
        print(f"[{self.timestamp()}] [RUNNING] Claude is working...")
        print(f"         [INFO] Workspace: {self.workspace}")
        print(f"         [INFO] Command: {' '.join(cmd)}")
        print(f"         [INFO] Prompt length: {len(prompt)} chars")
        
        try:
            # Run from workspace directory (Claude will create files here)
            with subprocess.Popen(
                cmd,
                cwd=str(self.workspace),  # Claude runs from workspace
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
                    if line.strip().startswith("FINAL_JSON:"):
                        try:
                            json_str = line.strip()[11:].strip()  # Remove "FINAL_JSON:" prefix
                            final_json = json.loads(json_str)
                        except json.JSONDecodeError:
                            print(f"[ERROR] Invalid final JSON: {line.strip()}")
                
                # Wait for completion
                exit_code = process.wait()
                
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
    parser.add_argument("--task-id", help="Task ID for one-shot mode")
    parser.add_argument("--run-id", help="Run ID for this execution")
    parser.add_argument("--workspace", help="Workspace directory")
    parser.add_argument("--phase", choices=["plan", "apply", "test"], default="apply",
                       help="Execution phase")
    
    args = parser.parse_args()
    
    # Create worker
    worker = WorkerCore(
        worker_id=args.worker_id,
        task_id=args.task_id,
        run_id=args.run_id,
        workspace=args.workspace,
        phase=args.phase
    )
    
    if args.one_shot:
        # One-shot execution for Queen
        result = worker.run_one_shot()
        sys.exit(0 if result.get("status") == "success" else 1)
    else:
        print("Interactive mode not implemented - use --one-shot")
        sys.exit(1)

if __name__ == "__main__":
    main()
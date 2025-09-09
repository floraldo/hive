#!/usr/bin/env python3
"""
Hive Safety Manager
Implements safety guardrails, branch isolation, and risk management for headless MAS
"""

import json
import pathlib
import subprocess
import shutil
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class SafetyManager:
    """Safety and risk management for the Hive headless MAS"""
    
    def __init__(self, root_dir: str = "."):
        self.root = pathlib.Path(root_dir).resolve()
        self.hive_dir = self.root / "hive"
        self.safety_dir = self.hive_dir / "safety"
        self.worktrees_dir = self.root / "worktrees"
        
        # Safety configuration
        self.safety_config_file = self.safety_dir / "config.json"
        self.risk_log_file = self.safety_dir / "risk_log.jsonl"
        
        # Ensure directories exist
        self.safety_dir.mkdir(exist_ok=True)
        
        # Load or create safety configuration
        self.config = self.load_safety_config()
    
    def load_safety_config(self) -> Dict[str, Any]:
        """Load safety configuration"""
        default_config = {
            "max_concurrent_workers": 4,
            "max_file_changes_per_task": 20,
            "max_task_runtime_minutes": 60,
            "require_tests": True,
            "require_pr_review": True,
            "blocked_commands": [
                "rm -rf /",
                "sudo rm",
                "dd if=",
                ":(){ :|:& };:",  # Fork bomb
                "curl * | bash",
                "wget * | bash"
            ],
            "blocked_file_patterns": [
                "**/.env",
                "**/.git/config", 
                "**/id_rsa*",
                "**/*.pem",
                "**/secrets.*"
            ],
            "required_backup_branches": ["main", "master", "develop"],
            "auto_rollback_on_failure": True,
            "max_retry_attempts": 3,
            "worker_health_check_interval": 30,
            "emergency_stop_conditions": [
                "high_error_rate",
                "system_resource_exhaustion",
                "security_violation"
            ]
        }
        
        try:
            with open(self.safety_config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except (FileNotFoundError, json.JSONDecodeError):
            # Create default config
            with open(self.safety_config_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def log_risk_event(self, risk_level: str, event_type: str, details: Dict[str, Any]):
        """Log a risk event for audit and monitoring"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "risk_level": risk_level,  # low, medium, high, critical
            "event_type": event_type,
            "details": details
        }
        
        with open(self.risk_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        
        logger.warning(f"Risk event logged: {risk_level} - {event_type}")
    
    def validate_claude_command(self, claude_args: List[str], prompt: str) -> Tuple[bool, str]:
        """Validate Claude command and prompt for safety"""
        # Check for blocked commands in prompt
        for blocked_cmd in self.config["blocked_commands"]:
            if blocked_cmd in prompt.lower():
                self.log_risk_event("high", "blocked_command_detected", {
                    "blocked_command": blocked_cmd,
                    "prompt_excerpt": prompt[:200]
                })
                return False, f"Blocked command detected: {blocked_cmd}"
        
        # Check for dangerous permissions
        if "--dangerously-skip-permissions" in claude_args:
            self.log_risk_event("medium", "dangerous_permissions_used", {
                "claude_args": claude_args
            })
            logger.warning("Using dangerous permissions - extra monitoring required")
        
        # Check for file access patterns  
        for pattern in self.config["blocked_file_patterns"]:
            if pattern.replace("**", "") in prompt:
                self.log_risk_event("high", "sensitive_file_access", {
                    "pattern": pattern,
                    "prompt_excerpt": prompt[:200]
                })
                return False, f"Access to sensitive files blocked: {pattern}"
        
        return True, "Command validated"
    
    def create_worker_worktree(self, worker_id: str, task_id: str) -> Optional[pathlib.Path]:
        """Create an isolated git worktree for a worker task"""
        try:
            # Create worktrees directory if it doesn't exist
            self.worktrees_dir.mkdir(exist_ok=True)
            
            # Create unique branch name
            branch_name = f"agent/{worker_id}/{task_id}"
            worktree_path = self.worktrees_dir / f"{worker_id}_{task_id}_{uuid.uuid4().hex[:8]}"
            
            # Ensure we're starting from a clean main branch
            subprocess.run(["git", "checkout", "main"], cwd=str(self.root), check=True)
            subprocess.run(["git", "pull", "origin", "main"], cwd=str(self.root), check=False)
            
            # Create new branch
            subprocess.run([
                "git", "checkout", "-b", branch_name
            ], cwd=str(self.root), check=True)
            
            # Create worktree
            subprocess.run([
                "git", "worktree", "add", str(worktree_path), branch_name
            ], cwd=str(self.root), check=True)
            
            logger.info(f"Created worktree for {worker_id}: {worktree_path}")
            
            self.log_risk_event("low", "worktree_created", {
                "worker_id": worker_id,
                "task_id": task_id,
                "branch_name": branch_name,
                "worktree_path": str(worktree_path)
            })
            
            return worktree_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create worktree for {worker_id}: {e}")
            self.log_risk_event("medium", "worktree_creation_failed", {
                "worker_id": worker_id,
                "task_id": task_id,
                "error": str(e)
            })
            return None
    
    def cleanup_worker_worktree(self, worker_id: str, task_id: str, worktree_path: pathlib.Path, 
                               preserve_on_success: bool = True):
        """Clean up worker worktree after task completion"""
        try:
            branch_name = f"agent/{worker_id}/{task_id}"
            
            # Remove worktree
            subprocess.run([
                "git", "worktree", "remove", str(worktree_path)
            ], cwd=str(self.root), check=True)
            
            # Optionally preserve successful branches for review
            if not preserve_on_success:
                subprocess.run([
                    "git", "branch", "-D", branch_name
                ], cwd=str(self.root), check=False)
            
            logger.info(f"Cleaned up worktree for {worker_id}: {worktree_path}")
            
            self.log_risk_event("low", "worktree_cleaned", {
                "worker_id": worker_id,
                "task_id": task_id,
                "worktree_path": str(worktree_path),
                "branch_preserved": preserve_on_success
            })
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to cleanup worktree for {worker_id}: {e}")
            self.log_risk_event("medium", "worktree_cleanup_failed", {
                "worker_id": worker_id,
                "task_id": task_id,
                "error": str(e)
            })
    
    def monitor_task_execution(self, worker_id: str, task_id: str, start_time: datetime) -> bool:
        """Monitor task execution for safety violations"""
        elapsed_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60
        
        # Check runtime limits
        if elapsed_minutes > self.config["max_task_runtime_minutes"]:
            self.log_risk_event("high", "task_runtime_exceeded", {
                "worker_id": worker_id,
                "task_id": task_id,
                "elapsed_minutes": elapsed_minutes,
                "limit": self.config["max_task_runtime_minutes"]
            })
            return False
        
        # Check system resources (basic implementation)
        try:
            # Check available disk space
            disk_usage = shutil.disk_usage(str(self.root))
            free_gb = disk_usage.free / (1024**3)
            
            if free_gb < 1.0:  # Less than 1GB free
                self.log_risk_event("critical", "low_disk_space", {
                    "free_gb": free_gb,
                    "worker_id": worker_id,
                    "task_id": task_id
                })
                return False
                
        except Exception as e:
            logger.error(f"Failed to check system resources: {e}")
        
        return True
    
    def validate_task_changes(self, worker_id: str, task_id: str, worktree_path: pathlib.Path) -> Tuple[bool, Dict[str, Any]]:
        """Validate changes made during task execution"""
        try:
            # Get list of changed files
            result = subprocess.run([
                "git", "diff", "--name-only", "HEAD"
            ], cwd=str(worktree_path), capture_output=True, text=True)
            
            changed_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            # Check number of changed files
            if len(changed_files) > self.config["max_file_changes_per_task"]:
                self.log_risk_event("medium", "excessive_file_changes", {
                    "worker_id": worker_id,
                    "task_id": task_id,
                    "changed_files_count": len(changed_files),
                    "limit": self.config["max_file_changes_per_task"]
                })
                return False, {
                    "error": "Too many file changes",
                    "count": len(changed_files),
                    "limit": self.config["max_file_changes_per_task"]
                }
            
            # Check for sensitive file modifications
            sensitive_files = []
            for file_path in changed_files:
                for pattern in self.config["blocked_file_patterns"]:
                    pattern_clean = pattern.replace("**", "").replace("*", "")
                    if pattern_clean in file_path:
                        sensitive_files.append(file_path)
            
            if sensitive_files:
                self.log_risk_event("high", "sensitive_file_modified", {
                    "worker_id": worker_id,
                    "task_id": task_id,
                    "sensitive_files": sensitive_files
                })
                return False, {
                    "error": "Sensitive files modified",
                    "files": sensitive_files
                }
            
            # Check for required tests if enabled
            if self.config["require_tests"] and changed_files:
                has_tests = any("test" in f.lower() for f in changed_files)
                if not has_tests:
                    # Look for test files that might test the changed functionality
                    test_patterns = ["test_*.py", "*_test.py", "*.test.js", "*.spec.js"]
                    has_existing_tests = False
                    
                    for pattern in test_patterns:
                        result = subprocess.run([
                            "find", ".", "-name", pattern
                        ], cwd=str(worktree_path), capture_output=True, text=True)
                        if result.stdout.strip():
                            has_existing_tests = True
                            break
                    
                    if not has_existing_tests:
                        self.log_risk_event("medium", "missing_tests", {
                            "worker_id": worker_id,
                            "task_id": task_id,
                            "changed_files": changed_files
                        })
                        logger.warning(f"No tests found for task {task_id}")
            
            return True, {
                "changed_files": changed_files,
                "file_count": len(changed_files),
                "validation_passed": True
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to validate task changes: {e}")
            return False, {"error": f"Validation failed: {str(e)}"}
    
    def create_safety_checkpoint(self, worker_id: str, task_id: str, worktree_path: pathlib.Path) -> str:
        """Create a safety checkpoint (git commit) before risky operations"""
        try:
            checkpoint_message = f"SAFETY_CHECKPOINT: Before task {task_id} by {worker_id}"
            
            # Add all changes
            subprocess.run(["git", "add", "."], cwd=str(worktree_path), check=True)
            
            # Create checkpoint commit
            result = subprocess.run([
                "git", "commit", "-m", checkpoint_message
            ], cwd=str(worktree_path), capture_output=True, text=True)
            
            if result.returncode == 0:
                # Get commit hash
                commit_result = subprocess.run([
                    "git", "rev-parse", "HEAD"
                ], cwd=str(worktree_path), capture_output=True, text=True)
                
                commit_hash = commit_result.stdout.strip()
                
                self.log_risk_event("low", "safety_checkpoint_created", {
                    "worker_id": worker_id,
                    "task_id": task_id,
                    "commit_hash": commit_hash
                })
                
                return commit_hash
            else:
                logger.warning("No changes to commit for safety checkpoint")
                return "no_changes"
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create safety checkpoint: {e}")
            self.log_risk_event("medium", "checkpoint_creation_failed", {
                "worker_id": worker_id,
                "task_id": task_id,
                "error": str(e)
            })
            return "failed"
    
    def rollback_to_checkpoint(self, worker_id: str, task_id: str, worktree_path: pathlib.Path, 
                              commit_hash: str) -> bool:
        """Rollback to a safety checkpoint"""
        try:
            subprocess.run([
                "git", "reset", "--hard", commit_hash
            ], cwd=str(worktree_path), check=True)
            
            self.log_risk_event("medium", "safety_rollback_executed", {
                "worker_id": worker_id,
                "task_id": task_id,
                "commit_hash": commit_hash
            })
            
            logger.info(f"Rolled back task {task_id} to checkpoint {commit_hash}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to rollback to checkpoint: {e}")
            self.log_risk_event("high", "rollback_failed", {
                "worker_id": worker_id,
                "task_id": task_id,
                "commit_hash": commit_hash,
                "error": str(e)
            })
            return False
    
    def check_emergency_stop_conditions(self) -> Tuple[bool, List[str]]:
        """Check if emergency stop conditions are met"""
        triggers = []
        
        # Check recent risk events
        if self.risk_log_file.exists():
            recent_events = []
            current_time = datetime.now(timezone.utc)
            
            with open(self.risk_log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                        
                        # Only consider events from the last hour
                        if (current_time - event_time).total_seconds() < 3600:
                            recent_events.append(event)
                    except (json.JSONDecodeError, ValueError, KeyError):
                        continue
            
            # Check for high error rate
            high_risk_events = [e for e in recent_events if e["risk_level"] in ["high", "critical"]]
            if len(high_risk_events) >= 5:
                triggers.append("high_error_rate")
            
            # Check for repeated security violations
            security_events = [e for e in recent_events if "security" in e["event_type"] or "blocked" in e["event_type"]]
            if len(security_events) >= 3:
                triggers.append("security_violation")
        
        # Check system resources
        try:
            disk_usage = shutil.disk_usage(str(self.root))
            free_gb = disk_usage.free / (1024**3)
            
            if free_gb < 0.5:  # Less than 500MB
                triggers.append("system_resource_exhaustion")
        except Exception:
            pass
        
        if triggers:
            self.log_risk_event("critical", "emergency_stop_triggered", {
                "triggers": triggers,
                "action": "system_halt_recommended"
            })
        
        return len(triggers) > 0, triggers
    
    def get_safety_report(self) -> Dict[str, Any]:
        """Generate a comprehensive safety report"""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": self.config,
            "recent_events": [],
            "risk_summary": {"low": 0, "medium": 0, "high": 0, "critical": 0},
            "worktrees": []
        }
        
        # Read recent risk events
        if self.risk_log_file.exists():
            current_time = datetime.now(timezone.utc)
            
            with open(self.risk_log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                        
                        # Only include events from the last 24 hours
                        if (current_time - event_time).total_seconds() < 86400:
                            report["recent_events"].append(event)
                            risk_level = event.get("risk_level", "unknown")
                            if risk_level in report["risk_summary"]:
                                report["risk_summary"][risk_level] += 1
                    except (json.JSONDecodeError, ValueError, KeyError):
                        continue
        
        # List active worktrees
        if self.worktrees_dir.exists():
            for worktree in self.worktrees_dir.iterdir():
                if worktree.is_dir():
                    report["worktrees"].append({
                        "path": str(worktree),
                        "name": worktree.name,
                        "created": worktree.stat().st_ctime
                    })
        
        return report

def main():
    """Demo/test safety manager functionality"""
    safety = SafetyManager()
    
    print("🛡️ Hive Safety Manager")
    print("=" * 40)
    
    # Generate safety report
    report = safety.get_safety_report()
    
    print(f"Risk Summary (last 24h):")
    for level, count in report["risk_summary"].items():
        print(f"  {level}: {count}")
    
    print(f"\nActive Worktrees: {len(report['worktrees'])}")
    
    print(f"\nRecent Events: {len(report['recent_events'])}")
    
    # Check emergency conditions
    emergency, triggers = safety.check_emergency_stop_conditions()
    if emergency:
        print(f"\n🚨 EMERGENCY STOP CONDITIONS DETECTED:")
        for trigger in triggers:
            print(f"   - {trigger}")
    else:
        print("\n✅ All safety conditions normal")

if __name__ == "__main__":
    main()
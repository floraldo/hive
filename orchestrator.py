#!/usr/bin/env python3
"""
Hive Headless MAS - Orchestrator System
Central coordinator for autonomous multi-agent development workflow
"""

import json
import time
import pathlib
import subprocess
import shutil
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hive/logs/orchestrator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('orchestrator')

class HiveOrchestrator:
    """Central orchestrator for the Hive headless MAS system"""
    
    def __init__(self, root_dir: str = "."):
        self.root = pathlib.Path(root_dir).resolve()
        self.hive_dir = self.root / "hive"
        self.bus_dir = self.hive_dir / "bus" 
        self.workers_dir = self.hive_dir / "workers"
        self.logs_dir = self.hive_dir / "logs"
        
        # Core files
        self.tasks_file = self.bus_dir / "tasks.json"
        self.events_file = self.bus_dir / "events.jsonl"
        
        # System state
        self.running = False
        self.workers = {}
        self.worker_threads = {}
        
        # Configuration
        self.claude_cmd = shutil.which("claude")
        if not self.claude_cmd:
            raise RuntimeError("Claude CLI not found in PATH")
            
        # Ensure directories exist
        self.logs_dir.mkdir(exist_ok=True)
        
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log an event to the events.jsonl file"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "data": data
        }
        
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
            
        logger.info(f"Event logged: {event_type} - {data}")
    
    def load_tasks(self) -> Dict[str, Any]:
        """Load tasks from tasks.json"""
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load tasks: {e}")
            return {"tasks": [], "task_counter": 0, "settings": {}}
    
    def save_tasks(self, tasks_data: Dict[str, Any]):
        """Save tasks to tasks.json"""
        tasks_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        with open(self.tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks_data, f, indent=2)
            
        logger.info(f"Tasks saved: {len(tasks_data.get('tasks', []))} tasks")
    
    def load_worker_config(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Load worker configuration"""
        worker_file = self.workers_dir / f"{worker_id}.json"
        try:
            with open(worker_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load worker {worker_id}: {e}")
            return None
    
    def save_worker_config(self, worker_id: str, config: Dict[str, Any]):
        """Save worker configuration"""
        config["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        worker_file = self.workers_dir / f"{worker_id}.json"
        
        with open(worker_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    
    def get_available_workers(self) -> List[str]:
        """Get list of available workers"""
        workers = []
        for worker_file in self.workers_dir.glob("*.json"):
            worker_config = self.load_worker_config(worker_file.stem)
            if worker_config and worker_config.get("is_enabled", False):
                if worker_config.get("status") in ["idle", "available"]:
                    workers.append(worker_file.stem)
        return workers
    
    def assign_task(self, task: Dict[str, Any]) -> Optional[str]:
        """Assign a task to an available worker"""
        available_workers = self.get_available_workers()
        
        # Simple assignment strategy: round-robin or tag-based
        task_tags = task.get("tags", [])
        
        # Priority assignment based on tags
        preferred_workers = []
        for worker_id in available_workers:
            worker_config = self.load_worker_config(worker_id)
            if worker_config:
                capabilities = worker_config.get("capabilities", [])
                # Check if worker has relevant capabilities
                if any(tag in capabilities for tag in task_tags):
                    preferred_workers.append(worker_id)
        
        # Use preferred workers first, otherwise any available worker
        candidates = preferred_workers if preferred_workers else available_workers
        
        if not candidates:
            return None
            
        # Simple round-robin for now
        selected_worker = candidates[0]
        
        # Update task and worker status
        task["status"] = "assigned"
        task["assignee"] = selected_worker
        task["assigned_at"] = datetime.now(timezone.utc).isoformat()
        
        # Update worker status
        worker_config = self.load_worker_config(selected_worker)
        worker_config["status"] = "assigned"
        worker_config["current_task"] = task["id"]
        self.save_worker_config(selected_worker, worker_config)
        
        # Log the assignment
        self.log_event("task_assigned", {
            "task_id": task["id"],
            "worker": selected_worker,
            "task_title": task["title"]
        })
        
        logger.info(f"Assigned task {task['id']} to worker {selected_worker}")
        return selected_worker
    
    def create_task(self, title: str, description: str = "", tags: List[str] = None, 
                   priority: str = "normal", acceptance_criteria: List[str] = None) -> str:
        """Create a new task"""
        tasks_data = self.load_tasks()
        
        task_id = f"tsk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "tags": tags or [],
            "priority": priority,
            "status": "queued",
            "assignee": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "acceptance_criteria": acceptance_criteria or [],
            "estimated_effort": "unknown",
            "dependencies": []
        }
        
        tasks_data["tasks"].append(task)
        tasks_data["task_counter"] = tasks_data.get("task_counter", 0) + 1
        
        self.save_tasks(tasks_data)
        
        self.log_event("task_created", {
            "task_id": task_id,
            "title": title,
            "priority": priority,
            "tags": tags
        })
        
        logger.info(f"Created task {task_id}: {title}")
        return task_id
    
    def run_headless_claude(self, worker_id: str, prompt: str) -> Dict[str, Any]:
        """Run Claude in headless mode for a worker"""
        worker_config = self.load_worker_config(worker_id)
        if not worker_config:
            return {"success": False, "error": "Worker config not found"}
        
        # Get Claude arguments from worker config
        claude_args = worker_config.get("config", {}).get("claude_args", [])
        workdir = self.root / worker_config.get("workdir", ".")
        
        # Construct command
        cmd = [self.claude_cmd] + claude_args + ["-p", prompt]
        
        # Log the execution
        self.log_event("claude_execution_start", {
            "worker": worker_id,
            "command": " ".join(cmd),
            "workdir": str(workdir)
        })
        
        try:
            # Create log file for this execution
            log_file = self.logs_dir / f"{worker_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            
            with open(log_file, "w", encoding="utf-8") as lf:
                process = subprocess.run(
                    cmd,
                    cwd=str(workdir),
                    capture_output=True,
                    text=True,
                    timeout=3600  # 1 hour timeout
                )
                
                # Write output to log file
                lf.write(f"Command: {' '.join(cmd)}\n")
                lf.write(f"Working Directory: {workdir}\n")
                lf.write(f"Return Code: {process.returncode}\n")
                lf.write(f"\n--- STDOUT ---\n{process.stdout}\n")
                lf.write(f"\n--- STDERR ---\n{process.stderr}\n")
                
                result = {
                    "success": process.returncode == 0,
                    "return_code": process.returncode,
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "log_file": str(log_file)
                }
                
                self.log_event("claude_execution_complete", {
                    "worker": worker_id,
                    "success": result["success"],
                    "return_code": process.returncode,
                    "log_file": str(log_file)
                })
                
                logger.info(f"Claude execution for {worker_id} completed: {result['success']}")
                return result
                
        except subprocess.TimeoutExpired:
            self.log_event("claude_execution_timeout", {"worker": worker_id})
            logger.error(f"Claude execution timeout for worker {worker_id}")
            return {"success": False, "error": "Execution timeout"}
        except Exception as e:
            self.log_event("claude_execution_error", {"worker": worker_id, "error": str(e)})
            logger.error(f"Claude execution error for {worker_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def process_queued_tasks(self):
        """Process all queued tasks by assigning them to workers"""
        tasks_data = self.load_tasks()
        queued_tasks = [t for t in tasks_data["tasks"] if t["status"] == "queued"]
        
        assignments_made = 0
        for task in queued_tasks:
            worker = self.assign_task(task)
            if worker:
                assignments_made += 1
            else:
                logger.info(f"No available workers for task {task['id']}")
        
        if assignments_made > 0:
            self.save_tasks(tasks_data)
            logger.info(f"Made {assignments_made} task assignments")
    
    def monitor_workers(self):
        """Monitor worker status and handle task execution"""
        tasks_data = self.load_tasks()
        active_tasks = [t for t in tasks_data["tasks"] if t["status"] == "assigned"]
        
        for task in active_tasks:
            worker_id = task["assignee"]
            worker_config = self.load_worker_config(worker_id)
            
            if not worker_config:
                continue
                
            # Check if worker should start executing this task
            if worker_config.get("status") == "assigned":
                self.start_task_execution(task, worker_id)
    
    def start_task_execution(self, task: Dict[str, Any], worker_id: str):
        """Start executing a task with a worker"""
        # Update task status
        task["status"] = "in_progress"
        task["started_at"] = datetime.now(timezone.utc).isoformat()
        
        # Update worker status
        worker_config = self.load_worker_config(worker_id)
        worker_config["status"] = "working"
        self.save_worker_config(worker_id, worker_config)
        
        # Create execution prompt based on worker role and task
        prompt = self.create_execution_prompt(task, worker_config)
        
        # Start execution in a separate thread
        def execute_task():
            logger.info(f"Starting task execution: {task['id']} on worker {worker_id}")
            result = self.run_headless_claude(worker_id, prompt)
            self.handle_task_completion(task, worker_id, result)
        
        thread = threading.Thread(target=execute_task, daemon=True)
        thread.start()
        self.worker_threads[f"{worker_id}_{task['id']}"] = thread
        
        logger.info(f"Started task {task['id']} execution on worker {worker_id}")
    
    def create_execution_prompt(self, task: Dict[str, Any], worker_config: Dict[str, Any]) -> str:
        """Create a prompt for Claude based on the task and worker capabilities"""
        role = worker_config.get("role", "general")
        capabilities = ", ".join(worker_config.get("capabilities", []))
        
        prompt = f"""
You are a {role} working in a headless autonomous development system.

TASK DETAILS:
- ID: {task['id']}
- Title: {task['title']}
- Description: {task.get('description', 'No description provided')}
- Priority: {task.get('priority', 'normal')}
- Tags: {', '.join(task.get('tags', []))}

YOUR CAPABILITIES: {capabilities}

ACCEPTANCE CRITERIA:
{chr(10).join(f'- {criteria}' for criteria in task.get('acceptance_criteria', ['Task completed successfully']))}

INSTRUCTIONS:
1. Analyze the task requirements carefully
2. Plan your implementation approach
3. Execute the necessary changes (code, tests, documentation)
4. Ensure all acceptance criteria are met
5. Commit your changes with a clear message referencing the task ID
6. Report your progress and final status

IMPORTANT:
- Work incrementally and commit frequently
- Write tests for any new functionality
- Follow the project's coding standards
- If you encounter blockers, document them clearly
- Provide a final JSON summary with: {{"status": "completed|blocked|failed", "summary": "description", "files_changed": ["list"], "next_steps": ["if any"]}}

Begin work on this task now.
"""
        
        return prompt.strip()
    
    def handle_task_completion(self, task: Dict[str, Any], worker_id: str, result: Dict[str, Any]):
        """Handle the completion of a task execution"""
        # Update task based on execution result
        if result["success"]:
            task["status"] = "ready_for_review" 
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Task {task['id']} completed successfully")
        else:
            task["status"] = "failed"
            task["failed_at"] = datetime.now(timezone.utc).isoformat()
            task["failure_reason"] = result.get("error", "Unknown error")
            logger.error(f"Task {task['id']} failed: {task['failure_reason']}")
        
        # Update worker status
        worker_config = self.load_worker_config(worker_id)
        worker_config["status"] = "idle"
        worker_config["current_task"] = None
        worker_config["total_tasks_completed"] = worker_config.get("total_tasks_completed", 0) + 1
        self.save_worker_config(worker_id, worker_config)
        
        # Save updated task data
        tasks_data = self.load_tasks()
        for i, t in enumerate(tasks_data["tasks"]):
            if t["id"] == task["id"]:
                tasks_data["tasks"][i] = task
                break
        self.save_tasks(tasks_data)
        
        # Log completion
        self.log_event("task_completed", {
            "task_id": task["id"],
            "worker": worker_id,
            "success": result["success"],
            "status": task["status"]
        })
        
        # Clean up thread
        thread_key = f"{worker_id}_{task['id']}"
        if thread_key in self.worker_threads:
            del self.worker_threads[thread_key]
    
    def run_orchestration_cycle(self):
        """Run one complete orchestration cycle"""
        logger.info("Starting orchestration cycle")
        
        # Process queued tasks
        self.process_queued_tasks()
        
        # Monitor active workers
        self.monitor_workers()
        
        # Generate status report
        self.generate_status_report()
        
        logger.info("Orchestration cycle completed")
    
    def generate_status_report(self):
        """Generate and log a status report"""
        tasks_data = self.load_tasks()
        tasks = tasks_data.get("tasks", [])
        
        status_counts = {}
        for task in tasks:
            status = task["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        worker_status = {}
        for worker_file in self.workers_dir.glob("*.json"):
            worker_config = self.load_worker_config(worker_file.stem)
            if worker_config:
                worker_status[worker_file.stem] = worker_config.get("status", "unknown")
        
        self.log_event("status_report", {
            "task_counts": status_counts,
            "worker_status": worker_status,
            "active_threads": len(self.worker_threads)
        })
    
    def run(self, cycle_interval: int = 30):
        """Run the orchestrator main loop"""
        logger.info(f"Starting Hive Orchestrator (cycle interval: {cycle_interval}s)")
        self.running = True
        
        try:
            while self.running:
                self.run_orchestration_cycle()
                time.sleep(cycle_interval)
        except KeyboardInterrupt:
            logger.info("Orchestrator stopped by user")
        finally:
            self.running = False
            # Wait for active threads to complete
            for thread in self.worker_threads.values():
                if thread.is_alive():
                    thread.join(timeout=10)
            logger.info("Orchestrator shutdown complete")

def main():
    """Main entry point"""
    orchestrator = HiveOrchestrator()
    
    # Create some initial tasks for demonstration
    orchestrator.create_task(
        "Setup headless MAS foundation",
        "Initialize the headless multi-agent system with all core components",
        tags=["initialization", "system"],
        priority="high",
        acceptance_criteria=[
            "All worker configurations are valid",
            "Task queue is operational", 
            "Orchestrator can assign tasks to workers",
            "Basic CI/CD setup is functional"
        ]
    )
    
    orchestrator.create_task(
        "Implement health check endpoint",
        "Add a /health endpoint that returns system status and uptime",
        tags=["backend", "api"],
        priority="normal",
        acceptance_criteria=[
            "GET /health returns 200 with JSON response",
            "Response includes status and timestamp",
            "Tests are written and passing"
        ]
    )
    
    # Run the orchestrator
    orchestrator.run()

if __name__ == "__main__":
    main()
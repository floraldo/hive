#!/usr/bin/env python3
"""
Hive Headless MAS - Worker System
Individual worker processes that execute tasks using headless Claude calls
"""

import json
import time
import pathlib
import subprocess
import shutil
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class HeadlessWorker:
    """Individual headless worker that executes tasks autonomously"""
    
    def __init__(self, worker_id: str, root_dir: str = "."):
        self.worker_id = worker_id
        self.root = pathlib.Path(root_dir).resolve()
        self.hive_dir = self.root / "hive"
        self.bus_dir = self.hive_dir / "bus"
        self.workers_dir = self.hive_dir / "workers"
        self.logs_dir = self.hive_dir / "logs"
        
        # Core files
        self.tasks_file = self.bus_dir / "tasks.json"
        self.events_file = self.bus_dir / "events.jsonl"
        self.worker_file = self.workers_dir / f"{worker_id}.json"
        
        # Setup logging for this worker
        self.logger = logging.getLogger(f'worker.{worker_id}')
        worker_log_file = self.logs_dir / f"{worker_id}.log"
        handler = logging.FileHandler(worker_log_file)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)
        
        # Worker state
        self.running = False
        self.config = self.load_config()
        
        # Claude CLI
        self.claude_cmd = shutil.which("claude")
        if not self.claude_cmd:
            raise RuntimeError("Claude CLI not found in PATH")
    
    def load_config(self) -> Dict[str, Any]:
        """Load worker configuration"""
        try:
            with open(self.worker_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.logger.info(f"Loaded config for {self.worker_id}")
                return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load worker config: {e}")
            raise
    
    def save_config(self):
        """Save worker configuration"""
        self.config["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        
        with open(self.worker_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log an event to the events.jsonl file"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "worker": self.worker_id,
            "data": data
        }
        
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        
        self.logger.info(f"Event: {event_type} - {data}")
    
    def get_assigned_task(self) -> Optional[Dict[str, Any]]:
        """Get the currently assigned task for this worker"""
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                tasks_data = json.load(f)
            
            # Find task assigned to this worker
            for task in tasks_data.get("tasks", []):
                if (task.get("assignee") == self.worker_id and 
                    task.get("status") in ["assigned", "in_progress"]):
                    return task
            
            return None
            
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load tasks: {e}")
            return None
    
    def update_task_status(self, task_id: str, status: str, **kwargs):
        """Update task status in the task queue"""
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                tasks_data = json.load(f)
            
            # Find and update the task
            for task in tasks_data.get("tasks", []):
                if task["id"] == task_id:
                    task["status"] = status
                    task["updated_at"] = datetime.now(timezone.utc).isoformat()
                    
                    # Add any additional fields
                    for key, value in kwargs.items():
                        task[key] = value
                    
                    break
            
            # Save updated tasks
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(tasks_data, f, indent=2)
                
            self.log_event("task_status_updated", {
                "task_id": task_id,
                "new_status": status,
                **kwargs
            })
            
        except Exception as e:
            self.logger.error(f"Failed to update task status: {e}")
    
    def run_claude_headless(self, prompt: str) -> Dict[str, Any]:
        """Run Claude in headless mode"""
        # Get Claude arguments from config
        claude_args = self.config.get("config", {}).get("claude_args", [])
        workdir = self.root / self.config.get("workdir", ".")
        
        # Ensure workdir exists
        workdir.mkdir(parents=True, exist_ok=True)
        
        # Construct command
        cmd = [self.claude_cmd] + claude_args + ["-p", prompt]
        
        self.logger.info(f"Executing Claude: {' '.join(cmd[:3])}... in {workdir}")
        
        try:
            # Create execution log
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = self.logs_dir / f"{self.worker_id}_execution_{timestamp}.log"
            
            with open(log_file, "w", encoding="utf-8") as lf:
                process = subprocess.run(
                    cmd,
                    cwd=str(workdir),
                    capture_output=True,
                    text=True,
                    timeout=1800  # 30 minute timeout
                )
                
                # Write detailed execution log
                lf.write(f"Worker: {self.worker_id}\n")
                lf.write(f"Command: {' '.join(cmd)}\n")
                lf.write(f"Working Directory: {workdir}\n")
                lf.write(f"Return Code: {process.returncode}\n")
                lf.write(f"Timestamp: {timestamp}\n")
                lf.write(f"\n{'='*50} STDOUT {'='*50}\n")
                lf.write(process.stdout)
                lf.write(f"\n{'='*50} STDERR {'='*50}\n")
                lf.write(process.stderr)
                
                result = {
                    "success": process.returncode == 0,
                    "return_code": process.returncode,
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "log_file": str(log_file),
                    "execution_time": timestamp
                }
                
                self.logger.info(f"Claude execution completed: success={result['success']}")
                return result
                
        except subprocess.TimeoutExpired:
            self.logger.error("Claude execution timeout")
            return {"success": False, "error": "Execution timeout"}
        except Exception as e:
            self.logger.error(f"Claude execution error: {e}")
            return {"success": False, "error": str(e)}
    
    def create_task_prompt(self, task: Dict[str, Any]) -> str:
        """Create a specialized prompt based on worker role and task"""
        role = self.config.get("role", "general_developer")
        capabilities = self.config.get("capabilities", [])
        
        # Role-specific prompt templates
        role_prompts = {
            "planner_orchestrator": self.create_planner_prompt,
            "frontend_developer": self.create_frontend_prompt,
            "backend_developer": self.create_backend_prompt,
            "infrastructure_engineer": self.create_infra_prompt,
        }
        
        prompt_creator = role_prompts.get(role, self.create_generic_prompt)
        return prompt_creator(task, capabilities)
    
    def create_planner_prompt(self, task: Dict[str, Any], capabilities: List[str]) -> str:
        """Create prompt for planner/orchestrator role"""
        return f"""
You are the QUEEN - strategic planner and orchestrator for the Hive development system.

CURRENT TASK: {task['title']}
DESCRIPTION: {task.get('description', 'No description provided')}
PRIORITY: {task.get('priority', 'normal')}

YOUR RESPONSIBILITIES:
1. **Strategic Planning** - Analyze the repository and create comprehensive development roadmaps
2. **Task Generation** - Break down large goals into actionable, well-defined tasks
3. **Quality Assurance** - Review completed work and ensure standards are met
4. **Coordination** - Ensure workers have clear, unambiguous instructions

CURRENT REPOSITORY STATE:
- Analyze the codebase structure and existing functionality
- Identify technical debt, opportunities for improvement
- Review recent changes and development patterns

FOR THIS TASK:
{chr(10).join(f'• {criteria}' for criteria in task.get('acceptance_criteria', ['Task completed successfully']))}

ACTIONS TO TAKE:
1. Examine the repository thoroughly
2. Create or update comprehensive task specifications
3. Add new tasks to hive/bus/tasks.json following this format:
   {{
     "id": "tsk_YYYYMMDD_HHMMSS_xxxxx", 
     "title": "Clear, actionable task title",
     "description": "Detailed requirements and context",
     "tags": ["relevant", "tags"],
     "priority": "high|normal|low",
     "acceptance_criteria": ["Specific", "measurable", "criteria"],
     "estimated_effort": "2h|1d|1w"
   }}

4. Document your analysis and recommendations
5. Report completion status in JSON format

Focus on creating tasks that are:
- **Specific** - Clear scope and deliverables
- **Actionable** - Workers can execute without clarification
- **Testable** - Success can be measured objectively
- **Incremental** - Build upon existing work logically

Begin your strategic analysis now.
"""
    
    def create_frontend_prompt(self, task: Dict[str, Any], capabilities: List[str]) -> str:
        """Create prompt for frontend developer role"""
        return f"""
You are a FRONTEND DEVELOPER specializing in modern web development.

TASK: {task['title']}
DESCRIPTION: {task.get('description', 'No description provided')}

YOUR EXPERTISE: {', '.join(capabilities)}

ACCEPTANCE CRITERIA:
{chr(10).join(f'• {criteria}' for criteria in task.get('acceptance_criteria', ['Feature implemented and tested']))}

DEVELOPMENT STANDARDS:
- **React/Next.js** - Use modern hooks and functional components
- **TypeScript** - Type all components and props
- **Responsive Design** - Mobile-first approach
- **Accessibility** - WCAG 2.1 compliance
- **Testing** - Jest + React Testing Library
- **Code Quality** - ESLint + Prettier formatting

WORKFLOW:
1. **Analysis** - Understand requirements and existing code
2. **Planning** - Design component structure and data flow  
3. **Implementation** - Write clean, reusable components
4. **Testing** - Unit and integration tests
5. **Documentation** - Update README and component docs
6. **Commit** - Clear commit message referencing task ID {task['id']}

IMPORTANT:
- Follow existing project patterns and style guidelines
- Ensure cross-browser compatibility
- Optimize for performance (lazy loading, code splitting)
- Handle loading and error states properly
- Provide meaningful user feedback

Start implementation now. Work incrementally and commit frequently.
"""
    
    def create_backend_prompt(self, task: Dict[str, Any], capabilities: List[str]) -> str:
        """Create prompt for backend developer role"""
        return f"""
You are a BACKEND DEVELOPER specializing in API development and data management.

TASK: {task['title']}  
DESCRIPTION: {task.get('description', 'No description provided')}

YOUR EXPERTISE: {', '.join(capabilities)}

ACCEPTANCE CRITERIA:
{chr(10).join(f'• {criteria}' for criteria in task.get('acceptance_criteria', ['API endpoint implemented and tested']))}

DEVELOPMENT STANDARDS:
- **Python/Flask** - RESTful API design principles
- **Data Validation** - Use Marshmallow or Pydantic schemas
- **Database** - SQLAlchemy ORM with proper migrations
- **Testing** - pytest with >80% coverage
- **Security** - Input validation, SQL injection prevention
- **Documentation** - OpenAPI/Swagger specifications

WORKFLOW:
1. **API Design** - Define endpoints, request/response schemas
2. **Database Schema** - Create/update models and migrations
3. **Implementation** - Write endpoint logic with error handling
4. **Testing** - Unit tests and integration tests
5. **Security Review** - Validate inputs, check authentication
6. **Documentation** - Update API docs and README
7. **Commit** - Reference task ID {task['id']} in commit message

BEST PRACTICES:
- Follow RESTful conventions (GET, POST, PUT, DELETE)
- Use appropriate HTTP status codes
- Implement proper error handling and logging
- Validate all input data thoroughly
- Use database transactions where appropriate
- Handle race conditions and concurrency

Begin implementation with a clear plan and execute systematically.
"""
    
    def create_infra_prompt(self, task: Dict[str, Any], capabilities: List[str]) -> str:
        """Create prompt for infrastructure engineer role"""
        return f"""
You are an INFRASTRUCTURE ENGINEER responsible for deployment, monitoring, and DevOps.

TASK: {task['title']}
DESCRIPTION: {task.get('description', 'No description provided')}

YOUR EXPERTISE: {', '.join(capabilities)}

ACCEPTANCE CRITERIA:
{chr(10).join(f'• {criteria}' for criteria in task.get('acceptance_criteria', ['Infrastructure configured and tested']))}

INFRASTRUCTURE STANDARDS:
- **Containerization** - Docker with multi-stage builds
- **Orchestration** - Docker Compose or Kubernetes manifests
- **CI/CD** - GitHub Actions or similar pipeline
- **Monitoring** - Health checks and logging
- **Security** - Principle of least privilege, secrets management
- **Documentation** - Deployment guides and runbooks

WORKFLOW:
1. **Assessment** - Analyze current infrastructure and requirements
2. **Design** - Plan architecture and resource allocation
3. **Implementation** - Create configs, scripts, and manifests
4. **Testing** - Validate deployments in staging environment
5. **Security** - Review permissions and secret handling
6. **Documentation** - Update deployment and operational guides
7. **Commit** - Reference task ID {task['id']} in commit message

KEY CONSIDERATIONS:
- **Scalability** - Design for growth and load
- **Reliability** - Implement redundancy and failover
- **Observability** - Comprehensive logging and metrics
- **Cost Efficiency** - Optimize resource usage
- **Security** - Defense in depth approach

Start with a thorough analysis of current state and requirements.
"""
    
    def create_generic_prompt(self, task: Dict[str, Any], capabilities: List[str]) -> str:
        """Create generic prompt for unknown roles"""
        return f"""
You are working on a development task in the Hive autonomous system.

TASK: {task['title']}
DESCRIPTION: {task.get('description', 'No description provided')}
PRIORITY: {task.get('priority', 'normal')}

YOUR CAPABILITIES: {', '.join(capabilities)}

ACCEPTANCE CRITERIA:
{chr(10).join(f'• {criteria}' for criteria in task.get('acceptance_criteria', ['Task completed successfully']))}

GENERAL WORKFLOW:
1. Analyze the requirements thoroughly
2. Plan your approach and identify dependencies  
3. Implement changes following best practices
4. Test your implementation thoroughly
5. Document any important decisions or changes
6. Commit with a clear message referencing {task['id']}

Provide a final JSON status report with:
{{"status": "completed|blocked|failed", "summary": "description", "files_changed": ["list"], "issues": ["any problems encountered"]}}

Begin work now.
"""
    
    def execute_task(self, task: Dict[str, Any]):
        """Execute a single task"""
        self.logger.info(f"Starting task execution: {task['id']} - {task['title']}")
        
        # Update task status to in_progress
        self.update_task_status(task["id"], "in_progress", started_at=datetime.now(timezone.utc).isoformat())
        
        # Update worker status
        self.config["status"] = "working"
        self.config["current_task"] = task["id"]
        self.save_config()
        
        # Create task-specific prompt
        prompt = self.create_task_prompt(task)
        
        # Execute with Claude
        self.log_event("task_execution_start", {"task_id": task["id"]})
        result = self.run_claude_headless(prompt)
        
        # Handle completion
        if result["success"]:
            self.logger.info(f"Task {task['id']} completed successfully")
            self.update_task_status(
                task["id"], 
                "ready_for_review",
                completed_at=datetime.now(timezone.utc).isoformat(),
                execution_log=result["log_file"]
            )
        else:
            self.logger.error(f"Task {task['id']} failed: {result.get('error', 'Unknown error')}")
            self.update_task_status(
                task["id"],
                "failed", 
                failed_at=datetime.now(timezone.utc).isoformat(),
                failure_reason=result.get("error", "Unknown error"),
                execution_log=result.get("log_file")
            )
        
        # Update worker status back to idle
        self.config["status"] = "idle"
        self.config["current_task"] = None
        self.config["total_tasks_completed"] = self.config.get("total_tasks_completed", 0) + 1
        self.save_config()
        
        self.log_event("task_execution_complete", {
            "task_id": task["id"],
            "success": result["success"],
            "final_status": "ready_for_review" if result["success"] else "failed"
        })
    
    def run_work_cycle(self):
        """Run one work cycle - check for assigned tasks and execute if found"""
        if not self.config.get("is_enabled", False):
            return
        
        # Update heartbeat
        self.save_config()
        
        # Check for assigned tasks
        task = self.get_assigned_task()
        if task:
            self.execute_task(task)
        else:
            # No task assigned, remain idle
            if self.config.get("status") != "idle":
                self.config["status"] = "idle"
                self.save_config()
    
    def run(self, cycle_interval: int = 15):
        """Run the worker main loop"""
        self.logger.info(f"Starting {self.worker_id} worker (cycle interval: {cycle_interval}s)")
        self.running = True
        
        # Initial status
        self.config["status"] = "idle"
        self.config["current_task"] = None
        self.save_config()
        
        try:
            while self.running:
                self.run_work_cycle()
                time.sleep(cycle_interval)
        except KeyboardInterrupt:
            self.logger.info(f"{self.worker_id} worker stopped by user")
        finally:
            self.running = False
            self.config["status"] = "offline"
            self.save_config()
            self.logger.info(f"{self.worker_id} worker shutdown complete")

def main():
    """Main entry point for individual worker process"""
    parser = argparse.ArgumentParser(description="Hive Headless Worker")
    parser.add_argument("worker_id", help="Worker ID (queen, frontend, backend, infra)")
    parser.add_argument("--interval", type=int, default=15, help="Cycle interval in seconds")
    parser.add_argument("--root", default=".", help="Root directory")
    
    args = parser.parse_args()
    
    worker = HeadlessWorker(args.worker_id, args.root)
    worker.run(args.interval)

if __name__ == "__main__":
    main()
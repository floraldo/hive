from orchestrator.tmux_controller import TmuxController
from plugins.gitops.workflow import GitWorkflow
import argparse

class HiveOrchestrator:
    def __init__(self, dry_run=False, auto_merge=True):
        self.tmux = TmuxController()
        self.git = GitWorkflow(dry_run=dry_run, auto_merge=auto_merge)
        
    def run_task(self, goal):
        """Complete task execution cycle"""
        print(f"\n👑 Queen initiating task: {goal}")
        
        # 1. Create feature branch
        branch = self.git.create_feature_branch(goal)
        
        # 2. Queen creates plan
        queen_prompt = f"""
        You are the Queen of the hive. Create a detailed execution plan for:
        '{goal}'
        
        Requirements:
        - Break into 3-5 atomic steps (<30min each)
        - Assign to workers: Backend, Frontend, or Infra
        - Define clear acceptance criteria
        - Consider dependencies between steps
        """
        
        task_id = self.tmux.send_to_agent("Queen", queen_prompt)
        queen_status = self.tmux.read_agent_status("Queen", task_id, timeout=60)
        
        if queen_status["status"] != "success":
            print(f"❌ Queen planning failed: {queen_status}")
            return False
        
        # 3. Parse and delegate to workers
        # For demo, using simple static delegation
        worker_tasks = {
            "Worker1-Backend": f"Implement backend for: {goal}",
            "Worker2-Frontend": f"Implement frontend for: {goal}",
        }
        
        task_ids = {}
        for worker, task in worker_tasks.items():
            task_ids[worker] = self.tmux.send_to_agent(worker, task)
        
        # 4. Collect results
        results = {}
        for worker, tid in task_ids.items():
            results[worker] = self.tmux.read_agent_status(worker, tid, timeout=120)
            print(f"  {worker}: {results[worker]['status']}")
        
        # 5. Commit and create PR if successful
        if all(r["status"] == "success" for r in results.values()):
            self.git.commit_and_push(branch, f"feat: {goal}")
            pr_url = self.git.create_pr(branch, f"feat: {goal}")
            
            if pr_url:
                print(f"\n✅ Task complete! PR: {pr_url}")
                return True
        
        print(f"\n❌ Task failed. Check logs for details")
        return False
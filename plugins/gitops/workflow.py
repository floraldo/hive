import git
import subprocess
import time  # Fixed: was missing in original
import json
from pathlib import Path
from urllib.parse import quote_plus

class GitWorkflow:
    def __init__(self, repo_path=".", dry_run=False, auto_merge=True):
        self.repo = git.Repo(repo_path)
        self.dry_run = dry_run
        self.auto_merge = auto_merge
        
    def create_feature_branch(self, feature_name):
        """Create feature branch from main"""
        safe_name = quote_plus(feature_name.lower().replace(" ", "-"))[:30]
        branch_name = f"feature/{safe_name}-{int(time.time())}"
        
        if not self.dry_run:
            # Ensure main is up to date
            self.repo.git.checkout("main")
            self.repo.git.pull()
            
            # Create and checkout new branch
            new_branch = self.repo.create_head(branch_name)
            new_branch.checkout()
            print(f"✅ Created branch: {branch_name}")
        else:
            print(f"[DRY RUN] Would create branch: {branch_name}")
        
        return branch_name
    
    def commit_and_push(self, branch_name, message):
        """Commit changes and push to remote"""
        if self.dry_run:
            print(f"[DRY RUN] Would commit: {message}")
            return True
        
        if not self.repo.is_dirty(untracked_files=True):
            print("No changes to commit")
            return False
        
        self.repo.git.add(A=True)
        self.repo.index.commit(message)
        self.repo.git.push("--set-upstream", "origin", branch_name)
        print(f"✅ Pushed changes to {branch_name}")
        return True
    
    def create_pr(self, branch_name, title, body=""):
        """Create PR with optional auto-merge"""
        if self.dry_run:
            print(f"[DRY RUN] Would create PR: {title}")
            return "dry-run-pr-url"
        
        # Check for kill switch file
        if Path(".ops/PAUSE").exists():
            print("🛑 PAUSE file detected. Skipping PR creation.")
            return None
        
        # Create PR
        cmd = [
            "gh", "pr", "create",
            "--title", title,
            "--body", body or "Automated PR by Hive Queen",
            "--base", "main",
            "--head", branch_name
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ PR creation failed: {result.stderr}")
            return None
        
        pr_url = result.stdout.strip()
        print(f"✅ PR created: {pr_url}")
        
        # Check for hold label (kill switch)
        pr_number = pr_url.split('/')[-1]
        labels_cmd = ["gh", "pr", "view", pr_number, "--json", "labels"]
        labels_result = subprocess.run(labels_cmd, capture_output=True, text=True)
        
        if labels_result.returncode == 0:
            labels_data = json.loads(labels_result.stdout)
            if any(label['name'] == 'hold' for label in labels_data.get('labels', [])):
                print("🚦 'hold' label detected. Skipping auto-merge.")
                return pr_url
        
        # Enable auto-merge if configured
        if self.auto_merge:
            merge_cmd = ["gh", "pr", "merge", pr_url, "--auto", "--squash"]
            subprocess.run(merge_cmd)
            print("✅ Auto-merge enabled (pending CI)")
        
        return pr_url
    
    def setup_worktrees(self):
        """Create isolated worktrees for each worker"""
        worktrees = {
            "backend": ("workspaces/backend", "worker/backend"),
            "frontend": ("workspaces/frontend", "worker/frontend"),
            "infra": ("workspaces/infra", "worker/infra")
        }
        
        for name, (path, branch) in worktrees.items():
            if not Path(path).exists():
                # Create branch if it doesn't exist
                try:
                    self.repo.git.branch(branch, "main")
                except:
                    pass  # Branch might already exist
                
                # Create worktree
                self.repo.git.worktree("add", path, branch)
                print(f"✅ Created worktree: {path} on branch {branch}")
    
    def push_worker_branches(self):
        """Push worker branches to remote"""
        branches = ["worker/backend", "worker/frontend", "worker/infra"]
        for branch in branches:
            try:
                self.repo.git.push("origin", branch)
                print(f"✅ Pushed {branch} to remote")
            except:
                pass  # Branch might already be pushed
#!/usr/bin/env python3
"""
Queen Launch Script - Automated startup for the Hive Queen
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def run_command(cmd, description="", check=True):
    """Run a command and handle errors"""
    print(f"🔄 {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"❌ Failed: {result.stderr}")
            return False
        if result.stdout.strip():
            print(f"   {result.stdout.strip()}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_dependencies():
    """Check and install dependencies"""
    print("🔍 Checking dependencies...")
    
    # Check Python packages
    try:
        import libtmux
        print("✅ libtmux installed")
    except ImportError:
        print("📦 Installing libtmux...")
        run_command("pip install libtmux", "Installing libtmux")
    
    # Check if packages are installed
    packages = [".", "packages/hive-api", "packages/hive-logging", "packages/hive-db", "packages/hive-deployment"]
    for pkg in packages:
        if Path(pkg).exists():
            run_command(f"pip install -e {pkg}", f"Installing {pkg}", check=False)

def setup_worktrees():
    """Create worker worktrees"""
    print("🌳 Setting up worker worktrees...")
    
    os.makedirs("workspaces", exist_ok=True)
    
    workers = ["backend", "frontend", "infra"]
    for worker in workers:
        worker_path = f"workspaces/{worker}"
        if not Path(worker_path).exists():
            run_command(
                f"git worktree add {worker_path} -b worker/{worker}",
                f"Creating {worker} worktree",
                check=False
            )

def start_tmux_session():
    """Start the tmux session"""
    print("🐝 Starting Hive swarm...")
    
    # Kill existing session
    run_command("tmux kill-session -t hive-swarm", check=False)
    
    # Create new session
    commands = [
        'tmux new-session -d -s hive-swarm -n "Hive"',
        'tmux rename-pane -t hive-swarm:0.0 "Queen"',
        'tmux split-window -h -t hive-swarm:0',
        'tmux rename-pane -t hive-swarm:0.1 "Worker1-Backend"',
        'tmux split-window -v -t hive-swarm:0.0',
        'tmux rename-pane -t hive-swarm:0.2 "Worker2-Frontend"',
        'tmux split-window -v -t hive-swarm:0.1',
        'tmux rename-pane -t hive-swarm:0.3 "Worker3-Infra"',
    ]
    
    for cmd in commands:
        if not run_command(cmd, check=False):
            print("❌ Failed to create tmux session")
            return False
    
    # Send commands to panes
    pane_commands = [
        ('hive-swarm:0.0', 'echo "👑 Queen ready for orders"'),
        ('hive-swarm:0.1', 'cd workspaces/backend && echo "🔧 Backend worker ready"'),
        ('hive-swarm:0.2', 'cd workspaces/frontend && echo "🎨 Frontend worker ready"'),
        ('hive-swarm:0.3', 'cd workspaces/infra && echo "🏗️ Infra worker ready"'),
    ]
    
    for pane, cmd in pane_commands:
        run_command(f'tmux send-keys -t {pane} "{cmd}" C-m', check=False)
    
    return True

def launch_queen():
    """Launch the Queen orchestrator"""
    print("👑 Launching Queen orchestrator...")
    
    try:
        from orchestrator.main import HiveOrchestrator
        
        print("🚀 Queen is ready! Starting orchestration...")
        print("=" * 60)
        
        orchestrator = HiveOrchestrator(dry_run=False, auto_merge=True)
        
        print("\n👑 Queen awaits your command!")
        print("Suggested first mission:")
        print("Add a GET /api/health endpoint to apps/backend that returns JSON: {\"status\": \"ok\", \"service\": \"backend\", \"timestamp\": current_time}. Include a pytest test.")
        print("=" * 60)
        
        # Interactive mode
        while True:
            try:
                goal = input("\n👑 Your command (or 'exit'): ").strip()
                if goal.lower() in ['exit', 'quit', 'q']:
                    print("🐝 Queen shutting down...")
                    break
                
                if goal:
                    success = orchestrator.run_task(goal)
                    if success:
                        print("✅ Mission accomplished!")
                    else:
                        print("❌ Mission failed - check the tmux session for details")
                        
            except KeyboardInterrupt:
                print("\n🐝 Queen shutting down...")
                break
                
    except Exception as e:
        print(f"❌ Failed to start Queen: {e}")
        print("💡 Try: tmux attach-session -t hive-swarm")
        return False

def main():
    """Main launch sequence"""
    print("🚀 HIVE QUEEN LAUNCH SEQUENCE")
    print("=" * 40)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"📂 Working directory: {script_dir}")
    
    # Step 1: Dependencies
    check_dependencies()
    
    # Step 2: Worktrees
    setup_worktrees()
    
    # Step 3: Tmux session
    if not start_tmux_session():
        print("❌ Failed to start tmux session")
        print("💡 Make sure tmux is installed: sudo apt install tmux")
        return
    
    print("✅ Tmux session created!")
    print("💡 You can view it with: tmux attach-session -t hive-swarm")
    
    # Step 4: Launch Queen
    launch_queen()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Queen Launch Script - Simple version without emojis for Windows
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def run_command(cmd, description="", check=True):
    """Run a command and handle errors"""
    print(f"Running: {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"FAILED: {result.stderr}")
            return False
        if result.stdout.strip():
            print(f"   {result.stdout.strip()}")
        print("SUCCESS")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def check_dependencies():
    """Check and install dependencies"""
    print("\nChecking dependencies...")
    
    # Check Python packages
    try:
        import libtmux
        print("libtmux: INSTALLED")
    except ImportError:
        print("Installing libtmux...")
        run_command("pip install libtmux", "Installing libtmux")
    
    # Install packages
    packages = [".", "packages/hive-api", "packages/hive-logging", "packages/hive-db", "packages/hive-deployment"]
    for pkg in packages:
        if Path(pkg).exists():
            run_command(f"pip install -e {pkg}", f"Installing {pkg}", check=False)

def setup_worktrees():
    """Create worker worktrees"""
    print("\nSetting up worker worktrees...")
    
    os.makedirs("workspaces", exist_ok=True)
    
    workers = ["backend", "frontend", "infra", "queen"]
    for worker in workers:
        worker_path = f"workspaces/{worker}"
        if not Path(worker_path).exists():
            run_command(
                f"git worktree add {worker_path} -b worker/{worker}",
                f"Creating {worker} worktree",
                check=False
            )
        else:
            print(f"{worker} worktree: EXISTS")

def test_orchestrator():
    """Test if the orchestrator can be imported"""
    print("\nTesting orchestrator...")
    try:
        from orchestrator.main import HiveOrchestrator
        print("HiveOrchestrator: IMPORTED SUCCESSFULLY")
        
        # Try to create it (will fail due to no tmux, but that's expected)
        try:
            orchestrator = HiveOrchestrator(dry_run=True)
            print("Orchestrator: CREATED")
        except Exception as e:
            print(f"Orchestrator creation failed (expected without tmux): {e}")
            
        return True
    except Exception as e:
        print(f"IMPORT ERROR: {e}")
        return False

def show_next_steps():
    """Show what to do next"""
    print("\n" + "="*50)
    print("SETUP COMPLETE!")
    print("="*50)
    print("To start the Queen, you need tmux.")
    print("On Windows, use WSL:")
    print("")
    print("1. Open WSL terminal")
    print("2. cd /mnt/c/git/hive")  
    print("3. source .venv/bin/activate  (or create new venv)")
    print("4. sudo apt install tmux  (if needed)")
    print("5. bash setup.sh  (starts tmux session)")
    print("6. In another WSL terminal:")
    print("   python hive_cli.py run")
    print("")
    print("FIRST MISSION:")
    print('Add a GET /api/health endpoint to apps/backend that returns JSON: {"status": "ok", "service": "backend", "timestamp": current_time}. Include a pytest test.')
    print("="*50)

def main():
    """Main setup sequence"""
    print("HIVE QUEEN SETUP")
    print("================")
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"Working directory: {script_dir}")
    
    # Step 1: Dependencies
    check_dependencies()
    
    # Step 2: Worktrees
    setup_worktrees()
    
    # Step 3: Test orchestrator
    if test_orchestrator():
        show_next_steps()
    else:
        print("FAILED: Could not import orchestrator")

if __name__ == "__main__":
    main()
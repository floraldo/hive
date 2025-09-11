#!/usr/bin/env python3
"""
Hive Cleanup Script
Clears all worktrees, logs, results, tasks, hints, and bus data for a fresh start.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report results"""
    print(f"Cleaning {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] {description} completed")
        else:
            print(f"[WARN]  {description} completed with warnings: {result.stderr}")
    except Exception as e:
        print(f"[ERROR] {description} failed: {e}")

def clean_directory(path, description):
    """Clean a directory if it exists"""
    if Path(path).exists():
        print(f"Cleaning {description}...")
        try:
            shutil.rmtree(path)
            print(f"[OK] {description} completed")
        except Exception as e:
            print(f"[ERROR] {description} failed: {e}")
    else:
        print(f"[INFO]  {description} - directory doesn't exist")

def clean_files(pattern, description):
    """Clean files matching a pattern"""
    print(f"Cleaning {description}...")
    try:
        result = subprocess.run(f"find . -name '{pattern}' -delete 2>/dev/null || true", shell=True)
        print(f"[OK] {description} completed")
    except Exception as e:
        print(f"[ERROR] {description} failed: {e}")

def main():
    print("Hive Cleanup Script")
    print("=" * 50)
    
    # Change to hive directory
    os.chdir(Path(__file__).parent)
    print(f"Working in: {os.getcwd()}")
    
    # Clean worktrees
    clean_directory(".worktrees", "Clearing worktrees")
    
    # Clean hive subdirectories
    clean_directory("hive/bus", "Clearing bus logs")
    clean_directory("hive/results", "Clearing results")
    clean_directory("hive/operator/hints", "Clearing hints")
    clean_directory("hive/logs", "Clearing logs")
    
    # Clean any remaining log files
    clean_files("*.log", "Clearing log files")
    clean_files("events_*.jsonl", "Clearing event files")
    
    # Reset task statuses to queued
    print("Cleaning Resetting task statuses...")
    try:
        import json
        tasks_dir = Path("hive/tasks")
        if tasks_dir.exists():
            for task_file in tasks_dir.glob("*.json"):
                if task_file.name != "index.json":
                    with open(task_file, 'r') as f:
                        task = json.load(f)
                    
                    # Reset status and remove phase info
                    task['status'] = 'queued'
                    for key in ['current_phase', 'assigned_at', 'worktree', 'workspace_type', 'started_at', 'updated_at']:
                        if key in task:
                            del task[key]
                    
                    with open(task_file, 'w') as f:
                        json.dump(task, f, indent=2)
                    
                    print(f"  [OK] Reset {task_file.name} to queued")
        
        print("[OK] Task status reset completed")
    except Exception as e:
        print(f"[ERROR] Task status reset failed: {e}")
    
    # Kill any running worker processes
    print("Cleaning Checking for running worker processes...")
    try:
        # Find and kill any python processes running cc_worker.py
        result = subprocess.run("ps aux | grep 'cc_worker.py' | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true", 
                              shell=True, capture_output=True)
        print("[OK] Worker process cleanup completed")
    except Exception as e:
        print(f"[WARN]  Worker process cleanup: {e}")
    
    print("\n[SUCCESS] Hive cleanup completed!")
    print(" Summary:")
    print("  - Worktrees cleared")
    print("  - All logs cleared")
    print("  - Results cleared")
    print("  - Hints cleared")
    print("  - Task statuses reset to queued")
    print("  - Worker processes terminated")
    print("\n[READY] Ready for fresh start!")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Hive Cleanup Script v2.0 - Database Edition
Clears all database tasks, runs, workers, logs, and results for a fresh start.
Updated for database-driven architecture.
"""

import os
import shutil
import subprocess
import sys
import argparse
import sqlite3
from pathlib import Path

# Add database package to path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-core-db" / "src"))

def run_command(cmd, description):
    """Run a command and report results"""
    print(f"Cleaning {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] {description} completed")
        else:
            print(f"[WARN] {description} completed with warnings: {result.stderr}")
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
        print(f"[INFO] {description} - directory doesn't exist")

def clean_database():
    """Clean the database tables"""
    print("Cleaning database...")
    db_path = Path("hive/db/hive-internal.db")

    if not db_path.exists():
        print("[INFO] Database doesn't exist - will be created fresh")
        return

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get table counts before cleaning
        cursor.execute("SELECT COUNT(*) FROM tasks")
        task_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM runs")
        run_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM workers")
        worker_count = cursor.fetchone()[0]

        print(f"  Found: {task_count} tasks, {run_count} runs, {worker_count} workers")

        # Clear all tables
        cursor.execute("DELETE FROM runs")
        cursor.execute("DELETE FROM tasks")
        cursor.execute("DELETE FROM workers")

        conn.commit()
        conn.close()

        print(f"[OK] Database cleaned - removed {task_count} tasks, {run_count} runs, {worker_count} workers")

    except Exception as e:
        print(f"[ERROR] Database cleanup failed: {e}")

def clean_git_branches(preserve=False):
    """Clean up agent git branches unless preserve flag is set"""
    if preserve:
        print("[INFO] Preserving git branches (--keep-branches flag set)")
        return

    print("Cleaning agent git branches...")
    try:
        # First, remove any worktrees
        result = subprocess.run("git worktree prune", shell=True, capture_output=True, text=True)

        # Get list of agent branches (Windows compatible)
        result = subprocess.run('git branch | findstr "agent/"',
                              shell=True, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            branches = [line.strip().replace('*', '').strip() for line in result.stdout.strip().split('\n')]
            branches = [b for b in branches if b and 'agent/' in b]

            if branches:
                print(f"  Found {len(branches)} agent branches to clean")
                for branch in branches:
                    try:
                        subprocess.run(f'git branch -D "{branch}"', shell=True,
                                     capture_output=True, check=True)
                        print(f"  [OK] Deleted branch: {branch}")
                    except subprocess.CalledProcessError:
                        print(f"  [WARN] Could not delete branch: {branch}")
            else:
                print("  [OK] No agent branches found")
        else:
            print("  [OK] No agent branches found")

        print("[OK] Git branch cleanup completed")
    except Exception as e:
        print(f"[WARN] Git branch cleanup: {e}")

def kill_processes():
    """Kill any running Queen or worker processes"""
    print("Cleaning running processes...")
    try:
        # Kill Python processes that might be Queen or workers (Windows compatible)
        processes_to_kill = ['queen.py', 'worker.py', 'cc_worker.py']

        for process_name in processes_to_kill:
            try:
                # Windows tasklist and taskkill
                result = subprocess.run(f'tasklist /FI "IMAGENAME eq python.exe" /FO CSV | findstr "{process_name}"',
                                      shell=True, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    print(f"  Found running {process_name} processes")
                    # Use wmic to kill by command line (more precise)
                    subprocess.run(f'wmic process where "commandline like \'%{process_name}%\'" delete',
                                 shell=True, capture_output=True)
                    print(f"  [OK] Killed {process_name} processes")
            except Exception as e:
                print(f"  [WARN] Could not kill {process_name}: {e}")

        print("[OK] Process cleanup completed")
    except Exception as e:
        print(f"[WARN] Process cleanup: {e}")

def clean_results_and_logs():
    """Clean results and logs directories"""
    # Clean traditional directories
    clean_directory(".worktrees", "Clearing worktrees")
    clean_directory("hive/bus", "Clearing bus logs")
    clean_directory("hive/results", "Clearing results")
    clean_directory("hive/operator/hints", "Clearing hints")
    clean_directory("hive/logs", "Clearing logs")

    # Clean app-specific results
    clean_directory("apps/ecosystemiser/ecosystemiser_results", "Clearing EcoSystemiser results")

    # Clean any log files
    print("Cleaning log files...")
    try:
        for pattern in ["*.log", "events_*.jsonl"]:
            for file_path in Path(".").rglob(pattern):
                try:
                    file_path.unlink()
                    print(f"  [OK] Removed {file_path}")
                except Exception as e:
                    print(f"  [WARN] Could not remove {file_path}: {e}")
        print("[OK] Log file cleanup completed")
    except Exception as e:
        print(f"[ERROR] Log file cleanup failed: {e}")

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Clean Hive workspace and database for fresh start")
    parser.add_argument("--keep-branches", action="store_true",
                       help="Preserve git branches (don't delete agent/* branches)")
    parser.add_argument("--db-only", action="store_true",
                       help="Only clean database, skip files and processes")
    args = parser.parse_args()

    print("Hive Cleanup Script v2.0 - Database Edition")
    print("=" * 50)

    # Change to hive directory
    os.chdir(Path(__file__).parent)
    print(f"Working in: {os.getcwd()}")

    if args.db_only:
        print("[INFO] Database-only cleanup mode")
        clean_database()
    else:
        # Full cleanup
        # Kill processes first
        kill_processes()

        # Clean database
        clean_database()

        # Clean git branches (before removing worktrees)
        clean_git_branches(preserve=args.keep_branches)

        # Clean results and logs
        clean_results_and_logs()

    print("\n[SUCCESS] Hive cleanup completed!")
    print(" Summary:")
    if not args.db_only:
        print("  - Processes terminated")
        print("  - Git branches cleaned" if not args.keep_branches else "  - Git branches preserved")
        print("  - Worktrees cleared")
        print("  - All logs cleared")
        print("  - Results cleared")
        print("  - Hints cleared")
    print("  - Database tables cleared")
    print("\n[READY] Ready for fresh start!")

if __name__ == "__main__":
    main()
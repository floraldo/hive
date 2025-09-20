#!/usr/bin/env python3
"""
Hive Cleanup Script v2.0 - Database Edition
Clears all database tasks, runs, workers, logs, and results for a fresh start.
Updated for database-driven architecture.
"""

import os
import shutil
import subprocess
import argparse
from pathlib import Path

# Import database functions properly
try:
    from hive_core_db import close_connection
    from hive_core_db.database import get_connection, transaction
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parents[4] / "packages" / "hive-core-db" / "src"))
    from hive_core_db import close_connection
    from hive_core_db.database import get_connection, transaction

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
    """Clean the database tables using hive_core_db functions"""
    print("Cleaning database...")

    try:
        conn = get_connection()
        if not conn:
            print("[ERROR] Could not establish database connection")
            return

        cursor = conn.cursor()

        # Get table counts before cleaning with error handling
        try:
            cursor.execute("SELECT COUNT(*) FROM tasks")
            result = cursor.fetchone()
            task_count = result[0] if result else 0
        except Exception as e:
            print(f"[WARN] Could not count tasks: {e}")
            task_count = 0

        try:
            cursor.execute("SELECT COUNT(*) FROM runs")
            result = cursor.fetchone()
            run_count = result[0] if result else 0
        except Exception as e:
            print(f"[WARN] Could not count runs: {e}")
            run_count = 0

        try:
            cursor.execute("SELECT COUNT(*) FROM workers")
            result = cursor.fetchone()
            worker_count = result[0] if result else 0
        except Exception as e:
            print(f"[WARN] Could not count workers: {e}")
            worker_count = 0

        print(f"  Found: {task_count} tasks, {run_count} runs, {worker_count} workers")

        # Clear all tables in transaction with error handling
        try:
            with transaction() as conn:
                # Delete in correct order to respect foreign keys
                conn.execute("DELETE FROM runs")
                conn.execute("DELETE FROM workers")
                conn.execute("DELETE FROM tasks")
            print(f"[OK] Database cleaned - removed {task_count} tasks, {run_count} runs, {worker_count} workers")
        except Exception as e:
            print(f"[ERROR] Failed to delete database records: {e}")
            return

    except ImportError as e:
        print(f"[ERROR] Database module not available: {e}")
        print("  Make sure hive-core-db package is installed")
    except Exception as e:
        print(f"[ERROR] Database cleanup failed: {e}")
    finally:
        try:
            close_connection()
        except Exception as e:
            print(f"[WARN] Error closing database connection: {e}")

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
        killed_any = False

        for process_name in processes_to_kill:
            try:
                # Windows tasklist and taskkill
                result = subprocess.run(f'tasklist /FI "IMAGENAME eq python.exe" /FO CSV | findstr "{process_name}"',
                                      shell=True, capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    print(f"  Found running {process_name} processes")
                    # Use wmic to kill by command line (more precise)
                    kill_result = subprocess.run(f'wmic process where "commandline like \'%{process_name}%\'" delete',
                                                shell=True, capture_output=True, timeout=10)
                    if kill_result.returncode == 0:
                        print(f"  [OK] Killed {process_name} processes")
                        killed_any = True
                    else:
                        print(f"  [WARN] Failed to kill {process_name} processes: {kill_result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"  [WARN] Timeout while processing {process_name}")
            except FileNotFoundError:
                print(f"  [INFO] Process management commands not available (tasklist/wmic)")
                break
            except Exception as e:
                print(f"  [WARN] Could not kill {process_name}: {e}")

        if not killed_any:
            print("  [INFO] No processes found to kill")
        print("[OK] Process cleanup completed")
    except Exception as e:
        print(f"[WARN] Process cleanup failed: {e}")

def clean_results_and_logs():
    """Clean results and logs directories"""
    try:
        # Clean traditional directories with error handling
        directories_to_clean = [
            (".worktrees", "Clearing worktrees"),
            ("hive/bus", "Clearing bus logs"),
            ("hive/results", "Clearing results"),
            ("hive/operator/hints", "Clearing hints"),
            ("hive/logs", "Clearing logs"),
            ("apps/ecosystemiser/ecosystemiser_results", "Clearing EcoSystemiser results")
        ]

        for directory, description in directories_to_clean:
            try:
                clean_directory(directory, description)
            except Exception as e:
                print(f"[WARN] Error cleaning {directory}: {e}")

        # Clean any log files with improved error handling
        print("Cleaning log files...")
        files_removed = 0
        try:
            for pattern in ["*.log", "events_*.jsonl"]:
                try:
                    for file_path in Path(".").rglob(pattern):
                        try:
                            # Check if file is not in use
                            if file_path.exists() and file_path.is_file():
                                file_path.unlink()
                                print(f"  [OK] Removed {file_path}")
                                files_removed += 1
                        except PermissionError:
                            print(f"  [WARN] Permission denied: {file_path} (file may be in use)")
                        except Exception as e:
                            print(f"  [WARN] Could not remove {file_path}: {e}")
                except Exception as e:
                    print(f"  [WARN] Error processing pattern {pattern}: {e}")

            if files_removed > 0:
                print(f"[OK] Log file cleanup completed - removed {files_removed} files")
            else:
                print("[INFO] No log files found to remove")
        except Exception as e:
            print(f"[ERROR] Log file cleanup failed: {e}")
    except Exception as e:
        print(f"[ERROR] Results and logs cleanup failed: {e}")

def main():
    try:
        # Parse arguments
        parser = argparse.ArgumentParser(description="Clean Hive workspace and database for fresh start")
        parser.add_argument("--keep-branches", action="store_true",
                           help="Preserve git branches (don't delete agent/* branches)")
        parser.add_argument("--db-only", action="store_true",
                           help="Only clean database, skip files and processes")
        args = parser.parse_args()

        print("Hive Cleanup Script v2.0 - Database Edition")
        print("=" * 50)

        # Change to hive directory with validation
        try:
            target_dir = Path(__file__).parent
            if target_dir.exists() and target_dir.is_dir():
                os.chdir(target_dir)
                print(f"Working in: {os.getcwd()}")
            else:
                print(f"[ERROR] Target directory does not exist: {target_dir}")
                return 1
        except Exception as e:
            print(f"[ERROR] Could not change to target directory: {e}")
            return 1

        # Track success of operations
        operations_success = []

        if args.db_only:
            print("[INFO] Database-only cleanup mode")
            try:
                clean_database()
                operations_success.append("Database cleanup")
            except Exception as e:
                print(f"[ERROR] Database cleanup failed: {e}")
                return 1
        else:
            # Full cleanup with individual error handling
            try:
                print("\nStep 1: Kill processes")
                kill_processes()
                operations_success.append("Process cleanup")
            except Exception as e:
                print(f"[ERROR] Process cleanup failed: {e}")

            try:
                print("\nStep 2: Clean database")
                clean_database()
                operations_success.append("Database cleanup")
            except Exception as e:
                print(f"[ERROR] Database cleanup failed: {e}")

            try:
                print("\nStep 3: Clean git branches")
                clean_git_branches(preserve=args.keep_branches)
                operations_success.append("Git branch cleanup")
            except Exception as e:
                print(f"[ERROR] Git branch cleanup failed: {e}")

            try:
                print("\nStep 4: Clean results and logs")
                clean_results_and_logs()
                operations_success.append("Files cleanup")
            except Exception as e:
                print(f"[ERROR] Files cleanup failed: {e}")

        print("\n[SUCCESS] Hive cleanup completed!")
        print(" Summary:")
        if not args.db_only:
            if "Process cleanup" in operations_success:
                print("  ✓ Processes terminated")
            if "Git branch cleanup" in operations_success:
                print("  ✓ Git branches cleaned" if not args.keep_branches else "  ✓ Git branches preserved")
            if "Files cleanup" in operations_success:
                print("  ✓ Worktrees, logs, results, and hints cleared")
        if "Database cleanup" in operations_success:
            print("  ✓ Database tables cleared")

        if len(operations_success) > 0:
            print("\n[READY] Ready for fresh start!")
            return 0
        else:
            print("\n[WARNING] Some operations failed - check messages above")
            return 1

    except KeyboardInterrupt:
        print("\n[INFO] Cleanup interrupted by user")
        return 130
    except Exception as e:
        print(f"\n[ERROR] Unexpected error during cleanup: {e}")
        return 1

if __name__ == "__main__":
    main()
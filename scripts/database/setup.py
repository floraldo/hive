#!/usr/bin/env python3
"""Database Setup Tool - Consolidated Database Management

This script consolidates the functionality of multiple database scripts:
- init_db_simple.py
- optimize_database.py
- seed_database.py

Features:
- Database initialization and seeding
- Schema creation
- Sample data loading
- Database cleanup

Usage:
    python setup.py --help
    python setup.py --init
    python setup.py --seed
    python setup.py --all
"""

import argparse
import sqlite3
import sys
from pathlib import Path


class DatabaseSetup:
    """Consolidated database setup and management tool"""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("apps/hive-orchestrator/hive/db/hive-internal.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize_database(self) -> bool:
        """Initialize the database with required tables"""
        print("Initializing database...")
        print(f"Database path: {self.db_path}")

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'queued',
                    priority INTEGER DEFAULT 5,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    status TEXT DEFAULT 'running',
                    phase TEXT DEFAULT 'init',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    result TEXT,
                    error TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """,
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workers (
                    worker_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """,
            )

            conn.commit()
            conn.close()

            print("Database initialized successfully")
            return True

        except Exception as e:
            print(f"Error initializing database: {e}")
            return False

    def seed_database(self) -> bool:
        """Seed database with sample data"""
        print("Seeding database with sample data...")

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            sample_tasks = [
                (
                    "task-001",
                    "backend",
                    "Create Hello World script",
                    "queued",
                    3,
                    '{"tags": ["python", "simple"]}',
                ),
                (
                    "task-002",
                    "frontend",
                    "Build user interface",
                    "queued",
                    2,
                    '{"tags": ["ui", "react"]}',
                ),
                (
                    "task-003",
                    "database",
                    "Optimize query performance",
                    "queued",
                    1,
                    '{"tags": ["optimization", "sql"]}',
                ),
            ]

            cursor.executemany(
                """
                INSERT OR IGNORE INTO tasks (task_id, type, description, status, priority, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                sample_tasks,
            )

            sample_workers = [
                ("worker-backend-001", "backend", "active", '{"capabilities": ["python", "api"]}'),
                ("worker-frontend-001", "frontend", "active", '{"capabilities": ["react", "ui"]}'),
                ("worker-database-001", "database", "active", '{"capabilities": ["sql", "optimization"]}'),
            ]

            cursor.executemany(
                """
                INSERT OR IGNORE INTO workers (worker_id, role, status, metadata)
                VALUES (?, ?, ?, ?)
            """,
                sample_workers,
            )

            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM tasks")
            task_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM workers")
            worker_count = cursor.fetchone()[0]

            conn.close()

            print("Database seeded successfully")
            print(f"  - Tasks: {task_count}")
            print(f"  - Workers: {worker_count}")
            return True

        except Exception as e:
            print(f"Error seeding database: {e}")
            return False

    def optimize_database(self) -> bool:
        """Optimize database performance"""
        print("Optimizing database...")

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs(task_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")

            cursor.execute("VACUUM")
            cursor.execute("ANALYZE")

            conn.commit()
            conn.close()

            print("Database optimized successfully")
            return True

        except Exception as e:
            print(f"Error optimizing database: {e}")
            return False

    def clear_database(self) -> bool:
        """Clear all data from database"""
        print("Clearing database...")

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("DELETE FROM runs")
            cursor.execute("DELETE FROM tasks")
            cursor.execute("DELETE FROM workers")

            conn.commit()
            conn.close()

            print("Database cleared successfully")
            return True

        except Exception as e:
            print(f"Error clearing database: {e}")
            return False

    def show_statistics(self) -> bool:
        """Show database statistics"""
        print("\nDatabase Statistics")
        print("=" * 60)

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM tasks")
            task_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM runs")
            run_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM workers")
            worker_count = cursor.fetchone()[0]

            cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
            task_status = cursor.fetchall()

            print(f"Total Tasks: {task_count}")
            print(f"Total Runs: {run_count}")
            print(f"Total Workers: {worker_count}")

            if task_status:
                print("\nTasks by Status:")
                for status, count in task_status:
                    print(f"  - {status}: {count}")

            conn.close()
            return True

        except Exception as e:
            print(f"Error getting statistics: {e}")
            return False


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Database Setup Tool")
    parser.add_argument("--version", action="version", version="1.0.0")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--init", action="store_true", help="Initialize database schema")
    parser.add_argument("--seed", action="store_true", help="Seed database with sample data")
    parser.add_argument("--optimize", action="store_true", help="Optimize database performance")
    parser.add_argument("--clear", action="store_true", help="Clear all database data")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--all", action="store_true", help="Run all database operations (init, seed, optimize)")
    parser.add_argument("--db-path", type=Path, help="Custom database path")

    args = parser.parse_args()

    if not any([args.init, args.seed, args.optimize, args.clear, args.stats, args.all]):
        parser.print_help()
        return 0

    if args.dry_run:
        print("DRY RUN: No database operations would be executed.")
        return 0

    db_path = args.db_path if args.db_path else None
    setup = DatabaseSetup(db_path)

    print("Database Setup Tool - Consolidated Database Management")
    print("=" * 60)

    success = True

    try:
        if args.all or args.init:
            success &= setup.initialize_database()

        if args.all or args.seed:
            success &= setup.seed_database()

        if args.all or args.optimize:
            success &= setup.optimize_database()

        if args.clear:
            success &= setup.clear_database()

        if args.stats:
            success &= setup.show_statistics()

        if success:
            print("\nAll operations completed successfully!")
        else:
            print("\nSome operations failed. Check logs above.")

        return 0 if success else 1

    except Exception as e:
        print(f"\nDatabase setup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())







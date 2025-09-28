"""Simple database initialization script"""

import sys
import sqlite3
from pathlib import Path

# Add source to path
sys.path.insert(0, "apps/hive-orchestrator/src")
sys.path.insert(0, "packages/hive-config/src")
sys.path.insert(0, "packages/hive-db/src")
sys.path.insert(0, "packages/hive-logging/src")

DB_PATH = Path("apps/hive-orchestrator/hive/db/hive-internal.db")

def init_db():
    """Initialize the database with required tables"""

    # Ensure directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Create connection
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Create tasks table
    cursor.execute("""
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
    """)

    # Create runs table
    cursor.execute("""
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
    """)

    # Create workers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            worker_id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        )
    """)

    conn.commit()
    conn.close()

    print(f"Database initialized at: {DB_PATH}")

if __name__ == "__main__":
    init_db()
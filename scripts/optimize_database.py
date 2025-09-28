#!/usr/bin/env python3
"""
Database optimization script for Hive platform

Adds indexes, analyzes query patterns, and optimizes database performance.
"""

import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Tuple

from hive_config.paths import DB_PATH
from hive_logging import get_logger

logger = get_logger(__name__)


class DatabaseOptimizer:
    """Optimize Hive database with indexes and performance tuning"""

    def __init__(self, db_path: Path = DB_PATH):
        """Initialize database optimizer"""
        self.db_path = db_path
        self.conn = None
        self.indexes_created = []
        self.performance_metrics = {}

    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {self.db_path}")

    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")

    def analyze_current_state(self) -> Dict[str, any]:
        """Analyze current database state and performance"""
        cursor = self.conn.cursor()

        # Get table statistics
        cursor.execute("""
            SELECT name, sql FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = cursor.fetchall()

        # Get existing indexes
        cursor.execute("""
            SELECT name, tbl_name, sql FROM sqlite_master
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
        """)
        indexes = cursor.fetchall()

        # Get row counts
        table_stats = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table['name']}")
            count = cursor.fetchone()['count']
            table_stats[table['name']] = count

        return {
            'tables': [dict(t) for t in tables],
            'indexes': [dict(i) for i in indexes],
            'table_stats': table_stats
        }

    def create_indexes(self) -> List[str]:
        """Create optimized indexes for common query patterns"""
        cursor = self.conn.cursor()
        indexes = []

        # Tasks table indexes
        task_indexes = [
            ("idx_tasks_status_priority", "tasks", "(status, priority DESC, created_at)"),
            ("idx_tasks_status_created", "tasks", "(status, created_at)"),
            ("idx_tasks_type_status", "tasks", "(type, status)"),
            ("idx_tasks_updated", "tasks", "(updated_at DESC)"),
        ]

        # Runs table indexes
        run_indexes = [
            ("idx_runs_task_id", "runs", "(task_id, status, started_at)"),
            ("idx_runs_worker_status", "runs", "(worker_id, status)"),
            ("idx_runs_status_started", "runs", "(status, started_at DESC)"),
            ("idx_runs_completed", "runs", "(completed_at DESC) WHERE completed_at IS NOT NULL"),
        ]

        # Workers table indexes
        worker_indexes = [
            ("idx_workers_role_status", "workers", "(role, status)"),
            ("idx_workers_heartbeat", "workers", "(last_heartbeat DESC)"),
        ]

        all_indexes = task_indexes + run_indexes + worker_indexes

        for index_name, table_name, columns in all_indexes:
            try:
                # Check if index already exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,)
                )
                if cursor.fetchone():
                    logger.info(f"Index {index_name} already exists")
                    continue

                # Create index
                sql = f"CREATE INDEX {index_name} ON {table_name} {columns}"
                cursor.execute(sql)
                self.conn.commit()
                indexes.append(index_name)
                logger.info(f"Created index: {index_name}")

            except Exception as e:
                logger.error(f"Failed to create index {index_name}: {e}")

        self.indexes_created = indexes
        return indexes

    def optimize_database(self):
        """Run database optimization commands"""
        cursor = self.conn.cursor()

        optimizations = [
            "PRAGMA journal_mode = WAL",  # Write-Ahead Logging
            "PRAGMA synchronous = NORMAL",  # Balance safety and speed
            "PRAGMA cache_size = -20000",  # 20MB cache
            "PRAGMA temp_store = MEMORY",  # Use memory for temp tables
            "PRAGMA mmap_size = 268435456",  # 256MB memory-mapped I/O
            "PRAGMA foreign_keys = ON",  # Enforce foreign keys
            "VACUUM",  # Rebuild database file
            "ANALYZE",  # Update statistics
        ]

        for optimization in optimizations:
            try:
                cursor.execute(optimization)
                self.conn.commit()
                logger.info(f"Applied optimization: {optimization}")
            except Exception as e:
                logger.error(f"Failed to apply {optimization}: {e}")

    def benchmark_queries(self) -> Dict[str, float]:
        """Benchmark common query patterns"""
        cursor = self.conn.cursor()
        benchmarks = {}

        test_queries = [
            ("get_queued_tasks", """
                SELECT * FROM tasks
                WHERE status = 'queued'
                ORDER BY priority DESC, created_at
                LIMIT 100
            """),
            ("get_task_by_id", """
                SELECT * FROM tasks
                WHERE task_id = (SELECT task_id FROM tasks LIMIT 1)
            """),
            ("get_tasks_by_status", """
                SELECT * FROM tasks
                WHERE status = 'running'
            """),
            ("get_recent_runs", """
                SELECT r.*, t.type, t.description
                FROM runs r
                JOIN tasks t ON r.task_id = t.task_id
                WHERE r.status = 'completed'
                ORDER BY r.completed_at DESC
                LIMIT 50
            """),
            ("get_worker_tasks", """
                SELECT COUNT(*) as task_count, worker_id
                FROM runs
                WHERE status = 'running'
                GROUP BY worker_id
            """),
            ("get_task_statistics", """
                SELECT status, COUNT(*) as count
                FROM tasks
                GROUP BY status
            """),
        ]

        for query_name, query in test_queries:
            try:
                start_time = time.time()
                cursor.execute(query)
                cursor.fetchall()
                elapsed = (time.time() - start_time) * 1000  # Convert to ms
                benchmarks[query_name] = elapsed
                logger.info(f"Benchmark {query_name}: {elapsed:.2f}ms")
            except Exception as e:
                logger.error(f"Benchmark {query_name} failed: {e}")
                benchmarks[query_name] = -1

        self.performance_metrics = benchmarks
        return benchmarks

    def generate_report(self) -> str:
        """Generate optimization report"""
        report = []
        report.append("=" * 60)
        report.append("DATABASE OPTIMIZATION REPORT")
        report.append("=" * 60)
        report.append("")

        # Current state
        state = self.analyze_current_state()
        report.append("DATABASE STATE:")
        for table_name, count in state['table_stats'].items():
            report.append(f"  Table {table_name}: {count} rows")
        report.append(f"  Total indexes: {len(state['indexes'])}")
        report.append("")

        # Indexes created
        report.append("INDEXES CREATED:")
        if self.indexes_created:
            for index in self.indexes_created:
                report.append(f"  [OK] {index}")
        else:
            report.append("  No new indexes created (all already exist)")
        report.append("")

        # Performance benchmarks
        report.append("QUERY BENCHMARKS:")
        for query_name, elapsed in self.performance_metrics.items():
            if elapsed >= 0:
                status = "[OK]" if elapsed < 50 else "[SLOW]" if elapsed < 100 else "[CRITICAL]"
                report.append(f"  {status} {query_name}: {elapsed:.2f}ms")
            else:
                report.append(f"  [ERROR] {query_name}: Failed")

        # Calculate average
        valid_times = [t for t in self.performance_metrics.values() if t >= 0]
        if valid_times:
            avg_time = sum(valid_times) / len(valid_times)
            report.append(f"\n  Average query time: {avg_time:.2f}ms")

        report.append("")
        report.append("OPTIMIZATIONS APPLIED:")
        report.append("  - Write-Ahead Logging (WAL) enabled")
        report.append("  - 20MB cache configured")
        report.append("  - Memory-mapped I/O enabled (256MB)")
        report.append("  - Database vacuumed and analyzed")

        return "\n".join(report)

    def run_optimization(self) -> str:
        """Run complete optimization process"""
        try:
            self.connect()

            logger.info("Starting database optimization...")

            # Analyze current state
            initial_state = self.analyze_current_state()
            logger.info(f"Found {len(initial_state['tables'])} tables")

            # Create indexes
            self.create_indexes()

            # Apply optimizations
            self.optimize_database()

            # Benchmark performance
            self.benchmark_queries()

            # Generate report
            report = self.generate_report()

            return report

        finally:
            self.disconnect()


def main():
    """Main execution"""
    print("\n" + "=" * 60)
    print("HIVE DATABASE OPTIMIZATION")
    print("=" * 60 + "\n")

    optimizer = DatabaseOptimizer()

    try:
        report = optimizer.run_optimization()
        print(report)

        # Save report
        report_path = Path("claudedocs/database_optimization_report.txt")
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(report)
        print(f"\nReport saved to: {report_path}")

    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        print(f"\n[ERROR] Optimization failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
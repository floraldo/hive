"""Database Metadata Service for simulation index management."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from hive_db import get_sqlite_connection, sqlite_transaction
from hive_logging import get_logger

logger = get_logger(__name__)


class DatabaseMetadataService:
    """Service for managing simulation metadata in SQLite database."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize database metadata service.

        Args:
            db_path: Path to SQLite database file. If None, uses default location.,
        """
        self.db_path = db_path or "data/simulation_index.sqlite"
        self._ensure_database_schema()

    def _ensure_database_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            run_id TEXT PRIMARY KEY,
            study_id TEXT NOT NULL,
            system_id TEXT,
            timesteps INTEGER,
            timestamp TEXT,
            solver_type TEXT,
            simulation_status TEXT DEFAULT 'completed'
            -- Key Performance Indicators (for fast querying)
            total_cost REAL,
            total_co2 REAL,
            self_consumption_rate REAL,
            self_sufficiency_rate REAL,
            renewable_fraction REAL,
            total_generation_kwh REAL,
            total_demand_kwh REAL,
            net_grid_usage_kwh REAL
            -- File system references,
            results_path TEXT NOT NULL,
            flows_path TEXT,
            components_path TEXT
            -- Metadata,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT  -- Additional metadata as JSON
        );,

        CREATE INDEX IF NOT EXISTS idx_simulation_runs_study_id ON simulation_runs(study_id);,
        CREATE INDEX IF NOT EXISTS idx_simulation_runs_timestamp ON simulation_runs(timestamp);,
        CREATE INDEX IF NOT EXISTS idx_simulation_runs_solver_type ON simulation_runs(solver_type);,
        CREATE INDEX IF NOT EXISTS idx_simulation_runs_total_cost ON simulation_runs(total_cost);,
        CREATE INDEX IF NOT EXISTS idx_simulation_runs_renewable_fraction ON simulation_runs(renewable_fraction);,

        CREATE TABLE IF NOT EXISTS studies (
            study_id TEXT PRIMARY KEY,
            study_name TEXT,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            run_count INTEGER DEFAULT 0,
            metadata_json TEXT
        );,
        """

        try:
            with sqlite_transaction(db_path=self.db_path) as conn:
                conn.executescript(schema_sql)
            logger.info(f"Database schema initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise,

    def log_simulation_run(self, run_summary: dict[str, Any]) -> bool:
        """Log a simulation run to the database.

        Args:
            run_summary: Summary dictionary from EnhancedResultsIO.create_run_summary()

        Returns:
            True if successful, False otherwise,
        """
        try:
            # Prepare data for insertion
            run_data = {
                "run_id": run_summary.get("run_id"),
                "study_id": run_summary.get("study_id", "default_study")
                "system_id": run_summary.get("system_id"),
                "timesteps": run_summary.get("timesteps")
                "timestamp": run_summary.get("timestamp"),
                "solver_type": run_summary.get("solver_type", "unknown")
                "simulation_status": run_summary.get("simulation_status", "completed")
                # KPIs,
                "total_cost": run_summary.get("total_cost"),
                "total_co2": run_summary.get("total_co2")
                "self_consumption_rate": run_summary.get("self_consumption_rate"),
                "self_sufficiency_rate": run_summary.get("self_sufficiency_rate")
                "renewable_fraction": run_summary.get("renewable_fraction"),
                "total_generation_kwh": run_summary.get("total_generation_kwh")
                "total_demand_kwh": run_summary.get("total_demand_kwh"),
                "net_grid_usage_kwh": run_summary.get("net_grid_usage_kwh")
                # File paths,
                "results_path": run_summary.get("results_path"),
                "flows_path": run_summary.get("flows_path")
                "components_path": run_summary.get("components_path")
                # Metadata,
                "metadata_json": json.dumps(
                    {
                        k: v,
                        for k, v in run_summary.items()
                        if k
                        not in [
                            "run_id",
                            "study_id",
                            "system_id",
                            "timesteps",
                            "timestamp",
                            "solver_type",
                            "simulation_status",
                            "total_cost",
                            "total_co2",
                            "self_consumption_rate",
                            "self_sufficiency_rate",
                            "renewable_fraction",
                            "total_generation_kwh",
                            "total_demand_kwh",
                            "net_grid_usage_kwh",
                            "results_path",
                            "flows_path",
                            "components_path",
                        ]
                    }
                ),
                "updated_at": datetime.now().isoformat()
            }

            # Insert into database
            placeholders = ", ".join(["?" for _ in run_data])
            columns = ", ".join(run_data.keys())
            values = list(run_data.values())
            insert_sql = f"""
            INSERT OR REPLACE INTO simulation_runs ({columns})
            VALUES ({placeholders})
            """

            with sqlite_transaction(db_path=self.db_path) as conn:
                conn.execute(insert_sql, values)

            # Update study run count,
            self._update_study_run_count(run_data["study_id"])

            logger.info(f"Logged simulation run: {run_data['run_id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to log simulation run: {e}")
            return False

    def _update_study_run_count(self, study_id: str) -> None:
        """Update the run count for a study."""
        try:
            with sqlite_transaction(db_path=self.db_path) as conn:
                # Insert or update study,
                conn.execute(
                    """
                    INSERT OR IGNORE INTO studies (study_id, study_name)
                    VALUES (?, ?)
                """
                    (study_id, study_id)
                )

                # Update run count,
                conn.execute(
                    """
                    UPDATE studies,
                    SET run_count = (
                        SELECT COUNT(*) FROM simulation_runs,
                        WHERE study_id = ?
                    ),
                    WHERE study_id = ?,
                """
                    (study_id, study_id)
                ),

        except Exception as e:
            logger.warning(f"Failed to update study run count: {e}")

    def query_simulation_runs(
        self
        study_id: str | None = None,
        solver_type: str | None = None,
        min_cost: float | None = None,
        max_cost: float | None = None,
        min_renewable_fraction: float | None = None,
        limit: int | None = None,
        order_by: str = "timestamp",
        order_desc: bool = True
    ) -> list[dict[str, Any]]:
        """Query simulation runs with optional filters.

        Args:
            study_id: Filter by study ID,
            solver_type: Filter by solver type,
            min_cost: Minimum total cost,
            max_cost: Maximum total cost,
            min_renewable_fraction: Minimum renewable fraction,
            limit: Maximum number of results,
            order_by: Column to order by,
            order_desc: If True, order descending

        Returns:
            List of simulation run records,
        """
        try:
            # Build query with filters
            where_clauses = []
            params = []

            if study_id:
                where_clauses.append("study_id = ?")
                params.append(study_id)

            if solver_type:
                where_clauses.append("solver_type = ?")
                params.append(solver_type)

            if min_cost is not None:
                where_clauses.append("total_cost >= ?")
                params.append(min_cost)

            if max_cost is not None:
                where_clauses.append("total_cost <= ?")
                params.append(max_cost)

            if min_renewable_fraction is not None:
                where_clauses.append("renewable_fraction >= ?")
                params.append(min_renewable_fraction)

            # Build SQL query
            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)
            order_sql = f"ORDER BY {order_by} {'DESC' if order_desc else 'ASC'}"
            limit_sql = f"LIMIT {limit}" if limit else ""
            query = f"""
            SELECT * FROM simulation_runs
            {where_sql}
            {order_sql}
            {limit_sql},
            """

            conn = get_sqlite_connection(db_path=self.db_path)
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Convert to dictionaries
            results = []
            for row in rows:
                result = dict(row)
                # Parse metadata JSON,
                if result.get("metadata_json"):
                    try:
                        result["metadata"] = json.loads(result["metadata_json"])
                    except json.JSONDecodeError:
                        result["metadata"] = {}
                    del result["metadata_json"],
                results.append(result)

            logger.info(f"Query returned {len(results)} simulation runs"),
            return results

        except Exception as e:
            logger.error(f"Failed to query simulation runs: {e}"),
            return []

    def get_study_summary(self, study_id: str) -> dict[str, Any]:
        """Get summary statistics for a study.

        Args:
            study_id: Study identifier

        Returns:
            Dictionary with study statistics,
        """
        try:
            conn = get_sqlite_connection(db_path=self.db_path)

            # Get study info
            study_cursor = conn.execute(
                """
                SELECT * FROM studies WHERE study_id = ?,
            """
                (study_id)
            )
            study_row = study_cursor.fetchone()

            # Get run statistics
            stats_cursor = conn.execute(
                """
                SELECT,
                    COUNT(*) as run_count,
                    AVG(total_cost) as avg_cost,
                    MIN(total_cost) as min_cost,
                    MAX(total_cost) as max_cost,
                    AVG(renewable_fraction) as avg_renewable_fraction,
                    AVG(self_sufficiency_rate) as avg_self_sufficiency,
                    MIN(timestamp) as first_run,
                    MAX(timestamp) as last_run,
                FROM simulation_runs,
                WHERE study_id = ?,
            """
                (study_id)
            )
            stats_row = stats_cursor.fetchone()

            conn.close()
            summary = {
                "study_id": study_id,
                "study_info": dict(study_row) if study_row else {},
                "statistics": dict(stats_row) if stats_row else {}
            },

            return summary

        except Exception as e:
            logger.error(f"Failed to get study summary: {e}")
            return {"study_id": study_id, "error": str(e)}

    def get_database_stats(self) -> dict[str, Any]:
        """Get overall database statistics.

        Returns:
            Dictionary with database statistics,
        """
        try:
            conn = get_sqlite_connection(db_path=self.db_path)
            stats = {}

            # Total runs
            cursor = conn.execute("SELECT COUNT(*) as total_runs FROM simulation_runs")
            stats["total_runs"] = cursor.fetchone()[0]

            # Total studies
            cursor = conn.execute("SELECT COUNT(*) as total_studies FROM studies")
            stats["total_studies"] = cursor.fetchone()[0]

            # Solver type distribution
            cursor = conn.execute(
                """,
                SELECT solver_type, COUNT(*) as count,
                FROM simulation_runs,
                GROUP BY solver_type,
            """
            ),
            stats["solver_distribution"] = {row[0]: row[1] for row in cursor.fetchall()}

            # Performance ranges
            cursor = conn.execute(
                """,
                SELECT,
                    MIN(total_cost) as min_cost,
                    MAX(total_cost) as max_cost,
                    AVG(total_cost) as avg_cost,
                    MIN(renewable_fraction) as min_renewable,
                    MAX(renewable_fraction) as max_renewable,
                    AVG(renewable_fraction) as avg_renewable,
                FROM simulation_runs,
                WHERE total_cost IS NOT NULL AND renewable_fraction IS NOT NULL,
            """
            )
            performance_row = cursor.fetchone()
            if performance_row:
                stats["performance_ranges"] = dict(performance_row)

            conn.close()

            stats["database_path"] = self.db_path
            stats["last_updated"] = datetime.now().isoformat()

            return stats

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"error": str(e)}

    def delete_simulation_run(self, run_id: str) -> bool:
        """Delete a simulation run from the database.

        Args:
            run_id: Run identifier to delete

        Returns:
            True if successful, False otherwise,
        """
        try:
            with sqlite_transaction(db_path=self.db_path) as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM simulation_runs WHERE run_id = ?,
                """
                    (run_id)
                ),

                if cursor.rowcount > 0:
                    logger.info(f"Deleted simulation run: {run_id}")
                    return True
                else:
                    logger.warning(f"Simulation run not found: {run_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete simulation run: {e}")
            return False

    def cleanup_orphaned_records(self) -> int:
        """Remove database records for missing result files.

        Returns:
            Number of records cleaned up,
        """
        try:
            runs = self.query_simulation_runs()
            cleaned_count = 0

            for run in runs:
                results_path = run.get("results_path")
                if results_path and not Path(results_path).exists():
                    if self.delete_simulation_run(run["run_id"]):
                        cleaned_count += 1

            logger.info(f"Cleaned up {cleaned_count} orphaned records")
            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned records: {e}")
            return 0

"""
EcoSystemiser database schema definition.

This module defines and manages the database schema specific to EcoSystemiser,
including tables for simulations, studies, analysis results, and optimization runs.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from EcoSystemiser.db import get_ecosystemiser_connection
from EcoSystemiser.hive_logging_adapter import get_logger

logger = get_logger(__name__)


def ensure_database_schema(db_path: Optional[Path] = None):
    """
    Ensure all EcoSystemiser database tables exist.

    Args:
        db_path: Optional path to database (ignored, uses configured path)
    """
    with get_ecosystemiser_connection() as conn:
        _create_simulation_tables(conn)
        _create_study_tables(conn)
        _create_analysis_tables(conn)
        _create_optimization_tables(conn)
        _create_component_tables(conn)
        _create_event_tables(conn)
        conn.commit()
        logger.info("EcoSystemiser database schema initialized")


def _create_simulation_tables(conn: sqlite3.Connection):
    """Create tables for simulation data."""

    # Main simulations table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS simulations (
            simulation_id TEXT PRIMARY KEY,
            system_config_path TEXT NOT NULL,
            solver_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            duration_seconds REAL,
            results_path TEXT,
            error_message TEXT,
            metadata JSON
        )
    """)

    # Simulation metrics table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS simulation_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            unit TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (simulation_id) REFERENCES simulations (simulation_id)
        )
    """)

    # Create indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_simulations_status
        ON simulations(status, created_at)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_simulation_metrics_sim
        ON simulation_metrics(simulation_id, metric_name)
    """)


def _create_study_tables(conn: sqlite3.Connection):
    """Create tables for multi-simulation studies."""

    # Studies table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS studies (
            study_id TEXT PRIMARY KEY,
            study_type TEXT NOT NULL,
            status TEXT NOT NULL,
            total_simulations INTEGER,
            completed_simulations INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            duration_seconds REAL,
            results_path TEXT,
            configuration JSON,
            metadata JSON
        )
    """)

    # Study simulations mapping
    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_id TEXT NOT NULL,
            simulation_id TEXT NOT NULL,
            parameter_set JSON,
            sequence_number INTEGER,
            FOREIGN KEY (study_id) REFERENCES studies (study_id),
            FOREIGN KEY (simulation_id) REFERENCES simulations (simulation_id)
        )
    """)

    # Create indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_studies_status
        ON studies(status, created_at)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_study_simulations
        ON study_simulations(study_id, sequence_number)
    """)


def _create_analysis_tables(conn: sqlite3.Connection):
    """Create tables for analysis results."""

    # Analysis runs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_runs (
            analysis_id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            status TEXT NOT NULL,
            strategies_executed JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            duration_seconds REAL,
            results_path TEXT,
            error_message TEXT,
            metadata JSON
        )
    """)

    # Analysis results table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            result_type TEXT NOT NULL,
            result_data JSON NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_id) REFERENCES analysis_runs (analysis_id)
        )
    """)

    # Create indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_runs_source
        ON analysis_runs(source_type, source_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_results
        ON analysis_results(analysis_id, strategy_name)
    """)


def _create_optimization_tables(conn: sqlite3.Connection):
    """Create tables for optimization runs."""

    # Optimization runs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS optimization_runs (
            optimization_id TEXT PRIMARY KEY,
            algorithm_type TEXT NOT NULL,
            objective_function TEXT NOT NULL,
            status TEXT NOT NULL,
            generations_completed INTEGER DEFAULT 0,
            best_fitness REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            duration_seconds REAL,
            results_path TEXT,
            configuration JSON,
            metadata JSON
        )
    """)

    # Optimization iterations table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS optimization_iterations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            optimization_id TEXT NOT NULL,
            generation INTEGER NOT NULL,
            individual_id TEXT NOT NULL,
            fitness REAL NOT NULL,
            parameters JSON NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (optimization_id) REFERENCES optimization_runs (optimization_id)
        )
    """)

    # Create indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_optimization_runs_status
        ON optimization_runs(status, created_at)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_optimization_iterations
        ON optimization_iterations(optimization_id, generation, fitness)
    """)


def _create_component_tables(conn: sqlite3.Connection):
    """Create tables for component specifications."""

    # Component types table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS component_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Component specifications table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS component_specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_type_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '1.0.0',
            technical_params JSON NOT NULL,
            economic_params JSON,
            environmental_params JSON,
            metadata JSON,
            is_default BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (component_type_id) REFERENCES component_types (id),
            UNIQUE(component_type_id, name, version)
        )
    """)

    # Create indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_component_type
        ON component_specs (component_type_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_is_default
        ON component_specs (is_default)
    """)


def _create_event_tables(conn: sqlite3.Connection):
    """Create tables for EcoSystemiser events."""

    # Events table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ecosystemiser_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            source_agent TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            correlation_id TEXT,
            payload JSON NOT NULL,
            metadata JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Event subscriptions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscriber_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            callback_url TEXT,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ecosystemiser_events_type
        ON ecosystemiser_events(event_type, timestamp)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ecosystemiser_events_correlation
        ON ecosystemiser_events(correlation_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_subscriptions
        ON event_subscriptions(event_type, active)
    """)


def drop_all_tables(db_path: Optional[Path] = None):
    """
    Drop all EcoSystemiser database tables.

    WARNING: This will delete all data!

    Args:
        db_path: Optional path to database
    """
    conn = get_db_connection(db_path)
    try:
        # Get list of all tables
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [row[0] for row in cursor.fetchall()]

        # Drop each table
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            logger.info(f"Dropped table: {table}")

        conn.commit()
        logger.warning("All EcoSystemiser database tables dropped")
    finally:
        conn.close()
"""
SQLite-based component data loader for the Component Library.

This module provides a SQLite backend for storing and retrieving component
specifications, replacing the YAML-based system with a proper database.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import contextmanager

from hive_logging import get_logger
from ecosystemiser.db import get_ecosystemiser_connection

logger = get_logger(__name__)


class SQLiteLoader:
    """SQLite-based loader for component specifications."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the SQLite loader.

        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
        """
        if db_path is None:
            db_path = Path(__file__).parent / "components.db"

        self.db_path = db_path
        self._init_database()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections using shared service."""
        with get_ecosystemiser_connection() as conn:
            yield conn

    def _init_database(self):
        """Initialize the database schema if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create component_types table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS component_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create component_specs table
            cursor.execute("""
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

            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_component_type
                ON component_specs (component_type_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_is_default
                ON component_specs (is_default)
            """)

            # Create version history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS version_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_spec_id INTEGER NOT NULL,
                    version TEXT NOT NULL,
                    change_description TEXT,
                    changed_by TEXT,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (component_spec_id) REFERENCES component_specs (id)
                )
            """)

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def add_component_type(self, name: str, category: str, description: Optional[str] = None) -> int:
        """
        Add a new component type.

        Args:
            name: Component type name (e.g., 'battery', 'solar_pv')
            category: Category (e.g., 'energy', 'water')
            description: Optional description

        Returns:
            The ID of the created component type
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO component_types (name, category, description)
                VALUES (?, ?, ?)
            """, (name, category, description))
            conn.commit()

            # Get the ID
            cursor.execute("SELECT id FROM component_types WHERE name = ?", (name,))
            return cursor.fetchone()[0]

    def add_component_spec(
        self,
        component_type: str,
        name: str,
        technical_params: Dict[str, Any],
        economic_params: Optional[Dict[str, Any]] = None,
        environmental_params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
        is_default: bool = False
    ) -> int:
        """
        Add a component specification.

        Args:
            component_type: Type of component (e.g., 'battery')
            name: Name of this specific spec
            technical_params: Technical parameters as dict
            economic_params: Optional economic parameters
            environmental_params: Optional environmental parameters
            metadata: Optional metadata
            version: Version string
            is_default: Whether this is the default spec for the type

        Returns:
            The ID of the created specification
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get component type ID
            cursor.execute("SELECT id FROM component_types WHERE name = ?", (component_type,))
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"Component type '{component_type}' not found")

            type_id = result[0]

            # If marking as default, unset other defaults for this type
            if is_default:
                cursor.execute("""
                    UPDATE component_specs
                    SET is_default = 0
                    WHERE component_type_id = ?
                """, (type_id,))

            # Insert the specification
            cursor.execute("""
                INSERT INTO component_specs (
                    component_type_id, name, version, technical_params,
                    economic_params, environmental_params, metadata, is_default
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                type_id,
                name,
                version,
                json.dumps(technical_params),
                json.dumps(economic_params) if economic_params else None,
                json.dumps(environmental_params) if environmental_params else None,
                json.dumps(metadata) if metadata else None,
                is_default
            ))

            conn.commit()
            spec_id = cursor.lastrowid

            logger.info(f"Added component spec: {component_type}/{name} v{version}")
            return spec_id

    def get_component_spec(
        self,
        component_type: str,
        name: Optional[str] = None,
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a component specification.

        Args:
            component_type: Type of component
            name: Specific spec name (if None, gets default)
            version: Specific version (if None, gets latest)

        Returns:
            Component specification as dict
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT cs.*, ct.name as type_name, ct.category
                FROM component_specs cs
                JOIN component_types ct ON cs.component_type_id = ct.id
                WHERE ct.name = ?
            """
            params = [component_type]

            if name:
                query += " AND cs.name = ?"
                params.append(name)
            else:
                # Get default if no name specified
                query += " AND cs.is_default = 1"

            if version:
                query += " AND cs.version = ?"
                params.append(version)
            else:
                # Get latest version
                query += " ORDER BY cs.created_at DESC"

            query += " LIMIT 1"

            cursor.execute(query, params)
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"Component spec not found: {component_type}/{name or 'default'}")

            # Convert to dict
            spec = {
                "type": row["type_name"],
                "category": row["category"],
                "name": row["name"],
                "version": row["version"],
                "technical": json.loads(row["technical_params"]),
                "economic": json.loads(row["economic_params"]) if row["economic_params"] else {},
                "environmental": json.loads(row["environmental_params"]) if row["environmental_params"] else {},
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
            }

            return spec

    def list_component_types(self) -> List[Dict[str, Any]]:
        """
        List all available component types.

        Returns:
            List of component type dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ct.*, COUNT(cs.id) as spec_count
                FROM component_types ct
                LEFT JOIN component_specs cs ON ct.id = cs.component_type_id
                GROUP BY ct.id
                ORDER BY ct.category, ct.name
            """)

            types = []
            for row in cursor.fetchall():
                types.append({
                    "name": row["name"],
                    "category": row["category"],
                    "description": row["description"],
                    "spec_count": row["spec_count"]
                })

            return types

    def list_component_specs(self, component_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available component specifications.

        Args:
            component_type: Optional filter by component type

        Returns:
            List of component specification summaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT cs.name, cs.version, cs.is_default,
                       ct.name as type_name, ct.category
                FROM component_specs cs
                JOIN component_types ct ON cs.component_type_id = ct.id
            """

            params = []
            if component_type:
                query += " WHERE ct.name = ?"
                params.append(component_type)

            query += " ORDER BY ct.name, cs.name, cs.version"

            cursor.execute(query, params)

            specs = []
            for row in cursor.fetchall():
                specs.append({
                    "type": row["type_name"],
                    "category": row["category"],
                    "name": row["name"],
                    "version": row["version"],
                    "is_default": bool(row["is_default"])
                })

            return specs

    def export_to_yaml(self, output_dir: Path):
        """
        Export all component specs to YAML files for backup/migration.

        Args:
            output_dir: Directory to write YAML files to
        """
        import yaml

        output_dir.mkdir(parents=True, exist_ok=True)

        specs = self.list_component_specs()
        for spec_summary in specs:
            spec = self.get_component_spec(spec_summary["type"], spec_summary["name"])

            # Create category directory
            category_dir = output_dir / spec["category"]
            category_dir.mkdir(exist_ok=True)

            # Write YAML file
            filename = f"{spec['type']}_{spec['name']}_v{spec['version']}.yaml"
            file_path = category_dir / filename

            with open(file_path, 'w') as f:
                yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Exported {spec['type']}/{spec['name']} to {file_path}")

    def import_from_yaml(self, yaml_dir: Path):
        """
        Import component specs from YAML files.

        Args:
            yaml_dir: Directory containing YAML files
        """
        import yaml

        for yaml_file in yaml_dir.rglob("*.yaml"):
            with open(yaml_file, 'r') as f:
                spec = yaml.safe_load(f)

            # Ensure component type exists
            self.add_component_type(
                spec.get("type"),
                spec.get("category", "energy"),
                spec.get("description")
            )

            # Add the specification
            self.add_component_spec(
                component_type=spec["type"],
                name=spec["name"],
                technical_params=spec.get("technical", {}),
                economic_params=spec.get("economic"),
                environmental_params=spec.get("environmental"),
                metadata=spec.get("metadata"),
                version=spec.get("version", "1.0.0"),
                is_default=spec.get("is_default", False)
            )

            logger.info(f"Imported {spec['type']}/{spec['name']} from {yaml_file}")
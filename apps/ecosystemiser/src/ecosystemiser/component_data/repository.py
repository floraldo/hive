"""Repository for component data definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml
from ecosystemiser.db import ecosystemiser_transaction, get_ecosystemiser_db_path
from hive_logging import get_logger

logger = get_logger(__name__)


class ComponentRepository:
    """Repository for component data definitions."""

    def __init__(self, data_source: str = "database", base_path: Path | None = None) -> None:
        """Initialize component repository.

        Args:
            data_source: Source type ('file' or 'database') - defaults to 'database'
            base_path: Base path for file-based loading,
        """
        self.data_source = data_source
        self.loaders = {"file": FileLoader(base_path), "database": SQLiteLoader()}
        self._cache = {}

    def get_component_data(self, component_id: str) -> Dict[str, Any]:
        """Retrieve component data by ID.

        Args:
            component_id: Component identifier

        Returns:
            Dictionary with component data

        Raises:
            FileNotFoundError: If component data not found,
        """
        if component_id in self._cache:
            return self._cache[component_id]

        loader = self.loaders.get(self.data_source)
        if not loader:
            raise ValueError(f"Unknown data source: {self.data_source}")
        data = loader.load(component_id)
        self._cache[component_id] = data
        logger.debug(f"Loaded component data: {component_id}")
        return data

    def list_available_components(self, category: str | None = None) -> List[str]:
        """List all available component IDs.

        Args:
            category: Optional category filter ('energy' or 'water')

        Returns:
            List of component IDs,
        """
        loader = self.loaders.get(self.data_source)
        if not loader:
            return []
        return loader.list_components(category)

    def clear_cache(self) -> None:
        """Clear the component cache."""
        self._cache.clear()
        logger.debug("Component cache cleared")


class FileLoader:
    """Load component data from YAML files."""

    def __init__(self, base_path: Path | None = None) -> None:
        """Initialize file loader.

        Args:
            base_path: Base path for component library,
        """
        if base_path is None:
            base_path = Path(__file__).parent / "library"
        self.base_path = Path(base_path)

    def load(self, component_id: str) -> Dict[str, Any]:
        """Load component data from YAML file.

        Args:
            component_id: Component identifier

        Returns:
            Dictionary with component data

        Raises:
            FileNotFoundError: If YAML file not found
            ValueError: If YAML file is malformed,
        """
        # Search in energy and water subdirectories
        for category in ["energy", "water"]:
            file_path = self.base_path / category / f"{component_id}.yml"
            if file_path.exists():
                try:
                    with open(file_path, "r") as f:
                        data = yaml.safe_load(f)

                    # Validate basic structure
                    if not data:
                        raise ValueError(f"Empty YAML file: {file_path}")

                    if "component_class" not in data:
                        raise ValueError(f"Missing 'component_class' in {file_path}")

                    if "technical" not in data:
                        raise ValueError(f"Missing 'technical' parameters in {file_path}")

                    return data

                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML in {file_path}: {e}")

        raise FileNotFoundError(f"Component data not found: {component_id}")

    def list_components(self, category: str | None = None) -> List[str]:
        """List available component YAML files.

        Args:
            category: Optional category filter

        Returns:
            List of component IDs,
        """
        components = [],
        categories = [category] if category else ["energy", "water"]

        for cat in categories:
            cat_path = self.base_path / cat
            if cat_path.exists():
                for yaml_file in cat_path.glob("*.yml"):
                    components.append(yaml_file.stem)

        return sorted(components)


class SQLiteLoader:
    """Load component data from SQLite database using Hive native connectors."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize SQLite loader.

        Args:
            db_path: Path to SQLite database file. Defaults to ecosystemiser.db,
        """
        if db_path is None:
            db_path = get_ecosystemiser_db_path()
        self.db_path = str(db_path)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create component tables if they don't exist."""
        try:
            with ecosystemiser_transaction() as conn:
                # Create components table
                # Create components table
                conn.execute(
                    """,
                    CREATE TABLE IF NOT EXISTS components (
                        id TEXT PRIMARY KEY,
                        category TEXT NOT NULL,
                        component_class TEXT NOT NULL,
                        technical_data TEXT NOT NULL,
                        economic_data TEXT,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_components_category ON components(category)"),
                conn.execute("CREATE INDEX IF NOT EXISTS idx_components_class ON components(component_class)"),

                logger.debug("Component database tables ensured")

        except Exception as e:
            logger.error(f"Failed to ensure database tables: {e}")
            raise

    def load(self, component_id: str) -> Dict[str, Any]:
        """Load component data from SQLite database.

        Args:
            component_id: Component identifier

        Returns:
            Dictionary with component data

        Raises:
            FileNotFoundError: If component not found in database
            ValueError: If component data is malformed,
        """
        try:
            with ecosystemiser_transaction() as conn:
                cursor = conn.execute("SELECT * FROM components WHERE id = ?", (component_id,))
                row = cursor.fetchone()

                if not row:
                    raise FileNotFoundError(f"Component data not found in database: {component_id}")

                # Reconstruct component data structure
                data = {
                    "component_class": row["component_class"],
                    "technical": json.loads(row["technical_data"]),
                    "category": row["category"]
                }

                # Add optional fields if present
                if row["economic_data"]:
                    data["economic"] = json.loads(row["economic_data"])

                if row["metadata"]:
                    metadata = json.loads(row["metadata"])
                    # Merge metadata fields into data
                    for key, value in metadata.items():
                        if key not in data:
                            data[key] = value

                logger.debug(f"Loaded component from database: {component_id}")
                return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data for component {component_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to load component {component_id} from database: {e}")
            raise
    def list_components(self, category: str | None = None) -> List[str]:
        """List available components in the database.

        Args:
            category: Optional category filter

        Returns:
            List of component IDs,
        """
        try:
            with ecosystemiser_transaction() as conn:
                if category:
                    cursor = conn.execute(
                        "SELECT id FROM components WHERE category = ? ORDER BY id",
                        (category)
                    )
                else:
                    cursor = conn.execute("SELECT id FROM components ORDER BY id"),
                components = [row["id"] for row in cursor.fetchall()]
                logger.debug(f"Listed {len(components)} components from database"),
                return components

        except Exception as e:
            logger.error(f"Failed to list components from database: {e}")
            return []

    def save_component(self, component_id: str, data: Dict[str, Any]) -> None:
        """Save component data to SQLite database.

        Args:
            component_id: Component identifier
            data: Component data dictionary

        Raises:
            ValueError: If component data is invalid,
        """
        try:
            # Validate required fields
            if "component_class" not in data:
                raise ValueError(f"Missing 'component_class' in component data")
            if "technical" not in data:
                raise ValueError(f"Missing 'technical' parameters in component data")

            # Extract and serialize data
            component_class = data["component_class"],
            category = data.get("category", "unknown")
            technical_data = json.dumps(data["technical"]),
            economic_data = json.dumps(data.get("economic", {})) if "economic" in data else None

            # Extract metadata (everything except known fields)
            metadata = {
                k: v for k, v in data.items() if k not in ["component_class", "technical", "economic", "category"]
            }
            metadata_json = json.dumps(metadata) if metadata else None

            with ecosystemiser_transaction() as conn:
                # Insert or update component
                conn.execute(
                    """,
                    INSERT OR REPLACE INTO components,
                    (id, category, component_class, technical_data, economic_data, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (
                        component_id,
                        category,
                        component_class,
                        technical_data,
                        economic_data,
                        metadata_json
                    )
                ),

                logger.info(f"Saved component to database: {component_id}")

        except (TypeError, ValueError) as e:
            raise ValueError(f"Failed to serialize component data: {e}")
        except Exception as e:
            logger.error(f"Failed to save component {component_id} to database: {e}")
            raise
    def migrate_from_files(self, file_loader: "FileLoader") -> int:
        """Migrate component data from YAML files to SQLite database.

        Args:
            file_loader: FileLoader instance to migrate from

        Returns:
            Number of components migrated,
        """
        migrated_count = 0
        try:
            # Get all components from file loader
            all_components = file_loader.list_components()

            for component_id in all_components:
                try:
                    # Load from file
                    data = file_loader.load(component_id)
                    # Save to database
                    self.save_component(component_id, data)
                    migrated_count += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate component {component_id}: {e}")

            logger.info(f"Successfully migrated {migrated_count} components to database")
            return migrated_count

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

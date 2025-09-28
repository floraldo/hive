from hive_logging import get_logger
#!/usr/bin/env python3
"""
Migrate component library from YAML files to SQLite database.

This script performs a one-time migration of all component specifications
from the YAML file-based system to the new SQLite backend.
"""

import json
from pathlib import Path

# Use proper Poetry workspace imports - no path manipulation needed
from EcoSystemiser.component_data.repository import ComponentRepository, FileLoader, SQLiteLoader
from EcoSystemiser.hive_logging_adapter import get_logger

logger = get_logger(__name__)


def main():
    """Run the component migration."""
    logger.info("Starting component library migration to SQLite...")

    try:
        # Initialize the file loader
        file_loader = FileLoader()

        # Initialize the SQLite loader
        sqlite_loader = SQLiteLoader()

        # List all components from files
        all_components = file_loader.list_components()
        logger.info(f"Found {len(all_components)} components to migrate")

        # Track migration stats
        migrated = 0
        skipped = 0
        failed = 0

        for component_id in all_components:
            try:
                logger.info(f"  Migrating: {component_id}...", end="")

                # Load from YAML
                data = file_loader.load(component_id)

                # Determine category from file location
                for category in ["energy", "water"]:
                    file_path = file_loader.base_path / category / f"{component_id}.yml"
                    if file_path.exists():
                        data["category"] = category
                        break

                # Save to SQLite
                sqlite_loader.save_component(component_id, data)

                logger.info(" [OK]")
                migrated += 1

            except Exception as e:
                logger.error(f" [FAILED: {e}]")
                logger.error(f"Failed to migrate {component_id}: {e}")
                failed += 1

        # Verify migration
        logger.info("\nVerifying migration...")
        db_components = sqlite_loader.list_components()
        logger.info(f"  Components in database: {len(db_components)}")

        # Report results
        logger.info("\nMigration Summary:")
        logger.info(f"  Successfully migrated: {migrated}")
        logger.error(f"  Failed: {failed}")
        logger.info(f"  Skipped: {skipped}")

        if failed > 0:
            logger.error("\nWARNING: Some components failed to migrate. Check the logs for details.")
            return 1
        else:
            logger.info("\nMigration completed successfully!")
            logger.info("The ComponentRepository will now use SQLite by default.")
            return 0

    except Exception as e:
        logger.error(f"\nERROR: Migration failed: {e}")
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
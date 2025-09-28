"""File adapter for loading demand profiles."""

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from hive_logging import get_logger

logger = get_logger(__name__)


class DemandFileAdapter:
    """Adapter for loading demand profiles from files."""

    def fetch(self, config: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """Load demand profiles from file.

        Args:
            config: Configuration dictionary with:
                - file_path: Path to CSV file
                - column_mapping: Dict mapping profile names to column names

        Returns:
            Dictionary of profile arrays
        """
        profiles = {}

        file_path = config.get("file_path")
        if not file_path:
            logger.warning("No demand file path specified")
            return profiles

        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"Demand file not found: {file_path}")
            return profiles

        try:
            # Load CSV file
            df = pd.read_csv(file_path)

            # Map columns to profile names
            column_mapping = config.get("column_mapping", {})

            for profile_name, column_name in column_mapping.items():
                if column_name in df.columns:
                    profiles[profile_name] = df[column_name].values
                    logger.info(f"Loaded demand profile '{profile_name}' from column '{column_name}'")
                else:
                    logger.warning(f"Column '{column_name}' not found in demand file")

            # If no mapping provided, use all columns
            if not column_mapping:
                for col in df.columns:
                    if col not in ["time", "timestamp", "index"]:  # Skip time columns
                        profiles[col] = df[col].values
                        logger.info(f"Loaded demand profile '{col}'")

        except Exception as e:
            logger.error(f"Error loading demand profiles: {e}")

        return profiles

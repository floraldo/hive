"""Repository for component data definitions."""
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
from EcoSystemiser.hive_logging_adapter import get_logger
logger = get_logger(__name__)

class ComponentRepository:
    """Repository for component data definitions."""

    def __init__(self, data_source: str = "file", base_path: Optional[Path] = None):
        """Initialize component repository.

        Args:
            data_source: Source type ('file' or future: 'database')
            base_path: Base path for file-based loading
        """
        self.data_source = data_source
        self.loaders = {
            "file": FileLoader(base_path),
            # Future: "database": DatabaseLoader()
        }
        self._cache = {}

    def get_component_data(self, component_id: str) -> Dict[str, Any]:
        """Retrieve component data by ID.

        Args:
            component_id: Component identifier

        Returns:
            Dictionary with component data

        Raises:
            FileNotFoundError: If component data not found
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

    def list_available_components(self, category: Optional[str] = None) -> List[str]:
        """List all available component IDs.

        Args:
            category: Optional category filter ('energy' or 'water')

        Returns:
            List of component IDs
        """
        loader = self.loaders.get(self.data_source)
        if not loader:
            return []
        return loader.list_components(category)

    def clear_cache(self):
        """Clear the component cache."""
        self._cache.clear()
        logger.debug("Component cache cleared")

class FileLoader:
    """Load component data from YAML files."""

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize file loader.

        Args:
            base_path: Base path for component library
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
            ValueError: If YAML file is malformed
        """
        # Search in energy and water subdirectories
        for category in ["energy", "water"]:
            file_path = self.base_path / category / f"{component_id}.yml"
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        data = yaml.safe_load(f)

                    # Validate basic structure
                    if not data:
                        raise ValueError(f"Empty YAML file: {file_path}")

                    if 'component_class' not in data:
                        raise ValueError(f"Missing 'component_class' in {file_path}")

                    if 'technical' not in data:
                        raise ValueError(f"Missing 'technical' parameters in {file_path}")

                    return data

                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML in {file_path}: {e}")

        raise FileNotFoundError(f"Component data not found: {component_id}")

    def list_components(self, category: Optional[str] = None) -> List[str]:
        """List available component YAML files.

        Args:
            category: Optional category filter

        Returns:
            List of component IDs
        """
        components = []
        categories = [category] if category else ["energy", "water"]

        for cat in categories:
            cat_path = self.base_path / cat
            if cat_path.exists():
                for yaml_file in cat_path.glob("*.yml"):
                    components.append(yaml_file.stem)

        return sorted(components)
"""Test SQLite component backend implementation."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ecosystemiser.component_data.repository import (
    ComponentRepository,
    FileLoader,
    SQLiteLoader,
)


class TestSQLiteLoader:
    """Test the SQLite component loader."""

    def test_initialization(self):
        """Test SQLiteLoader initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            loader = SQLiteLoader(str(db_path))
            assert loader.db_path == str(db_path)
            # Database file should be created
            assert db_path.exists()

    def test_save_and_load_component(self):
        """Test saving and loading a component."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            loader = SQLiteLoader(str(db_path))

            # Sample component data
            component_data = {
                "component_class": "Battery",
                "category": "energy",
                "technical": {
                    "capacity": 10.0,
                    "power_rating": 5.0,
                    "efficiency": 0.95,
                },
                "economic": {"capex": 5000, "opex": 100},
                # Metadata fields go at root level, not in a metadata dict
                "vendor": "TestCorp",
                "model": "TB-100",
            }

            # Save component
            loader.save_component("test_battery", component_data)

            # Load component
            loaded = loader.load("test_battery")

            # Verify data
            assert loaded["component_class"] == "Battery"
            assert loaded["category"] == "energy"
            assert loaded["technical"]["capacity"] == 10.0
            assert loaded["economic"]["capex"] == 5000
            # Metadata fields should be unpacked at root level
            assert loaded["vendor"] == "TestCorp"
            assert loaded["model"] == "TB-100"

    def test_list_components(self):
        """Test listing components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            loader = SQLiteLoader(str(db_path))

            # Add some components
            loader.save_component(
                "battery1",
                {
                    "component_class": "Battery",
                    "category": "energy",
                    "technical": {"capacity": 10.0},
                },
            )
            loader.save_component(
                "water_tank1",
                {
                    "component_class": "WaterStorage",
                    "category": "water",
                    "technical": {"volume": 1000},
                },
            )

            # List all components
            all_components = loader.list_components()
            assert len(all_components) == 2
            assert "battery1" in all_components
            assert "water_tank1" in all_components

            # List by category
            energy_components = loader.list_components("energy")
            assert len(energy_components) == 1
            assert "battery1" in energy_components

            water_components = loader.list_components("water")
            assert len(water_components) == 1
            assert "water_tank1" in water_components

    def test_component_not_found(self):
        """Test loading non-existent component."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            loader = SQLiteLoader(str(db_path))

            with pytest.raises(FileNotFoundError) as exc_info:
                loader.load("non_existent")
            assert "not found" in str(exc_info.value).lower()

    def test_invalid_component_data(self):
        """Test saving invalid component data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            loader = SQLiteLoader(str(db_path))

            # Missing component_class
            with pytest.raises(ValueError) as exc_info:
                loader.save_component("invalid1", {"technical": {}})
            assert "component_class" in str(exc_info.value)

            # Missing technical parameters
            with pytest.raises(ValueError) as exc_info:
                loader.save_component("invalid2", {"component_class": "Test"})
            assert "technical" in str(exc_info.value)


class TestComponentRepository:
    """Test the ComponentRepository with SQLite backend."""

    def test_default_to_database(self):
        """Test that repository defaults to database backend."""
        repo = ComponentRepository()
        assert repo.data_source == "database"

    @patch("EcoSystemiser.component_data.repository.SQLiteLoader")
    def test_get_component_data_from_database(self, mock_sqlite_loader):
        """Test getting component data from database backend."""
        # Setup mock
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = {
            "component_class": "Battery",
            "technical": {"capacity": 10.0},
        }
        mock_sqlite_loader.return_value = mock_loader_instance

        # Create repository
        repo = ComponentRepository(data_source="database")

        # Get component
        data = repo.get_component_data("test_battery")

        # Verify
        assert data["component_class"] == "Battery"
        assert data["technical"]["capacity"] == 10.0
        mock_loader_instance.load.assert_called_once_with("test_battery")

    def test_cache_functionality(self):
        """Test that repository caches loaded components."""
        with patch(
            "EcoSystemiser.component_data.repository.SQLiteLoader"
        ) as mock_sqlite_loader:
            # Setup mock
            mock_loader_instance = MagicMock()
            mock_loader_instance.load.return_value = {
                "component_class": "Battery",
                "technical": {"capacity": 10.0},
            }
            mock_sqlite_loader.return_value = mock_loader_instance

            # Create repository
            repo = ComponentRepository(data_source="database")

            # First load - should call loader
            data1 = repo.get_component_data("test_battery")
            assert mock_loader_instance.load.call_count == 1

            # Second load - should use cache
            data2 = repo.get_component_data("test_battery")
            assert mock_loader_instance.load.call_count == 1  # Still 1

            # Both should return same data
            assert data1 == data2

            # Clear cache
            repo.clear_cache()

            # Third load - should call loader again
            data3 = repo.get_component_data("test_battery")
            assert mock_loader_instance.load.call_count == 2

    def test_migrate_from_files(self):
        """Test migration from YAML files to SQLite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            sqlite_loader = SQLiteLoader(str(db_path))

            # Create mock file loader
            mock_file_loader = MagicMock()
            mock_file_loader.list_components.return_value = ["battery1", "solar1"]
            mock_file_loader.load.side_effect = [
                {
                    "component_class": "Battery",
                    "technical": {"capacity": 10.0},
                    "category": "energy",
                },
                {
                    "component_class": "SolarPV",
                    "technical": {"power": 5.0},
                    "category": "energy",
                },
            ]

            # Run migration
            migrated = sqlite_loader.migrate_from_files(mock_file_loader)

            # Verify migration
            assert migrated == 2
            assert mock_file_loader.list_components.called
            assert mock_file_loader.load.call_count == 2

            # Verify components were saved
            components = sqlite_loader.list_components()
            assert len(components) == 2
            assert "battery1" in components
            assert "solar1" in components


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

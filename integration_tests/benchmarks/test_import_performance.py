"""Performance benchmarks for import operations and package loading.
"""
import importlib
import sys

import pytest


@pytest.mark.crust
class TestImportPerformance:
    """Benchmark tests for import and module loading performance."""

    @pytest.mark.crust
    def test_hive_package_import_performance(self, benchmark):
        """Benchmark importing core hive packages."""

        def import_hive_packages():
            imported_modules = []
            hive_packages = ["hive_db", "hive_logging", "hive_config", "hive_tests"]
            for package_name in hive_packages:
                try:
                    if package_name in sys.modules:
                        del sys.modules[package_name]
                    module = importlib.import_module(package_name)
                    imported_modules.append(module)
                except ImportError:
                    pass
            return len(imported_modules)
        result = benchmark(import_hive_packages)
        assert result >= 1

    @pytest.mark.crust
    def test_standard_library_import_performance(self, benchmark):
        """Benchmark importing standard library modules."""

        def import_stdlib_modules():
            stdlib_modules = ["os", "sys", "json", "sqlite3", "asyncio", "datetime", "pathlib", "tempfile", "subprocess", "concurrent.futures"]
            imported_count = 0
            for module_name in stdlib_modules:
                try:
                    importlib.import_module(module_name)
                    imported_count += 1
                except ImportError:
                    pass
            return imported_count
        result = benchmark(import_stdlib_modules)
        assert result >= 8

    @pytest.mark.crust
    def test_dynamic_import_performance(self, benchmark):
        """Benchmark dynamic module imports."""

        def dynamic_imports():
            import_count = 0
            dynamic_modules = [("json", "loads"), ("sqlite3", "connect"), ("os.path", "exists"), ("datetime", "datetime"), ("pathlib", "Path")]
            for module_name, attr_name in dynamic_modules:
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, attr_name):
                        import_count += 1
                except ImportError:
                    pass
            return import_count
        result = benchmark(dynamic_imports)
        assert result >= 4

    @pytest.mark.crust
    def test_package_attribute_access_performance(self, benchmark):
        """Benchmark accessing attributes from imported packages."""
        import json
        import os
        import sqlite3
        import sys

        def attribute_access():
            access_count = 0
            attributes_to_test = [(os, "path"), (sys, "version"), (json, "loads"), (sqlite3, "connect"), (os.path, "exists"), (sys, "platform")]
            for module, attr_name in attributes_to_test:
                if hasattr(module, attr_name):
                    getattr(module, attr_name)
                    access_count += 1
            return access_count
        result = benchmark(attribute_access)
        assert result >= 5

    @pytest.mark.crust
    def test_module_reload_performance(self, benchmark):
        """Benchmark module reloading operations."""

        def module_reload_test():
            reload_count = 0
            modules_to_reload = ["json", "os", "sys"]
            for module_name in modules_to_reload:
                try:
                    if module_name in sys.modules:
                        module = sys.modules[module_name]
                        importlib.reload(module)
                        reload_count += 1
                except Exception:
                    pass
            return reload_count
        result = benchmark(module_reload_test)
        assert result >= 1

    @pytest.mark.crust
    def test_app_module_discovery_performance(self, benchmark):
        """Benchmark discovering modules in app directories."""
        from pathlib import Path

        def discover_app_modules():
            discovered_modules = []
            apps_dir = Path("/c/git/hive/apps")
            if apps_dir.exists():
                for app_dir in apps_dir.iterdir():
                    if app_dir.is_dir() and (not app_dir.name.startswith(".")):
                        src_dir = app_dir / "src"
                        if src_dir.exists():
                            for py_file in src_dir.rglob("*.py"):
                                if py_file.name != "__init__.py":
                                    discovered_modules.append(str(py_file))
            return len(discovered_modules)
        result = benchmark(discover_app_modules)
        assert result >= 0

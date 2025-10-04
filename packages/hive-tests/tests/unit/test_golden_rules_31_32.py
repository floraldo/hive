"""Unit tests for Golden Rules 31-32: Config Validators

Tests the registry-based validators for:
- Rule 31: Ruff Config Consistency
- Rule 32: Python Version Specification
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import toml

from hive_tests.architectural_validators import validate_python_version_in_pyproject, validate_ruff_config_in_pyproject


@pytest.fixture
def temp_project():
    """Create a temporary project structure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create packages and apps directories
        (project_root / "packages").mkdir()
        (project_root / "apps").mkdir()

        yield project_root


@pytest.mark.core
class TestRule31RuffConfigConsistency:
    """Tests for Rule 31: Ruff Config Consistency"""

    def test_passes_with_ruff_config(self, temp_project):
        """Rule 31 should pass when [tool.ruff] exists"""
        # Create package with ruff config
        package_dir = temp_project / "packages" / "test-package"
        package_dir.mkdir()

        pyproject_file = package_dir / "pyproject.toml"
        config = {
            "tool": {
                "ruff": {
                    "line-length": 120,
                    "select": ["E", "F", "I"],
                },
            },
        }
        pyproject_file.write_text(toml.dumps(config))

        passed, violations = validate_ruff_config_in_pyproject(temp_project)
        assert passed
        assert len(violations) == 0

    def test_fails_without_ruff_config(self, temp_project):
        """Rule 31 should fail when [tool.ruff] is missing"""
        # Create package without ruff config
        package_dir = temp_project / "packages" / "test-package"
        package_dir.mkdir()

        pyproject_file = package_dir / "pyproject.toml"
        config = {
            "tool": {
                "poetry": {
                    "name": "test-package",
                    "version": "0.1.0",
                },
            },
        }
        pyproject_file.write_text(toml.dumps(config))

        passed, violations = validate_ruff_config_in_pyproject(temp_project)
        assert not passed
        assert len(violations) == 1
        assert "Missing [tool.ruff]" in violations[0]
        assert "test-package" in violations[0]

    def test_checks_multiple_packages(self, temp_project):
        """Rule 31 should check all packages and apps"""
        # Create multiple components
        for base_dir in ["packages", "apps"]:
            for component in ["component1", "component2"]:
                comp_dir = temp_project / base_dir / component
                comp_dir.mkdir()

                pyproject_file = comp_dir / "pyproject.toml"

                # component1 has ruff, component2 doesn't
                if component == "component1":
                    config = {"tool": {"ruff": {"line-length": 120}}}
                else:
                    config = {"tool": {"poetry": {"name": component}}}

                pyproject_file.write_text(toml.dumps(config))

        passed, violations = validate_ruff_config_in_pyproject(temp_project)
        assert not passed
        # Should have 2 violations (component2 in packages and apps)
        assert len(violations) == 2

    def test_ignores_non_python_dirs(self, temp_project):
        """Rule 31 should only check Python components"""
        # Create directory without pyproject.toml
        misc_dir = temp_project / "packages" / "docs"
        misc_dir.mkdir()
        (misc_dir / "README.md").write_text("# Documentation")

        passed, violations = validate_ruff_config_in_pyproject(temp_project)
        assert passed  # No pyproject.toml files, so no violations


@pytest.mark.core
class TestRule32PythonVersionSpecification:
    """Tests for Rule 32: Python Version Specification"""

    def test_passes_with_poetry_python_version(self, temp_project):
        """Rule 32 should pass with python = '^3.11'"""
        package_dir = temp_project / "packages" / "test-package"
        package_dir.mkdir()

        pyproject_file = package_dir / "pyproject.toml"
        config = {
            "tool": {
                "poetry": {
                    "name": "test-package",
                    "dependencies": {
                        "python": "^3.11",
                    },
                },
            },
        }
        pyproject_file.write_text(toml.dumps(config))

        passed, violations = validate_python_version_in_pyproject(temp_project)
        assert passed
        assert len(violations) == 0

    def test_passes_with_pep621_python_version(self, temp_project):
        """Rule 32 should pass with requires-python = '>=3.11'"""
        package_dir = temp_project / "packages" / "test-package"
        package_dir.mkdir()

        pyproject_file = package_dir / "pyproject.toml"
        config = {
            "project": {
                "name": "test-package",
                "requires-python": ">=3.11",
            },
        }
        pyproject_file.write_text(toml.dumps(config))

        passed, violations = validate_python_version_in_pyproject(temp_project)
        assert passed
        assert len(violations) == 0

    def test_fails_without_python_version(self, temp_project):
        """Rule 32 should fail when Python version is missing"""
        package_dir = temp_project / "packages" / "test-package"
        package_dir.mkdir()

        pyproject_file = package_dir / "pyproject.toml"
        config = {
            "tool": {
                "poetry": {
                    "name": "test-package",
                    "dependencies": {
                        "requests": "^2.28.0",
                    },
                },
            },
        }
        pyproject_file.write_text(toml.dumps(config))

        passed, violations = validate_python_version_in_pyproject(temp_project)
        assert not passed
        assert len(violations) == 1
        assert "Missing Python version" in violations[0]

    def test_fails_with_wrong_python_version(self, temp_project):
        """Rule 32 should fail when Python version is not 3.11+"""
        package_dir = temp_project / "packages" / "test-package"
        package_dir.mkdir()

        pyproject_file = package_dir / "pyproject.toml"
        config = {
            "tool": {
                "poetry": {
                    "name": "test-package",
                    "dependencies": {
                        "python": "^3.9",  # Wrong version
                    },
                },
            },
        }
        pyproject_file.write_text(toml.dumps(config))

        passed, violations = validate_python_version_in_pyproject(temp_project)
        assert not passed
        assert len(violations) == 1
        assert "3.11" in violations[0]

    def test_fails_with_complex_version_specs(self, temp_project):
        """Rule 32 requires exact format, fails on non-standard specs"""
        package_dir = temp_project / "packages" / "test-package"
        package_dir.mkdir()

        pyproject_file = package_dir / "pyproject.toml"
        config = {
            "tool": {
                "poetry": {
                    "name": "test-package",
                    "dependencies": {
                        "python": ">=3.11,<3.13",  # Valid but non-standard format
                    },
                },
            },
        }
        pyproject_file.write_text(toml.dumps(config))

        passed, violations = validate_python_version_in_pyproject(temp_project)
        # The validator requires exact format: python = "^3.11"
        # Complex specs like ">=3.11,<3.13" don't match the pattern
        assert not passed
        assert len(violations) == 1
        assert 'python = "^3.11"' in violations[0]

    def test_checks_both_packages_and_apps(self, temp_project):
        """Rule 32 should check both packages/ and apps/ directories"""
        # Create package with correct version
        pkg_dir = temp_project / "packages" / "good-package"
        pkg_dir.mkdir()
        (pkg_dir / "pyproject.toml").write_text(
            toml.dumps({"tool": {"poetry": {"dependencies": {"python": "^3.11"}}}}),
        )

        # Create app without version
        app_dir = temp_project / "apps" / "bad-app"
        app_dir.mkdir()
        (app_dir / "pyproject.toml").write_text(
            toml.dumps({"tool": {"poetry": {"name": "bad-app"}}}),
        )

        passed, violations = validate_python_version_in_pyproject(temp_project)
        assert not passed
        assert len(violations) == 1
        assert "bad-app" in violations[0]


@pytest.mark.core
class TestIntegration:
    """Integration tests for Rules 31-32 together"""

    def test_both_rules_pass_on_compliant_project(self, temp_project):
        """Both rules should pass on a fully compliant project"""
        package_dir = temp_project / "packages" / "compliant-package"
        package_dir.mkdir()

        pyproject_file = package_dir / "pyproject.toml"
        config = {
            "tool": {
                "poetry": {
                    "name": "compliant-package",
                    "dependencies": {
                        "python": "^3.11",
                    },
                },
                "ruff": {
                    "line-length": 120,
                },
            },
        }
        pyproject_file.write_text(toml.dumps(config))

        # Test Rule 31
        passed_31, violations_31 = validate_ruff_config_in_pyproject(temp_project)
        assert passed_31
        assert len(violations_31) == 0

        # Test Rule 32
        passed_32, violations_32 = validate_python_version_in_pyproject(temp_project)
        assert passed_32
        assert len(violations_32) == 0

    def test_both_rules_fail_on_non_compliant_project(self, temp_project):
        """Both rules should fail on a non-compliant project"""
        package_dir = temp_project / "packages" / "bad-package"
        package_dir.mkdir()

        pyproject_file = package_dir / "pyproject.toml"
        config = {
            "tool": {
                "poetry": {
                    "name": "bad-package",
                    # Missing both python version and ruff config
                },
            },
        }
        pyproject_file.write_text(toml.dumps(config))

        # Test Rule 31
        passed_31, violations_31 = validate_ruff_config_in_pyproject(temp_project)
        assert not passed_31
        assert len(violations_31) == 1

        # Test Rule 32
        passed_32, violations_32 = validate_python_version_in_pyproject(temp_project)
        assert not passed_32
        assert len(violations_32) == 1

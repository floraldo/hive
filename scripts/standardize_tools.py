#!/usr/bin/env python3
"""
Standardize tool versions across all Hive packages and apps.
"""

import toml
from pathlib import Path
from hive_logging import get_logger

logger = get_logger(__name__)


def load_standard_versions():
    """Load standard tool versions from tool-versions.toml"""
    versions_file = Path(__file__).parent.parent / "tool-versions.toml"
    with open(versions_file, "r") as f:
        return toml.load(f)


def update_pyproject_tools(pyproject_path: Path, standard_versions: dict):
    """Update tool versions in a pyproject.toml file"""
    try:
        with open(pyproject_path, "r") as f:
            data = toml.load(f)

        updated = False

        # Update dev dependencies
        if "tool" in data and "poetry" in data["tool"]:
            poetry = data["tool"]["poetry"]

            # Update main dependencies if they include dev tools
            if "dependencies" in poetry:
                deps = poetry["dependencies"]
                for tool, version in standard_versions["tools"].items():
                    if tool in deps:
                        if deps[tool] != version:
                            logger.info(f"  Updating {tool}: {deps[tool]} -> {version}")
                            deps[tool] = version
                            updated = True

            # Update dev dependencies
            if "group" in poetry and "dev" in poetry["group"] and "dependencies" in poetry["group"]["dev"]:
                dev_deps = poetry["group"]["dev"]["dependencies"]
                for tool, version in standard_versions["tools"].items():
                    if tool in dev_deps:
                        if dev_deps[tool] != version:
                            logger.info(f"  Updating {tool}: {dev_deps[tool]} -> {version}")
                            dev_deps[tool] = version
                            updated = True

            # Legacy format (dev-dependencies)
            if "dev-dependencies" in poetry:
                dev_deps = poetry["dev-dependencies"]
                for tool, version in standard_versions["tools"].items():
                    if tool in dev_deps:
                        if dev_deps[tool] != version:
                            logger.info(f"  Updating {tool}: {dev_deps[tool]} -> {version}")
                            dev_deps[tool] = version
                            updated = True

        # Update tool configurations
        if "tool" in data:
            # Update black config
            if "black" in standard_versions["tool"]:
                if "black" not in data["tool"]:
                    data["tool"]["black"] = {}
                data["tool"]["black"].update(standard_versions["tool"]["black"])
                updated = True

            # Update ruff config
            if "ruff" in standard_versions["tool"]:
                if "ruff" not in data["tool"]:
                    data["tool"]["ruff"] = {}
                data["tool"]["ruff"].update(standard_versions["tool"]["ruff"])
                updated = True

            # Update pytest config
            if "pytest.ini_options" in standard_versions["tool"]:
                if "pytest" not in data["tool"]:
                    data["tool"]["pytest"] = {}
                if "ini_options" not in data["tool"]["pytest"]:
                    data["tool"]["pytest"]["ini_options"] = {}
                data["tool"]["pytest"]["ini_options"].update(standard_versions["tool"]["pytest.ini_options"])
                updated = True

            # Update mypy config
            if "mypy" in standard_versions["tool"]:
                if "mypy" not in data["tool"]:
                    data["tool"]["mypy"] = {}
                data["tool"]["mypy"].update(standard_versions["tool"]["mypy"])
                updated = True

        if updated:
            with open(pyproject_path, "w") as f:
                toml.dump(data, f)
            return True
        return False

    except Exception as e:
        logger.error(f"  Error updating {pyproject_path}: {e}")
        return False


def main():
    """Main execution"""
    logger.info("Standardizing tool versions across Hive platform")

    # Load standard versions
    standard_versions = load_standard_versions()
    logger.info(f"Loaded standard versions: {list(standard_versions['tools'].keys())}")

    # Find all pyproject.toml files
    root = Path(__file__).parent.parent
    pyproject_files = []

    # Add root pyproject.toml
    if (root / "pyproject.toml").exists():
        pyproject_files.append(root / "pyproject.toml")

    # Add package pyproject.toml files
    for package_dir in (root / "packages").glob("*/pyproject.toml"):
        pyproject_files.append(package_dir)

    # Add app pyproject.toml files
    for app_dir in (root / "apps").glob("*/pyproject.toml"):
        pyproject_files.append(app_dir)

    logger.info(f"Found {len(pyproject_files)} pyproject.toml files")

    # Update each file
    updated_count = 0
    for pyproject_path in pyproject_files:
        rel_path = pyproject_path.relative_to(root)
        logger.info(f"Checking {rel_path}")
        if update_pyproject_tools(pyproject_path, standard_versions):
            updated_count += 1
            logger.info(f"  ✓ Updated")
        else:
            logger.info(f"  - No changes needed")

    logger.info(f"\nSummary: Updated {updated_count}/{len(pyproject_files)} files")

    if updated_count > 0:
        logger.info("\nNext steps:")
        logger.info("1. Run 'poetry lock' in each updated directory")
        logger.info("2. Run 'poetry install' to apply changes")
        logger.info("3. Commit the standardized configurations")


if __name__ == "__main__":
    main()

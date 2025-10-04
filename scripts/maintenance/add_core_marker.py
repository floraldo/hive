"""Add 'core' marker to package pyproject.toml files.

This ensures packages work with root pytest.ini strict-markers setting.
"""
from pathlib import Path

import tomli
import tomli_w


def add_core_marker_to_pyproject(pyproject_path: Path) -> bool:
    """Add core marker to pytest.ini_options if not present."""
    try:
        with open(pyproject_path, "rb") as f:
            data = tomli.load(f)

        # Check if pytest config exists
        if "tool" not in data or "pytest" not in data["tool"]:
            return False

        if "ini_options" not in data["tool"]["pytest"]:
            data["tool"]["pytest"]["ini_options"] = {}

        # Get or create markers list
        markers = data["tool"]["pytest"]["ini_options"].get("markers", [])

        # Check if core marker already exists
        has_core = any("core:" in str(m) for m in markers)

        if not has_core:
            markers.append("core: Core infrastructure tests (packages/) - strict quality standards")
            data["tool"]["pytest"]["ini_options"]["markers"] = markers

            # Write back
            with open(pyproject_path, "wb") as f:
                tomli_w.dump(data, f)

            print(f"[OK] Added core marker to {pyproject_path.parent.name}")
            return True
        print(f"[SKIP] {pyproject_path.parent.name} already has core marker")
        return False

    except Exception as e:
        print(f"[ERROR] Error processing {pyproject_path}: {e}")
        return False

def main():
    """Add core marker to all package pyproject.toml files."""
    packages_dir = Path(__file__).parent.parent.parent / "packages"

    updated = 0
    for pyproject in packages_dir.rglob("pyproject.toml"):
        if add_core_marker_to_pyproject(pyproject):
            updated += 1

    print(f"\n[DONE] Updated {updated} package configs")

if __name__ == "__main__":
    main()

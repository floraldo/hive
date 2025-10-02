#!/usr/bin/env python3
"""
Script to replace sys.path.insert() patterns with centralized path management.

This script systematically updates all files in the Hive workspace to use
the new centralized path management system from hive-config.
"""

import sys
from pathlib import Path

# Add hive-config to path for this script
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages" / "hive-config" / "src"))

from hive_config import setup_hive_paths

setup_hive_paths()


def find_files_with_syspath_inserts() -> list[Path]:
    """Find all files containing sys.path.insert patterns."""
    files = []

    # Search in key directories
    search_dirs = [
        project_root / "apps",
        project_root / "scripts",
        project_root / "tests",
        project_root,  # Root level files
    ]

    for search_dir in search_dirs:
        if search_dir.exists():
            for py_file in search_dir.rglob("*.py"):
                try:
                    content = py_file.read_text(encoding="utf-8")
                    if "sys.path.insert" in content:
                        files.append(py_file)
                except (UnicodeDecodeError, PermissionError):
                    continue

    return files


def analyze_file_imports(file_path: Path) -> dict:
    """Analyze a file's import patterns to understand its structure."""
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        analysis = {
            "has_syspath_inserts": False,
            "syspath_lines": [],
            "imports_hive_packages": False,
            "relative_to_root": str(file_path.relative_to(project_root)),
            "needs_hive_config": False,
        }

        for i, line in enumerate(lines, 1):
            if "sys.path.insert" in line:
                analysis["has_syspath_inserts"] = True
                analysis["syspath_lines"].append((i, line.strip()))

                # Check if it's inserting Hive paths
                if any(hive_path in line for hive_path in ["packages", "apps", "hive-"]):
                    analysis["needs_hive_config"] = True

            if any(
                pkg in line
                for pkg in ["hive_core_db", "hive_utils", "hive_logging", "hive_orchestrator", "ai_reviewer"]
            ):
                analysis["imports_hive_packages"] = True

        return analysis

    except Exception as e:
        return {"error": str(e)}


def generate_replacement_pattern(file_path: Path, analysis: dict) -> tuple[str, str]:
    """Generate old and new content patterns for a file."""
    if not analysis.get("needs_hive_config", False):
        return None, None

    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Find the block of sys.path.insert lines
        syspath_start = None
        syspath_end = None

        for i, line in enumerate(lines):
            if "sys.path.insert" in line and any(hive_path in line for hive_path in ["packages", "apps", "hive-"]):
                if syspath_start is None:
                    syspath_start = i
                syspath_end = i

        if syspath_start is None:
            return None, None

        # Look for import section start
        import_start = syspath_start
        while import_start > 0 and not lines[import_start - 1].strip().startswith("# Add"):
            import_start -= 1
            if "import sys" in lines[import_start] or "from pathlib import Path" in lines[import_start]:
                break

        # Extract the old pattern
        old_block = lines[import_start : syspath_end + 1]

        # Create new pattern
        new_lines = []

        # Keep necessary imports
        has_sys_import = any("import sys" in line for line in old_block)
        has_path_import = any("from pathlib import Path" in line for line in old_block)

        if has_sys_import:
            new_lines.append("import sys")
        if has_path_import:
            new_lines.append("from pathlib import Path")

        if new_lines:
            new_lines.append("")

        # Add the centralized path setup
        new_lines.extend(
            [
                "# Add packages path first for hive-config",
                "project_root = Path(__file__).parent.parent.parent",
                'sys.path.insert(0, str(project_root / "packages" / "hive-config" / "src"))',
                "",
                "# Configure all Hive paths centrally",
                "from hive_config import setup_hive_paths",
                "setup_hive_paths()",
            ],
        )

        old_text = "\n".join(old_block)
        new_text = "\n".join(new_lines)

        return old_text, new_text

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None, None


def main():
    """Main execution function."""
    print("Import Path Centralization Tool")
    print("=" * 50)

    # Find all relevant files
    files = find_files_with_syspath_inserts()
    print(f"Found {len(files)} files with sys.path.insert patterns")

    # Analyze each file
    updates_needed = []
    for file_path in files:
        analysis = analyze_file_imports(file_path)
        if analysis.get("needs_hive_config", False):
            updates_needed.append((file_path, analysis))

    print(f"\nFiles needing updates: {len(updates_needed)}")

    # Show what would be updated
    for file_path, analysis in updates_needed[:10]:  # Show first 10
        rel_path = analysis["relative_to_root"]
        syspath_count = len(analysis["syspath_lines"])
        print(f"  {rel_path} ({syspath_count} sys.path lines)")

    if len(updates_needed) > 10:
        print(f"  ... and {len(updates_needed) - 10} more")

    print(
        f"\nThis would eliminate approximately {sum(len(a['syspath_lines']) for _, a in updates_needed)} lines of duplicated path setup code.",
    )

    return len(updates_needed)


if __name__ == "__main__":
    count = main()
    print(f"\nAnalysis complete. {count} files would be updated.")

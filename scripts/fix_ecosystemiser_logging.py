#!/usr/bin/env python3
"""Fix logging imports in EcoSystemiser app."""

import re
from pathlib import Path

def fix_logging_in_file(file_path: Path) -> bool:
    """Fix logging imports in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Check if file uses logging
        if ("logger" in content.lower() or "logging" in content.lower()):
            # Check if it already imports hive_logging adapter
            if ("from EcoSystemiser.hive_logging_adapter import" not in content and
                "from hive_logging import" not in content and
                "import hive_logging" not in content):

                # Add the import after the docstring
                if content.startswith('"""'):
                    # Find end of docstring
                    end_docstring = content.find('"""', 3)
                    if end_docstring != -1:
                        # Insert the import after the docstring
                        import_line = "\n\nfrom EcoSystemiser.hive_logging_adapter import get_logger"

                        # Check if logger is already defined
                        if "logger = " not in content:
                            import_line += "\n\nlogger = get_logger(__name__)"

                        content = content[:end_docstring + 3] + import_line + content[end_docstring + 3:]
                else:
                    # No docstring, add at the beginning
                    import_line = "from EcoSystemiser.hive_logging_adapter import get_logger\n\nlogger = get_logger(__name__)\n\n"
                    content = import_line + content

                # Replace logging imports with hive_logging
                content = re.sub(r'import logging\b', 'from EcoSystemiser.hive_logging_adapter import get_logger', content)
                content = re.sub(r'from logging import .*', 'from EcoSystemiser.hive_logging_adapter import get_logger', content)
                content = re.sub(r'logging\.getLogger\((.*?)\)', r'get_logger(\1)', content)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Fix logging in EcoSystemiser files."""
    project_root = Path(__file__).parent.parent
    ecosystemiser_dir = project_root / "apps" / "ecosystemiser" / "src" / "EcoSystemiser"

    files_to_fix = [
        "cli.py",
        "errors.py",
        "event_bus.py",
        "hive_env.py",
        "main.py",
        "observability.py",
        "settings.py",
        "worker.py",
        "analyser/factory.py",
        "analyser/kpi_calculator.py",
        "analyser/service.py",
        "analyser/worker.py",
        "analyser/strategies/economic.py",
        "analyser/strategies/sensitivity.py",
        "analyser/strategies/technical_kpi.py"
    ]

    fixed_count = 0
    for file_name in files_to_fix:
        file_path = ecosystemiser_dir / file_name
        if file_path.exists():
            if fix_logging_in_file(file_path):
                print(f"Fixed: {file_path.relative_to(project_root)}")
                fixed_count += 1

    # Also fix all other .py files in the directory recursively
    for py_file in ecosystemiser_dir.rglob("*.py"):
        if "test" not in str(py_file).lower() and "__pycache__" not in str(py_file):
            if fix_logging_in_file(py_file):
                print(f"Fixed: {py_file.relative_to(project_root)}")
                fixed_count += 1

    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()
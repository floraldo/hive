#!/usr/bin/env python3
"""Fix print statements in packages directory - Golden Rule 9."""

import re
from pathlib import Path
from typing import Tuple


def fix_print_to_logging(content: str) -> Tuple[str, int]:
    """Replace print statements with proper logging."""
    lines = content.split('\n')
    fixed_lines = []
    changes = 0
    has_logger = False
    has_imports = False
    last_import_idx = -1

    # Check if logger is already imported
    for idx, line in enumerate(lines):
        if 'import' in line or 'from' in line:
            has_imports = True
            last_import_idx = idx
        if 'from hive_logging import get_logger' in line:
            has_logger = True
        if 'logger = get_logger' in line:
            has_logger = True

    # Process lines and fix print statements
    for i, line in enumerate(lines):
        # Skip if it's a comment
        if line.strip().startswith('#'):
            fixed_lines.append(line)
            continue

        # Fix print statements
        if 'print(' in line:
            # Various print patterns to replace
            replacements = [
                (r'\s*print\(f"([^"]+)"\)', r'    logger.info("\1")'),
                (r'\s*print\(f\'([^\']+)\'\)', r'    logger.info("\1")'),
                (r'\s*print\("([^"]+)"\)', r'    logger.info("\1")'),
                (r'\s*print\(\'([^\']+)\'\)', r'    logger.info("\1")'),
                (r'\s*print\((.+)\)', r'    logger.info(\1)'),
            ]

            line_replaced = False
            for pattern, replacement in replacements:
                if re.match(pattern, line):
                    line = re.sub(pattern, replacement, line)
                    changes += 1
                    line_replaced = True
                    break

            if not line_replaced and 'print(' in line:
                # Fallback: simple replacement
                line = line.replace('print(', 'logger.info(')
                changes += 1

        fixed_lines.append(line)

    # Add logger import if needed and we made changes
    if changes > 0 and not has_logger:
        if has_imports and last_import_idx >= 0:
            # Add after last import
            fixed_lines.insert(last_import_idx + 1, '')
            fixed_lines.insert(last_import_idx + 2, 'from hive_logging import get_logger')
            fixed_lines.insert(last_import_idx + 3, '')
            fixed_lines.insert(last_import_idx + 4, 'logger = get_logger(__name__)')
        else:
            # Add at the beginning after docstring
            insert_idx = 0
            for idx, line in enumerate(fixed_lines):
                if line.strip() and not line.startswith('"""') and not line.startswith('#'):
                    insert_idx = idx
                    break

            fixed_lines.insert(insert_idx, '')
            fixed_lines.insert(insert_idx + 1, 'from hive_logging import get_logger')
            fixed_lines.insert(insert_idx + 2, '')
            fixed_lines.insert(insert_idx + 3, 'logger = get_logger(__name__)')

    return '\n'.join(fixed_lines), changes


def main():
    """Fix print statements in packages directory."""
    # Specific package files with print statements from the report
    files_to_fix = [
        'packages/hive-cache/src/hive_cache/performance_cache.py',
        'packages/hive-performance/src/hive_performance/monitor.py',
        'packages/hive-performance/src/hive_performance/profiling.py',
        'packages/hive-performance/src/hive_performance/system_monitor.py',
        'packages/hive-service-discovery/src/hive_service_discovery/discovery_client.py',
        'packages/hive-service-discovery/src/hive_service_discovery/load_balancer.py',
        'packages/hive-service-discovery/src/hive_service_discovery/service_registry.py',
    ]

    total_changes = 0
    files_fixed = 0

    for file_path in files_to_fix:
        path = Path(file_path)
        if path.exists():
            try:
                content = path.read_text()
                fixed_content, changes = fix_print_to_logging(content)

                if changes > 0:
                    path.write_text(fixed_content)
                    print(f"Fixed {changes} print statements in {file_path}")
                    total_changes += changes
                    files_fixed += 1
            except Exception as e:
                print(f"Error fixing {file_path}: {e}")
        else:
            print(f"File not found: {file_path}")

    print(f"\nTotal: Fixed {total_changes} print statements in {files_fixed} files")


if __name__ == "__main__":
    main()
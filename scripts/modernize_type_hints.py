#!/usr/bin/env python3
"""
Modernize Type Hints for Hive Platform V4.4

Converts old-style type hints using Union and Optional to modern Python 3.10+ syntax using |
"""

import os
import re
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

from hive_logging import get_logger

logger = get_logger(__name__)


class TypeHintModernizer:
    """Modernizes Python type hints to use | syntax instead of Union/Optional"""

    def __init__(self, hive_root: Path = None):
        self.hive_root = hive_root or Path.cwd()
        self.files_updated = 0
        self.total_changes = 0

    def find_python_files(self) -> List[Path]:
        """Find all Python files in packages and apps"""
        python_files = []

        for pattern in ["packages/**/*.py", "apps/**/*.py"]:
            python_files.extend(self.hive_root.glob(pattern))

        # Exclude test files and legacy/archive directories
        filtered_files = []
        for file_path in python_files:
            path_str = str(file_path).lower()
            if not any(exclude in path_str for exclude in ["test_", "/tests/", "archive", "legacy", "__pycache__"]):
                filtered_files.append(file_path)

        return filtered_files

    def modernize_file(self, file_path: Path) -> int:
        """Modernize type hints in a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content
            changes = 0

            # Track if we need to add from __future__ import annotations
            needs_future_import = False
            has_future_import = "from __future__ import annotations" in content

            # Pattern replacements
            replacements = [
                # Optional[X] -> X | None
                (r'Optional\[([^\[\]]+)\]', r'\1 | None'),
                # Union[X, Y] -> X | Y
                (r'Union\[([^\[\]]+),\s*([^\[\]]+)\]', r'\1 | \2'),
                # Union[X, Y, Z] -> X | Y | Z (handles 3 items)
                (r'Union\[([^\[\]]+),\s*([^\[\]]+),\s*([^\[\]]+)\]', r'\1 | \2 | \3'),
                # Handle nested Optional[Union[X, Y]] -> X | Y | None
                (r'Optional\[Union\[([^\[\]]+),\s*([^\[\]]+)\]\]', r'\1 | \2 | None'),
                # Handle Union[X, None] -> X | None
                (r'Union\[([^\[\]]+),\s*None\]', r'\1 | None'),
                (r'Union\[None,\s*([^\[\]]+)\]', r'\1 | None'),
            ]

            for pattern, replacement in replacements:
                new_content, count = re.subn(pattern, replacement, content)
                if count > 0:
                    content = new_content
                    changes += count
                    needs_future_import = True

            # Clean up imports if we made changes
            if changes > 0:
                # Remove Optional and Union from imports
                import_patterns = [
                    (r'from typing import ([^;\n]*?)(?:,\s*)?Optional(?:,\s*)?([^;\n]*)', r'from typing import \1\2'),
                    (r'from typing import ([^;\n]*?)(?:,\s*)?Union(?:,\s*)?([^;\n]*)', r'from typing import \1\2'),
                    # Clean up double commas and trailing commas
                    (r'from typing import\s*,', r'from typing import'),
                    (r',\s*,', r','),
                    (r',\s*\n', r'\n'),
                    (r'from typing import\s*\n', ''),  # Remove empty import
                ]

                for pattern, replacement in import_patterns:
                    content = re.sub(pattern, replacement, content)

                # Add from __future__ import annotations if needed and not present
                if needs_future_import and not has_future_import:
                    # Add after the module docstring and before other imports
                    lines = content.split('\n')
                    insert_index = 0

                    # Skip shebang
                    if lines[0].startswith('#!'):
                        insert_index = 1

                    # Skip module docstring
                    in_docstring = False
                    for i in range(insert_index, len(lines)):
                        line = lines[i].strip()
                        if line.startswith('"""') or line.startswith("'''"):
                            if in_docstring:
                                insert_index = i + 1
                                break
                            else:
                                in_docstring = True
                        elif not in_docstring and line and not line.startswith('#'):
                            insert_index = i
                            break

                    lines.insert(insert_index, 'from __future__ import annotations')
                    lines.insert(insert_index + 1, '')
                    content = '\n'.join(lines)

            # Only write if there were changes
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"Updated {file_path}: {changes} type hints modernized")
                return changes

            return 0

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return 0

    def modernize_all(self, dry_run: bool = False) -> Tuple[int, int]:
        """Modernize type hints in all Python files"""
        python_files = self.find_python_files()
        logger.info(f"Found {len(python_files)} Python files to check")

        files_updated = 0
        total_changes = 0

        for file_path in python_files:
            if dry_run:
                # Just check if file needs updates
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if 'Optional[' in content or 'Union[' in content:
                        logger.info(f"Would update: {file_path}")
                        files_updated += 1
                except Exception as e:
                    logger.error(f"Error reading {file_path}: {e}")
            else:
                changes = self.modernize_file(file_path)
                if changes > 0:
                    files_updated += 1
                    total_changes += changes

        return files_updated, total_changes

    def generate_report(self) -> str:
        """Generate a report of type hints that need modernization"""
        python_files = self.find_python_files()

        files_needing_update = []
        optional_usage = 0
        union_usage = 0

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                optional_count = content.count('Optional[')
                union_count = content.count('Union[')

                if optional_count > 0 or union_count > 0:
                    files_needing_update.append({
                        'path': file_path,
                        'optional': optional_count,
                        'union': union_count
                    })
                    optional_usage += optional_count
                    union_usage += union_count

            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

        report = f"""
# Type Hint Modernization Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Files scanned: {len(python_files)}
- Files needing update: {len(files_needing_update)}
- Total Optional[] usage: {optional_usage}
- Total Union[] usage: {union_usage}

## Files Requiring Updates
"""

        for file_info in sorted(files_needing_update, key=lambda x: x['optional'] + x['union'], reverse=True)[:20]:
            report += f"- {file_info['path'].relative_to(self.hive_root)}: Optional={file_info['optional']}, Union={file_info['union']}\n"

        if len(files_needing_update) > 20:
            report += f"\n... and {len(files_needing_update) - 20} more files\n"

        return report


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Modernize Python type hints")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    parser.add_argument("--report", action="store_true", help="Generate a report of type hints needing modernization")
    parser.add_argument("--path", type=Path, help="Specific path to modernize")

    args = parser.parse_args()

    modernizer = TypeHintModernizer()

    if args.report:
        print(modernizer.generate_report())
    elif args.path:
        changes = modernizer.modernize_file(args.path)
        print(f"Updated {args.path}: {changes} changes made")
    else:
        files_updated, total_changes = modernizer.modernize_all(dry_run=args.dry_run)
        if args.dry_run:
            print(f"Would update {files_updated} files")
        else:
            print(f"Updated {files_updated} files with {total_changes} total changes")


if __name__ == "__main__":
    main()
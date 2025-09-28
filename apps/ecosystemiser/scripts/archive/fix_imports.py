from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Fix import issues and remove sys.path hacks in EcoSystemiser.

This script removes all sys.path manipulations and ensures the application
works properly with Hive's editable install mechanism.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple, Set

def remove_sys_path_hacks(file_path: Path) -> bool:
    """Remove sys.path hacks from a Python file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    lines = content.split('\n')

    # Find lines to remove
    lines_to_remove: Set[int] = set()

    for i, line in enumerate(lines):
        # Check for sys.path manipulation
        if re.search(r'sys\.path\.(insert|append)', line):
            lines_to_remove.add(i)

            # Also remove related comments before the sys.path line
            if i > 0:
                prev_line = lines[i-1].strip()
                if prev_line.startswith('#') and any(word in prev_line.lower() for word in ['add', 'path', 'src', 'temporary']):
                    lines_to_remove.add(i-1)

            # Remove empty line after if present
            if i < len(lines) - 1 and lines[i+1].strip() == '':
                lines_to_remove.add(i+1)

    # Also check for unnecessary Path imports (only used for sys.path)
    for i, line in enumerate(lines):
        if 'from pathlib import Path' in line:
            # Check if Path is used for anything other than sys.path
            path_used_elsewhere = False
            for j, other_line in enumerate(lines):
                if j != i and j not in lines_to_remove:
                    # Check if Path is used in non-sys.path context
                    if 'Path(' in other_line and not re.search(r'sys\.path', other_line):
                        path_used_elsewhere = True
                        break

            if not path_used_elsewhere:
                lines_to_remove.add(i)

    # Remove marked lines
    if lines_to_remove:
        new_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
        new_content = '\n'.join(new_lines)

        # Clean up multiple blank lines
        while '\n\n\n' in new_content:
            new_content = new_content.replace('\n\n\n', '\n\n')

        # Save the fixed file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True

    return False

def scan_and_fix_directory(directory: Path) -> Tuple[List[Path], int]:
    """Scan directory for Python files with sys.path hacks and fix them."""
    fixed_files = []
    total_scanned = 0

    for py_file in directory.rglob('*.py'):
        total_scanned += 1
        if remove_sys_path_hacks(py_file):
            fixed_files.append(py_file)

    return fixed_files, total_scanned

def main():
    """Main execution to fix all import issues."""
    ecosystemiser_dir = Path(__file__).parent.parent

    logger.info("EcoSystemiser Hive Integration - Import Fix")
    logger.info("=" * 60)
    logger.info(f"Working directory: {ecosystemiser_dir}")
    logger.info()

    # Process all Python files
    logger.info("Scanning for sys.path hacks...")
    fixed_files, total_scanned = scan_and_fix_directory(ecosystemiser_dir)

    logger.info(f"\nScanned {total_scanned} Python files")
    logger.info(f"Fixed {len(fixed_files)} files with sys.path hacks")

    if fixed_files:
        logger.info("\nFiles fixed:")
        for f in sorted(fixed_files):
            rel_path = f.relative_to(ecosystemiser_dir)
            logger.info(f"  - {rel_path}")

    logger.info("\nImport standardization complete!")
    logger.info("All files now use proper imports compatible with Hive's editable installs.")

    # Provide next steps
    logger.info("\nNext steps:")
    logger.info("1. Run tests to verify imports still work: python -m pytest")
    logger.info("2. Check that the application starts properly")
    logger.info("3. Continue with Phase 2: Logging consolidation")

if __name__ == "__main__":
    main()
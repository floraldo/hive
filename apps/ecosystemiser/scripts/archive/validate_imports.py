from hive_logging import get_logger

logger = get_logger(__name__)
#!/usr/bin/env python3
"""
Validate that imports follow the Golden Rules of Imports architecture.

Golden Rules:
1. Business logic files (.py files that are NOT __init__.py) should use ABSOLUTE imports
2. __init__.py files should use RELATIVE imports for their own subdirectories
3. No sys.path manipulation should exist in production code

Usage:
    python scripts/validate_imports.py [--fix]
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Tuple, Dict

# Color codes for output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def find_python_files(root_dir: Path) -> List[Path]:
    """Find all Python files in the project."""
    python_files = []
    src_dir = root_dir / "src" / "EcoSystemiser"

    if src_dir.exists():
        for file_path in src_dir.rglob("*.py"):
            # Skip __pycache__ and test files
            if "__pycache__" not in str(file_path) and "test_" not in file_path.name:
                python_files.append(file_path)

    return python_files


def check_relative_imports(file_path: Path) -> List[Tuple[int, str]]:
    """Check for relative imports in a file."""
    violations = []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines, 1):
        # Check for relative imports
        if re.match(r'^from \.\S+ import', line.strip()) or re.match(r'^from \. import', line.strip()):
            violations.append((line_num, line.strip()))

    return violations


def check_sys_path_hacks(file_path: Path) -> List[Tuple[int, str]]:
    """Check for sys.path manipulation."""
    violations = []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines, 1):
        if 'sys.path' in line and any(x in line for x in ['append', 'insert', 'extend']):
            violations.append((line_num, line.strip()))

    return violations


def validate_imports(root_dir: Path, fix: bool = False) -> Dict[str, List]:
    """Validate imports in all Python files."""
    results = {
        'relative_in_business': [],
        'sys_path_hacks': [],
        'passed': []
    }

    python_files = find_python_files(root_dir)

    for file_path in python_files:
        file_name = file_path.name
        relative_path = file_path.relative_to(root_dir)

        # Check for sys.path hacks (never allowed)
        sys_path_violations = check_sys_path_hacks(file_path)
        if sys_path_violations:
            results['sys_path_hacks'].append({
                'file': str(relative_path),
                'violations': sys_path_violations
            })

        # Check for relative imports in business logic files
        if file_name != '__init__.py':
            relative_violations = check_relative_imports(file_path)
            if relative_violations:
                results['relative_in_business'].append({
                    'file': str(relative_path),
                    'violations': relative_violations
                })

                if fix:
                    fix_relative_imports(file_path, relative_path)
            elif not sys_path_violations:
                results['passed'].append(str(relative_path))
        else:
            # __init__.py files are allowed to have relative imports
            if not sys_path_violations:
                results['passed'].append(str(relative_path))

    return results


def fix_relative_imports(file_path: Path, relative_path: Path) -> None:
    """Fix relative imports in a file by converting to absolute."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Get the module path from the file path
    module_parts = relative_path.parts[1:-1]  # Skip 'src' and filename
    if module_parts:
        current_module = '.'.join(module_parts)

        # Replace relative imports with absolute
        # Pattern: from .module import -> from current_package.module import
        content = re.sub(
            r'^from \.(\S+) import',
            f'from {current_module}.\\1 import',
            content,
            flags=re.MULTILINE
        )

        # Pattern: from . import -> from current_package import
        content = re.sub(
            r'^from \. import',
            f'from {current_module} import',
            content,
            flags=re.MULTILINE
        )

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"{GREEN}Fixed:{RESET} {relative_path}")


def print_results(results: Dict[str, List]) -> int:
    """Print validation results and return exit code."""
    logger.info("\n" + "="*60)
    logger.info("Golden Rules of Imports Validation Report")
    logger.info("="*60 + "\n")

    # Print violations
    total_violations = 0

    if results['sys_path_hacks']:
        logger.info(f"{RED}✗ sys.path Manipulation Found:{RESET}")
        for item in results['sys_path_hacks']:
            logger.info(f"  {item['file']}")
            for line_num, line in item['violations']:
                logger.info(f"    Line {line_num}: {line}")
        total_violations += len(results['sys_path_hacks'])
        logger.info()

    if results['relative_in_business']:
        logger.warning(f"{YELLOW}[WARNING] Relative Imports in Business Logic:{RESET}")
        for item in results['relative_in_business']:
            logger.info(f"  {item['file']}")
            for line_num, line in item['violations']:
                logger.info(f"    Line {line_num}: {line}")
        total_violations += len(results['relative_in_business'])
        logger.info()

    # Print summary
    logger.info("Summary:")
    logger.info(f"  {GREEN}[PASS] Files following rules:{RESET} {len(results['passed'])}")
    logger.warning(f"  {YELLOW}[WARN] Relative import violations:{RESET} {len(results['relative_in_business'])} files")
    logger.error(f"  {RED}[FAIL] sys.path violations:{RESET} {len(results['sys_path_hacks'])} files")
    logger.info()

    if total_violations == 0:
        logger.info(f"{GREEN}[OK] All files follow the Golden Rules of Imports!{RESET}")
        return 0
    else:
        logger.info(f"{YELLOW}Found {total_violations} violations.{RESET}")
        logger.info("Run with --fix flag to automatically fix relative import violations.")
        return 1


def main():
    """Main entry point."""
    fix_mode = '--fix' in sys.argv

    root_dir = get_project_root()
    logger.info(f"Validating imports in: {root_dir}")

    if fix_mode:
        logger.info(f"{YELLOW}Running in FIX mode - will convert relative imports to absolute{RESET}\n")

    results = validate_imports(root_dir, fix=fix_mode)

    exit_code = print_results(results)

    if fix_mode and results['relative_in_business']:
        logger.info(f"\n{GREEN}Fixed {len(results['relative_in_business'])} files.{RESET}")
        logger.info("Please run validation again to confirm all issues are resolved.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
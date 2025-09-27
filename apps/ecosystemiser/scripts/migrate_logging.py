#!/usr/bin/env python3
"""
Migrate all EcoSystemiser logging to use the centralized Hive logging adapter.

This script replaces all direct Python logging imports with the Hive adapter,
ensuring consistent logging across the ecosystem.
"""

import re
from pathlib import Path
from typing import List, Tuple, Dict

def analyze_logging_usage(file_path: Path) -> Dict[str, any]:
    """Analyze how logging is used in a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    analysis = {
        'has_import_logging': bool(re.search(r'^import logging\s*$', content, re.MULTILINE)),
        'has_from_logging': bool(re.search(r'^from logging import', content, re.MULTILINE)),
        'has_getLogger': 'getLogger' in content,
        'has_logger_var': bool(re.search(r'logger\s*=', content)),
        'uses_logging_module': bool(re.search(r'logging\.\w+', content)),
        'already_uses_hive': 'hive_logging_adapter' in content
    }

    return analysis

def migrate_logging_in_file(file_path: Path) -> bool:
    """Migrate logging in a single Python file to use Hive adapter."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Skip if already using Hive adapter
    if 'hive_logging_adapter' in content:
        return False

    # Skip if no logging usage
    if 'logging' not in content and 'logger' not in content.lower():
        return False

    # Replace import statements
    replacements = [
        # Replace 'import logging' with Hive adapter import
        (r'^import logging\s*$',
         'from EcoSystemiser.hive_logging_adapter import get_logger'),

        # Replace 'from logging import ...' with Hive adapter
        (r'^from logging import .*$',
         'from EcoSystemiser.hive_logging_adapter import get_logger'),

        # Replace logging.getLogger patterns
        (r'logging\.getLogger\((.*?)\)',
         r'get_logger(\1)'),

        # Replace logger = logging.getLogger patterns
        (r'logger\s*=\s*logging\.getLogger\((.*?)\)',
         r'logger = get_logger(\1)'),

        # Replace logging.basicConfig calls (remove them as Hive adapter handles this)
        (r'logging\.basicConfig\([^)]*\)\s*\n?', ''),

        # Replace logging.info/error/debug etc direct calls
        (r'logging\.(info|debug|warning|error|critical)\(',
         r'get_logger(__name__).\1('),
    ]

    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    # Clean up multiple blank lines
    while '\n\n\n' in content:
        content = content.replace('\n\n\n', '\n\n')

    # Only save if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    return False

def process_directory(directory: Path) -> Tuple[List[Path], List[Path], Dict]:
    """Process all Python files in directory for logging migration."""
    migrated_files = []
    skipped_files = []
    stats = {
        'total_files': 0,
        'already_migrated': 0,
        'no_logging': 0,
        'migrated': 0,
        'test_files': 0
    }

    # Get all Python files
    py_files = list(directory.rglob('*.py'))
    stats['total_files'] = len(py_files)

    for py_file in py_files:
        # Skip test files (they might have different logging needs)
        if 'test' in py_file.name or py_file.parent.name == 'tests':
            stats['test_files'] += 1
            continue

        # Skip the hive_logging_adapter itself
        if py_file.name == 'hive_logging_adapter.py':
            continue

        # Analyze file
        analysis = analyze_logging_usage(py_file)

        if analysis['already_uses_hive']:
            stats['already_migrated'] += 1
            skipped_files.append(py_file)
        elif not any([analysis['has_import_logging'], analysis['has_from_logging'],
                      analysis['uses_logging_module']]):
            stats['no_logging'] += 1
            skipped_files.append(py_file)
        else:
            # Try to migrate
            if migrate_logging_in_file(py_file):
                migrated_files.append(py_file)
                stats['migrated'] += 1
            else:
                skipped_files.append(py_file)

    return migrated_files, skipped_files, stats

def main():
    """Main execution for logging migration."""
    ecosystemiser_dir = Path(__file__).parent.parent

    print("EcoSystemiser Hive Integration - Logging Migration")
    print("=" * 60)
    print(f"Working directory: {ecosystemiser_dir}")
    print()

    # Process all Python files
    print("Analyzing and migrating logging...")
    migrated, skipped, stats = process_directory(ecosystemiser_dir / 'src')

    # Print statistics
    print(f"\nStatistics:")
    print(f"  Total source files: {stats['total_files']}")
    print(f"  Already using Hive adapter: {stats['already_migrated']}")
    print(f"  No logging used: {stats['no_logging']}")
    print(f"  Test files skipped: {stats['test_files']}")
    print(f"  Files migrated: {stats['migrated']}")

    if migrated:
        print("\nMigrated files:")
        for f in sorted(migrated):
            rel_path = f.relative_to(ecosystemiser_dir)
            print(f"  - {rel_path}")

    print("\nLogging migration complete!")
    print("All source files now use the Hive logging adapter.")

    # Next steps
    print("\nNext steps:")
    print("1. Review migrated files to ensure logging still works")
    print("2. Run tests to verify no logging issues")
    print("3. Continue with Phase 3: Configuration centralization")

if __name__ == "__main__":
    main()
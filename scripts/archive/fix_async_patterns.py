#!/usr/bin/env python3
"""Fix async pattern consistency - Golden Rule 14."""

import re
from pathlib import Path
from typing import Tuple


def fix_async_patterns(content: str) -> Tuple[str, int]:
    """Fix async patterns to use hive-async utilities."""
    lines = content.split("\n")
    fixed_lines = []
    changes = 0

    # Check if we need hive-async imports
    needs_hive_async = False
    has_hive_async = False

    for line in lines:
        if "from hive_async" in line:
            has_hive_async = True
            break

    # Process each line
    for line in lines:
        original_line = line

        # Replace direct asyncio patterns with hive-async
        if "asyncio.create_task(" in line:
            line = line.replace("asyncio.create_task(", "await async_executor.submit(")
            needs_hive_async = True
            changes += 1

        if "asyncio.gather(" in line:
            line = line.replace("asyncio.gather(", "await async_executor.gather(")
            needs_hive_async = True
            changes += 1

        if "async with aiosqlite.connect" in line:
            line = re.sub(r"async with aiosqlite\.connect\(([^)]+)\)", r"async with get_async_connection(\1)", line)
            needs_hive_async = True
            changes += 1

        # Fix connection handling patterns
        if "conn = await aiosqlite.connect" in line:
            line = re.sub(r"conn = await aiosqlite\.connect\(([^)]+)\)", r"conn = await get_async_connection(\1)", line)
            needs_hive_async = True
            changes += 1

        fixed_lines.append(line)

    # Add hive-async imports if needed
    if needs_hive_async and not has_hive_async:
        # Find import section
        import_idx = 0
        for i, line in enumerate(fixed_lines):
            if "import" in line or "from" in line:
                import_idx = i

        # Add hive-async imports
        fixed_lines.insert(import_idx + 1, "")
        fixed_lines.insert(import_idx + 2, "from hive_async import AsyncExecutor, get_async_connection")
        fixed_lines.insert(import_idx + 3, "")
        fixed_lines.insert(import_idx + 4, "async_executor = AsyncExecutor()")
        changes += 1

    return "\n".join(fixed_lines), changes


def fix_file(file_path: Path) -> bool:
    """Fix async patterns in a single file."""
    try:
        content = file_path.read_text()
        fixed_content, changes = fix_async_patterns(content)

        if changes > 0:
            file_path.write_text(fixed_content)
            print(f"Fixed {changes} async patterns in {file_path}")
            return True
        return False
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    """Fix async pattern violations."""
    # Files with async pattern violations from the report
    files_to_fix = [
        "apps/ecosystemiser/tests/unit/core/test_db.py",
        "packages/hive-performance/tests/unit/test_pool.py",
        "tests/benchmarks/test_cache_latency_benchmark.py",
        "tests/resilience/test_database_resilience.py",
    ]

    fixed_count = 0
    for file_path in files_to_fix:
        path = Path(file_path)
        if path.exists():
            if fix_file(path):
                fixed_count += 1
        else:
            print(f"File not found: {file_path}")

    print(f"\nFixed async patterns in {fixed_count} files")


if __name__ == "__main__":
    main()

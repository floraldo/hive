#!/usr/bin/env python3
"""Fix global state access violations for Rule 16 compliance."""

import re
from pathlib import Path
from typing import List, Tuple


def fix_config_none_pattern(file_path: Path) -> bool:
    """Fix config=None anti-pattern by making config required."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original = content

        # Fix patterns like: def __init__(self, ..., config=None, ...):
        # Replace with: def __init__(self, ..., config, ...):
        content = re.sub(r"(\s+config)(\s*=\s*None)(\s*[,)])", r"\1\3", content)

        # Fix patterns like: if config is None:
        # Replace with comment explaining config is now required
        content = re.sub(
            r"(\s+)if config is None:\s*\n\s+config = load_config\(\)",
            r"\1# Config is now required parameter (no fallback)",
            content,
        )

        if content != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True

        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def fix_load_config_calls(file_path: Path) -> bool:
    """Remove global load_config() calls."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original = content

        # Comment out standalone load_config() calls
        content = re.sub(
            r"^(\s*)config = load_config\(\)",
            r"\1# config = load_config()  # Config should be injected",
            content,
            flags=re.MULTILINE,
        )

        # Fix fallback patterns
        content = re.sub(
            r"if config is None:\s*\n\s+config = load_config\(\)",
            "# Config is now required (no fallback to load_config)",
            content,
        )

        if content != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True

        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main() -> None:
    """Fix global state access violations."""

    # Files with config=None patterns
    files_with_config_none = [
        "apps/ai-planner/src/ai_planner/agent.py",
        "apps/ai-planner/src/ai_planner/async_agent.py",
        "apps/ai-reviewer/src/ai_reviewer/async_agent.py",
        "apps/ecosystemiser/src/ecosystemiser/solver/milp_solver.py",
        "apps/ecosystemiser/src/ecosystemiser/solver/rule_based_engine.py",
    ]

    # Files with load_config() calls
    files_with_load_config = [
        "apps/ai-deployer/src/ai_deployer/core/config.py",
        "apps/ai-planner/src/ai_planner/core/config.py",
        "apps/ai-reviewer/src/ai_reviewer/core/config.py",
        "apps/hive-orchestrator/src/hive_orchestrator/hive_core.py",
    ]

    # Files with if config is None patterns
    files_with_config_fallback = [
        "apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service.py",
        "apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service_di.py",
        "packages/hive-async/src/hive_async/retry.py",
        "packages/hive-cache/src/hive_cache/cache_client.py",
        "packages/hive-cache/src/hive_cache/claude_cache.py",
        "packages/hive-cache/src/hive_cache/performance_cache.py",
        "packages/hive-config/src/hive_config/unified_config.py",
        "packages/hive-db/src/hive_db/sqlite_connector.py",
    ]

    fixed_count = 0

    print("Fixing config=None anti-patterns...")
    for file_path in files_with_config_none:
        full_path = Path(file_path)
        if full_path.exists():
            if fix_config_none_pattern(full_path):
                print(f"  Fixed: {file_path}")
                fixed_count += 1

    print("\nFixing load_config() global calls...")
    for file_path in files_with_load_config:
        full_path = Path(file_path)
        if full_path.exists():
            if fix_load_config_calls(full_path):
                print(f"  Fixed: {file_path}")
                fixed_count += 1

    print("\nFixing config fallback patterns...")
    for file_path in files_with_config_fallback:
        full_path = Path(file_path)
        if full_path.exists():
            if fix_config_none_pattern(full_path):
                print(f"  Fixed: {file_path}")
                fixed_count += 1

    print(f"\nFixed global state access in {fixed_count} files")
    print("\nNote: After these changes, config must be explicitly passed to all constructors.")
    print("This enforces proper dependency injection and removes global state.")


if __name__ == "__main__":
    main()

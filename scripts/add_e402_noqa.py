#!/usr/bin/env python3
"""Add E402 noqa to files with logger-before-imports pattern."""

from pathlib import Path

files = [
    "apps/hive-orchestrator/src/hive_orchestrator/__main__.py",
    "apps/hive-orchestrator/src/hive_orchestrator/config.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/bus/__init__.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/bus/events.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/bus/hive_events.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/claude/__init__.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service_di.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/claude/interfaces.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/claude/planner_bridge.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/claude/reviewer_bridge.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/db/__init__.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/db/async_compat.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/db/database.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/db/database_enhanced.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/errors/__init__.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/errors/hive_errors/__init__.py",
    "apps/hive-orchestrator/src/hive_orchestrator/core/monitoring/interfaces.py",
    "apps/hive-orchestrator/src/hive_orchestrator/dashboard.py",
    "apps/hive-orchestrator/src/hive_orchestrator/hive_core.py",
    "apps/hive-orchestrator/src/hive_orchestrator/hive_status.py",
    "apps/hive-orchestrator/src/hive_orchestrator/queen.py",
    "apps/hive-orchestrator/src/hive_orchestrator/tasks/__init__.py",
    "apps/hive-orchestrator/src/hive_orchestrator/worker.py",
    "apps/hive-orchestrator/tests/e2e/test_e2e_full.py",
    "apps/hive-orchestrator/tests/integration/test_basic_integration.py",
    "apps/hive-orchestrator/tests/integration/test_certification.py",
    "apps/hive-orchestrator/tests/integration/test_comprehensive.py",
    "apps/hive-orchestrator/tests/integration/test_individual_modules.py",
    "apps/hive-orchestrator/tests/integration/test_v3_certification.py",
    "apps/hive-orchestrator/tests/unit/test_golden_rules.py",
    "packages/hive-deployment/src/hive_deployment/__init__.py",
    "packages/hive-deployment/src/hive_deployment/deployment.py",
]

root = Path(r"C:\git\hive")

for file_path in files:
    full_path = root / file_path.replace("/", "\\")
    if not full_path.exists():
        print(f"SKIP: {file_path} not found")
        continue

    with open(full_path) as f:
        lines = f.readlines()

    # Check if already has noqa E402
    if any("noqa" in line and "E402" in line for line in lines[:10]):
        print(f"SKIP: {file_path} already has E402 noqa")
        continue

    # Find first line with content (not blank, not comment)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            # Check if it's a docstring
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # Add noqa before docstring
                lines.insert(i, "# ruff: noqa: E402\n")
                print(f"ADDED: {file_path} (before docstring at line {i+1})")
                break
            # Check if it's from/import
            elif stripped.startswith("from ") or stripped.startswith("import "):
                # This shouldn't happen with E402 error
                print(f"WARN: {file_path} - imports at top, should not have E402")
                break

    with open(full_path, "w") as f:
        f.writelines(lines)

print("\nDone!")

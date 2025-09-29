#!/usr/bin/env python3
"""
Debug path matching for archive files
"""
from pathlib import Path

test_path = Path("apps/ecosystemiser/scripts/archive/debug_flows.py")
path_str = str(test_path)
normalized_path_str = path_str.replace("\\", "/")

print(f"Original path: {path_str}")
print(f"Normalized path: {normalized_path_str}")
print(f"Contains /archive/: {'/archive/' in normalized_path_str}")
print(f"Contains /scripts/: {'/scripts/' in normalized_path_str}")
print(f"Contains .backup: {'.backup' in normalized_path_str}")

# Test the exact condition with normalization
should_skip = (
    "/scripts/" in normalized_path_str
    or "/tests/" in normalized_path_str
    or "/archive/" in normalized_path_str
    or test_path.name.startswith(("test_", "demo_", "run_"))
    or ".backup" in normalized_path_str
)

print(f"Should skip: {should_skip}")

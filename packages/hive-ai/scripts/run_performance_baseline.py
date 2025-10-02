#!/usr/bin/env python3
"""
Runner script for performance baseline that ensures correct package imports.

This script sets up the Python path to use workspace packages instead of
globally installed ones, preventing ImportError issues.
"""
import sys
from pathlib import Path

# Add workspace packages to Python path (before any other imports)
repo_root = Path(__file__).parent.parent.parent.parent
packages_to_add = [
    "hive-ai/src",
    "hive-config/src",
    "hive-logging/src",
    "hive-async/src",
    "hive-errors/src",
    "hive-db/src",
    "hive-cache/src",
    "hive-performance/src",
]

for pkg in packages_to_add:
    pkg_path = str(repo_root / "packages" / pkg)
    if pkg_path not in sys.path:
        sys.path.insert(0, pkg_path)

# Now import and run the actual performance baseline
if __name__ == "__main__":
    # Import after path setup
    import performance_baseline
    import asyncio

    asyncio.run(performance_baseline.main())

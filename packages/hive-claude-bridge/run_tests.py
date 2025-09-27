#!/usr/bin/env python3
"""
Test runner for hive-claude-bridge package
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Run tests with proper PYTHONPATH setup"""

    # Get the project root
    project_root = Path(__file__).parent

    # Set up PYTHONPATH to include all necessary packages
    pythonpath_dirs = [
        project_root / "src",
        project_root.parent / "hive-errors" / "src",
        project_root.parent / "hive-core-db" / "src"
    ]

    # Convert to absolute paths and join
    pythonpath = os.pathsep.join(str(p.resolve()) for p in pythonpath_dirs)

    # Set environment
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath

    # Run pytest with all arguments passed through
    cmd = [sys.executable, "-m", "pytest", "tests/"] + sys.argv[1:]

    print(f"Running: {' '.join(cmd)}")
    print(f"PYTHONPATH: {pythonpath}")
    print()

    result = subprocess.run(cmd, cwd=project_root, env=env)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
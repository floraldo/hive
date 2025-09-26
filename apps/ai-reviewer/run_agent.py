#!/usr/bin/env python3
"""
Standalone entry point for AI Reviewer Agent
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Add paths for Hive packages
hive_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(hive_root / "packages" / "hive-logging" / "src"))

# Now import and run
from ai_reviewer.agent import main

if __name__ == "__main__":
    main()
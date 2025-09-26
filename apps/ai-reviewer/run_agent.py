#!/usr/bin/env python3
"""
Standalone entry point for AI Reviewer Agent
"""

import sys
import os
from pathlib import Path

# Add packages path first for hive-config
hive_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-config" / "src"))

# Configure all Hive paths centrally
from hive_config import setup_hive_paths
setup_hive_paths()

# Now import and run
from ai_reviewer.agent import main

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Launch the AI Planner daemon."""

import sys
from pathlib import Path

# Add packages path first for hive-config
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-config" / "src"))

# Add apps directories to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "ai-planner" / "src"))

# Configure all Hive paths centrally
from hive_config import setup_hive_paths

setup_hive_paths()

from ai_planner.agent import main

if __name__ == "__main__":
    main()

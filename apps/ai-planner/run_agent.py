#!/usr/bin/env python3
"""
Standalone entry point for AI Planner Agent

Intelligent task planning and workflow generation agent that monitors
the planning_queue and generates executable plans for complex tasks.
"""

import sys
import os
from pathlib import Path

# Add packages path first for hive-config
hive_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-config" / "src"))

# Add local src directory for ai_planner module
app_root = Path(__file__).parent
sys.path.insert(0, str(app_root / "src"))

# Configure all Hive paths centrally
from hive_config import setup_hive_paths
setup_hive_paths()

# Now import and run
from ai_planner.agent import main

if __name__ == "__main__":
    main()
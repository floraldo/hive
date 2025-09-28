#!/usr/bin/env python3
"""
Standalone entry point for AI Planner Agent

Intelligent task planning and workflow generation agent that monitors
the planning_queue and generates executable plans for complex tasks.
"""

import sys
import os
from pathlib import Path

# Configure all Hive paths centrally using path manager
# Note: This assumes the workspace has been properly installed with Poetry
from hive_config import setup_hive_paths
setup_hive_paths()

# Now import and run
from ai_planner.agent import main

if __name__ == "__main__":
    main()
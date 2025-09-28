#!/usr/bin/env python3
"""
Standalone entry point for AI Planner Agent

Intelligent task planning and workflow generation agent that monitors
the planning_queue and generates executable plans for complex tasks.
"""

import sys
import os
from pathlib import Path

# Now import and run
from ai_planner.agent import main

if __name__ == "__main__":
    main()
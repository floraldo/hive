from hive_logging import get_logger

logger = get_logger(__name__)

"""
AI Planner Agent Package

Intelligent task planning and workflow generation agent for the Hive system.
Monitors the planning_queue and generates executable plans for complex tasks.
"""

__version__ = "1.0.0"
__author__ = "Hive Fleet Command"

from .agent import AIPlanner, main

__all__ = ["AIPlanner", "main"]

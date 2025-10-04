"""
AI Planner Agent Package

Intelligent task planning and workflow generation agent for the Hive system.
Monitors the planning_queue and generates executable plans for complex tasks.
"""

from hive_logging import get_logger

from .agent import AIPlanner, main

logger = get_logger(__name__)

__version__ = "1.0.0"
__author__ = "Hive Fleet Command"

__all__ = ["AIPlanner", "main"]

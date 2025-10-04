"""Hive Coder - The Hands of Project Colossus

Autonomous code generator that transforms ExecutionPlans into production-ready services.

Example:
    from hive_coder import CoderAgent

    coder = CoderAgent()
    result = coder.execute_plan("execution_plan.json", output_dir="generated/my-service")

"""

from .agent import CoderAgent
from .models import ExecutionResult, TaskResult, ValidationResult

__version__ = "0.1.0"

__all__ = [
    "CoderAgent",
    "ExecutionResult",
    "TaskResult",
    "ValidationResult",
]

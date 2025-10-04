"""Hive Architect - The Brain of Project Colossus

Transforms natural language requirements into executable task plans.

Example:
    from hive_architect import ArchitectAgent

    agent = ArchitectAgent()
    plan = agent.create_plan("Create a 'feedback-service' API that stores user feedback")
    plan.to_json_file("execution_plan.json")

"""

from .agent import ArchitectAgent
from .models import ExecutionPlan, ExecutionTask, ParsedRequirement, ServiceType, TaskType
from .nlp import RequirementParser
from .planning import PlanGenerator

__version__ = "0.1.0"

__all__ = [
    "ArchitectAgent",
    "ExecutionPlan",
    "ExecutionTask",
    "ParsedRequirement",
    "PlanGenerator",
    "RequirementParser",
    "ServiceType",
    "TaskType",
]

"""Dependency resolution for task ordering.

Ensures tasks execute in correct order based on dependencies using topological sort.
"""

from __future__ import annotations

from hive_architect.models import ExecutionPlan, ExecutionTask
from hive_errors import BaseError
from hive_logging import get_logger

logger = get_logger(__name__)


class DependencyError(BaseError):
    """Raised when dependency resolution fails"""



class CyclicDependencyError(DependencyError):
    """Raised when circular dependencies detected"""



class DependencyResolver:
    """Resolves task dependencies and determines execution order.

    Uses topological sort (Kahn's algorithm) to order tasks such that
    dependencies are always executed before dependent tasks.
    """

    def __init__(self) -> None:
        self.logger = logger

    def resolve_order(self, plan: ExecutionPlan) -> list[ExecutionTask]:
        """Resolve task execution order based on dependencies.

        Args:
            plan: ExecutionPlan with tasks and dependencies

        Returns:
            Ordered list of tasks ready for execution

        Raises:
            CyclicDependencyError: If circular dependencies detected
            DependencyError: If dependency graph invalid

        """
        self.logger.info(f"Resolving task order for plan: {plan.plan_id}")

        # Build task lookup
        task_map = {task.task_id: task for task in plan.tasks}

        # Build dependency graph
        in_degree = {task.task_id: 0 for task in plan.tasks}
        dependency_graph = {task.task_id: [] for task in plan.tasks}

        for task in plan.tasks:
            for dep in task.dependencies:
                dep_id = dep.task_id

                # Validate dependency exists
                if dep_id not in task_map:
                    error_msg = f"Task {task.task_id} depends on non-existent task {dep_id}"
                    self.logger.error(error_msg)
                    raise DependencyError(error_msg)

                # Build graph
                dependency_graph[dep_id].append(task.task_id)
                in_degree[task.task_id] += 1

        # Topological sort using Kahn's algorithm
        ordered_tasks = []
        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]

        while queue:
            # Get next task with no dependencies
            current_id = queue.pop(0)
            ordered_tasks.append(task_map[current_id])

            # Update dependencies
            for dependent_id in dependency_graph[current_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        # Check for cycles
        if len(ordered_tasks) != len(plan.tasks):
            remaining = [task_id for task_id, degree in in_degree.items() if degree > 0]
            error_msg = f"Circular dependencies detected involving tasks: {remaining}"
            self.logger.error(error_msg)
            raise CyclicDependencyError(error_msg)

        self.logger.info(f"Task order resolved: {[t.task_id for t in ordered_tasks]}")
        return ordered_tasks

    def validate_dependencies(self, plan: ExecutionPlan) -> dict[str, bool]:
        """Validate dependency graph without resolving order.

        Args:
            plan: ExecutionPlan to validate

        Returns:
            Validation results with boolean flags

        """
        task_ids = {task.task_id for task in plan.tasks}
        validation = {"has_tasks": len(plan.tasks) > 0, "all_dependencies_exist": True, "no_cycles": True}

        # Check all dependencies exist
        for task in plan.tasks:
            for dep in task.dependencies:
                if dep.task_id not in task_ids:
                    validation["all_dependencies_exist"] = False
                    self.logger.warning(f"Task {task.task_id} has invalid dependency: {dep.task_id}")

        # Check for cycles (only if dependencies exist)
        if validation["all_dependencies_exist"]:
            try:
                self.resolve_order(plan)
            except CyclicDependencyError:
                validation["no_cycles"] = False
            except DependencyError:
                # Already logged above
                pass

        return validation

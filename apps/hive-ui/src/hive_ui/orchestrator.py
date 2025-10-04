"""Project Orchestrator for Colossus Pipeline.

Manages the complete autonomous development workflow:
1. Architect Agent: NL requirement → ExecutionPlan
2. Coder Agent: ExecutionPlan → Service code
3. Guardian Agent: Validation → Auto-fix → Approval
"""

from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from hive_config import create_config_from_sources
from hive_logging import get_logger

logger = get_logger(__name__)


class ProjectStatus(str, Enum):
    """Project execution status."""

    PENDING = "pending"
    PLANNING = "planning"
    CODING = "coding"
    VALIDATING = "validating"
    FIXING = "fixing"
    COMPLETE = "complete"
    FAILED = "failed"


class ProjectOrchestrator:
    """Orchestrates the complete Colossus autonomous development pipeline.

    This is the command center that coordinates the three autonomous agents:
    - Architect (Brain): Natural language → ExecutionPlan
    - Coder (Hands): ExecutionPlan → Service code
    - Guardian (Immune System): Validation → Auto-fix → Approval
    """

    # Python built-in modules to avoid in service names
    PYTHON_BUILTINS = {
        "uuid",
        "json",
        "time",
        "logging",
        "config",
        "path",
        "sys",
        "os",
        "io",
        "re",
        "test",
        "main",
        "http",
        "email",
        "string",
        "data",
        "file",
        "user",
    }

    def __init__(self, workspace_dir: Path | None = None):
        """Initialize Project Orchestrator.

        Args:
            workspace_dir: Directory for project workspaces

        """
        self.config = create_config_from_sources()
        self.workspace_dir = workspace_dir or Path("./workspaces")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Project state tracking
        self.projects: dict[str, dict[str, Any]] = {}

    async def create_project(
        self,
        requirement: str,
        service_name: str | None = None,
    ) -> str:
        """Create new autonomous development project.

        Args:
            requirement: Natural language requirement description
            service_name: Optional service name (auto-generated if not provided)

        Returns:
            project_id: Unique project identifier

        Raises:
            ValueError: If provided service_name conflicts with Python built-ins

        """
        project_id = str(uuid4())

        # Validate service name if provided
        if service_name:
            if service_name.lower() in self.PYTHON_BUILTINS:
                msg = (
                    f"Service name '{service_name}' conflicts with Python built-in module. "
                    f"Please choose a different name."
                )
                logger.error(msg)
                raise ValueError(msg)
            logger.info(f"Using provided service name: {service_name}")
        else:
            # Auto-generate safe name
            service_name = f"service-{project_id[:8]}"
            logger.info(f"Auto-generated service name: {service_name}")

        # Create project workspace
        project_dir = self.workspace_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        # Initialize project state
        self.projects[project_id] = {
            "id": project_id,
            "service_name": service_name,
            "requirement": requirement,
            "status": ProjectStatus.PENDING,
            "workspace": str(project_dir),
            "plan_file": None,
            "service_dir": None,
            "logs": [],
            "created_at": None,  # Will be set when execution starts
        }

        logger.info(f"Created project {project_id}: {service_name}")
        return project_id

    async def execute_project(self, project_id: str) -> dict[str, Any]:
        """Execute complete autonomous development pipeline.

        Pipeline stages:
        1. PLANNING: Architect generates ExecutionPlan
        2. CODING: Coder implements service from plan
        3. VALIDATING: Guardian validates code quality
        4. FIXING: Guardian auto-fixes issues (if needed)
        5. COMPLETE: Service ready for deployment

        Args:
            project_id: Project to execute

        Returns:
            project_state: Final project state with results

        """
        if project_id not in self.projects:
            msg = f"Project {project_id} not found"
            raise ValueError(msg)

        project = self.projects[project_id]
        project["status"] = ProjectStatus.PLANNING

        try:
            # Stage 1: Architect - Generate ExecutionPlan
            await self._run_architect(project)

            # Stage 2: Coder - Implement service
            project["status"] = ProjectStatus.CODING
            await self._run_coder(project)

            # Stage 3: Guardian - Validate and auto-fix
            project["status"] = ProjectStatus.VALIDATING
            validation_passed = await self._run_guardian(project)

            if validation_passed:
                project["status"] = ProjectStatus.COMPLETE
                logger.info(f"Project {project_id} completed successfully")
            else:
                project["status"] = ProjectStatus.FAILED
                logger.error(f"Project {project_id} failed validation")

        except Exception as e:
            project["status"] = ProjectStatus.FAILED
            project["logs"].append(f"ERROR: {e}")
            logger.exception(f"Project {project_id} failed")
            raise

        return project

    async def _run_architect(self, project: dict[str, Any]) -> None:
        """Run Architect Service to generate ExecutionPlan."""
        logger.info(f"Running Architect for project {project['id']}")

        # Import Architect Service from orchestrator
        from hive_orchestrator.services.colossus import ArchitectService

        # Create service
        architect = ArchitectService(config=self.config)

        # Generate plan
        plan_file = Path(project["workspace"]) / "execution_plan.json"
        plan = await architect.create_plan_from_requirement(
            requirement=project["requirement"],
            output_path=plan_file,
        )

        project["plan_file"] = str(plan_file)
        project["logs"].append(f"Plan generated: {plan.service_name}")
        logger.info(f"Plan generated for {project['id']}: {plan.service_name}")

    async def _run_coder(self, project: dict[str, Any]) -> None:
        """Run Coder Service to implement service."""
        logger.info(f"Running Coder for project {project['id']}")

        # Import Coder Service from orchestrator
        from hive_orchestrator.services.colossus import CoderService

        # Create service
        coder = CoderService(config=self.config)

        # Execute plan
        output_dir = Path(project["workspace"]) / "service"
        result = await coder.execute_plan(
            plan_file=Path(project["plan_file"]),
            output_dir=output_dir,
        )

        project["service_dir"] = str(output_dir)
        project["logs"].append(f"Service generated: {result.total_tasks} tasks executed")
        logger.info(f"Service generated for {project['id']}")

    async def _run_guardian(self, project: dict[str, Any]) -> bool:
        """Run Guardian Agent for validation and auto-fix.

        Returns:
            validation_passed: True if service is deployment-ready

        Note:
            For MVP Phase 1, Guardian integration is simplified.
            Full auto-fix loop will be enabled in Phase 2.

        """
        logger.info(f"Running Guardian for project {project['id']}")

        # MVP Phase 1: Basic syntax validation only
        # Phase 2 will integrate full ReviewAgent with auto-fix loop
        service_path = Path(project["service_dir"])

        try:
            # Check 1: Service directory must not be empty
            py_files = list(service_path.rglob("*.py"))
            if not py_files:
                project["logs"].append("Validation FAILED: No Python files generated")
                logger.error(f"Empty service directory for {project['id']}")
                return False

            # Check 2: Find the actual service root (hive-toolkit creates apps/{name}/src/{name}/)
            # Look for main.py at service level (not in api/ subdirectory)
            main_py_files = [
                p
                for p in service_path.rglob("main.py")
                if "__init__.py" in [f.name for f in p.parent.iterdir()]
                and p.parent.name != "api"  # Exclude api/main.py
            ]
            if not main_py_files:
                project["logs"].append("Validation FAILED: No service-level main.py found")
                logger.error(f"No service-level main.py in service directory for {project['id']}")
                return False

            # Use the directory containing main.py as the service root
            service_root = main_py_files[0].parent

            # Check 3: Minimum viable structure at service root
            required_files = ["__init__.py", "main.py"]
            for required in required_files:
                if not (service_root / required).exists():
                    project["logs"].append(f"Validation FAILED: Missing {required}")
                    logger.error(f"Missing required file {required} for {project['id']}")
                    return False

            # Check 4: Basic syntax check on all generated files
            import subprocess
            import sys

            for py_file in py_files:
                result = subprocess.run(  # noqa: S603
                    [sys.executable, "-m", "py_compile", str(py_file)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    project["logs"].append(f"Syntax error in {py_file.name}")
                    logger.warning(f"Syntax error in {py_file}")
                    return False

            project["logs"].append(f"Validation PASS: {len(py_files)} files validated")
            logger.info(f"Validation passed for {project['id']}")
            return True

        except Exception as e:
            project["logs"].append(f"Validation ERROR: {e}")
            logger.exception(f"Validation failed for {project['id']}")
            return False

    def get_project_status(self, project_id: str) -> dict[str, Any]:
        """Get current project status and logs."""
        if project_id not in self.projects:
            msg = f"Project {project_id} not found"
            raise ValueError(msg)

        return self.projects[project_id]

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects."""
        return list(self.projects.values())

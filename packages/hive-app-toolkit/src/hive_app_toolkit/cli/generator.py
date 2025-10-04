"""Application generator for Hive Application Toolkit."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from hive_logging import get_logger

from .templates import TemplateManager

logger = get_logger(__name__)


class ServiceType(Enum):
    """Supported service types."""

    API = "api"
    WORKER = "worker"
    BATCH = "batch"
    WEBHOOK = "webhook"


class ApplicationGenerator:
    """Generate production-ready Hive applications from blueprints.

    Provides methods to:
    - Generate new services from templates
    - Add toolkit features to existing applications
    - Check integration status
    """

    def __init__(self) -> None:
        """Initialize application generator."""
        self.template_manager = TemplateManager()

    async def generate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Generate a new Hive application.

        Args:
            config: Generation configuration containing:
                - app_name: Application name
                - service_type: ServiceType enum
                - output_dir: Output directory path
                - namespace: Kubernetes namespace
                - port: Application port
                - enable_database: Enable database configuration
                - enable_cache: Enable cache configuration
                - enable_auth: Enable authentication
                - cost_limits: Cost limit configuration
                - dry_run: If True, don't create files

        Returns:
            Dictionary with generation results

        """
        app_name = config["app_name"]
        service_type = config["service_type"]
        output_dir = Path(config["output_dir"])
        dry_run = config.get("dry_run", False)

        logger.info(f"Generating {service_type.value} service: {app_name}")

        # Load blueprint for service type
        blueprint = await self._load_blueprint(service_type)

        # Prepare template context
        context = self._prepare_context(config, blueprint)

        # Generate directory structure
        files_created = []

        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            files_created = await self._generate_from_blueprint(blueprint, context, output_dir)
        else:
            # Dry run - just list what would be created
            files_created = await self._list_files_from_blueprint(blueprint, context, output_dir)

        # Prepare next steps
        next_steps = [
            f"cd {output_dir}",
            "poetry install",
            "pytest",
            "poetry run python -m pytest --collect-only",
        ]

        if config.get("enable_database"):
            next_steps.append("Configure database connection in config/settings.yaml")

        return {
            "app_name": app_name,
            "service_type": service_type.value,
            "output_dir": str(output_dir),
            "files_created": files_created,
            "next_steps": next_steps,
        }

    async def add_api_foundation(self, output_dir: Path) -> dict[str, Any]:
        """Add API foundation to an existing application.

        Args:
            output_dir: Target directory

        Returns:
            Dictionary with modified files

        """
        logger.info(f"Adding API foundation to {output_dir}")

        files_modified = []

        # Check if pyproject.toml exists
        pyproject_path = output_dir / "pyproject.toml"
        if not pyproject_path.exists():
            raise FileNotFoundError(f"No pyproject.toml found in {output_dir}")

        # Add FastAPI and related dependencies
        context = {
            "add_api_dependencies": True,
            "fastapi_version": "^0.104.1",
            "uvicorn_version": "^0.24.0",
        }

        # Add API module
        api_dir = output_dir / "src" / output_dir.name.replace("-", "_") / "api"
        api_dir.mkdir(parents=True, exist_ok=True)

        # Render API templates
        api_templates = [
            ("python/api/main.py.j2", api_dir / "main.py"),
            ("python/api/health.py.j2", api_dir / "health.py"),
            ("python/api/__init__.py.j2", api_dir / "__init__.py"),
        ]

        for template_path, output_path in api_templates:
            await self.template_manager.render_template(template_path, context, output_path)
            files_modified.append(str(output_path))

        return {"files_modified": files_modified}

    async def add_kubernetes_manifests(self, output_dir: Path, namespace: str = "hive-platform") -> dict[str, Any]:
        """Add Kubernetes manifests to an existing application.

        Args:
            output_dir: Target directory
            namespace: Kubernetes namespace

        Returns:
            Dictionary with created files

        """
        logger.info(f"Adding Kubernetes manifests to {output_dir}")

        files_created = []

        # Create k8s directory
        k8s_dir = output_dir / "k8s"
        k8s_dir.mkdir(parents=True, exist_ok=True)

        # Get app name from directory
        app_name = output_dir.name

        context = {
            "app_name": app_name,
            "app_module": app_name.replace("-", "_"),
            "namespace": namespace,
            "port": 8000,
            "replicas": 2,
        }

        # Render K8s templates
        k8s_templates = [("k8s/deployment.yaml.j2", k8s_dir / "deployment.yaml")]

        for template_path, output_path in k8s_templates:
            await self.template_manager.render_template(template_path, context, output_path)
            files_created.append(str(output_path))

        return {"files_created": files_created}

    async def add_cicd_pipeline(self, output_dir: Path, registry: str = "ghcr.io") -> dict[str, Any]:
        """Add CI/CD pipeline to an existing application.

        Args:
            output_dir: Target directory
            registry: Docker registry

        Returns:
            Dictionary with created files

        """
        logger.info(f"Adding CI/CD pipeline to {output_dir}")

        files_created = []

        # Create .github/workflows directory
        workflows_dir = output_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        # Get app name from directory
        app_name = output_dir.name

        context = {"app_name": app_name, "registry": registry, "python_version": "3.11"}

        # For now, create a basic CI workflow
        # TODO: Create actual CI/CD template
        ci_workflow = workflows_dir / "ci.yaml"
        ci_content = f"""name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '{context["python_version"]}'
      - run: pip install poetry
      - run: poetry install
      - run: poetry run pytest
      - run: poetry run ruff check
"""
        ci_workflow.write_text(ci_content)
        files_created.append(str(ci_workflow))

        return {"files_created": files_created}

    async def get_integration_status(self, output_dir: Path) -> dict[str, Any]:
        """Get integration status of Hive toolkit components.

        Args:
            output_dir: Target directory

        Returns:
            Status information dictionary

        """
        logger.info(f"Checking integration status for {output_dir}")

        status = {}

        # Check API integration
        api_dir = output_dir / "src" / output_dir.name.replace("-", "_") / "api"
        status["api"] = {
            "integrated": api_dir.exists(),
            "status": "Integrated" if api_dir.exists() else "Not integrated",
            "files": [str(f) for f in api_dir.glob("*.py")] if api_dir.exists() else [],
        }

        # Check Kubernetes manifests
        k8s_dir = output_dir / "k8s"
        status["kubernetes"] = {
            "integrated": k8s_dir.exists(),
            "status": "Integrated" if k8s_dir.exists() else "Not integrated",
            "files": [str(f) for f in k8s_dir.glob("*.yaml")] if k8s_dir.exists() else [],
        }

        # Check CI/CD pipeline
        workflows_dir = output_dir / ".github" / "workflows"
        status["cicd"] = {
            "integrated": workflows_dir.exists(),
            "status": "Integrated" if workflows_dir.exists() else "Not integrated",
            "files": [str(f) for f in workflows_dir.glob("*.yaml")] if workflows_dir.exists() else [],
        }

        # Check Docker
        dockerfile = output_dir / "Dockerfile"
        status["docker"] = {
            "integrated": dockerfile.exists(),
            "status": "Integrated" if dockerfile.exists() else "Not integrated",
            "files": [str(dockerfile)] if dockerfile.exists() else [],
        }

        return status

    async def _load_blueprint(self, service_type: ServiceType) -> dict[str, Any]:
        """Load blueprint for service type."""
        # Import blueprints
        from ..blueprints import get_blueprint

        return get_blueprint(service_type)

    def _prepare_context(self, config: dict[str, Any], blueprint: dict[str, Any]) -> dict[str, Any]:
        """Prepare template rendering context."""
        app_name = config["app_name"]
        app_module = app_name.replace("-", "_")

        # Base context
        context = {
            "app_name": app_name,
            "app_module": app_module,
            "description": config.get("description", f"{app_name} - Hive platform service"),
            "version": "0.1.0",
            "service_type": config["service_type"].value,
            "namespace": config.get("namespace", "hive-platform"),
            "port": config.get("port", 8000),
            "enable_database": config.get("enable_database", False),
            "enable_cache": config.get("enable_cache", True),
            "enable_auth": config.get("enable_auth", False),
            "cost_limits": config.get("cost_limits", {}),
        }

        # Merge with blueprint context
        if "context_variables" in blueprint:
            context.update(blueprint["context_variables"])

        # Add hive packages list
        context["hive_packages"] = blueprint.get("hive_packages", [])

        # Add K8s/Docker defaults
        context.setdefault("resources", {
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"cpu": "2000m", "memory": "4Gi"},
        })
        context.setdefault("health_check", {
            "liveness": {"initial_delay": 10, "period": 30, "timeout": 5, "failure_threshold": 3},
            "readiness": {"initial_delay": 15, "period": 10, "timeout": 5, "failure_threshold": 3},
        })
        context.setdefault("image_repository", "ghcr.io/hive")
        context.setdefault("image_tag", "latest")
        context.setdefault("app_user", "appuser")
        context.setdefault("replicas", 2)

        return context

    async def _generate_from_blueprint(
        self,
        blueprint: dict[str, Any],
        context: dict[str, Any],
        output_dir: Path,
    ) -> list[str]:
        """Generate files from blueprint."""
        files_created = []

        # Create directory structure
        for dir_path_template, files in blueprint.get("directory_structure", {}).items():
            # Render directory path
            dir_path = output_dir / Path(dir_path_template.format(**context))
            dir_path.mkdir(parents=True, exist_ok=True)

            # Create files in directory
            for file_name in files:
                file_path = dir_path / file_name
                # Create empty file or from template
                if not file_path.exists():
                    file_path.write_text("")
                    files_created.append(str(file_path))

        # Render templates
        for template_path in blueprint.get("templates", []):
            # Determine output path from template path
            output_path = self._determine_output_path(template_path, output_dir, context)
            await self.template_manager.render_template(template_path, context, output_path)
            files_created.append(str(output_path))

        return files_created

    async def _list_files_from_blueprint(
        self,
        blueprint: dict[str, Any],
        context: dict[str, Any],
        output_dir: Path,
    ) -> list[str]:
        """List files that would be created (dry run)."""
        files_would_create = []

        # List directory structure
        for dir_path_template in blueprint.get("directory_structure", {}).keys():
            dir_path = output_dir / Path(dir_path_template.format(**context))
            files_would_create.append(f"{dir_path}/ (directory)")

        # List template files
        for template_path in blueprint.get("templates", []):
            output_path = self._determine_output_path(template_path, output_dir, context)
            files_would_create.append(str(output_path))

        return files_would_create

    def _determine_output_path(self, template_path: str, output_dir: Path, context: dict[str, Any]) -> Path:
        """Determine output file path from template path."""
        # Remove .j2 extension
        if template_path.endswith(".j2"):
            template_path = template_path[:-3]

        # Map template categories to output locations
        if template_path.startswith("python/"):
            relative_path = template_path.replace("python/", "")
            if "api/" in relative_path:
                # API module files
                relative_path = relative_path.replace("api/", f"src/{context['app_module']}/api/")
            elif relative_path in ["main.py", "__init__.py", "config.py"]:
                # Root module files
                relative_path = f"src/{context['app_module']}/{relative_path}"
            else:
                # Other python files
                relative_path = f"src/{context['app_module']}/{relative_path}"
        elif template_path.startswith("tests/"):
            relative_path = template_path
        elif template_path.startswith("docs/"):
            relative_path = template_path.replace("docs/", "")
        elif template_path.startswith("config/"):
            relative_path = template_path.replace("config/", "")
        elif template_path.startswith("k8s/"):
            relative_path = template_path
        elif template_path.startswith("docker/"):
            relative_path = template_path.replace("docker/", "")
        else:
            relative_path = template_path

        return output_dir / relative_path

"""Template management for Hive Application Toolkit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template

from hive_logging import get_logger

logger = get_logger(__name__)


class TemplateManager:
    """
    Manage Jinja2 templates for code generation.

    Provides methods to:
    - Load and render templates
    - Apply custom filters
    - Manage template paths
    """

    def __init__(self) -> None:
        """Initialize template manager."""
        self.template_dir = Path(__file__).parent.parent / "templates"

        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

        # Add custom filters
        self.env.filters["module_name"] = self._to_module_name
        self.env.filters["class_name"] = self._to_class_name

    async def render_template(
        self,
        template_path: str,
        context: dict[str, Any],
        output_path: Path,
    ) -> str:
        """
        Render a template and write to file.

        Args:
            template_path: Path to template (relative to templates dir)
            context: Template context variables
            output_path: Output file path

        Returns:
            Rendered content as string
        """
        logger.debug(f"Rendering template {template_path} to {output_path}")

        # Load and render template
        template = self.env.get_template(template_path)
        content = template.render(**context)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write rendered content
        output_path.write_text(content)

        logger.debug(f"Template rendered successfully: {output_path}")
        return content

    def render_string(self, template_string: str, context: dict[str, Any]) -> str:
        """
        Render a template from string.

        Args:
            template_string: Template content as string
            context: Template context variables

        Returns:
            Rendered content
        """
        template = Template(template_string)
        return template.render(**context)

    def template_exists(self, template_path: str) -> bool:
        """
        Check if template exists.

        Args:
            template_path: Path to template (relative to templates dir)

        Returns:
            True if template exists
        """
        full_path = self.template_dir / template_path
        return full_path.exists()

    def list_templates(self, pattern: str = "**/*.j2") -> list[str]:
        """
        List all templates matching pattern.

        Args:
            pattern: Glob pattern for templates

        Returns:
            List of template paths
        """
        templates = []
        for template_file in self.template_dir.glob(pattern):
            relative_path = template_file.relative_to(self.template_dir)
            templates.append(str(relative_path))

        return sorted(templates)

    @staticmethod
    def _to_module_name(value: str) -> str:
        """Convert string to Python module name (snake_case)."""
        return value.replace("-", "_").replace(" ", "_").lower()

    @staticmethod
    def _to_class_name(value: str) -> str:
        """Convert string to Python class name (PascalCase)."""
        parts = value.replace("-", " ").replace("_", " ").split()
        return "".join(part.capitalize() for part in parts)

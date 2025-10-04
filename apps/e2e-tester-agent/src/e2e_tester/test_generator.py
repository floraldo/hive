"""AI-powered test generation using templates and scenario parsing."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from hive_logging import get_logger
from jinja2 import Environment, FileSystemLoader

from .models import GeneratedTest, TestScenario
from .scenario_parser import ScenarioParser

logger = get_logger(__name__)


class TestGenerator:
    """Generate E2E tests from feature descriptions.

    Uses scenario parsing and Jinja2 templates to generate pytest-based
    browser automation tests with page object pattern.

    Example:
        generator = TestGenerator()
        generated = generator.generate_test(
            feature="User can login with Google OAuth",
            url="https://myapp.dev/login"
        )
        print(generated.test_code)

    """

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialize test generator.

        Args:
            template_dir: Path to Jinja2 templates (default: ./templates/)

        """
        self.logger = logger

        # Initialize scenario parser
        self.parser = ScenarioParser()

        # Setup Jinja2 environment
        if template_dir is None:
            # Default to templates/ relative to this file
            template_dir = Path(__file__).parent.parent.parent / "templates"

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,  # Prevent XSS in generated code
        )

        self.logger.info(f"Test generator initialized with templates: {template_dir}")

    def generate_test(
        self,
        feature: str,
        url: str,
        additional_context: dict[str, str] | None = None,
        generate_page_object: bool = True,
    ) -> GeneratedTest:
        """Generate E2E test from feature description.

        Args:
            feature: Natural language feature description
            url: Target URL for testing
            additional_context: Optional context hints
            generate_page_object: Include page object pattern

        Returns:
            Generated test code with metadata

        Example:
            generated = generator.generate_test(
                feature="User can login with Google OAuth",
                url="https://myapp.dev/login",
                additional_context={
                    "success_indicator": "User dashboard visible"
                }
            )

        """
        self.logger.info(f"Generating test for feature: {feature}")

        # Parse feature into scenario
        scenario = self.parser.parse(feature, url, additional_context)

        # Generate test name (safe for Python)
        test_name = self._generate_test_name(scenario.feature_name)

        # Generate page object class name
        page_object_class = self._generate_page_object_class_name(scenario.feature_name)
        page_object_name = page_object_class.lower().replace("page", "_page")

        # Render test template
        test_code = self._render_test_template(
            scenario=scenario,
            test_name=test_name,
            page_object_class=page_object_class,
            page_object_name=page_object_name,
        )

        generated = GeneratedTest(
            test_code=test_code,
            test_name=test_name,
            page_object_code=None,  # Included in test_code
            feature_description=feature,
            target_url=url,
            generated_at=datetime.now(),
            tokens_used=None,  # Would be set by Sequential Thinking integration
            reasoning_steps=None,
        )

        self.logger.info(f"Generated test: {test_name} ({len(test_code)} chars)")

        return generated

    def generate_test_file(
        self,
        feature: str,
        url: str,
        output_path: Path,
        additional_context: dict[str, str] | None = None,
    ) -> GeneratedTest:
        """Generate E2E test and save to file.

        Args:
            feature: Natural language feature description
            url: Target URL for testing
            output_path: Path to save generated test
            additional_context: Optional context hints

        Returns:
            Generated test with metadata

        Example:
            generated = generator.generate_test_file(
                feature="User can login with Google OAuth",
                url="https://myapp.dev/login",
                output_path=Path("tests/e2e/test_google_login.py")
            )

        """
        # Generate test
        generated = self.generate_test(feature, url, additional_context)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write test file
        output_path.write_text(generated.test_code, encoding="utf-8")

        self.logger.info(f"Test written to: {output_path}")

        return generated

    def _generate_test_name(self, feature_name: str) -> str:
        """Generate valid Python test function name from feature name."""
        # Convert to lowercase, replace spaces/special chars with underscores
        name = feature_name.lower()
        name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)

        # Remove consecutive underscores
        while "__" in name:
            name = name.replace("__", "_")

        # Strip leading/trailing underscores
        name = name.strip("_")

        return name

    def _generate_page_object_class_name(self, feature_name: str) -> str:
        """Generate page object class name from feature name."""
        # Split on spaces and capitalize each word
        words = feature_name.split()

        # Capitalize first letter of each word
        class_name = "".join(word.capitalize() for word in words)

        # Ensure ends with "Page"
        if not class_name.endswith("Page"):
            class_name += "Page"

        return class_name

    def _render_test_template(
        self,
        scenario: TestScenario,
        test_name: str,
        page_object_class: str,
        page_object_name: str,
    ) -> str:
        """Render Jinja2 test template with scenario data."""
        template = self.jinja_env.get_template("test_template.py.jinja2")

        test_code = template.render(
            scenario=scenario,
            test_name=test_name,
            page_object_class=page_object_class,
            page_object_name=page_object_name,
            generated_at=datetime.now().isoformat(),
        )

        return test_code

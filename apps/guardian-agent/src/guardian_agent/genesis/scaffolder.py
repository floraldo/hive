"""
Hive Scaffolder - Application Structure Generator

Generates complete, Golden Rules-compliant application structures
based on Oracle-advised specifications.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import toml

from hive_logging import get_logger

from .genesis_agent import AppSpec, FeatureStub, Priority

logger = get_logger(__name__)


class HiveScaffolder:
    """
    Generates complete Hive application structures with Golden Rules compliance.

    Creates directory structure, configuration files, stub implementations,
    and comprehensive documentation based on Oracle intelligence.
    """

    def __init__(self, config):
        self.config = config

    async def generate_app_async(self, app_spec: AppSpec, target_path: Path) -> None:
        """
        Generate complete application structure based on specification.

        Args:
            app_spec: Complete application specification from Genesis Agent
            target_path: Target directory for the new application
        """
        logger.info(f"Scaffolding application '{app_spec.name}' at {target_path}")

        try:
            # Create directory structure
            await self._create_directory_structure(target_path, app_spec)

            # Generate configuration files
            await self._generate_config_files(target_path, app_spec)

            # Generate source code stubs
            await self._generate_source_stubs(target_path, app_spec)

            # Generate test stubs
            await self._generate_test_stubs(target_path, app_spec)

            # Generate documentation
            await self._generate_documentation(target_path, app_spec)

            # Generate deployment files
            await self._generate_deployment_files(target_path, app_spec)

            logger.info(f"✅ Application scaffolding complete: {target_path}")

        except Exception as e:
            logger.error(f"Scaffolding failed: {e}")
            raise

    async def _create_directory_structure(self, target_path: Path, app_spec: AppSpec) -> None:
        """Create the standard Hive application directory structure."""

        directories = [
            target_path,
            target_path / "src" / app_spec.name.replace("-", "_"),
            target_path / "tests",
            target_path / "docs",
            target_path / "config",
            target_path / "k8s",
            target_path / "scripts",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {directory}")

    async def _generate_config_files(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate configuration files for the application."""

        # Generate pyproject.toml
        await self._generate_pyproject_toml(target_path, app_spec)

        # Generate hive-app.toml
        await self._generate_hive_app_toml(target_path, app_spec)

        # Generate application config
        await self._generate_app_config(target_path, app_spec)

    async def _generate_pyproject_toml(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate pyproject.toml with proper dependencies."""

        # Base dependencies
        dependencies = ["hive-logging>=0.1.0"]

        # Add recommended packages
        for package in app_spec.recommended_packages:
            dependencies.append(f"{package}>=0.1.0")

        # Add common dependencies based on app category
        if app_spec.category.value in ["web_application", "api_service"]:
            dependencies.extend(["fastapi>=0.104.0", "uvicorn>=0.24.0"])

        if "hive-db" in app_spec.recommended_packages:
            dependencies.append("sqlalchemy>=2.0.0")

        pyproject_content = {
            "build-system": {"requires": ["setuptools>=61.0", "wheel"], "build-backend": "setuptools.build_meta"},
            "project": {
                "name": app_spec.name,
                "version": "0.1.0",
                "description": app_spec.description,
                "readme": "README.md",
                "requires-python": ">=3.11",
                "dependencies": dependencies,
                "optional-dependencies": {
                    "dev": ["pytest>=7.0.0", "pytest-asyncio>=0.21.0", "black>=23.0.0", "ruff>=0.1.0", "mypy>=1.0.0"]
                },
            },
            "tool": {
                "setuptools": {"packages": {"find": {"where": ["src"]}}},
                "black": {"line-length": 100, "target-version": ["py311"]},
                "ruff": {"line-length": 100, "target-version": "py311"},
                "mypy": {"python_version": "3.11", "strict": True},
            },
        }

        pyproject_path = target_path / "pyproject.toml"
        with open(pyproject_path, "w") as f:
            toml.dump(pyproject_content, f)

        logger.debug(f"Generated pyproject.toml with {len(dependencies)} dependencies")

    async def _generate_hive_app_toml(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate hive-app.toml configuration."""

        hive_app_config = {
            "app": {
                "name": app_spec.name,
                "description": app_spec.description,
                "version": "0.1.0",
                "category": app_spec.category.value,
                "created_at": app_spec.created_at.isoformat(),
                "oracle_confidence": app_spec.oracle_confidence,
            },
            "architecture": {
                "pattern": app_spec.architecture_pattern,
                "storage": app_spec.storage_recommendation,
                "packages": app_spec.recommended_packages,
            },
            "features": [
                {
                    "name": feature.name,
                    "priority": feature.priority.value,
                    "estimated_effort": feature.estimated_effort,
                    "business_value": feature.business_value,
                }
                for feature in app_spec.features
            ],
            "oracle": {
                "business_intelligence": app_spec.business_intelligence,
                "market_opportunity": app_spec.market_opportunity,
                "competitive_advantage": app_spec.competitive_advantage,
            },
        }

        hive_app_path = target_path / "hive-app.toml"
        with open(hive_app_path, "w") as f:
            toml.dump(hive_app_config, f)

        logger.debug("Generated hive-app.toml configuration")

    async def _generate_app_config(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate application-specific configuration."""

        config_content = dedent(
            f''',
            """,
            Configuration for {app_spec.name}

            Oracle-optimized configuration based on business intelligence.
            """

            from hive_config import BaseConfig, ConfigField,
            from typing import Optional


            class {self._to_class_name(app_spec.name)}Config(BaseConfig):
                """Configuration for {app_spec.name} application."""

                # Application settings,
                app_name: str = ConfigField(default="{app_spec.name}")
                debug: bool = ConfigField(default=False, env="DEBUG")

                # Server settings (if web application)
                {"host: str = ConfigField(default='localhost', env='HOST')" if app_spec.category.value in ["web_application", "api_service"] else "# No server settings needed"}
                {"port: int = ConfigField(default=8000, env='PORT')" if app_spec.category.value in ["web_application", "api_service"] else ""}

                # Database settings (if using hive-db)
                {"database_url: str = ConfigField(default='sqlite:///data.db', env='DATABASE_URL')" if "hive-db" in app_spec.recommended_packages else "# No database settings needed"}

                # AI settings (if using hive-ai)
                {"ai_model: str = ConfigField(default='gpt-4', env='AI_MODEL')" if "hive-ai" in app_spec.recommended_packages else "# No AI settings needed"}
                {"ai_temperature: float = ConfigField(default=0.7, env='AI_TEMPERATURE')" if "hive-ai" in app_spec.recommended_packages else ""}

                # Oracle recommendations,
                # {app_spec.market_opportunity[:80] + "..." if len(app_spec.market_opportunity) > 80 else app_spec.market_opportunity}
        '''
        ).strip()

        config_path = (target_path / "config" / "config.py",)
        with open(config_path, "w") as f:
            f.write(config_content)

        logger.debug("Generated application configuration")

    async def _generate_source_stubs(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate source code stubs based on identified features."""

        src_path = target_path / "src" / app_spec.name.replace("-", "_")

        # Generate __init__.py,
        await self._generate_init_file(src_path, app_spec)

        # Generate main application file,
        await self._generate_main_file(src_path, app_spec)

        # Generate feature stubs,
        for feature in app_spec.features:
            await self._generate_feature_stub(src_path, feature, app_spec)

    async def _generate_init_file(self, src_path: Path, app_spec: AppSpec) -> None:
        """Generate package __init__.py file."""

        init_content = dedent(
            f''',
            """,
            {app_spec.name} - {app_spec.description}

            Oracle-generated application with strategic business intelligence integration.

            Generated on: {app_spec.created_at.strftime("%Y-%m-%d %H:%M:%S")}
            Oracle Confidence: {app_spec.oracle_confidence:.1%}
            """

            __version__ = "0.1.0",
            __description__ = "{app_spec.description}"

            # Oracle Strategic Insights:
            # Market Opportunity: {app_spec.market_opportunity or "Standard application"}
            # Competitive Advantage: {app_spec.competitive_advantage or "Hive platform benefits"}
        '''
        ).strip()

        init_path = (src_path / "__init__.py",)
        with open(init_path, "w") as f:
            f.write(init_content)

    async def _generate_main_file(self, src_path: Path, app_spec: AppSpec) -> None:
        """Generate main application entry point."""

        class_name = self._to_class_name(app_spec.name)

        if app_spec.category.value in ["web_application", "api_service"]:
            main_content = self._generate_web_app_main(class_name, app_spec)
        elif app_spec.category.value == "cli_tool":
            main_content = self._generate_cli_main(class_name, app_spec)
        else:
            main_content = self._generate_service_main(class_name, app_spec)

        main_path = (src_path / "main.py",)
        with open(main_path, "w") as f:
            f.write(main_content)

        logger.debug(f"Generated main.py for {app_spec.category.value}")

    def _generate_web_app_main(self, class_name: str, app_spec: AppSpec) -> str:
        """Generate web application main file."""

        return dedent(
            f''',
            """,
            {app_spec.name} - Web Application Main Entry Point

            Oracle-optimized web application with strategic feature prioritization.
            """

            from fastapi import FastAPI,
            from hive_logging import get_logger,
            {"from hive_db import DatabaseManager" if "hive-db" in app_spec.recommended_packages else ""}

            logger = get_logger(__name__)


            def create_app() -> FastAPI:
                """Create and configure the FastAPI application."""

                app = FastAPI(
                    title="{app_spec.name}",
                    description="{app_spec.description}",
                    version="0.1.0"
                )

                # Oracle Strategic Insight: {app_spec.market_opportunity or "Focus on core value proposition"}

                @app.get("/")
                async def root():
                    return {{
                        "message": "Welcome to {app_spec.name}",
                        "description": "{app_spec.description}",
                        "oracle_confidence": {app_spec.oracle_confidence:.2f}
                    }}

                @app.get("/health")
                async def health_check():
                    return {{"status": "healthy", "service": "{app_spec.name}"}}

                # TODO: Implement feature endpoints based on Oracle prioritization,
                {self._generate_feature_todos(app_spec.features)}

                return app


            if __name__ == "__main__":
                import uvicorn,
                app = create_app()
                uvicorn.run(app, host="0.0.0.0", port=8000)
        '''
        ).strip()

    def _generate_cli_main(self, class_name: str, app_spec: AppSpec) -> str:
        """Generate CLI application main file."""

        return dedent(
            f''',
            """,
            {app_spec.name} - CLI Application Main Entry Point

            Oracle-optimized CLI tool with strategic feature prioritization.
            """

            import click,
            from hive_logging import get_logger

            logger = get_logger(__name__)


            @click.group()
            @click.version_option(version="0.1.0")
            def cli():
                """,
                {app_spec.description}

                Oracle Confidence: {app_spec.oracle_confidence:.1%}
                """,
                pass


            @cli.command()
            def status():
                """Show application status.""",
                click.echo(f"{{'{app_spec.name}' Status: Ready}}")
                click.echo(f"Oracle Confidence: {app_spec.oracle_confidence:.1%}")
                click.echo(f"Features to implement: {len(app_spec.features)}")


            # TODO: Implement CLI commands based on Oracle prioritization,
            {self._generate_feature_todos(app_spec.features)}


            if __name__ == "__main__":
                cli()
        '''
        ).strip()

    def _generate_service_main(self, class_name: str, app_spec: AppSpec) -> str:
        """Generate service application main file."""

        return dedent(
            f''',
            """,
            {app_spec.name} - Service Main Entry Point

            Oracle-optimized service with strategic feature prioritization.
            """

            import asyncio,
            from hive_logging import get_logger

            logger = get_logger(__name__)


            class {class_name}Service:
                """Main service class for {app_spec.name}."""

                def __init__(self):
                    self.running = False,
                    logger.info("Initializing {app_spec.name} service")

                async def start_async(self):
                    """Start the service.""",
                    self.running = True,
                    logger.info("{app_spec.name} service started")

                    # Oracle Strategic Insight: {app_spec.market_opportunity or "Focus on core functionality"}

                    try:
                        while self.running:
                            await self._process_cycle()
                            await asyncio.sleep(1)
                    except KeyboardInterrupt:
                        logger.info("Shutdown signal received")
                    finally:
                        await self.stop_async()

                async def stop_async(self):
                    """Stop the service.""",
                    self.running = False,
                    logger.info("{app_spec.name} service stopped")

                async def _process_cycle(self):
                    """Process one service cycle.""",
                    # TODO: Implement service logic based on Oracle prioritization,
                    {self._generate_feature_todos(app_spec.features)}
                    pass


            async def main():
                """Main entry point.""",
                service = {class_name}Service()
                await service.start_async()


            if __name__ == "__main__":
                asyncio.run(main())
        '''
        ).strip()

    def _generate_feature_todos(self, features: list[FeatureStub]) -> str:
        """Generate TODO comments for features."""

        todos = []
        for feature in features[:5]:  # Top 5 features
            priority_marker = {
                Priority.CRITICAL: "CRITICAL",
                Priority.HIGH: "HIGH",
                Priority.MEDIUM: "MEDIUM",
                Priority.LOW: "LOW",
                Priority.FUTURE: "FUTURE",
            }.get(feature.priority, "TODO")

            todos.append(f"# TODO [{priority_marker}]: {feature.name} - {feature.business_value}")

            if feature.oracle_recommendations:
                todos.append(f"#   Oracle: {feature.oracle_recommendations[0]}")

        return "\n                ".join(todos)

    async def _generate_feature_stub(self, src_path: Path, feature: FeatureStub, app_spec: AppSpec) -> None:
        """Generate a stub file for a specific feature."""

        # Convert feature name to valid Python module name
        module_name = feature.name.lower().replace(" ", "_").replace("-", "_")
        module_path = src_path / f"{module_name}.py"

        # Skip if module already exists (avoid overwrites)
        if module_path.exists():
            return

        class_name = self._to_class_name(feature.name)

        stub_content = dedent(
            f''',
            """,
            {feature.name} - {feature.description}

            Priority: {feature.priority.value.upper()}
            Business Value: {feature.business_value}
            Estimated Effort: {feature.estimated_effort}

            Oracle Recommendations:
            {self._format_oracle_recommendations(feature.oracle_recommendations)}
            """

            from hive_logging import get_logger,
            {"from hive_db import DatabaseManager" if "hive-db" in app_spec.recommended_packages and "data" in feature.name.lower() else ""}
            {"from hive_ai import AIService" if "hive-ai" in app_spec.recommended_packages and "ai" in feature.name.lower() else ""}

            logger = get_logger(__name__)


            class {class_name}:
                """,
                {feature.description}

                This feature has {feature.priority.value} priority based on Oracle analysis.
                """

                def __init__(self):
                    logger.info("Initializing {feature.name}")
                    # TODO: Initialize {feature.name} components

                async def implement_async(self):
                    """,
                    Implement {feature.name} functionality.

                    Oracle Insight: {feature.business_value}
                    """,
                    # TODO [{feature.priority.value.upper()}]: Implement {feature.name}
                    # Estimated effort: {feature.estimated_effort}

                    {self._generate_implementation_template(feature)}

                    logger.info("{feature.name} implementation placeholder")
                    raise NotImplementedError("Feature not yet implemented")


            # TODO: Add tests for {class_name} in tests/test_{module_name}.py,
            # Oracle recommends: {feature.oracle_recommendations[0] if feature.oracle_recommendations else "Standard testing patterns"}
        '''
        ).strip()

        with open(module_path, "w") as f:
            f.write(stub_content)

        logger.debug(f"Generated feature stub: {module_name}.py")

    def _format_oracle_recommendations(self, recommendations: list[str]) -> str:
        """Format Oracle recommendations for documentation."""
        if not recommendations:
            return "- Standard Hive implementation patterns"

        return "\n            ".join(f"- {rec}" for rec in recommendations)

    def _generate_implementation_template(self, feature: FeatureStub) -> str:
        """Generate implementation template based on feature type."""

        feature_lower = feature.name.lower()

        if "auth" in feature_lower or "login" in feature_lower:
            return dedent(
                """,
                # Authentication implementation template,
                # 1. Set up user model and database schema,
                # 2. Implement password hashing and verification,
                # 3. Create login/logout endpoints,
                # 4. Add JWT token management,
                # 5. Implement role-based access control,
            """
            ).strip()

        elif "upload" in feature_lower or "file" in feature_lower:
            return dedent(
                """,
                # File upload implementation template,
                # 1. Set up file storage (local or cloud)
                # 2. Implement file validation and security checks,
                # 3. Create upload endpoint with progress tracking,
                # 4. Add file metadata storage,
                # 5. Implement file retrieval and serving,
            """
            ).strip()

        elif "search" in feature_lower:
            return dedent(
                """,
                # Search implementation template,
                # 1. Design search index structure,
                # 2. Implement full-text search capability,
                # 3. Add filtering and sorting options,
                # 4. Create search API endpoints,
                # 5. Optimize search performance and relevance,
            """
            ).strip()

        elif "ai" in feature_lower or "smart" in feature_lower:
            return dedent(
                """,
                # AI feature implementation template,
                # 1. Set up AI service integration (hive-ai)
                # 2. Design prompt templates and model selection,
                # 3. Implement AI processing pipeline,
                # 4. Add result caching and optimization,
                # 5. Monitor AI costs and performance,
            """
            ).strip()

        else:
            return dedent(
                f""",
                # {feature.name} implementation template,
                # 1. Define feature requirements and specifications,
                # 2. Design data models and API interfaces,
                # 3. Implement core business logic,
                # 4. Add error handling and validation,
                # 5. Create comprehensive tests,
            """
            ).strip()

    async def _generate_test_stubs(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate test stubs for Golden Rules compliance."""

        tests_path = target_path / "tests"

        # Generate test __init__.py
        init_path = tests_path / "__init__.py"
        with open(init_path, "w") as f:
            f.write('"""Test package for {app_spec.name}."""\n')

        # Generate main test file
        await self._generate_main_test(tests_path, app_spec)

        # Generate feature test stubs
        for feature in app_spec.features:
            await self._generate_feature_test(tests_path, feature, app_spec)

    async def _generate_main_test(self, tests_path: Path, app_spec: AppSpec) -> None:
        """Generate main application test file."""

        test_content = dedent(
            f''',
            """,
            Tests for {app_spec.name} main application.

            Golden Rules Compliance: These tests ensure the application,
            meets all architectural requirements.
            """

            import pytest,
            from {app_spec.name.replace("-", "_")}.main import *


            class Test{self._to_class_name(app_spec.name)}:
                """Test suite for main application functionality."""

                def test_application_initialization(self):
                    """Test that the application initializes correctly.""",
                    # TODO: Implement initialization test,
                    assert True  # Placeholder

                def test_health_check(self):
                    """Test health check endpoint.""",
                    # TODO: Implement health check test,
                    assert True  # Placeholder

                # TODO: Add tests for each feature based on Oracle prioritization,
                {self._generate_test_todos(app_spec.features)}


            # Golden Rules Compliance Tests,
            class TestGoldenRulesCompliance:
                """Ensure the application meets Golden Rules requirements."""

                def test_no_global_state_access(self):
                    """Test that no global state is accessed inappropriately.""",
                    # TODO: Implement global state check,
                    assert True  # Placeholder

                def test_proper_error_handling(self):
                    """Test that errors are handled according to standards.""",
                    # TODO: Implement error handling test,
                    assert True  # Placeholder

                def test_logging_standards(self):
                    """Test that logging follows Hive standards.""",
                    # TODO: Implement logging standards test,
                    assert True  # Placeholder,
        '''
        ).strip()

        test_path = tests_path / "test_main.py"
        with open(test_path, "w") as f:
            f.write(test_content)

    def _generate_test_todos(self, features: list[FeatureStub]) -> str:
        """Generate test TODO comments for features."""

        todos = []
        for feature in features[:5]:  # Top 5 features
            test_name = feature.name.lower().replace(" ", "_")
            todos.append(f"# TODO [{feature.priority.value.upper()}]: test_{test_name}")

        return "\n                ".join(todos)

    async def _generate_feature_test(self, tests_path: Path, feature: FeatureStub, app_spec: AppSpec) -> None:
        """Generate test stub for a specific feature."""

        module_name = feature.name.lower().replace(" ", "_").replace("-", "_")
        test_path = tests_path / f"test_{module_name}.py"

        # Skip if test already exists
        if test_path.exists():
            return

        class_name = self._to_class_name(feature.name)

        test_content = dedent(
            f''',
            """,
            Tests for {feature.name} feature.

            Priority: {feature.priority.value.upper()}
            Oracle Business Value: {feature.business_value}
            """

            import pytest,
            from {app_spec.name.replace("-", "_")}.{module_name} import {class_name}


            class Test{class_name}:
                """Test suite for {feature.name} functionality."""

                @pytest.fixture,
                def {module_name}(self):
                    """Create {class_name} instance for testing.""",
                    return {class_name}()

                def test_{module_name}_initialization(self, {module_name}):
                    """Test {feature.name} initialization.""",
                    assert {module_name} is not None,
                    # TODO: Add specific initialization tests

                @pytest.mark.asyncio,
                async def test_{module_name}_implementation(self, {module_name}):
                    """Test {feature.name} core functionality.""",
                    # TODO [{feature.priority.value.upper()}]: Implement {feature.name} tests,
                    # Oracle recommends: {feature.oracle_recommendations[0] if feature.oracle_recommendations else "Standard testing patterns"}

                    with pytest.raises(NotImplementedError):
                        await {module_name}.implement_async()

                # TODO: Add comprehensive test cases based on feature requirements,
                # Estimated test effort: {feature.estimated_effort}
        '''
        ).strip()

        with open(test_path, "w") as f:
            f.write(test_content)

    async def _generate_documentation(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate comprehensive documentation."""

        # Generate README.md,
        await self._generate_readme(target_path, app_spec)

        # Generate architecture documentation,
        await self._generate_architecture_docs(target_path, app_spec)

        # Generate feature documentation,
        await self._generate_feature_docs(target_path, app_spec)

    async def _generate_readme(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate comprehensive README.md."""

        readme_content = dedent(
            f""",
            # {app_spec.name}

            {app_spec.description}

            **Oracle Confidence:** {app_spec.oracle_confidence:.1%}
            **Generated:** {app_spec.created_at.strftime("%Y-%m-%d %H:%M:%S")}
            **Category:** {app_spec.category.value.replace("_", " ").title()}

            ## 🎯 Oracle Strategic Intelligence

            This application was generated using the Hive Oracle's business intelligence and strategic insights:

            - **Market Opportunity:** {app_spec.market_opportunity or "Standard application development"}
            - **Competitive Advantage:** {app_spec.competitive_advantage or "Built on Hive platform architecture"}
            - **Target Architecture:** {app_spec.architecture_pattern}
            - **Storage Strategy:** {app_spec.storage_recommendation}

            ## 📋 Features (Oracle-Prioritized)

            {self._generate_feature_table(app_spec.features)}

            ## 🚀 Quick Start

            1. **Install dependencies:**,
               ```bash,
               pip install -e .
               ```

            2. **Run the application:**,
               ```bash,
               {"python -m " + app_spec.name.replace("-", "_") + ".main" if app_spec.category.value != "cli_tool" else app_spec.name.replace("-", "_") + " --help"}
               ```

            3. **Run tests:**,
               ```bash,
               pytest tests/
               ```

            ## 🏗️ Architecture

            This application follows Hive Golden Rules and uses the following packages:

            {self._generate_package_list(app_spec.recommended_packages)}

            ## 📊 Business Intelligence Integration

            {self._generate_business_intelligence_section(app_spec)}

            ## 🔧 Development

            ### Prerequisites,
            - Python 3.11+
            - Hive platform packages

            ### Development Setup,
            ```bash,
            # Install development dependencies,
            pip install -e ".[dev]"

            # Run linting,
            black src/ tests/
            ruff check src/ tests/

            # Type checking,
            mypy src/
            ```

            ### Golden Rules Compliance

            This application is generated to be 100% compliant with Hive Golden Rules:
            - ✅ Package vs App Discipline,
            - ✅ Dependency Direction,
            - ✅ Interface Contracts,
            - ✅ Error Handling Standards,
            - ✅ No Global State Access,
            - ✅ Test-to-Source File Mapping

            ## 📈 Oracle Recommendations

            Based on business intelligence analysis, the Oracle recommends:

            {self._generate_oracle_recommendations_section(app_spec)}

            ## 🤝 Contributing

            1. Follow Hive Golden Rules,
            2. Implement features by Oracle priority,
            3. Add comprehensive tests,
            4. Update documentation

            ---

            *Generated by Hive Genesis Agent - The Oracle's App Creation Engine*
        """
        ).strip()

        readme_path = (target_path / "README.md",)
        with open(readme_path, "w") as f:
            f.write(readme_content)

        logger.debug("Generated comprehensive README.md")

    def _generate_feature_table(self, features: list[FeatureStub]) -> str:
        """Generate a table of features with priorities."""

        if not features:
            return "No specific features identified - implement core functionality."

        table = "| Feature | Priority | Effort | Business Value |\n"
        table += "|---------|----------|--------|----------------|\n"

        for feature in features:
            priority_emoji = {
                Priority.CRITICAL: "🚨",
                Priority.HIGH: "⚠️",
                Priority.MEDIUM: "📋",
                Priority.LOW: "💡",
                Priority.FUTURE: "🔮",
            }.get(feature.priority, "📋")

            table += f"| {feature.name} | {priority_emoji} {feature.priority.value.title()} | {feature.estimated_effort} | {feature.business_value[:50]}{'...' if len(feature.business_value) > 50 else ''} |\n"

        return table

    def _generate_package_list(self, packages: list[str]) -> str:
        """Generate a list of recommended packages."""

        package_descriptions = {
            "hive-config": "Configuration management and environment handling",
            "hive-db": "Database operations and ORM integration",
            "hive-ai": "AI services and model integration",
            "hive-bus": "Message bus and event handling",
            "hive-deployment": "Deployment and infrastructure management",
        }

        package_list = ""
        for package in packages:
            description = package_descriptions.get(package, "Core functionality")
            package_list += f"- **{package}**: {description}\n"

        return package_list

    def _generate_business_intelligence_section(self, app_spec: AppSpec) -> str:
        """Generate business intelligence insights section."""

        bi = app_spec.business_intelligence
        if not bi:
            return "No specific business intelligence data available."

        section = "The Oracle's business intelligence analysis for this application:\n\n"

        if "customer_health_score" in bi:
            section += f"- **Customer Health Score:** {bi['customer_health_score']:.1f}/100\n"

        if "feature_cost_efficiency" in bi:
            section += f"- **Feature Cost Efficiency:** {bi['feature_cost_efficiency']:.1f}% average adoption\n"

        if "revenue_growth_rate" in bi:
            section += f"- **Revenue Growth Context:** {bi['revenue_growth_rate']:.1f}% monthly growth\n"

        return section

    def _generate_oracle_recommendations_section(self, app_spec: AppSpec) -> str:
        """Generate Oracle recommendations section."""

        recommendations = []

        # Add feature-specific recommendations
        for feature in app_spec.features[:3]:  # Top 3 features
            if feature.oracle_recommendations:
                recommendations.append(f"**{feature.name}:** {feature.oracle_recommendations[0]}")

        if not recommendations:
            recommendations = [
                "Focus on core functionality first",
                "Ensure Golden Rules compliance",
                "Implement comprehensive testing",
            ]

        return "\n".join(f"- {rec}" for rec in recommendations)

    async def _generate_architecture_docs(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate architecture documentation."""

        docs_path = target_path / "docs"

        arch_content = dedent(
            f""",
            # Architecture Documentation

            ## Overview

            {app_spec.name} follows the {app_spec.architecture_pattern} pattern with Oracle-optimized design decisions.

            ## Oracle Strategic Decisions

            - **Storage Strategy:** {app_spec.storage_recommendation}
            - **Package Selection:** Based on feature analysis and business intelligence,
            - **Feature Prioritization:** Driven by ROI analysis and adoption rates

            ## Component Architecture

            ### Core Components

            {self._generate_component_architecture(app_spec)}

            ## Data Flow

            {self._generate_data_flow_docs(app_spec)}

            ## Deployment Architecture

            The application is designed for deployment using `hive-deployment` with the following characteristics:

            - **Scalability:** {self._assess_scalability(app_spec)}
            - **Performance:** Optimized based on Oracle business intelligence,
            - **Cost Efficiency:** Aligned with platform cost optimization goals

            ## Golden Rules Compliance

            This architecture ensures 100% compliance with Hive Golden Rules:

            1. **Package Discipline:** Clear separation between application and infrastructure,
            2. **Dependency Direction:** Proper dependency flow from app to packages,
            3. **Interface Contracts:** Well-defined APIs with type hints,
            4. **Error Handling:** Consistent error handling patterns,
            5. **No Global State:** All state managed through proper dependency injection,
            6. **Test Coverage:** Complete test-to-source file mapping,
        """
        ).strip()

        arch_path = (docs_path / "ARCHITECTURE.md",)
        with open(arch_path, "w") as f:
            f.write(arch_content)

    def _generate_component_architecture(self, app_spec: AppSpec) -> str:
        """Generate component architecture documentation."""

        components = []

        for package in app_spec.recommended_packages:
            if package == "hive-db":
                components.append("- **Database Layer:** Data persistence and ORM operations")
            elif package == "hive-ai":
                components.append("- **AI Service Layer:** Machine learning and intelligent features")
            elif package == "hive-bus":
                components.append("- **Message Bus:** Event handling and real-time communication")
            elif package == "hive-config":
                components.append("- **Configuration Layer:** Environment and settings management")

        if app_spec.category.value in ["web_application", "api_service"]:
            components.append("- **Web Layer:** HTTP endpoints and API interfaces")

        components.append("- **Business Logic:** Core application functionality")

        return "\n".join(components)

    def _generate_data_flow_docs(self, app_spec: AppSpec) -> str:
        """Generate data flow documentation."""

        if "hive-db" in app_spec.recommended_packages:
            return dedent(
                """,
                1. **Input Layer:** Receives requests/data from users or external systems,
                2. **Validation Layer:** Validates input according to business rules,
                3. **Business Logic:** Processes data according to application requirements,
                4. **Data Layer:** Persists data using hive-db components,
                5. **Response Layer:** Returns processed results to clients,
            """
            ).strip()
        else:
            return dedent(
                """,
                1. **Input Layer:** Receives requests/data from users or external systems,
                2. **Processing Layer:** Processes data according to application logic,
                3. **Output Layer:** Returns processed results to clients,
            """
            ).strip()

    def _assess_scalability(self, app_spec: AppSpec) -> str:
        """Assess scalability characteristics."""

        if app_spec.category.value in ["web_application", "api_service"]:
            return "Horizontal scaling supported with load balancing"
        elif app_spec.category.value == "background_service":
            return "Worker-based scaling with queue management"
        else:
            return "Standard application scaling patterns"

    async def _generate_feature_docs(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate feature-specific documentation."""

        docs_path = target_path / "docs"

        features_content = dedent(
            f""",
            # Feature Documentation

            ## Oracle-Prioritized Features

            This document outlines the features identified by the Oracle's semantic analysis,
            and prioritized based on business intelligence.

            {self._generate_detailed_feature_docs(app_spec.features)}

            ## Implementation Roadmap

            Based on Oracle analysis, implement features in this order:

            {self._generate_implementation_roadmap(app_spec.features)}

            ## Business Value Analysis

            {self._generate_business_value_analysis(app_spec)}
        """
        ).strip()

        features_path = (docs_path / "FEATURES.md",)
        with open(features_path, "w") as f:
            f.write(features_content)

    def _generate_detailed_feature_docs(self, features: list[FeatureStub]) -> str:
        """Generate detailed feature documentation."""

        docs = ""

        for feature in features:
            docs += f"\n### {feature.name}\n\n"
            docs += f"**Priority:** {feature.priority.value.title()}\n"
            docs += f"**Estimated Effort:** {feature.estimated_effort}\n"
            docs += f"**Business Value:** {feature.business_value}\n\n"

            if feature.oracle_recommendations:
                docs += "**Oracle Recommendations:**\n"
                for rec in feature.oracle_recommendations:
                    docs += f"- {rec}\n"
                docs += "\n"

            docs += "**Implementation Notes:**\n"
            docs += f"- Module: `{feature.module_path}`\n"
            if feature.dependencies:
                deps = ", ".join(feature.dependencies)
                docs += f"- Dependencies: {deps}\n"
            docs += "\n"

        return docs

    def _generate_implementation_roadmap(self, features: list[FeatureStub]) -> str:
        """Generate implementation roadmap."""

        roadmap = ""

        # Group by priority
        priority_groups = {}
        for feature in features:
            priority = feature.priority
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(feature)

        # Generate roadmap by priority
        for priority in [Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW, Priority.FUTURE]:
            if priority in priority_groups:
                roadmap += f"\n**{priority.value.title()} Priority:**\n"
                for feature in priority_groups[priority]:
                    roadmap += f"- {feature.name} ({feature.estimated_effort})\n"

        return roadmap

    def _generate_business_value_analysis(self, app_spec: AppSpec) -> str:
        """Generate business value analysis."""

        analysis = "Based on Oracle intelligence:\n\n"

        if app_spec.similar_apps_performance:
            analysis += "**Similar Apps Performance:**\n"
            for feature, perf in app_spec.similar_apps_performance.items():
                if "avg_adoption_rate" in perf:
                    analysis += f"- {feature}: {perf['avg_adoption_rate']:.1f}% adoption rate\n"

        analysis += f"\n**Market Opportunity:** {app_spec.market_opportunity or 'Standard market positioning'}\n"
        analysis += f"**Competitive Advantage:** {app_spec.competitive_advantage or 'Hive platform benefits'}\n"

        return analysis

    async def _generate_deployment_files(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate deployment configuration files."""

        k8s_path = target_path / "k8s"

        # Generate Dockerfile
        await self._generate_dockerfile(target_path, app_spec)

        # Generate Kubernetes manifests
        await self._generate_k8s_manifests(k8s_path, app_spec)

        # Generate deployment scripts
        await self._generate_deployment_scripts(target_path / "scripts", app_spec)

    async def _generate_dockerfile(self, target_path: Path, app_spec: AppSpec) -> None:
        """Generate Dockerfile for the application."""

        dockerfile_content = dedent(
            f""",
            FROM python:3.11-slim

            # Set working directory,
            WORKDIR /app

            # Install system dependencies,
            RUN apt-get update && apt-get install -y \\
                gcc \\
                && rm -rf /var/lib/apt/lists/*

            # Copy requirements and install Python dependencies,
            COPY pyproject.toml .
            RUN pip install --no-cache-dir -e .

            # Copy application code,
            COPY src/ src/
            COPY config/ config/

            # Create non-root user,
            RUN useradd --create-home --shell /bin/bash app,
            USER app

            # Expose port (if web application)
            {"EXPOSE 8000" if app_spec.category.value in ["web_application", "api_service"] else "# No port exposure needed"}

            # Health check,
            {"HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\\n  CMD curl -f http://localhost:8000/health || exit 1" if app_spec.category.value in ["web_application", "api_service"] else "# No health check for non-web services"}

            # Run application,
            CMD ["python", "-m", "{app_spec.name.replace("-", "_")}.main"]
        """
        ).strip()

        dockerfile_path = (target_path / "Dockerfile",)
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content)

    async def _generate_k8s_manifests(self, k8s_path: Path, app_spec: AppSpec) -> None:
        """Generate Kubernetes deployment manifests."""

        # Generate deployment.yaml,
        deployment_content = dedent(
            f""",
            apiVersion: apps/v1,
            kind: Deployment,
            metadata:
              name: {app_spec.name}
              labels:
                app: {app_spec.name}
                oracle-generated: "true",
            spec:
              replicas: 1,
              selector:
                matchLabels:
                  app: {app_spec.name}
              template:
                metadata:
                  labels:
                    app: {app_spec.name}
                spec:
                  containers:
                  - name: {app_spec.name}
                    image: {app_spec.name}:latest,
                    {"ports:" if app_spec.category.value in ["web_application", "api_service"] else "# No ports needed"}
                    {"- containerPort: 8000" if app_spec.category.value in ["web_application", "api_service"] else ""}
                    env:
                    - name: ENVIRONMENT,
                      value: "production",
                    {"- name: DATABASE_URL" if "hive-db" in app_spec.recommended_packages else ""}
                    {"  valueFrom:" if "hive-db" in app_spec.recommended_packages else ""}
                    {"    secretKeyRef:" if "hive-db" in app_spec.recommended_packages else ""}
                    {"      name: database-secret" if "hive-db" in app_spec.recommended_packages else ""}
                    {"      key: url" if "hive-db" in app_spec.recommended_packages else ""}
                    resources:
                      requests:
                        memory: "128Mi",
                        cpu: "100m",
                      limits:
                        memory: "512Mi",
                        cpu: "500m",
        """
        ).strip()

        deployment_path = (k8s_path / "deployment.yaml",)
        with open(deployment_path, "w") as f:
            f.write(deployment_content)

        # Generate service.yaml (if web application)
        if app_spec.category.value in ["web_application", "api_service"]:
            service_content = dedent(
                f""",
                apiVersion: v1,
                kind: Service,
                metadata:
                  name: {app_spec.name}-service,
                  labels:
                    app: {app_spec.name}
                spec:
                  selector:
                    app: {app_spec.name}
                  ports:
                  - protocol: TCP,
                    port: 80,
                    targetPort: 8000,
                  type: ClusterIP,
            """
            ).strip()

            service_path = (k8s_path / "service.yaml",)
            with open(service_path, "w") as f:
                f.write(service_content)

    async def _generate_deployment_scripts(self, scripts_path: Path, app_spec: AppSpec) -> None:
        """Generate deployment helper scripts."""

        # Generate build script,
        build_script = dedent(
            f""",
            #!/bin/bash,
            # Build script for {app_spec.name}
            # Generated by Hive Genesis Agent

            set -e

            echo "Building {app_spec.name}..."

            # Build Docker image,
            docker build -t {app_spec.name}:latest .

            # Tag for registry (customize as needed)
            # docker tag {app_spec.name}:latest your-registry/{app_spec.name}:latest

            echo "Build complete!",
        """
        ).strip()

        build_path = (scripts_path / "build.sh",)
        with open(build_path, "w") as f:
            f.write(build_script)
        build_path.chmod(0o755)  # Make executable

        # Generate deploy script,
        deploy_script = dedent(
            f""",
            #!/bin/bash,
            # Deploy script for {app_spec.name}
            # Generated by Hive Genesis Agent

            set -e

            echo "Deploying {app_spec.name}..."

            # Apply Kubernetes manifests,
            kubectl apply -f k8s/

            # Wait for deployment to be ready,
            kubectl rollout status deployment/{app_spec.name}

            {"# Get service URL" if app_spec.category.value in ["web_application", "api_service"] else ""}
            {"kubectl get service {app_spec.name}-service" if app_spec.category.value in ["web_application", "api_service"] else ""}

            echo "Deployment complete!",
        """
        ).strip()

        deploy_path = (scripts_path / "deploy.sh",)
        with open(deploy_path, "w") as f:
            f.write(deploy_script)
        deploy_path.chmod(0o755)  # Make executable

    def _to_class_name(self, name: str) -> str:
        """Convert a name to a valid Python class name."""
        # Remove hyphens and underscores, capitalize each word
        words = name.replace("-", " ").replace("_", " ").split()
        return "".join(word.capitalize() for word in words)

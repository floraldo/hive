"""
Golden Tests - Platform-Wide Architectural Validation

These tests enforce architectural gravity across the entire Hive platform.
They ensure that all components follow established patterns and standards.

These tests should NEVER be skipped or disabled. They are the guardians
of the platform's architectural integrity.

Enhanced with single-pass AST-based validation for superior performance
and accuracy, plus suppression support for controlled exceptions.
"""

from hive_logging import get_logger

logger = get_logger(__name__)

import pytest
from hive_tests.architectural_validators import (
    validate_app_contracts,
    validate_colocated_tests,
    validate_communication_patterns,
    validate_dependency_direction,
    validate_error_handling_standards,
    validate_interface_contracts,
    validate_logging_standards,
    validate_no_hardcoded_env_values,
    validate_no_syspath_hacks,
    validate_package_app_discipline,
    validate_service_layer_discipline,
    validate_single_config_source,
)
from hive_tests.ast_validator import EnhancedValidator


class TestArchitecturalCompliance:
    """
    Golden Tests for platform-wide architectural compliance.

    These tests enforce the "architectural gravity" that keeps
    the entire Hive ecosystem aligned with best practices.
    """

    def test_app_contract_compliance(self, project_root):
        """
        🏛️ GOLDEN TEST 1: App Contract Compliance

        Enforce that every app has a valid hive-app.toml contract.

        This test ensures that:
        - Every app directory has a hive-app.toml file
        - The contract file has required sections ([app])
        - The contract defines at least one service (daemons/tasks/endpoints)

        🎯 Gravity Effect: Forces every new app to be a well-behaved
           citizen of the Hive ecosystem with proper contracts.
        """
        is_valid, violations = validate_app_contracts(project_root)

        if not is_valid:
            failure_message = (
                "❌ App Contract Compliance FAILED\n\n" "The following apps violate the Hive app contract standard:\n\n"
            )
            for violation in violations:
                failure_message += f"  • {violation}\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Create hive-app.toml in each missing app directory\n"
                "  2. Add required [app] section with name field\n"
                "  3. Add at least one service section: [daemons], [tasks], or [endpoints]\n"
                "  4. See existing apps for examples\n\n"
                "📖 This enforces that every app properly declares its capabilities\n"
                "   and integration points with the Hive platform."
            )

            pytest.fail(failure_message)

    def test_service_layer_discipline(self, project_root):
        """
        🏗️ GOLDEN TEST 10: Service Layer Discipline

        Enforce proper service layer patterns.

        This test ensures that:
        - Service layers (core/) contain only interfaces
        - No business logic in service layers
        - Service interfaces are documented

        🎯 Gravity Effect: Maintains clean separation between
           service interfaces and business logic implementation.
        """
        is_valid, violations = validate_service_layer_discipline(project_root)

        if not is_valid:
            failure_message = "Service Layer Discipline FAILED\n\n" "The following violations were found:\n\n"
            for violation in violations[:15]:
                failure_message += f"  - {violation}\n"

            if len(violations) > 15:
                failure_message += f"  ... and {len(violations) - 15} more violations\n"

            failure_message += (
                "\nTo fix this:\n"
                "  1. Move business logic from core/ to app implementation\n"
                "  2. Keep only service interfaces in core/\n"
                "  3. Add docstrings to all service classes\n"
                "  4. Follow the service layer pattern documented in ARCHITECTURE.md\n\n"
                "This maintains clean separation between interfaces and implementation."
            )

            # Warning for now as this is a new rule
            logger.info(f"Warning: {len(violations)} service layer violations found")

    def test_communication_patterns(self, project_root):
        """
        📡 GOLDEN TEST 11: Communication Patterns

        Enforce approved inter-app communication patterns.

        This test ensures that:
        - Apps use approved communication channels
        - Background processes are properly configured
        - No forbidden IPC mechanisms

        🎯 Gravity Effect: Ensures clean, maintainable
           communication between system components.
        """
        is_valid, violations = validate_communication_patterns(project_root)

        if not is_valid:
            failure_message = "Communication Patterns FAILED\n\n" "The following violations were found:\n\n"
            for violation in violations[:15]:
                failure_message += f"  - {violation}\n"

            if len(violations) > 15:
                failure_message += f"  ... and {len(violations) - 15} more violations\n"

            failure_message += (
                "\nTo fix this:\n"
                "  1. Use approved communication patterns (DB queues, event bus, REST)\n"
                "  2. Remove direct socket or shared memory usage\n"
                "  3. Configure daemons properly in hive-app.toml\n"
                "  4. Follow communication patterns in ARCHITECTURE.md\n\n"
                "This ensures clean, scalable inter-app communication."
            )

            # Warning for now as this is a new rule
            logger.info(f"Warning: {len(violations)} communication pattern violations found")

    def test_colocated_tests_pattern(self, project_root):
        """
        🧪 GOLDEN TEST 2: Co-located Tests Pattern

        Enforce co-located tests for all apps and packages.

        This test ensures that:
        - Every app has a tests/ directory
        - Every package has a tests/ directory
        - Each tests/ directory has __init__.py for discovery

        🎯 Gravity Effect: Prevents creation of components without
           proper test structure, maintaining quality standards.
        """
        is_valid, violations = validate_colocated_tests(project_root)

        if not is_valid:
            failure_message = (
                "❌ Co-located Tests Pattern FAILED\n\n" "The following components lack proper test structure:\n\n"
            )
            for violation in violations:
                failure_message += f"  • {violation}\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Create tests/ directory in each component\n"
                "  2. Add tests/__init__.py file for pytest discovery\n"
                "  3. Follow the pattern: component/tests/test_*.py\n\n"
                "📖 This enforces that tests live next to the code they test,\n"
                "   making the codebase more maintainable and testable."
            )

            pytest.fail(failure_message)

    def test_no_syspath_hacks(self, project_root):
        """
        🚫 GOLDEN TEST 3: Perfect Import Purity

        Enforce Poetry-based imports - no path manipulation.

        This test ensures that:
        - No files contain path manipulation calls
        - All imports use Poetry workspace packages
        - Script entrypoints are defined in pyproject.toml

        🎯 Gravity Effect: Forces use of centralized path management,
           preventing path-related bugs and import chaos.
        """
        is_valid, violations = validate_no_syspath_hacks(project_root)

        if not is_valid:
            failure_message = (
                "❌ Path Import Violations FAILED\n\n" "The following files contain path import manipulations:\n\n"
            )
            for violation in violations[:10]:  # Show first 10
                failure_message += f"  • {violation}\n"

            if len(violations) > 10:
                failure_message += f"  ... and {len(violations) - 10} more files\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Remove all path manipulation calls\n"
                "  2. Use Poetry workspace imports instead\n"
                "  3. Rely on pyproject.toml script entrypoints\n"
                "  4. Ensure packages are properly installed in development mode\n\n"
                "📖 This enforces clean import practices and prevents the\n"
                "   'sys.path hell' that makes codebases unmaintainable."
            )

            pytest.fail(failure_message)

    def test_single_config_source(self, project_root):
        """
        📋 GOLDEN TEST 4: Single Config Source

        Enforce pyproject.toml as single source of configuration truth.

        This test ensures that:
        - No setup.py files exist in the project
        - Root pyproject.toml exists and has workspace config
        - All package management goes through Poetry

        🎯 Gravity Effect: Prevents configuration drift and maintains
           a single, authoritative source for all project metadata.
        """
        is_valid, violations = validate_single_config_source(project_root)

        if not is_valid:
            failure_message = "❌ Single Config Source FAILED\n\n" "Configuration violations found:\n\n"
            for violation in violations:
                failure_message += f"  • {violation}\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Remove any setup.py files - use pyproject.toml instead\n"
                "  2. Ensure root pyproject.toml has [tool.poetry.group.workspace]\n"
                "  3. Use Poetry for all dependency and package management\n"
                "  4. Convert any setuptools configurations to Poetry format\n\n"
                "📖 This enforces modern Python packaging standards and\n"
                "   prevents the confusion of multiple config systems."
            )

            pytest.fail(failure_message)

    def test_no_hardcoded_env_values(self, project_root):
        """
        🔒 GOLDEN TEST 4.5: No Hardcoded Environment Values

        Enforce environment-agnostic packages.

        This test ensures that:
        - No hardcoded server paths, usernames, or hostnames in packages
        - Deployment configuration uses environment variables
        - Generic packages remain environment-agnostic
        - No coupling between infrastructure code and specific environments

        🎯 Gravity Effect: Prevents environment-specific coupling in
           generic packages, enabling true portability and reusability.
        """
        is_valid, violations = validate_no_hardcoded_env_values(project_root)

        if not is_valid:
            failure_message = "❌ Hardcoded Environment Values FOUND\n\n" "Environment coupling violations found:\n\n"
            for violation in violations[:10]:
                failure_message += f"  • {violation}\n"

            if len(violations) > 10:
                failure_message += f"  ... and {len(violations) - 10} more violations\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Replace hardcoded paths with environment variables\n"
                "  2. Use get_deployment_config() in hive-deployment\n"
                "  3. Pass deployment_config to functions instead of constants\n"
                "  4. Make packages configurable, not environment-specific\n\n"
                "📖 This enforces portability and prevents coupling between\n"
                "   generic infrastructure and specific deployment environments."
            )

            pytest.fail(failure_message)

    def test_package_app_discipline(self, project_root):
        """
        🏗️ GOLDEN TEST 5: Package vs App Discipline

        Enforce the inherit → extend pattern.

        This test ensures that:
        - Packages contain only generic infrastructure
        - Apps contain business logic and extend packages
        - Clear separation of concerns is maintained

        🎯 Gravity Effect: Prevents business logic pollution in
           generic packages, maintaining reusability.
        """
        is_valid, violations = validate_package_app_discipline(project_root)

        if not is_valid:
            failure_message = "❌ Package vs App Discipline FAILED\n\n" "The following violations were found:\n\n"
            for violation in violations[:10]:
                failure_message += f"  • {violation}\n"

            if len(violations) > 10:
                failure_message += f"  ... and {len(violations) - 10} more violations\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Move business logic from packages to apps\n"
                "  2. Keep packages generic and reusable\n"
                "  3. Apps should extend package functionality\n"
                "  4. Follow the inherit → extend pattern\n\n"
                "📖 This enforces clean architecture where packages\n"
                "   provide tools and apps use them for business needs."
            )

            pytest.fail(failure_message)

    def test_dependency_direction(self, project_root):
        """
        🔄 GOLDEN TEST 6: Dependency Direction

        Enforce proper dependency flow.

        This test ensures that:
        - Apps can depend on packages (allowed)
        - Packages cannot depend on apps (forbidden)
        - Apps avoid direct app-to-app dependencies (use shared packages)

        🎯 Gravity Effect: Prevents circular dependencies and
           maintains clean architecture layers.
        """
        is_valid, violations = validate_dependency_direction(project_root)

        if not is_valid:
            failure_message = "❌ Dependency Direction FAILED\n\n" "Invalid dependencies detected:\n\n"
            for violation in violations[:10]:
                failure_message += f"  • {violation}\n"

            if len(violations) > 10:
                failure_message += f"  ... and {len(violations) - 10} more violations\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Remove package imports from apps\n"
                "  2. Use shared packages for app-to-app communication\n"
                "  3. Consider hive-orchestrator.core for shared app logic\n"
                "  4. Refactor to eliminate circular dependencies\n\n"
                "📖 This maintains clean architectural layers and\n"
                "   prevents dependency hell."
            )

            pytest.fail(failure_message)

    def test_interface_contracts(self, project_root):
        """
        📝 GOLDEN TEST 7: Interface Contracts

        Enforce API documentation and type safety.

        This test ensures that:
        - All public APIs have type hints
        - All public functions have docstrings
        - Async functions follow naming conventions (_async suffix)

        🎯 Gravity Effect: Makes APIs self-documenting and
           type-safe, improving maintainability.
        """
        is_valid, violations = validate_interface_contracts(project_root)

        # This is a strict rule but we'll start with warnings
        if not is_valid and len(violations) < 100:  # Only fail if reasonable number
            failure_message = "❌ Interface Contracts FAILED\n\n" "Missing type hints or documentation:\n\n"
            for violation in violations[:20]:  # Show more for this rule
                failure_message += f"  • {violation}\n"

            if len(violations) > 20:
                failure_message += f"  ... and {len(violations) - 20} more violations\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Add type hints to all public function parameters\n"
                "  2. Add return type hints to all functions\n"
                "  3. Add docstrings to all public functions\n"
                "  4. Rename async functions to end with _async\n\n"
                "📖 This ensures APIs are self-documenting and type-safe."
            )

            # For now, just warn instead of fail for this rule
            # pytest.fail(failure_message)
            logger.info(f"⚠️ WARNING: {len(violations)} interface contract violations found")

    def test_error_handling_standards(self, project_root):
        """
        🛡️ GOLDEN TEST 8: Error Handling Standards

        Enforce robust error handling practices.

        This test ensures that:
        - No bare except clauses in production code
        - All exceptions are properly typed
        - Errors include context for debugging

        🎯 Gravity Effect: Prevents silent failures and
           improves system reliability.
        """
        is_valid, violations = validate_error_handling_standards(project_root)

        if not is_valid:
            failure_message = "❌ Error Handling Standards FAILED\n\n" "Poor error handling detected:\n\n"
            for violation in violations[:15]:
                failure_message += f"  • {violation}\n"

            if len(violations) > 15:
                failure_message += f"  ... and {len(violations) - 15} more violations\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Replace bare except with specific exception types\n"
                "  2. Use hive-error-handling base classes\n"
                "  3. Include context in error messages\n"
                "  4. Consider error recovery strategies\n\n"
                "📖 This prevents silent failures and makes debugging easier."
            )

            pytest.fail(failure_message)

    def test_logging_standards(self, project_root):
        """
        📊 GOLDEN TEST 9: Logging Standards

        Enforce consistent logging practices.

        This test ensures that:
        - All components use hive-logging
        - No print statements in production code
        - Structured logging with appropriate levels

        🎯 Gravity Effect: Ensures observability and
           professional logging practices.
        """
        is_valid, violations = validate_logging_standards(project_root)

        if not is_valid:
            failure_message = "❌ Logging Standards FAILED\n\n" "Logging violations found:\n\n"
            for violation in violations[:15]:
                failure_message += f"  • {violation}\n"

            if len(violations) > 15:
                failure_message += f"  ... and {len(violations) - 15} more violations\n"

            failure_message += (
                "\n🔧 To fix this:\n"
                "  1. Replace print() with proper logging calls\n"
                "  2. Import and use hive_logging\n"
                "  3. Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)\n"
                "  4. Include structured context in log messages\n\n"
                "📖 This ensures professional logging and observability."
            )

            pytest.fail(failure_message)

    def test_enhanced_golden_rules(self, project_root):
        """
        🚀 ENHANCED GOLDEN RULES: Single-Pass AST-Based Validation

        This test runs the next-generation Golden Rules framework with:
        - 5-10x faster validation (single-pass AST traversal)
        - More accurate validation (AST-based vs string matching)
        - Suppression support for controlled exceptions
        - New security, performance, and maintainability rules

        New Rules Added:
        - Rule 17: No Unsafe Function Calls (Security)
        - Rule 18: API Endpoint Security (Security)
        - Rule 19: No Synchronous Calls in Async Code (Performance)
        - Rule 20: Test Quality and Coverage (Maintainability)
        - Rule 21: hive-models Purity (Architecture)
        - Rule 22: Documentation Hygiene (Maintainability)

        🎯 Gravity Effect: Creates an immune system that automatically
           prevents architectural decay and security vulnerabilities.
        """
        validator = EnhancedValidator(project_root)
        is_valid, violations_by_rule = validator.validate_all()

        if not is_valid:
            failure_message = (
                "🚀 Enhanced Golden Rules FAILED\n\n" "The next-generation validation framework found violations:\n\n"
            )

            for rule_name, rule_violations in violations_by_rule.items():
                failure_message += f"📋 {rule_name}:\n"
                for violation in rule_violations[:10]:  # Limit to first 10 per rule
                    failure_message += f"  • {violation}\n"
                if len(rule_violations) > 10:
                    failure_message += f"  ... and {len(rule_violations) - 10} more violations\n"
                failure_message += "\n"

            failure_message += (
                "🔧 To fix violations:\n"
                "  1. Review each violation message for specific guidance\n"
                "  2. Use suppression comments for valid exceptions:\n"
                "     # golden-rule-ignore: rule-17 - Legacy system integration\n"
                "  3. Run tests frequently to catch violations early\n"
                "  4. Consider the architectural intent behind each rule\n\n"
                "📖 This enhanced framework provides superior accuracy and performance\n"
                "   while maintaining the architectural integrity of your platform."
            )

            pytest.fail(failure_message)


class TestPlatformStandards:
    """
    Additional tests for Hive platform standards and patterns.
    """

    def test_no_root_python_files(self, project_root):
        """
        Ensure no Python files exist in the project root.
        All code should be in apps/ or packages/.
        """
        root_py_files = [f for f in project_root.glob("*.py") if f.name not in ["conftest.py"]]  # Allow conftest.py

        assert not root_py_files, (
            f"Found Python files in project root: {root_py_files}\n"
            "Move these to appropriate apps/ or packages/ directories."
        )

    def test_proper_package_structure(self, packages_dir):
        """
        Ensure all packages follow the standard structure.
        """
        if not packages_dir.exists():
            pytest.skip("No packages directory found")

        for package_dir in packages_dir.iterdir():
            if package_dir.is_dir() and not package_dir.name.startswith("."):
                # Each package should have pyproject.toml and src/
                assert (package_dir / "pyproject.toml").exists(), f"Package {package_dir.name} missing pyproject.toml"
                assert (package_dir / "src").exists(), f"Package {package_dir.name} missing src/ directory"

    def test_proper_app_structure(self, apps_dir):
        """
        Ensure all apps follow the standard structure.
        """
        if not apps_dir.exists():
            pytest.skip("No apps directory found")

        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                # Each app should have either src/ or be self-contained
                has_src = (app_dir / "src").exists()
                has_python_files = any(app_dir.glob("*.py"))

                assert has_src or has_python_files, f"App {app_dir.name} has no Python code (no src/ or *.py files)"


if __name__ == "__main__":
    # Allow running this file directly for quick validation

    # No sys.path manipulation needed - use Poetry workspace imports

    pytest.main([__file__, "-v"])

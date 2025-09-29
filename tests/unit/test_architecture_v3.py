"""
EcoSystemiser v3.0 Architecture Golden Tests

These tests enforce the architectural principles established during the v3.0 refactoring:
1. Service Layer Decoupling - No direct service-to-service imports
2. Climate Validation Co-location - QCProfile classes co-located with adapters
3. Reporting Service Centralization - Single source of truth for report generation
4. CLI Layer Purity - CLI is presentation only, no domain logic
5. Streamlit Isolation - Dashboard app does not import from ecosystemiser package
"""

import ast
from pathlib import Path

import pytest

# Root directories
PROJECT_ROOT = Path(__file__).parent.parent
ECOSYSTEMISER_ROOT = PROJECT_ROOT / "apps" / "ecosystemiser"
SRC_ROOT = ECOSYSTEMISER_ROOT / "src" / "ecosystemiser"


class ImportChecker(ast.NodeVisitor):
    """AST visitor to check imports in Python files."""

    def __init__(self):
        self.imports = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module)
        self.generic_visit(node)


def check_file_imports(file_path: Path, forbidden_patterns: list[str]) -> list[str]:
    """Check if a file contains forbidden imports."""
    violations = []

    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        checker = ImportChecker()
        checker.visit(tree)

        for import_name in checker.imports:
            for pattern in forbidden_patterns:
                if pattern in import_name:
                    violations.append(f"{file_path.relative_to(PROJECT_ROOT)}: Forbidden import '{import_name}'")
    except Exception:
        # Skip files that can't be parsed
        pass

    return violations


def test_service_layer_decoupling():
    """Test that services don't directly import other services."""
    services_dir = SRC_ROOT / "services"
    violations = []

    if not services_dir.exists():
        pytest.skip("Services directory not found")

    # Services should not import each other directly
    service_files = ["simulation_service.py", "study_service.py", "job_service.py", "reporting_service.py"]

    for service_file in service_files:
        file_path = services_dir / service_file
        if not file_path.exists():
            continue

        # Check that this service doesn't import other services directly
        # Exception: study_service can import types from simulation_service
        forbidden_patterns = []
        for other_service in service_files:
            if other_service != service_file:
                # Allow study_service to import from simulation_service for types
                if service_file == "study_service.py" and other_service == "simulation_service.py":
                    continue  # This is allowed for type imports
                service_name = other_service.replace(".py", "")
                forbidden_patterns.append(f"ecosystemiser.services.{service_name}")

        file_violations = check_file_imports(file_path, forbidden_patterns)
        violations.extend(file_violations)

    # StudyService should use JobFacade, not instantiate SimulationService directly
    study_service = services_dir / "study_service.py"
    if study_service.exists():
        with open(study_service) as f:
            content = f.read()
            # Check for direct instantiation of SimulationService
            if "SimulationService()" in content:
                violations.append("study_service.py: Direct instantiation of SimulationService (should use JobFacade)")
            if "from ecosystemiser.services.job_facade" not in content:
                violations.append("study_service.py: Missing import of JobFacade")
            # Allow type imports from simulation_service but with a comment explaining why
            if "from ecosystemiser.services.simulation_service" in content and "# Import only types" not in content:
                violations.append(
                    "study_service.py: Import from simulation_service should have comment explaining it's for types only"
                )

    assert len(violations) == 0, "Service decoupling violations:\n" + "\n".join(violations)


def test_climate_validation_colocated():
    """Test that QCProfile classes are co-located with their adapters."""
    adapters_dir = SRC_ROOT / "profile_loader" / "climate" / "adapters"
    validation_file = SRC_ROOT / "profile_loader" / "climate" / "processing" / "validation.py"

    violations = []

    # Check that validation.py doesn't contain adapter-specific QCProfile classes
    if validation_file.exists():
        with open(validation_file) as f:
            content = f.read()

        # These classes should NOT be in validation.py
        forbidden_classes = ["class NASAPowerQCProfile", "class MeteostatQCProfile", "class ERA5QCProfile"]

        for class_def in forbidden_classes:
            if class_def in content:
                violations.append(f"validation.py: Contains {class_def} (should be in adapter file)")

    # Check that adapter files contain their QCProfile classes
    expected_profiles = {
        "nasa_power.py": "NASAPowerQCProfile",
        "meteostat.py": "MeteostatQCProfile",
        "era5.py": "ERA5QCProfile",
    }

    for adapter_file, profile_class in expected_profiles.items():
        file_path = adapters_dir / adapter_file
        if file_path.exists():
            with open(file_path) as f:
                content = f.read()

            # Check class exists and inherits from QCProfile
            if f"class {profile_class}(QCProfile)" not in content:
                violations.append(f"{adapter_file}: Missing or incorrect {profile_class} definition")

            # Check proper imports
            if "from ecosystemiser.profile_loader.climate.processing.validation import" not in content:
                violations.append(f"{adapter_file}: Missing validation imports")

    assert len(violations) == 0, "Climate validation co-location violations:\n" + "\n".join(violations)


def test_reporting_service_centralized():
    """Test that report generation is centralized in ReportingService."""
    violations = []

    # Check that CLI uses ReportingService for reports
    cli_file = SRC_ROOT / "cli.py"
    if cli_file.exists():
        with open(cli_file) as f:
            content = f.read()

        # CLI should use ReportingService
        if "from ecosystemiser.services.reporting_service import ReportingService" not in content:
            violations.append("cli.py: Missing ReportingService import")

        # CLI should NOT directly use HTMLReportGenerator
        if "from ecosystemiser.reporting.generator import HTMLReportGenerator" in content:
            violations.append("cli.py: Direct use of HTMLReportGenerator (should use ReportingService)")

    # Check that Flask app uses ReportingService
    flask_app = SRC_ROOT / "reporting" / "app.py"
    if flask_app.exists():
        with open(flask_app) as f:
            content = f.read()

        # Flask should use ReportingService
        if "from ecosystemiser.services.reporting_service import ReportingService" not in content:
            violations.append("reporting/app.py: Missing ReportingService import")

        # Flask routes should use app.reporting_service
        if "app.reporting_service = ReportingService()" not in content:
            violations.append("reporting/app.py: ReportingService not initialized")

    assert len(violations) == 0, "Reporting centralization violations:\n" + "\n".join(violations)


def test_cli_layer_purity():
    """Test that CLI is pure presentation layer without domain logic."""
    cli_file = SRC_ROOT / "cli.py"
    violations = []

    if not cli_file.exists():
        pytest.skip("CLI file not found")

    with open(cli_file) as f:
        content = f.read()

    # CLI should NOT directly instantiate domain objects
    forbidden_patterns = [
        "SystemRepository(",
        "ConfigBuilder(",
        "SystemBuilder(",
        "SimulationEngine(",
        "EnergySystemSimulator(",
    ]

    for pattern in forbidden_patterns:
        if pattern in content:
            violations.append(f"cli.py: Direct instantiation of {pattern} (should use service layer)")

    # CLI should NOT import from repositories or builders directly
    forbidden_imports = [
        "from ecosystemiser.repositories",
        "from ecosystemiser.builders",
        "from ecosystemiser.simulation.engine",
    ]

    for import_pattern in forbidden_imports:
        if import_pattern in content:
            violations.append(f"cli.py: Forbidden import '{import_pattern}' (should use service layer)")

    # CLI SHOULD import from services
    required_imports = [
        "from ecosystemiser.services.simulation_service",
        "from ecosystemiser.services.reporting_service",
    ]

    for required_import in required_imports:
        if required_import not in content:
            violations.append(f"cli.py: Missing required service import '{required_import}'")

    assert len(violations) == 0, "CLI layer purity violations:\n" + "\n".join(violations)


def test_streamlit_isolation():
    """Test that Streamlit dashboard is isolated from main package."""
    dashboard_dir = ECOSYSTEMISER_ROOT / "dashboard"
    violations = []

    if not dashboard_dir.exists():
        pytest.skip("Dashboard directory not found")

    # Check all Python files in dashboard directory
    for py_file in dashboard_dir.rglob("*.py"):
        forbidden_patterns = ["ecosystemiser."]  # Should not import from main package

        file_violations = check_file_imports(py_file, forbidden_patterns)
        violations.extend(file_violations)

    # Dashboard should have its own requirements
    requirements_file = dashboard_dir / "requirements.txt"
    if not requirements_file.exists():
        violations.append("dashboard/requirements.txt: Missing (needed for isolation)")

    assert len(violations) == 0, "Streamlit isolation violations:\n" + "\n".join(violations)


def test_validation_file_size():
    """Test that validation.py has been properly refactored."""
    validation_file = SRC_ROOT / "profile_loader" / "climate" / "processing" / "validation.py"

    if not validation_file.exists():
        pytest.skip("Validation file not found")

    with open(validation_file) as f:
        lines = f.readlines()

    line_count = len(lines)

    # After refactoring, validation.py should be significantly smaller
    assert line_count < 1800, (
        f"validation.py has {line_count} lines (should be < 1800 after refactoring). "
        "QCProfile classes should be moved to adapter files."
    )


def test_job_facade_exists():
    """Test that JobFacade service exists and is properly structured."""
    job_facade = SRC_ROOT / "services" / "job_facade.py"

    assert job_facade.exists(), "job_facade.py missing (required for service decoupling)"

    with open(job_facade) as f:
        content = f.read()

    # JobFacade should have key methods
    required_methods = ["def submit_job", "def get_job_status", "def get_job_result"]

    violations = []
    for method in required_methods:
        if method not in content:
            violations.append(f"JobFacade missing required method: {method}")

    assert len(violations) == 0, "JobFacade structure violations:\n" + "\n".join(violations)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])

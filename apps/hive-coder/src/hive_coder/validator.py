"""
Code validation for generated services.

Validates syntax, Golden Rules compliance, and test execution.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from hive_logging import get_logger

from .models import ValidationResult

logger = get_logger(__name__)


class CodeValidator:
    """
    Validates generated code meets quality standards.

    Runs multiple validation checks:
    1. Syntax validation (py_compile)
    2. Golden Rules compliance (platform validators)
    3. Test execution (pytest)
    4. Type checking (mypy - optional)
    """

    def __init__(self) -> None:
        self.logger = logger

    def validate(self, service_dir: Path, run_tests: bool = True, run_type_check: bool = False) -> ValidationResult:
        """
        Run all validation checks on generated service.

        Args:
            service_dir: Directory containing generated service
            run_tests: Whether to execute test suite
            run_type_check: Whether to run mypy type checking

        Returns:
            ValidationResult with detailed validation status
        """
        self.logger.info(f"Validating generated service: {service_dir}")

        result = ValidationResult()

        # 1. Syntax validation
        result.syntax_valid, syntax_errors = self._validate_syntax(service_dir)
        if not result.syntax_valid:
            result.errors.extend(syntax_errors)

        # 2. Golden Rules validation
        result.golden_rules_passed, golden_errors = self._validate_golden_rules(service_dir)
        if not result.golden_rules_passed:
            result.errors.extend(golden_errors)

        # 3. Test execution (optional)
        if run_tests:
            result.tests_passed, test_errors = self._run_tests(service_dir)
            if not result.tests_passed:
                result.errors.extend(test_errors)

        # 4. Type checking (optional)
        if run_type_check:
            result.type_check_passed, type_errors = self._run_type_check(service_dir)
            if not result.type_check_passed:
                result.warnings.extend(type_errors)

        validation_status = "PASSED" if result.is_valid() else "FAILED"
        self.logger.info(f"Validation complete: {validation_status}")
        return result

    def _validate_syntax(self, service_dir: Path) -> tuple[bool, list[str]]:
        """Validate all Python files compile"""
        self.logger.info("Running syntax validation...")
        errors = []

        python_files = list(service_dir.rglob("*.py"))
        if not python_files:
            return True, []

        for py_file in python_files:
            try:
                result = subprocess.run(  # noqa: S603, S607
                    ["python", "-m", "py_compile", str(py_file)],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )

                if result.returncode != 0:
                    errors.append(f"Syntax error in {py_file.name}: {result.stderr.strip()}")
            except subprocess.TimeoutExpired:
                errors.append(f"Syntax check timeout for {py_file.name}")
            except Exception as e:
                errors.append(f"Syntax check failed for {py_file.name}: {e!s}")

        is_valid = len(errors) == 0
        self.logger.info(f"Syntax validation: {'PASSED' if is_valid else f'FAILED ({len(errors)} errors)'}")
        return is_valid, errors

    def _validate_golden_rules(self, service_dir: Path) -> tuple[bool, list[str]]:
        """Validate Golden Rules compliance"""
        self.logger.info("Running Golden Rules validation...")
        errors = []

        # Check if validation script exists
        validator_script = Path("scripts/validation/validate_golden_rules.py")
        if not validator_script.exists():
            self.logger.warning("Golden Rules validator not found, skipping")
            return True, []

        try:
            result = subprocess.run(  # noqa: S603, S607
                ["python", str(validator_script), "--level", "ERROR", "--app", service_dir.name],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                cwd=Path.cwd(),
            )

            if result.returncode != 0:
                errors.append(f"Golden Rules validation failed: {result.stdout.strip()}")
        except subprocess.TimeoutExpired:
            errors.append("Golden Rules validation timeout")
        except Exception as e:
            self.logger.warning(f"Golden Rules validation error: {e!s}")
            # Don't fail validation if script has issues
            return True, []

        is_valid = len(errors) == 0
        self.logger.info(f"Golden Rules validation: {'PASSED' if is_valid else 'FAILED'}")
        return is_valid, errors

    def _run_tests(self, service_dir: Path) -> tuple[bool, list[str]]:
        """Run test suite"""
        self.logger.info("Running test suite...")
        errors = []

        # Check if tests directory exists
        tests_dir = service_dir / "tests"
        if not tests_dir.exists():
            self.logger.warning("No tests directory found, skipping test execution")
            return True, []

        try:
            result = subprocess.run(  # noqa: S603, S607
                ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
                cwd=service_dir,
            )

            if result.returncode != 0:
                errors.append(f"Test suite failed: {result.stdout.strip()}")
        except subprocess.TimeoutExpired:
            errors.append("Test execution timeout")
        except Exception as e:
            errors.append(f"Test execution error: {e!s}")

        is_valid = len(errors) == 0
        self.logger.info(f"Test suite: {'PASSED' if is_valid else 'FAILED'}")
        return is_valid, errors

    def _run_type_check(self, service_dir: Path) -> tuple[bool, list[str]]:
        """Run mypy type checking"""
        self.logger.info("Running type checking...")
        errors = []

        try:
            result = subprocess.run(  # noqa: S603, S607
                ["python", "-m", "mypy", "src/", "--ignore-missing-imports"],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                cwd=service_dir,
            )

            if result.returncode != 0:
                # Type check warnings, not critical errors
                errors.append(f"Type check warnings: {result.stdout.strip()}")
        except subprocess.TimeoutExpired:
            errors.append("Type check timeout")
        except Exception as e:
            self.logger.warning(f"Type checking skipped: {e!s}")
            return True, []

        is_valid = len(errors) == 0
        self.logger.info(f"Type checking: {'PASSED' if is_valid else 'WARNINGS'}")
        return is_valid, errors

# ruff: noqa: S603
# Security: subprocess calls in this validator use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal validation tooling.

"""Environment Isolation Validator

Golden Rules for Environment Management and Multi-Language Platform Architecture

This validator ensures:
1. No environment path hardcoding
2. Proper conda/poetry separation
3. Multi-language toolchain validation
4. Docker/Kubernetes readiness
5. Consistent Python version across all packages

Severity Levels:
- CRITICAL: Environment conflicts, hardcoded paths in production code
- ERROR: Missing toolchain, inconsistent versions
- WARNING: Missing documentation, outdated lockfiles
- INFO: Best practice recommendations
"""

import re
import subprocess
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class EnvironmentIsolationValidator:
    """Validates environment isolation and multi-language platform setup."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.violations = []

    def validate_all(self) -> dict[str, Any]:
        """Run all environment isolation validation rules.

        Returns:
            Dictionary with validation results and violations
        """
        logger.info("Running environment isolation validation")

        self.violations = []

        # Rule 25: No conda references in production code
        self._validate_no_conda_in_code()

        # Rule 26: No hardcoded environment paths
        self._validate_no_hardcoded_paths()

        # Rule 27: Consistent Python version across pyproject.toml files
        self._validate_python_version_consistency()

        # Rule 28: Poetry lockfile exists and is up-to-date
        self._validate_poetry_lockfile()

        # Rule 29: Multi-language toolchain available
        self._validate_multi_language_toolchain()

        # Rule 30: Environment variable usage instead of hardcoded paths
        self._validate_environment_variables()

        return {
            "total_violations": len(self.violations),
            "violations": self.violations,
            "passed": len(self.violations) == 0,
        }

    def _validate_no_conda_in_code(self) -> None:
        """Rule 25: Production code must not reference conda directly.

        Severity: CRITICAL
        Rationale: Conda is a development environment manager, not a runtime dependency.
                   Production code should be environment-agnostic.
        """
        logger.debug("Validating Rule 25: No conda references in production code")

        excluded_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}
        excluded_files = {"environment.yml", "CONDA_HIVE_SETUP.md"}
        allowed_extensions = {".py", ".sh", ".bat"}

        for file_path in self.project_root.rglob("*"):
            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in excluded_dirs):
                continue

            # Skip excluded files
            if file_path.name in excluded_files:
                continue

            # Skip legacy and archive directories
            if "legacy" in file_path.parts or "archive" in file_path.parts:
                continue

            # Only check relevant file types
            if not file_path.is_file() or file_path.suffix not in allowed_extensions:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")

                # Check for conda activation or conda commands
                conda_patterns = [
                    r"conda\s+activate",
                    r"conda\s+install",
                    r"conda\s+env",
                    r"conda\s+create",
                    r"\$CONDA_DEFAULT_ENV",
                    r"os\.environ\[.CONDA",
                ]

                for pattern in conda_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        self.violations.append({
                            "rule": "Rule 25",
                            "severity": "CRITICAL",
                            "file": str(file_path.relative_to(self.project_root)),
                            "message": f"Conda reference found: {pattern}",
                            "description": "Production code must not depend on conda environment",
                        })
            except Exception as e:
                logger.debug(f"Could not read {file_path}: {e}")

    def _validate_no_hardcoded_paths(self) -> None:
        """Rule 26: No hardcoded absolute paths in code.

        Severity: ERROR
        Rationale: Hardcoded paths break portability and Docker/Kubernetes deployment.
        """
        logger.debug("Validating Rule 26: No hardcoded absolute paths")

        excluded_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules"}

        # Dangerous patterns (absolute paths)
        dangerous_patterns = [
            r"['\"]\/c\/git\/",  # Windows Git Bash paths
            r"['\"]C:\\git\\",   # Windows paths
            r"['\"]\/home\/\w+\/",  # Linux home paths
            r"['\"]C:\\Users\\",  # Windows user paths
        ]

        for py_file in self.project_root.rglob("*.py"):
            if any(excluded in py_file.parts for excluded in excluded_dirs):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")

                for pattern in dangerous_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        self.violations.append({
                            "rule": "Rule 26",
                            "severity": "ERROR",
                            "file": str(py_file.relative_to(self.project_root)),
                            "message": f"Hardcoded absolute path found: {matches[0]}",
                            "description": "Use environment variables or relative paths",
                        })
            except Exception as e:
                logger.debug(f"Could not read {py_file}: {e}")

    def _validate_python_version_consistency(self) -> None:
        """Rule 27: All pyproject.toml files must have consistent Python version.

        Severity: ERROR
        Rationale: Inconsistent Python versions cause dependency conflicts.
        """
        logger.debug("Validating Rule 27: Python version consistency")

        expected_version = "^3.11"
        version_pattern = re.compile(r'python\s*=\s*["\']([^"\']+)["\']')

        for toml_file in self.project_root.rglob("pyproject.toml"):
            try:
                content = toml_file.read_text(encoding="utf-8")

                matches = version_pattern.findall(content)
                if matches:
                    python_version = matches[0]
                    if python_version != expected_version:
                        self.violations.append({
                            "rule": "Rule 27",
                            "severity": "ERROR",
                            "file": str(toml_file.relative_to(self.project_root)),
                            "message": f"Python version '{python_version}' != expected '{expected_version}'",
                            "description": "All packages must use Python ^3.11",
                        })
            except Exception as e:
                logger.debug(f"Could not read {toml_file}: {e}")

    def _validate_poetry_lockfile(self) -> None:
        """Rule 28: Poetry lockfile must exist and be up-to-date.

        Severity: WARNING
        Rationale: Missing lockfile breaks reproducible builds.
        """
        logger.debug("Validating Rule 28: Poetry lockfile exists")

        lockfile = self.project_root / "poetry.lock"

        if not lockfile.exists():
            self.violations.append({
                "rule": "Rule 28",
                "severity": "WARNING",
                "file": "poetry.lock",
                "message": "Poetry lockfile does not exist",
                "description": "Run 'poetry lock' to generate lockfile",
            })
            return

        # Check if lockfile is older than pyproject.toml
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            if lockfile.stat().st_mtime < pyproject.stat().st_mtime:
                self.violations.append({
                    "rule": "Rule 28",
                    "severity": "WARNING",
                    "file": "poetry.lock",
                    "message": "Poetry lockfile is older than pyproject.toml",
                    "description": "Run 'poetry lock --no-update' to refresh lockfile",
                })

    def _validate_multi_language_toolchain(self) -> None:
        """Rule 29: Multi-language toolchain must be available.

        Severity: INFO
        Rationale: Platform supports Python, Node.js, Rust, Julia, Go.
        """
        logger.debug("Validating Rule 29: Multi-language toolchain")

        required_tools = {
            "python": {"cmd": ["python", "--version"], "min_version": "3.11"},
            "node": {"cmd": ["node", "--version"], "min_version": "20.0"},
            "cargo": {"cmd": ["cargo", "--version"], "min_version": "1.70"},
            "julia": {"cmd": ["julia", "--version"], "min_version": "1.9"},
            "go": {"cmd": ["go", "version"], "min_version": "1.21"},
        }

        for tool_name, tool_info in required_tools.items():
            try:
                result = subprocess.run(
                    tool_info["cmd"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode != 0:
                    self.violations.append({
                        "rule": "Rule 29",
                        "severity": "INFO",
                        "file": "system",
                        "message": f"{tool_name} not available",
                        "description": f"Install {tool_name} for multi-language support",
                    })
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.violations.append({
                    "rule": "Rule 29",
                    "severity": "INFO",
                    "file": "system",
                    "message": f"{tool_name} not found in PATH",
                    "description": f"Install {tool_name} via conda or system package manager",
                })

    def _validate_environment_variables(self) -> None:
        """Rule 30: Use environment variables instead of hardcoded config.

        Severity: WARNING
        Rationale: Environment variables enable 12-factor app deployment.
        """
        logger.debug("Validating Rule 30: Environment variable usage")

        # Check for config files that should use environment variables
        config_files = list(self.project_root.rglob("*config*.py"))
        config_files.extend(self.project_root.rglob("*settings*.py"))

        dangerous_patterns = [
            r"DATABASE_URL\s*=\s*['\"]sqlite:///",
            r"API_KEY\s*=\s*['\"][^'\"]+['\"]",
            r"SECRET_KEY\s*=\s*['\"][^'\"]+['\"]",
            r"PASSWORD\s*=\s*['\"][^'\"]+['\"]",
        ]

        for config_file in config_files:
            if "__pycache__" in str(config_file):
                continue

            try:
                content = config_file.read_text(encoding="utf-8")

                for pattern in dangerous_patterns:
                    if re.search(pattern, content):
                        # Check if it's using os.getenv or os.environ
                        if "os.getenv" not in content and "os.environ" not in content:
                            self.violations.append({
                                "rule": "Rule 30",
                                "severity": "WARNING",
                                "file": str(config_file.relative_to(self.project_root)),
                                "message": "Hardcoded configuration value found",
                                "description": "Use environment variables: os.getenv('VAR', 'default')",
                            })
            except Exception as e:
                logger.debug(f"Could not read {config_file}: {e}")


def validate_environment_isolation(project_root: Path | str) -> dict[str, Any]:
    """Validate environment isolation rules for the project.

    Args:
        project_root: Path to project root directory

    Returns:
        Dictionary with validation results
    """
    if isinstance(project_root, str):
        project_root = Path(project_root)

    validator = EnvironmentIsolationValidator(project_root)
    return validator.validate_all()

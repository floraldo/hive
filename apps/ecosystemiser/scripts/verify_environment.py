#!/usr/bin/env python3
"""
EcoSystemiser Environment Verification Script

This script verifies that EcoSystemiser is properly integrated with the Hive
ecosystem and all components are functioning correctly.
"""

import importlib
import subprocess
import sys
from pathlib import Path

from hive_logging import get_logger

logger = get_logger(__name__)


class EnvironmentVerifier:
    """Verifies EcoSystemiser environment and Hive integration."""

    def __init__(self) -> None:
        self.ecosystemiser_dir = Path(__file__).parent.parent
        self.results = []
        self.warnings = []
        self.errors = []

    def check_editable_install(self) -> bool:
        """Verify EcoSystemiser is installed as editable package."""
        try:
            import EcoSystemiser

            package_path = Path(EcoSystemiser.__file__).parent
            expected_path = self.ecosystemiser_dir / "src" / "EcoSystemiser"

            if package_path.resolve() == expected_path.resolve():
                self.results.append("[OK] EcoSystemiser installed as editable package")
                return True
            else:
                self.errors.append(f"[ERROR] EcoSystemiser not editable: {package_path}")
                return False
        except ImportError as e:
            self.errors.append(f"[ERROR] EcoSystemiser not installed: {e}")
            return False

    def check_hive_packages(self) -> bool:
        """Verify Hive packages are accessible."""
        hive_packages = [
            ("hive_config", "Configuration service"),
            ("hive_logging", "Logging service"),
        ]

        all_good = True
        for package, description in hive_packages:
            try:
                importlib.import_module(f"packages.{package}.src.{package}")
                self.results.append(f"[OK] {description} accessible ({package})")
            except ImportError:
                self.warnings.append(f"[WARN] {description} not found ({package})")
                all_good = False

        return all_good

    def check_no_sys_path_hacks(self) -> bool:
        """Verify no sys.path manipulations remain."""
        cmd = [
            "grep",
            "-r",
            "sys.path.insert\\|sys.path.append",
            "--include=*.py",
            str(self.ecosystemiser_dir),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                lines = result.stdout.strip().split("\n")
                # Filter out this script and legitimate uses
                bad_lines = [l for l in lines if "verify_environment.py" not in l]
                if bad_lines:
                    self.errors.append(f"[ERROR] Found {len(bad_lines)} sys.path hacks")
                    for line in bad_lines[:3]:  # Show first 3
                        self.errors.append(f"  - {line[:80]}...")
                    return False
            self.results.append("[OK] No sys.path hacks found")
            return True
        except Exception as e:
            self.warnings.append(f"[WARN] Could not check for sys.path hacks: {e}")
            return True

    def check_logging_integration(self) -> bool:
        """Verify logging is using Hive adapter."""
        try:
            from ecosystemiser.hive_logging_adapter import (
                USING_HIVE_LOGGING,
                get_logger,
            )

            get_logger(__name__)

            if USING_HIVE_LOGGING:
                self.results.append("[OK] Using Hive centralized logging")
            else:
                self.warnings.append("[WARN] Using fallback logging (Hive logging not available)")

            # Check that source files use the adapter
            src_dir = self.ecosystemiser_dir / "src"
            py_files = list(src_dir.rglob("*.py"))

            direct_logging_count = 0
            for py_file in py_files[:20]:  # Sample first 20 files
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                    if "import logging" in content and "hive_logging_adapter" not in content:
                        direct_logging_count += 1

            if direct_logging_count > 0:
                self.warnings.append(f"[WARN] {direct_logging_count} files still use direct logging")
            else:
                self.results.append("[OK] All sampled files use Hive logging adapter")

            return True
        except Exception as e:
            self.errors.append(f"[ERROR] Logging integration check failed: {e}")
            return False

    def check_configuration(self) -> bool:
        """Verify configuration is centralized."""
        try:
            from ecosystemiser.hive_env import get_app_config, get_app_settings

            get_app_config()
            get_app_settings()

            self.results.append("[OK] Configuration service accessible")

            # Check for direct os.getenv usage
            cmd = [
                "grep",
                "-r",
                "os.getenv\\|os.environ",
                "--include=*.py",
                str(self.ecosystemiser_dir / "src"),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                lines = [l for l in result.stdout.strip().split("\n") if "hive_env.py" not in l]
                if lines:
                    self.warnings.append(f"[WARN] {len(lines)} files use direct env vars")
                else:
                    self.results.append("[OK] No direct environment variable access")

            return True
        except Exception as e:
            self.errors.append(f"[ERROR] Configuration check failed: {e}")
            return False

    def check_imports(self) -> bool:
        """Verify all imports work correctly."""
        critical_imports = [
            "EcoSystemiser.cli",
            "EcoSystemiser.solver.milp_solver",
            "EcoSystemiser.system_model.system",
            "EcoSystemiser.profile_loader.climate.service",
            "EcoSystemiser.services.simulation_service",
        ]

        all_good = True
        for module_name in critical_imports:
            try:
                importlib.import_module(module_name)
                self.results.append(f"[OK] {module_name} imports correctly")
            except ImportError as e:
                self.errors.append(f"[ERROR] Failed to import {module_name}: {e}")
                all_good = False

        return all_good

    def check_import_consistency(self) -> bool:
        """Verify no relative imports cross module boundaries."""
        import ast

        src_dir = self.ecosystemiser_dir / "src" / "EcoSystemiser"
        py_files = list(src_dir.rglob("*.py"))

        relative_imports = []
        for py_file in py_files:
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.level > 0:  # Relative import
                            # Check if it crosses module boundaries
                            module_parts = py_file.relative_to(src_dir).parts[:-1]
                            if node.level > len(module_parts):
                                relative_imports.append(str(py_file.relative_to(self.ecosystemiser_dir)))
            except (SyntaxError, ValueError):
                # Skip files that can't be parsed
                continue

        if relative_imports:
            self.errors.append(f"[ERROR] Found {len(relative_imports)} files with boundary-crossing relative imports")
            for file in relative_imports[:3]:
                self.errors.append(f"  - {file}")
            return False
        else:
            self.results.append("[OK] No boundary-crossing relative imports found")
            return True

    def check_test_environment(self) -> bool:
        """Verify test environment is set up correctly."""
        try:
            # Run a simple test to verify pytest works
            result = subprocess.run(
                ["python", "-m", "pytest", "--collect-only", "-q"],
                cwd=self.ecosystemiser_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Parse test collection output
                lines = result.stdout.strip().split("\n")
                test_count = 0
                for line in lines:
                    if "test" in line.lower():
                        test_count += 1

                if test_count > 0:
                    self.results.append(f"[OK] Test environment working ({test_count} tests collected)")
                else:
                    self.warnings.append("[WARN] No tests collected")
            else:
                self.warnings.append(f"[WARN] Test collection failed: {result.stderr[:100]}")

            return True
        except Exception as e:
            self.warnings.append(f"[WARN] Test environment check failed: {e}")
            return True

    def run_verification(self) -> bool:
        """Run all verification checks."""
        logger.info("EcoSystemiser Environment Verification")
        logger.info("=" * 60)
        logger.info(f"Working directory: {self.ecosystemiser_dir}")
        logger.info()

        checks = [
            ("Editable Install", self.check_editable_install),
            ("Hive Packages", self.check_hive_packages),
            ("Import Cleanliness", self.check_no_sys_path_hacks),
            ("Import Consistency", self.check_import_consistency),
            ("Logging Integration", self.check_logging_integration),
            ("Configuration", self.check_configuration),
            ("Module Imports", self.check_imports),
            ("Test Environment", self.check_test_environment),
        ]

        for name, check_func in checks:
            logger.info(f"\nChecking {name}...")
            try:
                result = check_func()
                if not result:
                    pass
            except Exception as e:
                self.errors.append(f"[ERROR] {name} check crashed: {e}")

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 60)

        if self.results:
            logger.info("\nPASSED:")
            for result in self.results:
                logger.info(f"  {result}")

        if self.warnings:
            logger.warning("\nWARNINGS:")
            for warning in self.warnings:
                logger.warning(f"  {warning}")

        if self.errors:
            logger.error("\nERRORS:")
            for error in self.errors:
                logger.error(f"  {error}")

        # Overall status
        logger.info("\n" + "=" * 60)
        if not self.errors:
            if self.warnings:
                logger.warning("[OK] Environment MOSTLY READY (with warnings)")
                logger.info("  The system will work but some features may be limited")
            else:
                logger.info("[OK] Environment FULLY READY")
                logger.info("  EcoSystemiser is a model citizen of the Hive ecosystem!")
            return True
        else:
            logger.error("[FAILED] Environment NOT READY")
            logger.error("  Please fix the errors above before proceeding")
            return False


def main() -> None:
    """Main execution."""
    verifier = EnvironmentVerifier()
    success = verifier.run_verification()

    # Exit code indicates success/failure
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

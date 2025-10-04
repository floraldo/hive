#!/usr/bin/env python
"""
Project Colossus - Dress Rehearsal E2E Test

This is the final validation: a "live-fire exercise" of the complete autonomous
development pipeline with REAL filesystem generation.

Flow:
1. ArchitectAgent: Natural language → ExecutionPlan
2. CoderAgent: ExecutionPlan → Service code (REAL files on disk)
3. Inject intentional bug (missing import)
4. GuardianAgent: Detect → Fix → Retest → Approve
5. Validate complete autonomous loop

This is NOT a simulation. This creates REAL services on disk and tests the
complete pipeline end-to-end.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Add apps to path for imports
HIVE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(HIVE_ROOT / "apps" / "hive-architect" / "src"))
sys.path.insert(0, str(HIVE_ROOT / "apps" / "hive-coder" / "src"))
sys.path.insert(0, str(HIVE_ROOT / "apps" / "ai-reviewer" / "src"))

from hive_architect.agent import ArchitectAgent
from hive_coder.agent import CoderAgent

from hive_logging import get_logger

logger = get_logger(__name__)


class DressRehearsalTest:
    """
    Complete E2E test of Project Colossus autonomous development pipeline.
    """

    def __init__(self, output_dir: Path):
        """
        Initialize dress rehearsal test.

        Args:
            output_dir: Directory for test output (will be cleaned)
        """
        self.output_dir = output_dir
        self.architect = ArchitectAgent()
        self.coder = CoderAgent()

        # Test artifacts
        self.plan_file: Path | None = None
        self.service_dir: Path | None = None
        self.requirement = "Create a 'status-api' service that checks system health"

    def setup(self) -> None:
        """Setup test environment"""
        logger.info("=" * 80)
        logger.info("PROJECT COLOSSUS - DRESS REHEARSAL")
        logger.info("Complete Autonomous Development Pipeline Test")
        logger.info("=" * 80)

        # Clean output directory
        if self.output_dir.exists():
            logger.info(f"Cleaning output directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)

        self.output_dir.mkdir(parents=True)
        logger.info(f"Test output directory: {self.output_dir}")

    def test_architect_agent(self) -> bool:
        """
        Test 1: ArchitectAgent generates ExecutionPlan from natural language.

        Returns:
            True if plan generated successfully
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: ARCHITECT AGENT - Natural Language -> ExecutionPlan")
        logger.info("=" * 80)

        logger.info(f"Requirement: {self.requirement}")

        try:
            # Generate execution plan
            self.plan_file = self.output_dir / "execution_plan.json"
            plan = self.architect.create_plan(
                requirement_text=self.requirement,
                output_path=str(self.plan_file),
            )

            logger.info(f"Plan generated: {self.plan_file}")
            logger.info(f"Service name: {plan.service_name}")
            logger.info(f"Service type: {plan.service_type}")
            logger.info(f"Tasks: {len(plan.tasks)}")

            # Validate plan
            validation = self.coder.validate_plan(plan)

            if not validation["is_valid"]:
                logger.error("Plan validation failed!")
                for key, value in validation.items():
                    if not value and key != "is_valid":
                        logger.error(f"  - {key}: {value}")
                return False

            logger.info("Plan validation: PASS")
            return True

        except Exception as e:
            logger.error(f"Architect agent failed: {e}")
            return False

    def test_coder_agent(self) -> bool:
        """
        Test 2: CoderAgent generates service code from ExecutionPlan.

        Returns:
            True if code generated successfully
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: CODER AGENT - ExecutionPlan -> Service Code")
        logger.info("=" * 80)

        if not self.plan_file:
            logger.error("No plan file available")
            return False

        try:
            # Execute plan to generate service
            result = self.coder.execute_plan(
                plan_file=self.plan_file,
                output_dir=self.output_dir / "generated",
                validate_output=False,  # Skip validation initially
                run_tests=False,  # Skip tests initially
            )

            logger.info(f"Execution status: {result.status.value}")
            logger.info(f"Tasks completed: {result.tasks_completed}/{result.total_tasks}")
            logger.info(f"Output directory: {result.output_directory}")

            self.service_dir = result.output_directory

            # Check if service directory exists
            if not self.service_dir.exists():
                logger.error(f"Service directory not created: {self.service_dir}")
                return False

            # List generated files
            logger.info("\nGenerated files:")
            for file_path in sorted(self.service_dir.rglob("*.py")):
                rel_path = file_path.relative_to(self.service_dir)
                logger.info(f"  - {rel_path}")

            logger.info("Code generation: PASS")
            return True

        except Exception as e:
            logger.error(f"Coder agent failed: {e}")
            return False

    def inject_bug(self) -> bool:
        """
        Test 3: Inject intentional bug (missing import).

        This simulates a real-world scenario where generated code has errors.

        Returns:
            True if bug injected successfully
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 3: BUG INJECTION - Introduce Missing Import Error")
        logger.info("=" * 80)

        if not self.service_dir:
            logger.error("No service directory available")
            return False

        try:
            # Find main.py or api.py
            target_file = None
            for candidate in ["main.py", "api.py", "app.py"]:
                file_path = self.service_dir / candidate
                if file_path.exists():
                    target_file = file_path
                    break

            if not target_file:
                logger.warning("No suitable target file found for bug injection")
                # Try to find any Python file
                py_files = list(self.service_dir.rglob("*.py"))
                if py_files:
                    target_file = py_files[0]
                else:
                    return False

            logger.info(f"Target file: {target_file.relative_to(self.service_dir)}")

            # Read file content
            content = target_file.read_text(encoding="utf-8")

            # Inject bug: Add a line that uses 'os' without importing it
            bug_line = "\n# Intentional bug for testing\nCURRENT_DIR = os.getcwd()\n"

            # Find a good insertion point (after imports)
            lines = content.split("\n")
            insert_index = 0
            for i, line in enumerate(lines):
                if line.strip().startswith(("import ", "from ")):
                    insert_index = i + 1

            # Insert bug after imports
            lines.insert(insert_index + 1, bug_line)
            buggy_content = "\n".join(lines)

            # Write buggy content
            target_file.write_text(buggy_content, encoding="utf-8")

            logger.info("Bug injected: Using 'os.getcwd()' without 'import os'")
            logger.info("Expected error: F821 undefined name 'os'")

            return True

        except Exception as e:
            logger.error(f"Bug injection failed: {e}")
            return False

    def test_validation_fails(self) -> bool:
        """
        Test 4: Validate that ruff detects the injected bug.

        Returns:
            True if validation correctly fails
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 4: VALIDATION - Detect Injected Bug")
        logger.info("=" * 80)

        if not self.service_dir:
            logger.error("No service directory available")
            return False

        try:
            # Run ruff check
            result = subprocess.run(
                ["ruff", "check", str(self.service_dir)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            logger.info(f"Ruff exit code: {result.returncode}")

            if result.returncode == 0:
                logger.error("Validation PASSED - but should have FAILED!")
                logger.error("Bug was not detected by ruff")
                return False

            # Parse output for F821 error
            output = result.stdout + result.stderr
            logger.info("Validation output:")
            for line in output.split("\n")[:10]:  # First 10 lines
                if line.strip():
                    logger.info(f"  {line}")

            if "F821" in output and "os" in output:
                logger.info("Bug detected correctly: F821 undefined name 'os'")
                return True
            else:
                logger.warning("Bug detected but error may be different than expected")
                return True  # Still pass if validation failed

        except subprocess.TimeoutExpired:
            logger.error("Ruff check timed out")
            return False
        except FileNotFoundError:
            logger.error("Ruff not found - install with: pip install ruff")
            return False
        except Exception as e:
            logger.error(f"Validation check failed: {e}")
            return False

    def test_guardian_auto_fix(self) -> bool:
        """
        Test 5: GuardianAgent autonomously fixes the bug.

        This is the core test: Can the Guardian detect, fix, and validate?

        Returns:
            True if auto-fix succeeds
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 5: GUARDIAN AGENT - Autonomous Fix-Retry Loop")
        logger.info("=" * 80)

        if not self.service_dir:
            logger.error("No service directory available")
            return False

        try:
            from ai_reviewer.auto_fix import ErrorAnalyzer, EscalationLogic, FixGenerator, RetryManager

            # Initialize auto-fix components
            analyzer = ErrorAnalyzer()
            generator = FixGenerator()
            retry_manager = RetryManager(max_attempts=3)
            escalation_logic = EscalationLogic(max_attempts=3)

            logger.info("Auto-fix components initialized")

            # Get validation errors
            result = subprocess.run(
                ["ruff", "check", str(self.service_dir)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            validation_output = result.stdout + result.stderr

            # Parse errors
            errors = analyzer.parse_ruff_output(validation_output)
            logger.info(f"Parsed {len(errors)} errors")

            fixable_errors = analyzer.get_fixable_errors(errors)
            logger.info(f"Fixable errors: {len(fixable_errors)}")

            if not fixable_errors:
                logger.error("No fixable errors found!")
                return False

            # Start fix session
            session = retry_manager.start_session("test_task", self.service_dir)

            # Generate and apply fixes
            for error in fixable_errors:
                logger.info(f"\nFixing: {error.error_code} - {error.error_message}")
                logger.info(f"  File: {error.file_path}:{error.line_number}")

                # Read file content
                file_path = self.service_dir / error.file_path
                if not file_path.exists():
                    logger.warning(f"  File not found: {file_path}")
                    continue

                file_content = file_path.read_text(encoding="utf-8")

                # Generate fix
                fix = generator.generate_fix(error, file_content)
                if not fix:
                    logger.warning("  No fix generated")
                    continue

                logger.info(f"  Fix type: {fix.fix_type}")
                logger.info(f"  Fix: {fix.fixed_line}")
                logger.info(f"  Confidence: {fix.confidence:.2f}")

                # Apply fix
                success = retry_manager.apply_fix(session, fix)
                if success:
                    logger.info("  Fix applied successfully")
                else:
                    logger.warning("  Fix application failed")

            logger.info(f"\nFix session: {session.attempt_count} attempts")

            # Re-run validation
            logger.info("\nRe-running validation...")
            result = subprocess.run(
                ["ruff", "check", str(self.service_dir)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info("Validation PASSED after auto-fix!")
                retry_manager.complete_session(session, "fixed")
                return True
            else:
                logger.warning("Validation still failing after auto-fix")
                logger.info("Remaining errors:")
                for line in result.stdout.split("\n")[:5]:
                    if line.strip():
                        logger.info(f"  {line}")

                # Check if we should escalate
                decision = escalation_logic.should_escalate(session)
                if decision.should_escalate:
                    logger.info(f"\nEscalation triggered: {decision.reason}")
                    logger.info(f"Recommendation: {decision.recommendation}")

                retry_manager.complete_session(session, "escalated")
                return False

        except Exception as e:
            logger.error(f"Guardian auto-fix failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def test_final_validation(self) -> bool:
        """
        Test 6: Final validation that service is clean.

        Returns:
            True if final validation passes
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 6: FINAL VALIDATION - Service Quality Check")
        logger.info("=" * 80)

        if not self.service_dir:
            logger.error("No service directory available")
            return False

        try:
            # Run ruff check
            result = subprocess.run(
                ["ruff", "check", str(self.service_dir)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info("Ruff validation: PASS")
                ruff_passed = True
            else:
                logger.warning("Ruff validation: FAIL")
                logger.info(result.stdout)
                ruff_passed = False

            # Run syntax check on all Python files
            syntax_errors = []
            for py_file in self.service_dir.rglob("*.py"):
                result = subprocess.run(
                    ["python", "-m", "py_compile", str(py_file)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    syntax_errors.append(py_file.name)

            if syntax_errors:
                logger.error(f"Syntax errors in: {', '.join(syntax_errors)}")
                return False
            else:
                logger.info("Syntax validation: PASS")

            return ruff_passed

        except Exception as e:
            logger.error(f"Final validation failed: {e}")
            return False

    def run(self) -> bool:
        """
        Run complete dress rehearsal test.

        Returns:
            True if all tests pass
        """
        self.setup()

        # Test sequence
        tests = [
            ("Architect Agent", self.test_architect_agent),
            ("Coder Agent", self.test_coder_agent),
            ("Bug Injection", self.inject_bug),
            ("Validation Detects Bug", self.test_validation_fails),
            ("Guardian Auto-Fix", self.test_guardian_auto_fix),
            ("Final Validation", self.test_final_validation),
        ]

        results = {}
        for test_name, test_func in tests:
            try:
                passed = test_func()
                results[test_name] = passed
                status = "PASS" if passed else "FAIL"
                logger.info(f"\n{test_name}: {status}")

                if not passed:
                    logger.error(f"Test failed: {test_name}")
                    # Continue to see all results
            except Exception as e:
                logger.error(f"Test error in {test_name}: {e}")
                results[test_name] = False

        # Final summary
        logger.info("\n" + "=" * 80)
        logger.info("DRESS REHEARSAL - FINAL RESULTS")
        logger.info("=" * 80)

        for test_name, passed in results.items():
            status = "PASS" if passed else "FAIL"
            symbol = "[OK]" if passed else "[FAIL]"
            logger.info(f"{symbol} {test_name}: {status}")

        total = len(results)
        passed_count = sum(results.values())
        logger.info(f"\nTotal: {passed_count}/{total} tests passed")

        if passed_count == total:
            logger.info("\nDRESS REHEARSAL: SUCCESS")
            logger.info("Complete autonomous pipeline validated!")
            return True
        else:
            logger.info("\nDRESS REHEARSAL: PARTIAL SUCCESS")
            logger.info(f"{total - passed_count} tests failed")
            return False


def main():
    """Main entry point"""
    output_dir = HIVE_ROOT / "tmp" / "colossus_dress_rehearsal"

    test = DressRehearsalTest(output_dir)
    success = test.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

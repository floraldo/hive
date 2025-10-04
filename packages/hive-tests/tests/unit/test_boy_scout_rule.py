"""
Boy Scout Rule Enforcement Test.

This test enforces the "leave code cleaner than you found it" principle by:
1. Tracking total linting violations over time
2. Failing if violations increase
3. Celebrating when violations decrease

Philosophy: Technical debt should only go DOWN, never UP.
"""

import subprocess
from pathlib import Path

import pytest


class TestBoyScoutRule:
    """Enforce Boy Scout Rule: Always leave code cleaner than you found it."""

    # Baseline: Current violation count (update when violations decrease)
    BASELINE_VIOLATIONS = 1058  # As of 2025-10-04 02:50 UTC after parallel agent cleanup (541 violations fixed!)

    def test_linting_violations_do_not_increase(self):
        """
        CRITICAL: Total linting violations must not increase.

        This test enforces the Boy Scout Rule by ensuring that:
        - New code doesn't introduce violations (format-on-save prevents this)
        - Edited files have violations fixed (Boy Scout Rule)
        - Overall technical debt trends downward

        **When this test fails**:
        - You introduced new violations - run `ruff check . --fix`
        - You edited a file without fixing its violations
        - Fix the violations in the files you touched

        **When violations decrease**:
        - Update BASELINE_VIOLATIONS to the new lower count
        - Celebrate the progress! 🎉
        """
        # Run ruff check and count violations
        result = subprocess.run(  # noqa: S607 - Intentional use of python subprocess
            ["python", "-m", "ruff", "check", "."],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # Replace unicode errors with ?
            cwd=Path(__file__).parent.parent.parent.parent.parent,  # Project root
        )

        # Extract violation count from output
        output = (result.stdout or "") + (result.stderr or "")

        # Parse "Found X errors" from ruff output
        violation_count = 0
        for line in output.split("\n"):
            if "Found" in line and "error" in line:
                # Extract number from "Found 1733 errors."
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "Found" and i + 1 < len(parts):
                        try:
                            violation_count = int(parts[i + 1])
                            break
                        except ValueError:
                            continue

        # Boy Scout Rule enforcement
        if violation_count > self.BASELINE_VIOLATIONS:
            pytest.fail(
                f"BOY SCOUT RULE VIOLATION\n\n"
                f"Linting violations INCREASED:\n"
                f"  Baseline: {self.BASELINE_VIOLATIONS} violations\n"
                f"  Current:  {violation_count} violations\n"
                f"  Increase: +{violation_count - self.BASELINE_VIOLATIONS}\n\n"
                f"ACTION REQUIRED:\n"
                f"1. Run: ruff check . --fix\n"
                f"2. Fix remaining violations in files you touched\n"
                f"3. Never use --no-verify to bypass this check\n\n"
                f"Remember: Always leave code cleaner than you found it!"
            )

        elif violation_count < self.BASELINE_VIOLATIONS:
            # Celebrate progress!
            improvement = self.BASELINE_VIOLATIONS - violation_count
            print(
                f"\nBOY SCOUT RULE SUCCESS!\n"
                f"Violations DECREASED by {improvement}!\n"
                f"  Before: {self.BASELINE_VIOLATIONS}\n"
                f"  After:  {violation_count}\n\n"
                f"ACTION REQUIRED:\n"
                f"Update BASELINE_VIOLATIONS in this test to {violation_count}\n"
            )

        else:
            # No change - that's OK
            print(
                f"\nBoy Scout Rule: No new violations\n"
                f"Current: {violation_count} violations (same as baseline)\n"
            )

    def test_syntax_errors_remain_zero(self):
        """
        CRITICAL: Syntax errors must remain at ZERO.

        Layer 1 achieved 0 syntax errors. This test ensures we never regress.
        """
        result = subprocess.run(  # noqa: S607 - Intentional use of python subprocess
            ["python", "-m", "compileall", "-q", "."],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent.parent,
        )

        # Count "Error compiling" occurrences
        error_count = result.stdout.count("Error compiling")

        if error_count > 0:
            pytest.fail(
                f"SYNTAX ERROR REGRESSION\n\n"
                f"Found {error_count} syntax errors!\n"
                f"Layer 1 achieved ZERO - we cannot regress.\n\n"
                f"Run: python -m compileall -q . 2>&1 | grep 'Error compiling'\n"
            )

    @pytest.mark.skip(reason="Aspirational - will enable when violations < 100")
    def test_zero_violations_achieved(self):
        """
        ASPIRATIONAL: All linting violations fixed.

        Enable this test when BASELINE_VIOLATIONS drops below 100.
        Ultimate goal: 0 violations via Boy Scout Rule.
        """
        result = subprocess.run(  # noqa: S607 - Intentional use of python subprocess
            ["python", "-m", "ruff", "check", "."],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent.parent,
        )

        assert result.returncode == 0, "All linting violations should be fixed!"  # noqa: S101 - pytest uses assert

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


@pytest.mark.core
class TestBoyScoutRule:
    """Enforce Boy Scout Rule: Always leave code cleaner than you found it."""
    BASELINE_VIOLATIONS = 1058

    @pytest.mark.core
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
        result = subprocess.run(['python', '-m', 'ruff', 'check', '.'], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=Path(__file__).parent.parent.parent.parent.parent)
        output = (result.stdout or '') + (result.stderr or '')
        violation_count = 0
        for line in output.split('\n'):
            if 'Found' in line and 'error' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'Found' and i + 1 < len(parts):
                        try:
                            violation_count = int(parts[i + 1])
                            break
                        except ValueError:
                            continue
        if violation_count > self.BASELINE_VIOLATIONS:
            pytest.fail(f'BOY SCOUT RULE VIOLATION\n\nLinting violations INCREASED:\n  Baseline: {self.BASELINE_VIOLATIONS} violations\n  Current:  {violation_count} violations\n  Increase: +{violation_count - self.BASELINE_VIOLATIONS}\n\nACTION REQUIRED:\n1. Run: ruff check . --fix\n2. Fix remaining violations in files you touched\n3. Never use --no-verify to bypass this check\n\nRemember: Always leave code cleaner than you found it!')
        elif violation_count < self.BASELINE_VIOLATIONS:
            improvement = self.BASELINE_VIOLATIONS - violation_count
            print(f'\nBOY SCOUT RULE SUCCESS!\nViolations DECREASED by {improvement}!\n  Before: {self.BASELINE_VIOLATIONS}\n  After:  {violation_count}\n\nACTION REQUIRED:\nUpdate BASELINE_VIOLATIONS in this test to {violation_count}\n')
        else:
            print(f'\nBoy Scout Rule: No new violations\nCurrent: {violation_count} violations (same as baseline)\n')

    @pytest.mark.core
    def test_syntax_errors_remain_zero(self):
        """
        CRITICAL: Syntax errors must remain at ZERO.

        Layer 1 achieved 0 syntax errors. This test ensures we never regress.
        """
        result = subprocess.run(['python', '-m', 'compileall', '-q', '.'], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent.parent.parent)
        error_count = result.stdout.count('Error compiling')
        if error_count > 0:
            pytest.fail(f"SYNTAX ERROR REGRESSION\n\nFound {error_count} syntax errors!\nLayer 1 achieved ZERO - we cannot regress.\n\nRun: python -m compileall -q . 2>&1 | grep 'Error compiling'\n")

    @pytest.mark.core
    @pytest.mark.skip(reason='Aspirational - will enable when violations < 100')
    def test_zero_violations_achieved(self):
        """
        ASPIRATIONAL: All linting violations fixed.

        Enable this test when BASELINE_VIOLATIONS drops below 100.
        Ultimate goal: 0 violations via Boy Scout Rule.
        """
        result = subprocess.run(['python', '-m', 'ruff', 'check', '.'], capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent.parent.parent)
        assert result.returncode == 0, 'All linting violations should be fixed!'

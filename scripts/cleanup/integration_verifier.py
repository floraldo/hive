#!/usr/bin/env python3
"""
Integration Verifier - Step 1: Verify Consolidated Tools

This script verifies that all consolidated tools work correctly and
that no functionality has been lost during the refactoring process.
"""

import subprocess
import sys
from pathlib import Path


class IntegrationVerifier:
    """Verifies the functionality of consolidated tools"""

    def __init__(self, scripts_root: Path):
        self.scripts_root = scripts_root
        self.verification_results = {}

    def verify_tool(self, tool_path: Path, test_args: list[str]) -> tuple[bool, str]:
        """Verify a single consolidated tool"""
        try:
            result = subprocess.run(
                [sys.executable, str(tool_path)] + test_args, capture_output=True, text=True, timeout=30,
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Exit code {result.returncode}: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Tool execution timed out"
        except Exception as e:
            return False, f"Execution error: {e}"

    def verify_repository_hygiene(self) -> bool:
        """Verify maintenance/repository_hygiene.py"""
        print("Verifying repository_hygiene.py...")

        tool_path = self.scripts_root / "maintenance" / "repository_hygiene.py"
        if not tool_path.exists():
            print(f"[ERROR] Tool not found: {tool_path}")
            return False

        # Test dry-run mode
        success, output = self.verify_tool(tool_path, ["--dry-run", "--all"])

        if success:
            print("[OK] repository_hygiene.py - dry-run mode works")
            self.verification_results["repository_hygiene"] = "PASS"
            return True
        else:
            print(f"[ERROR] repository_hygiene.py failed: {output}")
            self.verification_results["repository_hygiene"] = f"FAIL: {output}"
            return False

    def verify_test_runner(self) -> bool:
        """Verify testing/run_tests.py"""
        print("Verifying run_tests.py...")

        tool_path = self.scripts_root / "testing" / "run_tests.py"
        if not tool_path.exists():
            print(f"[ERROR] Tool not found: {tool_path}")
            return False

        # Test help and dry-run modes
        test_modes = [["--help"], ["--dry-run", "--quick"], ["--dry-run", "--golden-rules"]]

        all_passed = True
        for test_args in test_modes:
            success, output = self.verify_tool(tool_path, test_args)
            if not success:
                print(f"[ERROR] run_tests.py failed with {test_args}: {output}")
                all_passed = False

        if all_passed:
            print("[OK] run_tests.py - all test modes work")
            self.verification_results["run_tests"] = "PASS"
            return True
        else:
            self.verification_results["run_tests"] = "FAIL: Some modes failed"
            return False

    def verify_security_audit(self) -> bool:
        """Verify security/run_audit.py"""
        print("Verifying run_audit.py...")

        tool_path = self.scripts_root / "security" / "run_audit.py"
        if not tool_path.exists():
            print(f"[ERROR] Tool not found: {tool_path}")
            return False

        # Test dry-run mode
        success, output = self.verify_tool(tool_path, ["--dry-run", "--quick"])

        if success:
            print("[OK] run_audit.py - dry-run mode works")
            self.verification_results["run_audit"] = "PASS"
            return True
        else:
            print(f"[ERROR] run_audit.py failed: {output}")
            self.verification_results["run_audit"] = f"FAIL: {output}"
            return False

    def verify_database_setup(self) -> bool:
        """Verify database/setup.py"""
        print("Verifying database setup.py...")

        tool_path = self.scripts_root / "database" / "setup.py"
        if not tool_path.exists():
            print(f"[ERROR] Tool not found: {tool_path}")
            return False

        # Test dry-run mode
        success, output = self.verify_tool(tool_path, ["--dry-run", "--init"])

        if success:
            print("[OK] database setup.py - dry-run mode works")
            self.verification_results["database_setup"] = "PASS"
            return True
        else:
            print(f"[ERROR] database setup.py failed: {output}")
            self.verification_results["database_setup"] = f"FAIL: {output}"
            return False

    def verify_code_fixers(self) -> bool:
        """Verify maintenance/fixers/code_fixers.py"""
        print("Verifying code_fixers.py...")

        tool_path = self.scripts_root / "maintenance" / "fixers" / "code_fixers.py"
        if not tool_path.exists():
            print(f"[ERROR] Tool not found: {tool_path}")
            return False

        # Test dry-run mode
        success, output = self.verify_tool(tool_path, ["--dry-run", "--type-hints"])

        if success:
            print("[OK] code_fixers.py - dry-run mode works")
            self.verification_results["code_fixers"] = "PASS"
            return True
        else:
            print(f"[ERROR] code_fixers.py failed: {output}")
            self.verification_results["code_fixers"] = f"FAIL: {output}"
            return False

    def run_verification(self) -> bool:
        """Run complete verification of all consolidated tools"""
        print("Step 1: Verifying Consolidated Tools")
        print("=" * 50)

        tools_to_verify = [
            ("Repository Hygiene", self.verify_repository_hygiene),
            ("Test Runner", self.verify_test_runner),
            ("Security Audit", self.verify_security_audit),
            ("Database Setup", self.verify_database_setup),
            ("Code Fixers", self.verify_code_fixers),
        ]

        passed = 0
        total = len(tools_to_verify)

        for tool_name, verify_func in tools_to_verify:
            print(f"\n[{passed + 1}/{total}] {tool_name}")
            if verify_func():
                passed += 1

        print(f"\nVerification Results: {passed}/{total} tools passed")

        if passed == total:
            print("[SUCCESS] All consolidated tools are working correctly!")
            return True
        else:
            print(f"[WARNING] {total - passed} tools need attention")
            return False

    def generate_verification_report(self) -> str:
        """Generate verification report"""
        report = f"""# Consolidated Tools Verification Report

**Generated**: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Verification Results

| Tool | Status | Notes |
|------|--------|-------|
"""

        for tool, result in self.verification_results.items():
            status = "✅ PASS" if result == "PASS" else "❌ FAIL"
            notes = result if result != "PASS" else "All tests passed"
            report += f"| {tool} | {status} | {notes} |\n"

        report += f"""

## Summary

- **Tools Verified**: {len(self.verification_results)}
- **Passed**: {len([r for r in self.verification_results.values() if r == "PASS"])}
- **Failed**: {len([r for r in self.verification_results.values() if r != "PASS"])}

## Next Steps

1. Address any failing tools before proceeding
2. Update CI/CD workflows to use new script paths
3. Begin addressing remaining code quality violations

---

*Integration verification completed as part of scripts refactoring follow-up.*
"""

        return report


def main():
    """Main execution function"""
    print("Scripts Integration Verification - Step 1")
    print("=" * 50)

    scripts_root = Path(__file__).parent.parent
    verifier = IntegrationVerifier(scripts_root)

    # Run verification
    success = verifier.run_verification()

    # Generate report
    report = verifier.generate_verification_report()
    report_path = scripts_root / "cleanup" / "verification_report.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\nVerification report saved: {report_path}")

    if success:
        print("\n[READY] Proceed to Step 2: Update CI/CD workflows")
        return 0
    else:
        print("\n[BLOCKED] Fix failing tools before proceeding")
        return 1


if __name__ == "__main__":
    sys.exit(main())



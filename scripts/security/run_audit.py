#!/usr/bin/env python3
"""
Security Audit Runner - Consolidated Security Tool

This script consolidates the functionality of multiple security scripts:
- audit_dependencies.py
- security_check.py
- security_audit.py

Features:
- Comprehensive security scanning
- Quick security checks
- Vulnerability reporting
- File permission validation
- Secret scanning
- Configuration compliance

Usage:
    python run_audit.py --help
    python run_audit.py --quick
    python run_audit.py --all
"""

import argparse
import json
import os
import re
import stat
import sys
from datetime import datetime
from pathlib import Path


class SecurityAuditResult:
    """Result of a security audit check"""

    def __init__(self, check_name: str, status: str, message: str, severity: str = "INFO", details: dict = None):
        self.check_name = check_name
        self.status = status
        self.message = message
        self.severity = severity
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()


class SecurityAuditor:
    """Consolidated security auditor for Hive platform"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.audit_results: list[SecurityAuditResult] = []

        self.sensitive_file_patterns = [
            r"\.env\.?.*",
            r".*\.key$",
            r".*\.pem$",
            r".*_rsa$",
            r"id_rsa.*",
            r"secrets\..*",
        ]

        self.secret_patterns = [
            (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', "API Key"),
            (r'(?i)(secret[_-]?key|secretkey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', "Secret Key"),
            (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', "Password"),
            (r'(?i)(token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?', "Token"),
        ]

    def run_quick_checks(self) -> bool:
        """Run quick security checks"""
        print("Security Quick Check")
        print("=" * 60)

        self.audit_file_permissions()
        self.audit_environment_variables()

        return self._report_results()

    def run_comprehensive_audit(self) -> bool:
        """Run comprehensive security audit"""
        print("Comprehensive Security Audit")
        print("=" * 80)

        self.audit_file_permissions()
        self.audit_environment_variables()
        self.scan_logs_for_secrets()
        self.audit_configuration_compliance()

        return self._report_results()

    def audit_file_permissions(self) -> None:
        """Audit file permissions for sensitive files"""
        print("Auditing file permissions...")

        sensitive_files = []
        for pattern in self.sensitive_file_patterns:
            for file_path in self.project_root.rglob("*"):
                if file_path.is_file() and re.match(pattern, file_path.name, re.IGNORECASE):
                    sensitive_files.append(file_path)

        if not sensitive_files:
            self.audit_results.append(
                SecurityAuditResult("file_permissions", "PASS", "No sensitive files found", "INFO")
            )
            return

        for file_path in sensitive_files:
            try:
                file_stat = file_path.stat()
                file_mode = stat.filemode(file_stat.st_mode)

                if file_stat.st_mode & stat.S_IROTH:
                    self.audit_results.append(
                        SecurityAuditResult(
                            "file_permissions",
                            "FAIL",
                            f"Sensitive file {file_path.name} is readable by others ({file_mode})",
                            "HIGH",
                            {"file_path": str(file_path), "permissions": file_mode},
                        )
                    )
                else:
                    self.audit_results.append(
                        SecurityAuditResult(
                            "file_permissions",
                            "PASS",
                            f"Sensitive file {file_path.name} has secure permissions",
                            "INFO",
                        )
                    )

            except Exception as e:
                self.audit_results.append(
                    SecurityAuditResult("file_permissions", "FAIL", f"Error checking permissions: {str(e)}", "MEDIUM")
                )

    def audit_environment_variables(self) -> None:
        """Audit environment variables for security issues"""
        print("Auditing environment variables...")

        env_vars = dict(os.environ)
        suspicious_vars = []

        for var_name, var_value in env_vars.items():
            var_name_lower = var_name.lower()

            if any(pattern in var_name_lower for pattern in ["password", "secret", "key", "token"]):
                suspicious_vars.append(var_name)

        if suspicious_vars:
            self.audit_results.append(
                SecurityAuditResult(
                    "environment_variables",
                    "WARNING",
                    f"Found {len(suspicious_vars)} suspicious environment variables",
                    "MEDIUM",
                    {"suspicious_vars": suspicious_vars},
                )
            )
        else:
            self.audit_results.append(
                SecurityAuditResult("environment_variables", "PASS", "No suspicious environment variables", "INFO")
            )

    def scan_logs_for_secrets(self, max_files: int = 10) -> None:
        """Scan log files for accidentally leaked secrets"""
        print("Scanning logs for leaked secrets...")

        log_files = []
        for pattern in ["*.log", "*.out", "*.err"]:
            log_files.extend(self.project_root.rglob(pattern))

        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        log_files = log_files[:max_files]

        if not log_files:
            self.audit_results.append(SecurityAuditResult("log_secret_scan", "SKIP", "No log files found", "INFO"))
            return

        leaked_secrets = []

        for log_file in log_files:
            try:
                with open(log_file, encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if line_num > 1000:
                            break

                        for pattern, secret_type in self.secret_patterns:
                            matches = re.finditer(pattern, line)
                            for match in matches:
                                secret_value = match.group(2) if len(match.groups()) >= 2 else match.group(1)
                                masked_value = secret_value[:4] + "*" * (len(secret_value) - 4)

                                leaked_secrets.append(
                                    {
                                        "file": str(log_file.relative_to(self.project_root)),
                                        "line": line_num,
                                        "type": secret_type,
                                        "masked_value": masked_value,
                                    }
                                )

            except Exception:
                pass

        if leaked_secrets:
            self.audit_results.append(
                SecurityAuditResult(
                    "log_secret_scan",
                    "FAIL",
                    f"Found {len(leaked_secrets)} potential secret leaks",
                    "CRITICAL",
                    {"leaked_secrets": leaked_secrets},
                )
            )
        else:
            self.audit_results.append(
                SecurityAuditResult("log_secret_scan", "PASS", f"No secrets found in {len(log_files)} files", "INFO")
            )

    def audit_configuration_compliance(self) -> None:
        """Audit configuration files for security compliance"""
        print("Auditing configuration compliance...")

        compliance_issues = []
        config_files = []

        for pattern in ["*.json", "*.yaml", "*.yml", "*.toml"]:
            config_files.extend(self.project_root.rglob(pattern))

        for config_file in config_files[:50]:
            try:
                with open(config_file, encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()

                    insecure_patterns = [
                        (r"debug\s*[:=]\s*true", "Debug mode enabled"),
                        (r"ssl\s*[:=]\s*false", "SSL disabled"),
                        (r"verify\s*[:=]\s*false", "Certificate verification disabled"),
                    ]

                    for pattern, description in insecure_patterns:
                        if re.search(pattern, content):
                            compliance_issues.append(
                                {
                                    "file": str(config_file.relative_to(self.project_root)),
                                    "issue": description,
                                    "severity": "HIGH" if "ssl" in description.lower() else "MEDIUM",
                                }
                            )

            except Exception:
                pass

        if compliance_issues:
            high_severity = [issue for issue in compliance_issues if issue["severity"] == "HIGH"]
            if high_severity:
                self.audit_results.append(
                    SecurityAuditResult(
                        "configuration_compliance",
                        "FAIL",
                        f"Found {len(high_severity)} high-severity issues",
                        "HIGH",
                        {"issues": compliance_issues},
                    )
                )
            else:
                self.audit_results.append(
                    SecurityAuditResult(
                        "configuration_compliance",
                        "WARNING",
                        f"Found {len(compliance_issues)} compliance issues",
                        "MEDIUM",
                        {"issues": compliance_issues},
                    )
                )
        else:
            self.audit_results.append(
                SecurityAuditResult("configuration_compliance", "PASS", "No compliance issues detected", "INFO")
            )

    def _report_results(self) -> bool:
        """Report audit results"""
        critical_count = len([r for r in self.audit_results if r.severity == "CRITICAL"])
        high_count = len([r for r in self.audit_results if r.severity == "HIGH"])
        failed_count = len([r for r in self.audit_results if r.status == "FAIL"])
        passed_count = len([r for r in self.audit_results if r.status == "PASS"])

        print("\n" + "=" * 80)
        print("SECURITY AUDIT SUMMARY")
        print("=" * 80)
        print(f"Total Checks: {len(self.audit_results)}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {failed_count}")
        print(f"Critical Issues: {critical_count}")
        print(f"High Severity: {high_count}")

        if critical_count > 0:
            print("\nCRITICAL SECURITY ISSUES DETECTED!")
            for result in self.audit_results:
                if result.severity == "CRITICAL":
                    print(f"  - {result.check_name}: {result.message}")
        elif failed_count > 0:
            print("\nSecurity issues found - review required")
        else:
            print("\nAll security checks passed!")

        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_checks": len(self.audit_results),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "critical_count": critical_count,
            "results": [
                {
                    "check_name": r.check_name,
                    "status": r.status,
                    "message": r.message,
                    "severity": r.severity,
                    "details": r.details,
                }
                for r in self.audit_results
            ],
        }

        report_file = self.project_root / "security_audit_report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\nReport saved to: {report_file}")

        return critical_count == 0 and failed_count == 0


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Security Audit Runner")
    parser.add_argument("--version", action="version", version="1.0.0")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--quick", action="store_true", help="Run quick security checks")
    parser.add_argument("--comprehensive", action="store_true", help="Run comprehensive security audit")
    parser.add_argument("--all", action="store_true", help="Run all security audits")

    args = parser.parse_args()

    if not any([args.quick, args.comprehensive, args.all]):
        parser.print_help()
        return 0

    project_root = Path(__file__).parent.parent.parent
    auditor = SecurityAuditor(project_root)

    if args.dry_run:
        print("DRY RUN: No security audits would be executed.")
        return 0

    success = True

    try:
        if args.all or args.quick:
            success &= auditor.run_quick_checks()

        if args.all or args.comprehensive:
            success &= auditor.run_comprehensive_audit()

    except Exception as e:
        print(f"\nSecurity audit failed: {e}")
        return 1

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

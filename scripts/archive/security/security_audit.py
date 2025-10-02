#!/usr/bin/env python3
"""
Post-Deployment Security & Configuration Audit

Automated security and configuration verification for deployed applications:
- File permission validation for sensitive files
- Environment variable security checks
- Log scanning for leaked secrets
- Configuration compliance verification
- SSL/TLS certificate validation

Part of the Production Shield Initiative for deployment security hardening.
"""

import argparse
import json
import os
import re
import socket
import ssl
import stat
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse


class SecurityAuditResult:
    """Result of a security audit check"""

    def __init__(self, check_name: str, status: str, message: str, severity: str = "INFO", details: Dict = None):
        self.check_name = check_name
        self.status = status  # PASS, FAIL, WARNING, SKIP
        self.message = message
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW, INFO
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()


class PostDeploymentSecurityAuditor:
    def __init__(self, deployment_path: Path = None, environment: str = "production"):
        self.deployment_path = deployment_path or Path.cwd()
        self.environment = environment
        self.audit_results: List[SecurityAuditResult] = []

        # Sensitive file patterns
        self.sensitive_file_patterns = [
            r"\.env\.?.*",
            r".*\.key$",
            r".*\.pem$",
            r".*\.p12$",
            r".*\.jks$",
            r"config\.json$",
            r"secrets\..*",
            r".*_rsa$",
            r".*_dsa$",
            r".*_ecdsa$",
            r"id_rsa.*",
            r"id_dsa.*",
        ]

        # Secret patterns to scan for in logs
        self.secret_patterns = [
            (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', "API Key"),
            (r'(?i)(secret[_-]?key|secretkey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', "Secret Key"),
            (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', "Password"),
            (r'(?i)(token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?', "Token"),
            (r"(?i)(bearer\s+)([a-zA-Z0-9_\-\.]{20,})", "Bearer Token"),
            (r"(?i)(basic\s+)([a-zA-Z0-9+/=]{20,})", "Basic Auth"),
            (r'(?i)(private[_-]?key)\s*[:=]\s*["\']?([^\s"\']{50,})["\']?', "Private Key"),
            (r'(?i)(database[_-]?url|db[_-]?url)\s*[:=]\s*["\']?([^\s"\']+)["\']?', "Database URL"),
            (r'(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[:=]\s*["\']?([A-Z0-9]{20})["\']?', "AWS Access Key"),
            (r'(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*["\']?([a-zA-Z0-9+/]{40})["\']?', "AWS Secret Key"),
        ]

        # Required security headers
        self.required_security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy",
        ]

    def audit_file_permissions(self) -> None:
        """Audit file permissions for sensitive files"""
        print("🔒 Auditing file permissions...")

        sensitive_files = []

        # Find sensitive files
        for pattern in self.sensitive_file_patterns:
            for file_path in self.deployment_path.rglob("*"):
                if file_path.is_file() and re.match(pattern, file_path.name, re.IGNORECASE):
                    sensitive_files.append(file_path)

        if not sensitive_files:
            self.audit_results.append(
                SecurityAuditResult(
                    "file_permissions", "PASS", "No sensitive files found requiring permission checks", "INFO"
                )
            )
            return

        for file_path in sensitive_files:
            try:
                file_stat = file_path.stat()
                file_mode = stat.filemode(file_stat.st_mode)
                octal_perms = oct(file_stat.st_mode)[-3:]

                # Check if file is readable by others
                if file_stat.st_mode & stat.S_IROTH:
                    self.audit_results.append(
                        SecurityAuditResult(
                            "file_permissions",
                            "FAIL",
                            f"Sensitive file {file_path.name} is readable by others ({file_mode})",
                            "HIGH",
                            {"file_path": str(file_path), "permissions": file_mode, "octal": octal_perms},
                        )
                    )
                elif file_stat.st_mode & stat.S_IRGRP:
                    self.audit_results.append(
                        SecurityAuditResult(
                            "file_permissions",
                            "WARNING",
                            f"Sensitive file {file_path.name} is readable by group ({file_mode})",
                            "MEDIUM",
                            {"file_path": str(file_path), "permissions": file_mode, "octal": octal_perms},
                        )
                    )
                else:
                    self.audit_results.append(
                        SecurityAuditResult(
                            "file_permissions",
                            "PASS",
                            f"Sensitive file {file_path.name} has secure permissions ({file_mode})",
                            "INFO",
                            {"file_path": str(file_path), "permissions": file_mode, "octal": octal_perms},
                        )
                    )

            except Exception as e:
                self.audit_results.append(
                    SecurityAuditResult(
                        "file_permissions",
                        "FAIL",
                        f"Error checking permissions for {file_path.name}: {str(e)}",
                        "MEDIUM",
                    )
                )

    def audit_environment_variables(self) -> None:
        """Audit environment variables for security issues"""
        print("🌍 Auditing environment variables...")

        # Check for unencrypted secrets in environment
        env_vars = dict(os.environ)

        suspicious_vars = []
        unencrypted_secrets = []

        for var_name, var_value in env_vars.items():
            var_name_lower = var_name.lower()

            # Check for suspicious variable names
            if any(pattern in var_name_lower for pattern in ["password", "secret", "key", "token"]):
                suspicious_vars.append(var_name)

                # Check if value looks like an unencrypted secret
                if (
                    len(var_value) > 8
                    and not var_value.startswith(("encrypted:", "vault:", "${"))
                    and not var_value.startswith("/")  # Not a file path
                    and re.match(r"^[a-zA-Z0-9_\-\.+/=]+$", var_value)
                ):  # Looks like a secret
                    unencrypted_secrets.append(var_name)

        if unencrypted_secrets:
            self.audit_results.append(
                SecurityAuditResult(
                    "environment_variables",
                    "FAIL",
                    f"Found {len(unencrypted_secrets)} potentially unencrypted secrets in environment",
                    "CRITICAL",
                    {"unencrypted_secrets": unencrypted_secrets},
                )
            )
        elif suspicious_vars:
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
                SecurityAuditResult(
                    "environment_variables", "PASS", "No suspicious environment variables detected", "INFO"
                )
            )

        # Check for development environment variables in production
        if self.environment == "production":
            dev_vars = [
                var for var in env_vars.keys() if any(pattern in var.lower() for pattern in ["debug", "dev", "test"])
            ]

            if dev_vars:
                self.audit_results.append(
                    SecurityAuditResult(
                        "environment_variables",
                        "WARNING",
                        f'Development variables found in production: {", ".join(dev_vars)}',
                        "MEDIUM",
                        {"dev_vars": dev_vars},
                    )
                )

    def scan_logs_for_secrets(self, max_files: int = 10, max_lines_per_file: int = 1000) -> None:
        """Scan log files for accidentally leaked secrets"""
        print("📋 Scanning logs for leaked secrets...")

        log_files = []

        # Find log files
        for pattern in ["*.log", "*.out", "*.err"]:
            log_files.extend(self.deployment_path.rglob(pattern))

        # Sort by modification time (newest first) and limit
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        log_files = log_files[:max_files]

        if not log_files:
            self.audit_results.append(
                SecurityAuditResult("log_secret_scan", "SKIP", "No log files found to scan", "INFO")
            )
            return

        leaked_secrets = []

        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines_read = 0
                    for line_num, line in enumerate(f, 1):
                        if lines_read >= max_lines_per_file:
                            break

                        # Check for secret patterns
                        for pattern, secret_type in self.secret_patterns:
                            matches = re.finditer(pattern, line)
                            for match in matches:
                                # Mask the secret value
                                secret_value = match.group(2) if len(match.groups()) >= 2 else match.group(1)
                                masked_value = secret_value[:4] + "*" * (len(secret_value) - 4)

                                leaked_secrets.append(
                                    {
                                        "file": str(log_file.relative_to(self.deployment_path)),
                                        "line": line_num,
                                        "type": secret_type,
                                        "masked_value": masked_value,
                                        "context": line.strip()[:100],
                                    }
                                )

                        lines_read += 1

            except Exception as e:
                print(f"Error scanning {log_file}: {e}")

        if leaked_secrets:
            self.audit_results.append(
                SecurityAuditResult(
                    "log_secret_scan",
                    "FAIL",
                    f"Found {len(leaked_secrets)} potential secret leaks in log files",
                    "CRITICAL",
                    {"leaked_secrets": leaked_secrets},
                )
            )
        else:
            self.audit_results.append(
                SecurityAuditResult(
                    "log_secret_scan",
                    "PASS",
                    f"No secrets found in {len(log_files)} log files scanned",
                    "INFO",
                    {"files_scanned": len(log_files)},
                )
            )

    def audit_ssl_certificates(self, endpoints: List[str] = None) -> None:
        """Audit SSL certificates for configured endpoints"""
        print("🔐 Auditing SSL certificates...")

        if not endpoints:
            # Try to discover endpoints from configuration
            endpoints = self._discover_https_endpoints()

        if not endpoints:
            self.audit_results.append(
                SecurityAuditResult("ssl_certificates", "SKIP", "No HTTPS endpoints configured for SSL audit", "INFO")
            )
            return

        for endpoint in endpoints:
            try:
                parsed_url = urlparse(endpoint)
                hostname = parsed_url.hostname
                port = parsed_url.port or 443

                # Get SSL certificate
                context = ssl.create_default_context()
                with socket.create_connection((hostname, port), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                        cert = ssock.getpeercert()

                # Check certificate expiration
                not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                days_until_expiry = (not_after - datetime.now()).days

                if days_until_expiry < 7:
                    self.audit_results.append(
                        SecurityAuditResult(
                            "ssl_certificates",
                            "FAIL",
                            f"SSL certificate for {hostname} expires in {days_until_expiry} days",
                            "CRITICAL",
                            {"hostname": hostname, "expiry_date": cert["notAfter"], "days_left": days_until_expiry},
                        )
                    )
                elif days_until_expiry < 30:
                    self.audit_results.append(
                        SecurityAuditResult(
                            "ssl_certificates",
                            "WARNING",
                            f"SSL certificate for {hostname} expires in {days_until_expiry} days",
                            "HIGH",
                            {"hostname": hostname, "expiry_date": cert["notAfter"], "days_left": days_until_expiry},
                        )
                    )
                else:
                    self.audit_results.append(
                        SecurityAuditResult(
                            "ssl_certificates",
                            "PASS",
                            f"SSL certificate for {hostname} is valid for {days_until_expiry} days",
                            "INFO",
                            {"hostname": hostname, "expiry_date": cert["notAfter"], "days_left": days_until_expiry},
                        )
                    )

            except Exception as e:
                self.audit_results.append(
                    SecurityAuditResult(
                        "ssl_certificates",
                        "FAIL",
                        f"Error checking SSL certificate for {endpoint}: {str(e)}",
                        "MEDIUM",
                        {"endpoint": endpoint, "error": str(e)},
                    )
                )

    def _discover_https_endpoints(self) -> List[str]:
        """Discover HTTPS endpoints from configuration files"""
        endpoints = []

        # Look for common configuration files
        config_patterns = ["*.json", "*.yaml", "*.yml", "*.toml", ".env*"]

        for pattern in config_patterns:
            for config_file in self.deployment_path.rglob(pattern):
                try:
                    with open(config_file, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                        # Find HTTPS URLs
                        https_urls = re.findall(r'https://[^\s"\']+', content)
                        endpoints.extend(https_urls)

                except Exception:
                    continue

        # Remove duplicates and filter out obvious non-endpoints
        unique_endpoints = list(set(endpoints))
        filtered_endpoints = [
            ep
            for ep in unique_endpoints
            if not any(exclude in ep.lower() for exclude in ["github.com", "example.com", "localhost"])
        ]

        return filtered_endpoints[:5]  # Limit to 5 endpoints

    def audit_configuration_compliance(self) -> None:
        """Audit configuration files for security compliance"""
        print("⚙️ Auditing configuration compliance...")

        compliance_issues = []

        # Check for common configuration files
        config_files = []
        for pattern in ["*.json", "*.yaml", "*.yml", "*.toml"]:
            config_files.extend(self.deployment_path.rglob(pattern))

        for config_file in config_files:
            try:
                with open(config_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()

                    # Check for insecure configurations
                    insecure_patterns = [
                        (r"debug\s*[:=]\s*true", "Debug mode enabled"),
                        (r"ssl\s*[:=]\s*false", "SSL disabled"),
                        (r"verify\s*[:=]\s*false", "Certificate verification disabled"),
                        (r"allow_origins\s*[:=]\s*\*", "CORS allows all origins"),
                        (r"trust_all\s*[:=]\s*true", "Trust all certificates enabled"),
                        (r"insecure\s*[:=]\s*true", "Insecure mode enabled"),
                    ]

                    for pattern, description in insecure_patterns:
                        if re.search(pattern, content):
                            compliance_issues.append(
                                {
                                    "file": str(config_file.relative_to(self.deployment_path)),
                                    "issue": description,
                                    "severity": "HIGH" if "ssl" in description.lower() else "MEDIUM",
                                }
                            )

            except Exception as e:
                print(f"Error checking {config_file}: {e}")

        if compliance_issues:
            high_severity = [issue for issue in compliance_issues if issue["severity"] == "HIGH"]
            if high_severity:
                self.audit_results.append(
                    SecurityAuditResult(
                        "configuration_compliance",
                        "FAIL",
                        f"Found {len(high_severity)} high-severity configuration issues",
                        "HIGH",
                        {"issues": compliance_issues},
                    )
                )
            else:
                self.audit_results.append(
                    SecurityAuditResult(
                        "configuration_compliance",
                        "WARNING",
                        f"Found {len(compliance_issues)} configuration compliance issues",
                        "MEDIUM",
                        {"issues": compliance_issues},
                    )
                )
        else:
            self.audit_results.append(
                SecurityAuditResult(
                    "configuration_compliance", "PASS", "No configuration compliance issues detected", "INFO"
                )
            )

    def run_full_audit(self, endpoints: List[str] = None) -> None:
        """Run complete security audit"""
        print(f"🛡️ Starting security audit for {self.environment} environment")
        print(f"📁 Audit path: {self.deployment_path}")
        print("=" * 80)

        # Run all audit checks
        self.audit_file_permissions()
        self.audit_environment_variables()
        self.scan_logs_for_secrets()
        self.audit_ssl_certificates(endpoints)
        self.audit_configuration_compliance()

        print("\n" + "=" * 80)
        print("🔍 Security audit completed")

    def generate_audit_report(self) -> str:
        """Generate comprehensive security audit report"""
        # Categorize results
        critical_issues = [r for r in self.audit_results if r.severity == "CRITICAL"]
        high_issues = [r for r in self.audit_results if r.severity == "HIGH"]
        medium_issues = [r for r in self.audit_results if r.severity == "MEDIUM"]
        low_issues = [r for r in self.audit_results if r.severity == "LOW"]

        failed_checks = [r for r in self.audit_results if r.status == "FAIL"]
        warning_checks = [r for r in self.audit_results if r.status == "WARNING"]
        passed_checks = [r for r in self.audit_results if r.status == "PASS"]

        report_lines = []

        # Header
        report_lines.extend(
            [
                "# 🛡️ Post-Deployment Security Audit Report",
                "",
                f"**Audit Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                f"**Environment**: {self.environment}",
                f"**Deployment Path**: {self.deployment_path}",
                "",
                "## 📊 Executive Summary",
                "",
                f"- **Total Checks**: {len(self.audit_results)}",
                f"- **Passed**: {len(passed_checks)}",
                f"- **Warnings**: {len(warning_checks)}",
                f"- **Failed**: {len(failed_checks)}",
                "",
                f"- **Critical Issues**: {len(critical_issues)}",
                f"- **High Severity**: {len(high_issues)}",
                f"- **Medium Severity**: {len(medium_issues)}",
                f"- **Low Severity**: {len(low_issues)}",
                "",
            ]
        )

        # Overall status
        if critical_issues or failed_checks:
            report_lines.extend(
                [
                    "## 🚨 Overall Status: FAILED",
                    "",
                    "**Deployment should be reviewed immediately due to critical security issues.**",
                    "",
                ]
            )
        elif high_issues or len(warning_checks) > 2:
            report_lines.extend(
                [
                    "## ⚠️ Overall Status: WARNING",
                    "",
                    "**Deployment has security concerns that should be addressed.**",
                    "",
                ]
            )
        else:
            report_lines.extend(["## ✅ Overall Status: PASSED", "", "**Deployment meets security requirements.**", ""])

        # Critical Issues
        if critical_issues:
            report_lines.extend(["## 🚨 Critical Security Issues", ""])

            for issue in critical_issues:
                report_lines.extend(
                    [
                        f"### {issue.check_name.replace('_', ' ').title()}",
                        f"- **Status**: {issue.status}",
                        f"- **Message**: {issue.message}",
                        f"- **Severity**: {issue.severity}",
                        "",
                    ]
                )

                if issue.details:
                    if "leaked_secrets" in issue.details:
                        report_lines.append("**Leaked Secrets:**")
                        for secret in issue.details["leaked_secrets"][:5]:
                            report_lines.append(f"  - {secret['type']} in {secret['file']}:{secret['line']}")
                        report_lines.append("")

                    if "unencrypted_secrets" in issue.details:
                        report_lines.append(
                            f"**Unencrypted Variables**: {', '.join(issue.details['unencrypted_secrets'])}"
                        )
                        report_lines.append("")

        # High Severity Issues
        if high_issues:
            report_lines.extend(["## ⚠️ High Severity Issues", ""])

            for issue in high_issues:
                report_lines.extend(
                    [f"### {issue.check_name.replace('_', ' ').title()}", f"- **Message**: {issue.message}", ""]
                )

        # Security Check Details
        report_lines.extend(["## 🔍 Detailed Security Check Results", ""])

        # Group by check type
        checks_by_type = {}
        for result in self.audit_results:
            if result.check_name not in checks_by_type:
                checks_by_type[result.check_name] = []
            checks_by_type[result.check_name].append(result)

        for check_type, results in checks_by_type.items():
            report_lines.append(f"### {check_type.replace('_', ' ').title()}")

            for result in results:
                status_emoji = {"PASS": "✅", "FAIL": "❌", "WARNING": "⚠️", "SKIP": "⏭️"}.get(result.status, "❓")

                report_lines.append(f"{status_emoji} **{result.status}**: {result.message}")

            report_lines.append("")

        # Recommendations
        report_lines.extend(["## 🎯 Security Recommendations", ""])

        if critical_issues:
            report_lines.extend(
                [
                    "### Immediate Actions (Critical)",
                    "1. **Stop deployment** if not already in production",
                    "2. **Rotate any leaked secrets** immediately",
                    "3. **Fix file permissions** on sensitive files",
                    "4. **Review environment variables** for unencrypted secrets",
                    "",
                ]
            )

        if high_issues:
            report_lines.extend(
                [
                    "### High Priority Actions",
                    "1. **Review SSL certificate expiration** dates",
                    "2. **Update insecure configurations** in config files",
                    "3. **Implement proper secret management**",
                    "",
                ]
            )

        report_lines.extend(
            [
                "### General Security Best Practices",
                "1. **Regular security audits** should be automated in CI/CD",
                "2. **Secret management** should use encrypted storage",
                "3. **File permissions** should follow principle of least privilege",
                "4. **SSL certificates** should be monitored for expiration",
                "5. **Configuration files** should be reviewed for security settings",
                "",
                "---",
                "",
                "*This audit report is generated automatically by the Production Shield Security Auditor.*",
                "*For immediate security concerns, escalate to the security team.*",
            ]
        )

        return "\n".join(report_lines)

    def save_audit_results(self) -> None:
        """Save audit results to files"""
        # Save JSON results
        results_data = {
            "audit_timestamp": datetime.now().isoformat(),
            "environment": self.environment,
            "deployment_path": str(self.deployment_path),
            "total_checks": len(self.audit_results),
            "results": [
                {
                    "check_name": r.check_name,
                    "status": r.status,
                    "message": r.message,
                    "severity": r.severity,
                    "details": r.details,
                    "timestamp": r.timestamp,
                }
                for r in self.audit_results
            ],
        }

        results_path = Path("security_audit_results.json")
        with open(results_path, "w") as f:
            json.dump(results_data, f, indent=2)

        # Save audit report
        report = self.generate_audit_report()
        report_path = Path("security_audit_report.md")
        with open(report_path, "w") as f:
            f.write(report)

        print(f"Audit results saved to: {results_path}")
        print(f"Audit report saved to: {report_path}")

        # Set GitHub Actions outputs
        critical_count = len([r for r in self.audit_results if r.severity == "CRITICAL"])
        failed_count = len([r for r in self.audit_results if r.status == "FAIL"])

        if os.getenv("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"has_critical_issues={'true' if critical_count > 0 else 'false'}\n")
                f.write(f"has_failures={'true' if failed_count > 0 else 'false'}\n")
                f.write(f"critical_count={critical_count}\n")
                f.write(f"failed_count={failed_count}\n")
                f.write(f"audit_status={'FAILED' if critical_count > 0 or failed_count > 0 else 'PASSED'}\n")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Post-Deployment Security Auditor")
    parser.add_argument("--deployment-path", type=Path, default=Path.cwd(), help="Path to deployed application")
    parser.add_argument(
        "--environment",
        choices=["production", "staging", "development"],
        default="production",
        help="Deployment environment",
    )
    parser.add_argument("--endpoints", nargs="+", help="HTTPS endpoints to audit")
    parser.add_argument(
        "--output-format", choices=["console", "json", "markdown"], default="console", help="Output format"
    )

    args = parser.parse_args()

    try:
        auditor = PostDeploymentSecurityAuditor(args.deployment_path, args.environment)
        auditor.run_full_audit(args.endpoints)

        if args.output_format == "json":
            results_data = {
                "results": [
                    {
                        "check_name": r.check_name,
                        "status": r.status,
                        "message": r.message,
                        "severity": r.severity,
                        "details": r.details,
                    }
                    for r in auditor.audit_results
                ]
            }
            print(json.dumps(results_data, indent=2))
        elif args.output_format == "markdown":
            report = auditor.generate_audit_report()
            print(report)
        else:
            # Console summary
            critical_count = len([r for r in auditor.audit_results if r.severity == "CRITICAL"])
            failed_count = len([r for r in auditor.audit_results if r.status == "FAIL"])
            passed_count = len([r for r in auditor.audit_results if r.status == "PASS"])

            print("\n" + "=" * 80)
            print("🛡️ SECURITY AUDIT SUMMARY")
            print("=" * 80)
            print(f"Environment: {args.environment}")
            print(f"Total Checks: {len(auditor.audit_results)}")
            print(f"Passed: {passed_count}")
            print(f"Failed: {failed_count}")
            print(f"Critical Issues: {critical_count}")

            if critical_count > 0:
                print("\n🚨 CRITICAL SECURITY ISSUES DETECTED!")
                for result in auditor.audit_results:
                    if result.severity == "CRITICAL":
                        print(f"  - {result.check_name}: {result.message}")
            elif failed_count > 0:
                print("\n⚠️ Security issues found - review required")
            else:
                print("\n✅ All security checks passed!")

        # Save results
        auditor.save_audit_results()

        # Exit with error code if critical issues or failures
        if critical_count > 0 or failed_count > 0:
            return 1

        return 0

    except Exception as e:
        print(f"Security audit failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

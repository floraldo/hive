#!/usr/bin/env python3
"""
Production Shield Security Audit Verification Tests

Meta-monitoring tests to verify the Security Audit system works correctly:
- Malicious configuration detection verification
- Secret leak detection verification
- File permission validation verification
- SSL certificate monitoring verification

Ensures the security guardian detects real security issues.
"""

import os

# Import the security auditor
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent / "scripts" / "operational_excellence"))
from security_audit import PostDeploymentSecurityAuditor


class MaliciousDeploymentGenerator:
    """Generates malicious deployment scenarios for testing security audit"""

    def __init__(self, deployment_dir: Path):
        self.deployment_dir = deployment_dir
        self.deployment_dir.mkdir(parents=True, exist_ok=True)

    def create_insecure_env_file(self, filename: str = ".env.prod"):
        """Create .env file with insecure permissions"""
        env_file = self.deployment_dir / filename

        # Create file with secrets
        with open(env_file, "w") as f:
            f.write("DATABASE_URL=postgresql://user:secret123@db.example.com:5432/prod\n")
            f.write("API_KEY=sk-1234567890abcdef1234567890abcdef\n")
            f.write("JWT_SECRET=super-secret-jwt-key-that-should-be-protected\n")
            f.write("STRIPE_SECRET_KEY=sk_live_1234567890abcdef\n")

        # Set insecure permissions (readable by all)
        os.chmod(env_file, 0o644)  # rw-r--r--

        return env_file

    def create_leaked_secrets_log(self, filename: str = "application.log"):
        """Create log file with accidentally leaked secrets"""
        log_file = self.deployment_dir / filename

        with open(log_file, "w") as f:
            # Normal log entries
            f.write("2023-12-01T10:00:00Z [INFO] Application starting up\n")
            f.write("2023-12-01T10:01:00Z [INFO] Database connection established\n")

            # Accidentally leaked secrets
            f.write("2023-12-01T10:02:00Z [DEBUG] API_KEY=sk-1234567890abcdef1234567890abcdef\n")
            f.write(
                "2023-12-01T10:03:00Z [ERROR] Authentication failed with token: bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9\n",
            )
            f.write(
                "2023-12-01T10:04:00Z [DEBUG] Database connection string: postgresql://admin:password123@prod-db:5432/app\n",
            )
            f.write("2023-12-01T10:05:00Z [INFO] AWS credentials loaded: aws_access_key_id=AKIAIOSFODNN7EXAMPLE\n")
            f.write(
                "2023-12-01T10:06:00Z [DEBUG] Private key loaded: -----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA1234567890abcdef...\n",
            )

            # More normal entries
            f.write("2023-12-01T10:07:00Z [INFO] Request processed successfully\n")
            f.write("2023-12-01T10:08:00Z [INFO] Health check passed\n")

        return log_file

    def create_insecure_config_files(self):
        """Create configuration files with insecure settings"""
        configs = []

        # Insecure JSON config
        json_config = self.deployment_dir / "config.json"
        with open(json_config, "w") as f:
            f.write(
                """{
    "debug": true,
    "ssl": false,
    "verify_certificates": false,
    "cors": {
        "allow_origins": "*"
    },
    "security": {
        "trust_all_certificates": true,
        "insecure_mode": true
    }
}""",
            )
        configs.append(json_config)

        # Insecure YAML config
        yaml_config = self.deployment_dir / "app.yml"
        with open(yaml_config, "w") as f:
            f.write(
                """
server:
  debug: true
  ssl: false

database:
  verify: false

cors:
  allow_origins: "*"

security:
  trust_all: true
  insecure: true
""",
            )
        configs.append(yaml_config)

        return configs

    def create_sensitive_files_with_bad_permissions(self):
        """Create sensitive files with inappropriate permissions"""
        files = []

        # SSH private key with bad permissions
        ssh_key = self.deployment_dir / "id_rsa"
        with open(ssh_key, "w") as f:
            f.write("-----BEGIN RSA PRIVATE KEY-----\n")
            f.write("MIIEpAIBAAKCAQEA1234567890abcdef...\n")
            f.write("-----END RSA PRIVATE KEY-----\n")
        os.chmod(ssh_key, 0o644)  # Should be 0o600
        files.append(ssh_key)

        # SSL certificate key with bad permissions
        ssl_key = self.deployment_dir / "server.key"
        with open(ssl_key, "w") as f:
            f.write("-----BEGIN PRIVATE KEY-----\n")
            f.write("MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n")
            f.write("-----END PRIVATE KEY-----\n")
        os.chmod(ssl_key, 0o755)  # Should be 0o600
        files.append(ssl_key)

        # Database secrets file with bad permissions
        db_secrets = self.deployment_dir / "secrets.json"
        with open(db_secrets, "w") as f:
            f.write('{"db_password": "super-secret-password", "api_key": "secret-api-key"}')
        os.chmod(db_secrets, 0o666)  # Should be 0o600
        files.append(db_secrets)

        return files

    def create_environment_with_unencrypted_secrets(self):
        """Set up environment variables with unencrypted secrets"""
        # These would be detected by the environment variable audit
        insecure_env_vars = {
            "DATABASE_PASSWORD": "plaintext-password-123",
            "API_SECRET_KEY": "sk-1234567890abcdef1234567890abcdef",
            "JWT_SECRET": "my-super-secret-jwt-key",
            "STRIPE_SECRET": "sk_live_abcdef1234567890",
            "DEBUG_MODE": "true",  # Development variable in production
            "TEST_API_KEY": "test-key-should-not-be-in-prod",
        }

        # Set environment variables
        for key, value in insecure_env_vars.items():
            os.environ[key] = value

        return insecure_env_vars

    def cleanup_environment(self, env_vars: dict[str, str]):
        """Clean up environment variables"""
        for key in env_vars.keys():
            if key in os.environ:
                del os.environ[key]


class TestSecurityAuditVerification:
    """Test suite for verifying security audit detection accuracy"""

    @pytest.fixture
    def temp_deployment_dir(self):
        """Create temporary deployment directory"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir)

    @pytest.fixture
    def malicious_generator(self, temp_deployment_dir):
        """Create malicious deployment generator"""
        return MaliciousDeploymentGenerator(temp_deployment_dir)

    def test_insecure_file_permissions_detection(self, malicious_generator, temp_deployment_dir):
        """Test detection of insecure file permissions"""
        # Create files with bad permissions
        insecure_files = malicious_generator.create_sensitive_files_with_bad_permissions()

        # Run security audit
        auditor = PostDeploymentSecurityAuditor(temp_deployment_dir, "production")
        auditor.audit_file_permissions()

        # Verify detection
        results = auditor.audit_results
        permission_results = [r for r in results if r.check_name == "file_permissions"]

        # Should detect multiple permission issues
        failed_checks = [r for r in permission_results if r.status == "FAIL"]
        warning_checks = [r for r in permission_results if r.status == "WARNING"]

        assert len(failed_checks) + len(warning_checks) >= 2  # Should detect at least 2 issues

        # Verify specific files are flagged
        flagged_files = []
        for result in failed_checks + warning_checks:
            if result.details and "file_path" in result.details:
                flagged_files.append(Path(result.details["file_path"]).name)

        expected_files = ["id_rsa", "server.key", "secrets.json"]
        detected_files = [f for f in expected_files if f in flagged_files]
        assert len(detected_files) >= 2

    def test_secret_leak_detection_in_logs(self, malicious_generator, temp_deployment_dir):
        """Test detection of leaked secrets in log files"""
        # Create log with leaked secrets
        log_file = malicious_generator.create_leaked_secrets_log()

        # Run security audit
        auditor = PostDeploymentSecurityAuditor(temp_deployment_dir, "production")
        auditor.scan_logs_for_secrets(max_files=5, max_lines_per_file=100)

        # Verify detection
        results = auditor.audit_results
        log_scan_results = [r for r in results if r.check_name == "log_secret_scan"]

        assert len(log_scan_results) > 0

        # Should detect leaked secrets
        failed_scans = [r for r in log_scan_results if r.status == "FAIL"]
        assert len(failed_scans) > 0

        # Verify specific secret types are detected
        if failed_scans[0].details and "leaked_secrets" in failed_scans[0].details:
            leaked_secrets = failed_scans[0].details["leaked_secrets"]
            assert len(leaked_secrets) >= 3  # Should detect multiple types

            detected_types = [secret["type"] for secret in leaked_secrets]
            expected_types = ["API Key", "Bearer Token", "Database URL", "AWS Access Key", "Private Key"]

            # Should detect at least 3 different types
            detected_count = sum(1 for t in expected_types if t in detected_types)
            assert detected_count >= 3

    def test_insecure_configuration_detection(self, malicious_generator, temp_deployment_dir):
        """Test detection of insecure configuration settings"""
        # Create insecure config files
        config_files = malicious_generator.create_insecure_config_files()

        # Run security audit
        auditor = PostDeploymentSecurityAuditor(temp_deployment_dir, "production")
        auditor.audit_configuration_compliance()

        # Verify detection
        results = auditor.audit_results
        config_results = [r for r in results if r.check_name == "configuration_compliance"]

        assert len(config_results) > 0

        # Should detect configuration issues
        failed_configs = [r for r in config_results if r.status in ["FAIL", "WARNING"]]
        assert len(failed_configs) > 0

        # Verify specific issues are detected
        if failed_configs[0].details and "issues" in failed_configs[0].details:
            issues = failed_configs[0].details["issues"]
            assert len(issues) >= 4  # Should detect multiple issues

            detected_issues = [issue["issue"] for issue in issues]
            expected_issues = [
                "Debug mode enabled",
                "SSL disabled",
                "Certificate verification disabled",
                "CORS allows all origins",
                "Trust all certificates enabled",
                "Insecure mode enabled",
            ]

            # Should detect at least 4 different issues
            detected_count = sum(1 for issue in expected_issues if issue in detected_issues)
            assert detected_count >= 4

    def test_environment_variable_security_audit(self, malicious_generator, temp_deployment_dir):
        """Test detection of insecure environment variables"""
        # Set up insecure environment
        env_vars = malicious_generator.create_environment_with_unencrypted_secrets()

        try:
            # Run security audit
            auditor = PostDeploymentSecurityAuditor(temp_deployment_dir, "production")
            auditor.audit_environment_variables()

            # Verify detection
            results = auditor.audit_results
            env_results = [r for r in results if r.check_name == "environment_variables"]

            assert len(env_results) > 0

            # Should detect environment issues
            failed_env = [r for r in env_results if r.status in ["FAIL", "WARNING"]]
            assert len(failed_env) > 0

            # Verify specific issues are detected
            critical_issues = [r for r in failed_env if r.severity == "CRITICAL"]
            if critical_issues and critical_issues[0].details:
                if "unencrypted_secrets" in critical_issues[0].details:
                    unencrypted = critical_issues[0].details["unencrypted_secrets"]
                    assert len(unencrypted) >= 3  # Should detect multiple unencrypted secrets

                    expected_vars = ["DATABASE_PASSWORD", "API_SECRET_KEY", "JWT_SECRET", "STRIPE_SECRET"]
                    detected_vars = [var for var in expected_vars if var in unencrypted]
                    assert len(detected_vars) >= 2

            # Should also detect development variables in production
            dev_var_issues = [r for r in failed_env if "development" in r.message.lower()]
            assert len(dev_var_issues) > 0

        finally:
            # Cleanup environment
            malicious_generator.cleanup_environment(env_vars)

    def test_comprehensive_security_audit(self, malicious_generator, temp_deployment_dir):
        """Test comprehensive security audit with multiple vulnerabilities"""
        # Create multiple security issues
        malicious_generator.create_insecure_env_file()
        malicious_generator.create_leaked_secrets_log()
        malicious_generator.create_insecure_config_files()
        malicious_generator.create_sensitive_files_with_bad_permissions()

        env_vars = malicious_generator.create_environment_with_unencrypted_secrets()

        try:
            # Run full security audit
            auditor = PostDeploymentSecurityAuditor(temp_deployment_dir, "production")
            auditor.run_full_audit()

            # Verify comprehensive detection
            results = auditor.audit_results

            # Should have results from all audit types
            check_types = set(r.check_name for r in results)
            expected_checks = {
                "file_permissions",
                "environment_variables",
                "log_secret_scan",
                "configuration_compliance",
            }

            assert expected_checks.issubset(check_types)

            # Should detect multiple critical issues
            critical_issues = [r for r in results if r.severity == "CRITICAL"]
            assert len(critical_issues) >= 2

            # Should detect multiple high severity issues
            high_issues = [r for r in results if r.severity == "HIGH"]
            assert len(high_issues) >= 1

            # Should have multiple failed checks
            failed_checks = [r for r in results if r.status == "FAIL"]
            assert len(failed_checks) >= 3

        finally:
            malicious_generator.cleanup_environment(env_vars)

    def test_security_audit_report_generation(self, malicious_generator, temp_deployment_dir):
        """Test generation of comprehensive security audit reports"""
        # Create security issues
        malicious_generator.create_insecure_env_file()
        malicious_generator.create_leaked_secrets_log()
        malicious_generator.create_insecure_config_files()

        # Run audit
        auditor = PostDeploymentSecurityAuditor(temp_deployment_dir, "production")
        auditor.run_full_audit()

        # Generate report
        report = auditor.generate_audit_report()

        # Verify report structure
        assert "Post-Deployment Security Audit Report" in report
        assert "Executive Summary" in report
        assert "Overall Status" in report
        assert "Critical Security Issues" in report or "High Severity Issues" in report
        assert "Detailed Security Check Results" in report
        assert "Security Recommendations" in report

        # Verify report contains specific findings
        assert "file_permissions" in report.lower() or "File Permissions" in report
        assert "configuration" in report.lower() or "Configuration" in report
        assert "log" in report.lower() or "Log" in report

        # Should recommend immediate actions for critical issues
        if "FAILED" in report:
            assert "Immediate Actions" in report or "Stop deployment" in report

    def test_security_audit_exit_codes(self, malicious_generator, temp_deployment_dir):
        """Test that security audit returns appropriate exit codes"""
        # Test with secure deployment (should pass)
        auditor_secure = PostDeploymentSecurityAuditor(temp_deployment_dir, "production")
        auditor_secure.run_full_audit()

        # Should have no critical issues
        critical_count = len([r for r in auditor_secure.audit_results if r.severity == "CRITICAL"])
        failed_count = len([r for r in auditor_secure.audit_results if r.status == "FAIL"])

        # Secure deployment should have minimal issues
        assert critical_count == 0
        assert failed_count <= 1  # Maybe one minor issue

        # Test with insecure deployment (should fail)
        malicious_generator.create_insecure_env_file()
        malicious_generator.create_leaked_secrets_log()

        auditor_insecure = PostDeploymentSecurityAuditor(temp_deployment_dir, "production")
        auditor_insecure.run_full_audit()

        # Should have critical issues
        critical_count = len([r for r in auditor_insecure.audit_results if r.severity == "CRITICAL"])
        failed_count = len([r for r in auditor_insecure.audit_results if r.status == "FAIL"])

        # Insecure deployment should fail
        assert critical_count > 0 or failed_count > 0

    def test_audit_results_serialization(self, malicious_generator, temp_deployment_dir):
        """Test that audit results can be properly serialized and saved"""
        # Create some security issues
        malicious_generator.create_insecure_env_file()
        malicious_generator.create_leaked_secrets_log()

        # Run audit
        auditor = PostDeploymentSecurityAuditor(temp_deployment_dir, "production")
        auditor.run_full_audit()

        # Save results
        auditor.save_audit_results()

        # Verify files are created
        results_file = Path("security_audit_results.json")
        report_file = Path("security_audit_report.md")

        assert results_file.exists()
        assert report_file.exists()

        # Verify JSON results are valid
        import json

        with open(results_file) as f:
            saved_results = json.load(f)

            assert "audit_timestamp" in saved_results
            assert "environment" in saved_results
            assert "total_checks" in saved_results
            assert "results" in saved_results
            assert len(saved_results["results"]) > 0

        # Verify report content
        with open(report_file) as f:
            saved_report = f.read()
            assert "Post-Deployment Security Audit Report" in saved_report
            assert len(saved_report) > 500  # Should be substantial

        # Cleanup
        results_file.unlink()
        report_file.unlink()


class TestSecurityAuditIntegration:
    """Integration tests for complete security audit workflow"""

    @pytest.fixture
    def realistic_insecure_deployment(self, temp_deployment_dir):
        """Create a realistic insecure deployment scenario"""
        generator = MaliciousDeploymentGenerator(temp_deployment_dir)

        # Create a realistic but insecure deployment
        generator.create_insecure_env_file(".env.production")
        generator.create_leaked_secrets_log("app.log")
        generator.create_insecure_config_files()
        generator.create_sensitive_files_with_bad_permissions()

        # Add some normal files too
        (temp_deployment_dir / "README.md").write_text("# Production Deployment\n\nThis is our app.")
        (temp_deployment_dir / "requirements.txt").write_text("flask==2.0.1\npsycopg2==2.9.1\n")

        return temp_deployment_dir

    def test_realistic_deployment_audit(self, realistic_insecure_deployment):
        """Test audit of a realistic insecure deployment"""
        # Run comprehensive audit
        auditor = PostDeploymentSecurityAuditor(realistic_insecure_deployment, "production")
        auditor.run_full_audit()

        # Should detect multiple categories of issues
        results = auditor.audit_results

        # Verify comprehensive detection
        check_types = set(r.check_name for r in results)
        assert len(check_types) >= 4  # Should run multiple types of checks

        # Should detect issues across severity levels
        severities = set(r.severity for r in results)
        assert "CRITICAL" in severities or "HIGH" in severities

        # Generate comprehensive report
        report = auditor.generate_audit_report()

        # Report should be comprehensive
        assert len(report) > 2000  # Should be a detailed report
        assert report.count("##") >= 5  # Should have multiple sections

        # Should provide actionable recommendations
        assert "Immediate Actions" in report or "High Priority Actions" in report
        assert "Security Recommendations" in report


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])

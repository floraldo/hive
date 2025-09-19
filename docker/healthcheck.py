#!/usr/bin/env python3
"""
Health check script for Hive Fleet Command System containers.
Returns exit code 0 if healthy, 1 if unhealthy.
"""

import os
import sys
import json
import time
import socket
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('healthcheck')

class HealthChecker:
    def __init__(self):
        self.role = os.environ.get('HIVE_ROLE', 'unknown')
        self.checks_passed = []
        self.checks_failed = []

    def check_file_system(self):
        """Check if critical directories are accessible."""
        try:
            critical_paths = [
                '/app',
                '/app/logs',
                '/app/hive'
            ]

            for path in critical_paths:
                if not Path(path).exists():
                    self.checks_failed.append(f"Path {path} does not exist")
                    return False

                # Try to write a test file
                test_file = Path(path) / '.health_check'
                try:
                    test_file.write_text(str(datetime.now()))
                    test_file.unlink()
                except Exception as e:
                    self.checks_failed.append(f"Cannot write to {path}: {e}")
                    return False

            self.checks_passed.append("File system check passed")
            return True
        except Exception as e:
            self.checks_failed.append(f"File system check failed: {e}")
            return False

    def check_network_connectivity(self):
        """Check if dependent services are reachable."""
        try:
            services = {
                'message-bus': ('message-bus', 6379),
                'database': ('database', 5432)
            }

            # Skip self-checks
            if self.role in services:
                del services[self.role]

            for service_name, (host, port) in services.items():
                try:
                    sock = socket.create_connection((host, port), timeout=5)
                    sock.close()
                    self.checks_passed.append(f"{service_name} is reachable")
                except (socket.timeout, socket.error) as e:
                    # Warning only - not a failure
                    logger.warning(f"{service_name} not reachable: {e}")

            return True
        except Exception as e:
            self.checks_failed.append(f"Network check failed: {e}")
            return False

    def check_process_health(self):
        """Check if the main process is running correctly."""
        try:
            # Check based on role
            if self.role == 'queen':
                # Check if queen.py process is running
                pid_file = Path('/app/logs/queen.pid')
                if pid_file.exists():
                    pid = int(pid_file.read_text().strip())
                    try:
                        # Check if process exists
                        os.kill(pid, 0)
                        self.checks_passed.append("Queen process is running")
                    except ProcessLookupError:
                        self.checks_failed.append("Queen process not found")
                        return False
                else:
                    # Check if it's starting up (grace period)
                    startup_grace = Path('/app/logs/startup.flag')
                    if startup_grace.exists():
                        age = time.time() - startup_grace.stat().st_mtime
                        if age < 60:  # 60 seconds grace period
                            self.checks_passed.append("Service is starting up")
                            return True
                    self.checks_failed.append("No queen process found")
                    return False

            elif self.role in ['frontend', 'backend', 'infra']:
                # Check worker process
                pid_file = Path(f'/app/logs/{self.role}.pid')
                if pid_file.exists():
                    pid = int(pid_file.read_text().strip())
                    try:
                        os.kill(pid, 0)
                        self.checks_passed.append(f"{self.role} worker is running")
                    except ProcessLookupError:
                        self.checks_failed.append(f"{self.role} worker not found")
                        return False
                else:
                    # Check startup grace period
                    startup_grace = Path('/app/logs/startup.flag')
                    if startup_grace.exists():
                        age = time.time() - startup_grace.stat().st_mtime
                        if age < 60:
                            self.checks_passed.append("Service is starting up")
                            return True
                    self.checks_failed.append(f"No {self.role} worker found")
                    return False

            return True
        except Exception as e:
            self.checks_failed.append(f"Process health check failed: {e}")
            return False

    def check_recent_activity(self):
        """Check if there's been recent activity (logs updated)."""
        try:
            log_dir = Path('/app/logs')
            if not log_dir.exists():
                self.checks_failed.append("Log directory does not exist")
                return False

            # Find most recent log file
            log_files = list(log_dir.glob('*.log'))
            if not log_files:
                # No logs yet might be OK during startup
                self.checks_passed.append("No logs yet (may be starting)")
                return True

            most_recent = max(log_files, key=lambda p: p.stat().st_mtime)
            age = time.time() - most_recent.stat().st_mtime

            # If logs haven't been updated in 5 minutes, might be stuck
            if age > 300:
                self.checks_failed.append(f"No log activity for {int(age)} seconds")
                return False

            self.checks_passed.append(f"Recent activity detected ({int(age)}s ago)")
            return True
        except Exception as e:
            logger.warning(f"Activity check failed: {e}")
            return True  # Non-critical check

    def check_memory_usage(self):
        """Check if memory usage is within limits."""
        try:
            import psutil

            # Get current process memory usage
            process = psutil.Process()
            mem_info = process.memory_info()
            mem_usage_mb = mem_info.rss / 1024 / 1024

            # Get memory limit based on role
            mem_limits = {
                'queen': 2048,
                'frontend': 1024,
                'backend': 1024,
                'infra': 1024
            }

            limit = mem_limits.get(self.role, 1024)

            if mem_usage_mb > limit * 0.9:  # 90% of limit
                self.checks_failed.append(f"High memory usage: {mem_usage_mb:.1f}MB")
                return False

            self.checks_passed.append(f"Memory usage OK: {mem_usage_mb:.1f}MB")
            return True
        except ImportError:
            logger.warning("psutil not available, skipping memory check")
            return True
        except Exception as e:
            logger.warning(f"Memory check failed: {e}")
            return True  # Non-critical check

    def run_health_checks(self):
        """Run all health checks and return overall status."""
        checks = [
            ('File System', self.check_file_system()),
            ('Network', self.check_network_connectivity()),
            ('Process', self.check_process_health()),
            ('Activity', self.check_recent_activity()),
            ('Memory', self.check_memory_usage())
        ]

        # Calculate overall health
        critical_checks = ['File System', 'Process']
        critical_passed = all(
            result for name, result in checks
            if name in critical_checks
        )

        # Log results
        logger.info(f"Health check for role: {self.role}")
        logger.info(f"Checks passed: {self.checks_passed}")
        if self.checks_failed:
            logger.warning(f"Checks failed: {self.checks_failed}")

        # Write health status to file
        try:
            health_status = {
                'role': self.role,
                'timestamp': datetime.now().isoformat(),
                'healthy': critical_passed,
                'checks_passed': self.checks_passed,
                'checks_failed': self.checks_failed
            }

            health_file = Path('/app/logs/health.json')
            health_file.write_text(json.dumps(health_status, indent=2))
        except Exception as e:
            logger.error(f"Failed to write health status: {e}")

        return critical_passed

def main():
    """Main entry point."""
    try:
        checker = HealthChecker()
        is_healthy = checker.run_health_checks()

        if is_healthy:
            logger.info("Health check PASSED")
            sys.exit(0)
        else:
            logger.error("Health check FAILED")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Health check error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
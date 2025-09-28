#!/usr/bin/env python3
"""
Database Connection Pool Monitoring Script

This script monitors the health and usage of database connection pools
across the Hive platform, with special focus on EcoSystemiser integration.
"""

import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from EcoSystemiser.hive_logging_adapter import get_logger
from EcoSystemiser.db import (
    get_ecosystemiser_connection,
    get_ecosystemiser_db_path,
    validate_hive_integration
)

# Import shared database service if available
try:
    from hive_orchestrator.core.db import (
        get_database_stats,
        database_health_check,
        get_shared_database_service
    )
    HIVE_DB_AVAILABLE = True
except ImportError:
    HIVE_DB_AVAILABLE = False

logger = get_logger(__name__)


class DatabaseConnectionMonitor:
    """Monitor for database connection pools."""

    def __init__(self):
        """Initialize the monitor."""
        self.start_time = datetime.now()
        self.stats_history = []

    def get_current_stats(self) -> Dict[str, Any]:
        """Get current database statistics."""
        stats = {
            'timestamp': datetime.now().isoformat(),
            'hive_service_available': HIVE_DB_AVAILABLE,
            'ecosystemiser_db_path': str(get_ecosystemiser_db_path()),
            'integration_status': validate_hive_integration()
        }

        if HIVE_DB_AVAILABLE:
            try:
                stats['pool_stats'] = get_database_stats()
                stats['health_check'] = database_health_check()
            except Exception as e:
                stats['error'] = f"Failed to get stats: {e}"

        # Test connection acquisition time
        try:
            start = time.time()
            with get_ecosystemiser_connection() as conn:
                conn.execute("SELECT 1")
            stats['connection_time_ms'] = (time.time() - start) * 1000
        except Exception as e:
            stats['connection_error'] = str(e)

        return stats

    def check_connection_leaks(self) -> Dict[str, Any]:
        """Check for potential connection leaks."""
        if not HIVE_DB_AVAILABLE:
            return {'status': 'skip', 'reason': 'Hive service not available'}

        try:
            # Get baseline stats
            baseline_stats = get_database_stats()

            # Perform many connection operations
            for i in range(100):
                with get_ecosystemiser_connection() as conn:
                    conn.execute("SELECT 1")

            # Wait for cleanup
            time.sleep(1.0)

            # Get final stats
            final_stats = get_database_stats()

            # Analyze for leaks
            ecosystemiser_baseline = baseline_stats.get('ecosystemiser', {})
            ecosystemiser_final = final_stats.get('ecosystemiser', {})

            baseline_connections = ecosystemiser_baseline.get('connections_created', 0)
            final_connections = ecosystemiser_final.get('connections_created', 0)

            return {
                'status': 'checked',
                'baseline_connections': baseline_connections,
                'final_connections': final_connections,
                'connections_created': final_connections - baseline_connections,
                'pool_size_final': ecosystemiser_final.get('pool_size', 0),
                'leak_detected': final_connections - baseline_connections > 10
            }

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def run_performance_test(self, duration_seconds: int = 30) -> Dict[str, Any]:
        """Run a performance test on the connection pool."""
        logger.info(f"Running performance test for {duration_seconds} seconds...")

        start_time = time.time()
        operations = 0
        errors = 0
        total_connection_time = 0
        max_connection_time = 0
        min_connection_time = float('inf')

        while time.time() - start_time < duration_seconds:
            try:
                conn_start = time.time()
                with get_ecosystemiser_connection() as conn:
                    conn.execute("SELECT 1, ?", (operations,))
                conn_time = time.time() - conn_start

                total_connection_time += conn_time
                max_connection_time = max(max_connection_time, conn_time)
                min_connection_time = min(min_connection_time, conn_time)

                operations += 1

                # Small delay to avoid overwhelming the system
                time.sleep(0.001)

            except Exception as e:
                errors += 1
                logger.error(f"Performance test error: {e}")

        actual_duration = time.time() - start_time
        avg_connection_time = total_connection_time / operations if operations > 0 else 0

        return {
            'duration_seconds': actual_duration,
            'operations_completed': operations,
            'errors': errors,
            'operations_per_second': operations / actual_duration,
            'avg_connection_time_ms': avg_connection_time * 1000,
            'max_connection_time_ms': max_connection_time * 1000,
            'min_connection_time_ms': min_connection_time * 1000 if min_connection_time != float('inf') else 0
        }

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive monitoring report."""
        logger.info("Generating database connection monitoring report...")

        report = {
            'generated_at': datetime.now().isoformat(),
            'monitor_uptime': str(datetime.now() - self.start_time),
        }

        # Current stats
        report['current_stats'] = self.get_current_stats()

        # Connection leak check
        report['leak_check'] = self.check_connection_leaks()

        # Performance test
        report['performance_test'] = self.run_performance_test(duration_seconds=10)

        # Integration validation
        report['integration_validation'] = {
            'hive_service_available': HIVE_DB_AVAILABLE,
            'ecosystemiser_integration': validate_hive_integration()
        }

        if HIVE_DB_AVAILABLE:
            try:
                service = get_shared_database_service()
                report['service_info'] = {
                    'all_stats': service.get_all_stats(),
                    'health_check': service.health_check()
                }
            except Exception as e:
                report['service_error'] = str(e)

        return report

    def monitor_continuously(self, interval_seconds: int = 60, duration_minutes: int = 10):
        """Run continuous monitoring."""
        logger.info(f"Starting continuous monitoring for {duration_minutes} minutes...")

        end_time = time.time() + (duration_minutes * 60)

        while time.time() < end_time:
            try:
                stats = self.get_current_stats()
                self.stats_history.append(stats)

                logger.info(f"Stats: {json.dumps(stats, indent=2)}")

                # Check for issues
                if 'connection_error' in stats:
                    logger.error(f"Connection error detected: {stats['connection_error']}")

                if 'connection_time_ms' in stats and stats['connection_time_ms'] > 1000:
                    logger.warning(f"Slow connection detected: {stats['connection_time_ms']:.2f}ms")

                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("Monitoring interrupted by user")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(interval_seconds)

        logger.info("Continuous monitoring completed")

    def save_report(self, report: Dict[str, Any], output_path: Path = None):
        """Save monitoring report to file."""
        if output_path is None:
            output_path = Path(__file__).parent / f"db_monitor_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Report saved to: {output_path}")
        return output_path


def main():
    """Main monitoring function."""
    monitor = DatabaseConnectionMonitor()

    try:
        # Generate comprehensive report
        report = monitor.generate_report()

        # Print summary
        print("\n" + "="*50)
        print("DATABASE CONNECTION MONITORING REPORT")
        print("="*50)
        print(f"Generated at: {report['generated_at']}")
        print(f"Hive Service Available: {report['current_stats']['hive_service_available']}")
        print(f"Integration Status: {report['current_stats']['integration_status']}")

        if 'connection_time_ms' in report['current_stats']:
            print(f"Connection Time: {report['current_stats']['connection_time_ms']:.2f}ms")

        print(f"\nLeak Check: {report['leak_check']['status']}")
        if report['leak_check']['status'] == 'checked':
            leak_detected = report['leak_check']['leak_detected']
            print(f"Leak Detected: {'❌ YES' if leak_detected else '✅ NO'}")
            print(f"Connections Created: {report['leak_check']['connections_created']}")

        perf = report['performance_test']
        print(f"\nPerformance Test:")
        print(f"  Operations/sec: {perf['operations_per_second']:.2f}")
        print(f"  Avg Connection Time: {perf['avg_connection_time_ms']:.2f}ms")
        print(f"  Errors: {perf['errors']}")

        if HIVE_DB_AVAILABLE and 'service_info' in report:
            service_info = report['service_info']
            print(f"\nService Stats:")
            for db_name, stats in service_info['all_stats'].items():
                print(f"  {db_name}: {stats['pool_size']} pooled, {stats['connections_created']} created")

        # Save detailed report
        output_path = monitor.save_report(report)
        print(f"\nDetailed report saved to: {output_path}")

        # Optionally run continuous monitoring
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
            monitor.monitor_continuously(interval_seconds=30, duration_minutes=5)

    except Exception as e:
        logger.error(f"Monitoring failed: {e}")
        raise


if __name__ == "__main__":
    main()
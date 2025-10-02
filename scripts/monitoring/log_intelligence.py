#!/usr/bin/env python3
"""
Centralized Log Intelligence System

Automated log analysis and trend detection for production environments:
- Log aggregation and parsing from multiple sources
- Error pattern detection and trend analysis
- Critical alert identification and escalation
- Daily log digest generation with actionable insights

Part of the Production Shield Initiative for proactive log monitoring.
"""

import argparse
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


class LogEntry:
    """Represents a single log entry"""

    def __init__(self, timestamp: datetime, level: str, message: str, source: str, raw_line: str):
        self.timestamp = timestamp
        self.level = level.upper()
        self.message = message
        self.source = source
        self.raw_line = raw_line
        self.is_error = level.upper() in ["ERROR", "CRITICAL", "FATAL"]
        self.is_warning = level.upper() in ["WARNING", "WARN"]


class LogIntelligenceAnalyzer:
    def __init__(self, log_directories: list[Path] = None):
        self.log_directories = log_directories or [Path("logs")]
        self.log_entries: list[LogEntry] = []
        self.analysis_results = {
            "total_entries": 0,
            "error_count": 0,
            "warning_count": 0,
            "critical_patterns": [],
            "error_trends": {},
            "top_errors": [],
            "new_error_patterns": [],
            "performance_issues": [],
            "security_alerts": [],
        }

        # Critical patterns that should trigger immediate alerts
        self.critical_patterns = [
            (r"database.*connection.*refused", "Database Connection Failure"),
            (r"out of memory|oom|memory.*exhausted", "Memory Exhaustion"),
            (r"disk.*full|no space left", "Disk Space Critical"),
            (r"authentication.*failed|unauthorized.*access", "Security: Auth Failure"),
            (r"ssl.*certificate.*expired|certificate.*invalid", "SSL Certificate Issue"),
            (r"timeout.*exceeded|request.*timeout", "Performance: Timeout"),
            (r"500.*internal.*server.*error", "HTTP 500 Errors"),
            (r"deadlock.*detected|lock.*timeout", "Database Deadlock"),
            (r"circuit.*breaker.*open", "Circuit Breaker Activated"),
            (r"rate.*limit.*exceeded", "Rate Limiting Triggered"),
        ]

        # Performance issue patterns
        self.performance_patterns = [
            (r"slow.*query|query.*took.*(\d+).*seconds", "Slow Database Query"),
            (r"response.*time.*(\d+).*ms", "High Response Time"),
            (r"garbage.*collection|gc.*took.*(\d+)", "GC Performance Issue"),
            (r"thread.*pool.*exhausted", "Thread Pool Exhaustion"),
            (r"connection.*pool.*exhausted", "Connection Pool Exhaustion"),
        ]

        # Security alert patterns
        self.security_patterns = [
            (r"failed.*login.*attempt", "Failed Login Attempt"),
            (r"suspicious.*activity|anomalous.*behavior", "Suspicious Activity"),
            (r"sql.*injection|xss.*attempt", "Security: Injection Attempt"),
            (r"brute.*force|multiple.*failed.*attempts", "Brute Force Attack"),
            (r"unauthorized.*api.*access", "Unauthorized API Access"),
        ]

    def discover_log_files(self) -> list[Path]:
        """Discover all log files in configured directories"""
        log_files = []

        for log_dir in self.log_directories:
            if not log_dir.exists():
                print(f"Warning: Log directory {log_dir} does not exist")
                continue

            # Find log files with common extensions
            patterns = ["*.log", "*.log.*", "*.out", "*.err"]

            for pattern in patterns:
                log_files.extend(log_dir.rglob(pattern))

        # Sort by modification time (newest first)
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        return log_files

    def parse_log_line(self, line: str, source: str) -> LogEntry | None:
        """Parse a single log line into a LogEntry"""
        line = line.strip()
        if not line:
            return None

        # Common log patterns
        patterns = [
            # ISO timestamp with level: 2023-12-01T10:30:45.123Z [ERROR] message
            (r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z?)\s*\[(\w+)\]\s*(.*)", "%Y-%m-%dT%H:%M:%S.%fZ"),
            # Standard timestamp: 2023-12-01 10:30:45 ERROR message
            (r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)", "%Y-%m-%d %H:%M:%S"),
            # Syslog format: Dec  1 10:30:45 hostname service[pid]: ERROR message
            (r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+\w+\s+\w+(?:\[\d+\])?\s*:\s*(\w+)\s+(.*)", "%b %d %H:%M:%S"),
            # Python logging: ERROR:module:message
            (r"(\w+):[\w\.]+:(.*)", None),
            # Simple level prefix: [ERROR] message
            (r"\[(\w+)\]\s*(.*)", None),
        ]

        for pattern, date_format in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()

                if date_format and len(groups) >= 3:
                    # Full timestamp parsing
                    try:
                        timestamp_str = groups[0]
                        # Handle different timestamp formats
                        if "T" in timestamp_str and timestamp_str.endswith("Z"):
                            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        else:
                            timestamp = datetime.strptime(timestamp_str, date_format)
                            # If no year in format, assume current year
                            if timestamp.year == 1900:
                                timestamp = timestamp.replace(year=datetime.now().year)
                    except ValueError:
                        timestamp = datetime.now()

                    level = groups[1]
                    message = groups[2]

                elif len(groups) >= 2:
                    # No timestamp or simple format
                    timestamp = datetime.now()
                    level = groups[0]
                    message = groups[1]
                else:
                    continue

                return LogEntry(timestamp, level, message, source, line)

        # If no pattern matches, treat as INFO level
        return LogEntry(datetime.now(), "INFO", line, source, line)

    def read_log_file(self, log_file: Path, max_lines: int = 10000) -> list[LogEntry]:
        """Read and parse a single log file"""
        entries = []
        lines_read = 0

        try:
            # Handle compressed files
            if log_file.suffix == ".gz":
                file_opener = gzip.open
                mode = "rt"
            else:
                file_opener = open
                mode = "r"

            with file_opener(log_file, mode, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if lines_read >= max_lines:
                        break

                    entry = self.parse_log_line(line, str(log_file.name))
                    if entry:
                        entries.append(entry)

                    lines_read += 1

        except Exception as e:
            print(f"Error reading {log_file}: {e}")

        return entries

    def analyze_logs(self, hours_back: int = 24, max_files: int = 50) -> None:
        """Analyze logs from the specified time period"""
        print(f"🔍 Analyzing logs from the last {hours_back} hours...")

        log_files = self.discover_log_files()[:max_files]

        if not log_files:
            print("No log files found")
            return

        print(f"Found {len(log_files)} log files to analyze")

        # Read and parse log files
        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        for log_file in log_files:
            print(f"Processing {log_file.name}...")
            entries = self.read_log_file(log_file)

            # Filter by time window
            recent_entries = [e for e in entries if e.timestamp >= cutoff_time]
            self.log_entries.extend(recent_entries)

        print(f"Loaded {len(self.log_entries)} log entries")

        # Perform analysis
        self._analyze_error_trends()
        self._detect_critical_patterns()
        self._analyze_performance_issues()
        self._detect_security_alerts()
        self._identify_new_error_patterns()

        # Update analysis results
        self.analysis_results.update(
            {
                "total_entries": len(self.log_entries),
                "error_count": len([e for e in self.log_entries if e.is_error]),
                "warning_count": len([e for e in self.log_entries if e.is_warning]),
                "analysis_timestamp": datetime.now().isoformat(),
                "time_window_hours": hours_back,
            },
        )

    def _analyze_error_trends(self) -> None:
        """Analyze error trends over time"""
        error_entries = [e for e in self.log_entries if e.is_error]

        if not error_entries:
            return

        # Group errors by hour
        hourly_errors = defaultdict(int)
        error_messages = Counter()

        for entry in error_entries:
            hour_key = entry.timestamp.strftime("%Y-%m-%d %H:00")
            hourly_errors[hour_key] += 1

            # Normalize error message for grouping
            normalized_message = self._normalize_error_message(entry.message)
            error_messages[normalized_message] += 1

        # Calculate trend
        hours = sorted(hourly_errors.keys())
        if len(hours) >= 2:
            recent_errors = hourly_errors[hours[-1]]
            previous_errors = hourly_errors[hours[-2]] if len(hours) > 1 else 0

            if previous_errors > 0:
                trend_percentage = ((recent_errors - previous_errors) / previous_errors) * 100
            else:
                trend_percentage = 100 if recent_errors > 0 else 0

            self.analysis_results["error_trends"] = {
                "current_hour_errors": recent_errors,
                "previous_hour_errors": previous_errors,
                "trend_percentage": round(trend_percentage, 1),
                "hourly_breakdown": dict(hourly_errors),
            }

        # Top error messages
        self.analysis_results["top_errors"] = [
            {"message": msg, "count": count} for msg, count in error_messages.most_common(10)
        ]

    def _normalize_error_message(self, message: str) -> str:
        """Normalize error message for grouping similar errors"""
        # Remove timestamps, IDs, and other variable parts
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "[TIMESTAMP]", message)
        normalized = re.sub(r"\b\d+\b", "[NUMBER]", normalized)
        normalized = re.sub(r"\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b", "[UUID]", normalized)
        normalized = re.sub(r"\b\w+@\w+\.\w+\b", "[EMAIL]", normalized)
        normalized = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP]", normalized)

        return normalized[:200]  # Limit length

    def _detect_critical_patterns(self) -> None:
        """Detect critical error patterns that require immediate attention"""
        critical_matches = []

        for entry in self.log_entries:
            if not entry.is_error:
                continue

            message_lower = entry.message.lower()

            for pattern, description in self.critical_patterns:
                if re.search(pattern, message_lower):
                    critical_matches.append(
                        {
                            "pattern": description,
                            "message": entry.message[:200],
                            "timestamp": entry.timestamp.isoformat(),
                            "source": entry.source,
                            "severity": "CRITICAL",
                        },
                    )

        self.analysis_results["critical_patterns"] = critical_matches

    def _analyze_performance_issues(self) -> None:
        """Analyze performance-related log entries"""
        performance_issues = []

        for entry in self.log_entries:
            message_lower = entry.message.lower()

            for pattern, description in self.performance_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    # Extract numeric values if present
                    numbers = re.findall(r"\d+", entry.message)
                    metric_value = numbers[0] if numbers else None

                    performance_issues.append(
                        {
                            "issue_type": description,
                            "message": entry.message[:200],
                            "timestamp": entry.timestamp.isoformat(),
                            "source": entry.source,
                            "metric_value": metric_value,
                            "severity": "HIGH" if metric_value and int(metric_value) > 5000 else "MEDIUM",
                        },
                    )

        self.analysis_results["performance_issues"] = performance_issues

    def _detect_security_alerts(self) -> None:
        """Detect security-related log entries"""
        security_alerts = []

        for entry in self.log_entries:
            message_lower = entry.message.lower()

            for pattern, description in self.security_patterns:
                if re.search(pattern, message_lower):
                    security_alerts.append(
                        {
                            "alert_type": description,
                            "message": entry.message[:200],
                            "timestamp": entry.timestamp.isoformat(),
                            "source": entry.source,
                            "severity": "HIGH",
                        },
                    )

        self.analysis_results["security_alerts"] = security_alerts

    def _identify_new_error_patterns(self) -> None:
        """Identify new or unusual error patterns"""
        # This is a simplified implementation
        # In production, you'd compare against historical patterns

        error_entries = [e for e in self.log_entries if e.is_error]
        error_patterns = Counter()

        for entry in error_entries:
            # Extract key words from error messages
            words = re.findall(r"\b[a-zA-Z]{4,}\b", entry.message.lower())
            key_words = [w for w in words if w not in ["error", "failed", "exception", "warning"]]

            if key_words:
                pattern = " ".join(sorted(key_words[:3]))  # Top 3 keywords
                error_patterns[pattern] += 1

        # Identify patterns that appear frequently (potential new issues)
        new_patterns = [
            {"pattern": pattern, "count": count}
            for pattern, count in error_patterns.most_common(5)
            if count >= 3  # Appeared at least 3 times
        ]

        self.analysis_results["new_error_patterns"] = new_patterns

    def generate_daily_digest(self) -> str:
        """Generate daily log digest report"""
        results = self.analysis_results

        report_lines = []

        # Header
        report_lines.extend(
            [
                "# 📊 Daily Log Intelligence Digest",
                "",
                f"**Analysis Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                f"**Time Window**: Last {results.get('time_window_hours', 24)} hours",
                f"**Total Log Entries**: {results['total_entries']:,}",
                "",
                "## 🚨 Executive Summary",
                "",
                f"- **Error Count**: {results['error_count']:,}",
                f"- **Warning Count**: {results['warning_count']:,}",
                f"- **Critical Alerts**: {len(results['critical_patterns'])}",
                f"- **Performance Issues**: {len(results['performance_issues'])}",
                f"- **Security Alerts**: {len(results['security_alerts'])}",
                "",
            ],
        )

        # Error Trends
        if results.get("error_trends"):
            trends = results["error_trends"]
            trend_emoji = "📈" if trends["trend_percentage"] > 0 else "📉" if trends["trend_percentage"] < 0 else "➡️"

            report_lines.extend(
                [
                    "## 📈 Error Trends",
                    "",
                    f"- **Current Hour**: {trends['current_hour_errors']} errors",
                    f"- **Previous Hour**: {trends['previous_hour_errors']} errors",
                    f"- **Trend**: {trend_emoji} {trends['trend_percentage']:+.1f}%",
                    "",
                ],
            )

            if abs(trends["trend_percentage"]) > 50:
                report_lines.extend(
                    [
                        f"⚠️ **Alert**: Error rate changed by {trends['trend_percentage']:+.1f}% - investigation recommended",
                        "",
                    ],
                )

        # Critical Patterns
        if results["critical_patterns"]:
            report_lines.extend(["## 🚨 Critical Issues Detected", ""])

            for issue in results["critical_patterns"][:10]:
                report_lines.extend(
                    [
                        f"### {issue['pattern']}",
                        f"- **Source**: {issue['source']}",
                        f"- **Time**: {issue['timestamp']}",
                        f"- **Message**: `{issue['message']}`",
                        "",
                    ],
                )

        # Performance Issues
        if results["performance_issues"]:
            report_lines.extend(["## ⚡ Performance Issues", ""])

            high_severity = [p for p in results["performance_issues"] if p["severity"] == "HIGH"]
            if high_severity:
                report_lines.append("### High Severity")
                for issue in high_severity[:5]:
                    report_lines.append(f"- **{issue['issue_type']}**: {issue['message']}")
                report_lines.append("")

        # Security Alerts
        if results["security_alerts"]:
            report_lines.extend(["## 🔒 Security Alerts", ""])

            for alert in results["security_alerts"][:10]:
                report_lines.extend([f"- **{alert['alert_type']}** ({alert['source']}): {alert['message']}"])
            report_lines.append("")

        # Top Errors
        if results["top_errors"]:
            report_lines.extend(["## 🔝 Most Frequent Errors", ""])

            for i, error in enumerate(results["top_errors"][:5], 1):
                report_lines.append(f"{i}. **{error['count']} occurrences**: {error['message']}")

            report_lines.append("")

        # New Error Patterns
        if results["new_error_patterns"]:
            report_lines.extend(["## 🆕 New Error Patterns", ""])

            for pattern in results["new_error_patterns"]:
                report_lines.append(f"- **{pattern['pattern']}**: {pattern['count']} occurrences")

            report_lines.append("")

        # Recommendations
        report_lines.extend(["## 🎯 Recommended Actions", ""])

        if results["critical_patterns"]:
            report_lines.append("1. **Immediate**: Investigate critical issues listed above")

        if results.get("error_trends", {}).get("trend_percentage", 0) > 25:
            report_lines.append("2. **High Priority**: Error rate is increasing - check recent deployments")

        if results["performance_issues"]:
            report_lines.append("3. **Medium Priority**: Review performance issues for optimization opportunities")

        if results["security_alerts"]:
            report_lines.append("4. **Security**: Review security alerts and strengthen monitoring")

        if not any([results["critical_patterns"], results["performance_issues"], results["security_alerts"]]):
            report_lines.extend(
                [
                    "✅ **All Clear**: No critical issues detected in the analyzed time window.",
                    "",
                    "**Routine Actions**:",
                    "- Continue monitoring trends",
                    "- Review top error patterns for optimization",
                    "- Maintain current logging levels",
                ],
            )

        report_lines.extend(
            [
                "",
                "---",
                "",
                "*This digest is generated automatically by the Log Intelligence System.*",
                "*For real-time alerts, monitor the production monitoring dashboard.*",
            ],
        )

        return "\n".join(report_lines)

    def save_analysis_results(self) -> None:
        """Save analysis results to files"""
        # Save JSON results
        results_path = Path("log_intelligence_results.json")
        with open(results_path, "w") as f:
            json.dump(self.analysis_results, f, indent=2, default=str)

        # Save daily digest
        digest = self.generate_daily_digest()
        digest_path = Path("daily_log_digest.md")
        with open(digest_path, "w") as f:
            f.write(digest)

        print(f"Analysis results saved to: {results_path}")
        print(f"Daily digest saved to: {digest_path}")

        # Set GitHub Actions outputs
        if os.getenv("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"has_critical_issues={'true' if self.analysis_results['critical_patterns'] else 'false'}\n")
                f.write(f"error_count={self.analysis_results['error_count']}\n")
                f.write(f"critical_count={len(self.analysis_results['critical_patterns'])}\n")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Log Intelligence Analyzer")
    parser.add_argument("--log-dirs", nargs="+", type=Path, help="Directories to search for log files")
    parser.add_argument("--hours", type=int, default=24, help="Hours of history to analyze")
    parser.add_argument("--max-files", type=int, default=50, help="Maximum number of log files to process")
    parser.add_argument(
        "--output-format", choices=["console", "json", "markdown"], default="console", help="Output format",
    )

    args = parser.parse_args()

    try:
        log_dirs = args.log_dirs or [Path("logs")]
        analyzer = LogIntelligenceAnalyzer(log_dirs)

        analyzer.analyze_logs(args.hours, args.max_files)

        if args.output_format == "json":
            print(json.dumps(analyzer.analysis_results, indent=2, default=str))
        elif args.output_format == "markdown":
            digest = analyzer.generate_daily_digest()
            print(digest)
        else:
            # Console summary
            results = analyzer.analysis_results
            print("\n" + "=" * 80)
            print("📊 LOG INTELLIGENCE SUMMARY")
            print("=" * 80)
            print(f"Total Entries: {results['total_entries']:,}")
            print(f"Errors: {results['error_count']:,}")
            print(f"Warnings: {results['warning_count']:,}")
            print(f"Critical Issues: {len(results['critical_patterns'])}")
            print(f"Performance Issues: {len(results['performance_issues'])}")
            print(f"Security Alerts: {len(results['security_alerts'])}")

            if results["critical_patterns"]:
                print("\n🚨 CRITICAL ISSUES:")
                for issue in results["critical_patterns"][:3]:
                    print(f"  - {issue['pattern']}: {issue['message'][:60]}...")

        # Save results
        analyzer.save_analysis_results()

        # Exit with error code if critical issues found
        if analyzer.analysis_results["critical_patterns"]:
            return 1

        return 0

    except Exception as e:
        print(f"Log analysis failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

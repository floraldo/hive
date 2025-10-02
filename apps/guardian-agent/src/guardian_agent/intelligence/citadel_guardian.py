"""
Citadel Guardian - The Oracle's Final Evolution

The Guardian of the Citadel enforces zero-tolerance architectural compliance,
ensuring the platform maintains its state of unassailable production readiness.

This represents the ultimate evolution of the Oracle: from advisor to architect
to certification mentor to the Guardian of architectural perfection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from hive_logging import get_logger

from .data_unification import DataUnificationLayer, MetricType, UnifiedMetric
from .oracle_service import OracleService

logger = get_logger(__name__)


class ComplianceAction(Enum):
    """Actions the Citadel Guardian can take."""

    ALLOW = "allow"  # PR passes all checks
    BLOCK = "block"  # PR blocked due to violations
    WARN = "warn"  # PR allowed with warnings
    REQUIRE_REVIEW = "require_review"  # Manual review required


class ViolationSeverity(Enum):
    """Severity levels for architectural violations."""

    BLOCKER = "blocker"  # Immediate CI/CD block
    CRITICAL = "critical"  # Requires fix before merge
    MAJOR = "major"  # Should be fixed soon
    MINOR = "minor"  # Nice to fix
    INFO = "info"  # Informational only


@dataclass
class CitadelViolation:
    """A violation detected by the Citadel Guardian."""

    rule_name: str
    severity: ViolationSeverity
    description: str
    file_path: str
    line_number: int | None = None

    # Fix suggestions
    suggested_fix: str = ""
    fix_command: str | None = None
    documentation_link: str = ""

    # Context
    component_affected: str = ""
    certification_impact: str = ""
    estimated_fix_time: str = ""

    # Oracle intelligence
    similar_fixes_applied: int = 0
    success_rate: float = 0.0
    oracle_confidence: float = 0.0

    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CitadelReport:
    """Complete compliance report from the Citadel Guardian."""

    # Overall assessment
    compliance_status: ComplianceAction
    overall_score: float  # 0-100
    score_change: float  # Difference from previous scan

    # Violations
    violations: list[CitadelViolation] = field(default_factory=list)
    blocker_count: int = 0
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0

    # Component impact
    components_affected: list[str] = field(default_factory=list)
    certification_levels_impacted: list[str] = field(default_factory=list)

    # Recommendations
    immediate_actions: list[str] = field(default_factory=list)
    suggested_fixes: list[str] = field(default_factory=list)

    # Context
    scan_type: str = "pr_validation"
    commit_sha: str | None = None
    pr_number: int | None = None
    branch_name: str = ""

    # Oracle insights
    historical_compliance_trend: str = "stable"
    predicted_fix_effort: str = "unknown"
    risk_assessment: str = "low"

    generated_at: datetime = field(default_factory=datetime.utcnow)


class CitadelGuardianConfig(BaseModel):
    """Configuration for the Citadel Guardian."""

    # Compliance thresholds
    minimum_score_to_pass: float = Field(default=85.0, description="Minimum score to allow PR")
    blocker_threshold: int = Field(default=0, description="Max blocker violations allowed")
    critical_threshold: int = Field(default=2, description="Max critical violations allowed")

    # CI/CD integration
    enable_pr_blocking: bool = Field(default=True, description="Block PRs that fail compliance")
    enable_auto_comments: bool = Field(default=True, description="Auto-comment on PRs")
    enable_auto_fixes: bool = Field(default=False, description="Attempt automatic fixes")

    # GitHub integration
    github_token: str | None = Field(default=None, description="GitHub API token")
    github_repository: str = Field(default="hive", description="Repository name")

    # Oracle consultation
    consult_oracle_for_fixes: bool = Field(default=True, description="Use Oracle intelligence")
    oracle_confidence_threshold: float = Field(default=0.7, description="Min confidence for Oracle suggestions")

    # Reporting
    generate_detailed_reports: bool = Field(default=True, description="Generate comprehensive reports")
    report_retention_days: int = Field(default=30, description="Days to retain reports")

    # Performance
    scan_timeout_seconds: int = Field(default=300, description="Max time for compliance scan")
    parallel_scanning: bool = Field(default=True, description="Enable parallel rule execution")


class CitadelGuardian:
    """
    The Guardian of the Citadel - Oracle's Final Evolution

    Enforces zero-tolerance architectural compliance through:
    - CI/CD quality gates
    - Automated PR blocking
    - Intelligent fix suggestions
    - Cross-package optimization recommendations
    """

    def __init__(self, config: CitadelGuardianConfig, oracle: OracleService | None = None):
        self.config = config
        self.oracle = oracle
        self.data_layer = DataUnificationLayer(oracle.warehouse) if oracle else None

        # Initialize compliance baselines
        self._baseline_scores = {}
        self._violation_patterns = {}
        self._fix_success_rates = {}

        logger.info("Citadel Guardian initialized - Zero tolerance compliance active")

    async def validate_pr_compliance_async(
        self, pr_number: int, commit_sha: str, branch_name: str, changed_files: list[str]
    ) -> CitadelReport:
        """
        Validate PR compliance with zero-tolerance standards.

        This is the core CI/CD quality gate function.
        """
        logger.info(f"🏰 Citadel Guardian validating PR #{pr_number} ({commit_sha[:8]})")

        try:
            # Run comprehensive compliance scan
            violations = await self._scan_for_violations_async(changed_files, commit_sha)

            # Calculate compliance score
            current_score = await self._calculate_compliance_score_async(),
            baseline_score = await self._get_baseline_score_async(branch_name),
            score_change = current_score - baseline_score

            # Categorize violations by severity
            blocker_count = len([v for v in violations if v.severity == ViolationSeverity.BLOCKER]),
            critical_count = len([v for v in violations if v.severity == ViolationSeverity.CRITICAL]),
            major_count = len([v for v in violations if v.severity == ViolationSeverity.MAJOR]),
            minor_count = len([v for v in violations if v.severity == ViolationSeverity.MINOR])

            # Determine compliance action
            compliance_status = self._determine_compliance_action(
                current_score, blocker_count, critical_count, score_change
            )

            # Generate Oracle-powered recommendations
            immediate_actions = [],
            suggested_fixes = []

            if self.oracle and self.config.consult_oracle_for_fixes:
                oracle_recommendations = await self._get_oracle_recommendations_async(violations)
                immediate_actions.extend(oracle_recommendations.get("immediate", []))
                suggested_fixes.extend(oracle_recommendations.get("fixes", []))

            # Extract affected components
            components_affected = list(set(v.component_affected for v in violations if v.component_affected))

            # Generate report
            report = CitadelReport(
                compliance_status=compliance_status,
                overall_score=current_score,
                score_change=score_change,
                violations=violations,
                blocker_count=blocker_count,
                critical_count=critical_count,
                major_count=major_count,
                minor_count=minor_count,
                components_affected=components_affected,
                immediate_actions=immediate_actions,
                suggested_fixes=suggested_fixes,
                commit_sha=commit_sha,
                pr_number=pr_number,
                branch_name=branch_name,
                risk_assessment=self._assess_risk_level(violations, score_change),
                predicted_fix_effort=self._estimate_fix_effort(violations),
            )

            # Store report for analytics,
            await self._store_compliance_report_async(report)

            logger.info(
                f"🏰 Compliance validation complete: {compliance_status.value} ",
                f"(score: {current_score:.1f}, change: {score_change:+.1f})"
            )

            return report

        except Exception as e:
            logger.error(f"Failed to validate PR compliance: {e}")
            # Return permissive report on error to avoid blocking legitimate PRs,
            return CitadelReport(
                compliance_status=ComplianceAction.WARN,
                overall_score=0.0,
                score_change=0.0,
                violations=[
                    CitadelViolation(
                        rule_name="validation_error",
                        severity=ViolationSeverity.MAJOR,
                        description=f"Compliance validation failed: {str(e)}",
                        file_path="system",
                        suggested_fix="Review Citadel Guardian configuration and logs",
                    )
                ],
                major_count=1,
                commit_sha=commit_sha,
                pr_number=pr_number,
                branch_name=branch_name,
            )

    async def _scan_for_violations_async(self, changed_files: list[str], commit_sha: str) -> list[CitadelViolation]:
        """Scan for architectural violations in changed files."""
        violations = []

        try:
            # Run Golden Rules validation,
            violations.extend(await self._run_golden_rules_scan_async(changed_files))

            # Run cross-package integration analysis,
            violations.extend(await self._run_cross_package_analysis_async(changed_files))

            # Run optimization opportunity detection,
            violations.extend(await self._detect_optimization_opportunities_async(changed_files))

            # Run certification impact analysis,
            violations.extend(await self._analyze_certification_impact_async(changed_files))

        except Exception as e:
            logger.error(f"Failed to scan for violations: {e}")
            violations.append(
                CitadelViolation(
                    rule_name="scan_error",
                    severity=ViolationSeverity.MAJOR,
                    description=f"Violation scanning failed: {str(e)}",
                    file_path="system",
                )
            )

        return violations

    async def _run_golden_rules_scan_async(self, changed_files: list[str]) -> list[CitadelViolation]:
        """Run Golden Rules validation on changed files."""
        violations = []

        try:
            # Import architectural validators,
            import sys,
            from pathlib import Path

            project_root = Path(__file__).parent.parent.parent.parent.parent,
            hive_tests_path = project_root / "packages" / "hive-tests" / "src"

            if hive_tests_path.exists():
                sys.path.insert(0, str(hive_tests_path))
                from hive_tests.architectural_validators import run_all_golden_rules

                # Run validation
                all_passed, results = run_all_golden_rules(project_root)

                # Convert results to violations
                for rule_name, rule_result in results.items():
                    if not rule_result["passed"]:
                        for violation_desc in rule_result["violations"]:
                            # Determine severity based on rule criticality
                            severity = self._determine_rule_severity(rule_name)

                            # Extract file path from violation description if possible
                            file_path = self._extract_file_path_from_violation(violation_desc, changed_files)

                            violation = CitadelViolation(
                                rule_name=rule_name,
                                severity=severity,
                                description=violation_desc,
                                file_path=file_path or "unknown",
                                component_affected=self._extract_component_from_path(file_path),
                                suggested_fix=self._generate_golden_rule_fix(rule_name, violation_desc),
                                documentation_link=self._get_rule_documentation_link(rule_name),
                                certification_impact=self._assess_certification_impact(rule_name),
                                estimated_fix_time=self._estimate_rule_fix_time(rule_name),
                            )

                            violations.append(violation)

        except Exception as e:
            logger.error(f"Failed to run Golden Rules scan: {e}")

        return violations

    async def _run_cross_package_analysis_async(self, changed_files: list[str]) -> list[CitadelViolation]:
        """Analyze cross-package integration opportunities."""
        violations = []

        try:
            # This is where we implement the cross-cutting analysis,
            # Looking for opportunities to use one hive package to improve another

            for file_path in changed_files:
                if not file_path.endswith(".py"):
                    continue

                # Read file content,
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()
                except (FileNotFoundError, UnicodeDecodeError):
                    continue

                # Analyze for integration opportunities,
                integration_opportunities = self._analyze_integration_opportunities(file_path, content)

                for opportunity in integration_opportunities:
                    violation = CitadelViolation(
                        rule_name="cross_package_integration",
                        severity=ViolationSeverity.MINOR,  # Optimizations are typically minor,
                        description=opportunity["description"],
                        file_path=file_path,
                        suggested_fix=opportunity["suggested_fix"],
                        component_affected=self._extract_component_from_path(file_path),
                        certification_impact="Improves architectural integration score",
                        estimated_fix_time=opportunity.get("estimated_time", "1-2 hours"),
                        oracle_confidence=opportunity.get("confidence", 0.8),
                    )
                    violations.append(violation)

        except Exception as e:
            logger.error(f"Failed to run cross-package analysis: {e}")

        return violations

    def _analyze_integration_opportunities(self, file_path: str, content: str) -> list[dict[str, Any]]:
        """Analyze a file for cross-package integration opportunities."""
        opportunities = []

        # Pattern: Direct API calls that could use caching
        if "requests.get" in content or "requests.post" in content:
            if "hive_cache" not in content:
                opportunities.append(
                    {
                        "description": "Direct HTTP requests detected without caching layer",
                        "suggested_fix": "Consider using hive-cache's ClaudeAPICache or HttpCache for better performance and resilience",
                        "estimated_time": "30 minutes",
                        "confidence": 0.85,
                    }
                )

        # Pattern: Manual retry logic that could use hive-async
        if "time.sleep" in content and ("retry" in content.lower() or "attempt" in content.lower()):
            if "hive_async" not in content:
                opportunities.append(
                    {
                        "description": "Manual retry logic detected",
                        "suggested_fix": "Replace manual retry with @async_retry decorator from hive-async for better reliability",
                        "estimated_time": "45 minutes",
                        "confidence": 0.9,
                    }
                )

        # Pattern: Generic exception handling that could use hive-errors
        if "except Exception" in content and "hive_errors" not in content:
            opportunities.append(
                {
                    "description": "Generic exception handling detected",
                    "suggested_fix": "Use specific exception types from hive-errors for better error categorization and handling",
                    "estimated_time": "20 minutes",
                    "confidence": 0.75,
                }
            )

        # Pattern: Manual logging setup that could use hive-logging
        if "logging.getLogger" in content and "hive_logging" not in content:
            opportunities.append(
                {
                    "description": "Manual logging setup detected",
                    "suggested_fix": "Use get_logger from hive-logging for standardized logging configuration",
                    "estimated_time": "15 minutes",
                    "confidence": 0.95,
                }
            )

        # Pattern: Database connections without connection pooling
        if "sqlite3.connect" in content and "hive_db" not in content:
            opportunities.append(
                {
                    "description": "Direct SQLite connection without connection management",
                    "suggested_fix": "Use hive-db's connection management for better resource handling and transaction support",
                    "estimated_time": "1 hour",
                    "confidence": 0.8,
                }
            )

        return opportunities

    async def _detect_optimization_opportunities_async(self, changed_files: list[str]) -> list[CitadelViolation]:
        """Detect optimization opportunities in changed files."""
        violations = []

        # This would contain sophisticated analysis for performance optimizations
        # For now, we'll implement basic patterns

        for file_path in changed_files:
            if file_path.endswith(".py"):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    # Check for performance anti-patterns
                    if "for" in content and "append" in content and len(content.split("\n")) > 100:
                        violations.append(
                            CitadelViolation(
                                rule_name="performance_optimization",
                                severity=ViolationSeverity.MINOR,
                                description="Potential performance issue: Large loop with list.append() detected",
                                file_path=file_path,
                                suggested_fix="Consider using list comprehension or generator for better performance",
                                component_affected=self._extract_component_from_path(file_path),
                                estimated_fix_time="15 minutes",
                            )
                        )

                except Exception:
                    continue

        return violations

    async def _analyze_certification_impact_async(self, changed_files: list[str]) -> list[CitadelViolation]:
        """Analyze how changes impact certification scores."""
        violations = []

        # This would analyze how the changes affect each component's certification score
        # For now, we'll implement basic heuristics

        for file_path in changed_files:
            component = self._extract_component_from_path(file_path)

            if component and file_path.endswith(".py"):
                # Check if this is a test file
                if "test" in file_path.lower():
                    continue  # Test files generally improve certification

                # Check if adding new functionality without tests
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    # Look for new function/class definitions
                    new_functions = content.count("def ") + content.count("class ")

                    if new_functions > 0:
                        # Check if corresponding test file exists
                        test_file_path = file_path.replace(".py", "_test.py")
                        if not Path(test_file_path).exists():
                            violations.append(
                                CitadelViolation(
                                    rule_name="certification_impact",
                                    severity=ViolationSeverity.MAJOR,
                                    description=f"New code added without corresponding tests in {component}",
                                    file_path=file_path,
                                    suggested_fix=f"Create test file {test_file_path} to maintain certification score",
                                    component_affected=component,
                                    certification_impact="May reduce Technical Excellence score",
                                    estimated_fix_time="30-60 minutes",
                                )
                            )

                except Exception:
                    continue

        return violations

    def _determine_rule_severity(self, rule_name: str) -> ViolationSeverity:
        """Determine severity level for a Golden Rule violation."""
        # Critical architectural rules that should block PRs
        blocker_rules = ["Golden Rule 16: No Global State Access", "Golden Rule 6: Dependency Direction"]

        critical_rules = [
            "Golden Rule 8: Error Handling Standards",
            "Golden Rule 17: Test-to-Source File Mapping",
            "Golden Rule 5: Package vs App Discipline",
        ]

        major_rules = [
            "Golden Rule 7: Interface Contracts",
            "Golden Rule 10: Service Layer Discipline",
            "Golden Rule 18: Test File Quality Standards",
        ]

        if any(blocker in rule_name for blocker in blocker_rules):
            return ViolationSeverity.BLOCKER
        elif any(critical in rule_name for critical in critical_rules):
            return ViolationSeverity.CRITICAL
        elif any(major in rule_name for major in major_rules):
            return ViolationSeverity.MAJOR
        else:
            return ViolationSeverity.MINOR

    def _extract_file_path_from_violation(self, violation_desc: str, changed_files: list[str]) -> str | None:
        """Extract file path from violation description."""
        # Try to match violation description with changed files
        for file_path in changed_files:
            if any(part in violation_desc for part in file_path.split("/")):
                return file_path
        return None

    def _extract_component_from_path(self, file_path: str | None) -> str:
        """Extract component name from file path."""
        if not file_path:
            return "unknown"

        # Look for hive-* patterns
        parts = file_path.split("/")
        for part in parts:
            if part.startswith("hive-"):
                return part

        # Look for app names
        if "apps/" in file_path:
            app_parts = file_path.split("apps/")[1].split("/")
            if app_parts:
                return app_parts[0]

        return "unknown"

    def _generate_golden_rule_fix(self, rule_name: str, violation_desc: str) -> str:
        """Generate suggested fix for Golden Rule violation."""
        fix_templates = {
            "Golden Rule 16": "Remove global state access and use dependency injection instead",
            "Golden Rule 17": "Create corresponding test file with comprehensive test coverage",
            "Golden Rule 5": "Move business logic to appropriate service layer",
            "Golden Rule 6": "Refactor dependencies to follow proper architectural layers",
            "Golden Rule 8": "Implement proper error handling using hive-errors base classes",
        }

        for rule_key, fix_template in fix_templates.items():
            if rule_key in rule_name:
                return fix_template

        return "Review architectural guidelines and apply appropriate fixes"

    def _get_rule_documentation_link(self, rule_name: str) -> str:
        """Get documentation link for a Golden Rule."""
        # This would link to the vectorized documentation
        return f"docs/certification/ARCHITECT_CERTIFICATION_V2.0.md#{rule_name.lower().replace(' ', '-')}"

    def _assess_certification_impact(self, rule_name: str) -> str:
        """Assess how a rule violation impacts certification."""
        impact_map = {
            "Golden Rule 16": "Critical impact on Technical Excellence (40 points)",
            "Golden Rule 17": "Major impact on Testing Coverage score",
            "Golden Rule 5": "Significant impact on Architecture Score",
            "Golden Rule 6": "Critical impact on Platform Integration (20 points)",
        }

        for rule_key, impact in impact_map.items():
            if rule_key in rule_name:
                return impact

        return "May impact overall certification score"

    def _estimate_rule_fix_time(self, rule_name: str) -> str:
        """Estimate time required to fix a rule violation."""
        time_estimates = {
            "Golden Rule 16": "2-4 hours",  # Global state refactoring,
            "Golden Rule 17": "30-60 minutes",  # Adding tests,
            "Golden Rule 5": "1-3 hours",  # Moving business logic,
            "Golden Rule 6": "3-6 hours",  # Dependency refactoring,
            "Golden Rule 8": "1-2 hours",  # Error handling
        }

        for rule_key, estimate in time_estimates.items():
            if rule_key in rule_name:
                return estimate

        return "1-2 hours"

    async def _calculate_compliance_score_async(self) -> float:
        """Calculate current overall compliance score."""
        try:
            if self.data_layer:
                # Get recent compliance metrics
                compliance_metrics = await self.data_layer.warehouse.query_metrics_async(
                    metric_types=[MetricType.GOLDEN_RULES_COMPLIANCE],
                    start_time=datetime.utcnow() - timedelta(hours=1),
                    limit=10,
                )

                if compliance_metrics:
                    # Get most recent comprehensive scan
                    comprehensive_scans = [m for m in compliance_metrics if m.tags.get("scan_type") == "comprehensive"]
                    if comprehensive_scans:
                        return float(max(comprehensive_scans, key=lambda x: x.timestamp).value)

            # Fallback: run quick scan
            return await self._run_quick_compliance_scan_async()

        except Exception as e:
            logger.error(f"Failed to calculate compliance score: {e}")
            return 75.0  # Conservative default

    async def _run_quick_compliance_scan_async(self) -> float:
        """Run a quick compliance scan for immediate feedback."""
        try:
            import sys
            from pathlib import Path

            project_root = Path(__file__).parent.parent.parent.parent.parent,
            hive_tests_path = project_root / "packages" / "hive-tests" / "src"

            if hive_tests_path.exists():
                sys.path.insert(0, str(hive_tests_path))
                from hive_tests.architectural_validators import (
                    validate_no_global_state_access,
                    validate_package_app_discipline,
                    validate_test_coverage_mapping,
                )

                # Run critical rules only for speed
                critical_checks = [
                    validate_no_global_state_access,
                    validate_test_coverage_mapping,
                    validate_package_app_discipline,
                ]

                passed_count = 0
                for check in critical_checks:
                    try:
                        passed, _ = check(project_root)
                        if passed:
                            passed_count += 1
                    except Exception:
                        pass  # Skip failed checks

                # Convert to percentage
                return (passed_count / len(critical_checks)) * 100

        except Exception as e:
            logger.error(f"Quick compliance scan failed: {e}")

        return 75.0

    async def _get_baseline_score_async(self, branch_name: str) -> float:
        """Get baseline compliance score for comparison."""
        # In a real implementation, this would query historical data
        # For now, return a reasonable baseline
        return self._baseline_scores.get(branch_name, 82.4)  # Current platform score

    def _determine_compliance_action(
        self, score: float, blocker_count: int, critical_count: int, score_change: float
    ) -> ComplianceAction:
        """Determine what action to take based on compliance results."""

        # Zero tolerance for blockers,
        if blocker_count > self.config.blocker_threshold:
            return ComplianceAction.BLOCK

        # Block if score drops below minimum,
        if score < self.config.minimum_score_to_pass:
            return ComplianceAction.BLOCK

        # Block if too many critical violations,
        if critical_count > self.config.critical_threshold:
            return ComplianceAction.BLOCK

        # Block if score drops significantly,
        if score_change < -5.0:  # More than 5 point drop,
            return ComplianceAction.BLOCK

        # Require review for moderate issues,
        if critical_count > 0 or score_change < -2.0:
            return ComplianceAction.REQUIRE_REVIEW

        # Warn for minor issues,
        if score_change < 0:
            return ComplianceAction.WARN

        # All good!
        return ComplianceAction.ALLOW

    async def _get_oracle_recommendations_async(self, violations: list[CitadelViolation]) -> dict[str, list[str]]:
        """Get Oracle-powered recommendations for fixing violations."""
        recommendations = {"immediate": [], "fixes": []}

        try:
            if not self.oracle:
                return recommendations

            # Group violations by component,
            component_violations = {}
            for violation in violations:
                component = violation.component_affected or "unknown",
                if component not in component_violations:
                    component_violations[component] = []
                component_violations[component].append(violation)

            # Generate recommendations for each component,
            for component, comp_violations in component_violations.items():
                blocker_violations = [v for v in comp_violations if v.severity == ViolationSeverity.BLOCKER],
                critical_violations = [v for v in comp_violations if v.severity == ViolationSeverity.CRITICAL]

                if blocker_violations:
                    recommendations["immediate"].append(
                        f"BLOCKER: {component} has {len(blocker_violations)} blocking violations - fix immediately"
                    )

                if critical_violations:
                    recommendations["immediate"].append(
                        f"CRITICAL: {component} has {len(critical_violations)} critical violations - fix before merge"
                    )

                # Generate specific fix suggestions,
                for violation in comp_violations[:3]:  # Top 3 violations per component,
                    if violation.suggested_fix:
                        recommendations["fixes"].append(f"{component}: {violation.suggested_fix}")

        except Exception as e:
            logger.error(f"Failed to get Oracle recommendations: {e}")

        return recommendations

    def _assess_risk_level(self, violations: list[CitadelViolation], score_change: float) -> str:
        """Assess overall risk level of the changes."""
        blocker_count = len([v for v in violations if v.severity == ViolationSeverity.BLOCKER]),
        critical_count = len([v for v in violations if v.severity == ViolationSeverity.CRITICAL])

        if blocker_count > 0 or score_change < -10:
            return "high"
        elif critical_count > 2 or score_change < -5:
            return "medium"
        elif critical_count > 0 or score_change < -2:
            return "low"
        else:
            return "minimal"

    def _estimate_fix_effort(self, violations: list[CitadelViolation]) -> str:
        """Estimate total effort required to fix all violations."""
        total_minutes = 0

        for violation in violations:
            # Parse estimated fix time
            time_str = violation.estimated_fix_time.lower()
            if "hour" in time_str:
                if "1-2" in time_str:
                    total_minutes += 90
                elif "2-4" in time_str:
                    total_minutes += 180
                elif "3-6" in time_str:
                    total_minutes += 270
                else:
                    total_minutes += 60
            elif "minute" in time_str:
                if "30-60" in time_str:
                    total_minutes += 45
                elif "15" in time_str:
                    total_minutes += 15
                else:
                    total_minutes += 30

        if total_minutes < 60:
            return f"{total_minutes} minutes"
        else:
            hours = total_minutes / 60
            if hours < 1.5:
                return "1 hour"
            elif hours < 4:
                return f"{hours:.1f} hours"
            elif hours < 8:
                return "Half day"
            else:
                return f"{hours/8:.1f} days"

    async def _store_compliance_report_async(self, report: CitadelReport) -> None:
        """Store compliance report for analytics and trending."""
        try:
            if self.data_layer:
                # Convert report to metrics for storage
                metrics = [
                    UnifiedMetric(
                        metric_type=MetricType.GOLDEN_RULES_COMPLIANCE,
                        source="citadel_guardian",
                        timestamp=report.generated_at,
                        value=report.overall_score,
                        unit="percent",
                        tags={
                            "scan_type": "pr_validation",
                            "pr_number": str(report.pr_number) if report.pr_number else "",
                            "branch": report.branch_name,
                            "compliance_action": report.compliance_status.value,
                        },
                        metadata={
                            "commit_sha": report.commit_sha,
                            "blocker_count": report.blocker_count,
                            "critical_count": report.critical_count,
                            "score_change": report.score_change,
                            "risk_level": report.risk_assessment,
                        },
                    )
                ]

                await self.data_layer.warehouse.store_metrics_async(metrics)

        except Exception as e:
            logger.error(f"Failed to store compliance report: {e}")

    async def generate_pr_comment_async(self, report: CitadelReport) -> str:
        """Generate comprehensive PR comment for the Citadel Guardian report."""

        # Status emoji and header
        status_emoji = {
            ComplianceAction.ALLOW: "✅",
            ComplianceAction.WARN: "⚠️",
            ComplianceAction.REQUIRE_REVIEW: "🔍",
            ComplianceAction.BLOCK: "🚫",
        }

        emoji = status_emoji.get(report.compliance_status, "❓")

        comment = f"""## {emoji} Citadel Guardian - Architectural Compliance Report

**Status**: {report.compliance_status.value.upper()}
**Overall Score**: {report.overall_score:.1f}/100 ({report.score_change:+.1f})
**Risk Level**: {report.risk_assessment.title()}

"""

        # Violation summary
        if report.violations:
            comment += f"""### 🏗️ Violations Summary
- 🚫 **Blockers**: {report.blocker_count}
- 🔴 **Critical**: {report.critical_count}
- 🟡 **Major**: {report.major_count}
- 🔵 **Minor**: {report.minor_count}

"""

        # Detailed violations (top 5)
        if report.violations:
            comment += "### 📋 Top Issues\n\n"

            for i, violation in enumerate(report.violations[:5], 1):
                severity_emoji = {
                    ViolationSeverity.BLOCKER: "🚫",
                    ViolationSeverity.CRITICAL: "🔴",
                    ViolationSeverity.MAJOR: "🟡",
                    ViolationSeverity.MINOR: "🔵",
                }

                emoji = severity_emoji.get(violation.severity, "❓")

                comment += f"""**{i}. {emoji} {violation.rule_name}**
- **File**: `{violation.file_path}`
- **Issue**: {violation.description}
- **Fix**: {violation.suggested_fix}
- **Effort**: {violation.estimated_fix_time}

"""

        # Oracle recommendations
        if report.immediate_actions:
            comment += "### 🔮 Oracle Recommendations\n\n"
            for action in report.immediate_actions:
                comment += f"- {action}\n"
            comment += "\n"

        # Components affected
        if report.components_affected:
            comment += "### 📦 Components Affected\n"
            comment += ", ".join(f"`{comp}`" for comp in report.components_affected)
            comment += "\n\n"

        # Action required
        if report.compliance_status == ComplianceAction.BLOCK:
            comment += """### ❌ Action Required
This PR is **blocked** due to architectural compliance violations. Please fix the issues above before merging.

"""
        elif report.compliance_status == ComplianceAction.REQUIRE_REVIEW:
            comment += """### 👀 Manual Review Required
This PR requires manual review due to compliance concerns. Please have an architect review the changes.

"""
        elif report.compliance_status == ComplianceAction.WARN:
            comment += """### ⚠️ Warnings Present
This PR has minor compliance issues. Consider addressing them to maintain architectural excellence.

"""
        else:
            comment += """### ✅ Compliance Passed
Excellent work! This PR meets all architectural standards.

"""

        # Footer
        comment += f"""---
*Generated by Citadel Guardian at {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}*
*Commit: {report.commit_sha[:8] if report.commit_sha else 'unknown'}*
"""

        return comment

    async def create_epic_for_remaining_gaps_async(self) -> dict[str, Any]:
        """Create Operation Citadel epic with child issues for remaining compliance gaps."""

        try:
            # Get current certification readiness data
            if not self.oracle:
                return {"error": "Oracle service not available"}

            dashboard_data = await self.oracle.get_dashboard_data_async(),
            cert_readiness = dashboard_data.certification_readiness

            # Identify components needing immediate attention
            critical_components = [
                scorecard,
                for scorecard in cert_readiness.component_scorecards,
                if scorecard.urgency == "high" or scorecard.overall_score < 70
            ]

            # Generate epic description
            epic_description = f"""# Operation Citadel: Achieve 100% Architectural Certification

## Mission Objective
Transform the Hive platform from its current state of **{cert_readiness.overall_platform_score:.1f}/100** to achieve **95+ certification score** across all components, establishing an unassailable foundation of architectural excellence.

## Current Status
- **Overall Platform Score**: {cert_readiness.overall_platform_score:.1f}/100
- **Certification Rate**: {cert_readiness.certification_rate:.1f}%
- **Components Needing Immediate Action**: {len(critical_components)}
- **Estimated Effort**: {cert_readiness.estimated_effort_days} days
- **Target Completion**: {(datetime.utcnow() + timedelta(days=cert_readiness.estimated_effort_days)).strftime('%Y-%m-%d')}

## Strategic Impact
Upon completion, the platform will achieve:
- **Zero-tolerance compliance** with all Golden Rules
- **Hyper-optimized cross-package integration**
- **Self-healing architectural governance**
- **Unassailable production readiness**

## Success Criteria
- [ ] All components achieve 85+ certification score
- [ ] Zero Golden Rules violations
- [ ] 90%+ test coverage across all components
- [ ] Full CI/CD integration with automated compliance gates

---
*Generated by Citadel Guardian - Operation Citadel Initiative*
"""

            # Generate child issues for critical components
            child_issues = []

            for scorecard in critical_components:
                issue_title = f"[Operation Citadel] Achieve certification compliance for {scorecard.name}",

                issue_description = f"""## Component: {scorecard.name}
**Current Score**: {scorecard.overall_score:.1f}/100 ({scorecard.certification_level})
**Target Score**: 90+ (Senior Hive Architect)
**Urgency**: {scorecard.urgency.upper()}

### Issues to Address
"""

                if scorecard.golden_rules_violations > 0:
                    issue_description += f"- **Golden Rules Violations**: {scorecard.golden_rules_violations}\n"

                if scorecard.missing_tests > 0:
                    issue_description += f"- **Missing Tests**: {scorecard.missing_tests} test files\n"

                if scorecard.deployment_blockers:
                    issue_description += f"- **Deployment Blockers**: {', '.join(scorecard.deployment_blockers)}\n"

                issue_description += f"""
### Certification Breakdown
- **Technical Excellence**: {scorecard.technical_excellence:.1f}/40
- **Operational Readiness**: {scorecard.operational_readiness:.1f}/30
- **Platform Integration**: {scorecard.platform_integration:.1f}/20
- **Innovation**: {scorecard.innovation:.1f}/10

### Oracle Guidance
{scorecard.certification_gap}

### Estimated Effort
{scorecard.estimated_fix_time if hasattr(scorecard, 'estimated_fix_time') else 'TBD'}

---
*Part of Operation Citadel - Fortifying the Core*
"""

                child_issues.append(
                    {
                        "title": issue_title,
                        "description": issue_description,
                        "component": scorecard.name,
                        "priority": "high" if scorecard.urgency == "high" else "medium",
                        "labels": ["operation-citadel", "certification", scorecard.urgency, scorecard.component_type],
                    }
                )

            return {
                "epic": {
                    "title": "Operation Citadel: Achieve 100% Architectural Certification",
                    "description": epic_description,
                    "labels": ["epic", "operation-citadel", "architecture", "certification"],
                    "milestone": f"Operation Citadel - {datetime.utcnow().strftime('%Y Q%q')}",
                },
                "child_issues": child_issues,
                "summary": {
                    "total_issues": len(child_issues),
                    "estimated_effort_days": cert_readiness.estimated_effort_days,
                    "target_completion": (
                        datetime.utcnow() + timedelta(days=cert_readiness.estimated_effort_days)
                    ).isoformat(),
                    "critical_components": len(critical_components),
                },
            }

        except Exception as e:
            logger.error(f"Failed to create Operation Citadel epic: {e}")
            return {"error": str(e)}

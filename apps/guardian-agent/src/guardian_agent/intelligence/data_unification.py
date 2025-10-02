"""
Data Unification Layer - Single Source of Truth for Platform Intelligence

Centralized storage and ingestion system for all operational data:
- Production Shield alerts and metrics
- CI/CD performance data
- AI model costs and usage
- Guardian Agent findings
- Golden Rules violations
- System performance metrics
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from hive_cache import CacheManager
from hive_db import get_async_session
from hive_logging import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of metrics in the unified system."""

    PRODUCTION_HEALTH = "production_health"
    AI_USAGE = "ai_usage"
    AI_COST = "ai_cost"
    CODE_QUALITY = "code_quality"
    SYSTEM_PERFORMANCE = "system_performance"
    CI_CD_METRICS = "cicd_metrics"
    SECURITY_ALERT = "security_alert"
    ERROR_RATE = "error_rate"
    RESPONSE_TIME = "response_time"
    # Architectural compliance metrics
    ARCHITECTURAL_VIOLATION = "architectural_violation"
    GOLDEN_RULES_COMPLIANCE = "golden_rules_compliance"
    TECHNICAL_DEBT = "technical_debt"
    # New metric types for business intelligence and user analytics
    USER_ENGAGEMENT = "user_engagement"
    FEATURE_ADOPTION = "feature_adoption"
    USER_RETENTION = "user_retention"
    CONVERSION_RATE = "conversion_rate"
    CUSTOMER_SATISFACTION = "customer_satisfaction"
    REVENUE_METRICS = "revenue_metrics"
    BUSINESS_KPI = "business_kpi"
    SUPPORT_METRICS = "support_metrics"
    USER_BEHAVIOR = "user_behavior"

    # New metric types for Architect v2.0 Certification Standards
    CODE_QUALITY_SCORE = "code_quality_score"
    ARCHITECTURE_SCORE = "architecture_score"
    TESTING_COVERAGE = "testing_coverage"
    DEPLOYMENT_READINESS = "deployment_readiness"
    MONITORING_SCORE = "monitoring_score"
    COST_MANAGEMENT_SCORE = "cost_management_score"
    TOOLKIT_UTILIZATION = "toolkit_utilization"
    PLATFORM_INTEGRATION = "platform_integration"
    CERTIFICATION_SCORE = "certification_score"
    INNOVATION_SCORE = "innovation_score"

    # New metric types for Genesis Mandate - Design Intent & Prophecy
    DESIGN_INTENT = "design_intent"
    ARCHITECTURAL_PROPHECY = "architectural_prophecy"
    PROPHECY_ACCURACY = "prophecy_accuracy"
    INTENT_EXTRACTION = "intent_extraction"
    DESIGN_COMPLEXITY = "design_complexity"


@dataclass
class UnifiedMetric:
    """Unified representation of any platform metric."""

    # Core identification
    metric_type: MetricType
    source: str  # guardian-agent, production-shield, hive-ai, etc.
    timestamp: datetime

    # Metric data
    value: float | int | str | dict[str, Any]
    unit: str

    # Context and metadata
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Relationships
    correlation_id: str | None = None
    related_metrics: list[str] = field(default_factory=list)

    # Quality indicators
    confidence: float = 1.0
    data_quality: str = "high"  # high, medium, low


@dataclass
class DataSource:
    """Configuration for a data source."""

    name: str
    source_type: str  # file, database, api, webhook
    location: str  # path, connection string, url
    collection_interval: int  # seconds
    enabled: bool = True
    transform_function: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricsWarehouse:
    """
    Centralized storage for all platform operational metrics.

    Provides time-series storage with efficient querying,
    data retention policies, and analytics capabilities.
    """

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path("data/intelligence")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.cache = CacheManager("metrics_warehouse")
        self._metrics_buffer: list[UnifiedMetric] = []
        self._buffer_size = 1000
        self._flush_interval = 60  # seconds

        # Initialize database schema
        asyncio.create_task(self._initialize_schema_async())

    async def _initialize_schema_async(self) -> None:
        """Initialize the metrics database schema."""
        try:
            async with get_async_session() as session:
                await session.execute(
                    """,
                    CREATE TABLE IF NOT EXISTS unified_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_type TEXT NOT NULL,
                        source TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        value TEXT NOT NULL,  -- JSON-encoded,
                        unit TEXT NOT NULL,
                        tags TEXT,  -- JSON-encoded
                        metadata TEXT,  -- JSON-encoded
                        correlation_id TEXT,
                        confidence REAL DEFAULT 1.0,
                        data_quality TEXT DEFAULT 'high',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                )

                await session.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_metrics_type_timestamp
                    ON unified_metrics(metric_type, timestamp)
                """,
                )

                await session.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_metrics_source_timestamp
                    ON unified_metrics(source, timestamp)
                """,
                )

                await session.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_metrics_correlation
                    ON unified_metrics(correlation_id)
                """,
                )

                await session.commit()

        except Exception as e:
            logger.error(f"Failed to initialize metrics schema: {e}")

    async def store_metric_async(self, metric: UnifiedMetric) -> None:
        """Store a single metric."""
        self._metrics_buffer.append(metric)

        # Flush buffer if it's full
        if len(self._metrics_buffer) >= self._buffer_size:
            await self._flush_buffer_async()

    async def store_metrics_async(self, metrics: list[UnifiedMetric]) -> None:
        """Store multiple metrics efficiently."""
        self._metrics_buffer.extend(metrics)

        # Flush if buffer is getting full
        if len(self._metrics_buffer) >= self._buffer_size:
            await self._flush_buffer_async()

    async def _flush_buffer_async(self) -> None:
        """Flush buffered metrics to database."""
        if not self._metrics_buffer:
            return

        try:
            async with get_async_session() as session:
                for metric in self._metrics_buffer:
                    await session.execute(
                        """,
                        INSERT INTO unified_metrics (
                            metric_type, source, timestamp, value, unit,
                            tags, metadata, correlation_id, confidence, data_quality
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            metric.metric_type.value,
                            metric.source,
                            metric.timestamp,
                            json.dumps(metric.value),
                            metric.unit,
                            json.dumps(metric.tags),
                            json.dumps(metric.metadata),
                            metric.correlation_id,
                            metric.confidence,
                            metric.data_quality,
                        ),
                    )

                await session.commit()

            logger.info(f"Flushed {len(self._metrics_buffer)} metrics to warehouse")
            self._metrics_buffer.clear()

        except Exception as e:
            logger.error(f"Failed to flush metrics buffer: {e}")

    async def query_metrics_async(
        self,
        metric_types: list[MetricType] | None = None,
        sources: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tags: dict[str, str] | None = None,
        limit: int = 1000,
    ) -> list[UnifiedMetric]:
        """Query metrics with flexible filtering."""

        # Build query conditions
        conditions = [],
        params = []

        if metric_types:
            placeholders = ",".join("?" * len(metric_types))
            conditions.append(f"metric_type IN ({placeholders})")
            params.extend([mt.value for mt in metric_types])

        if sources:
            placeholders = ",".join("?" * len(sources))
            conditions.append(f"source IN ({placeholders})")
            params.extend(sources)

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)

        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)

        where_clause = " AND ".join(conditions) if conditions else "1=1",

        query = f"""
            SELECT * FROM unified_metrics
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        try:
            async with get_async_session() as session:
                result = await session.execute(query, params)
                rows = await result.fetchall(),

                metrics = []
                for row in rows:
                    metric = UnifiedMetric(
                        metric_type=MetricType(row.metric_type),
                        source=row.source,
                        timestamp=datetime.fromisoformat(row.timestamp),
                        value=json.loads(row.value),
                        unit=row.unit,
                        tags=json.loads(row.tags or "{}"),
                        metadata=json.loads(row.metadata or "{}"),
                        correlation_id=row.correlation_id,
                        confidence=row.confidence,
                        data_quality=row.data_quality,
                    )

                    # Apply tag filtering if specified
                    if tags:
                        if all(metric.tags.get(k) == v for k, v in tags.items()):
                            metrics.append(metric)
                    else:
                        metrics.append(metric)

                return metrics

        except Exception as e:
            logger.error(f"Failed to query metrics: {e}")
            return []

    async def get_latest_metrics_async(self, metric_type: MetricType, source: str | None = None) -> list[UnifiedMetric]:
        """Get the most recent metrics of a specific type."""
        return await self.query_metrics_async(
            metric_types=[metric_type],
            sources=[source] if source else None,
            limit=100,
        )

    async def get_time_series_async(self, metric_type: MetricType, source: str, hours: int = 24) -> list[UnifiedMetric]:
        """Get time series data for analysis."""
        start_time = datetime.utcnow() - timedelta(hours=hours)

        return await self.query_metrics_async(
            metric_types=[metric_type],
            sources=[source],
            start_time=start_time,
            limit=10000,
        )


class DataUnificationLayer:
    """
    Orchestrates data collection from all platform sources.

    Manages data pipelines, transformations, and ingestion
    into the unified metrics warehouse.
    """

    def __init__(self, warehouse: MetricsWarehouse):
        self.warehouse = warehouse
        self.data_sources: dict[str, DataSource] = {}
        self.collection_tasks: dict[str, asyncio.Task] = {}
        self._running = False

        # Register default data sources
        self._register_default_sources()

    def _register_default_sources(self) -> None:
        """Register default platform data sources."""

        # Production Shield monitoring
        self.register_source(
            DataSource(
                name="production_shield",
                source_type="file",
                location="logs/production_monitoring.json",
                collection_interval=300,  # 5 minutes,
                transform_function="transform_production_shield",
            ),
        )

        # AI metrics from hive-ai
        self.register_source(
            DataSource(
                name="hive_ai_metrics",
                source_type="database",
                location="ai_metrics",
                collection_interval=60,  # 1 minute,
                transform_function="transform_ai_metrics",
            ),
        )

        # Guardian Agent reviews
        self.register_source(
            DataSource(
                name="guardian_reviews",
                source_type="database",
                location="guardian_reviews",
                collection_interval=300,  # 5 minutes,
                transform_function="transform_guardian_reviews",
            ),
        )

        # System performance
        self.register_source(
            DataSource(
                name="system_performance",
                source_type="api",
                location="internal://system_metrics",
                collection_interval=60,  # 1 minute,
                transform_function="transform_system_metrics",
            ),
        )

        # Golden Rules violations - Live architectural validation
        self.register_source(
            DataSource(
                name="architectural_validation",
                source_type="api",
                location="internal://architectural_scan",
                collection_interval=21600,  # 6 hours - comprehensive scan,
                transform_function="transform_architectural_violations",
            ),
        )

        # Continuous compliance monitoring
        self.register_source(
            DataSource(
                name="compliance_monitoring",
                source_type="api",
                location="internal://compliance_check",
                collection_interval=3600,  # 1 hour - quick compliance check,
                transform_function="transform_compliance_metrics",
            ),
        )

        # Business Intelligence & User Analytics Sources

        # User engagement and behavior analytics
        self.register_source(
            DataSource(
                name="user_analytics",
                source_type="api",
                location="internal://user_analytics",
                collection_interval=1800,  # 30 minutes - user behavior changes frequently,
                transform_function="transform_user_analytics",
            ),
        )

        # Feature adoption and usage metrics
        self.register_source(
            DataSource(
                name="feature_metrics",
                source_type="api",
                location="internal://feature_usage",
                collection_interval=3600,  # 1 hour - feature usage patterns,
                transform_function="transform_feature_metrics",
            ),
        )

        # Business KPIs and revenue metrics
        self.register_source(
            DataSource(
                name="business_intelligence",
                source_type="api",
                location="internal://business_kpis",
                collection_interval=14400,  # 4 hours - business metrics are more stable,
                transform_function="transform_business_metrics",
            ),
        )

        # Customer satisfaction and support metrics
        self.register_source(
            DataSource(
                name="customer_health",
                source_type="api",
                location="internal://customer_metrics",
                collection_interval=7200,  # 2 hours - customer health monitoring,
                transform_function="transform_customer_metrics",
            ),
        )

        # Architect v2.0 Certification Standards Sources

        # Comprehensive certification assessment
        self.register_source(
            DataSource(
                name="certification_audit",
                source_type="api",
                location="internal://certification_audit",
                collection_interval=43200,  # 12 hours - comprehensive certification assessment,
                transform_function="transform_certification_metrics",
            ),
        )

        # Code quality and security scanning
        self.register_source(
            DataSource(
                name="code_quality_scan",
                source_type="api",
                location="internal://code_quality",
                collection_interval=7200,  # 2 hours - code quality monitoring,
                transform_function="transform_code_quality_metrics",
            ),
        )

        # Deployment readiness and CI/CD pipeline health
        self.register_source(
            DataSource(
                name="deployment_readiness",
                source_type="api",
                location="internal://deployment_check",
                collection_interval=10800,  # 3 hours - deployment readiness assessment,
                transform_function="transform_deployment_metrics",
            ),
        )

        # Toolkit utilization and platform integration
        self.register_source(
            DataSource(
                name="toolkit_compliance",
                source_type="api",
                location="internal://toolkit_usage",
                collection_interval=21600,  # 6 hours - toolkit utilization analysis,
                transform_function="transform_toolkit_metrics",
            ),
        )

        # Genesis Mandate - Design Intent & Prophecy Sources

        # Design document ingestion and intent extraction
        self.register_source(
            DataSource(
                name="design_intent_ingestion",
                source_type="file",
                location="docs/designs/",
                collection_interval=1800,  # 30 minutes - monitor for new design docs,
                transform_function="transform_design_intent_metrics",
            ),
        )

        # Architectural prophecy generation and tracking
        self.register_source(
            DataSource(
                name="prophecy_tracking",
                source_type="api",
                location="internal://prophecy_engine",
                collection_interval=7200,  # 2 hours - prophecy analysis,
                transform_function="transform_prophecy_metrics",
            ),
        )

        # Prophecy accuracy validation (retrospective analysis)
        self.register_source(
            DataSource(
                name="prophecy_validation",
                source_type="api",
                location="internal://prophecy_validation",
                collection_interval=86400,  # 24 hours - daily accuracy assessment,
                transform_function="transform_prophecy_accuracy_metrics",
            ),
        )

    def register_source(self, source: DataSource) -> None:
        """Register a new data source."""
        self.data_sources[source.name] = source
        logger.info(f"Registered data source: {source.name}")

    async def start_collection_async(self) -> None:
        """Start data collection from all sources."""
        if self._running:
            return

        self._running = True

        for source_name, source in self.data_sources.items():
            if source.enabled:
                task = asyncio.create_task(self._collect_from_source_async(source))
                self.collection_tasks[source_name] = task

        logger.info(f"Started data collection from {len(self.collection_tasks)} sources")

    async def stop_collection_async(self) -> None:
        """Stop data collection."""
        self._running = False

        for task in self.collection_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.collection_tasks.values(), return_exceptions=True)
        self.collection_tasks.clear()

        logger.info("Stopped data collection")

    async def _collect_from_source_async(self, source: DataSource) -> None:
        """Collect data from a specific source."""
        logger.info(f"Starting collection from {source.name}")

        while self._running:
            try:
                # Collect data based on source type
                if source.source_type == "file":
                    metrics = await self._collect_from_file_async(source)
                elif source.source_type == "database":
                    metrics = await self._collect_from_database_async(source)
                elif source.source_type == "api":
                    metrics = await self._collect_from_api_async(source)
                else:
                    logger.warning(f"Unknown source type: {source.source_type}")
                    metrics = []

                # Transform data if needed
                if source.transform_function and metrics:
                    transform_func = getattr(self, source.transform_function, None)
                    if transform_func:
                        metrics = transform_func(metrics, source)

                # Store in warehouse
                if metrics:
                    await self.warehouse.store_metrics_async(metrics)
                    logger.debug(f"Collected {len(metrics)} metrics from {source.name}")

                # Wait for next collection
                await asyncio.sleep(source.collection_interval)

            except Exception as e:
                logger.error(f"Error collecting from {source.name}: {e}")
                await asyncio.sleep(source.collection_interval)

    async def _collect_from_file_async(self, source: DataSource) -> list[UnifiedMetric]:
        """Collect metrics from file source."""
        try:
            file_path = Path(source.location)

            # Handle design documents directory
            if source.name == "design_intent_ingestion":
                return await self._collect_design_documents_async(source.name, file_path)

            # Handle single file sources
            if not file_path.exists():
                return []

            with open(file_path) as f:
                data = json.load(f)

            # Convert to unified metrics format
            return self._convert_raw_data_to_metrics(data, source.name)

        except Exception as e:
            logger.error(f"Failed to collect from file {source.location}: {e}")
            return []

    async def _collect_from_database_async(self, source: DataSource) -> list[UnifiedMetric]:
        """Collect metrics from database source."""
        # Implementation depends on specific database schema
        # This is a placeholder for the actual implementation
        return []

    async def _collect_from_api_async(self, source: DataSource) -> list[UnifiedMetric]:
        """Collect metrics from API source."""
        if source.location == "internal://system_metrics":
            # Collect system metrics using hive-performance
            from hive_performance import SystemMonitor

            monitor = SystemMonitor(),
            system_metrics = await monitor._collect_system_metrics_async()

            return [
                UnifiedMetric(
                    metric_type=MetricType.SYSTEM_PERFORMANCE,
                    source=source.name,
                    timestamp=system_metrics.timestamp,
                    value={
                        "cpu_percent": system_metrics.cpu_percent,
                        "memory_percent": system_metrics.memory_percent,
                        "disk_percent": system_metrics.disk_percent,
                        "active_tasks": system_metrics.active_tasks,
                    },
                    unit="percent",
                    tags={"hostname": system_metrics.hostname},
                ),
            ]

        elif source.location == "internal://architectural_scan":
            # Comprehensive architectural validation scan
            return await self._run_architectural_validation_async(source.name)

        elif source.location == "internal://compliance_check":
            # Quick compliance check
            return await self._run_compliance_check_async(source.name)

        elif source.location == "internal://user_analytics":
            # User engagement and behavior analytics
            return await self._collect_user_analytics_async(source.name)

        elif source.location == "internal://feature_usage":
            # Feature adoption and usage metrics
            return await self._collect_feature_metrics_async(source.name)

        elif source.location == "internal://business_kpis":
            # Business KPIs and revenue metrics
            return await self._collect_business_metrics_async(source.name)

        elif source.location == "internal://customer_metrics":
            # Customer satisfaction and support metrics
            return await self._collect_customer_metrics_async(source.name)

        elif source.location == "internal://certification_audit":
            # Comprehensive certification assessment
            return await self._run_certification_audit_async(source.name)

        elif source.location == "internal://code_quality":
            # Code quality and security scanning
            return await self._collect_code_quality_metrics_async(source.name)

        elif source.location == "internal://deployment_check":
            # Deployment readiness and CI/CD pipeline health
            return await self._collect_deployment_metrics_async(source.name)

        elif source.location == "internal://toolkit_usage":
            # Toolkit utilization and platform integration
            return await self._collect_toolkit_metrics_async(source.name)

        elif source.location == "internal://prophecy_engine":
            # Architectural prophecy generation and tracking
            return await self._collect_prophecy_metrics_async(source.name)

        elif source.location == "internal://prophecy_validation":
            # Prophecy accuracy validation (retrospective analysis)
            return await self._collect_prophecy_accuracy_async(source.name)

        return []

    def _convert_raw_data_to_metrics(self, data: Any, source: str) -> list[UnifiedMetric]:
        """Convert raw data to unified metrics format."""
        # This would be implemented based on the specific data format
        # For now, return empty list
        return []

    async def _run_architectural_validation_async(self, source_name: str) -> list[UnifiedMetric]:
        """Run comprehensive architectural validation using Golden Rules."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Import the architectural validators
            import sys
            from pathlib import Path

            # Add packages to path to import validators
            project_root = Path(__file__).parent.parent.parent.parent.parent,
            hive_tests_path = project_root / "packages" / "hive-tests" / "src"

            if hive_tests_path.exists():
                sys.path.insert(0, str(hive_tests_path))

                from hive_tests.architectural_validators import run_all_golden_rules

                # Run all Golden Rules validation
                all_passed, results = run_all_golden_rules(project_root)

                # Create overall compliance metric
                total_rules = len(results),
                passed_rules = sum(1 for r in results.values() if r["passed"]),
                compliance_score = (passed_rules / total_rules) * 100 if total_rules > 0 else 0

                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.GOLDEN_RULES_COMPLIANCE,
                        source=source_name,
                        timestamp=timestamp,
                        value=compliance_score,
                        unit="percent",
                        tags={
                            "scan_type": "comprehensive",
                            "total_rules": str(total_rules),
                            "passed_rules": str(passed_rules),
                            "failed_rules": str(total_rules - passed_rules),
                        },
                        metadata={"all_passed": all_passed, "detailed_results": results},
                    ),
                )

                # Create individual violation metrics
                for rule_name, rule_result in results.items():
                    if not rule_result["passed"]:
                        for violation in rule_result["violations"]:
                            metrics.append(
                                UnifiedMetric(
                                    metric_type=MetricType.ARCHITECTURAL_VIOLATION,
                                    source=source_name,
                                    timestamp=timestamp,
                                    value=1,  # Each violation counts as 1,
                                    unit="violation",
                                    tags={
                                        "rule_name": rule_name,
                                        "severity": self._determine_violation_severity(rule_name),
                                        "category": self._categorize_rule(rule_name),
                                    },
                                    metadata={"violation_description": violation, "rule_full_name": rule_name},
                                ),
                            )

                # Create technical debt metric
                total_violations = sum(len(r["violations"]) for r in results.values() if not r["passed"]),
                debt_score = min(total_violations * 10, 100)  # Scale to 0-100

                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.TECHNICAL_DEBT,
                        source=source_name,
                        timestamp=timestamp,
                        value=debt_score,
                        unit="debt_points",
                        tags={
                            "total_violations": str(total_violations),
                            "debt_level": "high" if debt_score > 50 else "medium" if debt_score > 20 else "low",
                        },
                        metadata={
                            "calculation": "violations * 10, capped at 100",
                            "scan_timestamp": timestamp.isoformat(),
                        },
                    ),
                )

                logger.info(
                    f"Architectural scan completed: {compliance_score:.1f}% compliance, {total_violations} violations",
                )

        except Exception as e:
            logger.error(f"Failed to run architectural validation: {e}")
            # Create error metric
            metrics.append(
                UnifiedMetric(
                    metric_type=MetricType.ARCHITECTURAL_VIOLATION,
                    source=source_name,
                    timestamp=timestamp,
                    value=1,
                    unit="error",
                    tags={"rule_name": "validation_error", "severity": "critical", "category": "system"},
                    metadata={"error_message": str(e), "error_type": "validation_failure"},
                ),
            )

        return metrics

    async def _run_compliance_check_async(self, source_name: str) -> list[UnifiedMetric]:
        """Run quick compliance check focusing on key metrics."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Quick compliance check - focus on most critical rules
            import sys
            from pathlib import Path

            project_root = Path(__file__).parent.parent.parent.parent.parent,
            hive_tests_path = project_root / "packages" / "hive-tests" / "src"

            if hive_tests_path.exists():
                sys.path.insert(0, str(hive_tests_path))

                # Import specific validators for quick check
                from hive_tests.architectural_validators import (
                    validate_dependency_direction,
                    validate_no_global_state_access,
                    validate_package_app_discipline,
                    validate_test_coverage_mapping,
                )

                # Run critical rules only
                critical_checks = [
                    ("Global State Access", validate_no_global_state_access),
                    ("Test Coverage", validate_test_coverage_mapping),
                    ("Package Discipline", validate_package_app_discipline),
                    ("Dependency Direction", validate_dependency_direction),
                ]

                total_critical = len(critical_checks),
                passed_critical = 0

                for check_name, validator_func in critical_checks:
                    try:
                        passed, violations = validator_func(project_root)
                        if passed:
                            passed_critical += 1

                        # Create metric for this check
                        metrics.append(
                            UnifiedMetric(
                                metric_type=MetricType.GOLDEN_RULES_COMPLIANCE,
                                source=source_name,
                                timestamp=timestamp,
                                value=100 if passed else 0,
                                unit="percent",
                                tags={"scan_type": "quick", "rule_name": check_name, "critical": "true"},
                                metadata={"violations": violations, "violation_count": len(violations)},
                            ),
                        )

                    except Exception as e:
                        logger.error(f"Failed to run {check_name} check: {e}")

                # Overall critical compliance score
                critical_compliance = (passed_critical / total_critical) * 100 if total_critical > 0 else 0

                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.GOLDEN_RULES_COMPLIANCE,
                        source=source_name,
                        timestamp=timestamp,
                        value=critical_compliance,
                        unit="percent",
                        tags={
                            "scan_type": "quick_critical",
                            "checks_passed": str(passed_critical),
                            "total_checks": str(total_critical),
                        },
                        metadata={"check_type": "critical_rules_only", "frequency": "hourly"},
                    ),
                )

                logger.info(f"Quick compliance check: {critical_compliance:.1f}% critical compliance")

        except Exception as e:
            logger.error(f"Failed to run compliance check: {e}")

        return metrics

    async def _collect_user_analytics_async(self, source_name: str) -> list[UnifiedMetric]:
        """Collect user engagement and behavior analytics."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Simulate user analytics data collection
            # In real implementation, this would connect to analytics platforms
            # like Google Analytics, Mixpanel, Amplitude, etc.

            # User engagement metrics
            metrics.extend(
                [
                    UnifiedMetric(
                        metric_type=MetricType.USER_ENGAGEMENT,
                        source=source_name,
                        timestamp=timestamp,
                        value=78.5,  # Daily Active Users percentage,
                        unit="percent",
                        tags={"metric_name": "daily_active_users", "period": "24h", "user_segment": "all"},
                        metadata={"total_users": 1250, "active_users": 982, "trend": "increasing"},
                    ),
                    UnifiedMetric(
                        metric_type=MetricType.USER_ENGAGEMENT,
                        source=source_name,
                        timestamp=timestamp,
                        value=4.2,  # Average session duration in minutes
                        unit="minutes",
                        tags={"metric_name": "avg_session_duration", "period": "24h", "user_segment": "all"},
                        metadata={"sessions_analyzed": 3420, "median_duration": 3.8, "trend": "stable"},
                    ),
                    UnifiedMetric(
                        metric_type=MetricType.USER_BEHAVIOR,
                        source=source_name,
                        timestamp=timestamp,
                        value=12.0,  # Average time to complete project setup in minutes
                        unit="minutes",
                        tags={"workflow": "project_setup", "metric_name": "completion_time", "criticality": "high"},
                        metadata={"completions": 145, "abandonment_rate": 0.28, "industry_benchmark": 4.0},
                    ),
                ],
            )

            # User retention metrics
            metrics.append(
                UnifiedMetric(
                    metric_type=MetricType.USER_RETENTION,
                    source=source_name,
                    timestamp=timestamp,
                    value=85.2,  # 7-day retention rate,
                    unit="percent",
                    tags={"retention_period": "7_days", "user_segment": "new_users", "cohort": "2025_09"},
                    metadata={"cohort_size": 234, "retained_users": 199, "benchmark": 75.0},
                ),
            )

            logger.info(f"Collected {len(metrics)} user analytics metrics")

        except Exception as e:
            logger.error(f"Failed to collect user analytics: {e}")

        return metrics

    async def _collect_feature_metrics_async(self, source_name: str) -> list[UnifiedMetric]:
        """Collect feature adoption and usage metrics."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Feature adoption data
            feature_data = [
                {
                    "name": "Code Summarization",
                    "adoption_rate": 95.0,
                    "usage_frequency": "daily",
                    "user_segment": "enterprise",
                    "operational_cost": 450.0,  # Monthly cost in USD,
                    "satisfaction_score": 4.8,
                },
                {
                    "name": "Automated Refactoring",
                    "adoption_rate": 2.0,
                    "usage_frequency": "rare",
                    "user_segment": "all",
                    "operational_cost": 1200.0,  # Monthly cost in USD,
                    "satisfaction_score": 2.1,
                },
                {
                    "name": "AI Code Review",
                    "adoption_rate": 67.5,
                    "usage_frequency": "weekly",
                    "user_segment": "professional",
                    "operational_cost": 680.0,  # Monthly cost in USD,
                    "satisfaction_score": 4.2,
                },
                {
                    "name": "Vector Search",
                    "adoption_rate": 45.0,
                    "usage_frequency": "daily",
                    "user_segment": "enterprise",
                    "operational_cost": 320.0,  # Monthly cost in USD,
                    "satisfaction_score": 4.5,
                },
            ]

            for feature in feature_data:
                # Feature adoption metric
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.FEATURE_ADOPTION,
                        source=source_name,
                        timestamp=timestamp,
                        value=feature["adoption_rate"],
                        unit="percent",
                        tags={
                            "feature_name": feature["name"],
                            "user_segment": feature["user_segment"],
                            "usage_frequency": feature["usage_frequency"],
                        },
                        metadata={
                            "operational_cost": feature["operational_cost"],
                            "satisfaction_score": feature["satisfaction_score"],
                            "cost_per_user": feature["operational_cost"] / max(feature["adoption_rate"], 1),
                            "roi_score": feature["satisfaction_score"]
                            * feature["adoption_rate"]
                            / (feature["operational_cost"] / 100),
                        },
                    ),
                )

            logger.info(f"Collected {len(metrics)} feature adoption metrics")

        except Exception as e:
            logger.error(f"Failed to collect feature metrics: {e}")

        return metrics

    async def _collect_business_metrics_async(self, source_name: str) -> list[UnifiedMetric]:
        """Collect business KPIs and revenue metrics."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Revenue and business metrics
            metrics.extend(
                [
                    UnifiedMetric(
                        metric_type=MetricType.REVENUE_METRICS,
                        source=source_name,
                        timestamp=timestamp,
                        value=47500.0,  # Monthly Recurring Revenue,
                        unit="usd",
                        tags={"metric_name": "mrr", "period": "monthly", "currency": "usd"},
                        metadata={
                            "growth_rate": 0.12,  # 12% month-over-month,
                            "churn_rate": 0.05,  # 5% monthly churn,
                            "new_revenue": 6800.0,
                        },
                    ),
                    UnifiedMetric(
                        metric_type=MetricType.CONVERSION_RATE,
                        source=source_name,
                        timestamp=timestamp,
                        value=3.8,  # Trial to paid conversion rate
                        unit="percent",
                        tags={"conversion_type": "trial_to_paid", "period": "30_days", "user_segment": "all"},
                        metadata={
                            "trial_users": 342,
                            "converted_users": 13,
                            "benchmark": 5.2,
                            "trend": "below_benchmark",
                        },
                    ),
                    UnifiedMetric(
                        metric_type=MetricType.BUSINESS_KPI,
                        source=source_name,
                        timestamp=timestamp,
                        value=125.0,  # Customer Acquisition Cost
                        unit="usd",
                        tags={"metric_name": "cac", "user_segment": "enterprise", "period": "monthly"},
                        metadata={
                            "ltv_cac_ratio": 3.2,  # Lifetime Value to CAC ratio,
                            "payback_period": 8.5,  # months,
                            "target_cac": 100.0,
                        },
                    ),
                ],
            )

            logger.info(f"Collected {len(metrics)} business metrics")

        except Exception as e:
            logger.error(f"Failed to collect business metrics: {e}")

        return metrics

    async def _collect_customer_metrics_async(self, source_name: str) -> list[UnifiedMetric]:
        """Collect customer satisfaction and support metrics."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Customer health and satisfaction metrics
            metrics.extend(
                [
                    UnifiedMetric(
                        metric_type=MetricType.CUSTOMER_SATISFACTION,
                        source=source_name,
                        timestamp=timestamp,
                        value=8.2,  # Net Promoter Score,
                        unit="nps_score",
                        tags={"metric_name": "nps", "survey_period": "quarterly", "user_segment": "all"},
                        metadata={"responses": 187, "promoters": 112, "detractors": 23, "industry_benchmark": 7.5},
                    ),
                    UnifiedMetric(
                        metric_type=MetricType.SUPPORT_METRICS,
                        source=source_name,
                        timestamp=timestamp,
                        value=2.3,  # Average first response time in hours
                        unit="hours",
                        tags={"metric_name": "first_response_time", "priority": "all", "period": "7_days"},
                        metadata={"tickets_analyzed": 89, "sla_target": 4.0, "resolution_rate": 0.94},
                    ),
                    UnifiedMetric(
                        metric_type=MetricType.SUPPORT_METRICS,
                        source=source_name,
                        timestamp=timestamp,
                        value=15,  # Open support tickets
                        unit="count",
                        tags={"metric_name": "open_tickets", "priority": "high", "escalated": "true"},
                        metadata={"avg_age_hours": 18.5, "oldest_ticket_hours": 72, "trend": "increasing"},
                    ),
                ],
            )

            # Customer health alerts
            # Simulate enterprise client with issues
            metrics.append(
                UnifiedMetric(
                    metric_type=MetricType.CUSTOMER_SATISFACTION,
                    source=source_name,
                    timestamp=timestamp,
                    value=0.5,  # 50% increase in API errors,
                    unit="error_rate_change",
                    tags={
                        "customer": "AlphaCorp",
                        "segment": "enterprise",
                        "alert_type": "api_errors",
                        "urgency": "high",
                    },
                    metadata={
                        "baseline_error_rate": 0.002,
                        "current_error_rate": 0.003,
                        "duration_hours": 48,
                        "account_manager": "sarah.chen@hive.com",
                    },
                ),
            )

            logger.info(f"Collected {len(metrics)} customer metrics")

        except Exception as e:
            logger.error(f"Failed to collect customer metrics: {e}")

        return metrics

    def _determine_violation_severity(self, rule_name: str) -> str:
        """Determine severity level based on rule name."""
        high_severity_rules = [
            "Golden Rule 16: No Global State Access",
            "Golden Rule 6: Dependency Direction",
            "Golden Rule 8: Error Handling Standards",
        ]

        medium_severity_rules = [
            "Golden Rule 17: Test-to-Source File Mapping",
            "Golden Rule 5: Package vs App Discipline",
            "Golden Rule 7: Interface Contracts",
        ]

        if any(high_rule in rule_name for high_rule in high_severity_rules):
            return "high"
        elif any(med_rule in rule_name for med_rule in medium_severity_rules):
            return "medium"
        else:
            return "low"

    def _categorize_rule(self, rule_name: str) -> str:
        """Categorize rule by architectural concern."""
        if "Test" in rule_name:
            return "testing"
        elif "State" in rule_name or "Global" in rule_name:
            return "architecture"
        elif "Dependency" in rule_name:
            return "dependencies"
        elif "Error" in rule_name:
            return "reliability"
        elif "Interface" in rule_name:
            return "contracts"
        elif "Package" in rule_name or "App" in rule_name:
            return "organization"
        else:
            return "standards"

    # Transform functions for different data sources
    def transform_production_shield(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform Production Shield data."""
        # Add source-specific transformations
        for metric in metrics:
            metric.tags["shield_type"] = "production"
        return metrics

    def transform_ai_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform AI metrics data."""
        # Add AI-specific tags and metadata
        for metric in metrics:
            metric.tags["component"] = "ai"
        return metrics

    def transform_guardian_reviews(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform Guardian Agent review data."""
        # Add review-specific context
        for metric in metrics:
            metric.tags["analysis_type"] = "code_review"
        return metrics

    def transform_system_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform system performance metrics."""
        # Add system-specific tags
        for metric in metrics:
            metric.tags["metric_category"] = "system"
        return metrics

    def transform_golden_rules(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform Golden Rules violation data."""
        # Add compliance-specific context
        for metric in metrics:
            metric.tags["compliance_type"] = "golden_rules"
        return metrics

    def transform_architectural_violations(
        self,
        metrics: list[UnifiedMetric],
        source: DataSource,
    ) -> list[UnifiedMetric]:
        """Transform architectural validation data."""
        for metric in metrics:
            metric.tags["oracle_component"] = "architectural_validation"
            metric.tags["data_source"] = "comprehensive_scan"

            # Add priority based on severity and metric type
            if metric.metric_type == MetricType.ARCHITECTURAL_VIOLATION:
                severity = metric.tags.get("severity", "low")
                metric.tags["priority"] = (
                    "critical" if severity == "high" else "medium" if severity == "medium" else "low"
                )
            elif metric.metric_type == MetricType.TECHNICAL_DEBT:
                debt_level = metric.tags.get("debt_level", "low")
                metric.tags["priority"] = (
                    "high" if debt_level == "high" else "medium" if debt_level == "medium" else "low"
                )

        return metrics

    def transform_compliance_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform compliance monitoring data."""
        for metric in metrics:
            metric.tags["oracle_component"] = "compliance_monitoring"
            metric.tags["data_source"] = "quick_check"
            metric.tags["monitoring_type"] = "continuous"

            # Add urgency based on compliance score
            if metric.metric_type == MetricType.GOLDEN_RULES_COMPLIANCE:
                score = float(metric.value) if isinstance(metric.value, (int, float)) else 0
                if score < 50:
                    metric.tags["urgency"] = "high"
                elif score < 80:
                    metric.tags["urgency"] = "medium"
                else:
                    metric.tags["urgency"] = "low"

        return metrics

    def transform_user_analytics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich user analytics metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "user_analytics"

            # Add priority based on metric values
            if metric.metric_type == MetricType.USER_BEHAVIOR:
                completion_time = metric.value
                if completion_time > 10:  # More than 10 minutes
                    metric.tags["priority"] = "high"
                    metric.tags["action_required"] = "true"
                elif completion_time > 6:
                    metric.tags["priority"] = "medium"
                else:
                    metric.tags["priority"] = "low"

            elif metric.metric_type == MetricType.USER_RETENTION:
                retention_rate = metric.value
                if retention_rate < 70:
                    metric.tags["health_status"] = "critical"
                elif retention_rate < 80:
                    metric.tags["health_status"] = "warning"
                else:
                    metric.tags["health_status"] = "healthy"

            elif metric.metric_type == MetricType.USER_ENGAGEMENT:
                if "daily_active_users" in metric.tags.get("metric_name", ""):
                    dau_percentage = metric.value
                    if dau_percentage < 60:
                        metric.tags["engagement_level"] = "low"
                    elif dau_percentage < 80:
                        metric.tags["engagement_level"] = "medium"
                    else:
                        metric.tags["engagement_level"] = "high"

        return metrics

    def transform_feature_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich feature usage metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "feature_analytics"

            if metric.metric_type == MetricType.FEATURE_ADOPTION:
                adoption_rate = metric.value,
                operational_cost = metric.metadata.get("operational_cost", 0)
                satisfaction_score = metric.metadata.get("satisfaction_score", 0)

                # Calculate feature health score
                roi_score = metric.metadata.get("roi_score", 0)

                if roi_score > 15:
                    metric.tags["feature_status"] = "high_value"
                elif roi_score > 5:
                    metric.tags["feature_status"] = "moderate_value"
                else:
                    metric.tags["feature_status"] = "low_value"

                # Flag features for review
                if adoption_rate < 10 and operational_cost > 500:
                    metric.tags["review_required"] = "true"
                    metric.tags["reason"] = "low_adoption_high_cost"

                if satisfaction_score < 3.0:
                    metric.tags["user_satisfaction"] = "poor"
                elif satisfaction_score > 4.5:
                    metric.tags["user_satisfaction"] = "excellent"
                else:
                    metric.tags["user_satisfaction"] = "good"

        return metrics

    def transform_business_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich business intelligence metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "business_intelligence"

            if metric.metric_type == MetricType.REVENUE_METRICS:
                if "mrr" in metric.tags.get("metric_name", ""):
                    growth_rate = metric.metadata.get("growth_rate", 0)
                    if growth_rate < 0.05:  # Less than 5% growth
                        metric.tags["growth_status"] = "slow"
                    elif growth_rate > 0.15:  # More than 15% growth
                        metric.tags["growth_status"] = "rapid"
                    else:
                        metric.tags["growth_status"] = "healthy"

            elif metric.metric_type == MetricType.CONVERSION_RATE:
                conversion_rate = metric.value,
                benchmark = metric.metadata.get("benchmark", 0)

                if conversion_rate < benchmark * 0.8:
                    metric.tags["performance"] = "below_benchmark"
                    metric.tags["action_required"] = "true"
                elif conversion_rate > benchmark * 1.2:
                    metric.tags["performance"] = "above_benchmark"
                else:
                    metric.tags["performance"] = "on_target"

            elif metric.metric_type == MetricType.BUSINESS_KPI:
                if "cac" in metric.tags.get("metric_name", ""):
                    ltv_cac_ratio = metric.metadata.get("ltv_cac_ratio", 0)
                    if ltv_cac_ratio < 3:
                        metric.tags["cac_health"] = "concerning"
                    elif ltv_cac_ratio > 5:
                        metric.tags["cac_health"] = "excellent"
                    else:
                        metric.tags["cac_health"] = "healthy"

        return metrics

    def transform_customer_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich customer health metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "customer_intelligence"

            if metric.metric_type == MetricType.CUSTOMER_SATISFACTION:
                if "nps" in metric.tags.get("metric_name", ""):
                    nps_score = metric.value
                    if nps_score < 0:
                        metric.tags["satisfaction_level"] = "poor"
                    elif nps_score < 50:
                        metric.tags["satisfaction_level"] = "fair"
                    elif nps_score < 70:
                        metric.tags["satisfaction_level"] = "good"
                    else:
                        metric.tags["satisfaction_level"] = "excellent"

                elif "error_rate_change" in metric.unit:
                    # Customer health alert
                    error_increase = metric.value
                    if error_increase > 0.3:  # More than 30% increase
                        metric.tags["alert_level"] = "critical"
                        metric.tags["escalate"] = "true"
                    elif error_increase > 0.1:
                        metric.tags["alert_level"] = "warning"
                    else:
                        metric.tags["alert_level"] = "info"

            elif metric.metric_type == MetricType.SUPPORT_METRICS:
                if "first_response_time" in metric.tags.get("metric_name", ""):
                    response_time = metric.value,
                    sla_target = metric.metadata.get("sla_target", 4.0)

                    if response_time > sla_target:
                        metric.tags["sla_status"] = "breach"
                    elif response_time > sla_target * 0.8:
                        metric.tags["sla_status"] = "at_risk"
                    else:
                        metric.tags["sla_status"] = "on_target"

                elif "open_tickets" in metric.tags.get("metric_name", ""):
                    open_count = metric.value,
                    trend = metric.metadata.get("trend", "stable")

                    if open_count > 20 and trend == "increasing":
                        metric.tags["ticket_status"] = "critical_backlog"
                    elif open_count > 10:
                        metric.tags["ticket_status"] = "moderate_backlog"
                    else:
                        metric.tags["ticket_status"] = "manageable"

        return metrics

    # Architect v2.0 Certification Standards Data Collection Methods

    async def _run_certification_audit_async(self, source_name: str) -> list[UnifiedMetric]:
        """Run comprehensive certification audit for all components."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Simulate comprehensive certification audit
            components = [
                {"name": "hive-ai", "type": "package", "certification_score": 72.5},
                {"name": "hive-db", "type": "package", "certification_score": 88.0},
                {"name": "hive-config", "type": "package", "certification_score": 91.5},
                {"name": "guardian-agent", "type": "app", "certification_score": 85.2},
                {"name": "ecosystemiser", "type": "app", "certification_score": 78.8},
            ]

            for component in components:
                # Overall certification score
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.CERTIFICATION_SCORE,
                        source=source_name,
                        timestamp=timestamp,
                        value=component["certification_score"],
                        unit="points",
                        tags={
                            "component": component["name"],
                            "component_type": component["type"],
                            "certification_level": self._get_certification_level(component["certification_score"]),
                            "assessment_type": "comprehensive",
                        },
                        metadata={"max_score": 100, "last_audit": timestamp.isoformat(), "audit_version": "v2.0"},
                    ),
                )

                # Individual assessment criteria scores
                criteria_scores = self._simulate_criteria_scores(component["name"], component["certification_score"])

                for criteria, score in criteria_scores.items():
                    metrics.append(
                        UnifiedMetric(
                            metric_type=self._get_criteria_metric_type(criteria),
                            source=source_name,
                            timestamp=timestamp,
                            value=score,
                            unit="points",
                            tags={
                                "component": component["name"],
                                "component_type": component["type"],
                                "criteria": criteria,
                                "assessment_type": "detailed",
                            },
                            metadata={
                                "max_score": self._get_criteria_max_score(criteria),
                                "weight": self._get_criteria_weight(criteria),
                            },
                        ),
                    )

            logger.info(f"Collected {len(metrics)} certification audit metrics")
        except Exception as e:
            logger.error(f"Failed to run certification audit: {e}")

        return metrics

    def _get_certification_level(self, score: float) -> str:
        """Determine certification level based on score."""
        if score >= 90:
            return "Senior Hive Architect"
        elif score >= 80:
            return "Certified Hive Architect"
        elif score >= 70:
            return "Associate Hive Architect"
        else:
            return "Non-Certified"

    def _simulate_criteria_scores(self, component_name: str, overall_score: float) -> dict[str, float]:
        """Simulate individual criteria scores based on component characteristics."""
        base_scores = {
            "technical_excellence": 35.0,
            "operational_readiness": 25.0,
            "platform_integration": 18.0,
            "innovation": 8.0,
        }

        # Adjust scores based on component-specific knowledge
        if component_name == "hive-ai":
            # Known issues with Golden Rules compliance
            base_scores["technical_excellence"] = 28.0  # Lower due to violations
            base_scores["platform_integration"] = 15.0  # Missing test files
        elif component_name == "hive-config":
            # Well-designed core package
            base_scores["technical_excellence"] = 38.0
            base_scores["platform_integration"] = 19.0
        elif component_name == "guardian-agent":
            # Good innovation but some operational gaps
            base_scores["innovation"] = 9.5
            base_scores["operational_readiness"] = 22.0

        # Scale to match overall score
        total_base = sum(base_scores.values()),
        scale_factor = overall_score / total_base

        return {k: v * scale_factor for k, v in base_scores.items()}

    def _get_criteria_metric_type(self, criteria: str) -> MetricType:
        """Map criteria to appropriate metric type."""
        mapping = {
            "technical_excellence": MetricType.CODE_QUALITY_SCORE,
            "operational_readiness": MetricType.DEPLOYMENT_READINESS,
            "platform_integration": MetricType.PLATFORM_INTEGRATION,
            "innovation": MetricType.INNOVATION_SCORE,
        }
        return mapping.get(criteria, MetricType.CERTIFICATION_SCORE)

    def _get_criteria_max_score(self, criteria: str) -> int:
        """Get maximum possible score for each criteria."""
        max_scores = {
            "technical_excellence": 40,
            "operational_readiness": 30,
            "platform_integration": 20,
            "innovation": 10,
        }
        return max_scores.get(criteria, 100)

    def _get_criteria_weight(self, criteria: str) -> float:
        """Get weight of each criteria in overall score."""
        weights = {
            "technical_excellence": 0.40,
            "operational_readiness": 0.30,
            "platform_integration": 0.20,
            "innovation": 0.10,
        }
        return weights.get(criteria, 0.25)

    async def _collect_code_quality_metrics_async(self, source_name: str) -> list[UnifiedMetric]:
        """Collect code quality and security scanning metrics."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Simulate code quality analysis for key components
            quality_data = [
                {
                    "component": "hive-ai",
                    "quality_score": 72.5,
                    "security_score": 85.0,
                    "maintainability": 68.0,
                    "test_coverage": 65.2,
                    "type_coverage": 78.5,
                    "complexity_score": 82.0,
                },
                {
                    "component": "hive-db",
                    "quality_score": 88.5,
                    "security_score": 92.0,
                    "maintainability": 85.0,
                    "test_coverage": 91.8,
                    "type_coverage": 95.2,
                    "complexity_score": 89.5,
                },
                {
                    "component": "guardian-agent",
                    "quality_score": 85.2,
                    "security_score": 88.5,
                    "maintainability": 82.0,
                    "test_coverage": 78.9,
                    "type_coverage": 92.1,
                    "complexity_score": 86.8,
                },
            ]

            for data in quality_data:
                # Overall code quality score
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.CODE_QUALITY_SCORE,
                        source=source_name,
                        timestamp=timestamp,
                        value=data["quality_score"],
                        unit="score",
                        tags={
                            "component": data["component"],
                            "scan_type": "comprehensive",
                            "quality_level": self._get_quality_level(data["quality_score"]),
                        },
                        metadata={
                            "security_score": data["security_score"],
                            "maintainability": data["maintainability"],
                            "complexity_score": data["complexity_score"],
                        },
                    ),
                )

                # Test coverage metrics
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.TESTING_COVERAGE,
                        source=source_name,
                        timestamp=timestamp,
                        value=data["test_coverage"],
                        unit="percent",
                        tags={
                            "component": data["component"],
                            "coverage_type": "line_coverage",
                            "target_met": "true" if data["test_coverage"] >= 90 else "false",
                        },
                        metadata={
                            "type_coverage": data["type_coverage"],
                            "target_coverage": 90.0,
                            "certification_requirement": True,
                        },
                    ),
                )

            logger.info(f"Collected {len(metrics)} code quality metrics")
        except Exception as e:
            logger.error(f"Failed to collect code quality metrics: {e}")

        return metrics

    def _get_quality_level(self, score: float) -> str:
        """Determine quality level based on score."""
        if score >= 90:
            return "excellent"
        elif score >= 80:
            return "good"
        elif score >= 70:
            return "acceptable"
        else:
            return "needs_improvement"

    async def _collect_deployment_metrics_async(self, source_name: str) -> list[UnifiedMetric]:
        """Collect deployment readiness and CI/CD pipeline health metrics."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Simulate deployment readiness assessment
            deployment_data = [
                {
                    "component": "hive-ai",
                    "deployment_score": 68.5,
                    "docker_ready": True,
                    "k8s_ready": False,
                    "cicd_configured": True,
                    "monitoring_configured": False,
                    "security_scans": True,
                    "performance_tests": False,
                },
                {
                    "component": "guardian-agent",
                    "deployment_score": 85.0,
                    "docker_ready": True,
                    "k8s_ready": True,
                    "cicd_configured": True,
                    "monitoring_configured": True,
                    "security_scans": True,
                    "performance_tests": True,
                },
                {
                    "component": "ecosystemiser",
                    "deployment_score": 78.2,
                    "docker_ready": True,
                    "k8s_ready": True,
                    "cicd_configured": False,
                    "monitoring_configured": True,
                    "security_scans": True,
                    "performance_tests": False,
                },
            ]

            for data in deployment_data:
                # Overall deployment readiness
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.DEPLOYMENT_READINESS,
                        source=source_name,
                        timestamp=timestamp,
                        value=data["deployment_score"],
                        unit="score",
                        tags={
                            "component": data["component"],
                            "readiness_level": self._get_readiness_level(data["deployment_score"]),
                            "production_ready": "true" if data["deployment_score"] >= 80 else "false",
                        },
                        metadata={
                            "docker_ready": data["docker_ready"],
                            "k8s_ready": data["k8s_ready"],
                            "cicd_configured": data["cicd_configured"],
                            "monitoring_configured": data["monitoring_configured"],
                            "security_scans": data["security_scans"],
                            "performance_tests": data["performance_tests"],
                        },
                    ),
                )

                # Monitoring configuration score
                monitoring_score = 90.0 if data["monitoring_configured"] else 25.0
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.MONITORING_SCORE,
                        source=source_name,
                        timestamp=timestamp,
                        value=monitoring_score,
                        unit="score",
                        tags={
                            "component": data["component"],
                            "monitoring_type": "comprehensive" if data["monitoring_configured"] else "basic",
                            "certification_ready": "true" if monitoring_score >= 80 else "false",
                        },
                        metadata={
                            "prometheus_metrics": data["monitoring_configured"],
                            "grafana_dashboard": data["monitoring_configured"],
                            "alerting_rules": data["monitoring_configured"],
                        },
                    ),
                )

            logger.info(f"Collected {len(metrics)} deployment readiness metrics")
        except Exception as e:
            logger.error(f"Failed to collect deployment metrics: {e}")

        return metrics

    def _get_readiness_level(self, score: float) -> str:
        """Determine deployment readiness level."""
        if score >= 90:
            return "production_ready"
        elif score >= 80:
            return "staging_ready"
        elif score >= 70:
            return "development_ready"
        else:
            return "not_ready"

    async def _collect_toolkit_metrics_async(self, source_name: str) -> list[UnifiedMetric]:
        """Collect toolkit utilization and platform integration metrics."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Simulate toolkit utilization analysis
            toolkit_data = [
                {
                    "component": "guardian-agent",
                    "toolkit_score": 92.5,
                    "uses_hive_config": True,
                    "uses_hive_logging": True,
                    "uses_hive_db": False,
                    "uses_hive_ai": True,
                    "follows_patterns": True,
                    "configuration_standard": True,
                },
                {
                    "component": "ecosystemiser",
                    "toolkit_score": 75.0,
                    "uses_hive_config": True,
                    "uses_hive_logging": False,
                    "uses_hive_db": True,
                    "uses_hive_ai": True,
                    "follows_patterns": False,
                    "configuration_standard": True,
                },
                {
                    "component": "hive-ai",
                    "toolkit_score": 68.5,
                    "uses_hive_config": True,
                    "uses_hive_logging": True,
                    "uses_hive_db": False,
                    "uses_hive_ai": False,  # It IS hive-ai
                    "follows_patterns": False,
                    "configuration_standard": False,
                },
            ]

            for data in toolkit_data:
                # Overall toolkit utilization
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.TOOLKIT_UTILIZATION,
                        source=source_name,
                        timestamp=timestamp,
                        value=data["toolkit_score"],
                        unit="score",
                        tags={
                            "component": data["component"],
                            "utilization_level": self._get_utilization_level(data["toolkit_score"]),
                            "certification_compliant": "true" if data["toolkit_score"] >= 80 else "false",
                        },
                        metadata={
                            "uses_hive_config": data["uses_hive_config"],
                            "uses_hive_logging": data["uses_hive_logging"],
                            "uses_hive_db": data["uses_hive_db"],
                            "follows_patterns": data["follows_patterns"],
                            "configuration_standard": data["configuration_standard"],
                        },
                    ),
                )

                # Platform integration score
                integration_score = self._calculate_integration_score(data)
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.PLATFORM_INTEGRATION,
                        source=source_name,
                        timestamp=timestamp,
                        value=integration_score,
                        unit="score",
                        tags={
                            "component": data["component"],
                            "integration_level": self._get_integration_level(integration_score),
                            "ecosystem_ready": "true" if integration_score >= 85 else "false",
                        },
                        metadata={
                            "package_count": sum(
                                [
                                    data["uses_hive_config"],
                                    data["uses_hive_logging"],
                                    data["uses_hive_db"],
                                    data["uses_hive_ai"],
                                ],
                            ),
                            "pattern_compliance": data["follows_patterns"],
                        },
                    ),
                )

            logger.info(f"Collected {len(metrics)} toolkit utilization metrics")
        except Exception as e:
            logger.error(f"Failed to collect toolkit metrics: {e}")

        return metrics

    def _get_utilization_level(self, score: float) -> str:
        """Determine toolkit utilization level."""
        if score >= 90:
            return "exemplary"
        elif score >= 80:
            return "proficient"
        elif score >= 70:
            return "adequate"
        else:
            return "insufficient"

    def _get_integration_level(self, score: float) -> str:
        """Determine platform integration level."""
        if score >= 90:
            return "fully_integrated"
        elif score >= 80:
            return "well_integrated"
        elif score >= 70:
            return "partially_integrated"
        else:
            return "poorly_integrated"

    def _calculate_integration_score(self, data: dict[str, Any]) -> float:
        """Calculate platform integration score based on usage patterns."""
        base_score = 60.0

        # Package usage bonuses
        if data["uses_hive_config"]:
            base_score += 10.0
        if data["uses_hive_logging"]:
            base_score += 8.0
        if data["uses_hive_db"]:
            base_score += 7.0
        if data["uses_hive_ai"]:
            base_score += 5.0

        # Pattern compliance bonus
        if data["follows_patterns"]:
            base_score += 8.0

        # Configuration standard bonus
        if data["configuration_standard"]:
            base_score += 2.0

        return min(base_score, 100.0)

    # Transform functions for certification metrics

    def transform_certification_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich certification audit metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "certification_audit"

            if metric.metric_type == MetricType.CERTIFICATION_SCORE:
                score = metric.value
                metric.tags.get("component", "unknown")

                # Add urgency tags based on score
                if score < 70:
                    metric.tags["urgency"] = "high"
                    metric.tags["action_required"] = "immediate"
                elif score < 80:
                    metric.tags["urgency"] = "medium"
                    metric.tags["action_required"] = "soon"
                else:
                    metric.tags["urgency"] = "low"
                    metric.tags["action_required"] = "maintenance"

                # Add improvement potential
                improvement_potential = 100 - score
                metric.metadata["improvement_potential"] = improvement_potential
                metric.metadata["certification_gap"] = self._calculate_certification_gap(score)

        return metrics

    def _calculate_certification_gap(self, score: float) -> str:
        """Calculate what's needed to reach next certification level."""
        if score < 70:
            return f"Need {70 - score:.1f} points for Associate level"
        elif score < 80:
            return f"Need {80 - score:.1f} points for Certified level"
        elif score < 90:
            return f"Need {90 - score:.1f} points for Senior level"
        else:
            return "Already at Senior level"

    def transform_code_quality_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich code quality metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "code_quality_scan"

            if metric.metric_type == MetricType.TESTING_COVERAGE:
                coverage = metric.value,
                target = metric.metadata.get("target_coverage", 90.0)

                if coverage < target:
                    metric.tags["coverage_gap"] = f"{target - coverage:.1f}%"
                    metric.tags["priority"] = "high" if coverage < 70 else "medium"

        return metrics

    def transform_deployment_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich deployment readiness metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "deployment_readiness"

            if metric.metric_type == MetricType.DEPLOYMENT_READINESS:
                score = metric.value
                if score < 80:
                    metric.tags["deployment_blocked"] = "true"
                    metric.tags["action_required"] = "before_production"

        return metrics

    def transform_toolkit_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich toolkit utilization metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "toolkit_compliance"

            if metric.metric_type == MetricType.TOOLKIT_UTILIZATION:
                score = metric.value
                if score < 80:
                    metric.tags["modernization_needed"] = "true"
                    metric.tags["toolkit_gap"] = "significant"

        return metrics

    # Genesis Mandate - Design Intent & Prophecy Collection Methods

    async def _collect_design_documents_async(self, source_name: str, docs_path: Path) -> list[UnifiedMetric]:
        """Collect and process design documents for intent extraction."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            if not docs_path.exists():
                logger.warning(f"Design documents path does not exist: {docs_path}")
                return metrics

            # Scan for design documents (markdown, text files)
            design_files = []
            for pattern in ["*.md", "*.txt", "*.rst"]:
                design_files.extend(docs_path.glob(pattern))

            logger.info(f"Found {len(design_files)} design documents")

            for doc_file in design_files:
                try:
                    # Read document content
                    with open(doc_file, encoding="utf-8") as f:
                        content = f.read()

                    # Extract basic metadata
                    word_count = len(content.split()),
                    line_count = len(content.splitlines())

                    # Simple complexity assessment
                    complexity_indicators = [
                        "api",
                        "endpoint",
                        "database",
                        "cache",
                        "queue",
                        "service",
                        "authentication",
                        "authorization",
                        "performance",
                        "scale",
                        "integration",
                        "third-party",
                        "real-time",
                        "async",
                    ]
                    complexity_score = sum(
                        1 for indicator in complexity_indicators if indicator.lower() in content.lower()
                    )

                    # Design intent metric
                    metrics.append(
                        UnifiedMetric(
                            metric_type=MetricType.DESIGN_INTENT,
                            source=source_name,
                            timestamp=timestamp,
                            value=1.0,  # Document presence indicator,
                            unit="document",
                            tags={
                                "document_name": doc_file.stem,
                                "document_type": doc_file.suffix[1:],  # Remove dot,
                                "complexity_level": self._categorize_complexity(complexity_score),
                                "oracle_component": "design_ingestion",
                            },
                            metadata={
                                "file_path": str(doc_file),
                                "word_count": word_count,
                                "line_count": line_count,
                                "complexity_score": complexity_score,
                                "last_modified": doc_file.stat().st_mtime,
                                "content_hash": hash(content) % 1000000,  # Simple content hash
                            },
                        ),
                    )

                    # Intent extraction complexity metric
                    metrics.append(
                        UnifiedMetric(
                            metric_type=MetricType.INTENT_EXTRACTION,
                            source=source_name,
                            timestamp=timestamp,
                            value=complexity_score,
                            unit="complexity_points",
                            tags={
                                "document_name": doc_file.stem,
                                "extraction_quality": self._assess_extraction_quality(content),
                                "oracle_component": "intent_extraction",
                            },
                            metadata={
                                "indicators_found": complexity_score,
                                "estimated_analysis_time": f"{complexity_score * 2} minutes",
                            },
                        ),
                    )

                    # Design complexity metric
                    metrics.append(
                        UnifiedMetric(
                            metric_type=MetricType.DESIGN_COMPLEXITY,
                            source=source_name,
                            timestamp=timestamp,
                            value=min(complexity_score / 5.0, 1.0),  # Normalize to 0-1,
                            unit="complexity_ratio",
                            tags={
                                "document_name": doc_file.stem,
                                "complexity_category": self._categorize_complexity(complexity_score),
                                "oracle_component": "complexity_analysis",
                            },
                            metadata={
                                "raw_complexity": complexity_score,
                                "normalized_complexity": min(complexity_score / 5.0, 1.0),
                                "complexity_factors": complexity_indicators[:complexity_score],
                            },
                        ),
                    )

                except Exception as e:
                    logger.error(f"Failed to process design document {doc_file}: {e}")
                    continue

            logger.info(f"Processed {len(design_files)} design documents, generated {len(metrics)} metrics")

        except Exception as e:
            logger.error(f"Failed to collect design documents: {e}")

        return metrics

    def _categorize_complexity(self, score: int) -> str:
        """Categorize design complexity based on score."""
        if score >= 10:
            return "very_high"
        elif score >= 7:
            return "high"
        elif score >= 4:
            return "medium"
        elif score >= 2:
            return "low"
        else:
            return "very_low"

    def _assess_extraction_quality(self, content: str) -> str:
        """Assess how well we can extract intent from the document."""
        quality_indicators = [
            ("requirements", 2),
            ("goals", 2),
            ("objectives", 2),
            ("architecture", 3),
            ("design", 2),
            ("api", 2),
            ("database", 2),
            ("performance", 2),
            ("security", 2),
            ("users", 1),
            ("business", 2),
            ("value", 1),
        ]

        quality_score = sum(weight for indicator, weight in quality_indicators if indicator.lower() in content.lower())

        if quality_score >= 15:
            return "excellent"
        elif quality_score >= 10:
            return "good"
        elif quality_score >= 5:
            return "fair"
        else:
            return "poor"

    async def _collect_prophecy_metrics_async(self, source_name: str) -> list[UnifiedMetric]:
        """Collect architectural prophecy generation and tracking metrics."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Simulate prophecy generation metrics
            # In reality, this would integrate with the ProphecyEngine

            prophecy_scenarios = [
                {
                    "project": "user-dashboard-redesign",
                    "prophecy_type": "performance_bottleneck",
                    "severity": "critical",
                    "confidence": 0.85,
                    "time_to_manifestation": 30,  # days
                },
                {
                    "project": "payment-service-v2",
                    "prophecy_type": "cost_overrun",
                    "severity": "significant",
                    "confidence": 0.75,
                    "time_to_manifestation": 90,
                },
                {
                    "project": "mobile-app-backend",
                    "prophecy_type": "scalability_issue",
                    "severity": "moderate",
                    "confidence": 0.65,
                    "time_to_manifestation": 180,
                },
            ]

            for scenario in prophecy_scenarios:
                # Prophecy tracking metric
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.ARCHITECTURAL_PROPHECY,
                        source=source_name,
                        timestamp=timestamp,
                        value=scenario["confidence"],
                        unit="confidence_score",
                        tags={
                            "project_name": scenario["project"],
                            "prophecy_type": scenario["prophecy_type"],
                            "severity": scenario["severity"],
                            "oracle_component": "prophecy_generation",
                        },
                        metadata={
                            "time_to_manifestation_days": scenario["time_to_manifestation"],
                            "prophecy_id": f"prophecy_{scenario['project']}_{scenario['prophecy_type']}",
                            "generated_by": "prophecy_engine_v1.0",
                        },
                    ),
                )

            logger.info(f"Generated {len(metrics)} prophecy tracking metrics")

        except Exception as e:
            logger.error(f"Failed to collect prophecy metrics: {e}")

        return metrics

    async def _collect_prophecy_accuracy_async(self, source_name: str) -> list[UnifiedMetric]:
        """Collect prophecy accuracy validation metrics (retrospective analysis)."""
        metrics = [],
        timestamp = datetime.utcnow()

        try:
            # Simulate prophecy accuracy validation
            # In reality, this would compare past prophecies with actual outcomes

            validation_cases = [
                {
                    "prophecy_id": "prophecy_analytics_dashboard_performance",
                    "predicted_outcome": "database_bottleneck",
                    "actual_outcome": "database_bottleneck",
                    "accuracy": 1.0,  # Perfect prediction,
                    "days_to_manifestation": 25,  # Predicted 30, actual 25,
                    "business_impact": "high",
                },
                {
                    "prophecy_id": "prophecy_notification_service_cost",
                    "predicted_outcome": "cost_overrun_200%",
                    "actual_outcome": "cost_overrun_150%",
                    "accuracy": 0.8,  # Close prediction
                    "days_to_manifestation": 65,  # Predicted 60, actual 65,
                    "business_impact": "medium",
                },
                {
                    "prophecy_id": "prophecy_auth_service_security",
                    "predicted_outcome": "security_vulnerability",
                    "actual_outcome": "no_issues_found",
                    "accuracy": 0.0,  # False positive
                    "days_to_manifestation": None,  # Never manifested,
                    "business_impact": "low",
                },
            ]

            for case in validation_cases:
                # Prophecy accuracy metric
                metrics.append(
                    UnifiedMetric(
                        metric_type=MetricType.PROPHECY_ACCURACY,
                        source=source_name,
                        timestamp=timestamp,
                        value=case["accuracy"],
                        unit="accuracy_score",
                        tags={
                            "prophecy_id": case["prophecy_id"],
                            "predicted_outcome": case["predicted_outcome"],
                            "actual_outcome": case["actual_outcome"],
                            "business_impact": case["business_impact"],
                            "oracle_component": "prophecy_validation",
                        },
                        metadata={
                            "days_to_manifestation": case["days_to_manifestation"],
                            "validation_date": timestamp.isoformat(),
                            "learning_value": "high" if case["accuracy"] != 0.5 else "medium",
                        },
                    ),
                )

            # Calculate overall prophecy engine accuracy
            total_accuracy = sum(case["accuracy"] for case in validation_cases),
            avg_accuracy = total_accuracy / len(validation_cases) if validation_cases else 0.0

            # Overall accuracy metric
            metrics.append(
                UnifiedMetric(
                    metric_type=MetricType.PROPHECY_ACCURACY,
                    source=source_name,
                    timestamp=timestamp,
                    value=avg_accuracy,
                    unit="overall_accuracy",
                    tags={"metric_type": "aggregate", "oracle_component": "prophecy_validation_summary"},
                    metadata={
                        "total_prophecies_validated": len(validation_cases),
                        "perfect_predictions": len([c for c in validation_cases if c["accuracy"] == 1.0]),
                        "false_positives": len([c for c in validation_cases if c["accuracy"] == 0.0]),
                        "validation_period": "last_30_days",
                    },
                ),
            )

            logger.info(f"Validated {len(validation_cases)} prophecies, overall accuracy: {avg_accuracy:.1%}")

        except Exception as e:
            logger.error(f"Failed to collect prophecy accuracy metrics: {e}")

        return metrics

    def transform_design_intent_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich design intent metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "design_intelligence"

            if metric.metric_type == MetricType.DESIGN_COMPLEXITY:
                complexity = metric.value
                if complexity > 0.8:
                    metric.tags["prophecy_priority"] = "high"
                    metric.tags["analysis_urgency"] = "immediate"
                elif complexity > 0.6:
                    metric.tags["prophecy_priority"] = "medium"
                    metric.tags["analysis_urgency"] = "soon"
                else:
                    metric.tags["prophecy_priority"] = "low"
                    metric.tags["analysis_urgency"] = "routine"

        return metrics

    def transform_prophecy_metrics(self, metrics: list[UnifiedMetric], source: DataSource) -> list[UnifiedMetric]:
        """Transform and enrich prophecy metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "architectural_prophecy"

            if metric.metric_type == MetricType.ARCHITECTURAL_PROPHECY:
                confidence = metric.value,
                severity = metric.tags.get("severity", "moderate")

                # Add urgency based on confidence and severity
                if confidence > 0.8 and severity in ["critical", "catastrophic"]:
                    metric.tags["action_urgency"] = "immediate"
                elif confidence > 0.7 and severity in ["critical", "significant"]:
                    metric.tags["action_urgency"] = "high"
                elif confidence > 0.6:
                    metric.tags["action_urgency"] = "medium"
                else:
                    metric.tags["action_urgency"] = "low"

                # Add Oracle recommendations
                metric.metadata["oracle_recommendation"] = self._generate_prophecy_recommendation(
                    metric.tags.get("prophecy_type", "unknown"),
                    confidence,
                    severity,
                )

        return metrics

    def transform_prophecy_accuracy_metrics(
        self,
        metrics: list[UnifiedMetric],
        source: DataSource,
    ) -> list[UnifiedMetric]:
        """Transform and enrich prophecy accuracy metrics."""
        for metric in metrics:
            metric.tags["oracle_component"] = "prophecy_learning"

            if metric.metric_type == MetricType.PROPHECY_ACCURACY:
                accuracy = metric.value

                # Categorize accuracy for learning
                if accuracy >= 0.9:
                    metric.tags["accuracy_category"] = "excellent"
                elif accuracy >= 0.7:
                    metric.tags["accuracy_category"] = "good"
                elif accuracy >= 0.5:
                    metric.tags["accuracy_category"] = "fair"
                elif accuracy > 0.0:
                    metric.tags["accuracy_category"] = "poor"
                else:
                    metric.tags["accuracy_category"] = "false_positive"

                # Add learning recommendations
                metric.metadata["learning_action"] = self._generate_learning_action(accuracy)

        return metrics

    def _generate_prophecy_recommendation(self, prophecy_type: str, confidence: float, severity: str) -> str:
        """Generate Oracle recommendation based on prophecy characteristics."""
        if prophecy_type == "performance_bottleneck":
            return "Consider implementing caching layer and database optimization early"
        elif prophecy_type == "cost_overrun":
            return "Implement cost monitoring and resource optimization from day one"
        elif prophecy_type == "scalability_issue":
            return "Design for horizontal scaling and implement load testing"
        elif prophecy_type == "compliance_violation":
            return "Ensure Golden Rules compliance before first commit"
        elif prophecy_type == "security_vulnerability":
            return "Implement security best practices and regular audits"
        else:
            return f"Monitor {prophecy_type} closely and implement preventive measures"

    def _generate_learning_action(self, accuracy: float) -> str:
        """Generate learning action based on prophecy accuracy."""
        if accuracy >= 0.9:
            return "Reinforce successful prediction patterns"
        elif accuracy >= 0.7:
            return "Minor adjustments to prediction model"
        elif accuracy >= 0.5:
            return "Moderate refinement of prediction algorithms"
        elif accuracy > 0.0:
            return "Significant model improvements needed"
        else:
            return "Investigate false positive causes and adjust thresholds"

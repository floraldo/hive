"""
Cross-Package Pattern Analyzer

The Oracle's advanced intelligence for identifying opportunities to apply
the best patterns from one package to solve problems in another, achieving
true architectural integration and hyper-optimization.

This represents the Oracle's evolution into a system-wide architectural
intelligence that understands not just individual components, but the
synergies and optimization opportunities between them.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class IntegrationType(Enum):
    """Types of cross-package integration opportunities."""

    CACHING = "caching"  # Use hive-cache for performance
    ERROR_HANDLING = "error_handling"  # Use hive-errors for standardization
    ASYNC_PATTERNS = "async_patterns"  # Use hive-async for resilience
    LOGGING = "logging"  # Use hive-logging for observability
    DATABASE = "database"  # Use hive-db for data management
    CONFIGURATION = "configuration"  # Use hive-config for settings
    DEPLOYMENT = "deployment"  # Use hive-deployment for ops
    AI_INTEGRATION = "ai_integration"  # Use hive-ai for intelligence
    BUS_MESSAGING = "bus_messaging"  # Use hive-bus for communication


class OptimizationImpact(Enum):
    """Impact level of optimization opportunities."""

    TRANSFORMATIVE = "transformative"  # Major architectural improvement
    HIGH = "high"  # Significant improvement
    MEDIUM = "medium"  # Moderate improvement
    LOW = "low"  # Minor improvement
    INFORMATIONAL = "informational"  # Good to know


@dataclass
class IntegrationPattern:
    """A reusable integration pattern between packages."""

    name: str
    description: str
    source_package: str
    target_use_case: str

    # Pattern detection
    detection_pattern: str  # Regex or AST pattern
    context_indicators: list[str] = field(default_factory=list)

    # Integration details
    required_import: str = ""
    replacement_code: str = ""
    configuration_needed: bool = False

    # Benefits
    performance_improvement: str = ""
    reliability_improvement: str = ""
    maintainability_improvement: str = ""

    # Implementation
    estimated_effort: str = "30 minutes"
    complexity_level: str = "low"
    breaking_changes: bool = False

    # Success metrics
    success_rate: float = 0.9
    adoption_count: int = 0

    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OptimizationOpportunity:
    """A specific optimization opportunity discovered through cross-package analysis."""

    # Identification
    file_path: str
    line_number: int | None = None
    function_name: str | None = None
    class_name: str | None = None

    # Opportunity details
    integration_type: IntegrationType
    current_pattern: str
    suggested_pattern: str

    # Impact assessment
    impact_level: OptimizationImpact
    performance_gain: str | None = None
    reliability_gain: str | None = None
    maintainability_gain: str | None = None

    # Implementation guidance
    required_packages: list[str] = field(default_factory=list)
    implementation_steps: list[str] = field(default_factory=list)
    code_example: str = ""

    # Oracle intelligence
    confidence: float = 0.8
    similar_implementations: int = 0
    success_probability: float = 0.85

    # Business value
    certification_score_impact: float = 0.0
    estimated_effort: str = "30 minutes"
    business_value: str = ""

    # Context
    component_affected: str = ""
    architectural_principle: str = ""
    documentation_reference: str = ""

    discovered_at: datetime = field(default_factory=datetime.utcnow)


class CrossPackageAnalyzer:
    """
    Advanced Cross-Package Pattern Analysis Engine

    Identifies opportunities to leverage the best patterns from the Hive
    ecosystem to optimize and harden individual components, achieving
    true architectural integration.
    """

    def __init__(self):
        self.integration_patterns = self._initialize_integration_patterns()
        self.package_capabilities = self._map_package_capabilities()

        logger.info(f"Cross-Package Analyzer initialized with {len(self.integration_patterns)} patterns")

    def _initialize_integration_patterns(self) -> list[IntegrationPattern]:
        """Initialize the comprehensive library of integration patterns."""

        patterns = [
            # Caching Integration Patterns,
            IntegrationPattern(
                name="API Response Caching",
                description="Replace direct API calls with cached responses using hive-cache",
                source_package="hive-cache",
                target_use_case="HTTP API calls without caching",
                detection_pattern=r"requests\.(get|post|put|delete)",
                context_indicators=["requests", "http", "api", "fetch"],
                required_import="from hive_cache import ClaudeAPICache",
                replacement_code=""",
# Before: Direct API call,
response = requests.get(url, headers=headers)

# After: Cached API call,
cache = ClaudeAPICache()
response = await cache.get_or_fetch_async(
    key=f"api:{url}",
    fetch_func=lambda: requests.get(url, headers=headers),
    ttl=300  # 5 minutes
)
""",
                performance_improvement="50-90% faster for repeated requests",
                reliability_improvement="Resilience against API failures and rate limits",
                maintainability_improvement="Centralized cache management and invalidation",
                estimated_effort="30-45 minutes",
                success_rate=0.95,
            ),
            IntegrationPattern(
                name="Model Response Caching",
                description="Cache AI model responses to reduce costs and improve performance",
                source_package="hive-cache",
                target_use_case="Direct AI model API calls",
                detection_pattern=r"openai\.chat\.completions\.create|anthropic\.messages\.create",
                context_indicators=["openai", "anthropic", "model", "llm", "chat"],
                required_import="from hive_cache import ModelResponseCache",
                replacement_code=""",
# Before: Direct model call,
response = client.chat.completions.create(
    model="gpt-4",
    messages=messages
)

# After: Cached model call,
cache = ModelResponseCache()
response = await cache.get_or_generate_async(
    messages=messages,
    model="gpt-4",
    ttl=3600  # 1 hour for stable prompts
)
""",
                performance_improvement="Instant response for repeated prompts",
                reliability_improvement="Fallback responses during API outages",
                maintainability_improvement="Cost tracking and usage analytics",
                estimated_effort="45-60 minutes",
                success_rate=0.92,
            ),
            # Error Handling Integration Patterns,
            IntegrationPattern(
                name="Structured Exception Handling",
                description="Replace generic exceptions with structured hive-errors types",
                source_package="hive-errors",
                target_use_case="Generic exception handling",
                detection_pattern=r"except\s+Exception|raise\s+Exception",
                context_indicators=["except", "raise", "error", "exception"],
                required_import="from hive_errors import ValidationError, ConnectionError, ProcessingError",
                replacement_code=""",
# Before: Generic exception,
try:
    result = process_data(data)
except Exception as e:
    logger.error(f"Processing failed: {e}")
    raise

# After: Structured exception,
try:
    result = process_data(data)
except ValidationError as e:
    logger.error(f"Data validation failed: {e}")
    raise,
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
    raise ProcessingError("Unable to process due to connection issues") from e,
""",
                reliability_improvement="Better error categorization and handling",
                maintainability_improvement="Structured error information for monitoring",
                estimated_effort="20-30 minutes",
                success_rate=0.88,
            ),
            # Async Patterns Integration,
            IntegrationPattern(
                name="Robust Retry Logic",
                description="Replace manual retry with hive-async decorators",
                source_package="hive-async",
                target_use_case="Manual retry loops with time.sleep",
                detection_pattern=r"time\.sleep.*retry|for.*attempt.*range",
                context_indicators=["time.sleep", "retry", "attempt", "backoff"],
                required_import="from hive_async import async_retry, ExponentialBackoff",
                replacement_code=""",
# Before: Manual retry logic,
for attempt in range(3):
    try:
        result = call_external_service()
        break,
    except Exception as e:
        if attempt == 2:
            raise,
        time.sleep(2 ** attempt)

# After: Robust retry decorator,
@async_retry(
    max_attempts=3,
    backoff=ExponentialBackoff(base=2.0),
    exceptions=(ConnectionError, TimeoutError)
)
async def call_external_service_with_retry():
    return await call_external_service()
""",
                reliability_improvement="Configurable backoff strategies and exception handling",
                maintainability_improvement="Declarative retry configuration",
                estimated_effort="45 minutes",
                success_rate=0.91,
            ),
            # Logging Integration Patterns,
            IntegrationPattern(
                name="Standardized Logging",
                description="Replace manual logging setup with hive-logging",
                source_package="hive-logging",
                target_use_case="Manual logging.getLogger() usage",
                detection_pattern=r"logging\.getLogger|logger\s*=\s*logging",
                context_indicators=["logging.getLogger", "logging.basicConfig"],
                required_import="from hive_logging import get_logger",
                replacement_code=""",
# Before: Manual logging setup,
import logging,
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# After: Standardized logging,
from hive_logging import get_logger,
logger = get_logger(__name__)  # Automatic configuration,
""",
                maintainability_improvement="Consistent logging format and configuration",
                estimated_effort="15 minutes",
                success_rate=0.98,
            ),
            # Database Integration Patterns,
            IntegrationPattern(
                name="Connection Pool Management",
                description="Replace direct SQLite connections with hive-db connection management",
                source_package="hive-db",
                target_use_case="Direct sqlite3.connect() usage",
                detection_pattern=r"sqlite3\.connect",
                context_indicators=["sqlite3", "database", "connection", "cursor"],
                required_import="from hive_db import get_async_session",
                replacement_code=""",
# Before: Direct connection,
import sqlite3,
conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM table")
results = cursor.fetchall()
conn.close()

# After: Managed connection,
from hive_db import get_async_session,
async with get_async_session() as session:
    result = await session.execute("SELECT * FROM table")
    results = await result.fetchall()
    # Automatic connection management and cleanup,
""",
                reliability_improvement="Connection pooling and automatic cleanup",
                maintainability_improvement="Transaction management and error handling",
                estimated_effort="1-2 hours",
                success_rate=0.85,
            ),
            # Configuration Integration Patterns,
            IntegrationPattern(
                name="Centralized Configuration with DI",
                description="Replace hardcoded values with dependency-injected configuration",
                source_package="hive-config",
                target_use_case="Hardcoded configuration values",
                detection_pattern=r"['\"][a-zA-Z0-9._-]+['\"].*=.*['\"][^'\"]*['\"]",
                context_indicators=["config", "settings", "env", "parameter"],
                required_import="from hive_config import HiveConfig, create_config_from_sources",
                replacement_code=""",
# Before: Hardcoded values,
API_KEY = "sk-1234567890",
MAX_RETRIES = 3,
TIMEOUT = 30

# After: Dependency injection pattern (RECOMMENDED),
from hive_config import HiveConfig, create_config_from_sources

class MyService:
    def __init__(self, config: HiveConfig | None = None):
        # Dependency injection with sensible default
        self._config = config or create_config_from_sources()

        # Extract configuration values
        self.api_key = self._config.api_key
        self.max_retries = self._config.max_retries
        self.timeout = self._config.timeout_seconds

# Usage in production:
config = create_config_from_sources()
service = MyService(config=config)

# Usage in tests:
test_config = HiveConfig(api_key="test-key", max_retries=1)
service = MyService(config=test_config)
""",
                maintainability_improvement="Environment-specific configuration with explicit dependencies, testable, thread-safe",
                estimated_effort="30-45 minutes",
                success_rate=0.92,
            ),
            # AI Integration Patterns,
            IntegrationPattern(
                name="Model Pool Optimization",
                description="Route AI model calls through hive-ai ModelPool for cost optimization",
                source_package="hive-ai",
                target_use_case="Direct model API calls",
                detection_pattern=r"openai\.chat\.completions\.create",
                context_indicators=["openai", "model", "gpt", "completion"],
                required_import="from hive_ai import ModelPool",
                replacement_code=""",
# Before: Direct model call,
response = openai.chat.completions.create(
    model="gpt-4",
    messages=messages
)

# After: Optimized model routing,
pool = ModelPool()
response = await pool.generate_async(
    messages=messages,
    preferred_model="gpt-4",
    fallback_models=["gpt-3.5-turbo"],
    cost_optimization=True
)
""",
                performance_improvement="Automatic model selection and load balancing",
                reliability_improvement="Fallback models and error recovery",
                maintainability_improvement="Cost tracking and usage analytics",
                estimated_effort="1 hour",
                success_rate=0.89,
            ),
        ]

        return patterns

    def _map_package_capabilities(self) -> dict[str, dict[str, Any]]:
        """Map the capabilities provided by each hive package."""

        return {
            "hive-cache": {
                "primary_functions": ["caching", "performance", "resilience"],
                "classes": ["ClaudeAPICache", "ModelResponseCache", "HttpCache"],
                "use_cases": ["api_responses", "model_outputs", "expensive_computations"],
                "performance_impact": "high",
                "reliability_impact": "high",
            },
            "hive-errors": {
                "primary_functions": ["error_handling", "monitoring", "debugging"],
                "classes": ["ValidationError", "ConnectionError", "ProcessingError"],
                "use_cases": ["structured_exceptions", "error_categorization", "monitoring"],
                "performance_impact": "low",
                "reliability_impact": "high",
            },
            "hive-async": {
                "primary_functions": ["concurrency", "resilience", "timeouts"],
                "classes": ["async_retry", "TimeoutManager", "ExponentialBackoff"],
                "use_cases": ["retry_logic", "timeout_handling", "concurrent_operations"],
                "performance_impact": "medium",
                "reliability_impact": "very_high",
            },
            "hive-logging": {
                "primary_functions": ["observability", "debugging", "monitoring"],
                "classes": ["get_logger", "StructuredLogger"],
                "use_cases": ["standardized_logging", "structured_output", "correlation_ids"],
                "performance_impact": "low",
                "reliability_impact": "medium",
            },
            "hive-db": {
                "primary_functions": ["data_persistence", "transactions", "connections"],
                "classes": ["get_async_session", "DatabaseManager"],
                "use_cases": ["connection_pooling", "transaction_management", "async_queries"],
                "performance_impact": "high",
                "reliability_impact": "high",
            },
            "hive-config": {
                "primary_functions": ["configuration", "environment_management"],
                "classes": ["create_config_from_sources", "HiveConfig"],
                "use_cases": ["environment_variables", "configuration_validation", "dependency_injection"],
                "performance_impact": "low",
                "reliability_impact": "medium",
            },
            "hive-ai": {
                "primary_functions": ["ai_optimization", "model_management", "cost_control"],
                "classes": ["ModelPool", "CostTracker", "ModelClient"],
                "use_cases": ["model_routing", "cost_optimization", "fallback_handling"],
                "performance_impact": "high",
                "reliability_impact": "high",
            },
        }

    async def analyze_file_async(self, file_path: str) -> list[OptimizationOpportunity]:
        """Analyze a single file for cross-package optimization opportunities."""

        opportunities = []

        try:
            # Read file content
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Parse AST for deeper analysis
            try:
                tree = ast.parse(content)
                ast_opportunities = self._analyze_ast(tree, file_path, content)
                opportunities.extend(ast_opportunities)
            except SyntaxError:
                logger.warning(f"Could not parse AST for {file_path}")

            # Pattern-based analysis
            pattern_opportunities = self._analyze_patterns(content, file_path)
            opportunities.extend(pattern_opportunities)

            # Context-aware analysis
            context_opportunities = self._analyze_context(content, file_path)
            opportunities.extend(context_opportunities)

            logger.debug(f"Found {len(opportunities)} optimization opportunities in {file_path}")

        except Exception as e:
            logger.error(f"Failed to analyze file {file_path}: {e}")

        return opportunities

    def _analyze_ast(self, tree: ast.AST, file_path: str, content: str) -> list[OptimizationOpportunity]:
        """Analyze AST for sophisticated integration opportunities."""

        opportunities = []

        class IntegrationVisitor(ast.NodeVisitor):
            def __init__(self, analyzer):
                self.analyzer = analyzer
                self.opportunities = []
                self.current_function = None
                self.current_class = None

            def visit_FunctionDef(self, node):
                old_function = self.current_function
                self.current_function = node.name
                self.generic_visit(node)
                self.current_function = old_function

            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class

            def visit_Try(self, node):
                """Analyze try-except blocks for error handling opportunities."""
                for handler in node.handlers:
                    if isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                        # Generic exception handling detected
                        opportunity = OptimizationOpportunity(
                            file_path=file_path,
                            line_number=handler.lineno,
                            function_name=self.current_function,
                            class_name=self.current_class,
                            integration_type=IntegrationType.ERROR_HANDLING,
                            current_pattern="Generic Exception handling",
                            suggested_pattern="Structured exception types from hive-errors",
                            impact_level=OptimizationImpact.MEDIUM,
                            reliability_gain="Better error categorization and monitoring",
                            required_packages=["hive-errors"],
                            implementation_steps=[
                                "Import specific exception types from hive-errors",
                                "Replace generic Exception with appropriate specific types",
                                "Add structured error information",
                            ],
                            confidence=0.85,
                            certification_score_impact=2.0,
                            estimated_effort="20-30 minutes",
                            business_value="Improved error monitoring and debugging",
                            component_affected=self.analyzer._extract_component_from_path(file_path),
                            architectural_principle="Structured Error Handling",
                        )
                        self.opportunities.append(opportunity)

                self.generic_visit(node)

            def visit_Call(self, node):
                """Analyze function calls for integration opportunities."""

                # Check for requests library usage
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "requests"
                ):
                    opportunity = OptimizationOpportunity(
                        file_path=file_path,
                        line_number=node.lineno,
                        function_name=self.current_function,
                        class_name=self.current_class,
                        integration_type=IntegrationType.CACHING,
                        current_pattern=f"Direct requests.{node.func.attr}() call",
                        suggested_pattern="Cached HTTP requests using hive-cache",
                        impact_level=OptimizationImpact.HIGH,
                        performance_gain="50-90% faster for repeated requests",
                        reliability_gain="Resilience against API failures",
                        required_packages=["hive-cache"],
                        implementation_steps=[
                            "Import ClaudeAPICache from hive-cache",
                            "Wrap requests call with cache.get_or_fetch_async()",
                            "Configure appropriate TTL based on data freshness needs",
                        ],
                        confidence=0.9,
                        certification_score_impact=3.0,
                        estimated_effort="30-45 minutes",
                        business_value="Reduced API costs and improved user experience",
                        component_affected=self.analyzer._extract_component_from_path(file_path),
                        architectural_principle="Performance Optimization",
                    )
                    self.opportunities.append(opportunity)

                # Check for time.sleep in retry contexts,
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "time"
                    and node.func.attr == "sleep"
                ):
                    # Look for retry patterns in surrounding context,
                    if self._is_in_retry_context(node, content):
                        opportunity = OptimizationOpportunity(
                            file_path=file_path,
                            line_number=node.lineno,
                            function_name=self.current_function,
                            class_name=self.current_class,
                            integration_type=IntegrationType.ASYNC_PATTERNS,
                            current_pattern="Manual retry logic with time.sleep",
                            suggested_pattern="Robust retry decorators from hive-async",
                            impact_level=OptimizationImpact.HIGH,
                            reliability_gain="Configurable backoff and exception handling",
                            maintainability_gain="Declarative retry configuration",
                            required_packages=["hive-async"],
                            implementation_steps=[
                                "Import @async_retry decorator from hive-async",
                                "Replace manual retry loop with decorator",
                                "Configure backoff strategy and exception types",
                            ],
                            confidence=0.88,
                            certification_score_impact=4.0,
                            estimated_effort="45-60 minutes",
                            business_value="Improved reliability and reduced maintenance",
                            component_affected=self.analyzer._extract_component_from_path(file_path),
                            architectural_principle="Resilience Engineering",
                        )
                        self.opportunities.append(opportunity)

                self.generic_visit(node)

            def _is_in_retry_context(self, node, content):
                """Check if a time.sleep call is within a retry context."""
                # Simple heuristic: look for retry-related keywords in nearby lines
                lines = content.split("\n")
                start_line = max(0, node.lineno - 10)
                end_line = min(len(lines), node.lineno + 5)

                context = "\n".join(lines[start_line:end_line]).lower()
                retry_indicators = ["retry", "attempt", "for", "while", "except"]

                return any(indicator in context for indicator in retry_indicators)

        visitor = IntegrationVisitor(self)
        visitor.visit(tree)
        opportunities.extend(visitor.opportunities)

        return opportunities

    def _analyze_patterns(self, content: str, file_path: str) -> list[OptimizationOpportunity]:
        """Analyze file content using regex patterns for integration opportunities."""

        opportunities = []

        for pattern in self.integration_patterns:
            matches = re.finditer(pattern.detection_pattern, content, re.MULTILINE)

            for match in matches:
                # Check if context indicators are present
                context_match = True
                if pattern.context_indicators:
                    context_match = any(
                        indicator.lower() in content.lower() for indicator in pattern.context_indicators
                    )

                if context_match:
                    # Calculate line number,
                    line_number = content[: match.start()].count("\n") + 1

                    # Determine impact level based on pattern characteristics,
                    impact_level = self._assess_pattern_impact(pattern, content)

                    opportunity = OptimizationOpportunity(
                        file_path=file_path,
                        line_number=line_number,
                        integration_type=self._map_pattern_to_integration_type(pattern),
                        current_pattern=match.group(),
                        suggested_pattern=pattern.name,
                        impact_level=impact_level,
                        performance_gain=pattern.performance_improvement,
                        reliability_gain=pattern.reliability_improvement,
                        maintainability_gain=pattern.maintainability_improvement,
                        required_packages=[pattern.source_package],
                        implementation_steps=[
                            f"Add import: {pattern.required_import}",
                            f"Replace current pattern with {pattern.name}",
                            "Test integration and adjust configuration",
                        ],
                        code_example=pattern.replacement_code,
                        confidence=pattern.success_rate,
                        certification_score_impact=self._calculate_certification_impact(pattern),
                        estimated_effort=pattern.estimated_effort,
                        business_value=self._generate_business_value(pattern),
                        component_affected=self._extract_component_from_path(file_path),
                        architectural_principle=self._get_architectural_principle(pattern),
                        documentation_reference=f"docs/packages/{pattern.source_package}/README.md",
                    )

                    opportunities.append(opportunity)

        return opportunities

    def _analyze_context(self, content: str, file_path: str) -> list[OptimizationOpportunity]:
        """Analyze file context for sophisticated integration opportunities."""

        opportunities = []

        # Analyze import statements for missing integrations
        imports = re.findall(r"^(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", content, re.MULTILINE)

        # Check for missing hive package integrations
        hive_imports = [imp for imp in imports if imp.startswith("hive")]
        missing_integrations = self._identify_missing_integrations(content, hive_imports)

        for integration in missing_integrations:
            opportunity = OptimizationOpportunity(
                file_path=file_path,
                integration_type=integration["type"],
                current_pattern=integration["current"],
                suggested_pattern=integration["suggested"],
                impact_level=integration["impact"],
                required_packages=integration["packages"],
                confidence=integration["confidence"],
                certification_score_impact=integration["score_impact"],
                estimated_effort=integration["effort"],
                business_value=integration["business_value"],
                component_affected=self._extract_component_from_path(file_path),
            )
            opportunities.append(opportunity)

        return opportunities

    def _identify_missing_integrations(self, content: str, current_hive_imports: list[str]) -> list[dict[str, Any]]:
        """Identify missing hive package integrations based on content analysis."""

        missing = []

        # Check for logging without hive-logging
        if "logging.getLogger" in content and "hive_logging" not in current_hive_imports:
            missing.append(
                {
                    "type": IntegrationType.LOGGING,
                    "current": "Manual logging setup",
                    "suggested": "Standardized hive-logging",
                    "impact": OptimizationImpact.LOW,
                    "packages": ["hive-logging"],
                    "confidence": 0.95,
                    "score_impact": 1.0,
                    "effort": "15 minutes",
                    "business_value": "Consistent logging format and configuration",
                }
            )

        # Check for database operations without hive-db
        if "sqlite3.connect" in content and "hive_db" not in current_hive_imports:
            missing.append(
                {
                    "type": IntegrationType.DATABASE,
                    "current": "Direct database connections",
                    "suggested": "Managed connections with hive-db",
                    "impact": OptimizationImpact.HIGH,
                    "packages": ["hive-db"],
                    "confidence": 0.85,
                    "score_impact": 5.0,
                    "effort": "1-2 hours",
                    "business_value": "Better connection management and transaction support",
                }
            )

        # Check for AI model calls without optimization
        if (
            ("openai" in content or "anthropic" in content)
            and "hive_ai" not in current_hive_imports
            and "hive_cache" not in current_hive_imports
        ):
            missing.append(
                {
                    "type": IntegrationType.AI_INTEGRATION,
                    "current": "Direct AI model calls",
                    "suggested": "Optimized model routing and caching",
                    "impact": OptimizationImpact.TRANSFORMATIVE,
                    "packages": ["hive-ai", "hive-cache"],
                    "confidence": 0.9,
                    "score_impact": 8.0,
                    "effort": "2-3 hours",
                    "business_value": "Significant cost reduction and performance improvement",
                }
            )

        return missing

    def _assess_pattern_impact(self, pattern: IntegrationPattern, content: str) -> OptimizationImpact:
        """Assess the impact level of applying a pattern to the content."""

        # High impact patterns
        if pattern.name in ["Model Response Caching", "Robust Retry Logic"]:
            return OptimizationImpact.HIGH

        # Transformative patterns for AI-heavy files
        if "ai" in pattern.source_package and (
            "openai" in content or "anthropic" in content or "model" in content.lower()
        ):
            return OptimizationImpact.TRANSFORMATIVE

        # Medium impact for reliability improvements
        if pattern.reliability_improvement:
            return OptimizationImpact.MEDIUM

        # Default to low impact
        return OptimizationImpact.LOW

    def _map_pattern_to_integration_type(self, pattern: IntegrationPattern) -> IntegrationType:
        """Map an integration pattern to its integration type."""

        type_mapping = {
            "hive-cache": IntegrationType.CACHING,
            "hive-errors": IntegrationType.ERROR_HANDLING,
            "hive-async": IntegrationType.ASYNC_PATTERNS,
            "hive-logging": IntegrationType.LOGGING,
            "hive-db": IntegrationType.DATABASE,
            "hive-config": IntegrationType.CONFIGURATION,
            "hive-ai": IntegrationType.AI_INTEGRATION,
        }

        return type_mapping.get(pattern.source_package, IntegrationType.CONFIGURATION)

    def _calculate_certification_impact(self, pattern: IntegrationPattern) -> float:
        """Calculate the certification score impact of applying a pattern."""

        # High impact patterns
        if pattern.source_package in ["hive-ai", "hive-async"]:
            return 5.0

        # Medium impact patterns
        if pattern.source_package in ["hive-cache", "hive-db"]:
            return 3.0

        # Low impact patterns
        return 1.0

    def _generate_business_value(self, pattern: IntegrationPattern) -> str:
        """Generate business value description for a pattern."""

        value_map = {
            "hive-cache": "Reduced API costs and improved user experience",
            "hive-errors": "Better error monitoring and faster debugging",
            "hive-async": "Improved reliability and reduced downtime",
            "hive-logging": "Enhanced observability and troubleshooting",
            "hive-db": "Better data consistency and performance",
            "hive-ai": "Significant cost reduction and performance optimization",
        }

        return value_map.get(pattern.source_package, "Improved architectural consistency")

    def _get_architectural_principle(self, pattern: IntegrationPattern) -> str:
        """Get the architectural principle associated with a pattern."""

        principle_map = {
            "hive-cache": "Performance Optimization",
            "hive-errors": "Structured Error Handling",
            "hive-async": "Resilience Engineering",
            "hive-logging": "Observability",
            "hive-db": "Data Management",
            "hive-config": "Configuration Management",
            "hive-ai": "AI Optimization",
        }

        return principle_map.get(pattern.source_package, "Architectural Integration")

    def _extract_component_from_path(self, file_path: str) -> str:
        """Extract component name from file path."""

        parts = file_path.split("/")

        # Look for hive-* packages
        for part in parts:
            if part.startswith("hive-"):
                return part

        # Look for app names
        if "apps/" in file_path:
            app_parts = file_path.split("apps/")[1].split("/")
            if app_parts:
                return app_parts[0]

        return "unknown"

    async def generate_integration_report_async(self, opportunities: list[OptimizationOpportunity]) -> dict[str, Any]:
        """Generate a comprehensive cross-package integration report."""

        if not opportunities:
            return {"summary": "No cross-package integration opportunities found", "total_opportunities": 0}

        # Group by integration type
        by_type = {}
        for opp in opportunities:
            type_name = opp.integration_type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(opp)

        # Group by impact level
        by_impact = {}
        for opp in opportunities:
            impact_name = opp.impact_level.value
            if impact_name not in by_impact:
                by_impact[impact_name] = []
            by_impact[impact_name].append(opp)

        # Calculate total potential impact
        total_cert_impact = sum(opp.certification_score_impact for opp in opportunities)
        total_effort_hours = self._calculate_total_effort_hours(opportunities)

        # Generate top recommendations
        top_opportunities = sorted(
            opportunities,
            key=lambda x: (x.impact_level.value, x.certification_score_impact, x.confidence),
            reverse=True,
        )[:10]

        return {
            "summary": f"Found {len(opportunities)} cross-package integration opportunities",
            "total_opportunities": len(opportunities),
            "by_integration_type": {k: len(v) for k, v in by_type.items()},
            "by_impact_level": {k: len(v) for k, v in by_impact.items()},
            "potential_certification_impact": total_cert_impact,
            "estimated_implementation_hours": total_effort_hours,
            "top_recommendations": [
                {
                    "file": opp.file_path,
                    "type": opp.integration_type.value,
                    "current": opp.current_pattern,
                    "suggested": opp.suggested_pattern,
                    "impact": opp.impact_level.value,
                    "certification_gain": opp.certification_score_impact,
                    "effort": opp.estimated_effort,
                    "business_value": opp.business_value,
                }
                for opp in top_opportunities
            ],
            "quick_wins": [
                {"file": opp.file_path, "suggestion": opp.suggested_pattern, "effort": opp.estimated_effort}
                for opp in opportunities
                if opp.estimated_effort.startswith(("15", "30")) and opp.confidence > 0.9
            ][:5],
        }

    def _calculate_total_effort_hours(self, opportunities: list[OptimizationOpportunity]) -> float:
        """Calculate total implementation effort in hours."""

        total_hours = 0.0

        for opp in opportunities:
            effort_str = opp.estimated_effort.lower()

            if "hour" in effort_str:
                if "1-2" in effort_str:
                    total_hours += 1.5
                elif "2-3" in effort_str:
                    total_hours += 2.5
                else:
                    total_hours += 1.0
            elif "minute" in effort_str:
                if "30-45" in effort_str:
                    total_hours += 0.625
                elif "45-60" in effort_str:
                    total_hours += 0.875
                elif "15" in effort_str:
                    total_hours += 0.25
                else:
                    total_hours += 0.5

        return total_hours

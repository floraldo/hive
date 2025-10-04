"""
Data models for test intelligence system.

Defines the structure of test runs, test results, and derived analytics.
"""
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    """Test execution status."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class TestType(str, Enum):
    """Test category classification."""

    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    SMOKE = "smoke"
    BENCHMARK = "benchmark"
    RESILIENCE = "resilience"


class TestRun(BaseModel):
    """Represents a complete test suite execution."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_seconds: float
    git_commit: str | None = None
    git_branch: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100


class TestResult(BaseModel):
    """Individual test result within a test run."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    test_id: str  # Full pytest node ID: path::Class::test_method
    status: TestStatus
    duration_ms: float
    error_message: str | None = None
    error_traceback: str | None = None
    package_name: str
    test_type: TestType = TestType.UNIT
    file_path: str
    line_number: int | None = None

    @property
    def duration_seconds(self) -> float:
        """Convert duration to seconds."""
        return self.duration_ms / 1000


class FlakyTestResult(BaseModel):
    """Analysis result for flaky test detection."""

    test_id: str
    total_runs: int
    passed_runs: int
    failed_runs: int
    error_runs: int
    fail_rate: float
    first_seen: datetime
    last_seen: datetime
    error_messages: list[str]

    @property
    def is_flaky(self) -> bool:
        """Determine if test is considered flaky."""
        # Flaky: fails >10% but <90% of the time
        return 0.1 < self.fail_rate < 0.9


class PackageHealthReport(BaseModel):
    """Health metrics for a specific package."""

    package_name: str
    total_tests: int
    pass_rate: float
    avg_duration_ms: float
    flaky_count: int
    trend_direction: str  # "improving", "stable", "degrading"
    trend_percentage: float
    last_updated: datetime = Field(default_factory=datetime.now)


class FailurePattern(BaseModel):
    """Clustered failure pattern across multiple tests."""

    pattern_id: str = Field(default_factory=lambda: str(uuid4()))
    error_signature: str  # Normalized error message
    affected_tests: list[str]
    occurrence_count: int
    first_seen: datetime
    last_seen: datetime
    packages_affected: list[str]
    suggested_root_cause: str | None = None

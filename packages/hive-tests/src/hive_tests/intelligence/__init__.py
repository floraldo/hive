"""Hive Test Intelligence - Intelligent test analysis and health monitoring.

Provides automated test result collection, flaky test detection, failure
trend analysis, and actionable insights for platform health monitoring.
"""

from .models import FailurePattern, FlakyTestResult, PackageHealthReport, TestResult, TestRun, TestStatus, TestType
from .storage import TestIntelligenceStorage

__version__ = "0.1.0"

__all__ = [
    "FailurePattern",
    "FlakyTestResult",
    "PackageHealthReport",
    "TestIntelligenceStorage",
    "TestResult",
    "TestRun",
    "TestStatus",
    "TestType",
]

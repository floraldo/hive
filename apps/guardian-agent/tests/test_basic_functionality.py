"""Basic functionality tests for Guardian Agent."""

import asyncio
from pathlib import Path

import pytest

from guardian_agent.core.config import GuardianConfig
from guardian_agent.core.interfaces import Severity, ViolationType
from guardian_agent.analyzers.code_analyzer import CodeAnalyzer


@pytest.mark.asyncio
async def test_code_analyzer_detects_complexity():
    """Test that CodeAnalyzer detects high complexity."""
    analyzer = CodeAnalyzer()

    # Complex function with multiple branches
    complex_code = """
def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                for i in range(10):
                    if i % 2 == 0:
                        while i < 5:
                            if i == 3:
                                return i
                            i += 1
    elif x < 0:
        for j in range(5):
            if j > 2:
                return j
    else:
        return 0
"""

    result = await analyzer.analyze(Path("test.py"), complex_code)

    assert result.analyzer_name == "CodeAnalyzer"
    assert len(result.violations) > 0

    # Should detect high complexity
    complexity_violations = [
        v for v in result.violations
        if v.rule == "high-complexity"
    ]
    assert len(complexity_violations) > 0


@pytest.mark.asyncio
async def test_code_analyzer_suggests_type_hints():
    """Test that CodeAnalyzer suggests type hints."""
    analyzer = CodeAnalyzer()

    code_without_types = """
def add_numbers(a, b):
    return a + b

def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""

    result = await analyzer.analyze(Path("test.py"), code_without_types)

    # Should suggest type hints
    type_suggestions = [
        s for s in result.suggestions
        if s.category == "type-hints"
    ]
    assert len(type_suggestions) > 0


def test_config_loading():
    """Test configuration loading and validation."""
    config = GuardianConfig()

    # Default values should be set
    assert config.review.model == "gpt-4"
    assert config.review.temperature == 0.3
    assert config.review.enable_golden_rules is True

    # Test custom configuration
    custom_config = GuardianConfig()
    custom_config.review.model = "gpt-3.5-turbo"
    custom_config.review.max_tokens = 1000

    assert custom_config.review.model == "gpt-3.5-turbo"
    assert custom_config.review.max_tokens == 1000


def test_review_result_markdown_generation():
    """Test ReviewResult markdown generation."""
    from guardian_agent.core.interfaces import (
        ReviewResult,
        AnalysisResult,
        Violation,
        Suggestion,
    )

    # Create a sample review result
    violation = Violation(
        type=ViolationType.CODE_SMELL,
        severity=Severity.WARNING,
        rule="long-function",
        message="Function is too long",
        file_path=Path("test.py"),
        line_number=10,
    )

    suggestion = Suggestion(
        category="refactoring",
        message="Consider splitting into smaller functions",
        file_path=Path("test.py"),
        line_range=(10, 50),
        confidence=0.85,
    )

    analysis_result = AnalysisResult(
        analyzer_name="TestAnalyzer",
        violations=[violation],
        suggestions=[suggestion],
    )

    review_result = ReviewResult(
        file_path=Path("test.py"),
        analysis_results=[analysis_result],
        overall_score=75.0,
        summary="Code has some quality issues",
        violations_count={
            Severity.WARNING: 1,
            Severity.ERROR: 0,
            Severity.CRITICAL: 0,
            Severity.INFO: 0,
        },
        suggestions_count=1,
        auto_fixable_count=0,
        ai_confidence=0.9,
    )

    # Generate markdown
    markdown = review_result.to_markdown()

    # Check markdown contains expected elements
    assert "# Code Review: test.py" in markdown
    assert "Overall Score" in markdown
    assert "75" in markdown
    assert "Function is too long" in markdown
    assert "Consider splitting" in markdown


@pytest.mark.asyncio
async def test_code_analyzer_metrics():
    """Test that CodeAnalyzer collects metrics."""
    analyzer = CodeAnalyzer()

    sample_code = """
import os
import sys
from pathlib import Path

class MyClass:
    def method1(self):
        pass

    def method2(self):
        return 42

def standalone_function():
    pass

async def async_function():
    await some_operation()
"""

    result = await analyzer.analyze(Path("test.py"), sample_code)

    # Check metrics
    assert result.metrics["num_classes"] == 1
    assert result.metrics["num_functions"] == 3  # Including async
    assert result.metrics["num_async_functions"] == 1
    assert result.metrics["num_imports"] == 3
    assert result.metrics["lines_of_code"] > 10
"""
Tests for the AI Reviewer review engine
"""

from hive_logging import get_logger

logger = get_logger(__name__)

import pytest
from ai_reviewer.reviewer import (
    QualityMetrics,
    ReviewDecision,
    ReviewEngine,
    ReviewResult,
)


class TestQualityMetrics:
    """Test the QualityMetrics class"""

    def test_overall_score_calculation(self):
        """Test that overall score is calculated correctly"""
        metrics = QualityMetrics(
            code_quality=80,
            test_coverage=90,
            documentation=70,
            security=85,
            architecture=75,
        )

        # Expected: 80*0.3 + 90*0.25 + 70*0.15 + 85*0.2 + 75*0.1
        # = 24 + 22.5 + 10.5 + 17 + 7.5 = 81.5
        assert metrics.overall_score == 81.5

    def test_perfect_scores(self):
        """Test with perfect scores"""
        metrics = QualityMetrics(
            code_quality=100,
            test_coverage=100,
            documentation=100,
            security=100,
            architecture=100,
        )
        assert metrics.overall_score == 100

    def test_zero_scores(self):
        """Test with zero scores"""
        metrics = QualityMetrics(code_quality=0, test_coverage=0, documentation=0, security=0, architecture=0)
        assert metrics.overall_score == 0


class TestReviewEngine:
    """Test the ReviewEngine class"""

    @pytest.fixture
    def engine(self):
        """Create a review engine instance"""
        return ReviewEngine(mock_mode=True)

    @pytest.fixture
    def sample_code(self):
        """Sample code files for testing"""
        return {
            "main.py": """
def calculate_sum(a, b):
    \"\"\"Calculate the sum of two numbers\"\"\"
    return a + b

def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result
""",
            "test_main.py": """
import pytest
from main import calculate_sum, process_data

def test_calculate_sum():
    assert calculate_sum(2, 3) == 5
    assert calculate_sum(-1, 1) == 0

def test_process_data():
    assert process_data([1, 2, 3]) == [2, 4, 6]
    assert process_data([-1, 0, 1]) == [2]
""",
        }

    def test_review_task_basic(self, engine, sample_code):
        """Test basic review functionality"""
        result = engine.review_task(
            task_id="test-123",
            task_description="Implement basic math functions",
            code_files=sample_code,
            test_results={"passed": True, "coverage": 85},
        )

        assert isinstance(result, ReviewResult)
        assert result.task_id == "test-123"
        assert isinstance(result.decision, ReviewDecision)
        assert isinstance(result.metrics, QualityMetrics)
        assert isinstance(result.summary, str)
        assert isinstance(result.issues, list)
        assert isinstance(result.suggestions, list)
        assert 0 <= result.confidence <= 1

    def test_score_code_quality(self, engine):
        """Test code quality scoring"""
        good_code = {
            "good.py": """
def add(x: int, y: int) -> int:
    \"\"\"Add two integers.\"\"\"
    return x + y
"""
        }
        score = engine._score_code_quality(good_code)
        assert score > 80  # Good code should score high

        bad_code = {
            "bad.py": """
def very_long_function_that_does_too_many_things():
    # TODO: refactor this
    # TODO: add tests
    x = 12345
    y = 67890
    z = 11111
    for i in range(100):
        if i > 0:
            if i > 10:
                if i > 20:
                    if i > 30:
                        logger.info(i)
    """
            + "\n".join(["    pass"] * 50)  # Make it very long
        }
        score = engine._score_code_quality(bad_code)
        assert score < 70  # Bad code should score low

    def test_score_test_coverage(self, engine):
        """Test coverage scoring"""
        code_with_tests = {
            "main.py": "def func(): pass",
            "test_main.py": "def test_func(): pass",
        }
        score = engine._score_test_coverage(code_with_tests, {"passed": True, "coverage": 90})
        assert score > 80

        code_without_tests = {"main.py": "def func(): pass"}
        score = engine._score_test_coverage(code_without_tests, None)
        assert score == 0

    def test_score_documentation(self, engine):
        """Test documentation scoring"""
        well_documented = {
            "main.py": '''
def function_one():
    """This function does something."""
    pass

def function_two():
    """This function does something else."""
    pass
'''
        }
        score = engine._score_documentation(well_documented)
        assert score == 100

        poorly_documented = {
            "main.py": """
def function_one():
    pass

def function_two():
    pass
"""
        }
        score = engine._score_documentation(poorly_documented)
        assert score == 0

    def test_score_security(self, engine):
        """Test security scoring"""
        secure_code = {
            "secure.py": """
import json

def process_data(data):
    return json.loads(data)
"""
        }
        score = engine._score_security(secure_code)
        assert score == 100

        insecure_code = {
            "insecure.py": """
def run_command(cmd):
    eval(cmd)
    exec(cmd)
    os.system(cmd)
    password = "hardcoded123"
"""
        }
        score = engine._score_security(insecure_code)
        assert score < 60

    def test_detect_issues(self, engine):
        """Test issue detection"""
        problematic_code = {
            "problems.py": """
# TODO: fix this later
def process():
    try:
        logger.info("debugging")
        x = 1
    except:
        pass
"""
            + "x" * 150  # Long line
        }

        issues = engine._detect_issues(problematic_code, None)
        assert any("TODO" in issue for issue in issues)
        assert any("except" in issue for issue in issues)
        assert any("print" in issue for issue in issues)
        assert any("120 characters" in issue for issue in issues)

    def test_make_decision(self, engine):
        """Test decision making logic"""
        # High score should approve
        high_metrics = QualityMetrics(
            code_quality=90,
            test_coverage=85,
            documentation=80,
            security=95,
            architecture=90,
        )
        decision = engine._make_decision(high_metrics, [])
        assert decision == ReviewDecision.APPROVE

        # Medium score should suggest rework
        medium_metrics = QualityMetrics(
            code_quality=70,
            test_coverage=60,
            documentation=50,
            security=75,
            architecture=70,
        )
        decision = engine._make_decision(medium_metrics, [])
        assert decision == ReviewDecision.REWORK

        # Low score should reject
        low_metrics = QualityMetrics(
            code_quality=30,
            test_coverage=20,
            documentation=10,
            security=40,
            architecture=30,
        )
        decision = engine._make_decision(low_metrics, [])
        assert decision == ReviewDecision.REJECT

        # Critical issues should always reject
        good_metrics = QualityMetrics(
            code_quality=90,
            test_coverage=90,
            documentation=90,
            security=90,
            architecture=90,
        )
        critical_issues = ["Security vulnerability detected", "Test failures"]
        decision = engine._make_decision(good_metrics, critical_issues)
        assert decision == ReviewDecision.REJECT

    def test_generate_suggestions(self, engine):
        """Test suggestion generation"""
        low_metrics = QualityMetrics(
            code_quality=50,
            test_coverage=40,
            documentation=30,
            security=60,
            architecture=70,
        )
        issues = ["TODO comments found", "print statements detected"]

        suggestions = engine._generate_suggestions({}, issues, low_metrics)

        assert any("test coverage" in s.lower() for s in suggestions)
        assert any("docstring" in s.lower() for s in suggestions)
        assert any("TODO" in s for s in suggestions)
        assert any("logging" in s for s in suggestions)

    def test_review_result_to_dict(self, engine, sample_code):
        """Test ReviewResult.to_dict() method"""
        result = engine.review_task(task_id="test-456", task_description="Test task", code_files=sample_code)

        result_dict = result.to_dict()

        assert result_dict["task_id"] == "test-456"
        assert "decision" in result_dict
        assert "metrics" in result_dict
        assert "overall_score" in result_dict
        assert "summary" in result_dict
        assert "issues" in result_dict
        assert "suggestions" in result_dict
        assert "confidence" in result_dict


class TestReviewWorkflow:
    """Test the complete review workflow"""

    def test_approve_workflow(self):
        """Test approval workflow for high-quality code"""
        engine = ReviewEngine(mock_mode=True)

        excellent_code = {
            "calculator.py": '''
"""Calculator module with basic operations."""

def add(x: float, y: float) -> float:
    """
    Add two numbers.

    Args:
        x: First number
        y: Second number

    Returns:
        Sum of x and y
    """
    return x + y

def subtract(x: float, y: float) -> float:
    """
    Subtract y from x.

    Args:
        x: First number
        y: Second number

    Returns:
        Difference of x and y
    """
    return x - y
''',
            "test_calculator.py": '''
"""Tests for calculator module."""

import pytest
from calculator import add, subtract

def test_add():
    """Test addition function."""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0.5, 0.5) == 1.0

def test_subtract():
    """Test subtraction function."""
    assert subtract(5, 3) == 2
    assert subtract(0, 1) == -1
    assert subtract(1.5, 0.5) == 1.0
''',
        }

        result = engine.review_task(
            task_id="excel-001",
            task_description="Implement calculator with add and subtract",
            code_files=excellent_code,
            test_results={"passed": True, "coverage": 100},
        )

        assert result.decision == ReviewDecision.APPROVE
        assert result.metrics.overall_score > 80
        assert len(result.issues) == 0

    def test_reject_workflow(self):
        """Test rejection workflow for poor-quality code"""
        engine = ReviewEngine(mock_mode=True)

        poor_code = {
            "hack.py": """
# Quick hack, TODO: fix everything
def do_stuff(x):
    eval(x)  # Process input
    password = "admin123"
    try:
        # Lots of nested logic
        if x:
            if x > 0:
                if x > 10:
                    if x > 100:
                        logger.info("big number")
    except:
        pass  # Ignore all errors
"""
        }

        result = engine.review_task(
            task_id="poor-001",
            task_description="Process user input",
            code_files=poor_code,
            test_results=None,
        )

        assert result.decision in [ReviewDecision.REJECT, ReviewDecision.ESCALATE]
        assert result.metrics.overall_score < 60
        assert len(result.issues) > 0
        assert len(result.suggestions) > 0

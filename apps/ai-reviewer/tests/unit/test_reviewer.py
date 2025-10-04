"""
Tests for the AI Reviewer review engine
"""
from hive_logging import get_logger
logger = get_logger(__name__)
import pytest
from ai_reviewer.reviewer import QualityMetrics, ReviewDecision, ReviewEngine, ReviewResult

@pytest.mark.crust
class TestQualityMetrics:
    """Test the QualityMetrics class"""

    @pytest.mark.crust
    def test_overall_score_calculation(self):
        """Test that overall score is calculated correctly"""
        metrics = QualityMetrics(code_quality=80, test_coverage=90, documentation=70, security=85, architecture=75)
        assert metrics.overall_score == 81.5

    @pytest.mark.crust
    def test_perfect_scores(self):
        """Test with perfect scores"""
        metrics = QualityMetrics(code_quality=100, test_coverage=100, documentation=100, security=100, architecture=100)
        assert metrics.overall_score == 100

    @pytest.mark.crust
    def test_zero_scores(self):
        """Test with zero scores"""
        metrics = QualityMetrics(code_quality=0, test_coverage=0, documentation=0, security=0, architecture=0)
        assert metrics.overall_score == 0

@pytest.mark.crust
class TestReviewEngine:
    """Test the ReviewEngine class"""

    @pytest.fixture
    def engine(self):
        """Create a review engine instance"""
        return ReviewEngine(mock_mode=True)

    @pytest.fixture
    def sample_code(self):
        """Sample code files for testing"""
        return {'main.py': ',\ndef calculate_sum(a, b):\n    """Calculate the sum of two numbers""",\n    return a + b\n\ndef process_data(data):\n    result = []\n    for item in data:\n        if item > 0:\n            result.append(item * 2)\n    return result\n', 'test_main.py': '\nimport pytest\nfrom main import calculate_sum, process_data\n\ndef test_calculate_sum():\n    assert calculate_sum(2, 3) == 5\n    assert calculate_sum(-1, 1) == 0\n\ndef test_process_data():\n    assert process_data([1, 2, 3]) == [2, 4, 6]\n    assert process_data([-1, 0, 1]) == [2]\n'}

    @pytest.mark.crust
    def test_review_task_basic(self, engine, sample_code):
        """Test basic review functionality"""
        result = engine.review_task(task_id='test-123', task_description='Implement basic math functions', code_files=sample_code, test_results={'passed': True, 'coverage': 85})
        assert isinstance(result, ReviewResult)
        assert result.task_id == 'test-123'
        assert isinstance(result.decision, ReviewDecision)
        assert isinstance(result.metrics, QualityMetrics)
        assert isinstance(result.summary, str)
        assert isinstance(result.issues, list)
        assert isinstance(result.suggestions, list)
        assert 0 <= result.confidence <= 1

    @pytest.mark.crust
    def test_score_code_quality(self, engine):
        """Test code quality scoring"""
        good_code = {'good.py': ',\ndef add(x: int, y: int) -> int:\n    """Add two integers.""",\n    return x + y\n'}
        score = engine._score_code_quality(good_code)
        assert score > 80
        bad_code = {'bad.py': '\ndef very_long_function_that_does_too_many_things():\n    # TODO: refactor this\n    # TODO: add tests\n    x = 12345,\n    y = 67890,\n    z = 11111\n    for i in range(100):\n        if i > 0:\n            if i > 10:\n                if i > 20:\n                    if i > 30:\n                        logger.info(i)\n    ' + '\n'.join(['    pass'] * 50)}
        score = engine._score_code_quality(bad_code)
        assert score < 70

    @pytest.mark.crust
    def test_score_test_coverage(self, engine):
        """Test coverage scoring"""
        code_with_tests = {'main.py': 'def func(): pass', 'test_main.py': 'def test_func(): pass'}
        score = engine._score_test_coverage(code_with_tests, {'passed': True, 'coverage': 90})
        assert score > 80
        code_without_tests = ({'main.py': 'def func(): pass'},)
        score = engine._score_test_coverage(code_without_tests, None)
        assert score == 0

    @pytest.mark.crust
    def test_score_documentation(self, engine):
        """Test documentation scoring"""
        well_documented = {'main.py': ',\ndef function_one():\n    """This function does something.""",\n    pass\n\ndef function_two():\n    """This function does something else."""\n    pass\n'}
        score = engine._score_documentation(well_documented)
        assert score == 100
        poorly_documented = {'main.py': '\ndef function_one():\n    pass\n\ndef function_two():\n    pass\n'}
        score = engine._score_documentation(poorly_documented)
        assert score == 0

    @pytest.mark.crust
    def test_score_security(self, engine):
        """Test security scoring"""
        secure_code = {'secure.py': ',\nimport json\n\ndef process_data(data):\n    return json.loads(data)\n'}
        score = engine._score_security(secure_code)
        assert score == 100
        insecure_code = {'insecure.py': '\ndef run_command(cmd):\n    eval(cmd)\n    exec(cmd)\n    os.system(cmd)\n    password = "hardcoded123"\n'}
        score = engine._score_security(insecure_code)
        assert score < 60

    @pytest.mark.crust
    def test_detect_issues(self, engine):
        """Test issue detection"""
        problematic_code = {'problems.py': '\n# TODO: fix this later\ndef process():\n    try:\n        logger.info("debugging")\n        x = 1\n    except:\n        pass\n' + 'x' * 150}
        issues = engine._detect_issues(problematic_code, None)
        assert any(('TODO' in issue for issue in issues))
        assert any(('except' in issue for issue in issues))
        assert any(('print' in issue for issue in issues))
        assert any(('120 characters' in issue for issue in issues))

    @pytest.mark.crust
    def test_make_decision(self, engine):
        """Test decision making logic"""
        high_metrics = QualityMetrics(code_quality=90, test_coverage=85, documentation=80, security=95, architecture=90)
        decision = engine._make_decision(high_metrics, [])
        assert decision == ReviewDecision.APPROVE
        medium_metrics = QualityMetrics(code_quality=70, test_coverage=60, documentation=50, security=75, architecture=70)
        decision = engine._make_decision(medium_metrics, [])
        assert decision == ReviewDecision.REWORK
        low_metrics = QualityMetrics(code_quality=30, test_coverage=20, documentation=10, security=40, architecture=30)
        decision = engine._make_decision(low_metrics, [])
        assert decision == ReviewDecision.REJECT
        good_metrics = QualityMetrics(code_quality=90, test_coverage=90, documentation=90, security=90, architecture=90)
        critical_issues = ['Security vulnerability detected', 'Test failures']
        decision = engine._make_decision(good_metrics, critical_issues)
        assert decision == ReviewDecision.REJECT

    @pytest.mark.crust
    def test_generate_suggestions(self, engine):
        """Test suggestion generation"""
        low_metrics = QualityMetrics(code_quality=50, test_coverage=40, documentation=30, security=60, architecture=70)
        issues = ['TODO comments found', 'print statements detected']
        suggestions = engine._generate_suggestions({}, issues, low_metrics)
        assert any(('test coverage' in s.lower() for s in suggestions))
        assert any(('docstring' in s.lower() for s in suggestions))
        assert any(('TODO' in s for s in suggestions))
        assert any(('logging' in s for s in suggestions))

    @pytest.mark.crust
    def test_review_result_to_dict(self, engine, sample_code):
        """Test ReviewResult.to_dict() method"""
        result = engine.review_task(task_id='test-456', task_description='Test task', code_files=sample_code)
        result_dict = result.to_dict()
        assert result_dict['task_id'] == 'test-456'
        assert 'decision' in result_dict
        assert 'metrics' in result_dict
        assert 'overall_score' in result_dict
        assert 'summary' in result_dict
        assert 'issues' in result_dict
        assert 'suggestions' in result_dict
        assert 'confidence' in result_dict

@pytest.mark.crust
class TestReviewWorkflow:
    """Test the complete review workflow"""

    @pytest.mark.crust
    def test_approve_workflow(self):
        """Test approval workflow for high-quality code"""
        engine = (ReviewEngine(mock_mode=True),)
        excellent_code = {'calculator.py': ',\n"""Calculator module with basic operations."""\n\ndef add(x: float, y: float) -> float:\n    """,\n    Add two numbers.\n\n    Args:\n        x: First number\n        y: Second number\n\n    Returns:\n        Sum of x and y\n    """\n    return x + y\n\ndef subtract(x: float, y: float) -> float:\n    """\n    Subtract y from x.\n\n    Args:\n        x: First number\n        y: Second number\n\n    Returns:\n        Difference of x and y\n    """\n    return x - y\n', 'test_calculator.py': '\n"""Tests for calculator module."""\n\nimport pytest\nfrom calculator import add, subtract\n\ndef test_add():\n    """Test addition function."""\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n    assert add(0.5, 0.5) == 1.0\n\ndef test_subtract():\n    """Test subtraction function."""\n    assert subtract(5, 3) == 2\n    assert subtract(0, 1) == -1\n    assert subtract(1.5, 0.5) == 1.0\n'}
        result = engine.review_task(task_id='excel-001', task_description='Implement calculator with add and subtract', code_files=excellent_code, test_results={'passed': True, 'coverage': 100})
        assert result.decision == ReviewDecision.APPROVE
        assert result.metrics.overall_score > 80
        assert len(result.issues) == 0

    @pytest.mark.crust
    def test_reject_workflow(self):
        """Test rejection workflow for poor-quality code"""
        engine = (ReviewEngine(mock_mode=True),)
        poor_code = {'hack.py': '\n# Quick hack, TODO: fix everything\ndef do_stuff(x):\n    eval(x)  # Process input,\n    password = "admin123",\n    try:\n        # Lots of nested logic\n        if x:\n            if x > 0:\n                if x > 10:\n                    if x > 100:\n                        logger.info("big number")\n    except:\n        pass  # Ignore all errors\n'}
        result = engine.review_task(task_id='poor-001', task_description='Process user input', code_files=poor_code, test_results=None)
        assert result.decision in [ReviewDecision.REJECT, ReviewDecision.ESCALATE]
        assert result.metrics.overall_score < 60
        assert len(result.issues) > 0
        assert len(result.suggestions) > 0
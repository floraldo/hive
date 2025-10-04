"""Basic functionality tests for Guardian Agent."""
from pathlib import Path

import pytest

from guardian_agent.analyzers.code_analyzer import CodeAnalyzer
from guardian_agent.core.config import GuardianConfig
from guardian_agent.core.interfaces import Severity, ViolationType


@pytest.mark.crust
@pytest.mark.asyncio
async def test_code_analyzer_detects_complexity():
    """Test that CodeAnalyzer detects high complexity."""
    analyzer = CodeAnalyzer()
    complex_code = '\ndef complex_function(x, y, z):\n    if x > 0:\n        if y > 0:\n            if z > 0:\n                for i in range(10):\n                    if i % 2 == 0:\n                        while i < 5:\n                            if i == 3:\n                                return i\n                            i += 1\n    elif x < 0:\n        for j in range(5):\n            if j > 2:\n                return j\n    else:\n        return 0\n'
    result = await analyzer.analyze(Path('test.py'), complex_code)
    assert result.analyzer_name == 'CodeAnalyzer'
    assert len(result.violations) > 0
    complexity_violations = [v for v in result.violations if v.rule == 'high-complexity']
    assert len(complexity_violations) > 0

@pytest.mark.crust
@pytest.mark.asyncio
async def test_code_analyzer_suggests_type_hints():
    """Test that CodeAnalyzer suggests type hints."""
    analyzer = (CodeAnalyzer(),)
    code_without_types = '\ndef add_numbers(a, b):\n    return a + b\n\ndef process_data(data):\n    result = []\n    for item in data:\n        result.append(item * 2)\n    return result\n'
    result = await analyzer.analyze(Path('test.py'), code_without_types)
    type_suggestions = [s for s in result.suggestions if s.category == 'type-hints']
    assert len(type_suggestions) > 0

@pytest.mark.crust
def test_config_loading():
    """Test configuration loading and validation."""
    config = GuardianConfig()
    assert config.review.model == 'gpt-4'
    assert config.review.temperature == 0.3
    assert config.review.enable_golden_rules is True
    custom_config = GuardianConfig()
    custom_config.review.model = 'gpt-3.5-turbo'
    custom_config.review.max_tokens = 1000
    assert custom_config.review.model == 'gpt-3.5-turbo'
    assert custom_config.review.max_tokens == 1000

@pytest.mark.crust
def test_review_result_markdown_generation():
    """Test ReviewResult markdown generation."""
    from guardian_agent.core.interfaces import AnalysisResult, ReviewResult, Suggestion, Violation
    violation = Violation(type=ViolationType.CODE_SMELL, severity=Severity.WARNING, rule='long-function', message='Function is too long', file_path=Path('test.py'), line_number=10)
    suggestion = Suggestion(category='refactoring', message='Consider splitting into smaller functions', file_path=Path('test.py'), line_range=(10, 50), confidence=0.85)
    analysis_result = AnalysisResult(analyzer_name='TestAnalyzer', violations=[violation], suggestions=[suggestion])
    review_result = ReviewResult(file_path=Path('test.py'), analysis_results=[analysis_result], overall_score=75.0, summary='Code has some quality issues', violations_count={Severity.WARNING: 1, Severity.ERROR: 0, Severity.CRITICAL: 0, Severity.INFO: 0}, suggestions_count=1, auto_fixable_count=0, ai_confidence=0.9)
    markdown = review_result.to_markdown()
    assert '# Code Review: test.py' in markdown
    assert 'Overall Score' in markdown
    assert '75' in markdown
    assert 'Function is too long' in markdown
    assert 'Consider splitting' in markdown

@pytest.mark.crust
@pytest.mark.asyncio
async def test_code_analyzer_metrics():
    """Test that CodeAnalyzer collects metrics."""
    analyzer = (CodeAnalyzer(),)
    sample_code = '\nimport os\nimport sys\nfrom pathlib import Path\n\nclass MyClass:\n    def method1(self):\n        pass\n\n    def method2(self):\n        return 42\n\ndef standalone_function():\n    pass\n\nasync def async_function():\n    await some_operation()\n'
    result = await analyzer.analyze(Path('test.py'), sample_code)
    assert result.metrics['num_classes'] == 1
    assert result.metrics['num_functions'] == 3
    assert result.metrics['num_async_functions'] == 1
    assert result.metrics['num_imports'] == 3
    assert result.metrics['lines_of_code'] > 10

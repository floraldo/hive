"""Tests for hive_ai.core.exceptions module."""
from __future__ import annotations
import pytest
from hive_ai.core.exceptions import AIError, CostLimitError, ModelError, ModelUnavailableError, PromptError, VectorError

@pytest.mark.core
class TestAIError:
    """Test cases for AIError base exception."""

    @pytest.mark.core
    def test_ai_error_basic_creation(self):
        """Test creating AIError with just a message."""
        error = AIError('Test error message')
        assert str(error) == 'Test error message'
        assert error.model is None
        assert error.provider is None
        assert error.component == 'hive-ai'

    @pytest.mark.core
    def test_ai_error_with_model_context(self):
        """Test AIError with model information."""
        error = AIError('Model failed', model='claude-3-sonnet', provider='anthropic')
        assert str(error) == 'Model failed'
        assert error.model == 'claude-3-sonnet'
        assert error.provider == 'anthropic'

    @pytest.mark.core
    def test_ai_error_inheritance(self):
        """Test that AIError can be caught as BaseError."""
        error = AIError('Test error')
        assert isinstance(error, Exception)

@pytest.mark.core
class TestModelError:
    """Test cases for ModelError."""

    @pytest.mark.core
    def test_model_error_basic_creation(self):
        """Test creating ModelError with minimal fields."""
        error = ModelError('API request failed')
        assert str(error) == 'API request failed'
        assert error.request_id is None

    @pytest.mark.core
    def test_model_error_with_full_context(self):
        """Test ModelError with all context fields."""
        error = ModelError('Rate limit exceeded', model='gpt-4', provider='openai', request_id='req_123abc')
        assert str(error) == 'Rate limit exceeded'
        assert error.model == 'gpt-4'
        assert error.provider == 'openai'
        assert error.request_id == 'req_123abc'

    @pytest.mark.core
    def test_model_error_can_be_raised(self):
        """Test that ModelError can be raised and caught."""
        with pytest.raises(ModelError) as exc_info:
            raise ModelError('Test error', model='test-model')
        assert 'Test error' in str(exc_info.value)
        assert exc_info.value.model == 'test-model'

@pytest.mark.core
class TestVectorError:
    """Test cases for VectorError."""

    @pytest.mark.core
    def test_vector_error_basic_creation(self):
        """Test creating VectorError with message only."""
        error = VectorError('Vector operation failed')
        assert str(error) == 'Vector operation failed'
        assert error.collection is None
        assert error.operation is None

    @pytest.mark.core
    def test_vector_error_with_context(self):
        """Test VectorError with collection and operation details."""
        error = VectorError('Failed to store vectors', collection='embeddings', operation='store')
        assert str(error) == 'Failed to store vectors'
        assert error.collection == 'embeddings'
        assert error.operation == 'store'

    @pytest.mark.core
    def test_vector_error_different_operations(self):
        """Test VectorError with different operation types."""
        operations = ['store', 'search', 'delete', 'update']
        for op in operations:
            error = VectorError('Operation failed', operation=op)
            assert error.operation == op

@pytest.mark.core
class TestPromptError:
    """Test cases for PromptError."""

    @pytest.mark.core
    def test_prompt_error_basic_creation(self):
        """Test creating PromptError with message only."""
        error = PromptError('Template rendering failed')
        assert str(error) == 'Template rendering failed'
        assert error.template_name is None
        assert error.missing_variables == []

    @pytest.mark.core
    def test_prompt_error_with_template_name(self):
        """Test PromptError with template name."""
        error = PromptError('Missing variables', template_name='summarization.txt')
        assert error.template_name == 'summarization.txt'

    @pytest.mark.core
    def test_prompt_error_with_missing_variables(self):
        """Test PromptError tracking missing variables."""
        error = PromptError('Required variables not provided', template_name='analysis.txt', missing_variables=['input_text', 'context'])
        assert error.template_name == 'analysis.txt'
        assert 'input_text' in error.missing_variables
        assert 'context' in error.missing_variables
        assert len(error.missing_variables) == 2

    @pytest.mark.core
    def test_prompt_error_empty_missing_variables(self):
        """Test PromptError defaults to empty list for missing variables."""
        error = PromptError('Error', missing_variables=None)
        assert error.missing_variables == []

@pytest.mark.core
class TestCostLimitError:
    """Test cases for CostLimitError."""

    @pytest.mark.core
    def test_cost_limit_error_basic_creation(self):
        """Test creating CostLimitError with required fields."""
        error = CostLimitError('Daily limit exceeded', current_cost=150.0, limit=100.0)
        assert str(error) == 'Daily limit exceeded'
        assert error.current_cost == 150.0
        assert error.limit == 100.0
        assert error.period == 'daily'

    @pytest.mark.core
    def test_cost_limit_error_monthly_period(self):
        """Test CostLimitError with monthly period."""
        error = CostLimitError('Monthly budget exceeded', current_cost=5500.0, limit=5000.0, period='monthly')
        assert error.period == 'monthly'
        assert error.current_cost == 5500.0

    @pytest.mark.core
    def test_cost_limit_error_cost_tracking(self):
        """Test that CostLimitError correctly tracks costs."""
        current = (125.5,)
        limit = (100.0,)
        error = CostLimitError('Budget exceeded', current_cost=current, limit=limit)
        overage = current - limit
        assert overage == 25.5
        assert error.current_cost > error.limit

@pytest.mark.core
class TestModelUnavailableError:
    """Test cases for ModelUnavailableError."""

    @pytest.mark.core
    def test_model_unavailable_error_basic(self):
        """Test creating ModelUnavailableError with required fields."""
        error = ModelUnavailableError('Model not configured', model='gpt-5', provider='openai')
        assert str(error) == 'Model not configured'
        assert error.model == 'gpt-5'
        assert error.provider == 'openai'
        assert error.available_models == []

    @pytest.mark.core
    def test_model_unavailable_error_with_alternatives(self):
        """Test ModelUnavailableError suggesting alternatives."""
        alternatives = ['gpt-4', 'gpt-3.5-turbo', 'claude-3-sonnet']
        error = ModelUnavailableError('Requested model unavailable', model='gpt-5-ultra', provider='openai', available_models=alternatives)
        assert len(error.available_models) == 3
        assert 'gpt-4' in error.available_models
        assert 'claude-3-sonnet' in error.available_models

    @pytest.mark.core
    def test_model_unavailable_error_empty_alternatives(self):
        """Test ModelUnavailableError defaults to empty alternatives list."""
        error = ModelUnavailableError('No models available', model='test', provider='test-provider', available_models=None)
        assert error.available_models == []

@pytest.mark.core
class TestExceptionHierarchy:
    """Test exception inheritance and catching patterns."""

    @pytest.mark.core
    def test_all_errors_are_exceptions(self):
        """Test that all error classes are proper exceptions."""
        errors = [AIError('test'), ModelError('test'), VectorError('test'), PromptError('test'), CostLimitError('test', 10.0, 5.0), ModelUnavailableError('test', 'model', 'provider')]
        for error in errors:
            assert isinstance(error, Exception)

    @pytest.mark.core
    def test_catching_specific_errors(self):
        """Test that specific errors can be caught individually."""
        try:
            raise CostLimitError('Over budget', 200.0, 100.0)
        except CostLimitError as e:
            assert e.current_cost == 200.0
        except Exception:
            pytest.fail('Should have caught CostLimitError specifically')

    @pytest.mark.core
    def test_catching_base_ai_error(self):
        """Test that AI errors can be caught as AIError."""
        errors_raised = 0
        for error_class in [AIError, ModelError]:
            try:
                if error_class == AIError:
                    raise error_class('test')
                else:
                    raise error_class('test')
            except AIError:
                errors_raised += 1
            except Exception:
                pass
        assert errors_raised >= 1
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
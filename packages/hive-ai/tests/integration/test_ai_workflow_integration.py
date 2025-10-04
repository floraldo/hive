"""
Integration tests for complete AI workflows.

Tests end-to-end scenarios across multiple components.
"""
import asyncio
from unittest.mock import Mock

import pytest

from hive_ai.agents.agent import AgentConfig, BaseAgent
from hive_ai.agents.workflow import WorkflowConfig, WorkflowOrchestrator
from hive_ai.core.config import AIConfig, VectorConfig
from hive_ai.models.client import ModelClient
from hive_ai.models.registry import ModelRegistry
from hive_ai.prompts.template import PromptMetadata, PromptTemplate, PromptVariable
from hive_ai.vector.embedding import EmbeddingManager


@pytest.mark.core
class TestAIWorkflowIntegration:
    """Integration tests for complete AI workflows."""

    @pytest.fixture
    def ai_config(self):
        """Complete AI configuration for testing."""
        return AIConfig()

    @pytest.fixture
    def vector_config(self):
        """Vector configuration for testing."""
        return VectorConfig(provider='chroma', collection_name='test_collection', dimension=384)

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_model_vector_integration(self, ai_config, vector_config):
        """Test integration between model client and vector store."""
        ModelClient(ai_config)
        embedding_manager = EmbeddingManager(ai_config)
        texts = ['This is the first document for testing.', 'Here is another document with different content.', 'A third document to complete our test set.']
        embedding_results = await embedding_manager.generate_batch_embeddings_async(texts)
        assert len(embedding_results) == len(texts)
        for result in embedding_results:
            assert len(result.vector) > 0
            assert result.text in texts

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_prompt_agent_integration(self, ai_config):
        """Test integration between prompt templates and agents."""
        template = PromptTemplate(template='Analyze this data: {{ data }} and provide insights about {{ focus }}', variables=[PromptVariable(name='data', type='str', required=True), PromptVariable(name='focus', type='str', required=True)], metadata=PromptMetadata(name='analysis_prompt', description='Data analysis template'))

        @pytest.mark.core
        class TestAnalysisAgent(BaseAgent):

            async def _initialize_impl_async(self):
                self.prompt_template = template

            async def _execute_main_logic_async(self, input_data=None):
                rendered = self.prompt_template.render(data=input_data.get('data', 'test data'), focus=input_data.get('focus', 'patterns'))
                return f'Analysis based on: {rendered}'
        agent_config = AgentConfig(name='analysis_agent', description='Agent for data analysis', model='test-model')
        mock_client = (Mock(),)
        agent = TestAnalysisAgent(agent_config, mock_client)
        await agent.initialize_async()
        result = await agent.run_async({'data': 'sales figures for Q1', 'focus': 'growth trends'})
        assert 'sales figures for Q1' in result
        assert 'growth trends' in result

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_workflow_orchestration_integration(self, ai_config):
        """Test integration of workflow orchestration with multiple agents."""
        workflow_config = WorkflowConfig(name='data_processing_workflow', description='Complete data processing workflow')
        mock_client = (Mock(),)
        workflow = WorkflowOrchestrator(workflow_config, mock_client)

        class DataCollectorAgent(BaseAgent):

            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                return 'collected_data'

        class DataAnalyzerAgent(BaseAgent):

            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                return f'analyzed_{input_data}'

        class ReportGeneratorAgent(BaseAgent):

            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                return f'report_for_{input_data}'
        collector_config = AgentConfig(name='collector', description='Data collector', model='test')
        analyzer_config = AgentConfig(name='analyzer', description='Data analyzer', model='test')
        generator_config = AgentConfig(name='generator', description='Report generator', model='test')
        collector = DataCollectorAgent(collector_config, mock_client)
        analyzer = DataAnalyzerAgent(analyzer_config, mock_client)
        generator = ReportGeneratorAgent(generator_config, mock_client)
        collector_id = (workflow.add_agent(collector),)
        analyzer_id = (workflow.add_agent(analyzer),)
        generator_id = workflow.add_agent(generator)
        assert len(workflow.agents) == 3
        assert collector_id in workflow.agents
        assert analyzer_id in workflow.agents
        assert generator_id in workflow.agents

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_end_to_end_ai_pipeline(self, ai_config):
        """Test complete end-to-end AI pipeline."""
        pipeline_steps = ['prompt_creation', 'model_interaction', 'vector_storage', 'agent_processing', 'result_aggregation']
        results = {}
        for step in pipeline_steps:
            results[step] = f'completed_{step}'
        assert len(results) == len(pipeline_steps)
        assert all(step in results for step in pipeline_steps)

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, ai_config):
        """Test error handling across integrated components."""
        mock_client = Mock()

        class FailingAgent(BaseAgent):

            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                raise RuntimeError('Simulated agent failure')
        agent_config = AgentConfig(name='failing_agent', description='Test failure', model='test')
        agent = FailingAgent(agent_config, mock_client)
        await agent.initialize_async()
        with pytest.raises(RuntimeError):
            await agent.run_async('test input')

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_performance_integration(self, ai_config):
        """Test performance characteristics of integrated components."""
        import time
        start_time = time.time()
        tasks = []
        for _i in range(5):
            task = asyncio.create_task(asyncio.sleep(0.1))
            tasks.append(task)
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        assert total_time < 1.0

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_configuration_integration(self, ai_config):
        """Test that configuration propagates correctly across components."""
        model_client = (ModelClient(ai_config),)
        registry = ModelRegistry(ai_config)
        assert model_client.config == ai_config
        assert registry.config == ai_config
        original_default = ai_config.default_model
        ai_config.default_model = 'updated-model'
        assert model_client.config.default_model == 'updated-model'
        assert registry.config.default_model == 'updated-model'
        ai_config.default_model = original_default

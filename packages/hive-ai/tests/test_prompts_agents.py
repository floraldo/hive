"""
Comprehensive tests for hive-ai prompt engineering and agentic workflow components.

Tests PromptTemplate, PromptOptimizer, PromptRegistry, BaseAgent, and WorkflowOrchestrator
with property-based testing.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hive_ai.agents.agent import AgentConfig, AgentState, BaseAgent, SimpleTaskAgent
from hive_ai.agents.task import PromptTask, TaskConfig
from hive_ai.agents.workflow import ExecutionStrategy, WorkflowConfig, WorkflowOrchestrator, WorkflowStatus
from hive_ai.core.exceptions import AIError, PromptError
from hive_ai.prompts.optimizer import OptimizationResult, OptimizationStrategy, PromptOptimizer
from hive_ai.prompts.registry import PromptRegistry
from hive_ai.prompts.template import PromptChain, PromptMetadata, PromptTemplate, PromptVariable


# Prompt generation strategies for property-based testing
@st.composite
def prompt_template_data(draw):
    """Generate valid prompt template data."""
    variable_names = draw(
        st.lists(
            st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
            ),
            min_size=0,
            max_size=5,
            unique=True,
        )
    )

    template_parts = ["This is a test prompt"]
    for var_name in variable_names:
        template_parts.append(f"{{ {var_name} }}")
        template_parts.append("with some text")

    return {"template": " ".join(template_parts), "variables": variable_names}


@st.composite
def agent_config_data(draw):
    """Generate valid agent configuration data."""
    return {
        "name": draw(st.text(min_size=1, max_size=50)),
        "description": draw(st.text(min_size=1, max_size=200)),
        "model": draw(st.sampled_from(["claude-3-sonnet", "gpt-4", "test-model"])),
        "temperature": draw(st.floats(min_value=0.0, max_value=2.0)),
        "max_tokens": draw(st.integers(min_value=100, max_value=8192)),
        "max_iterations": draw(st.integers(min_value=1, max_value=50)),
    }


class TestPromptTemplate:
    """Test PromptTemplate functionality."""

    def test_template_creation_simple(self):
        """Test simple template creation."""
        template = PromptTemplate(
            template="Hello {{ name }}!", variables=[PromptVariable(name="name", type="str", required=True)]
        )

        assert template.template == "Hello {{ name }}!"
        assert len(template.variables) == 1
        assert "name" in template.variables

    def test_template_render_success(self):
        """Test successful template rendering."""
        template = PromptTemplate(
            template="Hello {{ name }}, you are {{ age }} years old.",
            variables=[
                PromptVariable(name="name", type="str", required=True),
                PromptVariable(name="age", type="int", required=True),
            ],
        )

        result = template.render(name="Alice", age=30)
        assert result == "Hello Alice, you are 30 years old."

    def test_template_render_missing_variable(self):
        """Test template rendering with missing variable."""
        template = PromptTemplate(
            template="Hello {{ name }}!", variables=[PromptVariable(name="name", type="str", required=True)]
        )

        with pytest.raises(PromptError, match="missing required variables"):
            template.render()

    def test_template_variable_validation(self):
        """Test variable type validation."""
        template = PromptTemplate(
            template="Number: {{ num }}", variables=[PromptVariable(name="num", type="int", required=True)]
        )

        # Valid integer
        assert template.validate_variables(num=42) is True

        # Invalid type
        assert template.validate_variables(num="not a number") is False

    def test_template_default_values(self):
        """Test template variables with default values."""
        template = PromptTemplate(
            template="Hello {{ name }}, welcome to {{ place }}!",
            variables=[
                PromptVariable(name="name", type="str", required=True),
                PromptVariable(name="place", type="str", required=False, default="our site"),
            ],
        )

        # With both variables
        result1 = template.render(name="Bob", place="the conference")
        assert result1 == "Hello Bob, welcome to the conference!"

        # With default value
        result2 = template.render(name="Bob")
        assert result2 == "Hello Bob, welcome to our site!"

    def test_template_auto_variable_extraction(self):
        """Test automatic variable extraction from template."""
        template = PromptTemplate(template="Process {{ input_data }} and return {{ output_format }}")

        # Should automatically extract variables
        assert len(template.variables) == 2
        assert "input_data" in template.variables
        assert "output_format" in template.variables

    def test_template_cloning(self):
        """Test template cloning."""
        original = PromptTemplate(
            template="Original {{ var }}",
            variables=[PromptVariable(name="var", type="str")],
            metadata=PromptMetadata(name="original", description="test"),
        )

        clone = original.clone("cloned")

        assert clone.template == original.template
        assert clone.metadata.name == "cloned"
        assert len(clone.variables) == len(original.variables)

    def test_template_serialization(self):
        """Test template serialization and deserialization."""
        template = PromptTemplate(
            template="Test {{ var }}",
            variables=[PromptVariable(name="var", type="str", description="test var")],
            metadata=PromptMetadata(name="test", description="test template"),
        )

        # Serialize
        data = template.to_dict()
        assert "template" in data
        assert "variables" in data
        assert "metadata" in data

        # Deserialize
        restored = PromptTemplate.from_dict(data)
        assert restored.template == template.template
        assert restored.metadata.name == template.metadata.name

    @given(prompt_template_data())
    def test_template_property_based(self, template_data):
        """Property-based test for template creation and rendering."""
        variables = [
            PromptVariable(name=var_name, type="str", required=True, default="default")
            for var_name in template_data["variables"]
        ]

        try:
            template = PromptTemplate(template=template_data["template"], variables=variables)

            # Should be able to validate
            variable_values = dict.fromkeys(template_data["variables"], "test_value")
            is_valid = template.validate_variables(**variable_values)
            assert isinstance(is_valid, bool)

            # Should be able to render with defaults
            if is_valid:
                result = template.render(**variable_values)
                assert isinstance(result, str)

        except (PromptError, ValueError):
            # Some combinations might be invalid, that's expected
            pass


class TestPromptChain:
    """Test PromptChain functionality."""

    def test_chain_creation(self):
        """Test prompt chain creation."""
        template1 = PromptTemplate("Step 1: {{ input }}")
        template2 = PromptTemplate("Step 2: Process {{ step_1_output }}")

        chain = PromptChain([template1, template2], name="test_chain")

        assert len(chain.templates) == 2
        assert chain.name == "test_chain"

    def test_chain_render_all(self):
        """Test rendering all templates in chain."""
        template1 = PromptTemplate("First: {{ data }}")
        template2 = PromptTemplate("Second: {{ data }}")

        chain = PromptChain([template1, template2])
        results = chain.render_all(data="test")

        assert len(results) == 2
        assert results[0] == "First: test"
        assert results[1] == "Second: test"

    def test_chain_required_variables(self):
        """Test getting required variables from chain."""
        template1 = PromptTemplate("Need {{ var1 }}")
        template2 = PromptTemplate("Need {{ var2 }}")

        chain = PromptChain([template1, template2])
        required = chain.get_required_variables()

        assert "var1" in required
        assert "var2" in required

    def test_chain_manipulation(self):
        """Test adding/removing templates from chain."""
        template1 = PromptTemplate("Template 1")
        template2 = PromptTemplate("Template 2")
        template3 = PromptTemplate("Template 3")

        chain = PromptChain([template1])

        # Add template
        chain.add_template(template2)
        assert len(chain) == 2

        # Insert template
        chain.insert_template(1, template3)
        assert len(chain) == 3
        assert chain[1] == template3

        # Remove template
        removed = chain.remove_template(1)
        assert removed == template3
        assert len(chain) == 2


class TestPromptOptimizer:
    """Test PromptOptimizer functionality."""

    @pytest.fixture
    def mock_model_client(self):
        """Mock ModelClient for testing."""
        client = Mock()
        client.generate_async = AsyncMock(
            return_value=Mock(
                content="Optimized prompt: The improved version\n\nImprovements:\n1. Better clarity\n2. More specific\n\nOptimized prompt:"
            )
        )
        return client

    @pytest.fixture
    def optimizer(self, mock_model_client):
        """PromptOptimizer instance for testing."""
        return PromptOptimizer(mock_model_client)

    @pytest.mark.asyncio
    async def test_optimize_prompt_clarity_async(self, optimizer):
        """Test prompt optimization for clarity."""
        original_prompt = "Make it better"

        result = await optimizer.optimize_prompt_async(original_prompt, strategy=OptimizationStrategy.CLARITY)

        assert isinstance(result, OptimizationResult)
        assert result.original_prompt == original_prompt
        assert result.strategy == OptimizationStrategy.CLARITY
        assert len(result.optimized_prompt) > 0

    @pytest.mark.asyncio
    async def test_optimize_prompt_brevity_async(self, optimizer):
        """Test prompt optimization for brevity."""
        original_prompt = "This is a very long and verbose prompt that could be made much shorter"

        result = await optimizer.optimize_prompt_async(original_prompt, strategy=OptimizationStrategy.BREVITY)

        assert result.strategy == OptimizationStrategy.BREVITY
        # For brevity, token change should ideally be negative (fewer tokens)

    @pytest.mark.asyncio
    async def test_batch_optimize_async(self, optimizer):
        """Test batch prompt optimization."""
        prompts = ["Prompt one", "Prompt two", "Prompt three"]

        results = await optimizer.batch_optimize_async(prompts)

        assert len(results) <= len(prompts)  # Some might fail
        for result in results:
            assert isinstance(result, OptimizationResult)

    def test_optimization_stats(self, optimizer):
        """Test optimization statistics."""
        stats = optimizer.get_optimization_stats()

        assert "supported_strategies" in stats
        assert len(stats["supported_strategies"]) == len(OptimizationStrategy)


class TestPromptRegistry:
    """Test PromptRegistry functionality."""

    @pytest.fixture
    def temp_registry_dir(self):
        """Temporary directory for registry testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def registry(self, temp_registry_dir):
        """PromptRegistry instance for testing."""
        return PromptRegistry(storage_path=temp_registry_dir, cache_enabled=False)

    @pytest.mark.asyncio
    async def test_register_template_async(self, registry):
        """Test template registration."""
        template = PromptTemplate(
            template="Test {{ var }}", metadata=PromptMetadata(name="test_template", description="A test template")
        )

        template_name = await registry.register_template_async(template)
        assert template_name == "test_template"

        # Should be able to retrieve
        retrieved = await registry.get_template_async("test_template")
        assert retrieved.template == template.template

    @pytest.mark.asyncio
    async def test_register_template_overwrite_async(self, registry):
        """Test template registration with overwrite."""
        template1 = PromptTemplate(template="Version 1", metadata=PromptMetadata(name="test", description="v1"))

        template2 = PromptTemplate(template="Version 2", metadata=PromptMetadata(name="test", description="v2"))

        # Register first template
        await registry.register_template_async(template1)

        # Should fail without overwrite
        with pytest.raises(PromptError, match="already exists"):
            await registry.register_template_async(template2, overwrite=False)

        # Should succeed with overwrite
        await registry.register_template_async(template2, overwrite=True)

        retrieved = await registry.get_template_async("test")
        assert retrieved.template == "Version 2"

    def test_list_templates_filtering(self, registry):
        """Test template listing with filters."""
        # List all templates (should be empty initially)
        all_templates = registry.list_templates()
        assert len(all_templates) == 0

        # Test search functionality (even with empty registry)
        search_results = registry.list_templates(search="nonexistent")
        assert len(search_results) == 0

    @pytest.mark.asyncio
    async def test_clone_template_async(self, registry):
        """Test template cloning."""
        original = PromptTemplate(
            template="Original {{ var }}", metadata=PromptMetadata(name="original", description="original template")
        )

        await registry.register_template_async(original)

        cloned_name = await registry.clone_template_async(
            "original", "cloned", modifications={"template": "Cloned {{ var }}"}
        )

        assert cloned_name == "cloned"

        cloned_template = await registry.get_template_async("cloned")
        assert cloned_template.template == "Cloned {{ var }}"

    @pytest.mark.asyncio
    async def test_export_import_templates_async(self, registry, temp_registry_dir):
        """Test template export and import."""
        # Register a template
        template = PromptTemplate(
            template="Export test {{ var }}", metadata=PromptMetadata(name="export_test", description="for export")
        )
        await registry.register_template_async(template)

        # Export
        export_path = Path(temp_registry_dir) / "exported.json"
        export_stats = await registry.export_templates_async(str(export_path))

        assert export_stats["exported_count"] == 1
        assert export_path.exists()

        # Create new registry and import
        new_registry = PromptRegistry(storage_path=temp_registry_dir + "_new", cache_enabled=False)
        import_stats = await new_registry.import_templates_async(str(export_path))

        assert import_stats["imported_count"] == 1
        assert import_stats["failed_count"] == 0

        # Verify imported template
        imported = await new_registry.get_template_async("export_test")
        assert imported.template == template.template

    @pytest.mark.asyncio
    async def test_registry_validation_async(self, registry):
        """Test registry validation."""
        validation_results = await registry.validate_registry_async()

        assert "valid_templates" in validation_results
        assert "invalid_templates" in validation_results
        assert "success_rate" in validation_results


class TestBaseAgent:
    """Test BaseAgent functionality."""

    @pytest.fixture
    def agent_config(self):
        """Agent configuration for testing."""
        return AgentConfig(name="test_agent", description="A test agent", model="test-model")

    @pytest.fixture
    def mock_model_client(self):
        """Mock ModelClient for testing."""
        client = Mock()
        client.generate_async = AsyncMock(return_value=Mock(content="Agent response", tokens_used=50, cost=0.001))
        return client

    def test_agent_creation(self, agent_config, mock_model_client):
        """Test agent creation."""

        class TestAgent(BaseAgent):
            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                return "test result"

        agent = TestAgent(agent_config, mock_model_client)

        assert agent.config == agent_config
        assert agent.state == AgentState.CREATED
        assert agent.memory is not None  # Memory enabled by default
        assert len(agent.tools) >= 3  # Default tools

    @pytest.mark.asyncio
    async def test_agent_initialization_async(self, agent_config, mock_model_client):
        """Test agent initialization."""

        class TestAgent(BaseAgent):
            async def _initialize_impl_async(self):
                await self._remember_tool("init_data", "initialized", "long_term")

            async def _execute_main_logic_async(self, input_data=None):
                return "test result"

        agent = TestAgent(agent_config, mock_model_client)
        await agent.initialize_async()

        assert agent.state == AgentState.INITIALIZED
        # Check memory was used during initialization
        init_data = await agent._recall_tool("init_data")
        assert init_data == "initialized"

    @pytest.mark.asyncio
    async def test_agent_execution_async(self, agent_config, mock_model_client):
        """Test agent execution."""

        class TestAgent(BaseAgent):
            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                return f"processed: {input_data}"

        agent = TestAgent(agent_config, mock_model_client)
        await agent.initialize_async()

        result = await agent.run_async("test input")

        assert result == "processed: test input"
        assert agent.state == AgentState.COMPLETED
        assert len(agent.results) == 1

    @pytest.mark.asyncio
    async def test_agent_tools_async(self, agent_config, mock_model_client):
        """Test agent tool usage."""

        class TestAgent(BaseAgent):
            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                # Use thinking tool
                thoughts = await self.call_tool_async("think", prompt="What should I do?")
                return thoughts

        agent = TestAgent(agent_config, mock_model_client)
        await agent.initialize_async()

        result = await agent.run_async()

        assert isinstance(result, str)
        # Should have episodic memory from thinking
        assert len(agent.memory.episodic) > 0

    @pytest.mark.asyncio
    async def test_agent_messaging_async(self, agent_config, mock_model_client):
        """Test agent messaging system."""

        class TestAgent(BaseAgent):
            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                return "done"

        agent = TestAgent(agent_config, mock_model_client)
        await agent.initialize_async()

        # Send a message
        message_id = await agent.send_message_async(recipient="other_agent", content="Hello other agent")

        assert message_id is not None
        assert len(agent.message_queue) == 1
        assert len(agent.memory.conversation) == 1

    def test_agent_status(self, agent_config, mock_model_client):
        """Test agent status reporting."""

        class TestAgent(BaseAgent):
            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                return "done"

        agent = TestAgent(agent_config, mock_model_client)
        status = agent.get_status()

        assert status["name"] == "test_agent"
        assert status["state"] == AgentState.CREATED.value
        assert status["tools_available"] >= 3

    @given(agent_config_data())
    def test_agent_configuration_property(self, config_data):
        """Property-based test for agent configuration."""
        try:
            config = AgentConfig(**config_data)
            mock_client = Mock()

            class TestAgent(BaseAgent):
                async def _initialize_impl_async(self):
                    pass

                async def _execute_main_logic_async(self, input_data=None):
                    return "done"

            agent = TestAgent(config, mock_client)

            assert agent.config.name == config_data["name"]
            assert agent.config.model == config_data["model"]
            assert 0.0 <= agent.config.temperature <= 2.0
            assert agent.config.max_tokens >= 100

        except (ValueError, TypeError):
            # Some configurations might be invalid, that's expected
            pass


class TestSimpleTaskAgent:
    """Test SimpleTaskAgent functionality."""

    @pytest.fixture
    def agent_config(self):
        """Agent configuration for testing."""
        return AgentConfig(name="task_agent", description="Simple task agent", model="test-model")

    @pytest.fixture
    def mock_model_client(self):
        """Mock ModelClient for testing."""
        client = Mock()
        client.generate_async = AsyncMock(
            return_value=Mock(content="Task completed successfully", tokens_used=25, cost=0.0005)
        )
        return client

    @pytest.mark.asyncio
    async def test_simple_task_execution_async(self, agent_config, mock_model_client):
        """Test simple task agent execution."""
        task_prompt = "Summarize the following text: {{ input }}"

        agent = SimpleTaskAgent(task_prompt, agent_config, mock_model_client)
        await agent.initialize_async()

        result = await agent.run_async("This is test input text to summarize.")

        assert result == "Task completed successfully"
        mock_model_client.generate_async.assert_called_once()

        # Check that prompt was stored in memory
        stored_prompt = await agent._recall_tool("task_prompt", "long_term")
        assert stored_prompt == task_prompt


class TestWorkflowOrchestrator:
    """Test WorkflowOrchestrator functionality."""

    @pytest.fixture
    def workflow_config(self):
        """Workflow configuration for testing."""
        return WorkflowConfig(
            name="test_workflow",
            description="A test workflow",
            execution_strategy=ExecutionStrategy.SEQUENTIAL,
            max_concurrent_steps=2,
        )

    @pytest.fixture
    def mock_model_client(self):
        """Mock ModelClient for testing."""
        client = Mock()
        client.generate_async = AsyncMock(
            return_value=Mock(content="Workflow step completed", tokens_used=30, cost=0.0006)
        )
        return client

    def test_workflow_creation(self, workflow_config, mock_model_client):
        """Test workflow orchestrator creation."""
        workflow = WorkflowOrchestrator(workflow_config, mock_model_client)

        assert workflow.config == workflow_config
        assert workflow.status == WorkflowStatus.CREATED
        assert len(workflow.agents) == 0
        assert len(workflow.steps) == 0

    @pytest.mark.asyncio
    async def test_workflow_with_simple_agent_async(self, workflow_config, mock_model_client):
        """Test workflow with a simple agent."""
        workflow = WorkflowOrchestrator(workflow_config, mock_model_client)

        # Create and add agent
        agent_config = AgentConfig(name="workflow_agent", description="Agent for workflow", model="test-model")

        class TestAgent(BaseAgent):
            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                return "workflow step completed"

        agent = TestAgent(agent_config, mock_model_client)
        agent_id = workflow.add_agent(agent)

        # Create and add task
        task_config = TaskConfig(name="test_task", description="A test task")

        task = PromptTask(task_config, "Complete this task: {{ input }}")
        task_id = workflow.add_task(task)

        # Create workflow step
        step_id = workflow.create_step(name="test_step", agent_id=agent_id, task_id=task_id)

        # Initialize and execute workflow
        await workflow.initialize_async()
        assert workflow.status == WorkflowStatus.INITIALIZED

        # Note: Full execution would require more complex mocking
        # This tests the workflow structure

    def test_workflow_step_creation(self, workflow_config, mock_model_client):
        """Test workflow step creation and management."""
        workflow = WorkflowOrchestrator(workflow_config, mock_model_client)

        # Create agent
        agent_config = AgentConfig(name="test", description="test", model="test")

        class TestAgent(BaseAgent):
            async def _initialize_impl_async(self):
                pass

            async def _execute_main_logic_async(self, input_data=None):
                return "done"

        agent = TestAgent(agent_config, mock_model_client)
        agent_id = workflow.add_agent(agent)

        # Create task
        task_config = TaskConfig(name="task", description="test task")
        task = PromptTask(task_config, "Test prompt")
        task_id = workflow.add_task(task)

        # Create step
        step_id = workflow.create_step(
            name="test_step", agent_id=agent_id, task_id=task_id, dependencies=[], timeout_seconds=60
        )

        assert step_id in workflow.steps
        step = workflow.steps[step_id]
        assert step.name == "test_step"
        assert step.agent_id == agent_id
        assert step.task_id == task_id

    def test_workflow_status_reporting(self, workflow_config, mock_model_client):
        """Test workflow status reporting."""
        workflow = WorkflowOrchestrator(workflow_config, mock_model_client)

        status = workflow.get_status()

        assert status["workflow_id"] == workflow.id
        assert status["name"] == "test_workflow"
        assert status["status"] == WorkflowStatus.CREATED.value
        assert status["total_steps"] == 0
        assert status["agents"] == 0


class TestIntegrationScenarios:
    """Integration tests combining multiple components."""

    @pytest.mark.asyncio
    async def test_prompt_agent_integration_async(self):
        """Test integration between prompts and agents."""
        # Create a prompt template
        template = PromptTemplate(
            template="Analyze this data: {{ data }}\nProvide insights about {{ focus_area }}",
            variables=[
                PromptVariable(name="data", type="str", required=True),
                PromptVariable(name="focus_area", type="str", required=True),
            ],
        )

        # Create agent configuration
        agent_config = AgentConfig(name="analysis_agent", description="Data analysis agent", model="test-model")

        # Mock model client
        mock_client = Mock()
        mock_client.generate_async = AsyncMock(
            return_value=Mock(
                content="Analysis complete: The data shows clear trends in the focus area.", tokens_used=45, cost=0.0009
            )
        )

        # Create simple task agent with rendered prompt
        rendered_prompt = template.render(data="sample dataset with numbers", focus_area="performance trends")

        agent = SimpleTaskAgent(rendered_prompt, agent_config, mock_client)
        await agent.initialize_async()

        result = await agent.run_async()

        assert "Analysis complete" in result
        mock_client.generate_async.assert_called_once()

    @settings(max_examples=5, deadline=10000)
    @given(st.lists(st.text(min_size=5, max_size=100), min_size=1, max_size=3))
    @pytest.mark.asyncio
    async def test_multi_step_workflow_property_async(self, step_descriptions):
        """Property-based test for multi-step workflows."""
        config = WorkflowConfig(
            name="property_test_workflow",
            description="Property-based workflow test",
            execution_strategy=ExecutionStrategy.SEQUENTIAL,
        )

        mock_client = Mock()
        mock_client.generate_async = AsyncMock(return_value=Mock(content="Step completed", tokens_used=20, cost=0.0004))

        workflow = WorkflowOrchestrator(config, mock_client)

        try:
            # Create agents and tasks for each step
            for i, description in enumerate(step_descriptions):
                # Create agent
                agent_config = AgentConfig(name=f"agent_{i}", description=f"Agent for step {i}", model="test-model")

                class PropertyTestAgent(BaseAgent):
                    async def _initialize_impl_async(self):
                        pass

                    async def _execute_main_logic_async(self, input_data=None):
                        return f"completed step {i}"

                agent = PropertyTestAgent(agent_config, mock_client)
                agent_id = workflow.add_agent(agent)

                # Create task
                task_config = TaskConfig(name=f"task_{i}", description=description)
                task = PromptTask(task_config, f"Execute: {description}")
                task_id = workflow.add_task(task)

                # Create step with dependencies (sequential)
                dependencies = [f"step_{i - 1}"] if i > 0 else []
                step_id = workflow.create_step(
                    name=f"step_{i}", agent_id=agent_id, task_id=task_id, dependencies=dependencies
                )

            # Workflow should initialize successfully
            await workflow.initialize_async()
            assert workflow.status == WorkflowStatus.INITIALIZED

            # Should have correct number of components
            assert len(workflow.agents) == len(step_descriptions)
            assert len(workflow.tasks) == len(step_descriptions)
            assert len(workflow.steps) == len(step_descriptions)

        except (AIError, ValueError):
            # Some combinations might be invalid, that's expected
            pass

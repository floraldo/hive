"""Tests for hive_ai.agents.agent module."""
from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from hive_agent_runtime.agent import (
    AgentConfig,
    AgentMemory,
    AgentMessage,
    AgentState,
    AgentTool,
    BaseAgent,
    SimpleTaskAgent,
)

from hive_ai.core.exceptions import AIError


@pytest.mark.core
class TestAgentMessage:
    """Test cases for AgentMessage dataclass."""

    @pytest.mark.core
    def test_agent_message_creation_basic(self):
        """Test creating AgentMessage with required fields."""
        timestamp = (datetime.utcnow(),)
        message = AgentMessage(id='msg-123', sender='agent-1', recipient='agent-2', content='Hello', message_type='greeting', timestamp=timestamp)
        assert message.id == 'msg-123'
        assert message.sender == 'agent-1'
        assert message.recipient == 'agent-2'
        assert message.content == 'Hello'
        assert message.message_type == 'greeting'
        assert message.timestamp == timestamp
        assert message.metadata == {}

    @pytest.mark.core
    def test_agent_message_with_metadata(self):
        """Test creating AgentMessage with metadata."""
        metadata = {'priority': 'high', 'tags': ['urgent', 'action-required']}
        message = AgentMessage(id='msg-456', sender='agent-1', recipient='agent-2', content='Critical update', message_type='alert', timestamp=datetime.utcnow(), metadata=metadata)
        assert message.metadata == metadata
        assert message.metadata['priority'] == 'high'

@pytest.mark.core
class TestAgentTool:
    """Test cases for AgentTool dataclass."""

    @pytest.mark.core
    def test_agent_tool_creation_basic(self):
        """Test creating AgentTool with minimal fields."""

        def dummy_function():
            return 'result'
        tool = AgentTool(name='test_tool', description='A test tool', function=dummy_function)
        assert tool.name == 'test_tool'
        assert tool.description == 'A test tool'
        assert tool.function == dummy_function
        assert tool.parameters == {}
        assert tool.enabled is True

    @pytest.mark.core
    def test_agent_tool_with_parameters(self):
        """Test creating AgentTool with parameters."""

        def calc_function(x: int, y: int):
            return x + y
        parameters = {'x': {'type': 'int', 'required': True}, 'y': {'type': 'int', 'required': True}}
        tool = AgentTool(name='calculator', description='Adds two numbers', function=calc_function, parameters=parameters, enabled=False)
        assert tool.parameters == parameters
        assert tool.enabled is False

@pytest.mark.core
class TestAgentMemory:
    """Test cases for AgentMemory dataclass."""

    @pytest.mark.core
    def test_agent_memory_creation_empty(self):
        """Test creating empty AgentMemory."""
        memory = AgentMemory()
        assert memory.short_term == {}
        assert memory.long_term == {}
        assert memory.episodic == []
        assert memory.conversation == []

    @pytest.mark.core
    def test_agent_memory_with_data(self):
        """Test creating AgentMemory with data."""
        short_term = ({'current_task': 'analysis'},)
        long_term = ({'user_preference': 'detailed'},)
        episodic = [{'event': 'task_started', 'time': '2025-01-15T10:00:00'}]
        conversation = [AgentMessage(id='msg-1', sender='agent-1', recipient='agent-2', content='Hello', message_type='greeting', timestamp=datetime.utcnow())]
        memory = AgentMemory(short_term=short_term, long_term=long_term, episodic=episodic, conversation=conversation)
        assert memory.short_term == short_term
        assert memory.long_term == long_term
        assert memory.episodic == episodic
        assert len(memory.conversation) == 1

@pytest.mark.core
class TestAgentConfig:
    """Test cases for AgentConfig dataclass."""

    @pytest.mark.core
    def test_agent_config_creation_minimal(self):
        """Test creating AgentConfig with required fields only."""
        config = AgentConfig(name='test_agent', description='Test agent description', model='claude-3-sonnet')
        assert config.name == 'test_agent'
        assert config.description == 'Test agent description'
        assert config.model == 'claude-3-sonnet'
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.max_iterations == 10
        assert config.timeout_seconds == 300
        assert config.memory_enabled is True
        assert config.tools_enabled is True
        assert config.observability_enabled is True
        assert config.metadata == {}

    @pytest.mark.core
    def test_agent_config_with_all_fields(self):
        """Test creating AgentConfig with all fields specified."""
        metadata = {'version': '1.0', 'team': 'ai-agents'}
        config = AgentConfig(name='advanced_agent', description='Advanced agent', model='claude-3-opus', temperature=0.5, max_tokens=8192, max_iterations=20, timeout_seconds=600, memory_enabled=False, tools_enabled=False, observability_enabled=False, metadata=metadata)
        assert config.temperature == 0.5
        assert config.max_tokens == 8192
        assert config.max_iterations == 20
        assert config.timeout_seconds == 600
        assert config.memory_enabled is False
        assert config.tools_enabled is False
        assert config.observability_enabled is False
        assert config.metadata == metadata

@pytest.mark.core
class TestAgentState:
    """Test cases for AgentState enum."""

    @pytest.mark.core
    def test_agent_state_values(self):
        """Test AgentState enum has all expected values."""
        expected_states = ['CREATED', 'INITIALIZED', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'STOPPED']
        actual_states = [state.name for state in AgentState]
        for expected in expected_states:
            assert expected in actual_states

@pytest.mark.core
class TestBaseAgentInitialization:
    """Test cases for BaseAgent initialization."""

    @pytest.fixture
    def mock_model_client(self):
        """Create a mock ModelClient."""
        client = Mock()
        client.generate_async = AsyncMock(return_value=Mock(content='Test response'))
        return client

    @pytest.fixture
    def mock_metrics_collector(self):
        """Create a mock AIMetricsCollector."""
        collector = Mock()
        collector.start_operation = Mock(return_value='op-123')
        collector.end_operation = Mock()
        return collector

    @pytest.fixture
    def basic_config(self):
        """Create a basic AgentConfig."""
        return AgentConfig(name='test_agent', description='Test agent', model='claude-3-sonnet')

    @pytest.mark.core
    def test_base_agent_cannot_instantiate_directly(self, basic_config, mock_model_client):
        """Test that BaseAgent is abstract and cannot be instantiated."""
        with pytest.raises(TypeError) as exc_info:
            BaseAgent(basic_config, mock_model_client)
        assert "Can't instantiate abstract class" in str(exc_info.value)

@pytest.mark.core
class TestSimpleTaskAgent:
    """Test cases for SimpleTaskAgent."""

    @pytest.fixture
    def mock_model_client(self):
        """Create a mock ModelClient."""
        client = Mock()
        client.generate_async = AsyncMock(return_value=Mock(content='Test response'))
        return client

    @pytest.fixture
    def mock_metrics_collector(self):
        """Create a mock AIMetricsCollector."""
        collector = Mock()
        collector.start_operation = Mock(return_value='op-123')
        collector.end_operation = Mock()
        return collector

    @pytest.fixture
    def basic_config(self):
        """Create a basic AgentConfig."""
        return AgentConfig(name='simple_agent', description='Simple test agent', model='claude-3-sonnet')

    @pytest.mark.core
    def test_simple_task_agent_creation(self, basic_config, mock_model_client):
        """Test creating SimpleTaskAgent."""
        agent = SimpleTaskAgent(task_prompt='Analyze this data', config=basic_config, model_client=mock_model_client)
        assert agent.task_prompt == 'Analyze this data'
        assert agent.config == basic_config
        assert agent.state == AgentState.CREATED
        assert agent.id is not None
        assert agent.memory is not None
        assert len(agent.tools) == 3

    @pytest.mark.core
    def test_simple_task_agent_creation_with_metrics(self, basic_config, mock_model_client, mock_metrics_collector):
        """Test creating SimpleTaskAgent with metrics collector."""
        agent = SimpleTaskAgent(task_prompt='Analyze this data', config=basic_config, model_client=mock_model_client, metrics_collector=mock_metrics_collector)
        assert agent.metrics == mock_metrics_collector

    @pytest.mark.core
    def test_simple_task_agent_creation_without_memory(self, mock_model_client):
        """Test creating SimpleTaskAgent without memory."""
        config = AgentConfig(name='no_memory_agent', description='Agent without memory', model='claude-3-sonnet', memory_enabled=False)
        agent = SimpleTaskAgent(task_prompt='Quick task', config=config, model_client=mock_model_client)
        assert agent.memory is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_simple_task_agent_initialize(self, basic_config, mock_model_client):
        """Test initializing SimpleTaskAgent."""
        agent = SimpleTaskAgent(task_prompt='Analyze this data', config=basic_config, model_client=mock_model_client)
        assert agent.state == AgentState.CREATED
        await agent.initialize_async()
        assert agent.state == AgentState.INITIALIZED

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_simple_task_agent_initialize_stores_task_in_memory(self, basic_config, mock_model_client):
        """Test that initialization stores task prompt in long-term memory."""
        agent = SimpleTaskAgent(task_prompt='Important task', config=basic_config, model_client=mock_model_client)
        await agent.initialize_async()
        assert 'task_prompt' in agent.memory.long_term
        assert agent.memory.long_term['task_prompt'] == 'Important task'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_simple_task_agent_run_basic(self, basic_config, mock_model_client):
        """Test running SimpleTaskAgent with basic execution."""
        agent = SimpleTaskAgent(task_prompt='Analyze this data', config=basic_config, model_client=mock_model_client)
        await agent.initialize_async()
        result = await agent.run_async()
        assert result == 'Test response'
        assert agent.state == AgentState.COMPLETED
        assert agent.current_iteration == 1
        assert len(agent.results) == 1

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_simple_task_agent_run_with_input_data(self, basic_config, mock_model_client):
        """Test running SimpleTaskAgent with input data."""
        agent = SimpleTaskAgent(task_prompt='Analyze this data', config=basic_config, model_client=mock_model_client)
        await agent.initialize_async()
        result = await agent.run_async(input_data='Sample data set')
        assert result == 'Test response'
        assert mock_model_client.generate_async.called

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_simple_task_agent_run_with_metrics(self, basic_config, mock_model_client, mock_metrics_collector):
        """Test running SimpleTaskAgent tracks metrics."""
        agent = SimpleTaskAgent(task_prompt='Analyze this data', config=basic_config, model_client=mock_model_client, metrics_collector=mock_metrics_collector)
        await agent.initialize_async()
        await agent.run_async()
        mock_metrics_collector.start_operation.assert_called_once()
        mock_metrics_collector.end_operation.assert_called_once()

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_simple_task_agent_run_fails_if_not_initialized(self, basic_config, mock_model_client):
        """Test that running agent without initialization raises error."""
        agent = SimpleTaskAgent(task_prompt='Analyze this data', config=basic_config, model_client=mock_model_client)
        with pytest.raises(AIError) as exc_info:
            await agent.run_async()
        assert 'must be initialized' in str(exc_info.value).lower()

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_simple_task_agent_execution_timing(self, basic_config, mock_model_client):
        """Test that agent tracks execution timing correctly."""
        agent = SimpleTaskAgent(task_prompt='Analyze this data', config=basic_config, model_client=mock_model_client)
        await agent.initialize_async()
        assert agent.start_time is None
        assert agent.end_time is None
        await agent.run_async()
        assert agent.start_time is not None
        assert agent.end_time is not None
        assert agent.end_time > agent.start_time

@pytest.mark.core
class TestBaseAgentTools:
    """Test cases for BaseAgent tool management."""

    @pytest.fixture
    def agent(self, mock_model_client, basic_config):
        """Create a SimpleTaskAgent for testing."""
        return SimpleTaskAgent(task_prompt='Test task', config=basic_config, model_client=mock_model_client)

    @pytest.fixture
    def mock_model_client(self):
        """Create a mock ModelClient."""
        client = Mock()
        client.generate_async = AsyncMock(return_value=Mock(content='Test response'))
        return client

    @pytest.fixture
    def basic_config(self):
        """Create a basic AgentConfig."""
        return AgentConfig(name='test_agent', description='Test agent', model='claude-3-sonnet')

    @pytest.mark.core
    def test_agent_has_default_tools(self, agent):
        """Test that agent has default tools registered."""
        assert 'think' in agent.tools
        assert 'remember' in agent.tools
        assert 'recall' in agent.tools
        assert len(agent.tools) == 3

    @pytest.mark.core
    def test_add_tool(self, agent):
        """Test adding a new tool to agent."""

        def custom_tool():
            return 'custom result'
        tool = AgentTool(name='custom_tool', description='Custom tool', function=custom_tool)
        agent.add_tool(tool)
        assert 'custom_tool' in agent.tools
        assert agent.tools['custom_tool'] == tool
        assert len(agent.tools) == 4

    @pytest.mark.core
    def test_remove_tool_success(self, agent):
        """Test removing an existing tool."""
        result = agent.remove_tool('think')
        assert result is True
        assert 'think' not in agent.tools

    @pytest.mark.core
    def test_remove_tool_not_found(self, agent):
        """Test removing a non-existent tool."""
        result = agent.remove_tool('nonexistent_tool')
        assert result is False

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_call_tool_sync_function(self, agent):
        """Test calling a tool with synchronous function."""

        def sync_tool(x: int, y: int):
            return x + y
        tool = AgentTool(name='add', description='Add two numbers', function=sync_tool)
        agent.add_tool(tool)
        result = await agent.call_tool_async('add', x=5, y=3)
        assert result == 8

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_call_tool_async_function(self, agent):
        """Test calling a tool with async function."""

        async def async_tool(message: str):
            await asyncio.sleep(0.01)
            return f'Processed: {message}'
        tool = AgentTool(name='process', description='Process message', function=async_tool)
        agent.add_tool(tool)
        result = await agent.call_tool_async('process', message='Hello')
        assert result == 'Processed: Hello'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_call_tool_not_found(self, agent):
        """Test calling a non-existent tool raises error."""
        with pytest.raises(AIError) as exc_info:
            await agent.call_tool_async('nonexistent_tool')
        assert 'not available' in str(exc_info.value).lower()

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_call_tool_disabled(self, agent):
        """Test calling a disabled tool raises error."""
        tool = agent.tools['think']
        tool.enabled = False
        with pytest.raises(AIError) as exc_info:
            await agent.call_tool_async('think', prompt='Test')
        assert 'disabled' in str(exc_info.value).lower()

@pytest.mark.core
class TestBaseAgentMemory:
    """Test cases for BaseAgent memory operations."""

    @pytest.fixture
    def agent(self, mock_model_client, basic_config):
        """Create a SimpleTaskAgent for testing."""
        return SimpleTaskAgent(task_prompt='Test task', config=basic_config, model_client=mock_model_client)

    @pytest.fixture
    def mock_model_client(self):
        """Create a mock ModelClient."""
        client = Mock()
        client.generate_async = AsyncMock(return_value=Mock(content='Test response'))
        return client

    @pytest.fixture
    def basic_config(self):
        """Create a basic AgentConfig."""
        return AgentConfig(name='test_agent', description='Test agent', model='claude-3-sonnet')

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_remember_short_term(self, agent):
        """Test storing information in short-term memory."""
        result = await agent._remember_tool_async('key1', 'value1', 'short_term')
        assert 'short_term' in result.lower()
        assert 'key1' in agent.memory.short_term
        assert agent.memory.short_term['key1'] == 'value1'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_remember_long_term(self, agent):
        """Test storing information in long-term memory."""
        result = await agent._remember_tool_async('important_key', 'important_value', 'long_term')
        assert 'long_term' in result.lower()
        assert 'important_key' in agent.memory.long_term
        assert agent.memory.long_term['important_key'] == 'important_value'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_recall_from_short_term(self, agent):
        """Test retrieving information from short-term memory."""
        agent.memory.short_term['test_key'] = 'test_value'
        result = await agent._recall_tool_async('test_key', 'short_term')
        assert result == 'test_value'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_recall_from_long_term(self, agent):
        """Test retrieving information from long-term memory."""
        agent.memory.long_term['test_key'] = 'test_value'
        result = await agent._recall_tool_async('test_key', 'long_term')
        assert result == 'test_value'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_recall_auto_searches_both_memories(self, agent):
        """Test that auto recall searches short-term first then long-term."""
        agent.memory.short_term['key1'] = 'short_value'
        agent.memory.long_term['key2'] = 'long_value'
        result1 = await agent._recall_tool_async('key1', 'auto')
        assert result1 == 'short_value'
        result2 = await agent._recall_tool_async('key2', 'auto')
        assert result2 == 'long_value'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_recall_key_not_found(self, agent):
        """Test recalling non-existent key returns error message."""
        result = await agent._recall_tool_async('nonexistent_key', 'auto')
        assert 'not found' in result.lower()

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_memory_disabled_agent(self, mock_model_client):
        """Test memory operations on agent with memory disabled."""
        config = AgentConfig(name='no_memory_agent', description='Agent without memory', model='claude-3-sonnet', memory_enabled=False)
        agent = SimpleTaskAgent(task_prompt='Test task', config=config, model_client=mock_model_client)
        result = await agent._remember_tool_async('key', 'value')
        assert 'disabled' in result.lower()
        result = await agent._recall_tool_async('key')
        assert 'disabled' in result.lower()

    @pytest.mark.core
    def test_get_memory_summary_with_memory(self, agent):
        """Test getting memory summary for agent with memory enabled."""
        agent.memory.short_term['key1'] = 'value1'
        agent.memory.long_term['key2'] = 'value2'
        summary = agent.get_memory_summary()
        assert summary['memory_enabled'] is True
        assert summary['short_term_items'] == 1
        assert summary['long_term_items'] == 1
        assert 'key1' in summary['short_term_keys']
        assert 'key2' in summary['long_term_keys']

    @pytest.mark.core
    def test_get_memory_summary_without_memory(self, mock_model_client):
        """Test getting memory summary for agent with memory disabled."""
        config = AgentConfig(name='no_memory_agent', description='Agent without memory', model='claude-3-sonnet', memory_enabled=False)
        agent = SimpleTaskAgent(task_prompt='Test task', config=config, model_client=mock_model_client)
        summary = agent.get_memory_summary()
        assert summary['memory_enabled'] is False

@pytest.mark.core
class TestBaseAgentMessaging:
    """Test cases for BaseAgent messaging."""

    @pytest.fixture
    def agent(self, mock_model_client, basic_config):
        """Create a SimpleTaskAgent for testing."""
        return SimpleTaskAgent(task_prompt='Test task', config=basic_config, model_client=mock_model_client)

    @pytest.fixture
    def mock_model_client(self):
        """Create a mock ModelClient."""
        client = Mock()
        client.generate_async = AsyncMock(return_value=Mock(content='Test response'))
        return client

    @pytest.fixture
    def basic_config(self):
        """Create a basic AgentConfig."""
        return AgentConfig(name='test_agent', description='Test agent', model='claude-3-sonnet')

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_send_message(self, agent):
        """Test sending a message."""
        message_id = await agent.send_message_async(recipient='agent-2', content='Hello', message_type='greeting')
        assert message_id is not None
        assert len(agent.message_queue) == 1
        assert agent.message_queue[0].content == 'Hello'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_send_message_stores_in_conversation(self, agent):
        """Test that sent messages are stored in conversation memory."""
        await agent.send_message_async(recipient='agent-2', content='Test message')
        assert len(agent.memory.conversation) == 1
        assert agent.memory.conversation[0].content == 'Test message'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_receive_message(self, agent):
        """Test receiving a message."""
        message = AgentMessage(id='msg-123', sender='agent-2', recipient=agent.id, content='Hello back', message_type='reply', timestamp=datetime.utcnow())
        await agent.receive_message_async(message)
        assert len(agent.memory.conversation) == 1
        assert agent.memory.conversation[0].sender == 'agent-2'

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_receive_message_with_handler(self, agent):
        """Test receiving a message triggers appropriate handler."""
        handler_called = []

        @pytest.mark.core
        def test_handler(msg):
            handler_called.append(msg)
        agent.add_response_handler('test_type', test_handler)
        message = AgentMessage(id='msg-123', sender='agent-2', recipient=agent.id, content='Test', message_type='test_type', timestamp=datetime.utcnow())
        await agent.receive_message_async(message)
        assert len(handler_called) == 1
        assert handler_called[0].content == 'Test'

@pytest.mark.core
class TestBaseAgentStatus:
    """Test cases for BaseAgent status and state management."""

    @pytest.fixture
    def agent(self, mock_model_client, basic_config):
        """Create a SimpleTaskAgent for testing."""
        return SimpleTaskAgent(task_prompt='Test task', config=basic_config, model_client=mock_model_client)

    @pytest.fixture
    def mock_model_client(self):
        """Create a mock ModelClient."""
        client = Mock()
        client.generate_async = AsyncMock(return_value=Mock(content='Test response'))
        return client

    @pytest.fixture
    def basic_config(self):
        """Create a basic AgentConfig."""
        return AgentConfig(name='test_agent', description='Test agent', model='claude-3-sonnet')

    @pytest.mark.core
    def test_get_status_initial(self, agent):
        """Test getting status of newly created agent."""
        status = agent.get_status()
        assert status['id'] == agent.id
        assert status['name'] == 'test_agent'
        assert status['state'] == 'created'
        assert status['current_iteration'] == 0
        assert status['start_time'] is None
        assert status['end_time'] is None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_get_status_after_run(self, agent):
        """Test getting status after agent has run."""
        await agent.initialize_async()
        await agent.run_async()
        status = agent.get_status()
        assert status['state'] == 'completed'
        assert status['current_iteration'] == 1
        assert status['start_time'] is not None
        assert status['end_time'] is not None
        assert status['duration_seconds'] is not None

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_pause_resume_agent(self, agent):
        """Test pausing and resuming agent."""
        await agent.initialize_async()
        agent.state = AgentState.RUNNING
        await agent.pause_async()
        assert agent.state == AgentState.PAUSED
        await agent.resume_async()
        assert agent.state == AgentState.RUNNING

    @pytest.mark.core
    @pytest.mark.asyncio
    async def test_stop_agent(self, agent):
        """Test stopping agent."""
        await agent.initialize_async()
        agent.state = AgentState.RUNNING
        await agent.stop_async()
        assert agent.state == AgentState.STOPPED
        assert agent.end_time is not None
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

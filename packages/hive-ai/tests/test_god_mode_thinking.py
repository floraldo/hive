"""Unit tests for God Mode sequential thinking loop and retry prevention.

Tests cover:
- Multi-step thinking loop execution
- Retry prevention via SHA256 hashing
- Timeout protection
- Task completion detection
- Error handling and recovery
"""

from datetime import datetime

import pytest

from hive_ai.agents.agent import BaseAgent, Task
from hive_ai.core.config import AgentConfig


class TestSequentialThinkingLoop:
    """Test the multi-step sequential thinking loop."""

    @pytest.mark.asyncio
    async def test_thinking_loop_completes_early(self):
        """Test that thinking loop stops when task completes before max_thoughts."""
        config = AgentConfig(
            max_thoughts=10,
            enable_retry_prevention=False,
        )
        agent = BaseAgent(config=config)

        # Mock the thinking tool to complete on thought 3
        call_count = 0

        async def mock_think(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                return {
                    "is_complete": True,
                    "next_step": None,
                    "solution": "Final solution achieved",
                    "reasoning": "Task completed successfully",
                }
            return {
                "is_complete": False,
                "next_step": f"Step {call_count}",
                "solution": None,
                "reasoning": f"Working on step {call_count}",
            }

        agent._tools["think"] = mock_think

        task = Task(
            task_id="test-001",
            description="Test task",
            requirements=["Complete successfully"],
        )

        result = await agent._execute_main_logic_async(task)

        assert result.success is True
        assert result.solution == "Final solution achieved"
        assert len(result.thoughts_log) == 3
        assert call_count == 3  # Should stop at thought 3, not continue to 10

    @pytest.mark.asyncio
    async def test_thinking_loop_reaches_max_thoughts(self):
        """Test that thinking loop respects max_thoughts limit."""
        config = AgentConfig(
            max_thoughts=5,
            enable_retry_prevention=False,
        )
        agent = BaseAgent(config=config)

        # Mock thinking tool that never completes
        async def mock_think(**kwargs):
            return {
                "is_complete": False,
                "next_step": "Continue working",
                "solution": None,
                "reasoning": "Still working...",
            }

        agent._tools["think"] = mock_think

        task = Task(task_id="test-002", description="Never-ending task")

        result = await agent._execute_main_logic_async(task)

        assert result.success is False
        assert len(result.thoughts_log) == 5
        assert "max_thoughts" in result.error.lower()
        assert result.metadata.get("max_thoughts_reached") is True

    @pytest.mark.asyncio
    async def test_thinking_loop_timeout_protection(self):
        """Test that thinking loop respects timeout."""
        config = AgentConfig(
            max_thoughts=100,
            thought_timeout_seconds=1,  # 1 second timeout
        )
        agent = BaseAgent(config=config)

        # Mock slow thinking tool
        import asyncio

        async def mock_think(**kwargs):
            await asyncio.sleep(0.5)  # Each thought takes 0.5s
            return {
                "is_complete": False,
                "next_step": "Continue",
                "solution": None,
                "reasoning": "Working...",
            }

        agent._tools["think"] = mock_think

        task = Task(task_id="test-003", description="Slow task")

        start_time = datetime.now()
        result = await agent._execute_main_logic_async(task)
        duration = (datetime.now() - start_time).total_seconds()

        assert result.success is False
        assert "timeout" in result.error.lower()
        assert duration < 2.0  # Should timeout around 1 second
        assert result.metadata.get("timeout") is True


class TestRetryPrevention:
    """Test retry prevention via solution hashing."""

    @pytest.mark.asyncio
    async def test_retry_prevention_hashes_failed_solutions(self):
        """Test that failed solutions are hashed and tracked."""
        config = AgentConfig(
            max_thoughts=10,
            enable_retry_prevention=True,
        )
        agent = BaseAgent(config=config)

        failed_attempts = []

        async def mock_think(**kwargs):
            prompt = kwargs.get("prompt", "")
            # Check if we're being warned about failed attempts
            if "AVOID RETRYING" in prompt:
                # Extract count from prompt
                import re

                match = re.search(r"(\d+) previously failed", prompt)
                if match:
                    failed_attempts.append(int(match.group(1)))

            return {
                "is_complete": False,
                "next_step": "attempt_solution",
                "solution": None,
                "reasoning": "Trying solution...",
            }

        async def mock_execute_step(step):
            raise Exception("Solution failed")

        agent._tools["think"] = mock_think
        agent._execute_step = mock_execute_step

        task = Task(task_id="test-004", description="Failing task")

        await agent._execute_main_logic_async(task)

        # Should have accumulated failed hashes
        assert len(failed_attempts) > 0
        # Each subsequent attempt should see more failures
        for i in range(len(failed_attempts) - 1):
            assert failed_attempts[i + 1] > failed_attempts[i]

    @pytest.mark.asyncio
    async def test_solution_hashing_consistency(self):
        """Test that same solutions produce same hashes."""
        config = AgentConfig()
        agent = BaseAgent(config=config)

        solution1 = {"approach": "method_a", "params": [1, 2, 3]}
        solution2 = {"params": [1, 2, 3], "approach": "method_a"}  # Different order
        solution3 = {"approach": "method_b", "params": [1, 2, 3]}

        hash1 = agent._hash_solution(solution1)
        hash2 = agent._hash_solution(solution2)
        hash3 = agent._hash_solution(solution3)

        # Same content, different order -> same hash (JSON sort_keys=True)
        assert hash1 == hash2

        # Different content -> different hash
        assert hash1 != hash3

        # Verify it's SHA256 (64 hex chars)
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

    @pytest.mark.asyncio
    async def test_retry_prevention_can_be_disabled(self):
        """Test that retry prevention can be disabled via config."""
        config = AgentConfig(
            max_thoughts=5,
            enable_retry_prevention=False,
        )
        agent = BaseAgent(config=config)

        hash_check_count = 0

        async def mock_think(**kwargs):
            nonlocal hash_check_count
            prompt = kwargs.get("prompt", "")
            if "AVOID RETRYING" in prompt:
                hash_check_count += 1
            return {
                "is_complete": False,
                "next_step": "attempt",
                "solution": None,
                "reasoning": "Trying...",
            }

        async def mock_execute_step(step):
            raise Exception("Failed")

        agent._tools["think"] = mock_think
        agent._execute_step = mock_execute_step

        task = Task(task_id="test-005", description="Task with retry prevention off")

        await agent._execute_main_logic_async(task)

        # Should NOT show retry prevention messages when disabled
        assert hash_check_count == 0


class TestThinkingPromptGeneration:
    """Test prompt generation for thinking steps."""

    def test_build_thinking_prompt_includes_context(self):
        """Test that thinking prompts include all relevant context."""
        config = AgentConfig(max_thoughts=10)
        agent = BaseAgent(config=config)

        task = Task(
            task_id="test-006",
            description="Solve optimization problem",
            context={"constraint": "memory < 1GB", "target": "speed"},
            requirements=["Must be thread-safe", "No external dependencies"],
        )

        prompt = agent._build_thinking_prompt(
            task=task,
            current_solution="Using algorithm X",
            failed_hashes=["abc123", "def456"],
            thought_number=5,
        )

        # Check all elements are present
        assert "Solve optimization problem" in prompt
        assert "THOUGHT 5/10" in prompt
        assert "Must be thread-safe" in prompt
        assert "No external dependencies" in prompt
        assert "constraint: memory < 1GB" in prompt
        assert "target: speed" in prompt
        assert "Using algorithm X" in prompt
        assert "AVOID RETRYING: 2 previously failed" in prompt

    def test_build_thinking_prompt_without_optional_fields(self):
        """Test prompt generation with minimal task data."""
        config = AgentConfig(max_thoughts=3)
        agent = BaseAgent(config=config)

        task = Task(task_id="test-007", description="Simple task")

        prompt = agent._build_thinking_prompt(
            task=task,
            current_solution=None,
            failed_hashes=[],
            thought_number=1,
        )

        assert "Simple task" in prompt
        assert "THOUGHT 1/3" in prompt
        # Should not crash with None/empty values
        assert "CURRENT SOLUTION" not in prompt
        assert "AVOID RETRYING" not in prompt


class TestThoughtResultParsing:
    """Test parsing of thought results."""

    def test_parse_complete_thought(self):
        """Test parsing a completed thought result."""
        config = AgentConfig()
        agent = BaseAgent(config=config)

        thought_result = {
            "is_complete": True,
            "next_step": None,
            "solution": "Final answer: 42",
            "reasoning": "Calculated based on...",
        }

        is_complete, next_step, solution = agent._parse_thought_result(thought_result)

        assert is_complete is True
        assert next_step is None
        assert solution == "Final answer: 42"

    def test_parse_incomplete_thought(self):
        """Test parsing an incomplete thought result."""
        config = AgentConfig()
        agent = BaseAgent(config=config)

        thought_result = {
            "is_complete": False,
            "next_step": "Try approach B",
            "solution": None,
            "reasoning": "Approach A failed, trying B...",
        }

        is_complete, next_step, solution = agent._parse_thought_result(thought_result)

        assert is_complete is False
        assert next_step == "Try approach B"
        assert solution is None

    def test_parse_malformed_thought_result(self):
        """Test handling of malformed thought results."""
        config = AgentConfig()
        agent = BaseAgent(config=config)

        # Missing fields should default to False, None, None
        thought_result = {"reasoning": "Something went wrong"}

        is_complete, next_step, solution = agent._parse_thought_result(thought_result)

        assert is_complete is False
        assert next_step is None
        assert solution is None


class TestTaskResultLogging:
    """Test thought logging and result metadata."""

    @pytest.mark.asyncio
    async def test_thoughts_log_structure(self):
        """Test that thoughts are logged with proper structure."""
        config = AgentConfig(max_thoughts=3)
        agent = BaseAgent(config=config)

        thought_count = 0

        async def mock_think(**kwargs):
            nonlocal thought_count
            thought_count += 1
            return {
                "is_complete": thought_count == 2,
                "next_step": "Continue" if thought_count < 2 else None,
                "solution": "Done" if thought_count == 2 else None,
                "reasoning": f"Thought {thought_count}",
            }

        agent._tools["think"] = mock_think

        task = Task(task_id="test-008", description="Logging test")

        result = await agent._execute_main_logic_async(task)

        # Verify log structure
        assert len(result.thoughts_log) == 2

        for i, thought in enumerate(result.thoughts_log, 1):
            assert thought["thought_number"] == i
            assert "timestamp" in thought
            assert "prompt" in thought
            assert "result" in thought
            assert thought["result"]["reasoning"] == f"Thought {i}"

    @pytest.mark.asyncio
    async def test_result_metadata_on_success(self):
        """Test metadata on successful completion."""
        config = AgentConfig(max_thoughts=10)
        agent = BaseAgent(config=config)

        async def mock_think(**kwargs):
            return {
                "is_complete": True,
                "next_step": None,
                "solution": "Success",
                "reasoning": "Done",
            }

        agent._tools["think"] = mock_think

        task = Task(task_id="test-009", description="Metadata test")

        result = await agent._execute_main_logic_async(task)

        assert result.metadata["total_thoughts"] == 1
        assert result.metadata["completed"] is True
        assert "failed_at_thought" not in result.metadata

    @pytest.mark.asyncio
    async def test_result_metadata_on_timeout(self):
        """Test metadata on timeout."""
        config = AgentConfig(max_thoughts=100, thought_timeout_seconds=1)
        agent = BaseAgent(config=config)

        import asyncio

        async def mock_think(**kwargs):
            await asyncio.sleep(0.5)
            return {"is_complete": False, "next_step": "Continue", "solution": None}

        agent._tools["think"] = mock_think

        task = Task(task_id="test-010", description="Timeout test")

        result = await agent._execute_main_logic_async(task)

        assert result.metadata["timeout"] is True
        assert "final_thought" in result.metadata


class TestAgentConfiguration:
    """Test agent configuration validation."""

    def test_agent_config_defaults(self):
        """Test default configuration values."""
        config = AgentConfig()

        assert config.max_thoughts == 1
        assert config.enable_retry_prevention is True
        assert config.thought_timeout_seconds == 300
        assert config.enable_exa_search is False
        assert config.enable_knowledge_archival is True
        assert config.agent_name == "default"
        assert config.agent_role == "general"

    def test_agent_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = AgentConfig(max_thoughts=30, thought_timeout_seconds=600)
        assert config.max_thoughts == 30

        # Invalid max_thoughts (too high)
        with pytest.raises(Exception):  # Pydantic ValidationError
            AgentConfig(max_thoughts=100)

        # Invalid timeout (too low)
        with pytest.raises(Exception):
            AgentConfig(thought_timeout_seconds=5)

        # Invalid agent role
        with pytest.raises(Exception):
            AgentConfig(agent_role="invalid_role")

    def test_agent_initialization_with_config(self):
        """Test agent initialization with custom config."""
        config = AgentConfig(
            agent_name="test_agent",
            agent_role="specialist",
            max_thoughts=20,
        )

        agent = BaseAgent(config=config)

        assert agent.config.agent_name == "test_agent"
        assert agent.config.agent_role == "specialist"
        assert agent.config.max_thoughts == 20

    def test_agent_tools_registration(self):
        """Test that tools are properly registered."""
        config = AgentConfig()
        agent = BaseAgent(config=config)

        # Default tool should be registered
        assert "think" in agent._tools

        # Web search should NOT be registered when disabled
        assert "web_search" not in agent._tools

    def test_agent_web_search_tool_registration(self):
        """Test web search tool registration when enabled."""
        # Note: This will fail without EXA_API_KEY, which is expected
        config = AgentConfig(enable_exa_search=True)
        agent = BaseAgent(config=config)

        # Tool registration happens even if client init fails
        # Client is just None
        assert agent._web_search_client is None  # No API key in test env

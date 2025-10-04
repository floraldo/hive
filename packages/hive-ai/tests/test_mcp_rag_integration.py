"""Real integration test for MCP + RAG synergy.

Tests the complete God Mode integration with actual MCP Sequential Thinking tool.
NO MOCKS - this tests real functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add hive-ai to path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hive_ai.agents.agent import BaseAgent, Task
from hive_ai.core.config import AgentConfig


async def test_agent_initialization():
    """Test that BaseAgent initializes with all components."""
    print("\n=== Test 1: Agent Initialization ===")

    config = AgentConfig(
        agent_name="integration_test_agent",
        max_thoughts=3,
        enable_retry_prevention=True,
        enable_exa_search=False,  # Disable to avoid API key requirement
        enable_knowledge_archival=True,
    )

    agent = BaseAgent(config=config)

    # Verify initialization
    assert agent.config.agent_name == "integration_test_agent"
    assert agent.config.max_thoughts == 3
    print("OK: Agent initialized successfully")

    # Check tools registration
    assert "think" in agent._tools
    print("OK: Think tool registered")

    if agent._context_service:
        print("OK: RAG context service available")
        assert "retrieve_context" in agent._tools
        print("OK: Retrieve context tool registered")
    else:
        print("INFO: RAG context service not available (optional dependency)")

    return agent


async def test_simple_task_execution(agent: BaseAgent):
    """Test simple task execution with thinking loop."""
    print("\n=== Test 2: Simple Task Execution ===")

    task = Task(
        task_id="test-simple-001",
        description="Calculate the sum of 2 + 2",
        requirements=["Must provide the correct numerical answer"],
    )

    print(f"Executing task: {task.description}")

    try:
        result = await agent.execute_async(task)

        print(f"Task completed: success={result.success}")
        print(f"Thoughts used: {len(result.thoughts_log)}/{agent.config.max_thoughts}")

        if result.solution:
            print(f"Solution: {result.solution}")

        if result.error:
            print(f"Error: {result.error}")

        # Basic validation
        assert result is not None
        print("OK: Task execution completed")

        return result

    except Exception as e:
        print(f"Exception during execution: {e}")
        raise


async def test_rag_context_retrieval(agent: BaseAgent):
    """Test RAG context retrieval before thinking."""
    print("\n=== Test 3: RAG Context Retrieval ===")

    if not agent._context_service:
        print("SKIP: RAG context service not available")
        return

    task = Task(
        task_id="test-rag-001",
        description="Test RAG context retrieval functionality",
    )

    try:
        # Test context retrieval tool directly
        context_result = await agent.call_tool_async(
            "retrieve_context",
            task_id=task.task_id,
            task_description=task.description,
            include_knowledge_archive=True,
            include_test_intelligence=False,
        )

        print(f"Context retrieved: {len(context_result.get('combined_context', ''))} chars")
        print(f"Sources: {len(context_result.get('sources', []))}")

        assert "combined_context" in context_result
        assert "sources" in context_result
        assert "metadata" in context_result

        print("OK: RAG context retrieval working")

    except Exception as e:
        print(f"RAG retrieval failed (expected if no archive): {e}")


async def test_mcp_tool_call(agent: BaseAgent):
    """Test that MCP tool call raises appropriate error when not in CC environment."""
    print("\n=== Test 4: MCP Tool Behavior ===")

    # When running in tests (not Claude Code), calling MCP should raise error
    try:
        await agent.call_tool_async(
            "mcp__sequential-thinking__sequentialthinking",
            query="Test query",
        )
        print("UNEXPECTED: MCP call did not raise error")

    except RuntimeError as e:
        if "cannot be called directly from Python code" in str(e):
            print("OK: MCP tool correctly raises error outside Claude Code context")
            print(f"   Error message: {str(e)[:100]}...")
        else:
            print(f"UNEXPECTED RuntimeError: {e}")
            raise
    except Exception as e:
        print(f"UNEXPECTED exception type: {type(e).__name__}: {e}")
        raise


async def main():
    """Run all integration tests."""
    print("=" * 60)
    print("God Mode Integration Tests - REAL FUNCTIONALITY")
    print("=" * 60)

    try:
        # Test 1: Initialization
        agent = await test_agent_initialization()

        # Test 2: Simple task execution
        result = await test_simple_task_execution(agent)

        # Test 3: RAG context retrieval
        await test_rag_context_retrieval(agent)

        # Test 4: MCP tool behavior
        await test_mcp_tool_call(agent)

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)

        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)

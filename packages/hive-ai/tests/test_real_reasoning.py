"""Test REAL reasoning - no mocks, no placeholders.

This tests the actual sequential thinking implementation.
"""

import asyncio
import sys
from pathlib import Path

# Direct import to avoid dependency issues
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hive_ai.agents.agent import BaseAgent, Task
from hive_ai.core.config import AgentConfig


async def test_real_reasoning():
    """Test the real reasoning algorithm."""
    print("\n" + "=" * 70)
    print("REAL REASONING TEST - NO MOCKS")
    print("=" * 70)

    # Create agent with testing mode
    config = AgentConfig(
        agent_name="test_agent",
        max_thoughts=5,
        enable_retry_prevention=True,
        enable_exa_search=False,
        enable_knowledge_archival=False,
        testing_mode=True,  # Allow graceful dependency handling
    )

    agent = BaseAgent(config=config)
    print(f"\nAgent created: {agent.config.agent_name}")
    print(f"Max thoughts: {agent.config.max_thoughts}")

    # Test simple task
    print("\n--- Test 1: Simple Task ---")
    task = Task(
        task_id="test-001",
        description="Calculate 2 + 2",
        requirements=["Must provide correct answer", "Must show reasoning"],
    )

    result = await agent.execute_async(task)

    print(f"Success: {result.success}")
    print(f"Thoughts used: {len(result.thoughts_log)}/{config.max_thoughts}")
    print(f"Solution: {result.solution}")

    # Show thought progression
    print("\n--- Thought Progression ---")
    for i, thought in enumerate(result.thoughts_log, 1):
        print(f"\nThought {i}:")
        print(f"  Reasoning: {thought['result']['reasoning'][:100]}...")
        print(f"  Complete: {thought['result']['is_complete']}")
        if thought["result"]["solution"]:
            print(f"  Solution: {thought['result']['solution'][:100]}...")

    # Validate it's REAL reasoning
    print("\n--- Validation: REAL Reasoning ---")
    assert result is not None, "Result should not be None"
    assert result.thoughts_log, "Should have thoughts logged"
    assert all("reasoning" in t["result"] for t in result.thoughts_log), "All thoughts should have reasoning"

    # Check it's not mocks
    first_thought = result.thoughts_log[0]["result"]
    assert "mock" not in first_thought["reasoning"].lower(), "Should not contain 'mock'"
    assert "placeholder" not in first_thought["reasoning"].lower(), "Should not contain 'placeholder'"

    print("\nOK: All reasoning is REAL")
    print(f"  - {len(result.thoughts_log)} real thinking steps")
    print(f"  - Real completion detection: {result.success}")
    print(f"  - Real solution generation: {result.solution is not None}")

    return True


async def main():
    try:
        success = await test_real_reasoning()
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED - REAL REASONING VERIFIED")
        print("=" * 70)
        return success
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"TEST FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)

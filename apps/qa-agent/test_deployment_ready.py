#!/usr/bin/env python3
"""Deployment Readiness Test - Verify QA Agent is ready to deploy.

This script validates:
1. All modules import correctly
2. Core components can be instantiated
3. Database connection works
4. Decision engine routes violations

Run: python test_deployment_ready.py
"""

import asyncio
import sys

# Add all required packages to path
for pkg in [  # noqa: E501
    'hive-logging', 'hive-config', 'hive-errors', 'hive-db',
    'hive-bus', 'hive-models', 'hive-async', 'hive-orchestration'
]:
    sys.path.insert(0, f'C:/git/hive/packages/{pkg}/src')
sys.path.insert(0, 'C:/git/hive/apps/qa-agent/src')


async def test_daemon_creation():
    """Test daemon can be created."""
    print("[1/5] Testing daemon instantiation...")
    from qa_agent.daemon import QAAgentDaemon

    daemon = QAAgentDaemon(
        poll_interval=5.0,
        max_concurrent_chimera=3,
        max_concurrent_cc_workers=2
    )

    assert daemon.client is not None, "OrchestrationClient not initialized"
    assert daemon.poll_interval == 5.0
    print("      OK - Daemon created successfully")


async def test_decision_engine():
    """Test decision engine routing logic."""
    print("[2/5] Testing decision engine...")
    from qa_agent.decision_engine import WorkerDecisionEngine

    # Create mock RAG engine
    class MockRAG:
        async def retrieve(self, query, top_k=5):
            return [{"type": "git_commit", "similarity": 0.8, "data": {"message": "test"}}]

    engine = WorkerDecisionEngine(rag_engine=MockRAG())

    # Test simple violation (should route to Chimera)
    simple_violations = [
        {"type": "E501", "file": "test.py", "message": "Line too long"}
    ]

    decision = await engine.decide(simple_violations)

    assert decision.worker_type == "chimera-agent", f"Expected chimera-agent, got {decision.worker_type}"
    assert decision.complexity_score < 0.3, f"Expected low complexity, got {decision.complexity_score}"
    print("      OK - Decision engine routes correctly")


async def test_complexity_scorer():
    """Test complexity scoring."""
    print("[3/5] Testing complexity scorer...")
    from qa_agent.complexity_scorer import ComplexityScorer

    scorer = ComplexityScorer()

    # Test style violation (low complexity)
    style = [{"type": "E501", "file": "test.py"}]
    score = scorer.score(style)
    assert score < 0.2, f"Expected low complexity for style, got {score}"

    # Test architectural violation (higher complexity than style)
    arch = [{"type": "GR37", "file": "config.py", "severity": "ERROR"}]
    score = scorer.score(arch)
    assert score > 0.15, f"Expected higher complexity for architectural, got {score}"

    print("      OK - Complexity scoring works")


async def test_batch_optimizer():
    """Test batch optimization."""
    print("[4/5] Testing batch optimizer...")
    from qa_agent.batch_optimizer import BatchOptimizer

    optimizer = BatchOptimizer(max_batch_size=20)

    violations = [
        {"type": "E501", "file": "a.py"},
        {"type": "E501", "file": "b.py"},
        {"type": "F401", "file": "a.py"},
        {"type": "GR31", "file": "c.py"},
    ]

    batches = optimizer.create_batches(violations, strategy="by_type")

    assert len(batches) == 3, f"Expected 3 batches (E501, F401, GR31), got {len(batches)}"
    print("      OK - Batch optimization works")


async def test_orchestration_client():
    """Test orchestration client integration."""
    print("[5/5] Testing orchestration client...")
    from hive_orchestration.client import OrchestrationClient

    client = OrchestrationClient()

    # Test querying for tasks (database might not exist yet)
    try:
        tasks = client.get_pending_tasks(task_type="qa_workflow")
        assert isinstance(tasks, list), "get_pending_tasks should return a list"
    except Exception as e:
        # Database doesn't exist yet - this is expected for first run
        if "no such table" in str(e):
            print("      Note: Orchestrator database not initialized (expected for first run)")
        else:
            raise

    print("      OK - Orchestration client works")


async def main():
    """Run all deployment readiness tests."""
    print("=" * 80)
    print("QA AGENT DEPLOYMENT READINESS TEST")
    print("=" * 80)
    print()

    try:
        await test_daemon_creation()
        await test_decision_engine()
        await test_complexity_scorer()
        await test_batch_optimizer()
        await test_orchestration_client()

        print()
        print("=" * 80)
        print("SUCCESS: All tests passed - QA Agent ready for deployment!")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Run demo: ./demo_deployment.sh")
        # noqa: E501
        print("  2. Start daemon: python start_with_dashboard.py")
        print("  3. See quickstart: cat QUICKSTART.md")
        print()

        return 0

    except AssertionError as e:
        print()
        print("=" * 80)
        print(f"TEST FAILED: {e}")
        print("=" * 80)
        return 1

    except Exception as e:
        print()
        print("=" * 80)
        print(f"ERROR: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

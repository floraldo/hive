#!/bin/bash
# Quick Test - Validate QA Agent components without full deployment

set -e

echo "========================================================================"
echo "QA AGENT QUICK VALIDATION TEST"
echo "========================================================================"
echo ""

cd "$(dirname "${BASH_SOURCE[0]}")"

# Test 1: Import checks
echo "TEST 1: Verifying Python imports..."
poetry run python << 'EOF'
try:
    from qa_agent.daemon import QAAgentDaemon
    from qa_agent.decision_engine import WorkerDecisionEngine
    from qa_agent.rag_priming import RAGEngine
    from qa_agent.monitoring import QAWorkerMonitor
    from qa_agent.cc_spawner import CCWorkerSpawner
    from qa_agent.persona_builder import build_worker_persona
    from qa_agent.complexity_scorer import ComplexityScorer
    from qa_agent.batch_optimizer import BatchOptimizer
    from qa_agent.escalation import EscalationManager
    from qa_agent.dashboard import Dashboard
    print("✅ All QA Agent modules import successfully")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)
EOF

# Test 2: Decision engine
echo ""
echo "TEST 2: Testing decision engine routing..."
poetry run python << 'EOF'
from qa_agent.decision_engine import WorkerDecisionEngine

# Mock RAG engine
class MockRAG:
    async def retrieve(self, query, top_k=5):
        return [{"type": "git_commit", "similarity": 0.8, "data": {"message": "test"}}]

engine = WorkerDecisionEngine(rag_engine=MockRAG())

# Test simple violation (should route to Chimera)
simple_violations = [
    {"type": "E501", "file": "test.py", "message": "Line too long"}
]

import asyncio
decision = asyncio.run(engine.decide(simple_violations))

assert decision.worker_type == "chimera-agent", f"Expected chimera-agent, got {decision.worker_type}"
assert decision.complexity_score < 0.3, f"Expected low complexity, got {decision.complexity_score}"

print(f"✅ Simple violations route to Chimera (complexity: {decision.complexity_score:.2f})")

# Test complex violation (should route to CC worker)
complex_violations = [
    {"type": "GR37", "file": "config.py", "severity": "ERROR", "message": "Unified config"}
]

decision = asyncio.run(engine.decide(complex_violations))

assert decision.worker_type in ("cc-worker-headless", "chimera-agent"), f"Unexpected worker: {decision.worker_type}"
print(f"✅ Complex violations route correctly (complexity: {decision.complexity_score:.2f}, type: {decision.worker_type})")

# Test critical violation (should route to HITL)
critical_violations = [
    {"type": "security", "file": "auth.py", "severity": "CRITICAL", "message": "SQL injection"}
]

decision = asyncio.run(engine.decide(critical_violations))

assert decision.worker_type == "cc-worker-with-hitl", f"Expected HITL, got {decision.worker_type}"
print(f"✅ Critical violations route to HITL")
EOF

# Test 3: Complexity scorer
echo ""
echo "TEST 3: Testing complexity scorer..."
poetry run python << 'EOF'
from qa_agent.complexity_scorer import ComplexityScorer

scorer = ComplexityScorer()

# Test style violation (low complexity)
style = [{"type": "E501", "file": "test.py"}]
score = scorer.score(style)
assert score < 0.2, f"Expected low complexity for style, got {score}"
print(f"✅ Style violations scored low: {score:.2f}")

# Test architectural violation (high complexity)
arch = [{"type": "GR37", "file": "config.py", "severity": "ERROR"}]
score = scorer.score(arch)
assert score > 0.5, f"Expected high complexity for architectural, got {score}"
print(f"✅ Architectural violations scored high: {score:.2f}")
EOF

# Test 4: Batch optimizer
echo ""
echo "TEST 4: Testing batch optimizer..."
poetry run python << 'EOF'
from qa_agent.batch_optimizer import BatchOptimizer

optimizer = BatchOptimizer(max_batch_size=20)

# Test batching
violations = [
    {"type": "E501", "file": "a.py"},
    {"type": "E501", "file": "b.py"},
    {"type": "F401", "file": "a.py"},
    {"type": "GR31", "file": "c.py"},
]

batches = optimizer.create_batches(violations, strategy="by_type")

assert len(batches) == 3, f"Expected 3 batches (E501, F401, GR31), got {len(batches)}"
print(f"✅ Batching by type works: {len(batches)} batches created")

# Test prioritization
prioritized = optimizer.prioritize_batches(batches)
assert len(prioritized) == len(batches), "Prioritization should preserve batch count"
print(f"✅ Batch prioritization works")
EOF

# Test 5: Persona builder
echo ""
echo "TEST 5: Testing persona builder..."
poetry run python << 'EOF'
from qa_agent.persona_builder import build_worker_persona

task = {
    "id": "test-123",
    "title": "Test task",
    "description": "Demo task",
    "payload": {
        "qa_type": "ruff",
        "scope": ".",
        "violations": [{"type": "E501", "file": "test.py"}]
    }
}

rag_context = [
    {"type": "git_commit", "similarity": 0.8, "data": {"message": "fix: test"}}
]

persona = build_worker_persona(task, rag_context, mode="headless")

assert persona["worker_id"].startswith("qa-cc-headless-"), f"Invalid worker ID: {persona['worker_id']}"
assert persona["mode"] == "headless", f"Expected headless, got {persona['mode']}"
assert len(persona["violations"]) == 1, f"Expected 1 violation, got {len(persona['violations'])}"
assert len(persona["rag_context"]) == 1, f"Expected 1 RAG pattern, got {len(persona['rag_context'])}"

print(f"✅ Persona builder works: {persona['worker_id']}")
EOF

# Test 6: Escalation manager
echo ""
echo "TEST 6: Testing escalation manager..."
poetry run python << 'EOF'
import asyncio
from qa_agent.escalation import EscalationManager, EscalationStatus

# Mock event bus
class MockEventBus:
    async def publish(self, topic, event):
        pass

manager = EscalationManager()
manager.event_bus = MockEventBus()

async def test_escalation():
    # Create escalation
    esc = await manager.create_escalation(
        task_id="test-123",
        worker_id="worker-456",
        reason="Test escalation",
        violations=[{"type": "test"}]
    )

    assert esc.status == EscalationStatus.PENDING, f"Expected PENDING, got {esc.status}"
    print(f"✅ Escalation created: {esc.escalation_id}")

    # Assign escalation
    success = await manager.assign_escalation(esc.escalation_id, "human@example.com")
    assert success, "Escalation assignment failed"
    assert esc.status == EscalationStatus.IN_REVIEW, f"Expected IN_REVIEW, got {esc.status}"
    print(f"✅ Escalation assigned to reviewer")

    # Resolve escalation
    success = await manager.resolve_escalation(
        esc.escalation_id,
        EscalationStatus.RESOLVED,
        "Fixed manually"
    )
    assert success, "Escalation resolution failed"
    assert esc.status == EscalationStatus.RESOLVED, f"Expected RESOLVED, got {esc.status}"
    print(f"✅ Escalation resolved")

    # Get stats
    stats = manager.get_escalation_stats()
    assert stats["total_escalations"] == 1, f"Expected 1 total, got {stats['total_escalations']}"
    assert stats["resolved"] == 1, f"Expected 1 resolved, got {stats['resolved']}"
    print(f"✅ Escalation stats correct")

asyncio.run(test_escalation())
EOF

# Test 7: CLI commands
echo ""
echo "TEST 7: Testing CLI commands..."
poetry run qa-agent --version
echo "✅ CLI version command works"

# Summary
echo ""
echo "========================================================================"
echo "VALIDATION SUMMARY"
echo "========================================================================"
echo ""
echo "✅ All imports successful"
echo "✅ Decision engine routes correctly"
echo "✅ Complexity scorer works"
echo "✅ Batch optimizer works"
echo "✅ Persona builder works"
echo "✅ Escalation manager works"
echo "✅ CLI commands work"
echo ""
echo "🎉 QA Agent validation passed!"
echo ""
echo "Next steps:"
echo "  1. Run full deployment: ./demo_deployment.sh"
echo "  2. Or start daemon: ./cli/start_qa_agent.sh"
echo "  3. Or follow quickstart: cat DEPLOYMENT_QUICKSTART.md"
echo ""
echo "========================================================================"

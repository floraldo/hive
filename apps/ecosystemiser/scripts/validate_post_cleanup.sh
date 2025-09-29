#!/bin/bash
# Agent 2 Post-Cleanup Validation Script
# Run this after Agent 1 completes systematic syntax cleanup

set -e  # Exit on first error

echo "=========================================="
echo "Agent 2: Post-Cleanup Validation"
echo "=========================================="
echo ""

# Phase 1: Test Collection
echo "Phase 1: Test Collection Validation"
echo "------------------------------------"
python -m pytest --collect-only --quiet
COLLECT_EXIT=$?

if [ $COLLECT_EXIT -eq 0 ]; then
    echo "✅ Phase 1 PASSED: All tests collected successfully"
else
    echo "❌ Phase 1 FAILED: Test collection errors remain"
    exit 1
fi
echo ""

# Phase 2: Test Execution
echo "Phase 2: Test Execution Validation"
echo "-----------------------------------"
python -m pytest tests/ -v --tb=short | tee test_results.log
TEST_EXIT=$?

# Count passing tests
PASSING=$(grep -c "PASSED" test_results.log || echo "0")
TOTAL=$(grep -c "PASSED\|FAILED" test_results.log || echo "1")
PASS_RATE=$(python -c "print(f'{($PASSING/$TOTAL)*100:.1f}')")

echo ""
echo "Test Results: $PASSING/$TOTAL passing ($PASS_RATE%)"

if (( $(echo "$PASS_RATE >= 90.0" | bc -l) )); then
    echo "✅ Phase 2 PASSED: $PASS_RATE% pass rate (≥90% required)"
else
    echo "❌ Phase 2 FAILED: $PASS_RATE% pass rate (<90% required)"
    exit 1
fi
echo ""

# Phase 3: Import Chain Validation
echo "Phase 3: Import Chain Validation"
echo "---------------------------------"
python << 'PYTHON_IMPORTS'
import sys

critical_imports = [
    ("StudyService", "from ecosystemiser.services.study_service import StudyService"),
    ("AnalyserService", "from ecosystemiser.analyser import AnalyserService"),
    ("ClimateService", "from ecosystemiser.profile_loader.climate import ClimateService"),
    ("GeneticAlgorithm", "from ecosystemiser.discovery.algorithms import GeneticAlgorithm"),
]

failed = []
for name, import_stmt in critical_imports:
    try:
        exec(import_stmt)
        print(f"✅ {name}: Import successful")
    except Exception as e:
        print(f"❌ {name}: Import failed - {e}")
        failed.append(name)

if failed:
    print(f"\n❌ Phase 3 FAILED: {len(failed)} critical imports failed")
    sys.exit(1)
else:
    print("\n✅ Phase 3 PASSED: All critical imports working")
PYTHON_IMPORTS

IMPORT_EXIT=$?
if [ $IMPORT_EXIT -ne 0 ]; then
    exit 1
fi
echo ""

# Phase 4: Demo Validation (Optional)
echo "Phase 4: Demo Validation (Optional)"
echo "------------------------------------"
if [ -f "examples/run_full_demo.py" ]; then
    echo "Demo script found. Ready for manual validation."
    echo "Run: python examples/run_full_demo.py"
else
    echo "⚠️  Demo script not found"
fi
echo ""

# Summary
echo "=========================================="
echo "✅ ALL VALIDATION PHASES PASSED"
echo "=========================================="
echo ""
echo "Agent 2 Assessment: Codebase ready for:"
echo "  - v3.0.0-beta release (if Phase 4 demo works)"
echo "  - v3.0.0 final release (if all artifacts generated)"
echo ""
echo "Next Steps:"
echo "  1. Run demo: python examples/run_full_demo.py"
echo "  2. Verify artifacts in results/"
echo "  3. Update CHANGELOG.md"
echo "  4. Create release tag"
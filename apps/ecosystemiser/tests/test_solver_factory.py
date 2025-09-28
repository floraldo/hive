#!/usr/bin/env python3
"""
Test script to validate the SolverFactory consolidation.

This script tests that the rolling horizon solver consolidation is working
correctly and that the SolverFactory can create the unified implementation.
"""

from ecosystemiser.solver.factory import SolverFactory
from ecosystemiser.solver.rolling_horizon_milp import RollingHorizonMILPSolver


def test_solver_factory_consolidation():
    """Test that SolverFactory correctly uses the unified rolling horizon implementation."""
    print("=== Testing SolverFactory Rolling Horizon Consolidation ===")

    try:
        # Test that we can list available solvers
        available_solvers = SolverFactory.list_available_solvers()
        print(f"[INFO] Available solvers: {available_solvers}")

        # Verify rolling_horizon is available
        if "rolling_horizon" not in available_solvers:
            print("[FAIL] rolling_horizon solver not available in factory")
            return False

        print("[SUCCESS] rolling_horizon solver available in factory")

        # Test that we can create a rolling horizon solver
        # We need a mock system for this
        class MockSystem:
            def __init__(self):
                self.N = 24
                self.system_id = "test_system"
                self.components = {}

        mock_system = MockSystem()

        # Create rolling horizon solver through factory
        solver = SolverFactory.get_solver("rolling_horizon", mock_system)
        print(f"[SUCCESS] Created solver through factory: {type(solver)}")

        # Verify it's the correct implementation
        if not isinstance(solver, RollingHorizonMILPSolver):
            print(f"[FAIL] Expected RollingHorizonMILPSolver, got {type(solver)}")
            return False

        print("[SUCCESS] Solver is correct RollingHorizonMILPSolver type")

        # Test that it has the expected attributes of the comprehensive implementation
        expected_attrs = ["_generate_windows", "validate_solution", "get_full_solution"]
        for attr in expected_attrs:
            if hasattr(solver, attr):
                print(f"[SUCCESS] Found expected method: {attr}")
            else:
                print(f"[FAIL] Missing expected method: {attr}")
                return False

        print(
            "[SUCCESS] All expected methods found - using comprehensive implementation"
        )

        return True

    except Exception as e:
        print(f"[FAIL] SolverFactory test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_no_ambiguity():
    """Test that there's no longer any ambiguity about which implementation to use."""
    print("\n=== Testing No Implementation Ambiguity ===")

    try:
        # Try to import the old implementation - should fail
        try:
            from ecosystemiser.solver.rolling_horizon_solver import (
                RollingHorizonMILPSolver as OldSolver,
            )

            print(
                "[FAIL] Old rolling_horizon_solver.py still importable - should have been removed"
            )
            return False
        except ImportError:
            print(
                "[SUCCESS] Old implementation no longer importable - correctly removed"
            )

        # Import the unified implementation - should work
        from ecosystemiser.solver.rolling_horizon_milp import (
            RollingHorizonMILPSolver as UnifiedSolver,
        )

        print("[SUCCESS] Unified implementation successfully importable")

        # Verify they're the same implementation the factory uses
        class MockSystem:
            N = 24
            system_id = "test"
            components = {}

        factory_solver = SolverFactory.get_solver("rolling_horizon", MockSystem())
        direct_solver = UnifiedSolver(MockSystem())

        if type(factory_solver) == type(direct_solver):
            print("[SUCCESS] Factory and direct imports use same implementation")
        else:
            print(
                f"[FAIL] Factory uses {type(factory_solver)}, direct uses {type(direct_solver)}"
            )
            return False

        return True

    except Exception as e:
        print(f"[FAIL] Ambiguity test failed: {e}")
        return False


def main():
    """Run all rolling horizon consolidation validation tests."""
    print("Rolling Horizon Solver Consolidation Validation")
    print("=" * 60)

    # Test 1: SolverFactory consolidation
    test1_success = test_solver_factory_consolidation()

    # Test 2: No ambiguity
    test2_success = test_no_ambiguity()

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY:")

    if test1_success:
        print("[PASS] SolverFactory Consolidation: PASSED")
    else:
        print("[FAIL] SolverFactory Consolidation: FAILED")

    if test2_success:
        print("[PASS] No Implementation Ambiguity: PASSED")
    else:
        print("[FAIL] No Implementation Ambiguity: FAILED")

    overall_success = test1_success and test2_success

    if overall_success:
        print("\n[SUCCESS] Phase 2 Rolling Horizon Consolidation: SUCCESS!")
        print("   [SUCCESS] Duplicate implementation removed")
        print("   [SUCCESS] SolverFactory points to unified implementation")
        print("   [SUCCESS] No more architectural ambiguity")
    else:
        print("\n[FAIL] Phase 2 Rolling Horizon Consolidation: FAILED")
        print("   Some tests failed - review output above")

    return overall_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

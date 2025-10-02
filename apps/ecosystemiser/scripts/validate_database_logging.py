"""Standalone validation script for database logging functionality.

This script validates that the database logging implementation works correctly
without requiring full pytest or environment setup.
"""

import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import DatabaseMetadataService directly to avoid import chain issues
import importlib.util

spec = importlib.util.spec_from_file_location(
    "database_metadata_service",
    Path(__file__).parent.parent / "src" / "ecosystemiser" / "services" / "database_metadata_service.py"
)
db_module = importlib.util.module_from_spec(spec)

try:
    spec.loader.exec_module(db_module)
    DatabaseMetadataService = db_module.DatabaseMetadataService
    print("[OK] DatabaseMetadataService imported successfully")
except Exception as e:
    print(f"[FAIL] Failed to import DatabaseMetadataService: {e}")
    sys.exit(1)


def test_database_basic_operations():
    """Test basic database operations."""
    print("\n=== Testing Basic Database Operations ===")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name

    try:
        # Initialize service
        db_service = DatabaseMetadataService(db_path=db_path)
        print(f"[OK] Initialized DatabaseMetadataService with temp DB: {db_path}")

        # Test 1: Log a simulation run
        run_id = str(uuid.uuid4()),
        run_data = {
            "run_id": run_id,
            "study_id": "test_study",
            "system_id": "test_system",
            "timesteps": 8760,
            "timestamp": datetime.now().isoformat(),
            "solver_type": "hybrid",
            "simulation_status": "running",
        }

        db_service.log_simulation_run(run_data)
        print(f"[OK] Logged simulation run: {run_id}")

        # Test 2: Update with KPIs
        update_data = {
            "run_id": run_id,
            "simulation_status": "completed",
            "total_cost": 150000.0,
            "total_co2": 50.0,
            "renewable_fraction": 0.85,
            "total_generation_kwh": 10000.0,
            "total_demand_kwh": 8500.0,
        }

        db_service.log_simulation_run(update_data)
        print(f"[OK] Updated simulation run with KPIs")

        # Test 3: Query runs
        runs = db_service.query_simulation_runs(filters={"study_id": "test_study"})
        if runs and len(runs) > 0:
            print(f"[OK] Queried simulation runs: {len(runs)} found")
            run = runs[0]
            print(f"   - Run ID: {run.get('run_id')}")
            print(f"   - Status: {run.get('simulation_status')}")
            print(f"   - Cost: ${run.get('total_cost')}")
            print(f"   - Renewable: {run.get('renewable_fraction')*100:.1f}%")
        else:
            print("[FAIL] Query returned no results")
            return False

        # Test 4: Query by solver type
        hybrid_runs = db_service.query_simulation_runs(
            filters={"solver_type": "hybrid"}
        )
        if hybrid_runs and len(hybrid_runs) > 0:
            print(f"[OK] Filtered by solver_type: {len(hybrid_runs)} hybrid runs found")
        else:
            print("[FAIL] Filter by solver_type failed")
            return False

        # Test 5: Order by cost
        ordered_runs = db_service.query_simulation_runs(
            filters={"study_id": "test_study"},
            order_by="total_cost",
            limit=5
        )
        if ordered_runs:
            print(f"[OK] Ordered query works: {len(ordered_runs)} runs")
        else:
            print("[FAIL] Ordered query failed")
            return False

        print("\n[OK] All database tests passed!")
        return True

    except Exception as e:
        print(f"[FAIL] Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        try:
            Path(db_path).unlink()
        except Exception:
            pass


def test_logging_workflow():
    """Test the complete logging workflow."""
    print("\n=== Testing Complete Logging Workflow ===")

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name

    try:
        db_service = DatabaseMetadataService(db_path=db_path)

        # Simulate multiple runs
        run_ids = []
        for i in range(3):
            run_id = str(uuid.uuid4())
            run_ids.append(run_id)

            # Pre-run logging
            db_service.log_simulation_run({
                "run_id": run_id,
                "study_id": "workflow_test",
                "solver_type": "hybrid" if i % 2 == 0 else "milp",
                "simulation_status": "running",
                "timestamp": datetime.now().isoformat(),
            })

            # Post-run logging with KPIs
            db_service.log_simulation_run({
                "run_id": run_id,
                "simulation_status": "completed",
                "total_cost": 100000.0 + i * 25000.0,
                "renewable_fraction": 0.7 + i * 0.1,
            })

        print(f"[OK] Logged {len(run_ids)} simulation runs")

        # Query all runs
        all_runs = db_service.query_simulation_runs(
            filters={"study_id": "workflow_test"}
        )

        if len(all_runs) == 3:
            print(f"[OK] Retrieved all {len(all_runs)} runs")
        else:
            print(f"[FAIL] Expected 3 runs, got {len(all_runs)}")
            return False

        # Query cheapest
        cheapest = db_service.query_simulation_runs(
            filters={"study_id": "workflow_test"},
            order_by="total_cost",
            limit=1
        )

        if cheapest and cheapest[0].get("total_cost") == 100000.0:
            print(f"[OK] Cheapest run found: ${cheapest[0].get('total_cost')}")
        else:
            print("[FAIL] Cheapest query failed")
            return False

        # Query by solver type
        hybrid_runs = db_service.query_simulation_runs(
            filters={"solver_type": "hybrid", "study_id": "workflow_test"}
        )

        if len(hybrid_runs) == 2:  # runs 0 and 2 are hybrid
            print(f"[OK] Solver type filter works: {len(hybrid_runs)} hybrid runs")
        else:
            print(f"[FAIL] Expected 2 hybrid runs, got {len(hybrid_runs)}")
            return False

        print("\n[OK] Complete workflow test passed!")
        return True

    except Exception as e:
        print(f"[FAIL] Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        try:
            Path(db_path).unlink()
        except Exception:
            pass


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Database Logging Validation Script")
    print("=" * 60)

    results = []

    # Test 1: Basic operations
    results.append(("Basic Database Operations", test_database_basic_operations()))

    # Test 2: Complete workflow
    results.append(("Complete Logging Workflow", test_logging_workflow()))

    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    for test_name, passed in results:
        status = "[OK] PASSED" if passed else "[FAIL] FAILED"
        print(f"{test_name}: {status}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n[OK] All validation tests passed!")
        print("\nDatabase logging implementation is production-ready.")
        return 0
    else:
        print("\n[FAIL] Some validation tests failed.")
        print("\nPlease review errors above and fix issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

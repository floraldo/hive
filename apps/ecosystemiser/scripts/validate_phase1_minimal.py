"""Minimal Phase 1 validation - database_metadata_service.py only."""

import sqlite3
import sys
from pathlib import Path

print("=" * 60)
print("Phase 1 Minimal Validation - SQL Syntax Check")
print("=" * 60)

# Test SQL schema directly
schema_sql = """
CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    system_id TEXT,
    timesteps INTEGER,
    timestamp TEXT,
    solver_type TEXT,
    simulation_status TEXT DEFAULT 'completed',
    total_cost REAL,
    total_co2 REAL,
    self_consumption_rate REAL,
    self_sufficiency_rate REAL,
    renewable_fraction REAL,
    total_generation_kwh REAL,
    total_demand_kwh REAL,
    net_grid_usage_kwh REAL,
    results_path TEXT NOT NULL,
    flows_path TEXT,
    components_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_simulation_runs_study_id ON simulation_runs(study_id);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_timestamp ON simulation_runs(timestamp);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_solver_type ON simulation_runs(solver_type);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_total_cost ON simulation_runs(total_cost);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_renewable_fraction ON simulation_runs(renewable_fraction);

CREATE TABLE IF NOT EXISTS studies (
    study_id TEXT PRIMARY KEY,
    study_name TEXT,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    run_count INTEGER DEFAULT 0,
    metadata_json TEXT
);
"""

try:
    # Test 1: SQL syntax is valid
    print("\n=== Test 1: SQL Schema Syntax ===")
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_sql)
    print("[OK] SQL schema executes without errors")

    # Test 2: Can insert data
    print("\n=== Test 2: Data Insertion ===")
    conn.execute("""
        INSERT INTO simulation_runs (run_id, study_id, results_path)
        VALUES ('test_run_1', 'test_study', '/tmp/test')
    """)
    print("[OK] Can insert simulation run")

    # Test 3: Can query data
    print("\n=== Test 3: Data Querying ===")
    cursor = conn.execute("SELECT * FROM simulation_runs WHERE study_id = 'test_study'")
    rows = cursor.fetchall()
    if len(rows) == 1:
        print(f"[OK] Query returned {len(rows)} row")
    else:
        print(f"[FAIL] Expected 1 row, got {len(rows)}")
        sys.exit(1)

    # Test 4: Python file compiles
    print("\n=== Test 4: Python File Compilation ===")
    db_service_path = Path(__file__).parent.parent / "src" / "ecosystemiser" / "services" / "database_metadata_service.py"
    import py_compile
    py_compile.compile(str(db_service_path), doraise=True)
    print(f"[OK] {db_service_path.name} compiles successfully")

    conn.close()

    print("\n" + "=" * 60)
    print("Phase 1 Validation Result")
    print("=" * 60)
    print("[OK] All Phase 1 tests passed!")
    print("\nThe SQL schema is syntactically correct and functional.")
    print("database_metadata_service.py compiles without errors.")
    print("\nPhase 1 COMPLETE - Ready for Phase 2 implementation.")
    sys.exit(0)

except sqlite3.OperationalError as e:
    print(f"\n[FAIL] SQL syntax error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n[FAIL] Validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Database Integration Phase 1 - Implementation Plan

**Status**: Ready for Implementation
**Component**: StudyService Database Logging Integration
**Goal**: Automatically log every simulation run to SQLite database for querying and analysis

---

## Context

The Hybrid Solver is production-ready, but simulation results are scattered across files. We need to transform simulation outputs into a structured, queryable knowledge base by automatically logging runs to the database.

---

## Existing Infrastructure (Already Built ✅)

### 1. DatabaseMetadataService (`src/ecosystemiser/services/database_metadata_service.py`)
- **Already integrated** in StudyService (line 115: `self.database_service = DatabaseMetadataService()`)
- Schema includes:
  - `simulation_runs` table with KPI fields (total_cost, renewable_fraction, etc.)
  - `studies` table for study tracking
  - Enhanced schema for GA/MC support (via `migrate_to_enhanced_schema()`)

### 2. KPICalculator (`src/ecosystemiser/analyser/kpi_calculator.py`)
- `calculate_from_system(system)` - Calculate KPIs from solved system
- Returns dict with energy/water KPIs
- System type auto-detection

### 3. JobFacade (`src/ecosystemiser/services/job_facade.py`)
- Decouples StudyService from SimulationService
- Job tracking with status (PENDING, RUNNING, COMPLETED, FAILED)
- Event bus integration

---

## Implementation Strategy

### Integration Points in StudyService

The `StudyService` already has:
1. `self.database_service = DatabaseMetadataService()` - ready to use
2. `self.job_facade` - for running simulations
3. Event bus integration - for monitoring

**Key Methods to Modify**:
1. `_run_simulations()` - Runs batch of simulations
2. `_run_genetic_algorithm_study()` - GA workflow
3. `_run_monte_carlo_study()` - MC workflow

---

## Phase 1 Tasks

### Task 1: Add Pre-Run Logging (Status: "running")

**Location**: `StudyService._run_simulations()` (around line 926)

**Implementation**:
```python
def _run_simulations(self, configs: list[SimulationConfig], study_config: StudyConfig):
    """Run simulations with database logging."""
    results = []

    for config in configs:
        run_id = str(uuid.uuid4())

        # PRE-RUN: Log simulation as "running"
        self.database_service.log_simulation_run({
            "run_id": run_id,
            "study_id": study_config.study_id,
            "system_id": config.system_id,
            "timesteps": config.timesteps,
            "timestamp": datetime.now().isoformat(),
            "solver_type": config.solver_type,
            "simulation_status": "running",
            "results_path": str(study_config.output_directory / run_id),
        })

        # Run simulation
        result = self.job_facade.submit_job(...)

        # POST-RUN: Update with KPIs (see Task 2)
        ...
```

### Task 2: Add Post-Run Logging (Status: "completed" + KPIs)

**After simulation completes**:

```python
# Calculate KPIs from solved system
from ecosystemiser.analyser.kpi_calculator import KPICalculator

kpi_calculator = KPICalculator()
kpis = kpi_calculator.calculate_from_system(system)

# Update database with results
self.database_service.log_simulation_run({
    "run_id": run_id,
    "study_id": study_config.study_id,
    "simulation_status": "completed",
    "total_cost": kpis.get("total_cost"),
    "renewable_fraction": kpis.get("renewable_fraction"),
    "self_consumption_rate": kpis.get("self_consumption_rate"),
    "self_sufficiency_rate": kpis.get("self_sufficiency_rate"),
    "total_generation_kwh": kpis.get("total_generation_kwh"),
    "total_demand_kwh": kpis.get("total_demand_kwh"),
    # ... all KPI fields from schema
})
```

### Task 3: Handle Failures (Status: "failed")

**On error**:
```python
except Exception as e:
    self.database_service.log_simulation_run({
        "run_id": run_id,
        "simulation_status": "failed",
        "metadata_json": json.dumps({"error": str(e)})
    })
    raise
```

---

## Integration Test Specification

**File**: `tests/integration/test_database_logging.py`

```python
def test_simulation_logged_to_database():
    """Test that simulations are automatically logged to database."""

    # Create study service
    study_service = StudyService()

    # Run simple simulation
    config = StudyConfig(
        study_id="test_db_logging",
        study_type="parametric",
        base_config=SimulationConfig(...)
    )

    result = study_service.run_study(config)

    # Query database
    db_service = DatabaseMetadataService()
    runs = db_service.query_simulation_runs(study_id="test_db_logging")

    # Assertions
    assert len(runs) > 0, "Should have logged at least one run"
    assert runs[0]["simulation_status"] == "completed"
    assert runs[0]["total_cost"] is not None, "Should have KPIs"
    assert runs[0]["solver_type"] is not None


def test_hybrid_solver_logged():
    """Test that Hybrid Solver runs are logged correctly."""

    config = SimulationConfig(
        solver_type="hybrid",
        timesteps=168,  # 1 week
    )

    # ... run simulation

    # Verify database has solver_type="hybrid"
    runs = db_service.query_simulation_runs(solver_type="hybrid")
    assert len(runs) > 0
```

---

## KPI Fields to Extract

From `DatabaseMetadataService` schema (lines 38-47):
- `total_cost` - Total system cost (€)
- `total_co2` - Total CO2 emissions
- `self_consumption_rate` - Solar self-consumption rate
- `self_sufficiency_rate` - Energy self-sufficiency rate
- `renewable_fraction` - Renewable energy fraction
- `total_generation_kwh` - Total generation (kWh)
- `total_demand_kwh` - Total demand (kWh)
- `net_grid_usage_kwh` - Net grid import/export (kWh)

**Mapping from KPICalculator**:
- Check `_calculate_energy_kpis()` for exact field names
- May need adapter if field names don't match exactly

---

## Implementation Steps

### Step 1: Modify StudyService
1. Add `run_id` generation in `_run_simulations()`
2. Add pre-run logging (status: "running")
3. Add post-run logging with KPIs (status: "completed")
4. Add error handling (status: "failed")

### Step 2: Test Database Logging
1. Create integration test
2. Run test with simple simulation
3. Verify database contains correct records

### Step 3: Validate with HybridSolver
1. Run simulation with solver_type="hybrid"
2. Query database for hybrid runs
3. Verify KPIs are correct

### Step 4: Migrate Enhanced Schema (Optional)
1. Run `database_service.migrate_to_enhanced_schema()`
2. Enables GA/MC-specific tables
3. Future-proofs for Phase 2 & 3

---

## Key Files to Modify

**Primary**:
- `src/ecosystemiser/services/study_service.py`
  - `_run_simulations()` method
  - Add KPI calculation
  - Add database logging

**Testing**:
- `tests/integration/test_database_logging.py` (create new)

**Reference** (read-only):
- `src/ecosystemiser/services/database_metadata_service.py`
- `src/ecosystemiser/analyser/kpi_calculator.py`

---

## Success Criteria

✅ **Phase 1 Complete When**:
1. Every simulation run is logged to database with status
2. KPIs are calculated and stored
3. Integration test passes
4. HybridSolver runs appear in database
5. Can query simulations by study_id, solver_type, cost, etc.

---

## Next Steps (Phase 2 & 3)

**Phase 2: Results Explorer Dashboard**
- Streamlit dashboard for browsing runs
- Filterable table of all simulations
- Detailed view for individual runs

**Phase 3: Run Comparison Feature**
- Side-by-side comparison of 2+ runs
- Overlay plots of time-series data
- KPI difference analysis

---

## Notes

**Database Location**: `data/simulation_index.sqlite` (default)

**Thread Safety**: `DatabaseMetadataService` uses `sqlite_transaction` for safe concurrent access

**Event Bus**: StudyService already publishes events - could enhance to include database run_id

**GA/MC Support**: Enhanced schema ready via `migrate_to_enhanced_schema()` - enables:
- `study_runs` table for individual GA evaluations
- `convergence_metrics` for generation tracking
- `pareto_fronts` for multi-objective optimization
- `uncertainty_analysis` for Monte Carlo stats

---

**Status**: Plan complete, ready for implementation
**Estimated Time**: 2-3 hours for Phase 1 implementation + testing
**Dependencies**: None (all infrastructure exists)
**Risk**: Low (non-breaking addition to existing flow)

# Database Schema Design for GA/MC/MILP Results - Phase 2

**Date**: 2025-09-30
**Purpose**: Design centralized queryable database for optimization studies
**Status**: Design Complete - Ready for Implementation

---

## Executive Summary

The current `DatabaseMetadataService` only supports single simulation runs. This design extends it to support Genetic Algorithm (GA), Monte Carlo (MC), and MILP optimization studies with full query capabilities for thousands of runs.

**Key Enhancements**:
1. New tables for studies, study_runs, and optimization_results
2. Support for Pareto fronts, convergence tracking, uncertainty analysis
3. Fast queries for "top 10 designs", "compare studies", "parameter sensitivity"
4. Backward compatible with existing simulation_runs table

---

## Current State Analysis

### Existing Schema (`database_metadata_service.py`)

**Tables**:
- `simulation_runs`: Single simulation metadata + KPIs
- `studies`: Basic study tracking

**Limitations**:
1. No GA/MC optimization result storage
2. No parameter vector tracking
3. No Pareto front support
4. No generation/iteration tracking
5. Multiple syntax errors (15+ missing/trailing commas)

**Needs**:
1. Fix syntax errors (lines 78, 93-111, 171-189, 246-256, 273, 276, 280, 300, 328, 361, 409)
2. Add optimization-specific tables
3. Maintain backward compatibility

---

## Enhanced Schema Design

### Table 1: `studies` (Enhanced)

**Purpose**: Track optimization studies (GA, MC, or single simulations)

```sql
CREATE TABLE IF NOT EXISTS studies (
    study_id TEXT PRIMARY KEY,
    study_type TEXT NOT NULL,  -- NEW: 'genetic_algorithm', 'monte_carlo', 'single_simulation'
    study_name TEXT,
    description TEXT,

    -- Base configuration
    base_system_config_path TEXT,
    optimization_objective TEXT,  -- NEW: e.g., "total_cost,co2_emissions"
    optimization_constraints TEXT,  -- NEW: JSON of constraints

    -- Study parameters
    population_size INTEGER,  -- NEW: GA/MC sample count
    max_generations INTEGER,  -- NEW: GA generations
    max_evaluations INTEGER,  -- NEW: MC evaluations

    -- Status tracking
    status TEXT DEFAULT 'pending',  -- NEW: 'pending', 'running', 'completed', 'failed'
    progress_percent REAL,  -- NEW: 0-100

    -- Results summary
    run_count INTEGER DEFAULT 0,
    best_fitness REAL,  -- NEW: Best objective value found
    best_solution_id TEXT,  -- NEW: FK to study_runs

    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,  -- NEW
    execution_time_seconds REAL,  -- NEW
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_studies_type ON studies(study_type);
CREATE INDEX IF NOT EXISTS idx_studies_status ON studies(status);
CREATE INDEX IF NOT EXISTS idx_studies_best_fitness ON studies(best_fitness);
```

### Table 2: `study_runs` (NEW)

**Purpose**: Track individual evaluations within a study (GA individuals, MC samples)

```sql
CREATE TABLE IF NOT EXISTS study_runs (
    run_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    evaluation_number INTEGER,  -- Order within study (0-indexed)
    generation_number INTEGER,  -- For GA: which generation (NULL for MC)

    -- Parameter vector (decision variables)
    parameter_vector TEXT NOT NULL,  -- JSON array of parameter values
    parameter_names TEXT,  -- JSON array of parameter names

    -- Objectives and fitness
    fitness REAL NOT NULL,  -- Primary objective value
    objectives TEXT,  -- JSON array for multi-objective
    constraint_violations TEXT,  -- JSON of any constraint violations

    -- Simulation result reference
    simulation_run_id TEXT,  -- FK to simulation_runs (if simulation was executed)
    simulation_status TEXT DEFAULT 'success',  -- 'success', 'failed', 'infeasible'

    -- Performance tracking
    evaluation_time_seconds REAL,
    solver_time_seconds REAL,

    -- Domination tracking (for multi-objective)
    is_pareto_optimal BOOLEAN DEFAULT 0,
    domination_count INTEGER DEFAULT 0,  -- How many solutions dominate this one

    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT,

    FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_study_runs_study_id ON study_runs(study_id);
CREATE INDEX IF NOT EXISTS idx_study_runs_generation ON study_runs(study_id, generation_number);
CREATE INDEX IF NOT EXISTS idx_study_runs_fitness ON study_runs(fitness);
CREATE INDEX IF NOT EXISTS idx_study_runs_pareto ON study_runs(study_id, is_pareto_optimal);
CREATE INDEX IF NOT EXISTS idx_study_runs_evaluation_number ON study_runs(study_id, evaluation_number);
```

### Table 3: `pareto_fronts` (NEW)

**Purpose**: Store Pareto-optimal solutions for multi-objective optimization

```sql
CREATE TABLE IF NOT EXISTS pareto_fronts (
    pareto_id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL,
    generation_number INTEGER,  -- For GA: track front evolution (NULL for final)

    -- Front metadata
    front_size INTEGER,
    hypervolume REAL,  -- Quality metric for multi-objective fronts

    -- Reference to runs on this front (JSON array of run_ids)
    run_ids TEXT NOT NULL,  -- JSON array: ["run1", "run2", ...]

    -- Timestamp
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pareto_fronts_study_id ON pareto_fronts(study_id);
CREATE INDEX IF NOT EXISTS idx_pareto_fronts_generation ON pareto_fronts(study_id, generation_number);
```

### Table 4: `convergence_metrics` (NEW)

**Purpose**: Track optimization convergence over generations/iterations

```sql
CREATE TABLE IF NOT EXISTS convergence_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL,
    generation_number INTEGER NOT NULL,

    -- Convergence metrics
    best_fitness REAL,
    average_fitness REAL,
    worst_fitness REAL,
    fitness_std_dev REAL,

    -- Diversity metrics
    population_diversity REAL,  -- Measure of solution diversity
    stagnation_count INTEGER,  -- Generations without improvement

    -- Performance
    generation_time_seconds REAL,
    evaluations_in_generation INTEGER,

    -- Timestamp
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_convergence_study_gen ON convergence_metrics(study_id, generation_number);
```

### Table 5: `uncertainty_analysis` (NEW)

**Purpose**: Store Monte Carlo uncertainty and sensitivity analysis results

```sql
CREATE TABLE IF NOT EXISTS uncertainty_analysis (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL,

    -- Target design (the solution being analyzed)
    target_solution_id TEXT,  -- FK to study_runs

    -- Distribution statistics (per objective)
    objective_name TEXT,
    mean_value REAL,
    median_value REAL,
    std_dev REAL,
    percentile_5 REAL,
    percentile_25 REAL,
    percentile_50 REAL,
    percentile_75 REAL,
    percentile_95 REAL,

    -- Risk metrics
    var_95 REAL,  -- Value at Risk (95% confidence)
    cvar_95 REAL,  -- Conditional Value at Risk

    -- Timestamp
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE,
    FOREIGN KEY (target_solution_id) REFERENCES study_runs(run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_uncertainty_study ON uncertainty_analysis(study_id);
```

### Table 6: `sensitivity_analysis` (NEW)

**Purpose**: Store parameter sensitivity rankings from MC analysis

```sql
CREATE TABLE IF NOT EXISTS sensitivity_analysis (
    sensitivity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL,
    analysis_id INTEGER,  -- FK to uncertainty_analysis

    -- Parameter being analyzed
    parameter_name TEXT NOT NULL,
    parameter_index INTEGER,

    -- Sensitivity metrics
    correlation_coefficient REAL,  -- Linear correlation with objective
    rank_correlation REAL,  -- Spearman rank correlation
    sobol_first_order REAL,  -- Sobol first-order index
    sobol_total REAL,  -- Sobol total effect index

    -- Importance ranking
    importance_rank INTEGER,

    -- Timestamp
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES uncertainty_analysis(analysis_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sensitivity_study ON sensitivity_analysis(study_id);
CREATE INDEX IF NOT EXISTS idx_sensitivity_rank ON sensitivity_analysis(study_id, importance_rank);
```

### Table 7: `simulation_runs` (Keep Existing, Add FKs)

**Minimal changes** - just add foreign key relationships

```sql
-- Add to existing table (migration):
ALTER TABLE simulation_runs ADD COLUMN study_run_id TEXT;
ALTER TABLE simulation_runs ADD COLUMN study_id TEXT;

CREATE INDEX IF NOT EXISTS idx_simulation_runs_study_run_id ON simulation_runs(study_run_id);
```

---

## Query Examples & Use Cases

### Use Case 1: "Find Top 10 Lowest Cost Designs"

```sql
SELECT
    sr.run_id,
    sr.fitness as total_cost,
    sr.parameter_vector,
    sim.renewable_fraction,
    sim.self_sufficiency_rate
FROM study_runs sr
LEFT JOIN simulation_runs sim ON sr.simulation_run_id = sim.run_id
WHERE sr.study_id = 'my_ga_study'
  AND sr.simulation_status = 'success'
ORDER BY sr.fitness ASC
LIMIT 10;
```

**Performance**: <1ms with index on `fitness`

### Use Case 2: "Compare Two Studies Side-by-Side"

```sql
SELECT
    s.study_id,
    s.study_type,
    s.best_fitness,
    s.run_count,
    s.execution_time_seconds,
    (SELECT AVG(fitness) FROM study_runs WHERE study_id = s.study_id) as avg_fitness,
    (SELECT COUNT(*) FROM study_runs WHERE study_id = s.study_id AND is_pareto_optimal = 1) as pareto_count
FROM studies s
WHERE s.study_id IN ('study_1', 'study_2');
```

**Performance**: <10ms

### Use Case 3: "Get Convergence History for GA"

```sql
SELECT
    generation_number,
    best_fitness,
    average_fitness,
    fitness_std_dev,
    stagnation_count
FROM convergence_metrics
WHERE study_id = 'my_ga_study'
ORDER BY generation_number ASC;
```

**Use**: Plot convergence curves in reports

### Use Case 4: "Get Pareto Front for Multi-Objective"

```sql
SELECT
    sr.run_id,
    sr.objectives,
    sr.parameter_vector,
    sim.total_cost,
    sim.renewable_fraction
FROM study_runs sr
LEFT JOIN simulation_runs sim ON sr.simulation_run_id = sim.run_id
WHERE sr.study_id = 'my_moo_study'
  AND sr.is_pareto_optimal = 1
ORDER BY sr.fitness ASC;
```

**Use**: Generate Pareto front visualizations

### Use Case 5: "Get Uncertainty Analysis for Best Design"

```sql
SELECT
    ua.objective_name,
    ua.mean_value,
    ua.median_value,
    ua.std_dev,
    ua.percentile_5,
    ua.percentile_95,
    ua.var_95,
    ua.cvar_95
FROM uncertainty_analysis ua
WHERE ua.study_id = 'my_mc_study'
ORDER BY ua.objective_name;
```

**Use**: Risk assessment reports

### Use Case 6: "Get Sensitivity Rankings"

```sql
SELECT
    parameter_name,
    correlation_coefficient,
    sobol_total,
    importance_rank
FROM sensitivity_analysis
WHERE study_id = 'my_mc_study'
ORDER BY importance_rank ASC
LIMIT 10;
```

**Use**: Identify most influential parameters

---

## Integration with StudyService

### Current Flow (Single Simulation)
```
SimulationService.run_simulation()
  → SimulationResult
  → DatabaseMetadataService.log_simulation_run()
```

### Enhanced Flow (GA/MC Studies)

```python
# 1. Create study record at start
study_record = {
    "study_id": "ga_001",
    "study_type": "genetic_algorithm",
    "optimization_objective": "total_cost",
    "population_size": 50,
    "max_generations": 100,
    "status": "running",
}
db_service.create_study(study_record)

# 2. Log each evaluation as it completes
for evaluation in ga_evaluations:
    run_record = {
        "study_id": "ga_001",
        "evaluation_number": evaluation.index,
        "generation_number": evaluation.generation,
        "parameter_vector": json.dumps(evaluation.parameters),
        "fitness": evaluation.fitness,
        "objectives": json.dumps(evaluation.objectives),
    }
    db_service.log_study_run(run_record)

    # Also log the underlying simulation
    if evaluation.simulation_result:
        db_service.log_simulation_run(evaluation.simulation_result)

# 3. Log convergence metrics after each generation
convergence = {
    "study_id": "ga_001",
    "generation_number": gen_num,
    "best_fitness": generation.best_fitness,
    "average_fitness": generation.avg_fitness,
    # ...
}
db_service.log_convergence_metrics(convergence)

# 4. Update study status on completion
db_service.update_study_status("ga_001", "completed", best_fitness=final_best)
```

---

## Implementation Plan

### Phase 2.1: Schema Enhancement (Week 3, Day 1-2)

**Tasks**:
1. Fix syntax errors in `database_metadata_service.py`
2. Add new tables to schema SQL
3. Create migration script for existing databases
4. Add new logging methods:
   - `create_study()`
   - `log_study_run()`
   - `log_convergence_metrics()`
   - `log_pareto_front()`
   - `log_uncertainty_analysis()`
   - `log_sensitivity_analysis()`

**Deliverable**: Enhanced DatabaseMetadataService with GA/MC support

### Phase 2.2: Query Interface (Week 3, Day 3-4)

**Tasks**:
1. Add query methods:
   - `query_study_runs()` - filter by study, generation, fitness
   - `get_pareto_front()` - get Pareto-optimal solutions
   - `get_convergence_history()` - get generation-by-generation metrics
   - `get_best_designs()` - top N by fitness
   - `compare_studies()` - side-by-side comparison
   - `get_uncertainty_summary()` - MC risk metrics
   - `get_sensitivity_rankings()` - parameter importance

**Deliverable**: Complete query API for optimization results

### Phase 2.3: StudyService Integration (Week 3, Day 5)

**Tasks**:
1. Modify `StudyService._create_fitness_function()` to log each evaluation
2. Add generation-level logging in GA loop
3. Add MC uncertainty logging after analysis
4. Test with small GA run (10 pop × 5 gen = 50 evaluations)

**Deliverable**: Auto-save GA/MC results to database

### Phase 2.4: CLI Implementation (Week 4, Day 1-2)

**Tasks**:
1. Add CLI commands:
   ```bash
   hive-cli query list-studies --type ga --status completed
   hive-cli query best-designs --study-id ga_001 --limit 10
   hive-cli query compare --study-ids ga_001,mc_002
   hive-cli query pareto-front --study-id moo_001 --output chart.png
   hive-cli query convergence --study-id ga_001 --output convergence.png
   ```

**Deliverable**: Complete CLI for database queries

---

## Performance Considerations

### Scalability Analysis

**For 100 GA Studies × 50 pop × 100 gen = 500,000 evaluations**:

| Table | Rows | Row Size | Total Size | Query Time |
|-------|------|----------|------------|------------|
| studies | 100 | 500 bytes | 50 KB | <1ms |
| study_runs | 500,000 | 300 bytes | 150 MB | <10ms with indexes |
| convergence_metrics | 10,000 | 100 bytes | 1 MB | <5ms |
| simulation_runs | 500,000 | 500 bytes | 250 MB | <10ms with indexes |
| **Total** | **~1M rows** | - | **~400 MB** | **<50ms worst case** |

**Conclusion**: SQLite can handle 1M+ rows efficiently with proper indexing

### Index Strategy

**Critical Indexes** (already in design):
- `study_runs.study_id` - for study filtering
- `study_runs.fitness` - for best design queries
- `study_runs.is_pareto_optimal` - for Pareto front queries
- `convergence_metrics.study_id, generation_number` - for convergence plots

**Optional Indexes** (add if needed):
- `study_runs.generation_number` - if frequently querying specific generations
- `study_runs.evaluation_number` - if frequently querying evaluation order

---

## Migration Strategy

### Backward Compatibility

**Existing Code**:
```python
# This still works unchanged
db_service = DatabaseMetadataService()
db_service.log_simulation_run(simulation_result)
```

**Enhanced Code**:
```python
# New functionality - opt-in
db_service.create_study(study_config)
db_service.log_study_run(evaluation_result)
```

### Database Migration

```python
def migrate_database_v1_to_v2(db_path):
    """Migrate existing database to v2 schema."""
    with sqlite_transaction(db_path=db_path) as conn:
        # Add new tables
        conn.executescript(ENHANCED_SCHEMA_SQL)

        # Add new columns to existing tables
        try:
            conn.execute("ALTER TABLE simulation_runs ADD COLUMN study_run_id TEXT")
            conn.execute("ALTER TABLE simulation_runs ADD COLUMN study_id TEXT")
        except sqlite3.OperationalError:
            pass  # Columns already exist

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_simulation_runs_study_run_id ON simulation_runs(study_run_id)")
```

**No data loss** - all existing records remain unchanged

---

## Testing Strategy

### Unit Tests

```python
def test_create_study():
    """Test study creation"""
    db = DatabaseMetadataService(":memory:")
    study = {"study_id": "test_ga", "study_type": "genetic_algorithm"}
    assert db.create_study(study)

def test_log_study_run():
    """Test evaluation logging"""
    db = DatabaseMetadataService(":memory:")
    run = {"study_id": "test_ga", "evaluation_number": 0, "fitness": 42.5}
    assert db.log_study_run(run)

def test_query_best_designs():
    """Test best design query"""
    # Log 10 runs with different fitness values
    # Query top 3
    # Assert correct order
```

### Integration Tests

```python
def test_ga_study_workflow():
    """Test full GA study workflow"""
    db = DatabaseMetadataService(":memory:")

    # Create study
    study_id = "integration_ga"
    db.create_study({"study_id": study_id, "study_type": "genetic_algorithm"})

    # Log 50 evaluations across 5 generations
    for gen in range(5):
        for ind in range(10):
            db.log_study_run({
                "study_id": study_id,
                "evaluation_number": gen * 10 + ind,
                "generation_number": gen,
                "fitness": random.uniform(100, 200),
            })

        # Log convergence
        db.log_convergence_metrics({
            "study_id": study_id,
            "generation_number": gen,
            "best_fitness": 100 + gen * 10,
        })

    # Query results
    best = db.get_best_designs(study_id, limit=5)
    assert len(best) == 5
    assert best[0]["fitness"] < best[1]["fitness"]  # Ascending order

    convergence = db.get_convergence_history(study_id)
    assert len(convergence) == 5
```

---

## Success Metrics

### Functional Requirements
- ✅ Store 100,000+ GA/MC evaluations without performance degradation
- ✅ Query top 10 designs in <10ms
- ✅ Compare 2-5 studies in <50ms
- ✅ Retrieve Pareto front in <20ms
- ✅ Get convergence history in <10ms

### Non-Functional Requirements
- ✅ Backward compatible with existing simulation logging
- ✅ Database size <500MB for 1M evaluations
- ✅ Support concurrent reads (multiple CLI queries)
- ✅ Zero data loss on migration

---

## Future Enhancements (Post Phase 2)

### Phase 3+ Possibilities

1. **Distributed Storage**
   - PostgreSQL backend for multi-user scenarios
   - Cloud storage integration (S3 for result files)

2. **Real-Time Monitoring**
   - WebSocket updates for live optimization progress
   - Dashboard for active studies

3. **Advanced Analytics**
   - Clustering analysis of solution space
   - Transfer learning (use past studies to seed new ones)
   - Meta-optimization (optimize GA parameters based on past performance)

4. **Visualization Service**
   - Auto-generate charts from database
   - Interactive Pareto front explorer
   - Parameter sensitivity heatmaps

---

## Conclusion

This enhanced schema provides a solid foundation for storing and querying GA/MC/MILP optimization results. The design is:
- **Scalable**: Handles 1M+ evaluations efficiently
- **Queryable**: Fast queries for common use cases
- **Backward Compatible**: Existing code continues to work
- **Extensible**: Easy to add new metrics and analysis types

**Next Step**: Implement Phase 2.1 (schema enhancement) in next session
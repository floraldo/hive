# Systemiser Refactoring Plan

**Status:** Actively Refactoring - Solver & Balance Checks Refactored, Debugging Rule-Based Solver

This document outlines the plan to refactor the existing energy system simulation and optimization code into a modular and robust tool named "Systemiser".

**Goal:** Create a well-structured tool capable of defining, solving (via rule-based simulation or MILP optimization), analyzing, and visualizing energy systems.

**Approach:** Incremental refactoring, starting with a working script (`run.py`) within the `Systemiser` folder and gradually moving dependencies into a defined modular structure within this folder. Testing will be integrated early.

**Initial State:**
- `Systemiser/run.py`: Based on `SankeyDiagram/data/test_complex_system.py`. Relies on external dependencies via `sys.path` adjustments. Initial balance violations identified.

**Proposed Modular Structure (within `Systemiser/`):**
- `data/`: Scenario-specific input data, configuration files.
- `system/`: Core component and system class definitions (from `model/`).
- `Systemiser/solver/`: Solver implementations (Rule-based, MILP).
- `analysis/`: Post-processing logic and analyst services.
- `datavis/`: Plotting, Sankey generation, other visualizations.
- `utils/`: Common helper functions (logging, normalization, system setup).
- `io/`: Input/output functions (e.g., results saving).
- `tests/`: Unit and integration tests using `pytest`.

**Refactoring Steps:**

1.  **Establish Base:**
    *   [x] Create `Systemiser` folder.
    *   [x] Create `Systemiser/README.md` (this file).
    *   [x] Create `Systemiser/run.py` based on `SankeyDiagram/data/test_complex_system.py` with temporary `sys.path` adjustments.
    *   [x] Verify `run.py` executes (though with known balance errors).
2.  **Integrate Utilities (Logger & Testing):**
    *   [x] Create `Systemiser/utils/` directory.
    *   [x] Move `SankeyDiagram/data/logger.py` to `Systemiser/utils/logger.py` (with minor improvements).
    *   [x] Update `Systemiser/run.py` to import and use the new logger from `Systemiser.utils.logger`.
    *   [x] Create `Systemiser/tests/` and `Systemiser/tests/utils/` directories.
    *   [x] Create basic test file `Systemiser/tests/utils/test_logger.py`.
    *   [x] Run `pytest` to confirm logger tests pass.
3.  **Move Core System Models:**
    *   [x] Create `Systemiser/system/` directory.
    *   [x] Identify and move component classes and the `System` class from `model/` into `Systemiser/system/` (assuming component definitions were implicitly moved or are stand-alone).
    *   [x] Update `Systemiser/run.py` to import from `Systemiser.system` instead of `model`.
    *   [x] Remove `model/` path adjustment from `run.py`.
    *   [x] Add tests for core system/component logic in `Systemiser/tests/system/test_system_setup.py`.
4.  **Integrate & Refactor Rule-Based Solver:**
    *   [x] Create `Systemiser/solver/` directory.
    *   [x] Move `ComponentBasedRuleEngine` class from `SankeyDiagram/data/rule_engine_component.py` into `Systemiser/solver/rule_based_solver.py`.
    *   [x] Update `Systemiser/run.py` to import the engine from `Systemiser.solver.rule_based_solver`.
    *   [x] **Refactor Solver:** Modified engine to directly use `system.flows` for flow calculation and storage updates. Removed complex helper methods.
    *   [x] **Debug Balance Violation:** Iteratively adjusted efficiency logic (charge/discharge potentials) in `_get_system_state`.
    *   [ ] **Current Issue:** Persistent energy balance violations remain, primarily in early timesteps. Requires further debugging of state calculations, efficiency application, or potentially input data review.
    *   [ ] Add comprehensive tests for the rule engine in `Systemiser/tests/solver/`.
5.  **Integrate System Setup/Saving Logic:**
    *   [x] Analyze `SankeyDiagram/data/solve_system_simple.py`.
    *   [x] Move `create_system` function (and helpers) into `Systemiser/utils/system_setup.py`.
    *   [x] Create `Systemiser/io/` directory.
    *   [x] Move `save_system_results` function into `Systemiser/io/results.py`.
    *   [x] Update `Systemiser/run.py` to use these new locations.
    *   [x] Update balance verification functions (`verify_energy_balance`, `verify_water_balance`) in `run.py` to align with solver logic (read from `system.flows`).
    *   [x] Add basic tests for system setup in `Systemiser/tests/utils/test_system_setup.py`.
    *   [ ] Add tests for results saving in `Systemiser/tests/io/`.
6.  **Integrate MILP Solver:** (Requires analysing `solve_system.py` from root and `System` class methods)
    *   [ ] Create `Systemiser/solver/milp_solver.py`.
    *   [ ] Refactor MILP setup (objective, constraints, solve call) logic into an `MILPSolver` class.
    *   [ ] Adapt `run.py` to optionally use the `MILPSolver`.
    *   [ ] Consider using MILP solver results to validate/debug the rule-based solver once stable.
    *   [ ] Add tests for the MILP solver.
7.  **Integrate Analysis:**
    *   [ ] Create `Systemiser/analysis/` directory.
    *   [ ] Move logic from `post_solve.py` (root) and relevant analyst services here.
    *   [ ] Create `run_analysis.py` or integrate into `run.py`.
    *   [ ] Add tests for analysis functions.
8.  **Integrate Data Visualization:**
    *   [ ] Create `Systemiser/datavis/` directory.
    *   [ ] Move `plot_results.py` (root) and plotting utilities here.
    *   [ ] Refactor Sankey JSON generation logic into `Systemiser/datavis/generate_sankey_json.py`.
    *   [ ] Move Sankey visualizer code (JS, HTML, CSS) into `Systemiser/datavis/sankey_visualizer/`.
    *   [ ] Add tests for plotting functions (if feasible).
9.  **Consolidate Data Input:**
    *   [ ] Move relevant scenario data from `SankeyDiagram/data/schoonschip_sc1/` etc. into `Systemiser/data/scenarios/`.
    *   [ ] Refactor data loading (profiles, parameters) to read from `Systemiser/data/`.
10. **Cleanup:**
    *   [x] Remove temporary `sys.path` modifications in `run.py`.
    *   [ ] Delete original, now redundant, files from `SankeyDiagram/` and workspace root after successful migration and testing.

**Tracking:**
- Use checkboxes above to track progress.
- Add notes or deviations as needed. 
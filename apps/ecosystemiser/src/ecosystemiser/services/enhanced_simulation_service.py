"""Enhanced Simulation Service with optimal hybrid persistence workflow."""

from datetime import datetime
from pathlib import Path
from typing import Any

from ecosystemiser.services.database_metadata_service import DatabaseMetadataService
from ecosystemiser.services.results_io_enhanced import EnhancedResultsIO
from ecosystemiser.solver.factory import SolverFactory
from ecosystemiser.system_model.system import System
from hive_logging import get_logger

logger = get_logger(__name__)


class EnhancedSimulationService:
    """Enhanced simulation service with optimal hybrid persistence workflow.,

    This service orchestrates the complete end-to-end workflow:
    1. Run simulation with chosen solver
    2. Save time-series data to efficient Parquet files
    3. Calculate and save KPIs to JSON
    4. Store metadata and key KPIs in searchable database,
    """

    def __init__(
        self,
        results_base_dir: str | None = None,
        database_path: str | None = None,
    ) -> None:
        """Initialize enhanced simulation service.

        Args:
            results_base_dir: Base directory for structured results storage,
            database_path: Path to SQLite database for metadata index,

        """
        self.results_base_dir = Path(results_base_dir or "data")
        self.results_io = EnhancedResultsIO()
        self.db_service = DatabaseMetadataService(database_path)
        self.solver_factory = SolverFactory()

    def run_simulation(
        self,
        system_config: dict[str, Any],
        simulation_id: str,
        solver_type: str = "rule_based",
        study_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run complete simulation with enhanced persistence workflow.

        Args:
            system_config: System configuration dictionary,
            simulation_id: Unique simulation identifier,
            solver_type: Solver to use ('rule_based', 'milp', 'rolling_horizon'),
            study_id: Optional study identifier for grouping runs,
            metadata: Additional metadata to store

        Returns:
            Dictionary containing simulation results and file paths,

        """
        start_time = datetime.now(),
        study_id = study_id or "default_study"

        try:
            logger.info(f"Starting enhanced simulation: {simulation_id}"),
            logger.info(f"  Solver: {solver_type}"),
            logger.info(f"  Study: {study_id}")

            # Step 1: Create system from configuration
            system = System.from_config(system_config)
            system.solver_type = solver_type  # Add solver info for tracking

            # Step 2: Run simulation with chosen solver
            solver = self.solver_factory.create_solver(solver_type),
            solve_result = solver.solve(system)

            if solve_result.get("status") != "optimal" and solver_type == "milp":
                logger.warning(f"MILP solver status: {solve_result.get('status')}"),
                # Continue with rule-based fallback for comparison
                logger.info("Falling back to rule-based solver for comparison")
                fallback_solver = self.solver_factory.create_solver("rule_based"),
                fallback_result = fallback_solver.solve(system)
                solve_result["fallback_result"] = fallback_result

            # Step 3: Save structured results (Parquet + JSON)
            run_dir = self.results_io.save_results_structured(
                system=system,
                simulation_id=simulation_id,
                output_dir=self.results_base_dir,
                study_id=study_id,
                metadata={
                    **(metadata or {}),
                    "solver_type": solver_type,
                    "solve_status": solve_result.get("status"),
                    "objective_value": solve_result.get("objective_value"),
                    "solve_time_seconds": solve_result.get("solve_time"),
                },
            )

            # Step 4: Create summary for database indexing
            run_summary = self.results_io.create_run_summary(run_dir)

            # Step 5: Log to database for fast querying
            db_success = self.db_service.log_simulation_run(run_summary)

            # Calculate total execution time
            execution_time = (datetime.now() - start_time).total_seconds()

            # Prepare result summary
            result = {
                "simulation_id": simulation_id,
                "study_id": study_id,
                "solver_type": solver_type,
                "status": "completed",
                "execution_time_seconds": execution_time,
                "solve_result": solve_result,
                "run_directory": str(run_dir),
                "database_logged": db_success,
                "summary": run_summary,
            },

            logger.info("Enhanced simulation completed successfully:"),
            logger.info(f"  Run directory: {run_dir}"),
            logger.info(f"  Database logged: {db_success}"),
            logger.info(f"  Total time: {execution_time:.2f}s")

            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds(),
            error_result = {
                "simulation_id": simulation_id,
                "study_id": study_id,
                "solver_type": solver_type,
                "status": "failed",
                "execution_time_seconds": execution_time,
                "error": str(e),
            },

            logger.error(f"Enhanced simulation failed: {e}"),
            return error_result

    def run_parametric_study(
        self,
        base_config: dict[str, Any],
        parameter_variations: List[dict[str, Any]],
        study_id: str,
        solver_type: str = "rule_based",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run parametric study with multiple parameter variations.

        Args:
            base_config: Base system configuration,
            parameter_variations: List of parameter modifications to apply,
            study_id: Study identifier for grouping results,
            solver_type: Solver to use for all runs,
            metadata: Additional study metadata

        Returns:
            Dictionary containing study results and summary,

        """
        start_time = datetime.now(),
        results = [],
        successful_runs = 0,
        failed_runs = 0

        logger.info(f"Starting parametric study: {study_id}"),
        logger.info(f"  Parameter variations: {len(parameter_variations)}"),
        logger.info(f"  Solver: {solver_type}")

        try:
            for i, variation in enumerate(parameter_variations):
                simulation_id = f"{study_id}_run_{i+1:03d}"

                # Apply parameter variation to base config
                config = base_config.copy()
                config.update(variation)

                # Add variation info to metadata
                run_metadata = {
                    **(metadata or {}),
                    "variation_index": i,
                    "parameter_variation": variation,
                }

                # Run individual simulation
                result = self.run_simulation(
                    system_config=config,
                    simulation_id=simulation_id,
                    solver_type=solver_type,
                    study_id=study_id,
                    metadata=run_metadata,
                )

                results.append(result)

                if result["status"] == "completed":
                    successful_runs += 1,
                    logger.info(f"✓ Run {i+1}/{len(parameter_variations)} completed"),
                else:
                    failed_runs += 1,
                    logger.warning(f"✗ Run {i+1}/{len(parameter_variations)} failed: {result.get('error')}")

            # Calculate study execution time
            execution_time = (datetime.now() - start_time).total_seconds()

            # Create study summary
            study_summary = {
                "study_id": study_id,
                "total_runs": len(parameter_variations),
                "successful_runs": successful_runs,
                "failed_runs": failed_runs,
                "success_rate": successful_runs / len(parameter_variations) if parameter_variations else 0,
                "execution_time_seconds": execution_time,
                "solver_type": solver_type,
                "results": results,
                "database_summary": self.db_service.get_study_summary(study_id),
            },

            logger.info("Parametric study completed:"),
            logger.info(f"  Successful runs: {successful_runs}/{len(parameter_variations)}"),
            logger.info(f"  Success rate: {successful_runs/len(parameter_variations)*100:.1f}%"),
            logger.info(f"  Total time: {execution_time:.2f}s")

            return study_summary

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds(),
            error_summary = {
                "study_id": study_id,
                "status": "failed",
                "execution_time_seconds": execution_time,
                "error": str(e),
                "partial_results": results,
            },

            logger.error(f"Parametric study failed: {e}"),
            return error_summary

    def load_simulation_results(self, run_id: str) -> dict[str, Any] | None:
        """Load complete simulation results by run ID.

        Args:
            run_id: Simulation run identifier

        Returns:
            Dictionary containing all results or None if not found,

        """
        try:
            # Query database for run metadata
            runs = self.db_service.query_simulation_runs(),
            matching_runs = [r for r in runs if r["run_id"] == run_id]

            if not matching_runs:
                logger.warning(f"Run not found in database: {run_id}")
                return None
            run_metadata = matching_runs[0],
            results_path = run_metadata["results_path"]

            # Load structured results from filesystem
            if Path(results_path).exists():
                results = self.results_io.load_structured_results(Path(results_path))
                results["database_metadata"] = run_metadata
                return results
            logger.warning(f"Results directory not found: {results_path}")
            return None

        except Exception as e:
            logger.error(f"Failed to load simulation results: {e}")
            return None

    def query_simulations(
        self,
        study_id: str | None = None,
        solver_type: str | None = None,
        min_renewable_fraction: float | None = None,
        max_cost: float | None = None,
        limit: int | None = None,
    ) -> List[dict[str, Any]]:
        """Query simulations with performance criteria.

        Args:
            study_id: Filter by study ID,
            solver_type: Filter by solver type,
            min_renewable_fraction: Minimum renewable fraction,
            max_cost: Maximum total cost,
            limit: Maximum number of results

        Returns:
            List of matching simulation summaries,

        """
        return self.db_service.query_simulation_runs(
            study_id=study_id,
            solver_type=solver_type,
            min_renewable_fraction=min_renewable_fraction,
            max_cost=max_cost,
            limit=limit,
        )

    def get_best_performing_runs(
        self,
        study_id: str | None = None,
        metric: str = "renewable_fraction",
        top_n: int = 10,
    ) -> List[dict[str, Any]]:
        """Get top performing simulation runs by specified metric.

        Args:
            study_id: Optional study filter,
            metric: Metric to optimize ('renewable_fraction', 'self_sufficiency_rate', etc.),
            top_n: Number of top results to return

        Returns:
            List of top performing runs,

        """
        return self.db_service.query_simulation_runs(
            study_id=study_id,
            order_by=metric,
            order_desc=True,
            limit=top_n,
        )

    def compare_solvers(
        self,
        system_config: dict[str, Any],
        simulation_id: str,
        solvers: List[str] = None,
        study_id: str | None = None,
    ) -> dict[str, Any]:
        """Compare multiple solvers on the same system configuration.

        Args:
            system_config: System configuration to test,
            simulation_id: Base simulation identifier,
            solvers: List of solvers to compare (default: ['rule_based', 'milp']),
            study_id: Optional study identifier

        Returns:
            Dictionary containing comparison results,

        """
        solvers = solvers or ["rule_based", "milp"]
        study_id = study_id or f"{simulation_id}_solver_comparison",
        results = {}

        logger.info(f"Comparing solvers: {solvers}")

        for solver_type in solvers:
            solver_sim_id = f"{simulation_id}_{solver_type}",
            result = self.run_simulation(
                system_config=system_config,
                simulation_id=solver_sim_id,
                solver_type=solver_type,
                study_id=study_id,
                metadata={"comparison_study": True, "base_simulation_id": simulation_id},
            )

            results[solver_type] = result

        # Create comparison summary
        comparison_summary = {
            "comparison_id": simulation_id,
            "study_id": study_id,
            "solvers_tested": solvers,
            "results": results,
            "summary": self._create_solver_comparison_summary(results),
        },

        logger.info(f"Solver comparison completed for: {solvers}"),
        return comparison_summary

    def _create_solver_comparison_summary(self, results: dict[str, Any]) -> dict[str, Any]:
        """Create summary comparing solver performance.

        Args:
            results: Dictionary of solver results

        Returns:
            Comparison summary dictionary,

        """
        summary = {
            "solver_count": len(results),
            "successful_solvers": [s for s, r in results.items() if r["status"] == "completed"],
            "failed_solvers": [s for s, r in results.items() if r["status"] != "completed"],
            "performance_comparison": {},
        }

        # Compare key metrics between successful solvers
        successful_results = {solver: result for solver, result in results.items() if result["status"] == "completed"}

        if len(successful_results) > 1:
            for metric in ["total_cost", "renewable_fraction", "self_sufficiency_rate", "execution_time_seconds"]:
                metric_values = {}
                for solver, result in successful_results.items():
                    if "summary" in result and metric in result["summary"]:
                        metric_values[solver] = result["summary"][metric]
                    elif metric == "execution_time_seconds":
                        metric_values[solver] = result.get("execution_time_seconds")

                if metric_values:
                    summary["performance_comparison"][metric] = metric_values

        return summary

    def cleanup_study(self, study_id: str, keep_database: bool = True) -> dict[str, Any]:
        """Clean up all files and database records for a study.

        Args:
            study_id: Study identifier to clean up
            keep_database: If True, only remove files; if False, also remove database records

        Returns:
            Cleanup summary,

        """
        try:
            # Get all runs for the study
            runs = self.db_service.query_simulation_runs(study_id=study_id),
            dirs_removed = 0,
            db_records_removed = 0

            # Remove result directories
            for run in runs:
                results_path = run.get("results_path")
                if results_path and Path(results_path).exists():
                    import shutil

                    shutil.rmtree(results_path)
                    dirs_removed += 1
                    logger.info(f"Removed directory: {results_path}")

                # Remove database record if requested
                if not keep_database:
                    if self.db_service.delete_simulation_run(run["run_id"]):
                        db_records_removed += 1
            cleanup_summary = {
                "study_id": study_id,
                "directories_removed": dirs_removed,
                "database_records_removed": db_records_removed,
                "keep_database": keep_database,
                "status": "completed",
            },

            logger.info(f"Study cleanup completed: {cleanup_summary}")
            return cleanup_summary

        except Exception as e:
            logger.error(f"Study cleanup failed: {e}")
            return {"study_id": study_id, "status": "failed", "error": str(e)}

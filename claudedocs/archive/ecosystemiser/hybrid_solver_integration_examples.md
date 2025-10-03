# Hybrid Solver - Integration Examples

**Component**: `ecosystemiser.solver.hybrid_solver`
**Status**: Production Ready
**Date**: 2025-10-02

## Overview

This document provides practical integration examples for using the Hybrid Solver in various scenarios including GA workflows, Monte Carlo simulations, and custom optimization pipelines.

---

## Example 1: Basic Usage - Standalone Optimization

The simplest way to use the Hybrid Solver for a single optimization run.

```python
from ecosystemiser.solver.factory import SolverFactory
from ecosystemiser.solver.rolling_horizon_milp import RollingHorizonConfig

# Load your energy system (use existing system loading logic)
system = load_energy_system("config/systems/golden_residential_microgrid.yml")

# Configure hybrid solver for 1-week simulation
config = RollingHorizonConfig(
    warmstart=True,        # Enable warm-start (REQUIRED for hybrid)
    horizon_hours=168,     # 1-week rolling windows
    overlap_hours=24,      # 1-day overlap between windows
)

# Create and run solver
solver = SolverFactory.get_solver("hybrid", system, config)
result = solver.solve()

# Check results
if result.status in ["optimal", "feasible"]:
    print(f"✅ Optimization successful!")
    print(f"   Solve time: {result.solve_time:.1f}s")
    print(f"   Status: {result.status}")

    # Extract system flows and costs
    total_cost = calculate_total_cost(system)
    print(f"   Total cost: €{total_cost:,.2f}")
else:
    print(f"❌ Optimization failed: {result.message}")
```

**When to use**: Single-shot optimizations, validation runs, debugging

---

## Example 2: Yearly Simulation (8760h)

Optimizing a full year of energy system operation.

```python
from ecosystemiser.solver.factory import SolverFactory
from ecosystemiser.solver.rolling_horizon_milp import RollingHorizonConfig
import time

# Load system with 8760-hour profiles
system = load_energy_system_with_yearly_profiles(
    "config/systems/residential_system.yml",
    profile_year=2024
)

# Configure for yearly optimization
config = RollingHorizonConfig(
    warmstart=True,
    horizon_hours=168,     # 1-week windows (recommended)
    overlap_hours=24,      # 1-day overlap
)

print(f"Optimizing {system.N}h simulation...")
print(f"Expected windows: ~{system.N // (168 - 24)} windows")
print(f"Estimated time: ~10 minutes")

start = time.time()
solver = SolverFactory.get_solver("hybrid", system, config)
result = solver.solve()
elapsed = time.time() - start

print(f"\nResults:")
print(f"  Status: {result.status}")
print(f"  Actual time: {elapsed / 60:.1f} minutes")
print(f"  Message: {result.message}")

# Analyze yearly performance
annual_costs = analyze_annual_costs(system)
print(f"\nAnnual Performance:")
print(f"  Total energy cost: €{annual_costs['total']:,.2f}")
print(f"  Grid import cost: €{annual_costs['grid_import']:,.2f}")
print(f"  Solar utilization: {annual_costs['solar_fraction']:.1%}")
```

**When to use**: Annual energy planning, TCO analysis, long-term optimization

---

## Example 3: Genetic Algorithm Integration

Using Hybrid Solver as the fitness function for design optimization.

```python
from ecosystemiser.discovery.algorithms.genetic_algorithm import (
    GeneticAlgorithm,
    GeneticAlgorithmConfig,
)
from ecosystemiser.solver.factory import SolverFactory
from ecosystemiser.solver.rolling_horizon_milp import RollingHorizonConfig
import numpy as np


class YearlyEnergySystemFitness:
    """Fitness function for GA using Hybrid Solver for yearly evaluations."""

    def __init__(self, base_system_config: str, profile_year: int = 2024):
        """Initialize fitness function.

        Args:
            base_system_config: Path to base system YAML
            profile_year: Year for weather/demand profiles
        """
        self.base_system_config = base_system_config
        self.profile_year = profile_year

        # Hybrid solver configuration (reused across evaluations)
        self.solver_config = RollingHorizonConfig(
            warmstart=True,
            horizon_hours=168,
            overlap_hours=24,
        )

        self.evaluation_count = 0

    def evaluate(self, design_vars: np.ndarray) -> dict:
        """Evaluate energy system design.

        Args:
            design_vars: [solar_kw, battery_kwh, wind_count]

        Returns:
            dict with 'fitness' and performance metrics
        """
        self.evaluation_count += 1
        solar_kw, battery_kwh, wind_count = design_vars

        # Create system with design parameters
        system = self._create_system_from_design(solar_kw, battery_kwh, int(wind_count))

        # Optimize with Hybrid Solver
        solver = SolverFactory.get_solver("hybrid", system, self.solver_config)
        result = solver.solve()

        if result.status == "error":
            # Penalize failed designs
            return {"fitness": 1e9, "valid": False, "error": result.message}

        # Calculate Total Cost of Ownership (20-year horizon)
        capex = self._calculate_capex(solar_kw, battery_kwh, wind_count)
        opex_annual = self._calculate_opex(system)
        tco = capex + (opex_annual * 20)  # 20-year TCO

        # Performance metrics
        metrics = {
            "fitness": tco / 1_000_000,  # Millions EUR (to minimize)
            "valid": True,
            "capex_eur": capex,
            "opex_annual_eur": opex_annual,
            "tco_20y_eur": tco,
            "solve_time_sec": result.solve_time,
            "solver_status": result.status,
        }

        if self.evaluation_count % 10 == 0:
            print(
                f"Eval {self.evaluation_count}: "
                f"Solar={solar_kw:.0f}kW, Battery={battery_kwh:.0f}kWh, "
                f"Wind={wind_count:.0f}, TCO=€{tco/1e6:.2f}M ({result.solve_time:.1f}s)"
            )

        return metrics

    def _create_system_from_design(self, solar_kw, battery_kwh, wind_count):
        """Create energy system with specified design parameters."""
        # Load base system
        system = load_energy_system(self.base_system_config, horizon=8760)

        # Update component capacities
        system.components["solar"].capacity = solar_kw
        system.components["battery"].capacity = battery_kwh
        # ... configure wind turbines, etc.

        return system

    def _calculate_capex(self, solar_kw, battery_kwh, wind_count):
        """Calculate capital expenditure."""
        solar_cost = solar_kw * 1200  # €1200/kW
        battery_cost = battery_kwh * 600  # €600/kWh
        wind_cost = wind_count * 25000  # €25k per 10kW turbine
        return solar_cost + battery_cost + wind_cost

    def _calculate_opex(self, system):
        """Calculate annual operating expenditure from optimized system."""
        # Extract grid import from optimized flows
        grid_import_kwh = np.sum(system.flows["grid_to_load"]["value"])
        grid_cost_per_kwh = 0.20
        annual_grid_cost = grid_import_kwh * grid_cost_per_kwh

        # Add O&M costs
        om_cost = 5000  # Annual O&M
        return annual_grid_cost + om_cost


# GA Configuration
ga_config = GeneticAlgorithmConfig(
    dimensions=3,
    bounds=[
        (50.0, 500.0),     # Solar: 50-500 kW
        (100.0, 1000.0),   # Battery: 100-1000 kWh
        (0.0, 5.0),        # Wind: 0-5 turbines
    ],
    objectives=["fitness"],  # Minimize TCO
    population_size=20,      # Small population for speed
    max_generations=50,      # Limit iterations
    mutation_rate=0.15,
    crossover_rate=0.8,
)

# Create fitness function
fitness = YearlyEnergySystemFitness(
    base_system_config="config/systems/residential_base.yml",
    profile_year=2024
)

# Run GA optimization
print("Starting GA optimization with Hybrid Solver...")
print(f"Population: {ga_config.population_size}, Generations: {ga_config.max_generations}")
print(f"Expected evaluations: {ga_config.population_size * ga_config.max_generations}")
print(f"Estimated time: ~{ga_config.population_size * ga_config.max_generations * 10 / 60:.0f} minutes\n")

ga = GeneticAlgorithm(ga_config, fitness_function=fitness.evaluate)
best_solution = ga.optimize()

print("\n" + "=" * 80)
print("OPTIMIZATION COMPLETE")
print("=" * 80)
print(f"Best design:")
print(f"  Solar: {best_solution.best_individual[0]:.1f} kW")
print(f"  Battery: {best_solution.best_individual[1]:.1f} kWh")
print(f"  Wind turbines: {int(best_solution.best_individual[2])}")
print(f"  20-year TCO: €{best_solution.best_fitness * 1e6:,.0f}")
print(f"  Total evaluations: {fitness.evaluation_count}")
```

**When to use**: Design optimization, capacity planning, Pareto front exploration

---

## Example 4: Monte Carlo Uncertainty Analysis

Using Hybrid Solver for stochastic optimization under uncertainty.

```python
from ecosystemiser.solver.factory import SolverFactory
from ecosystemiser.solver.rolling_horizon_milp import RollingHorizonConfig
import numpy as np


class MonteCarloEnergyAnalysis:
    """Monte Carlo analysis using Hybrid Solver for scenario evaluations."""

    def __init__(self, base_design: dict, num_scenarios: int = 100):
        """Initialize MC analysis.

        Args:
            base_design: Baseline system design parameters
            num_scenarios: Number of MC scenarios to simulate
        """
        self.base_design = base_design
        self.num_scenarios = num_scenarios

        # Hybrid solver config
        self.solver_config = RollingHorizonConfig(
            warmstart=True,
            horizon_hours=168,
            overlap_hours=24,
        )

    def run_analysis(self):
        """Run Monte Carlo analysis across weather scenarios."""
        print(f"Running Monte Carlo analysis: {self.num_scenarios} scenarios")
        print(f"Estimated time: ~{self.num_scenarios * 10 / 60:.0f} minutes\n")

        results = []

        for scenario_id in range(self.num_scenarios):
            # Generate stochastic weather scenario
            scenario = self._generate_scenario(scenario_id)

            # Create system with scenario
            system = self._create_system_with_scenario(self.base_design, scenario)

            # Optimize with Hybrid Solver
            solver = SolverFactory.get_solver("hybrid", system, self.solver_config)
            result = solver.solve()

            # Extract metrics
            if result.status in ["optimal", "feasible"]:
                metrics = self._extract_metrics(system, result)
                metrics["scenario_id"] = scenario_id
                metrics["status"] = result.status
                results.append(metrics)

            if (scenario_id + 1) % 10 == 0:
                print(f"  Completed {scenario_id + 1}/{self.num_scenarios} scenarios...")

        return self._analyze_results(results)

    def _generate_scenario(self, seed: int) -> dict:
        """Generate stochastic weather scenario."""
        np.random.seed(seed)

        return {
            "solar_variation": 1.0 + np.random.normal(0, 0.15),  # ±15% solar
            "demand_variation": 1.0 + np.random.normal(0, 0.10),  # ±10% demand
            "wind_variation": 1.0 + np.random.normal(0, 0.20),  # ±20% wind
        }

    def _create_system_with_scenario(self, design, scenario):
        """Create system with design and scenario parameters."""
        system = load_energy_system("config/systems/base.yml", horizon=8760)

        # Apply design parameters
        system.components["solar"].capacity = design["solar_kw"]
        system.components["battery"].capacity = design["battery_kwh"]

        # Apply scenario variations
        system.components["solar"].generation *= scenario["solar_variation"]
        system.components["load"].demand *= scenario["demand_variation"]

        return system

    def _extract_metrics(self, system, result) -> dict:
        """Extract performance metrics from optimized system."""
        grid_import = np.sum(system.flows["grid_to_load"]["value"])
        solar_generation = np.sum(system.components["solar"].generation)
        total_demand = np.sum(system.components["load"].demand)

        return {
            "annual_cost": grid_import * 0.20,  # Grid cost
            "grid_import_kwh": grid_import,
            "solar_utilization": (solar_generation - grid_import) / solar_generation,
            "demand_coverage": 1.0 - (grid_import / total_demand),
            "solve_time": result.solve_time,
        }

    def _analyze_results(self, results) -> dict:
        """Analyze MC results for statistics."""
        costs = [r["annual_cost"] for r in results]

        return {
            "mean_annual_cost": np.mean(costs),
            "std_annual_cost": np.std(costs),
            "p10_cost": np.percentile(costs, 10),
            "p50_cost": np.percentile(costs, 50),
            "p90_cost": np.percentile(costs, 90),
            "num_successful": len(results),
            "success_rate": len(results) / self.num_scenarios,
        }


# Run Monte Carlo analysis
design = {"solar_kw": 200, "battery_kwh": 400, "wind_count": 2}

mc_analysis = MonteCarloEnergyAnalysis(base_design=design, num_scenarios=100)
mc_results = mc_analysis.run_analysis()

print("\n" + "=" * 80)
print("MONTE CARLO RESULTS")
print("=" * 80)
print(f"Scenarios analyzed: {mc_results['num_successful']}/{mc_analysis.num_scenarios}")
print(f"Success rate: {mc_results['success_rate']:.1%}")
print(f"\nAnnual Cost Statistics:")
print(f"  Mean: €{mc_results['mean_annual_cost']:,.2f}")
print(f"  Std Dev: €{mc_results['std_annual_cost']:,.2f}")
print(f"  10th percentile: €{mc_results['p10_cost']:,.2f}")
print(f"  50th percentile: €{mc_results['p50_cost']:,.2f}")
print(f"  90th percentile: €{mc_results['p90_cost']:,.2f}")
```

**When to use**: Risk assessment, uncertainty quantification, robust design

---

## Example 5: Configuration Tuning for Performance

Choosing the right configuration based on use case.

```python
from ecosystemiser.solver.factory import SolverFactory
from ecosystemiser.solver.rolling_horizon_milp import RollingHorizonConfig
import time


def benchmark_configurations(system):
    """Benchmark different Hybrid Solver configurations."""

    configurations = {
        "fast": RollingHorizonConfig(
            warmstart=True,
            horizon_hours=72,      # 3-day windows
            overlap_hours=12,      # 12-hour overlap
        ),
        "balanced": RollingHorizonConfig(
            warmstart=True,
            horizon_hours=168,     # 1-week windows
            overlap_hours=24,      # 1-day overlap
        ),
        "quality": RollingHorizonConfig(
            warmstart=True,
            horizon_hours=336,     # 2-week windows
            overlap_hours=48,      # 2-day overlap
        ),
    }

    results = {}

    for name, config in configurations.items():
        print(f"\nTesting '{name}' configuration...")

        start = time.time()
        solver = SolverFactory.get_solver("hybrid", system, config)
        result = solver.solve()
        elapsed = time.time() - start

        if result.status in ["optimal", "feasible"]:
            cost = calculate_total_cost(system)
            results[name] = {
                "time": elapsed,
                "cost": cost,
                "status": result.status,
                "windows": system.N // (config.horizon_hours - config.overlap_hours),
            }

            print(f"  Time: {elapsed:.1f}s")
            print(f"  Cost: €{cost:,.2f}")
            print(f"  Windows: {results[name]['windows']}")
        else:
            print(f"  Failed: {result.message}")

    # Compare results
    print("\n" + "=" * 80)
    print("CONFIGURATION COMPARISON")
    print("=" * 80)

    baseline_cost = results["fast"]["cost"]
    for name, r in results.items():
        cost_diff_pct = (r["cost"] - baseline_cost) / baseline_cost * 100
        print(
            f"{name:10s}: {r['time']:5.1f}s, €{r['cost']:,.2f} "
            f"({cost_diff_pct:+.1f}% vs fast)"
        )

    return results


# Load system
system = load_energy_system("config/systems/test.yml", horizon=8760)

# Benchmark
benchmark_results = benchmark_configurations(system)
```

**When to use**: Performance tuning, configuration selection, trade-off analysis

---

## Performance Monitoring

Track Hybrid Solver performance in production:

```python
import logging
from ecosystemiser.solver.factory import SolverFactory
from hive_logging import get_logger

logger = get_logger(__name__)


class MonitoredHybridSolver:
    """Wrapper for Hybrid Solver with performance monitoring."""

    def __init__(self, system, config):
        self.solver = SolverFactory.get_solver("hybrid", system, config)
        self.metrics = []

    def solve(self):
        """Solve with performance monitoring."""
        import time

        start = time.time()

        # Run solver
        result = self.solver.solve()

        elapsed = time.time() - start

        # Log performance metrics
        metrics = {
            "timestamp": time.time(),
            "solve_time": elapsed,
            "status": result.status,
            "horizon_hours": self.solver.system.N,
            "message": result.message,
        }

        self.metrics.append(metrics)

        logger.info(
            "Hybrid solver completed",
            extra={
                "solve_time_sec": elapsed,
                "status": result.status,
                "horizon_hours": self.solver.system.N,
            },
        )

        return result

    def get_statistics(self):
        """Get solver performance statistics."""
        if not self.metrics:
            return {}

        import numpy as np

        solve_times = [m["solve_time"] for m in self.metrics]

        return {
            "num_solves": len(self.metrics),
            "mean_time": np.mean(solve_times),
            "std_time": np.std(solve_times),
            "min_time": np.min(solve_times),
            "max_time": np.max(solve_times),
            "success_rate": sum(
                1 for m in self.metrics if m["status"] in ["optimal", "feasible"]
            )
            / len(self.metrics),
        }


# Usage
system = load_energy_system("config/systems/test.yml")
config = RollingHorizonConfig(warmstart=True, horizon_hours=168, overlap_hours=24)

monitored_solver = MonitoredHybridSolver(system, config)

# Run multiple optimizations
for i in range(10):
    result = monitored_solver.solve()

# Get statistics
stats = monitored_solver.get_statistics()
print(f"\nPerformance Statistics:")
print(f"  Solves: {stats['num_solves']}")
print(f"  Mean time: {stats['mean_time']:.1f}s")
print(f"  Success rate: {stats['success_rate']:.1%}")
```

---

## Best Practices

### 1. Configuration Selection

| Use Case | Window Size | Overlap | Expected Time (8760h) |
|----------|-------------|---------|-----------------------|
| GA exploration | 72h | 12h | 3-5 min |
| Production runs | 168h | 24h | 5-10 min |
| Final validation | 336h | 48h | 15-20 min |

### 2. Error Handling

```python
result = solver.solve()

if result.status == "error":
    # Scout phase failed - check system configuration
    logger.error(f"Solver failed: {result.message}")
elif result.status == "feasible":
    # Surveyor couldn't prove optimality, but solution is valid
    logger.warning("Solution is feasible but not proven optimal")
elif result.status == "optimal":
    # Best case - optimal solution found
    logger.info("Optimal solution found")
```

### 3. Performance Optimization

- **Reuse configurations** across evaluations to avoid re-instantiation
- **Monitor solve times** and adjust window sizes if needed
- **Use logging** to track scout vs surveyor time splits
- **Cache fitness evaluations** in GA to avoid redundant solves

---

## Troubleshooting

See `claudedocs/hybrid_solver_deployment_guide.md` for comprehensive troubleshooting.

---

**Last Updated**: 2025-10-02
**Related**: `hybrid_solver_deployment_guide.md`, `apps/ecosystemiser/README.md`

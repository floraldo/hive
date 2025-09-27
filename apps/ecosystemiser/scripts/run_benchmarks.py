#!/usr/bin/env python3
"""
Performance Benchmarking Script for EcoSystemiser

This script establishes quantitative baselines for our own performance optimization,
providing the data-driven foundation for architectural decisions and regression detection.

Purpose: Establish baseline metrics for:
- SimulationService.run_simulation solve times across fidelity levels
- Peak memory usage during standard simulations
- RollingHorizonMILPSolver performance with/without warm-starting

Usage:
    python scripts/run_benchmarks.py                    # Run all benchmarks
    python scripts/run_benchmarks.py --simulation-only  # Just simulation benchmarks
    python scripts/run_benchmarks.py --milp-only        # Just MILP benchmarks
    python scripts/run_benchmarks.py --profile          # Include memory profiling
"""

import argparse
import json
import time
import tracemalloc
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import sys

# Optional dependency for memory monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Memory monitoring will be limited.")

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from EcoSystemiser.services.simulation_service import SimulationService, FidelityLevel
from EcoSystemiser.solver.rolling_horizon_milp import RollingHorizonMILPSolver
from EcoSystemiser.utils.system_builder import SystemBuilder
from EcoSystemiser.hive_logging_adapter import get_logger

logger = get_logger(__name__)

class PerformanceBenchmark:
    """Performance benchmarking suite for EcoSystemiser optimization."""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path(__file__).parent / "benchmark_results"
        self.output_dir.mkdir(exist_ok=True)
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'system_info': self._get_system_info(),
            'simulation_benchmarks': {},
            'milp_benchmarks': {},
            'memory_benchmarks': {}
        }

    def _get_system_info(self) -> Dict[str, Any]:
        """Capture system configuration for benchmark context."""
        return {
            'cpu_count': psutil.cpu_count(logical=False),
            'cpu_count_logical': psutil.cpu_count(logical=True),
            'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'python_version': sys.version,
            'platform': sys.platform
        }

    def benchmark_simulation_service(self) -> Dict[str, Any]:
        """
        Benchmark SimulationService.run_simulation across fidelity levels.

        Establishes baseline solve times for standard system configurations.
        """
        logger.info("Starting simulation service benchmarks...")

        # Standard test system configuration
        system_config = {
            'location': {'latitude': 52.0, 'longitude': 4.0},
            'components': {
                'solar_pv': {'capacity_kw': 10.0},
                'battery': {'capacity_kwh': 20.0, 'power_kw': 5.0},
                'heat_pump': {'capacity_kw': 8.0},
                'power_demand': {'annual_kwh': 8000},
                'heat_demand': {'annual_kwh': 12000}
            },
            'optimization': {
                'horizon_days': 7,
                'timestep_hours': 1
            }
        }

        simulation_results = {}

        # Benchmark each fidelity level
        for fidelity in [FidelityLevel.FAST, FidelityLevel.BALANCED, FidelityLevel.ACCURATE]:
            logger.info(f"Benchmarking fidelity level: {fidelity.value}")

            try:
                # Memory tracking
                tracemalloc.start()
                start_memory = psutil.Process().memory_info().rss / (1024**2)  # MB

                # Time the simulation
                start_time = time.perf_counter()

                # Run simulation
                simulation_service = SimulationService()
                result = simulation_service.run_simulation(
                    system_config=system_config,
                    fidelity_level=fidelity,
                    start_date=datetime.now(),
                    end_date=datetime.now() + timedelta(days=7)
                )

                end_time = time.perf_counter()
                solve_time = end_time - start_time

                # Memory measurements
                end_memory = psutil.Process().memory_info().rss / (1024**2)  # MB
                peak_memory = tracemalloc.get_traced_memory()[1] / (1024**2)  # MB
                tracemalloc.stop()

                simulation_results[fidelity.value] = {
                    'solve_time_seconds': round(solve_time, 3),
                    'memory_delta_mb': round(end_memory - start_memory, 2),
                    'peak_memory_mb': round(peak_memory, 2),
                    'success': True,
                    'objective_value': getattr(result, 'objective_value', None)
                }

                logger.info(f"  {fidelity.value}: {solve_time:.3f}s, peak memory: {peak_memory:.1f}MB")

            except Exception as e:
                logger.error(f"Benchmark failed for {fidelity.value}: {e}")
                simulation_results[fidelity.value] = {
                    'solve_time_seconds': None,
                    'memory_delta_mb': None,
                    'peak_memory_mb': None,
                    'success': False,
                    'error': str(e)
                }

        return simulation_results

    def benchmark_milp_warm_starting(self) -> Dict[str, Any]:
        """
        Benchmark RollingHorizonMILPSolver with and without warm-starting.

        Quantifies the performance impact of enhanced warm-starting logic.
        """
        logger.info("Starting MILP warm-starting benchmarks...")

        # Standard multi-day scenario for rolling horizon
        scenario_config = {
            'horizon_days': 3,
            'timestep_hours': 1,
            'total_days': 7,  # Multiple windows for warm-start testing
            'system': {
                'solar_pv': {'capacity_kw': 15.0},
                'battery': {'capacity_kwh': 30.0, 'power_kw': 10.0},
                'heat_pump': {'capacity_kw': 12.0},
                'power_demand': {'annual_kwh': 10000},
                'heat_demand': {'annual_kwh': 15000}
            }
        }

        milp_results = {}

        # Test both cold start and warm start scenarios
        for warm_start_enabled in [False, True]:
            scenario_name = "with_warm_start" if warm_start_enabled else "cold_start"
            logger.info(f"Benchmarking MILP solver: {scenario_name}")

            try:
                start_time = time.perf_counter()
                tracemalloc.start()

                # Initialize solver with warm start configuration
                solver = RollingHorizonMILPSolver(
                    horizon_hours=scenario_config['horizon_days'] * 24,
                    timestep_hours=scenario_config['timestep_hours'],
                    warm_start_enabled=warm_start_enabled
                )

                # Simulate multiple rolling windows
                total_solve_time = 0
                window_count = 0

                for window_start in range(0, scenario_config['total_days'], scenario_config['horizon_days']):
                    window_solve_start = time.perf_counter()

                    # Run optimization window
                    result = solver.optimize_window(
                        start_hour=window_start * 24,
                        system_config=scenario_config['system']
                    )

                    window_solve_time = time.perf_counter() - window_solve_start
                    total_solve_time += window_solve_time
                    window_count += 1

                    if not warm_start_enabled:
                        # Clear solution for cold start
                        solver.previous_solution = None

                end_time = time.perf_counter()
                peak_memory = tracemalloc.get_traced_memory()[1] / (1024**2)  # MB
                tracemalloc.stop()

                total_time = end_time - start_time
                avg_window_time = total_solve_time / window_count if window_count > 0 else 0

                milp_results[scenario_name] = {
                    'total_time_seconds': round(total_time, 3),
                    'total_solve_time_seconds': round(total_solve_time, 3),
                    'average_window_solve_time_seconds': round(avg_window_time, 3),
                    'window_count': window_count,
                    'peak_memory_mb': round(peak_memory, 2),
                    'success': True
                }

                logger.info(f"  {scenario_name}: {total_solve_time:.3f}s total, {avg_window_time:.3f}s avg/window")

            except Exception as e:
                logger.error(f"MILP benchmark failed for {scenario_name}: {e}")
                milp_results[scenario_name] = {
                    'total_time_seconds': None,
                    'total_solve_time_seconds': None,
                    'average_window_solve_time_seconds': None,
                    'window_count': 0,
                    'peak_memory_mb': None,
                    'success': False,
                    'error': str(e)
                }

        # Calculate warm-start performance improvement
        if milp_results.get('cold_start', {}).get('success') and milp_results.get('with_warm_start', {}).get('success'):
            cold_time = milp_results['cold_start']['total_solve_time_seconds']
            warm_time = milp_results['with_warm_start']['total_solve_time_seconds']

            if cold_time and warm_time and cold_time > 0:
                improvement_percent = ((cold_time - warm_time) / cold_time) * 100
                milp_results['warm_start_improvement'] = {
                    'solve_time_improvement_percent': round(improvement_percent, 1),
                    'solve_time_reduction_seconds': round(cold_time - warm_time, 3)
                }

        return milp_results

    def benchmark_memory_usage(self) -> Dict[str, Any]:
        """
        Benchmark peak memory usage patterns for different operation types.

        Establishes baseline memory consumption for regression detection.
        """
        logger.info("Starting memory usage benchmarks...")

        memory_results = {}

        # Test different operation scales
        scenarios = {
            'small_system': {'days': 3, 'timestep_hours': 1},
            'medium_system': {'days': 7, 'timestep_hours': 1},
            'large_system': {'days': 14, 'timestep_hours': 1},
            'high_resolution': {'days': 3, 'timestep_hours': 0.25}  # 15-minute resolution
        }

        for scenario_name, config in scenarios.items():
            logger.info(f"Memory benchmark: {scenario_name}")

            try:
                tracemalloc.start()
                initial_memory = psutil.Process().memory_info().rss / (1024**2)

                # Create system builder and run simulation
                builder = SystemBuilder()
                system = builder.build_standard_system(
                    location={'latitude': 52.0, 'longitude': 4.0},
                    horizon_days=config['days'],
                    timestep_hours=config['timestep_hours']
                )

                # Simulate data loading and processing
                simulation_service = SimulationService()
                result = simulation_service.run_simulation(
                    system_config=system,
                    fidelity_level=FidelityLevel.BALANCED,
                    start_date=datetime.now(),
                    end_date=datetime.now() + timedelta(days=config['days'])
                )

                peak_memory = tracemalloc.get_traced_memory()[1] / (1024**2)
                final_memory = psutil.Process().memory_info().rss / (1024**2)
                tracemalloc.stop()

                memory_results[scenario_name] = {
                    'initial_memory_mb': round(initial_memory, 2),
                    'peak_memory_mb': round(peak_memory, 2),
                    'final_memory_mb': round(final_memory, 2),
                    'memory_delta_mb': round(final_memory - initial_memory, 2),
                    'scenario_config': config,
                    'success': True
                }

                logger.info(f"  {scenario_name}: peak {peak_memory:.1f}MB, delta {final_memory - initial_memory:.1f}MB")

            except Exception as e:
                logger.error(f"Memory benchmark failed for {scenario_name}: {e}")
                memory_results[scenario_name] = {
                    'initial_memory_mb': None,
                    'peak_memory_mb': None,
                    'final_memory_mb': None,
                    'memory_delta_mb': None,
                    'scenario_config': config,
                    'success': False,
                    'error': str(e)
                }

        return memory_results

    def run_all_benchmarks(self, simulation_only=False, milp_only=False, include_memory=False):
        """Run the complete benchmark suite."""
        logger.info("Starting EcoSystemiser performance benchmarks...")

        try:
            if not milp_only:
                self.results['simulation_benchmarks'] = self.benchmark_simulation_service()

            if not simulation_only:
                self.results['milp_benchmarks'] = self.benchmark_milp_warm_starting()

            if include_memory:
                self.results['memory_benchmarks'] = self.benchmark_memory_usage()

            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = self.output_dir / f"benchmark_results_{timestamp}.json"

            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2)

            logger.info(f"Benchmark results saved to: {results_file}")

            # Print summary
            self._print_summary()

        except Exception as e:
            logger.error(f"Benchmark suite failed: {e}")
            raise

    def _print_summary(self):
        """Print benchmark summary to console."""
        print("\n" + "="*60)
        print("ECOSYSTEMISER PERFORMANCE BENCHMARK SUMMARY")
        print("="*60)

        # System info
        sys_info = self.results['system_info']
        print(f"System: {sys_info['cpu_count']} cores, {sys_info['memory_total_gb']}GB RAM")
        print(f"Timestamp: {self.results['timestamp']}")

        # Simulation benchmarks
        if self.results.get('simulation_benchmarks'):
            print("\nSIMULATION SERVICE BENCHMARKS:")
            for fidelity, result in self.results['simulation_benchmarks'].items():
                if result['success']:
                    print(f"  {fidelity:12}: {result['solve_time_seconds']:6.3f}s, {result['peak_memory_mb']:6.1f}MB peak")
                else:
                    print(f"  {fidelity:12}: FAILED")

        # MILP benchmarks
        if self.results.get('milp_benchmarks'):
            print("\nMILP SOLVER BENCHMARKS:")
            for scenario, result in self.results['milp_benchmarks'].items():
                if scenario == 'warm_start_improvement':
                    continue
                if result['success']:
                    print(f"  {scenario:15}: {result['total_solve_time_seconds']:6.3f}s total, {result['average_window_solve_time_seconds']:6.3f}s avg/window")
                else:
                    print(f"  {scenario:15}: FAILED")

            # Warm start improvement
            if 'warm_start_improvement' in self.results['milp_benchmarks']:
                improvement = self.results['milp_benchmarks']['warm_start_improvement']
                print(f"\nWarm-start improvement: {improvement['solve_time_improvement_percent']:.1f}% faster")

        # Memory benchmarks
        if self.results.get('memory_benchmarks'):
            print("\nMEMORY USAGE BENCHMARKS:")
            for scenario, result in self.results['memory_benchmarks'].items():
                if result['success']:
                    print(f"  {scenario:15}: {result['peak_memory_mb']:6.1f}MB peak, {result['memory_delta_mb']:+6.1f}MB delta")
                else:
                    print(f"  {scenario:15}: FAILED")

        print("\n" + "="*60)


def main():
    """Main benchmark execution."""
    parser = argparse.ArgumentParser(description="EcoSystemiser Performance Benchmarks")
    parser.add_argument('--simulation-only', action='store_true',
                       help='Run only simulation service benchmarks')
    parser.add_argument('--milp-only', action='store_true',
                       help='Run only MILP solver benchmarks')
    parser.add_argument('--profile', action='store_true',
                       help='Include detailed memory profiling')
    parser.add_argument('--output-dir', type=Path,
                       help='Output directory for results')

    args = parser.parse_args()

    # Create benchmark runner
    benchmark = PerformanceBenchmark(output_dir=args.output_dir)

    # Run benchmarks
    benchmark.run_all_benchmarks(
        simulation_only=args.simulation_only,
        milp_only=args.milp_only,
        include_memory=args.profile
    )


if __name__ == '__main__':
    main()
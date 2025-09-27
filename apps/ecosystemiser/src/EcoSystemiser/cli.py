#!/usr/bin/env python3
"""
EcoSystemiser CLI - Complete system simulation and climate profiles interface
"""

import click
import json
import sys
from pathlib import Path
from EcoSystemiser.hive_logging_adapter import get_logger
import yaml
from typing import Dict, Any

from EcoSystemiser.profile_loader.climate import get_profile_sync, ClimateRequest

logger = get_logger(__name__)

@click.group()
def cli():
    """EcoSystemiser - Climate and Ecosystem Analysis Tool"""
    pass

@cli.group()
def climate():
    """Climate profile commands"""
    pass

@cli.group()
def simulate():
    """System simulation commands"""
    pass

@climate.command()
@click.option('--loc', '-l', help='Location (e.g., "Lisbon, PT" or "38.7,-9.1"). Required unless using file source.')
@click.option('--file', '-f', type=click.Path(exists=True), help='Input file path for file-based sources (e.g., EPW file)')
@click.option('--year', '-y', type=int, help='Year to fetch (e.g., 2019)')
@click.option('--start', help='Start date (e.g., "2019-01-01")')
@click.option('--end', help='End date (e.g., "2019-12-31")')
@click.option('--vars', '-v', default='temp_air,ghi,wind_speed', help='Variables (comma-separated)')
@click.option('--source', '-s', default='nasa_power', 
              type=click.Choice(['nasa_power', 'meteostat', 'pvgis', 'era5', 'file_epw', 'epw']))
@click.option('--mode', '-m', default='observed',
              type=click.Choice(['observed', 'tmy', 'average', 'synthetic']))
@click.option('--resolution', '-r', default='1H',
              type=click.Choice(['15min', '30min', '1H', '3H', '1D']))
@click.option('--timezone', '-tz', default='UTC',
              type=click.Choice(['UTC', 'local']))
@click.option('--out', '-o', help='Output parquet file path')
@click.option('--json-out', help='Output JSON manifest path')
@click.option('--subset-month', type=int, help='Subset to specific month (1-12)')
@click.option('--subset-season', type=click.Choice(['spring', 'summer', 'fall', 'winter']),
              help='Subset to season')
@click.option('--seed', type=int, help='Random seed for synthetic generation')
@click.option('--stats', is_flag=True, help='Show statistics')
def get(loc, file, year, start, end, vars, source, mode, resolution, timezone, 
        out, json_out, subset_month, subset_season, seed, stats):
    """
    Get climate profile for a location.
    
    Examples:
        ecosys climate get --loc "Lisbon, PT" --year 2019 --vars temp_air,ghi,wind_speed
        ecosys climate get --loc "38.7,-9.1" --start 2019-01-01 --end 2019-12-31 --mode synthetic
        ecosys climate get --file weather.epw --source epw --vars temp_air,ghi
    """
    try:
        # Validate input based on source
        is_file_source = source in ['file_epw', 'epw']
        
        if is_file_source:
            if not file:
                click.echo("Error: --file is required for file-based sources", err=True)
                sys.exit(1)
            # Use file path as location for file sources
            location = str(Path(file).resolve())
        else:
            if not loc:
                click.echo("Error: --loc is required for API-based sources", err=True)
                sys.exit(1)
            # Parse location
            if ',' in loc and any(c.isdigit() for c in loc):
                # Coordinate format
                parts = loc.split(',')
                location = (float(parts[0]), float(parts[1]))
            else:
                # String location
                location = loc
        
        # Build period
        if year:
            period = {"year": year}
        elif start and end:
            period = {"start": start, "end": end}
        else:
            click.echo("Error: Must specify either --year or both --start and --end", err=True)
            sys.exit(1)
        
        # Parse variables
        variables = [v.strip() for v in vars.split(',')]
        
        # Build subset if specified
        subset = None
        if subset_month:
            subset = {"month": f"{subset_month:02d}"}
        elif subset_season:
            subset = {"season": subset_season}
        
        # Create request
        request = ClimateRequest(
            location=location,
            variables=variables,
            source=source,
            period=period,
            mode=mode,
            resolution=resolution,
            timezone=timezone,
            subset=subset,
            seed=seed
        )
        
        # Get profile using synchronous wrapper
        click.echo(f"Fetching climate data from {source}...")
        ds, response = get_profile_sync(request)
        
        # Output results
        click.echo(f"[SUCCESS] Retrieved climate data: shape={response.shape}")
        
        if out:
            # Save to custom path
            out_path = Path(out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            df = ds.to_dataframe()
            df.to_parquet(out_path)
            click.echo(f"[SUCCESS] Saved to {out_path}")
        else:
            click.echo(f"[SUCCESS] Cached to {response.path_parquet}")
        
        if json_out:
            # Save manifest
            json_path = Path(json_out)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, 'w') as f:
                json.dump(response.manifest, f, indent=2, default=str)
            click.echo(f"[SUCCESS] Saved manifest to {json_path}")
        
        # Show statistics if requested
        if stats and response.stats:
            click.echo("\n[STATS] Statistics:")
            for var, var_stats in response.stats.items():
                if var != 'correlations':
                    click.echo(f"\n  {var}:")
                    click.echo(f"    Mean: {var_stats.get('mean', 'N/A'):.2f}")
                    click.echo(f"    Std:  {var_stats.get('std', 'N/A'):.2f}")
                    click.echo(f"    Min:  {var_stats.get('min', 'N/A'):.2f}")
                    click.echo(f"    Max:  {var_stats.get('max', 'N/A'):.2f}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.exception("Failed to get climate profile")
        sys.exit(1)

@climate.command()
@click.option('--pattern', '-p', help='Pattern to match (e.g., "nasa_power_*")')
def clear_cache(pattern):
    """Clear climate data cache"""
    from profile_loader.climate.cache.store import clear_cache as _clear_cache
    
    try:
        _clear_cache(pattern)
        click.echo("[SUCCESS] Cache cleared")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@climate.command()
def cache_info():
    """Show cache information"""
    from profile_loader.climate.cache.store import get_cache_size
    
    try:
        stats = get_cache_size()
        click.echo("[PKG] Cache Statistics:")
        click.echo(f"  Files: {stats['n_files']}")
        click.echo(f"  Total size: {stats['total_bytes'] / 1024 / 1024:.2f} MB")
        click.echo(f"  Data: {stats['data_bytes'] / 1024 / 1024:.2f} MB")
        click.echo(f"  Manifests: {stats['manifest_bytes'] / 1024:.2f} KB")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@simulate.command()
@click.argument('config', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output results file path (default: results.json)')
@click.option('--solver', '-s', default='milp', type=click.Choice(['milp', 'rule_based']),
              help='Solver to use for optimization')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def run(config, output, solver, verbose):
    """
    Run a system simulation from configuration file.

    Examples:
        ecosys simulate run config.yaml
        ecosys simulate run config.yaml -o results.json --solver milp
    """
    from EcoSystemiser.services.simulation_service import SimulationService
    from EcoSystemiser.solver.base import SolverConfig
    from EcoSystemiser.component_data.repository import ComponentRepository

    try:
        # Load configuration
        with open(config, 'r') as f:
            config_data = yaml.safe_load(f)

        click.echo(f"[INFO] Loading configuration from {config}")

        # Create component repository
        component_repo = ComponentRepository(
            data_source="file",
            base_path=Path(__file__).parent.parent / "component_data" / "library"
        )

        # Create simulation service
        service = SimulationService()

        # Create solver config
        solver_config = SolverConfig(
            verbose=verbose,
            solver_type=solver,
            solver_specific=config_data.get('solver_config', {})
        )

        # Run simulation
        click.echo(f"[INFO] Running simulation with {solver} solver...")
        results = service.run_simulation(
            config_path=Path(config),
            solver_config=solver_config,
            component_repo=component_repo,
            results_path=Path(output) if output else None
        )

        # Display summary
        click.echo("\n[SUCCESS] Simulation completed!")
        click.echo(f"  Status: {results.get('status', 'unknown')}")
        if 'objective_value' in results:
            click.echo(f"  Objective Value: {results['objective_value']:.2f}")
        if 'solve_time' in results:
            click.echo(f"  Solve Time: {results['solve_time']:.3f}s")

        if output:
            click.echo(f"  Results saved to: {output}")

    except FileNotFoundError:
        click.echo(f"Error: Configuration file not found: {config}", err=True)
        sys.exit(1)
    except yaml.YAMLError as e:
        click.echo(f"Error parsing YAML configuration: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error running simulation: {e}", err=True)
        logger.exception("Failed to run simulation")
        sys.exit(1)

@simulate.command()
@click.argument('config')
def validate(config):
    """
    Validate a system configuration file.

    Examples:
        ecosys simulate validate config.yaml
    """
    from EcoSystemiser.utils.system_builder import SystemBuilder
    from EcoSystemiser.component_data.repository import ComponentRepository

    click.echo(f"[INFO] Validating configuration from {config}")

    try:
        # Load configuration
        with open(config, 'r') as f:
            config_data = yaml.safe_load(f)

        # Create component repository
        component_repo = ComponentRepository(
            data_source="file",
            base_path=Path(__file__).parent.parent / "component_data" / "library"
        )

        # Try to build system
        builder = SystemBuilder(Path(config), component_repo)
        system = builder.build()

        # Display validation results
        click.echo("\n[SUCCESS] Configuration is valid!")
        click.echo(f"  System ID: {getattr(system, 'system_id', 'Unknown')}")
        click.echo(f"  Components: {len(system.components)}")
        click.echo(f"  Timesteps: {system.N}")

        # List components
        click.echo("\n  Component List:")
        for comp in system.components.values():
            click.echo(f"    - {comp.name} ({comp.__class__.__name__})")

    except FileNotFoundError:
        click.echo(f"Error: Configuration file not found: {config}", err=True)
        sys.exit(1)
    except yaml.YAMLError as e:
        click.echo(f"Error parsing YAML configuration: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Configuration validation failed: {e}", err=True)
        sys.exit(1)

@cli.group()
def results():
    """Results management commands"""
    pass

@cli.group()
def discover():
    """Design space exploration and optimization commands"""
    pass

@discover.command()
@click.argument('config', type=click.Path(exists=True))
@click.option('--objectives', '-obj', default='minimize_cost',
              help='Comma-separated objectives (e.g., "minimize_cost,maximize_renewable")')
@click.option('--population', '-p', default=50, type=int,
              help='Population size for genetic algorithm')
@click.option('--generations', '-g', default=100, type=int,
              help='Maximum number of generations')
@click.option('--variables', '-v', type=click.Path(exists=True),
              help='JSON file defining optimization variables (optional)')
@click.option('--multi-objective', is_flag=True,
              help='Use NSGA-II for multi-objective optimization')
@click.option('--mutation-rate', default=0.1, type=float,
              help='Mutation rate (0.0-1.0)')
@click.option('--crossover-rate', default=0.9, type=float,
              help='Crossover rate (0.0-1.0)')
@click.option('--output', '-o', help='Output directory for results')
@click.option('--workers', '-w', default=4, type=int,
              help='Number of parallel workers')
@click.option('--verbose', is_flag=True, help='Verbose output')
def optimize(config, objectives, population, generations, variables, multi_objective,
            mutation_rate, crossover_rate, output, workers, verbose):
    """
    Run genetic algorithm optimization to find optimal system configurations.

    This command uses genetic algorithms (GA) or NSGA-II for multi-objective optimization
    to explore the design space and find optimal component sizing and configurations.

    Examples:
        # Single-objective cost minimization
        ecosys discover optimize config.yaml

        # Multi-objective optimization
        ecosys discover optimize config.yaml --objectives "minimize_cost,maximize_renewable" --multi-objective

        # Custom GA parameters
        ecosys discover optimize config.yaml --population 100 --generations 200 --mutation-rate 0.15

        # With custom variables definition
        ecosys discover optimize config.yaml --variables variables.json --output results/
    """
    from EcoSystemiser.services.study_service import StudyService
    import json

    try:
        click.echo(f"[INFO] Starting genetic algorithm optimization")
        click.echo(f"  Configuration: {config}")
        click.echo(f"  Objectives: {objectives}")
        click.echo(f"  Algorithm: {'NSGA-II' if multi_objective else 'Single-objective GA'}")
        click.echo(f"  Population: {population}, Generations: {generations}")

        # Load optimization variables if provided
        optimization_variables = None
        if variables:
            with open(variables, 'r') as f:
                optimization_variables = json.load(f)
            click.echo(f"  Variables: Loaded {len(optimization_variables)} custom variables")

        # Create study service
        study_service = StudyService()

        # Configure GA parameters
        ga_config = {
            'population_size': population,
            'max_generations': generations,
            'mutation_rate': mutation_rate,
            'crossover_rate': crossover_rate
        }

        # Run optimization
        result = study_service.run_genetic_algorithm_optimization(
            base_config_path=Path(config),
            optimization_variables=optimization_variables or [],
            objectives=objectives,
            multi_objective=multi_objective,
            **ga_config
        )

        # Display results
        click.echo(f"\n[SUCCESS] Optimization completed!")
        click.echo(f"  Status: {result.summary_statistics.get('convergence_status', 'unknown')}")
        click.echo(f"  Total evaluations: {result.num_simulations}")
        click.echo(f"  Execution time: {result.execution_time:.2f}s")

        if result.best_result:
            best = result.best_result
            if best.get('best_fitness'):
                click.echo(f"  Best fitness: {best['best_fitness']:.4f}")

            if best.get('pareto_front'):
                pareto_size = len(best['pareto_front'])
                click.echo(f"  Pareto front size: {pareto_size} solutions")

        # Save results
        if output:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)

            results_file = output_dir / f"ga_optimization_{result.study_id}.json"
            with open(results_file, 'w') as f:
                json.dump({
                    'study_result': result.dict(),
                    'configuration': {
                        'objectives': objectives,
                        'multi_objective': multi_objective,
                        'ga_config': ga_config
                    }
                }, f, indent=2, default=str)

            click.echo(f"  Results saved to: {results_file}")
        else:
            click.echo(f"  Study ID: {result.study_id}")

        # Show recommendations
        if result.best_result and result.best_result.get('best_solution'):
            click.echo(f"\n[RECOMMENDATIONS] Best solution found:")
            best_solution = result.best_result['best_solution']
            if optimization_variables:
                for i, var in enumerate(optimization_variables):
                    if i < len(best_solution):
                        click.echo(f"  {var.get('name', f'param_{i}')}: {best_solution[i]:.3f}")
            else:
                click.echo(f"  Solution vector: {[f'{x:.3f}' for x in best_solution[:5]]}")
                if len(best_solution) > 5:
                    click.echo(f"  ... and {len(best_solution) - 5} more parameters")

    except FileNotFoundError as e:
        click.echo(f"Error: File not found: {e}", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"Error parsing variables JSON: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error running optimization: {e}", err=True)
        if verbose:
            logger.exception("Failed to run genetic algorithm optimization")
        sys.exit(1)

@discover.command()
@click.argument('config', type=click.Path(exists=True))
@click.option('--objectives', '-obj', default='total_cost',
              help='Comma-separated objectives to analyze (e.g., "total_cost,renewable_fraction")')
@click.option('--samples', '-n', default=1000, type=int,
              help='Number of Monte Carlo samples')
@click.option('--uncertainties', '-u', type=click.Path(exists=True),
              help='JSON file defining uncertain parameters (required)')
@click.option('--sampling', '-s', default='lhs',
              type=click.Choice(['lhs', 'random', 'sobol', 'halton']),
              help='Sampling method')
@click.option('--confidence', default='0.05,0.25,0.50,0.75,0.95',
              help='Comma-separated confidence levels (e.g., "0.05,0.95")')
@click.option('--sensitivity', is_flag=True, default=True,
              help='Perform sensitivity analysis')
@click.option('--risk', is_flag=True, default=True,
              help='Perform risk analysis')
@click.option('--output', '-o', help='Output directory for results')
@click.option('--workers', '-w', default=4, type=int,
              help='Number of parallel workers')
@click.option('--verbose', is_flag=True, help='Verbose output')
def uncertainty(config, objectives, samples, uncertainties, sampling, confidence,
               sensitivity, risk, output, workers, verbose):
    """
    Run Monte Carlo uncertainty analysis to quantify system performance under uncertainty.

    This command uses Monte Carlo sampling to propagate parameter uncertainties through
    the system model and analyze the resulting distribution of key outputs.

    Examples:
        # Basic uncertainty analysis
        ecosys discover uncertainty config.yaml --uncertainties uncertain_params.json

        # Custom sampling configuration
        ecosys discover uncertainty config.yaml -u params.json --samples 5000 --sampling sobol

        # Focus on specific outputs
        ecosys discover uncertainty config.yaml -u params.json --objectives "lcoe,emissions"

        # Comprehensive analysis with risk metrics
        ecosys discover uncertainty config.yaml -u params.json --sensitivity --risk --output results/
    """
    from EcoSystemiser.services.study_service import StudyService
    import json

    try:
        click.echo(f"[INFO] Starting Monte Carlo uncertainty analysis")
        click.echo(f"  Configuration: {config}")
        click.echo(f"  Objectives: {objectives}")
        click.echo(f"  Samples: {samples}")
        click.echo(f"  Sampling method: {sampling}")

        # Load uncertainty definitions (required)
        if not uncertainties:
            click.echo("Error: Uncertainty definitions file is required (--uncertainties)", err=True)
            sys.exit(1)

        with open(uncertainties, 'r') as f:
            uncertainty_variables = json.load(f)
        click.echo(f"  Uncertainties: Loaded {len(uncertainty_variables)} uncertain parameters")

        # Parse confidence levels
        confidence_levels = [float(x.strip()) for x in confidence.split(',')]

        # Create study service
        study_service = StudyService()

        # Configure MC parameters
        mc_config = {
            'n_samples': samples,
            'sampling_method': sampling,
            'confidence_levels': confidence_levels,
            'sensitivity_analysis': sensitivity,
            'risk_analysis': risk
        }

        # Run uncertainty analysis
        result = study_service.run_monte_carlo_uncertainty(
            base_config_path=Path(config),
            uncertainty_variables=uncertainty_variables,
            objectives=objectives,
            **mc_config
        )

        # Display results
        click.echo(f"\n[SUCCESS] Uncertainty analysis completed!")
        click.echo(f"  Total samples: {result.num_simulations}")
        click.echo(f"  Execution time: {result.execution_time:.2f}s")

        # Show statistical summary
        if result.summary_statistics:
            stats = result.summary_statistics

            if 'statistics' in stats:
                click.echo(f"\n[STATISTICS] Output distributions:")
                for obj_name, obj_stats in stats['statistics'].items():
                    click.echo(f"  {obj_name}:")
                    click.echo(f"    Mean: {obj_stats.get('mean', 0):.4f}")
                    click.echo(f"    Std:  {obj_stats.get('std', 0):.4f}")
                    click.echo(f"    Range: [{obj_stats.get('min', 0):.4f}, {obj_stats.get('max', 0):.4f}]")

            if 'confidence_intervals' in stats:
                click.echo(f"\n[CONFIDENCE] Confidence intervals:")
                conf_data = stats['confidence_intervals']
                for obj_name, intervals in conf_data.items():
                    click.echo(f"  {obj_name}:")
                    for level, bounds in intervals.items():
                        click.echo(f"    {level}: [{bounds.get('lower', 0):.4f}, {bounds.get('upper', 0):.4f}]")

            if sensitivity and 'sensitivity_indices' in stats:
                click.echo(f"\n[SENSITIVITY] Most influential parameters:")
                sens_data = stats['sensitivity_indices']
                for obj_name, param_sens in sens_data.items():
                    if param_sens:
                        # Sort by sensitivity index
                        sorted_params = sorted(param_sens.items(),
                                             key=lambda x: abs(x[1].get('sensitivity_index', 0)),
                                             reverse=True)
                        click.echo(f"  {obj_name}:")
                        for param_name, sens_info in sorted_params[:5]:  # Top 5
                            sens_idx = sens_info.get('sensitivity_index', 0)
                            click.echo(f"    {param_name}: {sens_idx:.3f}")

            if risk and 'risk_metrics' in stats:
                click.echo(f"\n[RISK] Risk metrics:")
                risk_data = stats['risk_metrics']
                for obj_name, risk_info in risk_data.items():
                    click.echo(f"  {obj_name}:")
                    click.echo(f"    VaR 95%: {risk_info.get('var_95', 0):.4f}")
                    click.echo(f"    CVaR 95%: {risk_info.get('cvar_95', 0):.4f}")
                    click.echo(f"    Risk ratio: {risk_info.get('risk_ratio', 0):.3f}")

        # Save results
        if output:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)

            results_file = output_dir / f"mc_uncertainty_{result.study_id}.json"
            with open(results_file, 'w') as f:
                json.dump({
                    'study_result': result.dict(),
                    'configuration': {
                        'objectives': objectives,
                        'uncertainty_variables': uncertainty_variables,
                        'mc_config': mc_config
                    }
                }, f, indent=2, default=str)

            click.echo(f"\n  Results saved to: {results_file}")

            # Also save summary CSV
            if result.summary_statistics and 'statistics' in result.summary_statistics:
                import pandas as pd
                stats_data = []
                for obj_name, obj_stats in result.summary_statistics['statistics'].items():
                    stats_data.append({
                        'objective': obj_name,
                        'mean': obj_stats.get('mean', 0),
                        'std': obj_stats.get('std', 0),
                        'min': obj_stats.get('min', 0),
                        'max': obj_stats.get('max', 0)
                    })

                if stats_data:
                    df = pd.DataFrame(stats_data)
                    csv_file = output_dir / f"mc_summary_{result.study_id}.csv"
                    df.to_csv(csv_file, index=False)
                    click.echo(f"  Summary saved to: {csv_file}")
        else:
            click.echo(f"  Study ID: {result.study_id}")

    except FileNotFoundError as e:
        click.echo(f"Error: File not found: {e}", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"Error parsing JSON file: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error running uncertainty analysis: {e}", err=True)
        if verbose:
            logger.exception("Failed to run Monte Carlo uncertainty analysis")
        sys.exit(1)

@discover.command()
@click.argument('config', type=click.Path(exists=True))
@click.option('--variables', '-v', type=click.Path(exists=True), required=True,
              help='JSON file defining design variables (required)')
@click.option('--objectives', '-obj', default='minimize_cost,maximize_renewable',
              help='Comma-separated objectives (e.g., "minimize_cost,maximize_renewable")')
@click.option('--method', '-m', default='nsga2',
              type=click.Choice(['nsga2', 'monte_carlo']),
              help='Exploration method')
@click.option('--samples', '-n', default=100, type=int,
              help='Number of samples/population size')
@click.option('--output', '-o', help='Output directory for results')
@click.option('--workers', '-w', default=4, type=int,
              help='Number of parallel workers')
@click.option('--verbose', is_flag=True, help='Verbose output')
def explore(config, variables, objectives, method, samples, output, workers, verbose):
    """
    Comprehensive design space exploration for multi-objective optimization.

    This command provides a unified interface for exploring the design space using
    either genetic algorithms (NSGA-II) or Monte Carlo sampling. It automatically
    configures the chosen method for multi-objective design space exploration.

    Examples:
        # NSGA-II design space exploration
        ecosys discover explore config.yaml --variables design_vars.json

        # Monte Carlo design space exploration
        ecosys discover explore config.yaml -v vars.json --method monte_carlo --samples 5000

        # Custom objectives and output
        ecosys discover explore config.yaml -v vars.json --objectives "cost,emissions,efficiency" -o results/
    """
    from EcoSystemiser.services.study_service import StudyService
    import json

    try:
        click.echo(f"[INFO] Starting design space exploration")
        click.echo(f"  Configuration: {config}")
        click.echo(f"  Objectives: {objectives}")
        click.echo(f"  Method: {method}")
        click.echo(f"  Samples/Population: {samples}")

        # Load design variables
        with open(variables, 'r') as f:
            design_variables = json.load(f)
        click.echo(f"  Variables: Loaded {len(design_variables)} design variables")

        # Create study service
        study_service = StudyService()

        # Run design space exploration
        result = study_service.run_design_space_exploration(
            base_config_path=Path(config),
            design_variables=design_variables,
            objectives=objectives,
            exploration_method=method,
            population_size=samples if method == 'nsga2' else None,
            max_generations=100 if method == 'nsga2' else None,
            n_samples=samples if method == 'monte_carlo' else None,
            sampling_method='lhs' if method == 'monte_carlo' else None
        )

        # Display results
        click.echo(f"\n[SUCCESS] Design space exploration completed!")
        click.echo(f"  Method: {method}")
        click.echo(f"  Total evaluations: {result.num_simulations}")
        click.echo(f"  Execution time: {result.execution_time:.2f}s")

        if method == 'nsga2' and result.best_result:
            best = result.best_result
            if best.get('pareto_front'):
                pareto_size = len(best['pareto_front'])
                click.echo(f"  Pareto front size: {pareto_size} solutions")

        if method == 'monte_carlo' and result.summary_statistics:
            stats = result.summary_statistics
            if 'statistics' in stats:
                click.echo(f"\n[DESIGN SPACE] Variable ranges explored:")
                for var in design_variables:
                    var_name = var.get('name', 'unknown')
                    bounds = var.get('bounds', (0, 1))
                    click.echo(f"  {var_name}: [{bounds[0]:.3f}, {bounds[1]:.3f}]")

        # Save results
        if output:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)

            results_file = output_dir / f"exploration_{method}_{result.study_id}.json"
            with open(results_file, 'w') as f:
                json.dump({
                    'study_result': result.dict(),
                    'configuration': {
                        'method': method,
                        'objectives': objectives,
                        'design_variables': design_variables,
                        'samples': samples
                    }
                }, f, indent=2, default=str)

            click.echo(f"\n  Results saved to: {results_file}")

            # Save design variables for reference
            vars_file = output_dir / f"design_variables_{result.study_id}.json"
            with open(vars_file, 'w') as f:
                json.dump(design_variables, f, indent=2)
            click.echo(f"  Variables saved to: {vars_file}")

        else:
            click.echo(f"  Study ID: {result.study_id}")

        # Provide next steps guidance
        click.echo(f"\n[NEXT STEPS] To visualize results:")
        if method == 'nsga2':
            click.echo(f"  - Use Pareto front visualization for trade-off analysis")
            click.echo(f"  - Examine convergence history for algorithm performance")
        else:
            click.echo(f"  - Plot uncertainty distributions for key outputs")
            click.echo(f"  - Review sensitivity analysis for design insights")

    except FileNotFoundError as e:
        click.echo(f"Error: File not found: {e}", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"Error parsing variables JSON: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error running design space exploration: {e}", err=True)
        if verbose:
            logger.exception("Failed to run design space exploration")
        sys.exit(1)

@cli.group()
def report():
    """Report generation and server commands"""
    pass

@results.command()
@click.argument('results_file', type=click.Path(exists=True))
@click.option('--format', '-f', type=click.Choice(['summary', 'detailed', 'kpi']),
              default='summary', help='Output format')
def show(results_file, format):
    """
    Display simulation results.

    Examples:
        ecosys results show results.json
        ecosys results show results.json --format detailed
    """
    from EcoSystemiser.services.results_io import ResultsIO

    try:
        # Load results
        results_io = ResultsIO()
        results = results_io.load(Path(results_file))

        click.echo(f"\n[RESULTS] Simulation: {results_file}")
        click.echo("=" * 50)

        # Display based on format
        if format == 'summary' or format == 'kpi':
            if 'summary' in results:
                summary = results['summary']
                click.echo(f"  Status: {summary.get('status', 'unknown')}")
                click.echo(f"  Objective: {summary.get('objective_value', 0):.2f}")
                click.echo(f"  Solve Time: {summary.get('solve_time', 0):.3f}s")

            if 'kpis' in results and format == 'kpi':
                click.echo("\n  Key Performance Indicators:")
                for kpi, value in results['kpis'].items():
                    if isinstance(value, (int, float)):
                        click.echo(f"    {kpi}: {value:.2f}")
                    else:
                        click.echo(f"    {kpi}: {value}")

        elif format == 'detailed':
            # Show component results
            if 'components' in results:
                click.echo("\n  Component Results:")
                for comp_name, comp_data in results['components'].items():
                    click.echo(f"\n    {comp_name}:")
                    for key, value in comp_data.items():
                        if isinstance(value, list) and len(value) > 0:
                            click.echo(f"      {key}: {len(value)} timesteps")
                        elif isinstance(value, (int, float)):
                            click.echo(f"      {key}: {value:.2f}")

    except FileNotFoundError:
        click.echo(f"Error: Results file not found: {results_file}", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"Error parsing results file: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error displaying results: {e}", err=True)
        sys.exit(1)

@report.command()
@click.argument('results_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(),
              help='Output directory for report files')
@click.option('--strategies', '-s', multiple=True,
              help='Analysis strategies to run (default: all)')
@click.option('--format', 'output_format', type=click.Choice(['json', 'html']),
              default='json', help='Output format')
def analyze(results_file, output, strategies, output_format):
    """Analyze simulation results and generate report data."""
    from EcoSystemiser.analyser import AnalyserService

    try:
        # Initialize analyser
        analyser = AnalyserService()

        # Run analysis
        strategies_list = list(strategies) if strategies else None
        analysis_results = analyser.analyse(results_file, strategies_list)

        # Determine output path
        if output:
            output_dir = Path(output)
        else:
            output_dir = Path(results_file).parent / 'analysis_output'

        output_dir.mkdir(exist_ok=True)

        if output_format == 'json':
            # Save JSON results
            output_file = output_dir / 'analysis_results.json'
            analyser.save_analysis(analysis_results, str(output_file))
            click.echo(f"Analysis saved to: {output_file}")
        else:
            click.echo("HTML format requires Flask server. Use 'report server' command.")

        # Print summary
        summary = analysis_results.get('summary', {})
        click.echo(f"\nAnalysis Summary:")
        click.echo(f"  Successful analyses: {summary.get('successful_analyses', 0)}")
        click.echo(f"  Failed analyses: {summary.get('failed_analyses', 0)}")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@report.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=5000, help='Port to bind to')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def server(host, port, debug):
    """Start the reporting web server."""
    from EcoSystemiser.reporting import run_server

    click.echo(f"Starting EcoSystemiser Reporting Server...")
    click.echo(f"Server will be available at: http://{host}:{port}")
    click.echo(f"Upload your simulation results to generate reports.")
    click.echo(f"Press Ctrl+C to stop the server.")

    try:
        run_server(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        click.echo("\nShutting down server...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        click.echo(f"Server error: {e}", err=True)
        sys.exit(1)

@report.command()
@click.argument('results_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), default='report.html',
              help='Output HTML file path')
def generate(results_file, output):
    """Generate a standalone HTML report."""
    from EcoSystemiser.analyser import AnalyserService
    from EcoSystemiser.datavis.plot_factory import PlotFactory

    try:
        # Run analysis
        analyser = AnalyserService()
        analysis_results = analyser.analyse(results_file)

        # Load raw results
        with open(results_file, 'r') as f:
            raw_results = json.load(f)

        # Generate plots
        plot_factory = PlotFactory()
        plots = {}
        analyses = analysis_results.get('analyses', {})

        # Generate relevant plots
        if 'technical_kpi' in analyses:
            plots['kpi_gauges'] = plot_factory.create_technical_kpi_gauges(analyses['technical_kpi'])

        if 'economic' in analyses:
            plots['economic_summary'] = plot_factory.create_economic_summary_plot(analyses['economic'])

        # Create basic HTML report
        html_content = _create_standalone_html_report(analysis_results, plots)

        # Save report
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(html_content)

        click.echo(f"HTML report generated: {output_path}")

        # Print summary
        summary = analysis_results.get('summary', {})
        click.echo(f"Report includes {summary.get('successful_analyses', 0)} successful analyses")

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

def _create_standalone_html_report(analysis_results: dict, plots: dict) -> str:
    """Create a basic standalone HTML report."""
    summary = analysis_results.get('summary', {})

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>EcoSystemiser Analysis Report</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .metric {{ display: inline-block; margin: 20px; text-align: center; }}
            .metric-value {{ font-size: 2em; font-weight: bold; color: #2E7D32; }}
            .metric-label {{ color: #666; }}
            .plot {{ margin: 30px 0; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>EcoSystemiser Analysis Report</h1>

        <h2>Summary</h2>
        <div class="metric">
            <div class="metric-value">{summary.get('successful_analyses', 0)}</div>
            <div class="metric-label">Successful Analyses</div>
        </div>
        <div class="metric">
            <div class="metric-value">{summary.get('failed_analyses', 0)}</div>
            <div class="metric-label">Failed Analyses</div>
        </div>
    """

    # Add key metrics if available
    key_metrics = summary.get('key_metrics', {})
    if key_metrics:
        if 'grid_self_sufficiency' in key_metrics:
            html += f"""
        <div class="metric">
            <div class="metric-value">{key_metrics['grid_self_sufficiency']:.1%}</div>
            <div class="metric-label">Grid Self-Sufficiency</div>
        </div>
            """
        if 'renewable_fraction' in key_metrics:
            html += f"""
        <div class="metric">
            <div class="metric-value">{key_metrics['renewable_fraction']:.1%}</div>
            <div class="metric-label">Renewable Fraction</div>
        </div>
            """

    # Add plots
    html += '<h2>Visualizations</h2>'
    for plot_name in plots.keys():
        html += f'<div id="{plot_name}" class="plot"></div>'

    # Add analysis results in tables
    analyses = analysis_results.get('analyses', {})
    if analyses:
        html += '<h2>Detailed Results</h2>'

        for analysis_name, analysis_data in analyses.items():
            if 'error' not in analysis_data:
                html += f'<h3>{analysis_name.replace("_", " ").title()}</h3>'
                html += '<table>'

                for key, value in analysis_data.items():
                    if key not in ['analysis_type', 'analysis_version']:
                        if isinstance(value, (int, float)):
                            if 0 <= value <= 1:
                                formatted_value = f"{value:.1%}"
                            else:
                                formatted_value = f"{value:.2f}"
                        else:
                            formatted_value = str(value)[:100]  # Truncate long values

                        html += f'<tr><td>{key.replace("_", " ").title()}</td><td>{formatted_value}</td></tr>'

                html += '</table>'

    # Add script to render plots
    html += f"""
        <script>
        const plots = {json.dumps(plots)};
        Object.keys(plots).forEach(key => {{
            if (plots[key] && document.getElementById(key)) {{
                Plotly.newPlot(key, plots[key], {{}}, {{responsive: true}});
            }}
        }});
        </script>
    </body>
    </html>
    """

    return html

if __name__ == '__main__':
    cli()
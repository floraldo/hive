#!/usr/bin/env python3
"""
EcoSystemiser CLI - Complete system simulation and climate profiles interface
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

import click
import yaml
from ecosystemiser.profile_loader.climate import ClimateRequest, get_profile_sync
from ecosystemiser.reporting.generator import create_standalone_html_report
from hive_logging import get_logger

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
    from ecosystemiser.services.simulation_service import SimulationService

    try:
        click.echo(f"[INFO] Loading configuration from {config}")

        # Create simulation service (it handles repository creation internally)
        service = SimulationService()

        # Run simulation using the new service method
        click.echo(f"[INFO] Running simulation with {solver} solver...")
        result = service.run_simulation_from_path(
            config_path=Path(config),
            solver_type=solver,
            output_path=Path(output) if output else None,
            verbose=verbose
        )

        # Display summary
        click.echo("\n[SUCCESS] Simulation completed!")
        click.echo(f"  Status: {result.status}")
        if result.kpis:
            click.echo(f"  Key Performance Indicators:")
            for key, value in result.kpis.items():
                click.echo(f"    {key}: {value:.2f}")
        if result.solver_metrics:
            if 'objective_value' in result.solver_metrics:
                click.echo(f"  Objective Value: {result.solver_metrics['objective_value']:.2f}")
            if 'solve_time' in result.solver_metrics:
                click.echo(f"  Solve Time: {result.solver_metrics['solve_time']:.3f}s")

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
    from ecosystemiser.services.simulation_service import SimulationService

    click.echo(f"[INFO] Validating configuration from {config}")

    try:
        # Create simulation service
        service = SimulationService()

        # Validate configuration using the service
        validation_result = service.validate_system_config(Path(config))

        if validation_result['valid']:
            # Display validation results
            click.echo("\n[SUCCESS] Configuration is valid!")
            click.echo(f"  System ID: {validation_result['system_id']}")
            click.echo(f"  Components: {validation_result['num_components']}")
            click.echo(f"  Timesteps: {validation_result['timesteps']}")

            # List components
            click.echo("\n  Component List:")
            for comp in validation_result['components']:
                click.echo(f"    - {comp['name']} ({comp['type']})")
        else:
            click.echo(f"\n[ERROR] Configuration validation failed: {validation_result['error']}", err=True)
            sys.exit(1)

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
@click.option('--report', is_flag=True,
              help='Generate HTML report after optimization')
@click.option('--verbose', is_flag=True, help='Verbose output')
def optimize(config, objectives, population, generations, variables, multi_objective,
            mutation_rate, crossover_rate, output, workers, report, verbose):
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
    import json

    from ecosystemiser.services.study_service import StudyService

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

            # Generate report if requested
            if report:
                click.echo("\n[INFO] Generating HTML report...")
                from ecosystemiser.services.reporting_service import ReportingService, ReportConfig

                # Create reporting service
                reporting_service = ReportingService()

                # Configure report
                report_config = ReportConfig(
                    report_type='genetic_algorithm',
                    title='Genetic Algorithm Optimization Report',
                    include_plots=True,
                    output_format='html',
                    save_path=output_dir / f"ga_report_{result.study_id}"
                )

                # Generate report using the centralized service
                report_result = reporting_service.generate_report(
                    analysis_results=result.dict(),
                    config=report_config
                )
                report_file = output_dir / f"ga_report_{result.study_id}.html"
                click.echo(f"  HTML report saved to: {report_file}")
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
    import json

    from ecosystemiser.services.study_service import StudyService

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
    import json

    from ecosystemiser.services.study_service import StudyService

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
    from ecosystemiser.services.results_io import ResultsIO

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
    from ecosystemiser.analyser import AnalyserService

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
    from ecosystemiser.reporting import run_server

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

@report.command('generate')
@click.argument('study_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), default='report.html',
              help='Output HTML file path')
@click.option('--type', 'study_type', type=click.Choice(['auto', 'ga', 'mc', 'standard']),
              default='auto', help='Type of study (auto-detect by default)')
def generate(study_file, output, study_type):
    """Generate a standalone HTML report from study results.

    Examples:
        ecosys report generate ga_optimization_123.json
        ecosys report generate mc_uncertainty_456.json --output analysis.html
    """
    import json
    from ecosystemiser.services.reporting_service import ReportingService, ReportConfig

    try:
        # Load study results
        with open(study_file, 'r') as f:
            study_data = json.load(f)

        # Auto-detect study type if needed
        if study_type == 'auto':
            if 'pareto_front' in study_data.get('best_result', {}):
                study_type = 'genetic_algorithm'
            elif 'uncertainty_analysis' in study_data.get('best_result', {}):
                study_type = 'monte_carlo'
            elif 'study_type' in study_data:
                study_type = study_data['study_type']
            else:
                study_type = 'standard'

        # Map legacy type names
        type_map = {
            'ga': 'genetic_algorithm',
            'mc': 'monte_carlo'
        }
        study_type = type_map.get(study_type, study_type)

        click.echo(f"Generating {study_type} report from: {study_file}")

        # Create reporting service
        reporting_service = ReportingService()

        # Configure report generation
        report_config = ReportConfig(
            report_type=study_type,
            title=f"EcoSystemiser {study_type.replace('_', ' ').title()} Report",
            include_plots=True,
            output_format="html",
            save_path=Path(output)
        )

        # Generate report using the centralized service
        report_result = reporting_service.generate_report(
            analysis_results=study_data,
            config=report_config
        )

        click.echo(f"HTML report saved to: {output}")

        # Open in browser if available
        import webbrowser
        webbrowser.open(f'file://{Path(output).absolute()}')

    except FileNotFoundError:
        click.echo(f"Error: Study file not found: {study_file}", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"Error parsing study file: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error generating report: {e}", err=True)
        if verbose:
            logger.exception("Failed to generate report")
        sys.exit(1)
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

        # Create HTML report using centralized generator
        html_content = create_standalone_html_report(analysis_results, plots)

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

if __name__ == '__main__':
    cli()
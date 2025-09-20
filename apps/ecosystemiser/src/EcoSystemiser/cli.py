#!/usr/bin/env python3
"""
EcoSystemiser CLI - Climate profiles command-line interface
"""

import click
import json
import sys
from pathlib import Path
import logging

from EcoSystemiser.profile_loader.climate import get_profile_sync, ClimateRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.group()
def cli():
    """EcoSystemiser - Climate and Ecosystem Analysis Tool"""
    pass

@cli.group()
def climate():
    """Climate profile commands"""
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

if __name__ == '__main__':
    cli()
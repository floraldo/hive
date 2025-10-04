"""Main CLI entry point for the Hive Application Toolkit."""

import asyncio
import sys
from pathlib import Path

import click

from hive_logging import get_logger

from .generator import ApplicationGenerator, ServiceType

logger = get_logger(__name__)


@click.group()
@click.version_option(version="1.0.0")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(verbose: bool = False) -> None:
    """
    Hive Application Toolkit - Strategic Force Multiplier for Development.

    Build production-ready applications in hours instead of weeks.
    """
    if verbose:
        import logging

        # Set root logger level for verbose mode
        root_logger = get_logger("hive_app_toolkit")
        root_logger.setLevel(logging.DEBUG)


@main.command()
@click.argument("app_name")
@click.option(
    "--type",
    "service_type",
    type=click.Choice(["api", "worker", "batch", "webhook"]),
    default="api",
    help="Type of service to create",
)
@click.option("--output", "-o", type=click.Path(), help="Output directory (defaults to ./apps/{app_name})")
@click.option("--namespace", "-n", default="hive-platform", help="Kubernetes namespace")
@click.option("--port", "-p", type=int, default=8000, help="Application port")
@click.option("--enable-database", is_flag=True, help="Enable database configuration")
@click.option("--enable-cache", is_flag=True, default=True, help="Enable cache configuration")
@click.option("--enable-auth", is_flag=True, help="Enable authentication")
@click.option("--cost-limits", help="Cost limits (format: daily,monthly,per_op)")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without creating files")
def init(
    app_name: str,
    service_type: str,
    output: str | None = None,
    namespace: str = "hive-platform",
    port: int = 8000,
    enable_database: bool = False,
    enable_cache: bool = True,
    enable_auth: bool = False,
    cost_limits: str | None = None,
    dry_run: bool = False,
) -> None:
    """Initialize a new Hive application with production-grade foundation."""

    # Parse cost limits
    daily_limit = (100.0,)
    monthly_limit = (2000.0,)
    per_op_limit = 1.0

    if cost_limits:
        try:
            parts = cost_limits.split(",")
            if len(parts) >= 1:
                daily_limit = float(parts[0])
            if len(parts) >= 2:
                monthly_limit = float(parts[1])
            if len(parts) >= 3:
                per_op_limit = float(parts[2])
        except ValueError:
            (click.echo(f"Invalid cost limits format: {cost_limits}", err=True),)
            sys.exit(1)

    # Determine output directory
    if output:
        output_dir = Path(output)
    else:
        output_dir = Path(f"apps/{app_name}")

    # Create generator configuration
    config = {
        "app_name": app_name,
        "service_type": ServiceType(service_type),
        "output_dir": output_dir,
        "namespace": namespace,
        "port": port,
        "enable_database": enable_database,
        "enable_cache": enable_cache,
        "enable_auth": enable_auth,
        "cost_limits": {"daily": daily_limit, "monthly": monthly_limit, "per_operation": per_op_limit},
        "dry_run": dry_run,
    }

    # Generate application
    try:
        generator = ApplicationGenerator()
        result = asyncio.run(generator.generate(config))

        if dry_run:
            (click.echo(" Dry run - would generate:"),)
            for file_path in result["files_created"]:
                click.echo(f"   {file_path}")
        else:
            click.echo(" Application generated successfully!")
            (click.echo(f" Location: {output_dir}"),)
            click.echo(f" Files created: {len(result['files_created'])}")

            if result.get("next_steps"):
                (click.echo("\n Next steps:"),)
                for step in result["next_steps"]:
                    click.echo(f"   {step}")

    except Exception as e:
        (click.echo(f"MISSING Generation failed: {e}", err=True),)
        if "--verbose" in sys.argv:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.option("--output", "-o", type=click.Path(exists=True), default=".", help="Target directory")
def add_api(output: str = ".") -> None:
    """Add API endpoints and middleware to an existing application."""

    output_dir = Path(output)

    try:
        generator = ApplicationGenerator()
        result = asyncio.run(generator.add_api_foundation(output_dir))

        click.echo(" API foundation added!")
        click.echo(f" Files modified: {len(result['files_modified'])}")

        for file_path in result["files_modified"]:
            click.echo(f"   {file_path}")

    except Exception as e:
        click.echo(f"MISSING Failed to add API foundation: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--output", "-o", type=click.Path(exists=True), default=".", help="Target directory")
@click.option("--namespace", "-n", default="hive-platform", help="Kubernetes namespace")
def add_k8s(output: str = ".", namespace: str = "hive-platform") -> None:
    """Add Kubernetes manifests to an existing application."""

    output_dir = Path(output)

    try:
        generator = ApplicationGenerator()
        result = asyncio.run(generator.add_kubernetes_manifests(output_dir, namespace))

        click.echo(" Kubernetes manifests added!")
        click.echo(f" Files created: {len(result['files_created'])}")

        for file_path in result["files_created"]:
            click.echo(f"   {file_path}")

    except Exception as e:
        click.echo(f"MISSING Failed to add Kubernetes manifests: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--output", "-o", type=click.Path(exists=True), default=".", help="Target directory")
@click.option("--registry", default="ghcr.io", help="Docker registry")
def add_ci(output: str = ".", registry: str = "ghcr.io") -> None:
    """Add CI/CD pipeline to an existing application."""

    output_dir = Path(output)

    try:
        generator = ApplicationGenerator()
        result = asyncio.run(generator.add_cicd_pipeline(output_dir, registry))

        click.echo(" CI/CD pipeline added!")
        click.echo(f" Files created: {len(result['files_created'])}")

        for file_path in result["files_created"]:
            click.echo(f"   {file_path}")

        click.echo("\n Don't forget to:")
        click.echo("   Add secrets to your GitHub repository")
        click.echo("   Configure deployment credentials")
        click.echo("   Review and customize the pipeline")

    except Exception as e:
        click.echo(f"MISSING Failed to add CI/CD pipeline: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--output", "-o", type=click.Path(exists=True), default=".", help="Target directory")
def status(output: str = ".") -> None:
    """Show status of Hive toolkit integration."""

    output_dir = Path(output)

    try:
        generator = ApplicationGenerator()
        status_info = asyncio.run(generator.get_integration_status(output_dir))

        click.echo(f" Hive Toolkit Integration Status for {output_dir}")
        click.echo("=" * 50)

        for component, info in status_info.items():
            status_icon = "OK" if info["integrated"] else "MISSING"
            click.echo(f"{status_icon} {component.title()}: {info['status']}")

            if info.get("files"):
                for file_path in info["files"]:
                    click.echo(f"     {file_path}")

    except Exception as e:
        click.echo(f"MISSING Failed to check status: {e}", err=True)
        sys.exit(1)


@main.command()
def examples() -> None:
    """Show usage examples."""

    examples_text = """
 Hive Application Toolkit - Usage Examples

1 Create a new API service:
   hive-toolkit init my-api --type api --enable-database --enable-auth

2 Create a webhook service:
   hive-toolkit init webhook-handler --type webhook --port 8080

3 Add API foundation to existing project:
   cd my-project && hive-toolkit add-api

4 Add Kubernetes deployment:
   hive-toolkit add-k8s --namespace my-namespace

5 Add CI/CD pipeline:
   hive-toolkit add-ci --registry my-registry.com

6 Check integration status:
   hive-toolkit status

7 Create with custom cost limits:
   hive-toolkit init cost-aware-service --cost-limits 50,1000,0.5

 From zero to production in minutes!
"""
    click.echo(examples_text)


if __name__ == "__main__":
    main()

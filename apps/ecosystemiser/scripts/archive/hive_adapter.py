#!/usr/bin/env python3
"""
EcoSystemiser Hive Adapter

This adapter translates between Hive's task system and EcoSystemiser's
capabilities, enabling the AI app to execute meaningful ecosystem analysis
and optimization tasks.
"""

import argparse
import json
import os

# Temporary path setup until package installation completes
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ecosystemiser.hive_env import get_app_config, get_app_settings

# Import from properly installed packages
from hive_logging import get_logger, setup_logging

# Import real EcoSystemiser components for climate service
try:
    from ecosystemiser.profile_loader.climate.data_models import (
        ClimateRequest,
        ClimateResponse,
    )
    from ecosystemiser.profile_loader.climate.service import ClimateService

    CLIMATE_SERVICE_AVAILABLE = True
except Exception as e:
    CLIMATE_SERVICE_AVAILABLE = False
    # Check if we can at least import the data models
    try:
        from ecosystemiser.profile_loader.climate.data_models import (
            ClimateRequest,
            ClimateResponse,
        )

        CLIMATE_MODELS_AVAILABLE = True
    except ImportError as import_err:
        CLIMATE_MODELS_AVAILABLE = False
    logger.warning(f"Warning: EcoSystemiser climate service not available: {e}")


class EcoSystemiserAdapter:
    """Adapter for EcoSystemiser tasks within Hive"""

    def __init__(self):
        """Initialize the adapter with proper config service"""
        self.logger = get_logger(__name__)

        # Get configuration from hive-config service
        self.config = get_app_config()
        self.settings = get_app_settings()

        # Set up results directory from config
        results_dir = self.settings.get("RESULTS_DIR", "./ecosystemiser_results")
        self.results_dir = Path.cwd() / results_dir
        self.results_dir.mkdir(exist_ok=True)

    def execute_task(self, task_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific EcoSystemiser task

        Args:
            task_name: Name of the task to execute
            payload: Task-specific parameters

        Returns:
            Result dictionary with status and outputs
        """
        self.logger.info(f"Executing EcoSystemiser task: {task_name}")

        # Route to specific task handlers
        if task_name == "health-check":
            return self.health_check(payload)
        elif task_name == "fetch-climate-data":
            return self.fetch_climate_data(payload)
        elif task_name == "analyze-ecosystem":
            return self.analyze_ecosystem(payload)
        elif task_name == "optimize-balance":
            return self.optimize_balance(payload)
        elif task_name == "generate-report":
            return self.generate_report(payload)
        else:
            return {"status": "error", "message": f"Unknown task: {task_name}"}

    def health_check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a health check of the EcoSystemiser

        Returns system status and capabilities
        """
        self.logger.info("Running EcoSystemiser health check")

        capabilities = ["analyze-ecosystem", "optimize-balance", "generate-report"]

        if CLIMATE_SERVICE_AVAILABLE:
            capabilities.append("fetch-climate-data")

        return {
            "status": "success",
            "message": "EcoSystemiser is operational",
            "capabilities": capabilities,
            "climate_service": "available" if CLIMATE_SERVICE_AVAILABLE else "unavailable",
            "version": "0.1.0",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def analyze_ecosystem(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the current state of the ecosystem

        Args:
            payload: Contains ecosystem parameters to analyze

        Returns:
            Analysis results with metrics and insights
        """
        self.logger.info("Analyzing ecosystem")

        # Extract parameters
        ecosystem_type = payload.get("ecosystem_type", "software")
        components = payload.get("components", [])

        # Perform analysis (simplified for demonstration)
        analysis = {
            "ecosystem_type": ecosystem_type,
            "total_components": len(components),
            "health_score": 85,  # Simulated score
            "balance_metrics": {"diversity": 0.75, "resilience": 0.80, "efficiency": 0.70},
            "issues_detected": ["Component coupling above threshold", "Insufficient test coverage in module-3"],
            "recommendations": [
                "Decouple auth module from business logic",
                "Increase test coverage to 80%",
                "Add monitoring for critical paths",
            ],
        }

        # Save results
        output_file = self.results_dir / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(analysis, f, indent=2)

        return {
            "status": "success",
            "message": "Ecosystem analysis complete",
            "results": analysis,
            "output_file": str(output_file),
        }

    def optimize_balance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize the balance of the ecosystem

        Args:
            payload: Contains optimization parameters

        Returns:
            Optimization results with suggested changes
        """
        self.logger.info("Optimizing ecosystem balance")

        # Extract parameters
        target_metrics = payload.get("target_metrics", {})
        constraints = payload.get("constraints", [])

        # Perform optimization (simplified for demonstration)
        optimizations = {
            "proposed_changes": [
                {"component": "database", "action": "add_caching", "impact": "20% performance improvement"},
                {"component": "api_gateway", "action": "implement_rate_limiting", "impact": "Improved resilience"},
                {"component": "worker_pool", "action": "auto_scaling", "impact": "Better resource utilization"},
            ],
            "expected_improvements": {"performance": "+20%", "resilience": "+15%", "cost": "-10%"},
            "implementation_priority": ["add_caching", "implement_rate_limiting", "auto_scaling"],
        }

        # Save results
        output_file = self.results_dir / f"optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(optimizations, f, indent=2)

        return {
            "status": "success",
            "message": "Balance optimization complete",
            "results": optimizations,
            "output_file": str(output_file),
        }

    def fetch_climate_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch real climate data using EcoSystemiser's climate service

        Args:
            payload: Contains location, date range, and other parameters

        Returns:
            Result with status and path to saved climate data
        """
        if not CLIMATE_SERVICE_AVAILABLE:
            return {"status": "error", "message": "Climate service not available. Check EcoSystemiser installation."}

        self.logger.info("Fetching real climate data using EcoSystemiser service")

        try:
            # Extract and validate parameters
            location = payload.get("location", "51.5074,-0.1278")  # Default: London
            start_date = payload.get("start_date", "2023-07-01")
            end_date = payload.get("end_date", "2023-07-07")
            source = payload.get("source", "nasa_power")
            variables = payload.get("variables", ["temp_air", "ghi", "wind_speed"])

            # Parse location string into tuple
            if isinstance(location, str):
                parts = location.split(",")
                if len(parts) == 2:
                    lat, lon = float(parts[0]), float(parts[1])
                    location_tuple = (lat, lon)
                else:
                    return {"status": "error", "message": f"Invalid location format: {location}. Use 'lat,lon'"}
            else:
                location_tuple = location

            self.logger.info(f"Location: {location_tuple}, Period: {start_date} to {end_date}, Source: {source}")

            # Create the climate request
            climate_request = ClimateRequest(
                location=location_tuple,
                variables=variables,
                source=source,
                period={"start": start_date, "end": end_date},
                mode="observed",  # Use observed data
                resolution="1H",  # Hourly resolution
                timezone="UTC",
            )

            # Initialize climate service and process request
            service = ClimateService()
            self.logger.info("Processing climate request with EcoSystemiser service...")

            # Process the request (synchronous version)
            ds, response = service.process_request(climate_request)

            # Get the output path from response
            output_path = response.path_parquet if hasattr(response, "path_parquet") else None

            self.logger.info(f"Climate data successfully fetched and saved to: {output_path}")

            # Prepare successful response
            result = {
                "status": "success",
                "message": f"Climate data fetched for {location}",
                "location": location_tuple,
                "period": {"start": start_date, "end": end_date},
                "source": source,
                "variables": variables,
                "shape": response.shape if hasattr(response, "shape") else None,
                "output_file": output_path,
                "stats": response.stats if hasattr(response, "stats") else None,
            }

            # Also save a copy in our results directory for easy access
            if output_path and Path(output_path).exists():
                local_copy = self.results_dir / f"climate_{source}_{start_date}_{end_date}.parquet"
                import shutil

                shutil.copy2(output_path, local_copy)
                result["local_copy"] = str(local_copy)
                self.logger.info(f"Local copy saved to: {local_copy}")

            return result

        except Exception as e:
            self.logger.error(f"Error fetching climate data: {e}")
            import traceback

            self.logger.debug(traceback.format_exc())

            return {
                "status": "error",
                "message": f"Failed to fetch climate data: {str(e)}",
                "error_type": type(e).__name__,
            }

    def generate_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a comprehensive ecosystem report

        Args:
            payload: Report configuration parameters

        Returns:
            Report generation results
        """
        self.logger.info("Generating ecosystem report")

        # Extract parameters
        report_type = payload.get("report_type", "summary")
        include_visualizations = payload.get("include_visualizations", False)

        # Generate report content
        report = {
            "title": "EcoSystemiser Analysis Report",
            "generated_at": datetime.utcnow().isoformat(),
            "report_type": report_type,
            "executive_summary": "The ecosystem shows good overall health with opportunities for optimization",
            "sections": [
                {
                    "title": "Current State",
                    "content": "System is operating at 85% efficiency with stable performance metrics",
                },
                {
                    "title": "Key Findings",
                    "content": "Identified 3 areas for improvement: caching, rate limiting, and auto-scaling",
                },
                {
                    "title": "Recommendations",
                    "content": "Prioritize caching implementation for immediate performance gains",
                },
            ],
            "metrics_summary": {"health_score": 85, "efficiency": 0.85, "resilience": 0.80, "scalability": 0.75},
        }

        # Save report as JSON
        output_file = self.results_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        # Also create a markdown version
        md_file = output_file.with_suffix(".md")
        with open(md_file, "w") as f:
            f.write(f"# {report['title']}\n\n")
            f.write(f"Generated: {report['generated_at']}\n\n")
            f.write(f"## Executive Summary\n{report['executive_summary']}\n\n")
            for section in report["sections"]:
                f.write(f"## {section['title']}\n{section['content']}\n\n")
            f.write(f"## Metrics Summary\n")
            for key, value in report["metrics_summary"].items():
                f.write(f"- {key}: {value}\n")

        return {
            "status": "success",
            "message": "Report generated successfully",
            "report": report,
            "output_files": {"json": str(output_file), "markdown": str(md_file)},
        }


def main():
    """Main entry point for the adapter"""
    parser = argparse.ArgumentParser(description="EcoSystemiser Hive Adapter")
    parser.add_argument("--task", required=True, help="Task name to execute")
    parser.add_argument("--payload", type=str, default="{}", help="JSON payload for the task")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging("ecosystemiser", level=log_level)

    # Parse payload
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing payload: {e}")
        sys.exit(1)

    # Execute task
    adapter = EcoSystemiserAdapter()
    result = adapter.execute_task(args.task, payload)

    # Output result
    logger.info(json.dumps(result, indent=2))

    # Exit with appropriate code
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()

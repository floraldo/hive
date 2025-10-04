#!/usr/bin/env python
"""
Submit hive-catalog requirement to Colossus Command Center.

This script demonstrates Project Genesis Phase 2: The First Creation.
It submits a service requirement to hive-ui and monitors the autonomous
development pipeline execution.
"""

import asyncio
import sys

import httpx

from hive_logging import get_logger

logger = get_logger(__name__)

# Requirement for hive-catalog service
HIVE_CATALOG_REQUIREMENT = """
Create a hive-catalog service that provides a centralized catalog and registry for all Hive platform services.

Core Functionality:
- Service registration with metadata (name, version, type, endpoints, health_check_url)
- Service discovery by name or ID
- List all services with filtering
- Update service metadata
- Deregister services
- Health monitoring with status tracking

API Endpoints:
- POST /services - Register new service
- GET /services - List all services
- GET /services/{service_id} - Get service details
- PUT /services/{service_id} - Update service
- DELETE /services/{service_id} - Deregister service
- GET /services/{service_id}/health - Get health status

Technical Requirements:
- FastAPI with async support
- In-memory storage (dict) for MVP
- Pydantic models for validation
- hive-logging and hive-config packages
- Golden Rules compliant
- 80%+ test coverage

Data Model:
{
  "service_id": "uuid",
  "name": "string",
  "version": "string",
  "type": "api|worker|batch",
  "endpoints": ["url"],
  "health_check_url": "url",
  "metadata": {"description": "string", "tags": [], "owner": "string"},
  "status": "healthy|unhealthy|unknown",
  "registered_at": "iso8601",
  "last_health_check": "iso8601"
}
"""


async def submit_project(api_url: str = "http://localhost:8000") -> str:
    """
    Submit hive-catalog project to Command Center.

    Args:
        api_url: Base URL for hive-ui API

    Returns:
        project_id: Created project ID
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info("Submitting hive-catalog requirement to Colossus...")

        response = await client.post(
            f"{api_url}/api/projects",
            json={
                "requirement": HIVE_CATALOG_REQUIREMENT,
                "service_name": "hive-catalog",
            },
        )

        if response.status_code != 200:
            logger.error(f"Failed to create project: {response.status_code}")
            logger.error(f"Response: {response.text}")
            raise RuntimeError("Project creation failed")

        result = response.json()
        project_id = result["project_id"]

        logger.info(f"✅ Project created: {project_id}")
        logger.info(f"Status URL: {result['status_url']}")

        return project_id


async def monitor_project(
    project_id: str,
    api_url: str = "http://localhost:8000",
    poll_interval: int = 3,
) -> dict:
    """
    Monitor project execution until completion.

    Args:
        project_id: Project to monitor
        api_url: Base URL for hive-ui API
        poll_interval: Seconds between status checks

    Returns:
        final_project_state: Project data when complete/failed
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info(f"Monitoring project {project_id}...")

        last_status = None
        last_log_count = 0

        while True:
            # Get project status
            response = await client.get(f"{api_url}/api/projects/{project_id}")

            if response.status_code != 200:
                logger.error(f"Failed to get project status: {response.status_code}")
                break

            project = response.json()
            status = project["status"]

            # Print status change
            if status != last_status:
                logger.info(f"Status: {status.upper()}")
                last_status = status

            # Print new logs
            logs = project.get("logs", [])
            if len(logs) > last_log_count:
                for log in logs[last_log_count:]:
                    logger.info(f"  📋 {log}")
                last_log_count = len(logs)

            # Check if complete
            if status in ("complete", "failed"):
                logger.info(f"Pipeline finished: {status.upper()}")
                return project

            await asyncio.sleep(poll_interval)


async def main():
    """Execute Phase 2: The First Creation."""
    logger.info("=" * 80)
    logger.info("PROJECT GENESIS - PHASE 2: THE FIRST CREATION")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Target: Autonomous generation of hive-catalog service")
    logger.info("Pipeline: Architect → Coder → Guardian")
    logger.info("")

    try:
        # Submit project
        project_id = await submit_project()

        # Monitor execution
        final_state = await monitor_project(project_id)

        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("PIPELINE EXECUTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Final Status: {final_state['status'].upper()}")
        logger.info(f"Service Name: {final_state['service_name']}")
        logger.info(f"Workspace: {final_state['workspace']}")

        if final_state.get("plan_file"):
            logger.info(f"Execution Plan: {final_state['plan_file']}")

        if final_state.get("service_dir"):
            logger.info(f"Generated Code: {final_state['service_dir']}")

        logger.info("")
        logger.info("Execution Logs:")
        for log in final_state.get("logs", []):
            logger.info(f"  {log}")

        # Check success
        if final_state["status"] == "complete":
            logger.info("")
            logger.info("🎉 SUCCESS: hive-catalog generated autonomously!")
            logger.info("")
            logger.info("Next steps:")
            logger.info("  1. Review generated code in workspace")
            logger.info("  2. Run tests: pytest {service_dir}/tests/")
            logger.info("  3. Validate API endpoints")
            logger.info("  4. Proceed to Phase 3: Graduation")
            return 0
        else:
            logger.error("")
            logger.error("❌ FAILED: Pipeline did not complete successfully")
            logger.error("Review logs above for error details")
            return 1

    except Exception as e:
        logger.exception(f"Error during Phase 2 execution: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

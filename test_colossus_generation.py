#!/usr/bin/env python3
"""Test Colossus autonomous service generation with hive-catalog."""

import asyncio
import sys
from pathlib import Path

# Add hive-ui to path
sys.path.insert(0, str(Path(__file__).parent / "apps/hive-ui/src"))

from hive_ui.orchestrator import ProjectOrchestrator


async def generate_hive_catalog():
    """Generate hive-catalog service using Colossus pipeline."""

    requirement = '''
Create a 'hive-catalog' REST API service that maintains an intelligent registry of all platform services, components, and their relationships.

Core Features:
- Service discovery and registration
- Health monitoring and status tracking
- Dependency graph visualization
- Component metadata management
- Version tracking and compatibility checking

Technical Requirements:
- FastAPI REST endpoints
- SQLite persistence layer
- In-memory caching for fast lookups
- Event bus integration for real-time updates
- Health check endpoint

Expected JSON structure:
{
  "service_id": "uuid",
  "name": "hive-catalog",
  "type": "api",
  "capabilities": ["service discovery", "health monitoring"]
}
'''

    print('Generating hive-catalog service via Colossus...')
    print('=' * 60)

    orchestrator = ProjectOrchestrator()

    try:
        # Create project with explicit service name
        project_id = await orchestrator.create_project(
            requirement=requirement,
            service_name='hive-catalog'
        )

        print(f'Project created: {project_id}')

        # Execute autonomous pipeline
        result = await orchestrator.execute_project(project_id)

        print('\nGeneration Result:')
        print(f'  Status: {result["status"]}')
        print(f'  Service Dir: {result.get("service_dir", "N/A")}')
        print('\nExecution Log:')
        for log in result['logs'][-10:]:  # Last 10 logs
            print(f'  {log}')

        return result

    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    result = asyncio.run(generate_hive_catalog())
    sys.exit(0 if result and result['status'] == 'COMPLETE' else 1)

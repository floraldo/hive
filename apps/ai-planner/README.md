# AI Planner

Intelligent task planning and orchestration service for the Hive platform.

## Features

- Automated task planning and decomposition
- Intelligent resource allocation
- Async task processing with queue management
- Integration with Hive orchestration system

## Usage

```python
from ai_planner.core import PlannerService

planner = PlannerService()
await planner.create_plan(task_specification)
```

## Configuration

Configuration is managed through the core config system extending hive-config.

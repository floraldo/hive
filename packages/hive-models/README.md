# Hive Models

Shared data models and domain objects for the Hive platform.

## Purpose

This package provides centralized data models that are shared across multiple Hive applications, ensuring:
- Consistent data structures across the platform
- Type safety with Pydantic models
- Clean dependency direction (apps depend on packages, not on each other)
- Single source of truth for domain models

## Structure

```
hive_models/
├── __init__.py           # Public API exports
├── base.py              # Base models and mixins
├── deployment.py        # Deployment-related models
├── review.py           # Code review models
├── planning.py         # Planning and task models
├── orchestration.py    # Orchestration and workflow models
├── climate.py          # Climate and environmental models
└── common.py           # Common shared models
```

## Usage

```python
from hive_models import DeploymentTask, ReviewRequest, PlanningTask
from hive_models.base import BaseModel, TimestampMixin

# Use models in your application
task = DeploymentTask(
    name="Deploy API",
    target="production",
    config={"replicas": 3}
)
```

## Design Principles

1. **Pure Data Models**: No business logic, only data structure definitions
2. **Validation**: Use Pydantic for automatic validation
3. **Type Safety**: Full type hints for all models
4. **Serialization**: JSON-serializable by default
5. **Versioning**: Models are versioned for backward compatibility

## Dependencies

- `pydantic`: For data validation and serialization
- `typing-extensions`: For advanced type hints

## Golden Rules Compliance

This package follows Hive platform Golden Rules:
- ✅ Pure infrastructure package (no business logic)
- ✅ No app dependencies (only standard libraries)
- ✅ Full type annotations
- ✅ Comprehensive documentation
- ✅ Proper error handling with validation
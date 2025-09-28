# ADR-004: Service Layer Architecture

## Status
Accepted

## Context
The Hive platform initially mixed business logic with infrastructure concerns, leading to:
- Difficult testing due to coupled dependencies
- Unclear boundaries between layers
- Business logic scattered across multiple layers
- Core modules containing implementation details
- Violation of clean architecture principles

## Decision
We will implement a strict Service Layer Architecture with clear separation:

1. **Core Layer** (`core/`): Pure interfaces and contracts
   - No business logic
   - No external dependencies
   - Only abstract base classes and protocols

2. **Service Layer** (`services/`): Business logic implementation
   - Implements core interfaces
   - Contains all business rules and workflows
   - Depends only on core interfaces, not implementations

3. **Infrastructure Layer**: External integrations
   - Database, APIs, file systems
   - Implements core interfaces for external services

## Consequences

### Positive
- **Testability**: Business logic testable without infrastructure
- **Flexibility**: Easy to swap infrastructure implementations
- **Clarity**: Clear separation of concerns
- **Maintainability**: Changes isolated to appropriate layers
- **Reusability**: Business logic reusable across different infrastructures

### Negative
- **More Files**: Separation requires interface and implementation files
- **Indirection**: Additional layer of abstraction
- **Initial Complexity**: More design work upfront

## Implementation

### Directory Structure
```
apps/hive-orchestrator/
├── core/                    # Interfaces only
│   ├── claude/
│   │   └── interfaces.py   # Abstract interfaces
│   └── monitoring/
│       └── interfaces.py   # Abstract interfaces
└── services/               # Business logic
    ├── claude/
    │   └── implementation.py  # Concrete implementations
    └── monitoring/
        └── pipeline_impl.py   # Concrete implementations
```

### Example Code
```python
# core/monitoring/interfaces.py - Interface only
from abc import ABC, abstractmethod

class MetricsCollectorInterface(ABC):
    @abstractmethod
    def record_metric(self, name: str, value: float) -> None:
        pass

# services/monitoring/implementation.py - Business logic
from core.monitoring.interfaces import MetricsCollectorInterface

class PrometheusCollector(MetricsCollectorInterface):
    def record_metric(self, name: str, value: float) -> None:
        # Actual business logic here
        self.metrics[name] = value
        self._push_to_prometheus()
```

## Migration Path
1. Create interface definitions in core/
2. Move implementations to services/
3. Update imports throughout codebase
4. Validate with Golden Rules enforcement

## Related
- ADR-001: Dependency Injection Pattern
- ADR-002: Golden Rules Architectural Governance
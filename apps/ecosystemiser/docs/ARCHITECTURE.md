# EcoSystemiser Architecture

## Overview

EcoSystemiser is built as a **modular monolith** - a single deployable unit with clear internal boundaries and modular structure. This architecture provides the simplicity of a monolith with the modularity needed for future growth.

## Directory Structure

```
apps/EcoSystemiser/
├── __init__.py
├── main.py              # Application entry point
├── settings.py          # Centralized configuration
├── errors.py            # Shared error handling
├── observability.py     # Monitoring and logging
├── worker.py            # Background task worker
│
├── profile_loader/      # Time series data loading module
│   ├── __init__.py
│   ├── shared/          # Shared components across all loaders
│   │   ├── models.py    # Base data models
│   │   └── timeseries.py # Common time series utilities
│   │
│   ├── climate/         # Climate data profile loader
│   │   ├── adapters/    # Data source adapters
│   │   │   ├── base.py  # Unified base adapter with async support
│   │   │   ├── factory.py # Adapter factory pattern
│   │   │   ├── nasa_power.py
│   │   │   ├── meteostat.py
│   │   │   ├── era5.py
│   │   │   ├── pvgis.py
│   │   │   └── file_epw.py
│   │   ├── processing/  # Data processing pipeline
│   │   │   ├── pipeline.py # Main processing pipeline
│   │   │   ├── preprocessing/
│   │   │   └── postprocessing/
│   │   ├── analysis/    # Domain-specific analysis
│   │   │   ├── building_science.py
│   │   │   ├── extremes.py
│   │   │   └── synthetic/
│   │   ├── cache/       # Caching layer
│   │   ├── service.py   # Climate service layer
│   │   └── data_models.py
│   │
│   └── demand/          # Demand profile loader (future)
│       ├── __init__.py
│       └── models.py    # Demand-specific models
│
├── analyser/            # Analysis and optimization module
│   └── __init__.py
│
├── solver/              # Optimization solver module
│   └── __init__.py
│
└── reporting/           # Reporting and visualization
    └── __init__.py
```

## Key Design Principles

### 1. Modular Monolith Architecture

- **Single Deployment**: One application to deploy and manage
- **Clear Boundaries**: Well-defined module interfaces
- **Future-Ready**: Can be split into microservices if needed

### 2. Unified Adapter Pattern

All data source adapters inherit from a single `BaseAdapter` class that provides:
- Async HTTP client with connection pooling
- Retry logic with exponential backoff
- Rate limiting per data source
- Three-tier caching (memory → disk → Redis)
- Standardized error handling

### 3. Processing Pipeline

Data processing is managed through a configurable `ProcessingPipeline` that:
- Separates preprocessing from postprocessing
- Allows enabling/disabling individual steps
- Provides execution reports for traceability
- Maintains consistency across all data sources

### 4. Shared Resources

Common functionality is shared across profile types through:
- `BaseProfileRequest` and `BaseProfileResponse` models
- Time series utilities in `shared/timeseries.py`
- Centralized settings in `settings.py`
- Unified error handling in `errors.py`

### 5. Service Layer Pattern

Each module has a service layer that:
- Orchestrates adapters and processing
- Handles business logic
- Manages fallback strategies
- Provides a clean API to other modules

## Configuration

All configuration is centralized in `settings.py` using Pydantic settings:

```python
from settings import get_settings

settings = get_settings()
```

Configuration includes:
- Adapter enablement and settings
- Cache configuration
- API settings
- Observability configuration
- Processing pipeline settings

## Testing Architecture

Tests mirror the application structure:

```
tests/
└── apps/
    └── EcoSystemiser/
        ├── profile_loader/
        │   ├── climate/
        │   │   ├── adapters/
        │   │   ├── processing/
        │   │   └── analysis/
        │   └── shared/
        └── test_integration.py
```

## Adding New Profile Types

To add a new profile type (e.g., demand profiles):

1. Create directory: `profile_loader/demand/`
2. Create models inheriting from base: `models.py`
3. Implement adapters extending `BaseAdapter`
4. Create service layer
5. Add to settings configuration
6. Write tests following the same structure

## Benefits of This Architecture

1. **Simplicity**: Single application to understand and deploy
2. **Modularity**: Clear separation of concerns
3. **Reusability**: Shared components across profile types
4. **Extensibility**: Easy to add new profile types or adapters
5. **Testability**: Clear boundaries make testing easier
6. **Performance**: Shared resources like connection pools
7. **Future-Proof**: Can evolve to microservices if needed

## Migration Path

If future requirements demand microservices:

1. Each top-level module can become a service
2. Shared components become a shared library
3. Service layers become API gateways
4. Internal calls become HTTP/gRPC calls

The modular structure ensures this transition would be straightforward.
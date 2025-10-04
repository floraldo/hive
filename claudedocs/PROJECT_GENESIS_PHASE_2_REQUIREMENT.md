# Project Genesis Phase 2: hive-catalog Service Requirement

**Date**: 2025-10-04
**Phase**: 2 - The First Creation
**Target Service**: hive-catalog

## Natural Language Requirement

Create a **hive-catalog** service that provides a centralized catalog and registry for all Hive platform services and components.

### Core Functionality

**Service Discovery**:
- Register new services with metadata (name, version, type, endpoints, health check URL)
- Retrieve service information by name or ID
- List all registered services with filtering capabilities
- Update service metadata
- Deregister services

**Health Monitoring**:
- Periodic health checks for registered services
- Service status tracking (healthy, unhealthy, unknown)
- Health history and uptime metrics

**API Requirements**:
- `POST /services` - Register new service
- `GET /services` - List all services (with optional filters)
- `GET /services/{service_id}` - Get service details
- `PUT /services/{service_id}` - Update service metadata
- `DELETE /services/{service_id}` - Deregister service
- `GET /services/{service_id}/health` - Get service health status

### Data Model

**Service Registration**:
```python
{
    "service_id": "uuid",
    "name": "service-name",
    "version": "1.0.0",
    "type": "api|worker|batch",
    "endpoints": ["http://localhost:8000"],
    "health_check_url": "http://localhost:8000/health/live",
    "metadata": {
        "description": "Service description",
        "tags": ["tag1", "tag2"],
        "owner": "team-name"
    },
    "status": "healthy|unhealthy|unknown",
    "registered_at": "2025-10-04T12:00:00Z",
    "last_health_check": "2025-10-04T12:05:00Z"
}
```

### Technical Requirements

**Framework**: FastAPI with async support
**Storage**: In-memory dictionary for MVP (extensible to database later)
**Logging**: Use hive-logging package
**Configuration**: Use hive-config with DI pattern
**Validation**: Pydantic models for request/response validation
**Testing**: Comprehensive unit and integration tests (≥80% coverage)

### Quality Standards

- Golden Rules compliant (DI pattern, no print statements, proper error handling)
- Type hints on all functions
- Comprehensive docstrings
- API documentation via FastAPI automatic docs
- Health check endpoints (liveness and readiness probes)

### Success Criteria

1. All API endpoints functional and tested
2. Service registration and deregistration working
3. Health check integration operational
4. 100% test pass rate
5. Ruff linting passes with zero errors
6. Syntax validation passes
7. Deployment-ready code quality

## Expected Execution Plan Tasks

The Architect Agent should generate an ExecutionPlan with approximately:
1. **Scaffold Task**: Generate service structure with hive-app-toolkit
2. **API Endpoint Tasks**: Implement service registration, listing, retrieval, update, deletion, health endpoints
3. **Data Models**: Pydantic models for Service, HealthStatus, etc.
4. **Business Logic**: Service registry manager, health checker
5. **Test Suite**: Unit tests for all endpoints and business logic
6. **Documentation**: API docs and README

## Validation Criteria

**Architect Phase**: ExecutionPlan generated with valid task structure
**Coder Phase**: Service code generated with all endpoints implemented
**Guardian Phase**: Syntax validation passes, basic quality checks pass

---

**This requirement will be submitted to the hive-ui Command Center for autonomous execution via the Colossus pipeline.**

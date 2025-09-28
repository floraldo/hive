# EcoSystemiser API v3.0 Documentation

## Overview

The EcoSystemiser API v3.0 provides a comprehensive platform for sustainable energy system analysis with enhanced type safety, validation, and monitoring capabilities.

## Key Features

- **Type-Safe Interface**: Comprehensive Pydantic models for all requests and responses
- **Enhanced Validation**: Input validation with detailed error messages
- **Monitoring & Health Checks**: Real-time system metrics and health monitoring
- **OpenAPI Documentation**: Interactive API documentation with Swagger UI
- **Structured Error Handling**: Consistent error responses with correlation IDs
- **Production-Grade Logging**: Comprehensive logging with correlation tracking

## API Modules

### 1. Platform Management
- **Health Checks**: `/health` - Enhanced health monitoring with component-level checks
- **System Metrics**: `/metrics` - Real-time performance and resource metrics
- **Version Info**: `/version` - Detailed version and feature information
- **Platform Info**: `/` - Module status and capability overview

### 2. Profile Loader (Active)
- **Climate Data**: `/api/v3/profile/climate/*` - Enhanced climate data endpoints
- **Batch Processing**: Support for multiple location requests
- **Streaming Responses**: Memory-efficient large dataset handling
- **Async Jobs**: Background processing for heavy requests

### 3. Solver Module (Planned)
- **Status**: `/api/v3/solver/status` - Module readiness and capabilities
- **Optimization**: Future endpoints for energy system optimization

### 4. Analyser Module (Planned)
- **Status**: `/api/v3/analyser/status` - Module readiness and capabilities
- **Analytics**: Future endpoints for post-processing analysis

### 5. Reporting Module (Planned)
- **Status**: `/api/v3/reporting/status` - Module readiness and capabilities
- **Reports**: Future endpoints for automated report generation

## Enhanced Features in v3.0

### Type Safety
All endpoints now use comprehensive Pydantic models:
- **Request Validation**: Automatic validation of input parameters
- **Response Models**: Structured, typed responses
- **Error Models**: Consistent error response format

### Health Monitoring
Enhanced health checks covering:
- Database connectivity
- Profile loader service status
- Cache system health
- Filesystem accessibility
- System resource monitoring

### API Documentation
- **OpenAPI 3.0**: Complete specification
- **Interactive Docs**: Swagger UI at `/docs`
- **ReDoc**: Alternative documentation at `/redoc`
- **Schema Export**: OpenAPI JSON at `/openapi.json`

### Error Handling
Structured error responses with:
- Error classification
- Detailed error messages
- Correlation ID tracking
- Timestamp information
- Optional debug details

### Legacy Support
- **v2 Redirects**: Automatic redirection from v2 endpoints to v3
- **Migration Guidance**: Links to migration documentation
- **Deprecation Warnings**: Clear notification of deprecated features

## Example Usage

### Health Check
```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "platform": "EcoSystemiser",
  "timestamp": "2025-01-28T10:30:00Z",
  "version": "3.0.0",
  "checks": {
    "database": true,
    "profile_loader": true,
    "cache": true,
    "filesystem": true
  }
}
```

### System Metrics
```bash
GET /metrics
```

Response:
```json
{
  "timestamp": "2025-01-28T10:30:00Z",
  "system_metrics": {
    "cpu_usage": 15.5,
    "memory_usage": 45.2,
    "disk_usage": 67.8,
    "active_connections": 12,
    "request_rate": 25.3,
    "error_rate": 0.1,
    "uptime_seconds": 86400
  },
  "performance_metrics": {
    "avg_response_time": 0.125,
    "p95_response_time": 0.250,
    "p99_response_time": 0.500,
    "requests_per_second": 10.0,
    "cache_hit_rate": 85.0
  },
  "health_checks": {
    "database": true,
    "profile_loader": true,
    "cache": true,
    "filesystem": true
  }
}
```

### Platform Information
```bash
GET /
```

Response:
```json
{
  "platform": "EcoSystemiser",
  "version": "3.0.0",
  "modules": {
    "profile_loader": {
      "status": "active",
      "endpoints": ["/api/v3/profile/climate", "/api/v3/profile/demand"],
      "version": "2.0.0",
      "description": "Climate and demand profile data loader with multiple adapters"
    },
    "solver": {
      "status": "planned",
      "endpoints": [],
      "description": "Optimization solver for energy system analysis"
    }
  },
  "uptime": "24:00:00",
  "build_info": {
    "version": "3.0.0",
    "build_date": "2025-01-28T10:30:00Z",
    "environment": "production"
  }
}
```

## API Standards

### Request Headers
- `Content-Type: application/json` (for POST/PUT requests)
- `Accept: application/json`
- `X-Correlation-ID: <uuid>` (optional, auto-generated if not provided)

### Response Headers
- `Content-Type: application/json`
- `X-Correlation-ID: <uuid>` (for request tracking)
- `Cache-Control: no-cache` (for streaming endpoints)

### Error Responses
All errors follow a consistent structure:
```json
{
  "error": "ValidationError",
  "message": "Field 'location' is required",
  "details": {
    "field": "location",
    "invalid_value": null
  },
  "correlation_id": "12345678-1234-1234-1234-123456789012",
  "timestamp": "2025-01-28T10:30:00Z"
}
```

### Status Codes
- `200`: Success
- `201`: Created
- `301`: Permanent redirect (for legacy endpoints)
- `400`: Bad request (validation errors)
- `404`: Not found
- `500`: Internal server error

## Development Features

### Interactive Documentation
- **Swagger UI**: Available at `/docs`
- **ReDoc**: Available at `/redoc`
- **OpenAPI Spec**: Available at `/openapi.json`

### Testing Support
- **Type Safety**: Automatic request/response validation
- **Mock Responses**: Consistent response structures for testing
- **Health Endpoints**: Easy integration testing

## Migration from v2

v2 endpoints are automatically redirected to v3 with:
- HTTP 301 permanent redirect
- Migration guidance
- Documentation links

Example v2 to v3 migration:
- `GET /api/v2/climate/single` → `GET /api/v3/profile/climate/single`
- Enhanced request/response models
- Additional validation and error handling

## Performance Considerations

- **Streaming**: Large datasets use streaming responses
- **Async Processing**: Background jobs for heavy operations
- **Caching**: Intelligent caching for frequently accessed data
- **Resource Monitoring**: Real-time performance tracking

## Security Features

- **Input Validation**: Comprehensive validation using Pydantic
- **Error Sanitization**: Safe error messages without sensitive data
- **CORS Configuration**: Configurable cross-origin resource sharing
- **Health Isolation**: Component-level health checks

## Future Enhancements

The API is designed for extensibility with planned additions:
- **Authentication**: OAuth2/JWT token support
- **Rate Limiting**: Request throttling and quotas
- **Async Workflows**: Multi-step processing pipelines
- **Real-time Updates**: WebSocket support for live data
- **Advanced Analytics**: ML-powered insights and recommendations
# hive-ui API Documentation

Version: 0.1.0

## Base URL

```
http://localhost:8000
```

## Authentication

*Add authentication documentation here*

## Endpoints

### Health Checks

#### GET /health/live

Liveness probe for Kubernetes health checks.

**Response**

```json
{
  "status": "alive",
  "timestamp": "2025-10-04T12:00:00.000000",
  "service": "hive-ui"
}
```

#### GET /health/ready

Readiness probe for Kubernetes traffic routing.

**Response**

```json
{
  "status": "ready",
  "timestamp": "2025-10-04T12:00:00.000000",
  "service": "hive-ui"
}
```

### API Endpoints

*Add your API endpoints documentation here*

## Error Responses

All endpoints return standard error responses:

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2025-10-04T12:00:00.000000"
}
```

## Rate Limiting

- Per-operation limit: $1.0
- Daily limit: $(100.0,)
- Monthly limit: $(2000.0,)

## Examples

### cURL

```bash
# Liveness check
curl http://localhost:8000/health/live

# Readiness check
curl http://localhost:8000/health/ready
```

### Python

```python
import requests

# Liveness check
response = requests.get("http://localhost:8000/health/live")
print(response.json())

# Readiness check
response = requests.get("http://localhost:8000/health/ready")
print(response.json())
```

## Interactive Documentation

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

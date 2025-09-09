# test-weather-service

Test Weather Service API

## Features

- Flask REST API with CORS support
- Structured logging with hive-logging
- Health check endpoints
- Docker support
- Gunicorn production server
- Test suite with pytest

## Quick Start

### Development

1. Install dependencies:
```bash
pip install -e .
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Run the development server:
```bash
python app.py
```

The API will be available at http://localhost:5000

### Production

1. Build Docker image:
```bash
docker build -t test-weather-service .
```

2. Run container:
```bash
docker run -p 5000:5000 --env-file .env test-weather-service
```

## API Endpoints

- `GET /api/health` - Health check endpoint
- `GET /api/info` - Application information

## Testing

Run tests with pytest:
```bash
pytest tests/
```

With coverage:
```bash
pytest --cov=api tests/
```

## Deployment

This project is configured for deployment with the Hive orchestrator:
```bash
hive deploy test-weather-service
```

## Project Structure

```
test-weather-service/
├── api/                # API blueprints
│   ├── __init__.py
│   └── health.py      # Health endpoints
├── tests/             # Test suite
│   ├── __init__.py
│   └── test_health.py
├── app.py             # Main Flask application
├── pyproject.toml     # Project dependencies
├── Dockerfile         # Container configuration
├── .env.example       # Environment template
└── .deployignore      # Deployment exclusions
```

## Environment Variables

- `FLASK_ENV` - Environment (development/production)
- `SECRET_KEY` - Flask secret key
- `PORT` - Server port (default: 5000)

## Built with Hive

This project was scaffolded using the Hive orchestrator Flask API template.
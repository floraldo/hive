# EcoSystemiser v3.0 Deployment Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Quick Start](#quick-start)
3. [Production Deployment](#production-deployment)
4. [Configuration](#configuration)
5. [Service Architecture](#service-architecture)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Storage**: 10 GB free space
- **OS**: Linux (Ubuntu 20.04+), macOS, or Windows with WSL2
- **Docker**: 20.10+
- **Docker Compose**: 2.0+

### Recommended Production Requirements
- **CPU**: 4+ cores
- **RAM**: 8+ GB
- **Storage**: 50+ GB SSD
- **Network**: Stable internet for external data sources

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/your-org/hive.git
cd hive/apps/ecosystemiser
```

### 2. Set Environment Variables
```bash
# Copy the example environment file
cp .env.example .env

# Edit with your configuration
nano .env
```

### 3. Build and Start Services
```bash
# Build all services
docker-compose build

# Start core services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Verify Installation
```bash
# Check service health
curl http://localhost:8000/health

# Access web interfaces:
# - API Documentation: http://localhost:8000/docs
# - Reporting Dashboard: http://localhost:5000
# - Streamlit Dashboard: http://localhost:8501 (if enabled)
```

## Production Deployment

### 1. Enable Production Profile
```bash
# Start with production configurations
docker-compose --profile production up -d
```

### 2. Use PostgreSQL Instead of SQLite
```bash
# Start with PostgreSQL
docker-compose --profile postgres up -d

# Update .env with PostgreSQL connection
DATABASE_URL=postgresql://ecosys:password@postgres:5432/ecosystemiser
```

### 3. Configure Nginx SSL
```bash
# Create SSL certificates
mkdir ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/nginx.key -out ssl/nginx.crt

# Update nginx.conf with your domain
cp nginx.conf.example nginx.conf
nano nginx.conf
```

### 4. Scale Workers
```bash
# Scale analyser workers for parallel processing
docker-compose up -d --scale analyser-worker=3
```

## Configuration

### Environment Variables

#### Core Settings
| Variable | Description | Default |
|----------|-------------|---------|
| `ECOSYS_ENV` | Environment (development/production) | `production` |
| `ECOSYS_LOG_LEVEL` | Logging level | `INFO` |
| `DATABASE_URL` | Database connection string | `sqlite:///data/ecosys.db` |
| `SECRET_KEY` | Application secret key | (generate unique) |

#### Service URLs
| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | Main API endpoint | `http://localhost:8000` |
| `REPORTING_URL` | Reporting service | `http://localhost:5000` |
| `HIVE_BUS_HOST` | Message bus host | `hive-bus` |
| `HIVE_BUS_PORT` | Message bus port | `6379` |

#### Resource Limits
| Variable | Description | Default |
|----------|-------------|---------|
| `MAX_WORKERS` | Maximum parallel workers | `4` |
| `MEMORY_LIMIT` | Container memory limit | `2G` |
| `CPU_LIMIT` | Container CPU limit | `2.0` |

### Volume Mounts

| Local Path | Container Path | Purpose |
|------------|----------------|---------|
| `./results` | `/app/results` | Simulation results |
| `./reports` | `/app/reports` | Generated reports |
| `./data` | `/app/data` | Database and cache |
| `./logs` | `/app/logs` | Application logs |

## Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Nginx (Port 80/443)                  │
└─────────────┬───────────────────────┬───────────────────┘
              │                       │
    ┌─────────▼──────────┐  ┌────────▼──────────┐
    │  EcoSystemiser API  │  │  Reporting App    │
    │    (Port 8000)      │  │   (Port 5000)     │
    └─────────┬───────────┘  └─────────────────┘
              │
    ┌─────────▼───────────────────────┐
    │       Hive Bus (Redis)          │
    └─────────┬───────────────────────┘
              │
    ┌─────────▼──────────┐
    │  Analyser Workers  │
    │   (Scaled 1-N)     │
    └────────────────────┘
```

### Service Descriptions

- **ecosystemiser-api**: Main FastAPI application handling all API requests
- **analyser-worker**: Background workers for async analysis tasks
- **reporting-app**: Flask application for report generation and viewing
- **dashboard**: Optional Streamlit dashboard for interactive exploration
- **hive-bus**: Redis message bus for inter-service communication
- **postgres**: Optional PostgreSQL database for production
- **nginx**: Reverse proxy for SSL termination and load balancing

## Monitoring & Maintenance

### Health Checks
```bash
# Check all service status
docker-compose ps

# Check specific service health
curl http://localhost:8000/health
curl http://localhost:5000/health
```

### Log Management
```bash
# View all logs
docker-compose logs

# Follow specific service logs
docker-compose logs -f ecosystemiser-api

# Export logs for analysis
docker-compose logs > deployment_logs_$(date +%Y%m%d).txt
```

### Backup & Recovery
```bash
# Backup data volumes
docker run --rm -v ecosystemiser_postgres-data:/data \
  -v $(pwd)/backups:/backup alpine \
  tar czf /backup/postgres_$(date +%Y%m%d).tar.gz /data

# Backup results and reports
tar czf backups/results_$(date +%Y%m%d).tar.gz results/ reports/

# Restore from backup
tar xzf backups/results_20240101.tar.gz
```

### Updates
```bash
# Pull latest changes
git pull origin main

# Rebuild services
docker-compose build --no-cache

# Rolling update
docker-compose up -d --no-deps --build ecosystemiser-api
```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Check what's using the port
lsof -i :8000

# Change port in docker-compose.yml
ports:
  - "8001:8000"  # Use different host port
```

#### 2. Database Connection Failed
```bash
# Check database container
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up -d postgres
docker-compose exec postgres psql -U ecosys -c "CREATE DATABASE ecosystemiser;"
```

#### 3. Out of Memory
```bash
# Increase Docker memory limits
# Docker Desktop: Settings > Resources > Memory

# Or limit service memory in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G
```

#### 4. Slow Performance
```bash
# Scale workers
docker-compose up -d --scale analyser-worker=5

# Check resource usage
docker stats

# Clear cache
docker system prune -a
```

### Debug Mode
```bash
# Run in debug mode
ECOSYS_ENV=development ECOSYS_LOG_LEVEL=DEBUG docker-compose up

# Access container shell
docker-compose exec ecosystemiser-api bash

# Run diagnostics
python -m EcoSystemiser.diagnostics
```

### Support

For issues and questions:
1. Check the [FAQ](./docs/FAQ.md)
2. Review [GitHub Issues](https://github.com/your-org/hive/issues)
3. Contact support: support@ecosystemiser.com

## Security Considerations

### Production Checklist
- [ ] Change default passwords in `.env`
- [ ] Configure SSL certificates
- [ ] Set up firewall rules
- [ ] Enable rate limiting in Nginx
- [ ] Configure log rotation
- [ ] Set up monitoring alerts
- [ ] Regular security updates
- [ ] Backup strategy in place

### API Authentication
```bash
# Generate secure API key
openssl rand -hex 32

# Add to .env
API_KEY=your_generated_key
```

## Performance Tuning

### Optimization Tips
1. Use PostgreSQL for production (10x faster than SQLite)
2. Scale analyser workers based on CPU cores
3. Enable Redis persistence for reliability
4. Configure Nginx caching for static assets
5. Use SSD storage for database and results

### Benchmarking
```bash
# Run performance tests
docker-compose exec ecosystemiser-api python -m pytest tests/performance/

# Monitor resource usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

---

**Version**: 3.0.0
**Last Updated**: September 2024
**Maintainer**: EcoSystemiser Team
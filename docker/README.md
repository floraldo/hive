# Hive Fleet Command - Docker Infrastructure

This directory contains the Docker configuration and orchestration files for the Hive Fleet Command System, a multi-agent AI collaboration platform.

## Architecture Overview

The system consists of the following services:

- **Queen (Orchestrator)**: Fleet commander that delegates tasks to workers
- **Frontend Worker**: React/Next.js specialist for UI development
- **Backend Worker**: Python/Flask/FastAPI specialist for API development
- **Infrastructure Worker**: Docker/Kubernetes/CI specialist for DevOps
- **Message Bus (Redis)**: Inter-agent communication backbone
- **Database (PostgreSQL)**: Persistent data storage
- **Nginx**: Reverse proxy and load balancer (production)

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum
- 20GB free disk space

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd hive
   ```

2. **Copy environment template:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start development environment:**
   ```bash
   cd docker
   make dev
   ```

4. **View logs:**
   ```bash
   make dev-logs
   ```

5. **Access services:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Queen API: http://localhost:5000
   - Adminer (DB): http://localhost:8082
   - Redis Commander: http://localhost:8081

### Production Setup

1. **Build production images:**
   ```bash
   make build-prod
   ```

2. **Start production environment:**
   ```bash
   make prod
   ```

3. **Configure nginx SSL (optional):**
   - Place SSL certificates in `nginx/ssl/`
   - Update `nginx/nginx.conf` with your domain
   - Uncomment HTTPS server block

## File Structure

```
docker/
├── docker-entrypoint.sh   # Container initialization script
├── healthcheck.py         # Health check script for containers
├── Makefile              # Docker operation commands
├── validate_docker.sh    # Configuration validation script
└── README.md            # This file

../
├── Dockerfile           # Production multi-stage build
├── Dockerfile.dev       # Development build
├── docker-compose.yml   # Base service definitions
├── docker-compose.dev.yml   # Development overrides
├── docker-compose.prod.yml  # Production overrides
├── .dockerignore        # Files to exclude from build
└── nginx/
    └── nginx.conf       # Nginx reverse proxy configuration
```

## Available Commands

Run these commands from the `docker/` directory:

### Basic Operations
```bash
make help          # Show all available commands
make dev           # Start development environment
make prod          # Start production environment
make down          # Stop all containers
make restart       # Restart all containers
make status        # Show container status
```

### Building
```bash
make build         # Build all images (no cache)
make build-quick   # Build with cache
make build-prod    # Build production images
```

### Logging & Monitoring
```bash
make logs          # Show all logs
make logs-queen    # Show Queen logs
make logs-frontend # Show Frontend logs
make logs-backend  # Show Backend logs
make logs-infra    # Show Infra logs
make health        # Check service health
make monitor       # Open monitoring dashboards
```

### Shell Access
```bash
make shell-queen    # Shell into Queen container
make shell-frontend # Shell into Frontend container
make shell-backend  # Shell into Backend container
make shell-infra    # Shell into Infra container
```

### Database Operations
```bash
make db-backup     # Backup database
make db-restore    # Restore from backup
```

### Cleanup
```bash
make clean         # Remove containers and volumes
make clean-images  # Remove all project images
make prune         # Prune Docker system
```

### Testing & Validation
```bash
make test          # Run tests in containers
make validate      # Validate Docker configuration
```

## Environment Variables

Key environment variables (set in `.env`):

```bash
# Environment
HIVE_ENV=development|production
HIVE_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR

# Database
POSTGRES_USER=hive
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=hive_db

# GitHub (for PR operations)
GITHUB_TOKEN=<your-github-token>

# Versions
VERSION=latest
```

## Service Configuration

### Resource Limits

Production resource limits per service:

| Service | CPU | Memory | Storage |
|---------|-----|--------|---------|
| Queen | 2.0 cores | 2GB | 10GB |
| Frontend Worker | 1.0 core | 1GB | 5GB |
| Backend Worker | 1.0 core | 1GB | 5GB |
| Infra Worker | 1.0 core | 1GB | 5GB |
| PostgreSQL | 1.0 core | 1GB | 20GB |
| Redis | 0.5 core | 512MB | 5GB |

### Network Configuration

All services communicate on a custom bridge network `hive-network` with subnet `172.20.0.0/16`.

### Port Mapping

| Service | Internal | External | Description |
|---------|----------|----------|-------------|
| Frontend | 3000 | 3000 | React dev server |
| Queen API | 5000 | 5000 | Orchestrator API |
| Backend API | 8000 | 8000 | FastAPI/Flask |
| PostgreSQL | 5432 | 5432 | Database |
| Redis | 6379 | 6379 | Message bus |
| Adminer | 8080 | 8082 | Database UI |
| Redis Commander | 8081 | 8081 | Redis UI |
| Infra Metrics | 9000 | 9000 | Monitoring |
| Nginx | 80/443 | 80/443 | Reverse proxy |

## Health Checks

Each container includes health checks that monitor:

- File system accessibility
- Network connectivity to dependencies
- Process status
- Recent activity (log updates)
- Memory usage

Health check results are written to `/app/logs/health.json` in each container.

## Security Considerations

1. **Secrets Management:**
   - Never commit `.env` files
   - Use Docker secrets in production
   - Rotate credentials regularly

2. **Network Security:**
   - Services isolated on custom network
   - Nginx provides single entry point
   - Rate limiting configured

3. **Container Security:**
   - Non-root user execution
   - Read-only root filesystem (production)
   - Minimal base images

4. **Access Control:**
   - Implement authentication on Queen API
   - Restrict database access
   - Use HTTPS in production

## Troubleshooting

### Common Issues

1. **Port conflicts:**
   ```bash
   # Check port usage
   lsof -i :3000
   # Or change port in docker-compose.yml
   ```

2. **Permission errors:**
   ```bash
   # Fix ownership
   sudo chown -R $(id -u):$(id -g) .
   ```

3. **Build failures:**
   ```bash
   # Clean and rebuild
   make clean
   make build
   ```

4. **Container crashes:**
   ```bash
   # Check logs
   make logs-<service>
   # Check health
   make health
   ```

5. **Network issues:**
   ```bash
   # Recreate network
   docker network rm hive-network
   docker network create hive-network
   ```

### Validation

Run the validation script to check your setup:

```bash
./validate_docker.sh
```

This checks:
- Docker installation
- Required files
- Configuration syntax
- Environment variables
- Port availability
- Resource usage
- Network setup
- Security settings

## Development Workflow

1. **Start development environment:**
   ```bash
   make dev
   ```

2. **Make code changes** - volumes are mounted for hot-reload

3. **View logs in real-time:**
   ```bash
   make dev-logs
   ```

4. **Run tests:**
   ```bash
   make test
   ```

5. **Stop when done:**
   ```bash
   make dev-down
   ```

## Production Deployment

1. **Validate configuration:**
   ```bash
   make validate
   ```

2. **Build production images:**
   ```bash
   make build-prod
   ```

3. **Tag and push images:**
   ```bash
   docker tag hive/queen:latest your-registry/hive/queen:v1.0.0
   docker push your-registry/hive/queen:v1.0.0
   ```

4. **Deploy with production config:**
   ```bash
   make prod
   ```

5. **Monitor health:**
   ```bash
   make health
   make monitor
   ```

## Backup and Recovery

### Backup

```bash
# Automated backup
make db-backup

# Manual backup with timestamp
docker-compose exec -T database pg_dump -U hive hive_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore

```bash
# Interactive restore
make db-restore

# Direct restore
docker-compose exec -T database psql -U hive hive_db < backup.sql
```

## Performance Tuning

### Docker Settings

1. **Increase Docker resources** (Docker Desktop):
   - CPUs: 4+
   - Memory: 8GB+
   - Swap: 2GB+
   - Disk: 50GB+

2. **Enable BuildKit:**
   ```bash
   export DOCKER_BUILDKIT=1
   ```

3. **Use volume caching (macOS):**
   ```yaml
   volumes:
     - ./:/app:cached
   ```

### Service Optimization

1. **Database:**
   - Tune PostgreSQL configuration
   - Add indexes for common queries
   - Regular VACUUM and ANALYZE

2. **Redis:**
   - Configure maxmemory policy
   - Enable persistence if needed
   - Monitor memory usage

3. **Application:**
   - Use production builds
   - Enable caching
   - Optimize database queries

## Contributing

When adding new services or modifying configuration:

1. Update all docker-compose files
2. Add health checks
3. Document changes in this README
4. Test with validation script
5. Update Makefile targets if needed

## Support

For issues or questions:

1. Check troubleshooting section
2. Run validation script
3. Review container logs
4. Check health status
5. Open an issue with diagnostic info

## License

[Your License Here]

---

Built with ❤️ by the Hive Fleet Command Team
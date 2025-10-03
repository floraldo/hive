# Hive Platform Architecture

## Overview

Hive is a multi-language, microservices-based platform for energy system optimization, AI-powered planning, and intelligent code review. The platform is designed for scale, supporting Python, Node.js, Rust, Julia, and Go.

## Architecture Philosophy

### Hybrid Environment Management

**Conda**: Ecosystem-level package manager
- Manages multiple language runtimes (Python, Node.js, Rust, Julia, Go)
- Provides system-level dependencies
- Creates isolated development environment

**Poetry**: Python-specific dependency manager
- Manages Python package dependencies
- Creates Python virtual environments within conda
- Provides reproducible builds with lockfiles

**Why Hybrid?**
- Multi-language platform requires ecosystem manager (Conda)
- Python packages need precise dependency resolution (Poetry)
- Clean separation: Conda handles runtimes, Poetry handles Python deps
- Docker-ready: Both tools work seamlessly in containers

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                        │
│                                                              │
│  Apps (Business Logic):                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ EcoSystemiser│  │ AI Planner   │  │ AI Reviewer  │     │
│  │ (Python)     │  │ (Python)     │  │ (Python)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Hive Orch.   │  │ Guardian     │  │ Notifications│     │
│  │ (Python)     │  │ (Python)     │  │ (Python)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                      │
│                                                              │
│  Packages (Shared Libraries):                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ hive-logging │  │ hive-config  │  │ hive-db      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ hive-bus     │  │ hive-cache   │  │ hive-async   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PLATFORM SERVICES                         │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ PostgreSQL   │  │ Redis        │  │ RabbitMQ     │     │
│  │ (Database)   │  │ (Cache)      │  │ (Message Bus)│     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐                                           │
│  │ MinIO (S3)   │                                           │
│  │ (Object Store)│                                          │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

## Multi-Language Technology Stack

### Python (Primary Language)
**Use Cases**: Core business logic, AI integration, data processing
**Tools**:
- Poetry 2.2.0 for dependency management
- pytest for testing
- FastAPI/Flask for web services
- pydantic for data validation

**Key Packages**:
- `packages/hive-*` - 18 shared infrastructure packages
- `apps/*` - 7 business logic applications

### Node.js (Frontend & Tooling)
**Use Cases**: React/Vue frontends, build tooling, CLI utilities
**Tools**:
- npm/yarn for package management
- TypeScript for type safety
- Jest for testing
- ESLint/Prettier for code quality

**Configuration**: `package.json` (workspace setup)

### Rust (Performance-Critical Services)
**Use Cases**: High-performance optimization, data processing pipelines
**Tools**:
- Cargo for package management
- cargo-test for testing
- cargo-clippy for linting

**Configuration**: `Cargo.toml` (workspace setup)

### Julia (Scientific Computing)
**Use Cases**: Advanced optimization algorithms, numerical analysis
**Tools**:
- Pkg for package management
- Julia REPL for interactive development

### Go (Microservices & CLI)
**Use Cases**: Lightweight microservices, command-line tools
**Tools**:
- go mod for dependency management
- go test for testing

## Environment Setup

### Development Environment

```bash
# 1. Create conda environment
conda env create -f environment.yml
conda activate hive

# 2. Install Python packages
poetry install --with dev

# 3. Install Node.js packages (if frontend development)
npm install

# 4. Verify installation
bash scripts/validation/validate_environment.sh
```

### Environment Layers

```
┌─────────────────────────────────────────┐
│  Conda Environment (hive)                │
│  - Python 3.11.13                        │
│  - Node.js 20.11.1                       │
│  - Rust 1.76.0                           │
│  - Julia 1.10.0                          │
│  - Go 1.22.0                             │
│  - System tools (git, docker, etc.)      │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Poetry Virtual Environment              │
│  - hive-workspace-{hash}-py3.11          │
│  - All Python packages in develop mode   │
│  - Isolated from system Python           │
│  - Uses conda Python as base             │
└─────────────────────────────────────────┘
```

## Data Flow Architecture

### Synchronous Request Flow
```
User/Client
    │
    ├─> HTTP Request
    │
    ▼
┌─────────────────┐
│ FastAPI Service │
│ (Python)        │
└─────────────────┘
    │
    ├─> Validation (pydantic)
    ├─> Business Logic
    ├─> Database Query (PostgreSQL)
    ├─> Cache Check (Redis)
    │
    ▼
HTTP Response
```

### Asynchronous Event Flow
```
Service A                  RabbitMQ                Service B
    │                         │                         │
    ├─> Publish Event ───────>│                         │
    │                         │                         │
    │                         ├─> Route Event ─────────>│
    │                         │                         │
    │                         │                    Process Event
    │                         │                         │
    │                         │<─── Acknowledge ────────┤
```

## Dependency Management

### Import Rules (Golden Rules)

**✅ ALLOWED**:
```python
# Package imports (infrastructure)
from hive_logging import get_logger
from hive_config import create_config_from_sources
from hive_db import get_sqlite_connection

# Same app imports
from ecosystemiser.services.solver import optimize
from ecosystemiser.core.bus import EventBus

# App.core extensions (inherit→extend pattern)
from hive_bus import BaseBus
class MyAppEventBus(BaseBus):
    pass
```

**❌ FORBIDDEN**:
```python
# Cross-app business logic imports
from ecosystemiser.services.solver import optimize  # From ai-planner
from ai_reviewer.core.cost import CostTracker  # From ecosystemiser
```

**Communication Between Apps**:
- Use `hive-bus` for event-driven communication
- Use `hive-orchestration` for task coordination
- Extract shared logic to `packages/` if needed

## Docker & Kubernetes Deployment

### Multi-Stage Docker Builds

```dockerfile
# Stage 1: Python builder
FROM python:3.11-slim AS python-builder
RUN pip install poetry==2.2.0
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev

# Stage 2: Node.js builder
FROM node:20-slim AS node-builder
COPY package.json package-lock.json ./
RUN npm ci --only=production
RUN npm run build

# Stage 3: Rust builder
FROM rust:1.76-slim AS rust-builder
COPY Cargo.toml Cargo.lock ./
RUN cargo build --release

# Stage 4: Runtime
FROM python:3.11-slim
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=node-builder /build/dist /app/static
COPY --from=rust-builder /build/target/release/optimizer /usr/local/bin/
```

### Platform Docker Compose

```bash
# Start entire platform
docker-compose -f docker-compose.platform.yml up

# Services:
# - postgres (Database)
# - redis (Cache)
# - rabbitmq (Message Bus)
# - minio (Object Storage)
# - hive-orchestrator (Coordination)
# - ecosystemiser (Energy Optimization)
# - ai-planner (Planning)
# - ai-reviewer (Code Review)
# - guardian-agent (System Guardian)
# - notification-service (Notifications)
```

### Kubernetes Deployment

```bash
# Example k8s structure (see apps/guardian-agent/k8s/ for reference)
apps/{service}/k8s/
├── deployment.yaml    # Service deployment
├── service.yaml       # Load balancer
├── configmap.yaml     # Configuration
├── secrets.yaml       # Sensitive data
├── hpa.yaml          # Auto-scaling
└── pvc.yaml          # Persistent storage
```

## Configuration Management

### Dependency Injection Pattern (Gold Standard)

```python
# ✅ CORRECT: DI Pattern
from hive_config import HiveConfig, create_config_from_sources

class MyService:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()
        self.db_path = self._config.database.path

# ❌ DEPRECATED: Global State
from hive_config import get_config

class MyService:
    def __init__(self):
        self.config = get_config()  # Hidden dependency!
```

**Benefits**:
- ✅ Explicit dependencies
- ✅ Testable (inject mock configs)
- ✅ Thread-safe (no global state)
- ✅ Parallel-friendly (each instance isolated)

## Golden Rules (Environment Isolation)

### Rule 25: No Conda in Production Code
**Severity**: CRITICAL
**Rationale**: Conda is a development tool, not a runtime dependency

```python
# ❌ WRONG
import os
if os.environ.get("CONDA_DEFAULT_ENV") == "hive":
    ...

# ✅ RIGHT
# Production code should be environment-agnostic
```

### Rule 26: No Hardcoded Paths
**Severity**: ERROR
**Rationale**: Breaks portability and Docker deployment

```python
# ❌ WRONG
DB_PATH = "C:/git/hive/data/database.db"

# ✅ RIGHT
DB_PATH = os.getenv("DATABASE_PATH", "/app/data/database.db")
```

### Rule 27: Consistent Python Version
**Severity**: ERROR
**Rationale**: Prevents dependency conflicts

```toml
# All pyproject.toml files must specify:
[tool.poetry.dependencies]
python = "^3.11"
```

### Rule 28: Poetry Lockfile
**Severity**: WARNING
**Rationale**: Ensures reproducible builds

```bash
# Generate lockfile
poetry lock

# Keep lockfile up-to-date
poetry lock --no-update
```

### Rule 29: Multi-Language Toolchain
**Severity**: INFO
**Rationale**: Platform supports multiple languages

```bash
# Required tools:
python --version  # >= 3.11
node --version    # >= 20.0
cargo --version   # >= 1.70
julia --version   # >= 1.9
go version        # >= 1.21
```

### Rule 30: Environment Variables
**Severity**: WARNING
**Rationale**: 12-factor app compatibility

```python
# ✅ RIGHT: Use environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app/data/hive.db")
API_KEY = os.getenv("API_KEY")  # No default for secrets

# ❌ WRONG: Hardcoded config
DATABASE_URL = "sqlite:///C:/git/hive/data/hive.db"
API_KEY = "sk-1234567890abcdef"
```

## Quality Assurance

### Pre-Commit Validation

```bash
# Syntax validation
python -m py_compile modified_file.py

# Test collection
python -m pytest --collect-only

# Linting
python -m ruff check .

# Golden rules
python scripts/validation/validate_golden_rules.py --level ERROR

# Type checking
python -m mypy modified_file.py
```

### Tiered Compliance

```bash
# Development (fast iteration)
validate_golden_rules.py --level CRITICAL  # ~5s

# Pull Request (quality gate)
validate_golden_rules.py --level ERROR     # ~15s

# Sprint Cleanup (comprehensive)
validate_golden_rules.py --level WARNING   # ~25s

# Production Release (complete)
validate_golden_rules.py --level INFO      # ~30s
```

## Performance & Scalability

### Horizontal Scaling
- **Stateless Services**: All app services are stateless, can scale horizontally
- **Load Balancing**: Kubernetes HPA for auto-scaling
- **Caching**: Redis for distributed caching
- **Message Queue**: RabbitMQ for async processing

### Language-Specific Optimization
- **Python**: AsyncIO for I/O-bound tasks, multiprocessing for CPU-bound
- **Node.js**: Event loop for high concurrency
- **Rust**: Zero-cost abstractions, native performance
- **Julia**: JIT compilation, parallel computing
- **Go**: Goroutines for lightweight concurrency

## Security

### Secrets Management
- **Development**: `.env` files (gitignored)
- **Production**: Kubernetes secrets, HashiCorp Vault
- **Never**: Hardcode secrets in code

### Network Security
- **Internal**: Services communicate via private network
- **External**: TLS/SSL for all external communication
- **API**: JWT authentication, rate limiting

## Monitoring & Observability

### Logging
- **Structured Logging**: `hive-logging` package
- **Centralized**: All logs to stdout/stderr
- **Log Aggregation**: (Future: ELK stack or Loki)

### Metrics
- **Performance**: `hive-performance` package
- **Metrics Export**: (Future: Prometheus)
- **Dashboards**: (Future: Grafana)

### Tracing
- **Distributed Tracing**: (Future: Jaeger/Zipkin)
- **Request ID**: Track requests across services

## Future Roadmap

### Phase 1 (Current)
- ✅ Multi-language environment (Python, Node.js, Rust, Julia, Go)
- ✅ Docker & Kubernetes infrastructure
- ✅ Golden rules for environment isolation
- ✅ Comprehensive documentation

### Phase 2 (Next)
- 🔄 Frontend applications (React/Vue dashboards)
- 🔄 Rust performance services
- 🔄 Julia optimization modules
- 🔄 Go CLI tools and microservices

### Phase 3 (Future)
- ⏳ Monitoring & observability stack
- ⏳ CI/CD pipeline enhancements
- ⏳ Multi-region deployment
- ⏳ Advanced security features

## Resources

- **Setup Guide**: `scripts/setup/setup_hive_environment.sh`
- **Validation**: `scripts/validation/validate_environment.sh`
- **Docker**: `Dockerfile.multiservice`, `docker-compose.platform.yml`
- **Configuration**: `environment.yml`, `poetry.toml`, `package.json`, `Cargo.toml`
- **Documentation**: `.claude/CLAUDE.md`, `README.md`

---

**Last Updated**: 2025-10-03
**Architecture Version**: 2.0 (Multi-Language Hybrid)

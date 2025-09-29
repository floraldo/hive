# Multi-stage build for Guardian Agent
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Install poetry and dependencies
RUN pip install --no-cache-dir poetry==1.7.1 && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Production stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 guardian && \
    mkdir -p /app/data /app/logs /app/cache && \
    chown -R guardian:guardian /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=guardian:guardian src/ ./src/
COPY --chown=guardian:guardian config/ ./config/

# Copy hive packages (in production, these would be installed from a package registry)
COPY --chown=guardian:guardian ../../packages/hive-app-toolkit /packages/hive-app-toolkit
COPY --chown=guardian:guardian ../../packages/hive-ai /packages/hive-ai
COPY --chown=guardian:guardian ../../packages/hive-async /packages/hive-async
COPY --chown=guardian:guardian ../../packages/hive-db /packages/hive-db
COPY --chown=guardian:guardian ../../packages/hive-cache /packages/hive-cache
COPY --chown=guardian:guardian ../../packages/hive-logging /packages/hive-logging
COPY --chown=guardian:guardian ../../packages/hive-config /packages/hive-config
COPY --chown=guardian:guardian ../../packages/hive-errors /packages/hive-errors
COPY --chown=guardian:guardian ../../packages/hive-tests /packages/hive-tests
COPY --chown=guardian:guardian ../../packages/hive-performance /packages/hive-performance

# Set Python path
ENV PYTHONPATH=/app/src:/packages/hive-app-toolkit/src:/packages/hive-ai/src:/packages/hive-async/src:/packages/hive-db/src:/packages/hive-cache/src:/packages/hive-logging/src:/packages/hive-config/src:/packages/hive-errors/src:/packages/hive-tests/src:/packages/hive-performance/src

# Environment variables
ENV GUARDIAN_ENV=production \
    LOG_LEVEL=INFO \
    WORKERS=4 \
    PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Switch to non-root user
USER guardian

# Expose port
EXPOSE 8000

# Run the application (hive-app-toolkit handles uvicorn configuration)
CMD ["python", "-m", "guardian_agent.api"]

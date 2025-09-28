# Multi-stage Dockerfile for EcoSystemiser v3.0
# Optimized for production deployment with all services

# Stage 1: Builder
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files first (better caching)
COPY pyproject.toml poetry.lock* ./
COPY packages/ ./packages/

# Install poetry and dependencies
RUN pip install --no-cache-dir poetry==1.7.1 && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY apps/ecosystemiser/ ./apps/ecosystemiser/

# Stage 2: Runtime
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 ecosys && \
    mkdir -p /app/results /app/reports /app/logs /app/data && \
    chown -R ecosys:ecosys /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
WORKDIR /app
COPY --chown=ecosys:ecosys apps/ecosystemiser/ ./apps/ecosystemiser/
COPY --chown=ecosys:ecosys packages/ ./packages/

# Set Python path
ENV PYTHONPATH="/app/apps/ecosystemiser/src:/app/packages:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

# Environment variables for configuration
ENV ECOSYS_ENV=production
ENV ECOSYS_LOG_LEVEL=INFO
ENV ECOSYS_RESULTS_DIR=/app/results
ENV ECOSYS_REPORTS_DIR=/app/reports
ENV ECOSYS_DATA_DIR=/app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER ecosys

# Expose ports
# 8000: Main FastAPI application
# 5000: Flask reporting application
# 8501: Streamlit dashboard (if enabled)
EXPOSE 8000 5000 8501

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "uvicorn", "EcoSystemiser.main:app", "--host", "0.0.0.0", "--port", "8000"]
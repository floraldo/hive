#!/bin/bash
set -e

# Docker entrypoint script for Hive Fleet Command System
# This script initializes the container environment and starts the appropriate service

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Environment validation
validate_environment() {
    log_info "Validating environment configuration..."

    if [ -z "$HIVE_ROLE" ]; then
        log_error "HIVE_ROLE is not set!"
        exit 1
    fi

    log_info "Role: $HIVE_ROLE"
    log_info "Environment: ${HIVE_ENV:-development}"
    log_info "Log Level: ${HIVE_LOG_LEVEL:-INFO}"
}

# Create necessary directories
setup_directories() {
    log_info "Setting up directories..."

    mkdir -p /app/logs
    mkdir -p /app/hive/tasks
    mkdir -p /app/hive/messages
    mkdir -p /app/.worktrees

    # Ensure proper permissions
    if [ "$HIVE_ROLE" != "root" ]; then
        chown -R hive:hive /app/logs
        chown -R hive:hive /app/hive
    fi
}

# Initialize git configuration if needed
setup_git() {
    if [ -f /home/hive/.gitconfig ]; then
        log_info "Git configuration found"
    else
        log_warn "No git configuration found, setting defaults..."
        git config --global user.name "Hive Worker"
        git config --global user.email "hive@localhost"
        git config --global init.defaultBranch main
    fi
}

# Wait for dependent services
wait_for_services() {
    log_info "Checking service dependencies..."

    # Wait for message bus (Redis)
    if [ "$HIVE_ROLE" != "message-bus" ]; then
        log_info "Waiting for message bus..."
        for i in {1..30}; do
            if nc -z message-bus 6379 2>/dev/null; then
                log_info "Message bus is ready"
                break
            fi
            if [ $i -eq 30 ]; then
                log_warn "Message bus not available, continuing anyway..."
            fi
            sleep 1
        done
    fi

    # Wait for database (PostgreSQL)
    if [ "$HIVE_ROLE" != "database" ] && [ "$HIVE_ROLE" != "message-bus" ]; then
        log_info "Waiting for database..."
        for i in {1..30}; do
            if nc -z database 5432 2>/dev/null; then
                log_info "Database is ready"
                break
            fi
            if [ $i -eq 30 ]; then
                log_warn "Database not available, continuing anyway..."
            fi
            sleep 1
        done
    fi
}

# Run database migrations if needed
run_migrations() {
    if [ "$HIVE_ROLE" = "queen" ] && [ "$HIVE_ENV" = "production" ]; then
        log_info "Running database migrations..."
        # Add migration commands here when database schema is ready
        # python manage.py migrate || log_warn "Migrations failed or not configured"
    fi
}

# Main execution
main() {
    log_info "Starting Hive Fleet Command System..."
    log_info "Container initialization for role: $HIVE_ROLE"

    validate_environment
    setup_directories
    setup_git
    wait_for_services
    run_migrations

    log_info "Initialization complete, starting service..."

    # Execute the command passed to the container
    exec "$@"
}

# Run main function
main "$@"
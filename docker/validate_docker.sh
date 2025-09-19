#!/bin/bash

# Docker Configuration Validation Script for Hive Fleet Command
# This script validates Docker setup and configuration

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0
CHECKS=0

# Helper functions
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((ERRORS++))
    ((CHECKS++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
    ((CHECKS++))
}

section() {
    echo ""
    echo -e "${BLUE}═══ $1 ═══${NC}"
    echo ""
}

# Check Docker installation
check_docker_installation() {
    section "Docker Installation"

    if command -v docker &> /dev/null; then
        check_pass "Docker is installed"
        docker_version=$(docker --version)
        echo "    Version: $docker_version"
    else
        check_fail "Docker is not installed"
        return 1
    fi

    if command -v docker-compose &> /dev/null; then
        check_pass "Docker Compose is installed"
        compose_version=$(docker-compose --version)
        echo "    Version: $compose_version"
    else
        check_fail "Docker Compose is not installed"
        return 1
    fi

    # Check Docker daemon
    if docker info &> /dev/null; then
        check_pass "Docker daemon is running"
    else
        check_fail "Docker daemon is not running"
        echo "    Try: sudo systemctl start docker"
        return 1
    fi
}

# Check required files
check_required_files() {
    section "Required Files"

    required_files=(
        "../Dockerfile"
        "../Dockerfile.dev"
        "../docker-compose.yml"
        "../docker-compose.dev.yml"
        "../docker-compose.prod.yml"
        "../.dockerignore"
        "../nginx/nginx.conf"
        "docker-entrypoint.sh"
        "healthcheck.py"
        "Makefile"
    )

    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            check_pass "Found: $file"
        else
            check_fail "Missing: $file"
        fi
    done
}

# Check Docker Compose configuration
check_compose_config() {
    section "Docker Compose Configuration"

    # Validate compose files
    if docker-compose -f ../docker-compose.yml config &> /dev/null; then
        check_pass "docker-compose.yml is valid"
    else
        check_fail "docker-compose.yml has syntax errors"
        docker-compose -f ../docker-compose.yml config 2>&1 | head -10
    fi

    if docker-compose -f ../docker-compose.yml -f ../docker-compose.dev.yml config &> /dev/null; then
        check_pass "Development configuration is valid"
    else
        check_fail "Development configuration has errors"
    fi

    if docker-compose -f ../docker-compose.yml -f ../docker-compose.prod.yml config &> /dev/null; then
        check_pass "Production configuration is valid"
    else
        check_fail "Production configuration has errors"
    fi
}

# Check environment variables
check_environment() {
    section "Environment Variables"

    if [ -f "../.env" ]; then
        check_pass "Environment file exists (.env)"

        # Check for required variables
        required_vars=(
            "HIVE_ENV"
            "POSTGRES_USER"
            "POSTGRES_PASSWORD"
            "POSTGRES_DB"
        )

        source ../.env 2>/dev/null

        for var in "${required_vars[@]}"; do
            if [ ! -z "${!var}" ]; then
                check_pass "$var is set"
            else
                check_warn "$var is not set in .env"
            fi
        done
    else
        check_warn "No .env file found (using defaults)"
    fi
}

# Check port availability
check_ports() {
    section "Port Availability"

    ports=(
        "3000:Frontend"
        "5000:Queen API"
        "5432:PostgreSQL"
        "6379:Redis"
        "8000:Backend API"
        "8081:Redis Commander"
        "8082:Adminer"
        "9000:Metrics"
    )

    for port_desc in "${ports[@]}"; do
        port="${port_desc%%:*}"
        desc="${port_desc#*:}"

        if ! lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            check_pass "Port $port ($desc) is available"
        else
            check_warn "Port $port ($desc) is in use"
            echo "    Process using port: $(lsof -Pi :$port -sTCP:LISTEN 2>/dev/null | tail -1)"
        fi
    done
}

# Check Docker resources
check_resources() {
    section "Docker Resources"

    # Check disk space
    available_space=$(df -h . | awk 'NR==2 {print $4}')
    check_pass "Available disk space: $available_space"

    # Check Docker disk usage
    docker_usage=$(docker system df --format "table {{.Type}}\t{{.Size}}" 2>/dev/null | tail -n +2)
    if [ ! -z "$docker_usage" ]; then
        echo "Docker disk usage:"
        echo "$docker_usage" | while read line; do
            echo "    $line"
        done
    fi

    # Check for dangling images
    dangling_images=$(docker images -f "dangling=true" -q | wc -l)
    if [ "$dangling_images" -gt 0 ]; then
        check_warn "Found $dangling_images dangling images"
        echo "    Clean with: docker image prune"
    else
        check_pass "No dangling images"
    fi

    # Check for stopped containers
    stopped_containers=$(docker ps -a -q -f status=exited | wc -l)
    if [ "$stopped_containers" -gt 0 ]; then
        check_warn "Found $stopped_containers stopped containers"
        echo "    Clean with: docker container prune"
    else
        check_pass "No stopped containers"
    fi
}

# Check network configuration
check_network() {
    section "Network Configuration"

    # Check if custom network exists
    if docker network inspect hive-network &> /dev/null; then
        check_pass "Custom network 'hive-network' exists"
    else
        check_warn "Custom network 'hive-network' not found"
        echo "    It will be created on first run"
    fi

    # Check Docker bridge network
    if docker network inspect bridge &> /dev/null; then
        check_pass "Docker bridge network is available"
    else
        check_fail "Docker bridge network not found"
    fi
}

# Check security settings
check_security() {
    section "Security Settings"

    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        check_warn "Running as root (not recommended for production)"
    else
        check_pass "Not running as root"
    fi

    # Check .env permissions
    if [ -f "../.env" ]; then
        perms=$(stat -c %a ../.env 2>/dev/null || stat -f %A ../.env 2>/dev/null)
        if [ "$perms" = "600" ] || [ "$perms" = "644" ]; then
            check_pass ".env has appropriate permissions ($perms)"
        else
            check_warn ".env permissions are $perms (recommend 600 or 644)"
        fi
    fi

    # Check for secrets in Docker images
    if [ -f "../Dockerfile" ]; then
        if grep -q "COPY.*\.env" ../Dockerfile; then
            check_fail "Dockerfile copies .env file (security risk)"
        else
            check_pass "Dockerfile doesn't copy sensitive files"
        fi
    fi
}

# Test build
test_build() {
    section "Build Test"

    read -p "Do you want to test building the images? This may take time. [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Testing Docker build..."
        if docker-compose -f ../docker-compose.yml build --no-cache queen &> /dev/null; then
            check_pass "Queen image builds successfully"
        else
            check_fail "Queen image build failed"
        fi
    else
        echo "Skipping build test"
    fi
}

# Main execution
main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Hive Fleet Docker Validation Script      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"

    check_docker_installation
    check_required_files
    check_compose_config
    check_environment
    check_ports
    check_resources
    check_network
    check_security
    test_build

    # Summary
    section "Validation Summary"

    echo -e "Total checks: $CHECKS"
    echo -e "${GREEN}Passed: $((CHECKS - ERRORS - WARNINGS))${NC}"
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
    echo -e "${RED}Errors: $ERRORS${NC}"

    if [ $ERRORS -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ Docker configuration is valid and ready!${NC}"
        echo ""
        echo "You can now run:"
        echo "  make dev    - Start development environment"
        echo "  make prod   - Start production environment"
        exit 0
    else
        echo ""
        echo -e "${RED}✗ Docker configuration has errors that need to be fixed${NC}"
        exit 1
    fi
}

# Run main function
main
#!/usr/bin/env bash
# Hive Platform Environment Validation
#
# Validates that the complete multi-language development environment is properly configured
#
# Usage:
#   bash scripts/validation/validate_environment.sh

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# ========================================
# Helper Functions
# ========================================

check_passed() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS_COUNT++))
}

check_failed() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL_COUNT++))
}

check_warning() {
    echo -e "${YELLOW}!${NC} $1"
    ((WARN_COUNT++))
}

check_version() {
    local tool=$1
    local min_version=$2
    local current_version=$3

    if [[ "$current_version" =~ ^v?([0-9]+)\.([0-9]+) ]]; then
        local major="${BASH_REMATCH[1]}"
        local minor="${BASH_REMATCH[2]}"

        if [[ "$min_version" =~ ^([0-9]+)\.([0-9]+) ]]; then
            local min_major="${BASH_REMATCH[1]}"
            local min_minor="${BASH_REMATCH[2]}"

            if [ "$major" -gt "$min_major" ] || \
               ([ "$major" -eq "$min_major" ] && [ "$minor" -ge "$min_minor" ]); then
                check_passed "$tool $current_version (>= $min_version required)"
                return 0
            else
                check_failed "$tool $current_version (>= $min_version required)"
                return 1
            fi
        fi
    fi

    check_warning "$tool version check inconclusive: $current_version"
    return 1
}

# ========================================
# Conda Environment Validation
# ========================================

echo -e "${BLUE}=== Conda Environment ===${NC}"

if command -v conda &> /dev/null; then
    check_passed "Conda is installed"

    if conda env list | grep -q "^hive "; then
        check_passed "Conda environment 'hive' exists"

        # Check if environment is active
        if [[ "${CONDA_DEFAULT_ENV:-}" == "hive" ]]; then
            check_passed "Conda environment 'hive' is active"
        else
            check_warning "Conda environment 'hive' is not active"
            echo "           Run: conda activate hive"
        fi
    else
        check_failed "Conda environment 'hive' does not exist"
        echo "           Run: conda env create -f environment.yml"
    fi
else
    check_failed "Conda is not installed"
fi

# ========================================
# Python Toolchain
# ========================================

echo -e "\n${BLUE}=== Python Toolchain ===${NC}"

if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    check_version "Python" "3.11" "$PYTHON_VERSION"
else
    check_failed "Python is not installed"
fi

if command -v poetry &> /dev/null; then
    POETRY_VERSION=$(poetry --version 2>&1 | awk '{print $3}' | tr -d '()')
    check_version "Poetry" "2.0" "$POETRY_VERSION"

    # Check Poetry configuration
    if poetry config virtualenvs.create | grep -q "true"; then
        check_passed "Poetry virtualenvs.create = true"
    else
        check_warning "Poetry virtualenvs.create != true"
    fi

    if poetry config virtualenvs.prefer-active-python | grep -q "true"; then
        check_passed "Poetry prefer-active-python = true"
    else
        check_warning "Poetry prefer-active-python != true"
    fi
else
    check_failed "Poetry is not installed"
fi

# Check if poetry.lock exists
if [ -f "poetry.lock" ]; then
    check_passed "poetry.lock exists"
else
    check_warning "poetry.lock does not exist"
fi

# ========================================
# Node.js Toolchain
# ========================================

echo -e "\n${BLUE}=== Node.js Toolchain ===${NC}"

if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    check_version "Node.js" "20.0" "$NODE_VERSION"
else
    check_warning "Node.js is not installed (optional)"
fi

if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    check_version "npm" "10.0" "$NPM_VERSION"
else
    check_warning "npm is not installed (optional)"
fi

# Check if node_modules exists
if [ -f "package.json" ]; then
    check_passed "package.json exists"

    if [ -d "node_modules" ]; then
        check_passed "node_modules directory exists"
    else
        check_warning "node_modules not installed. Run: npm install"
    fi
else
    check_warning "package.json does not exist (optional)"
fi

# ========================================
# Rust Toolchain
# ========================================

echo -e "\n${BLUE}=== Rust Toolchain ===${NC}"

if command -v cargo &> /dev/null; then
    CARGO_VERSION=$(cargo --version | awk '{print $2}')
    check_version "Rust/Cargo" "1.70" "$CARGO_VERSION"
else
    check_warning "Rust/Cargo is not installed (optional)"
fi

if [ -f "Cargo.toml" ]; then
    check_passed "Cargo.toml exists"
else
    check_warning "Cargo.toml does not exist (optional)"
fi

# ========================================
# Julia Toolchain
# ========================================

echo -e "\n${BLUE}=== Julia Toolchain ===${NC}"

if command -v julia &> /dev/null; then
    JULIA_VERSION=$(julia --version | awk '{print $3}')
    check_version "Julia" "1.9" "$JULIA_VERSION"
else
    check_warning "Julia is not installed (optional)"
fi

# ========================================
# Go Toolchain
# ========================================

echo -e "\n${BLUE}=== Go Toolchain ===${NC}"

if command -v go &> /dev/null; then
    GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
    check_version "Go" "1.21" "$GO_VERSION"
else
    check_warning "Go is not installed (optional)"
fi

# ========================================
# Docker & Kubernetes
# ========================================

echo -e "\n${BLUE}=== Container Tools ===${NC}"

if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
    check_passed "Docker $DOCKER_VERSION is installed"
else
    check_warning "Docker is not installed (optional for development)"
fi

if command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version | awk '{print $4}' | tr -d ',')
    check_passed "Docker Compose $COMPOSE_VERSION is installed"
else
    check_warning "Docker Compose is not installed (optional)"
fi

if command -v kubectl &> /dev/null; then
    KUBECTL_VERSION=$(kubectl version --client --short 2>&1 | grep -o 'v[0-9.]*' | head -1)
    check_passed "kubectl $KUBECTL_VERSION is installed"
else
    check_warning "kubectl is not installed (optional for deployment)"
fi

# ========================================
# Environment Variables
# ========================================

echo -e "\n${BLUE}=== Environment Variables ===${NC}"

# Check important environment variables
ENV_VARS=(
    "CONDA_DEFAULT_ENV"
    "POETRY_VIRTUALENVS_CREATE"
    "POETRY_VIRTUALENVS_IN_PROJECT"
)

for var in "${ENV_VARS[@]}"; do
    if [ -n "${!var:-}" ]; then
        check_passed "$var=${!var}"
    else
        check_warning "$var is not set"
    fi
done

# ========================================
# Summary
# ========================================

echo -e "\n${BLUE}=== Validation Summary ===${NC}"
echo -e "${GREEN}Passed:${NC}  $PASS_COUNT"
echo -e "${YELLOW}Warnings:${NC} $WARN_COUNT"
echo -e "${RED}Failed:${NC}  $FAIL_COUNT"

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "\n${GREEN}✓ Environment validation successful!${NC}"
    exit 0
else
    echo -e "\n${RED}✗ Environment validation failed with $FAIL_COUNT critical issues${NC}"
    exit 1
fi

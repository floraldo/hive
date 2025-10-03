#!/usr/bin/env bash
# Hive Platform Multi-Language Environment Setup
#
# This script sets up the complete Hive development environment with:
# - Conda environment (Python, Node.js, Rust, Julia, Go)
# - Poetry for Python package management
# - Node.js packages (npm/yarn)
# - Rust toolchain (cargo)
# - Julia packages
# - Go modules
#
# Usage:
#   bash scripts/setup/setup_hive_environment.sh
#
# Requirements:
#   - Conda/Miniconda installed
#   - Internet connection for package downloads

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# ========================================
# Helper Functions
# ========================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        log_success "$1 is installed"
        return 0
    else
        log_warning "$1 is not installed"
        return 1
    fi
}

# ========================================
# Pre-flight Checks
# ========================================

log_info "Starting Hive environment setup..."
log_info "Project root: $PROJECT_ROOT"

# Check for conda
if ! check_command conda; then
    log_error "Conda is not installed. Please install Miniconda or Anaconda first."
    log_info "Download from: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# ========================================
# Conda Environment Setup
# ========================================

log_info "Setting up conda environment..."

# Check if environment.yml exists
if [ ! -f "$PROJECT_ROOT/environment.yml" ]; then
    log_error "environment.yml not found at $PROJECT_ROOT"
    exit 1
fi

# Check if hive environment already exists
if conda env list | grep -q "^hive "; then
    log_warning "Conda environment 'hive' already exists"
    read -p "Do you want to recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Removing existing hive environment..."
        conda env remove -n hive -y
    else
        log_info "Using existing hive environment"
    fi
fi

# Create conda environment if it doesn't exist
if ! conda env list | grep -q "^hive "; then
    log_info "Creating conda environment from environment.yml..."
    conda env create -f "$PROJECT_ROOT/environment.yml"
    log_success "Conda environment 'hive' created"
else
    log_info "Updating existing conda environment..."
    conda env update -f "$PROJECT_ROOT/environment.yml" --prune
    log_success "Conda environment 'hive' updated"
fi

# ========================================
# Activate Conda Environment
# ========================================

log_info "Activating conda environment..."

# Source conda for this shell
eval "$(conda shell.bash hook)"
conda activate hive

log_success "Conda environment 'hive' activated"

# ========================================
# Verify Toolchain Installation
# ========================================

log_info "Verifying toolchain installation..."

# Python
if check_command python; then
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    log_info "Python version: $PYTHON_VERSION"
fi

# Node.js
if check_command node; then
    NODE_VERSION=$(node --version)
    log_info "Node.js version: $NODE_VERSION"
fi

# Rust
if check_command cargo; then
    CARGO_VERSION=$(cargo --version | awk '{print $2}')
    log_info "Rust/Cargo version: $CARGO_VERSION"
fi

# Julia
if check_command julia; then
    JULIA_VERSION=$(julia --version | awk '{print $3}')
    log_info "Julia version: $JULIA_VERSION"
fi

# Go
if check_command go; then
    GO_VERSION=$(go version | awk '{print $3}')
    log_info "Go version: $GO_VERSION"
fi

# ========================================
# Poetry Setup
# ========================================

log_info "Setting up Poetry for Python package management..."

# Verify Poetry installation
if ! check_command poetry; then
    log_error "Poetry not installed. Installing via pip..."
    pip install poetry==2.2.0
fi

POETRY_VERSION=$(poetry --version | awk '{print $3}' | tr -d '()')
log_info "Poetry version: $POETRY_VERSION"

# Configure Poetry
log_info "Configuring Poetry..."
poetry config virtualenvs.create true
poetry config virtualenvs.in-project false
poetry config virtualenvs.prefer-active-python true
poetry config installer.parallel true

log_success "Poetry configured"

# ========================================
# Python Package Installation
# ========================================

log_info "Installing Python packages with Poetry..."

cd "$PROJECT_ROOT"

# Check if pyproject.toml exists
if [ ! -f "pyproject.toml" ]; then
    log_error "pyproject.toml not found at $PROJECT_ROOT"
    exit 1
fi

# Install Python dependencies
log_info "Running: poetry install --with dev"
poetry install --with dev

log_success "Python packages installed"

# ========================================
# Node.js Package Installation
# ========================================

if [ -f "$PROJECT_ROOT/package.json" ]; then
    log_info "Installing Node.js packages..."

    # Use npm (installed via conda)
    npm install

    log_success "Node.js packages installed"
else
    log_warning "package.json not found, skipping Node.js setup"
fi

# ========================================
# Rust Project Setup
# ========================================

if [ -f "$PROJECT_ROOT/Cargo.toml" ]; then
    log_info "Setting up Rust workspace..."

    # Create services/rust directory if it doesn't exist
    mkdir -p "$PROJECT_ROOT/services/rust"

    log_info "Rust workspace configured"
    log_info "To add Rust services, create crates in services/rust/"
else
    log_warning "Cargo.toml not found, skipping Rust setup"
fi

# ========================================
# Julia Package Setup
# ========================================

if command -v julia &> /dev/null; then
    log_info "Julia is available for package installation"
    log_info "To install Julia packages, create a Project.toml and run: julia> using Pkg; Pkg.instantiate()"
fi

# ========================================
# Environment Validation
# ========================================

log_info "Validating environment setup..."

# Run golden rules validation if available
if [ -f "$PROJECT_ROOT/scripts/validation/validate_golden_rules.py" ]; then
    log_info "Running golden rules validation..."
    python "$PROJECT_ROOT/scripts/validation/validate_golden_rules.py" --level CRITICAL || {
        log_warning "Some validation checks failed (this is normal during setup)"
    }
fi

# ========================================
# Post-Installation Instructions
# ========================================

log_success "Hive environment setup complete!"
echo
log_info "Next steps:"
echo "  1. Activate the environment: conda activate hive"
echo "  2. Verify installation: python --version && node --version"
echo "  3. Run tests: poetry run pytest"
echo "  4. Start development: poetry shell"
echo
log_info "Available commands:"
echo "  - poetry run pytest          # Run Python tests"
echo "  - npm run dev                # Start development servers"
echo "  - npm run build              # Build all projects"
echo "  - cargo test --workspace     # Run Rust tests"
echo
log_info "For more information, see: $PROJECT_ROOT/README.md"

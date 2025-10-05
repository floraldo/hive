#!/bin/bash
# QA Agent Startup Script
# Launches CC terminal with QA agent daemon running in background

set -e  # Exit on error

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

echo "==================================="
echo "QA Agent - Hybrid Autonomous Quality Enforcement"
echo "==================================="
echo ""
echo "App Directory: $APP_DIR"
echo ""

# Check if poetry is available
if ! command -v poetry &> /dev/null; then
    echo "Error: Poetry not found. Please install Poetry first:"
    echo "  curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

# Check if dependencies are installed
cd "$APP_DIR"
if [ ! -d ".venv" ]; then
    echo "Installing dependencies..."
    poetry install
fi

# Activate virtual environment
source "$(poetry env info --path)/bin/activate" 2>/dev/null || \
source "$(poetry env info --path)/Scripts/activate" 2>/dev/null || \
echo "Warning: Could not activate virtual environment"

# Configuration
export QA_AGENT_POLL_INTERVAL="${QA_AGENT_POLL_INTERVAL:-5.0}"
export QA_AGENT_MAX_CHIMERA="${QA_AGENT_MAX_CHIMERA:-3}"
export QA_AGENT_MAX_CC_WORKERS="${QA_AGENT_MAX_CC_WORKERS:-2}"

echo "Configuration:"
echo "  Poll Interval: $QA_AGENT_POLL_INTERVAL seconds"
echo "  Max Chimera Agents: $QA_AGENT_MAX_CHIMERA"
echo "  Max CC Workers: $QA_AGENT_MAX_CC_WORKERS"
echo ""

# Check hive-orchestrator database
ORCHESTRATOR_DB="${HIVE_DB_PATH:-../../packages/hive-orchestration/data/orchestrator.db}"
if [ ! -f "$ORCHESTRATOR_DB" ]; then
    echo "Warning: hive-orchestrator database not found at: $ORCHESTRATOR_DB"
    echo "  Tasks will fail until orchestrator database is initialized"
    echo ""
fi

# Check RAG index
RAG_INDEX_PATH="${RAG_INDEX_PATH:-../../data/rag_index}"
if [ ! -d "$RAG_INDEX_PATH" ]; then
    echo "Warning: RAG index not found at: $RAG_INDEX_PATH"
    echo "  Pattern retrieval will be limited"
    echo ""
fi

# Start daemon
echo "Starting QA Agent daemon..."
echo "Press Ctrl+C to stop"
echo "==================================="
echo ""

# Run daemon via Poetry
poetry run qa-agent start \
    --poll-interval "$QA_AGENT_POLL_INTERVAL" \
    --max-chimera "$QA_AGENT_MAX_CHIMERA" \
    --max-cc-workers "$QA_AGENT_MAX_CC_WORKERS"

# Cleanup on exit
echo ""
echo "==================================="
echo "QA Agent daemon stopped"
echo "==================================="

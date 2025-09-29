#!/bin/bash
# Run tests for a specific component in the Docker container
# Usage: ./scripts/quick-test.sh [component] [pytest-args]

set -e

COMPONENT=${1:-"."}
shift  # Remove first argument to pass rest to pytest

echo "🧪 ============================================"
echo "🧪   Running Hive Tests"
echo "🧪 ============================================"
echo ""
echo "📍 Testing: $COMPONENT"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Navigate to project root
cd "$(dirname "$0")/.."

# Check if image exists, build if not
if ! docker images | grep -q "hive-dev"; then
    echo "🔨 Building development image first..."
    docker-compose -f docker-compose.dev.yml build
fi

# Run tests in container
docker-compose -f docker-compose.dev.yml run --rm hive-dev \
    poetry run pytest $COMPONENT -v "$@"

echo ""
echo "✅ Test run complete!"

#!/bin/bash
# Start a development session in Docker container
# This gives you a perfect, isolated development environment

set -e

echo "🐝 ============================================"
echo "🐝   Starting Hive Development Environment"
echo "🐝 ============================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Parse arguments
REBUILD=false
PULL=false

for arg in "$@"; do
    case $arg in
        --rebuild)
            REBUILD=true
            shift
            ;;
        --pull)
            PULL=true
            shift
            ;;
        --help)
            echo "Usage: ./scripts/dev-session.sh [options]"
            echo ""
            echo "Options:"
            echo "  --rebuild    Force rebuild of the Docker image"
            echo "  --pull       Pull latest base images before building"
            echo "  --help       Show this help message"
            echo ""
            exit 0
            ;;
    esac
done

# Navigate to project root
cd "$(dirname "$0")/.."

# Pull latest images if requested
if [ "$PULL" = true ]; then
    echo "📥 Pulling latest base images..."
    docker-compose -f docker-compose.dev.yml pull
fi

# Build the development image
if [ "$REBUILD" = true ]; then
    echo "🔨 Forcing rebuild of development image..."
    docker-compose -f docker-compose.dev.yml build --no-cache
else
    echo "🔨 Building development image (using cache if available)..."
    docker-compose -f docker-compose.dev.yml build
fi

echo ""
echo "🚀 Starting interactive development session..."
echo ""

# Start the container and attach to it
docker-compose -f docker-compose.dev.yml run --rm hive-dev

echo ""
echo "👋 Hive development session ended"
echo ""
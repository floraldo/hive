#!/bin/bash
# Simple script to start CC MAS workers

echo "Starting CC MAS Workers..."
echo "=========================="
echo ""
echo "To start a worker in background terminal:"
echo "  python cc_worker.py backend 10    # Backend worker, 10 second cycles"
echo "  python cc_worker.py frontend 10   # Frontend worker"
echo "  python cc_worker.py infra 10      # Infrastructure worker"
echo ""
echo "Workers will:"
echo "  - Run continuously (Ctrl+C to stop)"
echo "  - Check for tasks every N seconds"
echo "  - Execute with real Claude CLI"
echo "  - Show status in terminal"
echo ""
echo "To create test tasks:"
echo "  python create_test_tasks.py"
echo ""
echo "To reset failed tasks:"
echo "  python reset_tasks.py"

# Start workers if requested
if [ "$1" == "all" ]; then
    echo ""
    echo "Starting all workers..."
    python cc_worker.py backend 10 &
    python cc_worker.py frontend 10 &
    python cc_worker.py infra 10 &
    echo "Workers started in background!"
fi
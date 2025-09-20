#!/bin/bash

# AI Reviewer Startup Script
# Starts the autonomous AI code review agent as a daemon

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$SCRIPT_DIR"
LOG_DIR="$APP_DIR/logs"
PID_FILE="$LOG_DIR/ai-reviewer.pid"
LOG_FILE="$LOG_DIR/ai-reviewer.log"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to check if agent is running
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            # PID file exists but process is not running
            rm "$PID_FILE"
            return 1
        fi
    else
        return 1
    fi
}

# Function to start the agent
start_agent() {
    if check_running; then
        echo -e "${YELLOW}AI Reviewer is already running with PID $(cat $PID_FILE)${NC}"
        exit 1
    fi

    echo -e "${GREEN}Starting AI Reviewer Agent...${NC}"

    # Check for Poetry
    if ! command -v poetry &> /dev/null; then
        echo -e "${RED}Poetry is not installed. Please install Poetry first.${NC}"
        exit 1
    fi

    # Change to app directory
    cd "$APP_DIR"

    # Install dependencies if needed
    if [ ! -d ".venv" ]; then
        echo "Installing dependencies..."
        poetry install
    fi

    # Start the agent in background
    nohup poetry run python src/ai_reviewer/agent.py \
        >> "$LOG_FILE" 2>&1 &

    # Save PID
    echo $! > "$PID_FILE"

    # Wait a moment to check if it started successfully
    sleep 2

    if check_running; then
        echo -e "${GREEN}AI Reviewer started successfully with PID $(cat $PID_FILE)${NC}"
        echo "Logs: $LOG_FILE"
        echo "PID file: $PID_FILE"
    else
        echo -e "${RED}Failed to start AI Reviewer. Check logs at $LOG_FILE${NC}"
        exit 1
    fi
}

# Function to stop the agent
stop_agent() {
    if ! check_running; then
        echo -e "${YELLOW}AI Reviewer is not running${NC}"
        exit 0
    fi

    echo -e "${YELLOW}Stopping AI Reviewer Agent...${NC}"
    PID=$(cat "$PID_FILE")

    # Send SIGTERM for graceful shutdown
    kill -TERM "$PID"

    # Wait for process to stop (max 30 seconds)
    for i in {1..30}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            rm -f "$PID_FILE"
            echo -e "${GREEN}AI Reviewer stopped successfully${NC}"
            exit 0
        fi
        sleep 1
    done

    # Force kill if still running
    echo -e "${YELLOW}Force stopping AI Reviewer...${NC}"
    kill -9 "$PID" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo -e "${GREEN}AI Reviewer stopped${NC}"
}

# Function to restart the agent
restart_agent() {
    stop_agent
    sleep 2
    start_agent
}

# Function to show status
show_status() {
    if check_running; then
        PID=$(cat "$PID_FILE")
        echo -e "${GREEN}AI Reviewer is running with PID $PID${NC}"

        # Show recent log entries
        echo -e "\nRecent activity:"
        tail -5 "$LOG_FILE" 2>/dev/null || echo "No log entries yet"

        # Show process info
        echo -e "\nProcess info:"
        ps -fp "$PID"
    else
        echo -e "${YELLOW}AI Reviewer is not running${NC}"
    fi
}

# Function to follow logs
follow_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}No log file found at $LOG_FILE${NC}"
        exit 1
    fi

    echo -e "${GREEN}Following AI Reviewer logs (Ctrl+C to stop)...${NC}"
    tail -f "$LOG_FILE"
}

# Function to run in test mode
run_test_mode() {
    echo -e "${GREEN}Running AI Reviewer in test mode...${NC}"
    cd "$APP_DIR"

    # Install dependencies if needed
    if [ ! -d ".venv" ]; then
        echo "Installing dependencies..."
        poetry install
    fi

    # Run in foreground with test mode
    poetry run python src/ai_reviewer/agent.py --test-mode
}

# Main script logic
case "${1:-}" in
    start)
        start_agent
        ;;
    stop)
        stop_agent
        ;;
    restart)
        restart_agent
        ;;
    status)
        show_status
        ;;
    logs)
        follow_logs
        ;;
    test)
        run_test_mode
        ;;
    *)
        echo "AI Reviewer Agent Control Script"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|test}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the AI Reviewer daemon"
        echo "  stop     - Stop the AI Reviewer daemon"
        echo "  restart  - Restart the AI Reviewer daemon"
        echo "  status   - Show current status"
        echo "  logs     - Follow the log file"
        echo "  test     - Run in test mode (foreground, short intervals)"
        echo ""
        echo "Configuration:"
        echo "  Log file: $LOG_FILE"
        echo "  PID file: $PID_FILE"
        exit 1
        ;;
esac
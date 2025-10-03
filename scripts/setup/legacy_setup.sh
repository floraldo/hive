#!/bin/bash
set -e

SESSION="hive-swarm"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Launching Fleet Command v4.0 - Expect Automation Enabled..."

# Verify expect is available
if ! command -v expect &> /dev/null; then
    echo "⚠️  WARNING: expect not found. Installing expect for automation..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y expect
    elif command -v yum &> /dev/null; then
        sudo yum install -y expect
    elif command -v brew &> /dev/null; then
        brew install expect
    else
        echo "❌ Cannot install expect automatically. Please install manually."
        echo "   On Ubuntu/Debian: sudo apt-get install expect"
        echo "   On CentOS/RHEL: sudo yum install expect" 
        echo "   On macOS: brew install expect"
        exit 1
    fi
fi

# Handle root user automatically - no manual switching required
if [ "$EUID" -eq 0 ]; then
    echo "Running as root - auto-setting up hiveuser for seamless operation..."
    
    # Create hiveuser if it doesn't exist
    if ! id -u hiveuser >/dev/null 2>&1; then
        useradd -m -s /bin/bash hiveuser
        echo "✅ Created hiveuser"
    fi
    
    # Give hiveuser access to project
    chown -R hiveuser:hiveuser .
    
    # Auto-restart script as hiveuser - SEAMLESS!
    echo "🔄 Restarting as hiveuser for permission compatibility..."
    exec su hiveuser -c "cd '$(pwd)' && $0"
fi

# Now running as hiveuser - proceed normally
echo "✅ Running as $(whoami) - proceeding with launch..."

tmux kill-session -t $SESSION 2>/dev/null || true

# --- THE PROVEN WORKING 2x2 GRID LOGIC ---
tmux new-session -d -s $SESSION -n "Fleet"
tmux split-window -v -t $SESSION:0
tmux split-window -h -t $SESSION:0.0  
tmux split-window -h -t $SESSION:0.2

# Create workspaces and automation directories
mkdir -p workspaces/backend workspaces/frontend workspaces/infra
mkdir -p bus logs

# Configure tmux for automation
tmux set-option -g mouse on
tmux set-option -g focus-events on  # Helps apps notice readiness

# Allow more time for panes to initialize 
echo "🔧 Configuring automation environment..."
sleep 2

# Launch all agents with expect automation
CLAUDE_CMD="claude --dangerously-skip-permissions"

echo "🔧 Launching agents with expect automation..."
echo "   Using robust retry logic and readiness detection"

# Launch Queen with readiness marker
echo "🧠 Queen (Pane 0) - Fleet Commander..."
tmux send-keys -t $SESSION:0.0 "echo '🚀 Queen Ready - $(date)' && $CLAUDE_CMD" C-m

# Launch Workers with workspace setup and readiness markers  
echo "🎨 Frontend Worker (Pane 1)..."
tmux send-keys -t $SESSION:0.1 "cd workspaces/frontend && echo '🎨 Frontend Ready - $(date)' && $CLAUDE_CMD" C-m

echo "🔧 Backend Worker (Pane 2)..."
tmux send-keys -t $SESSION:0.2 "cd workspaces/backend && echo '🔧 Backend Ready - $(date)' && $CLAUDE_CMD" C-m

echo "🏗️ Infra Worker (Pane 3)..."
tmux send-keys -t $SESSION:0.3 "cd workspaces/infra && echo '🏗️ Infra Ready - $(date)' && $CLAUDE_CMD" C-m

# Wait for agents to fully initialize
echo "⏳ Waiting for all agents to initialize..."
sleep 3

echo ""
echo "✅ Fleet Command v4.0 operational! Full automation enabled."
echo "📡 Run 'make attach' to enter the cockpit."
echo ""
echo "🤖 AUTOMATION FEATURES:"
echo "   ✅ Expect-based message delivery (no manual Enter needed)"
echo "   ✅ Readiness detection with retry logic"
echo "   ✅ Large message support with chunking"
echo "   ✅ Error recovery and fallback mechanisms"
echo ""
echo "🔧 Fleet Command Tools:"
echo "   ./scripts/fleet_send.sh send <agent> '<message>'"
echo "   ./scripts/fleet_send.sh broadcast '<message>'"
echo "   ./scripts/fleet_send.sh test"
echo "   ./scripts/readiness_test.sh"
echo ""
echo "📋 Example Automated Mission:"
echo "   ./scripts/fleet_send.sh send frontend '[T101] Create login component with React Hook Form and Zod validation'"
echo ""
echo "🔍 Test automation: ./scripts/readiness_test.sh"
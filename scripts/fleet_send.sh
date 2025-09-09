#!/bin/bash
#
# fleet_send.sh - Fleet Command message routing system
# Routes messages between Queen and Workers via tmux + expect
#

set -e

SESSION="hive-swarm"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPECT_SCRIPT="$SCRIPT_DIR/worker_expect.sh"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2" >&2
}

# Pane mapping
declare -A PANE_MAP=(
    ["queen"]="0.0"
    ["frontend"]="0.1" 
    ["backend"]="0.2"
    ["infra"]="0.3"
)

# Validate pane exists and is running
validate_pane() {
    local target="$1"
    
    if ! tmux list-panes -t "$SESSION" -F "#{pane_index}" | grep -q "^${target#*.}$"; then
        log "ERROR" "Pane $target does not exist in session $SESSION"
        return 1
    fi
    
    # Check if pane is responsive (has a process running)
    local pane_info=$(tmux display-panes -t "$SESSION:$target" -p)
    if [[ -z "$pane_info" ]]; then
        log "ERROR" "Pane $target is not responsive"
        return 1
    fi
    
    return 0
}

# Send message to specific agent
send_to_agent() {
    local target_agent="$1"
    local message="$2"
    local message_file=""
    
    # Validate target agent
    if [[ -z "${PANE_MAP[$target_agent]}" ]]; then
        log "ERROR" "Unknown agent: $target_agent"
        log "INFO" "Available agents: ${!PANE_MAP[*]}"
        return 1
    fi
    
    local target_pane="${PANE_MAP[$target_agent]}"
    log "INFO" "Sending message to $target_agent (pane $target_pane)"
    
    # Validate target pane exists
    if ! validate_pane "$target_pane"; then
        return 1
    fi
    
    # Create temporary message file if message is large or contains special chars
    if [[ ${#message} -gt 100 ]] || [[ "$message" == *$'\n'* ]]; then
        message_file=$(mktemp)
        echo "$message" > "$message_file"
        log "INFO" "Created temporary message file: $message_file"
    fi
    
    # Use expect script for reliable delivery
    if [[ -n "$message_file" ]]; then
        if "$EXPECT_SCRIPT" "$SESSION" "$target_pane" "$message_file"; then
            log "SUCCESS" "Message delivered to $target_agent"
            rm -f "$message_file"
            return 0
        else
            log "ERROR" "Failed to deliver message to $target_agent"
            rm -f "$message_file"
            return 1
        fi
    else
        if "$EXPECT_SCRIPT" "$SESSION" "$target_pane" "$message"; then
            log "SUCCESS" "Message delivered to $target_agent"
            return 0
        else
            log "ERROR" "Failed to deliver message to $target_agent"
            return 1
        fi
    fi
}

# Broadcast message to all workers
broadcast_to_workers() {
    local message="$1"
    local failed_agents=()
    
    log "INFO" "Broadcasting message to all workers"
    
    for agent in frontend backend infra; do
        if ! send_to_agent "$agent" "$message"; then
            failed_agents+=("$agent")
        fi
    done
    
    if [[ ${#failed_agents[@]} -gt 0 ]]; then
        log "ERROR" "Failed to deliver to: ${failed_agents[*]}"
        return 1
    else
        log "SUCCESS" "Broadcast completed successfully"
        return 0
    fi
}

# Show fleet status
show_status() {
    log "INFO" "Fleet Command Status Report"
    echo "Session: $SESSION"
    echo "Panes:"
    
    for agent in "${!PANE_MAP[@]}"; do
        local pane="${PANE_MAP[$agent]}"
        if validate_pane "$pane" 2>/dev/null; then
            echo "  ✅ $agent ($pane) - READY"
        else
            echo "  ❌ $agent ($pane) - NOT READY"
        fi
    done
}

# Test message delivery
test_delivery() {
    local test_msg="🧪 Fleet Command Test Message - $(date)"
    log "INFO" "Testing message delivery system"
    
    echo "Testing with simple message..."
    if send_to_agent "frontend" "$test_msg"; then
        echo "✅ Simple message delivery: PASS"
    else
        echo "❌ Simple message delivery: FAIL"
        return 1
    fi
    
    echo "Testing with large message..."
    local large_msg="🧪 Large Test Message - This is a multi-line test message with various characters and symbols. It contains:\n- Multiple lines\n- Special characters: @#\$%^&*()\n- Unicode: 🚀🎯💡\n- Code snippets: function test() { return 'hello'; }\n- Long text to test chunking behavior when messages exceed the expected buffer size."
    
    if send_to_agent "backend" "$large_msg"; then
        echo "✅ Large message delivery: PASS"
    else
        echo "❌ Large message delivery: FAIL"  
        return 1
    fi
    
    echo "✅ All tests passed!"
}

# Main command handling
case "${1:-}" in
    "send")
        if [[ $# -lt 3 ]]; then
            echo "Usage: $0 send <agent> <message>"
            echo "Agents: ${!PANE_MAP[*]}"
            exit 1
        fi
        send_to_agent "$2" "$3"
        ;;
    "broadcast")
        if [[ $# -lt 2 ]]; then
            echo "Usage: $0 broadcast <message>"
            exit 1
        fi
        broadcast_to_workers "$2"
        ;;
    "status")
        show_status
        ;;
    "test")
        test_delivery
        ;;
    *)
        echo "Fleet Command Message Router"
        echo ""
        echo "Usage: $0 <command> [args...]"
        echo ""
        echo "Commands:"
        echo "  send <agent> <message>    Send message to specific agent"
        echo "  broadcast <message>       Send message to all workers"
        echo "  status                    Show fleet status"
        echo "  test                      Test message delivery system"
        echo ""
        echo "Available agents: ${!PANE_MAP[*]}"
        echo ""
        echo "Examples:"
        echo "  $0 send frontend '[T101] Create login component with validation'"
        echo "  $0 broadcast 'Fleet status report requested'"
        echo "  $0 test"
        exit 1
        ;;
esac
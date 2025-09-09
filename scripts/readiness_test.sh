#!/bin/bash
#
# readiness_test.sh - Test pane readiness and expect functionality
#

set -e

SESSION="hive-swarm"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2"
}

# Test if tmux session exists
test_session() {
    log "INFO" "Testing tmux session: $SESSION"
    
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        log "SUCCESS" "Session $SESSION exists"
        return 0
    else
        log "ERROR" "Session $SESSION does not exist"
        return 1
    fi
}

# Test pane accessibility
test_panes() {
    log "INFO" "Testing pane accessibility"
    
    local panes=("0.0" "0.1" "0.2" "0.3")
    local failed_panes=()
    
    for pane in "${panes[@]}"; do
        if tmux list-panes -t "$SESSION" -F "#{pane_index}" | grep -q "^${pane#*.}$"; then
            log "SUCCESS" "Pane $pane is accessible"
        else
            log "ERROR" "Pane $pane is not accessible"
            failed_panes+=("$pane")
        fi
    done
    
    if [[ ${#failed_panes[@]} -gt 0 ]]; then
        log "ERROR" "Failed panes: ${failed_panes[*]}"
        return 1
    fi
    
    return 0
}

# Test expect script functionality
test_expect() {
    log "INFO" "Testing expect script functionality"
    
    # Test with a simple echo command
    local test_pane="0.1"  # Frontend pane
    local test_msg="echo '🧪 Expect test - $(date)'"
    
    log "INFO" "Sending test command to pane $test_pane"
    
    if "$SCRIPT_DIR/worker_expect.sh" "$SESSION" "$test_pane" "$test_msg"; then
        log "SUCCESS" "Expect script test passed"
        
        # Capture the output to verify it worked
        sleep 2
        local output=$(tmux capture-pane -pt "$SESSION:$test_pane" -S -5)
        
        if echo "$output" | grep -q "Expect test"; then
            log "SUCCESS" "Command output verified in pane"
            return 0
        else
            log "WARN" "Command sent but output not found in pane"
            return 1
        fi
    else
        log "ERROR" "Expect script test failed"
        return 1
    fi
}

# Test message routing
test_routing() {
    log "INFO" "Testing message routing system"
    
    if "$SCRIPT_DIR/fleet_send.sh" test; then
        log "SUCCESS" "Message routing test passed"
        return 0
    else
        log "ERROR" "Message routing test failed"
        return 1
    fi
}

# Show pane contents for debugging
show_pane_contents() {
    log "INFO" "Showing current pane contents for debugging"
    
    local panes=("0.0:Queen" "0.1:Frontend" "0.2:Backend" "0.3:Infra")
    
    for pane_info in "${panes[@]}"; do
        local pane="${pane_info%:*}"
        local name="${pane_info#*:}"
        
        echo ""
        echo "=== $name (Pane $pane) ==="
        tmux capture-pane -pt "$SESSION:$pane" -S -10 || echo "Failed to capture pane $pane"
        echo "=========================="
    done
}

# Main test runner
run_all_tests() {
    log "INFO" "Starting Fleet Command readiness tests"
    
    local tests=(
        "test_session"
        "test_panes" 
        "test_expect"
        "test_routing"
    )
    
    local failed_tests=()
    
    for test in "${tests[@]}"; do
        echo ""
        if ! $test; then
            failed_tests+=("$test")
        fi
    done
    
    echo ""
    if [[ ${#failed_tests[@]} -eq 0 ]]; then
        log "SUCCESS" "All readiness tests passed! ✅"
        return 0
    else
        log "ERROR" "Failed tests: ${failed_tests[*]} ❌"
        echo ""
        log "INFO" "Running diagnostics..."
        show_pane_contents
        return 1
    fi
}

# Command handling
case "${1:-all}" in
    "session")
        test_session
        ;;
    "panes")
        test_panes
        ;;
    "expect")
        test_expect
        ;;
    "routing")
        test_routing
        ;;
    "debug")
        show_pane_contents
        ;;
    "all"|"")
        run_all_tests
        ;;
    *)
        echo "Usage: $0 [session|panes|expect|routing|debug|all]"
        echo ""
        echo "Tests:"
        echo "  session  - Test if tmux session exists"
        echo "  panes    - Test pane accessibility"  
        echo "  expect   - Test expect script functionality"
        echo "  routing  - Test message routing system"
        echo "  debug    - Show pane contents for debugging"
        echo "  all      - Run all tests (default)"
        exit 1
        ;;
esac
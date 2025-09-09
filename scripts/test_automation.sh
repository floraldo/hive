#!/bin/bash
#
# test_automation.sh - Comprehensive testing for Fleet Command automation
# Tests expect functionality, message delivery, error recovery, and edge cases
#

set -e

SESSION="hive-swarm"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEST_MESSAGES="$PROJECT_DIR/test_messages.md"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2"
}

success() {
    log "${GREEN}SUCCESS${NC}" "$1"
}

error() {
    log "${RED}ERROR${NC}" "$1"
}

warn() {
    log "${YELLOW}WARN${NC}" "$1"
}

info() {
    log "${BLUE}INFO${NC}" "$1"
}

# Extract test messages from the test file
extract_message() {
    local message_type="$1"
    local start_pattern=""
    local end_pattern=""
    
    case "$message_type" in
        "small")
            start_pattern="## Small Test Message"
            end_pattern="## Medium Test Message"
            ;;
        "medium")
            start_pattern="## Medium Test Message"
            end_pattern="## Large Test Message"
            ;;
        "large")
            start_pattern="## Large Test Message"
            end_pattern="$"  # End of file
            ;;
        *)
            error "Unknown message type: $message_type"
            return 1
            ;;
    esac
    
    # Extract the message content between patterns
    sed -n "/$start_pattern/,/$end_pattern/p" "$TEST_MESSAGES" | \
        sed '1d' | \
        if [[ "$end_pattern" != '$' ]]; then sed '$d'; fi
}

# Test basic session and pane availability
test_fleet_availability() {
    info "Testing fleet availability..."
    
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        error "Tmux session '$SESSION' not found. Run 'make swarm' first."
        return 1
    fi
    
    local required_panes=("0.0" "0.1" "0.2" "0.3")
    for pane in "${required_panes[@]}"; do
        if ! tmux list-panes -t "$SESSION" -F "#{pane_index}" | grep -q "^${pane#*.}$"; then
            error "Required pane $pane not found"
            return 1
        fi
    done
    
    success "All required panes available"
    return 0
}

# Test small message delivery
test_small_message() {
    info "Testing small message delivery..."
    
    local message=$(extract_message "small")
    local target_pane="0.1"  # Frontend pane
    
    info "Sending small message to pane $target_pane"
    
    if "$SCRIPT_DIR/worker_expect.sh" "$SESSION" "$target_pane" "$message"; then
        success "Small message delivered successfully"
        
        # Verify the message appeared in the pane
        sleep 2
        local output=$(tmux capture-pane -pt "$SESSION:$target_pane" -S -10)
        if echo "$output" | grep -q "Simple test message"; then
            success "Message content verified in pane"
            return 0
        else
            warn "Message sent but content not found in pane output"
            return 1
        fi
    else
        error "Failed to deliver small message"
        return 1
    fi
}

# Test medium message with special characters
test_medium_message() {
    info "Testing medium message with special characters..."
    
    local message=$(extract_message "medium")
    local target_pane="0.2"  # Backend pane
    
    info "Sending medium message to pane $target_pane"
    
    if "$SCRIPT_DIR/worker_expect.sh" "$SESSION" "$target_pane" "$message"; then
        success "Medium message delivered successfully"
        
        # Verify special characters and emojis were handled
        sleep 2
        local output=$(tmux capture-pane -pt "$SESSION:$target_pane" -S -15)
        if echo "$output" | grep -q "T001" && echo "$output" | grep -q "🚀"; then
            success "Special characters and emojis handled correctly"
            return 0
        else
            warn "Message sent but special characters not verified"
            return 1
        fi
    else
        error "Failed to deliver medium message"
        return 1
    fi
}

# Test large message chunking
test_large_message() {
    info "Testing large message chunking and delivery..."
    
    local message=$(extract_message "large")
    local target_pane="0.3"  # Infra pane
    
    info "Sending large message ($(echo "$message" | wc -c) characters) to pane $target_pane"
    
    if "$SCRIPT_DIR/worker_expect.sh" "$SESSION" "$target_pane" "$message"; then
        success "Large message delivered successfully"
        
        # Verify key parts of the message
        sleep 3
        local output=$(tmux capture-pane -pt "$SESSION:$target_pane" -S -50)
        
        local checks_passed=0
        local total_checks=4
        
        if echo "$output" | grep -q "T101"; then
            success "Task ID found in output"
            ((checks_passed++))
        else
            warn "Task ID not found in output"
        fi
        
        if echo "$output" | grep -q "Authentication System"; then
            success "Title found in output"
            ((checks_passed++))
        else
            warn "Title not found in output"
        fi
        
        if echo "$output" | grep -q "require_auth"; then
            success "Code example found in output"
            ((checks_passed++))
        else
            warn "Code example not found in output"
        fi
        
        if echo "$output" | grep -q "chunking"; then
            success "End of message found in output"
            ((checks_passed++))
        else
            warn "End of message not found in output"
        fi
        
        if [[ $checks_passed -ge 3 ]]; then
            success "Large message chunking test passed ($checks_passed/$total_checks checks)"
            return 0
        else
            error "Large message chunking test failed ($checks_passed/$total_checks checks)"
            return 1
        fi
    else
        error "Failed to deliver large message"
        return 1
    fi
}

# Test fleet routing system
test_fleet_routing() {
    info "Testing fleet routing system..."
    
    # Test broadcast functionality
    local broadcast_msg="🧪 Fleet Command Broadcast Test - $(date)"
    
    info "Testing broadcast to all workers..."
    if "$SCRIPT_DIR/fleet_send.sh" broadcast "$broadcast_msg"; then
        success "Broadcast completed successfully"
    else
        error "Broadcast test failed"
        return 1
    fi
    
    # Test individual agent targeting
    local agents=("frontend" "backend" "infra")
    for agent in "${agents[@]}"; do
        local agent_msg="🎯 Direct message test for $agent - $(date)"
        info "Testing direct message to $agent..."
        
        if "$SCRIPT_DIR/fleet_send.sh" send "$agent" "$agent_msg"; then
            success "Direct message to $agent delivered"
        else
            error "Direct message to $agent failed"
            return 1
        fi
    done
    
    return 0
}

# Test error recovery scenarios
test_error_recovery() {
    info "Testing error recovery scenarios..."
    
    # Test sending to non-existent agent
    info "Testing graceful failure for invalid agent..."
    if ! "$SCRIPT_DIR/fleet_send.sh" send "nonexistent" "test message" 2>/dev/null; then
        success "Correctly rejected invalid agent"
    else
        warn "Should have rejected invalid agent"
    fi
    
    # Test with empty message
    info "Testing handling of empty message..."
    if ! "$SCRIPT_DIR/fleet_send.sh" send "frontend" "" 2>/dev/null; then
        success "Correctly handled empty message"
    else
        warn "Should have handled empty message gracefully"
    fi
    
    return 0
}

# Performance test with rapid message delivery
test_performance() {
    info "Testing performance with rapid message delivery..."
    
    local start_time=$(date +%s)
    local message_count=5
    local target_agent="frontend"
    
    for i in $(seq 1 $message_count); do
        local msg="🏎️ Performance test message $i/$$message_count - $(date)"
        info "Sending rapid message $i..."
        
        if ! "$SCRIPT_DIR/fleet_send.sh" send "$target_agent" "$msg"; then
            error "Performance test failed at message $i"
            return 1
        fi
    done
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    success "Performance test completed: $message_count messages in ${duration}s"
    return 0
}

# Run all tests
run_all_tests() {
    info "🧪 Starting comprehensive Fleet Command automation tests"
    
    local tests=(
        "test_fleet_availability"
        "test_small_message"
        "test_medium_message"
        "test_large_message"
        "test_fleet_routing"
        "test_error_recovery"
        "test_performance"
    )
    
    local passed_tests=()
    local failed_tests=()
    
    for test in "${tests[@]}"; do
        echo ""
        info "Running: $test"
        if $test; then
            passed_tests+=("$test")
        else
            failed_tests+=("$test")
        fi
    done
    
    echo ""
    echo "=========================================="
    info "🧪 Test Results Summary"
    echo "=========================================="
    
    if [[ ${#passed_tests[@]} -gt 0 ]]; then
        success "Passed tests (${#passed_tests[@]}):"
        for test in "${passed_tests[@]}"; do
            echo "  ✅ $test"
        done
    fi
    
    if [[ ${#failed_tests[@]} -gt 0 ]]; then
        error "Failed tests (${#failed_tests[@]}):"
        for test in "${failed_tests[@]}"; do
            echo "  ❌ $test"
        done
        echo ""
        error "Some tests failed. Check the output above for details."
        return 1
    else
        echo ""
        success "🎉 All automation tests passed! Fleet Command v4.0 is ready for deployment."
        return 0
    fi
}

# Command handling
case "${1:-all}" in
    "availability")
        test_fleet_availability
        ;;
    "small")
        test_small_message
        ;;
    "medium")
        test_medium_message
        ;;
    "large")
        test_large_message
        ;;
    "routing")
        test_fleet_routing
        ;;
    "recovery")
        test_error_recovery
        ;;
    "performance")
        test_performance
        ;;
    "all"|"")
        run_all_tests
        ;;
    *)
        echo "Fleet Command Automation Test Suite"
        echo ""
        echo "Usage: $0 [test_name]"
        echo ""
        echo "Available tests:"
        echo "  availability  - Test fleet session and pane availability"
        echo "  small         - Test small message delivery"
        echo "  medium        - Test medium message with special characters"
        echo "  large         - Test large message chunking"
        echo "  routing       - Test fleet routing and broadcast"
        echo "  recovery      - Test error recovery scenarios"
        echo "  performance   - Test rapid message delivery"
        echo "  all           - Run all tests (default)"
        echo ""
        echo "Prerequisites:"
        echo "  - Run 'make swarm' to start the fleet first"
        echo "  - Ensure expect is installed"
        exit 1
        ;;
esac
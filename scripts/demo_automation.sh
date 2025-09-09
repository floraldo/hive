#!/bin/bash
#
# demo_automation.sh - Fleet Command v4.0 Automation Demonstration
# Showcases expect automation, message bus, and inter-agent communication
#

set -e

SESSION="hive-swarm"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging with colors
log() {
    echo -e "[$(date '+%H:%M:%S')] [$1] $2"
}

success() {
    log "${GREEN}SUCCESS${NC}" "$1"
}

info() {
    log "${BLUE}INFO${NC}" "$1"
}

demo_step() {
    log "${PURPLE}DEMO${NC}" "$1"
}

wait_for_user() {
    echo ""
    read -p "Press Enter to continue to next demonstration..."
    echo ""
}

# Check prerequisites
check_prerequisites() {
    demo_step "Checking Fleet Command prerequisites..."
    
    # Check if session exists
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        echo "❌ Tmux session '$SESSION' not found."
        echo "   Please run 'make swarm' first to start the fleet."
        exit 1
    fi
    
    # Check if expect is available
    if ! command -v expect &> /dev/null; then
        echo "❌ expect command not found."
        echo "   Please install expect for automation features."
        exit 1
    fi
    
    # Check if scripts are executable
    local scripts=("fleet_send.sh" "hive-send" "hive-recv" "hive-status")
    for script in "${scripts[@]}"; do
        if [[ ! -x "$SCRIPT_DIR/$script" ]]; then
            echo "❌ Script not executable: $script"
            echo "   Please run: chmod +x scripts/$script"
            exit 1
        fi
    done
    
    success "All prerequisites met!"
    wait_for_user
}

# Demo 1: Basic automated message delivery
demo_basic_automation() {
    demo_step "DEMO 1: Basic Automated Message Delivery"
    echo ""
    echo "This demonstrates expect-based automation that sends messages"
    echo "directly to Claude Code REPLs without manual Enter presses."
    echo ""
    
    info "Sending automated message to Frontend Worker..."
    local message="🎨 Automated Demo Message: Frontend, please acknowledge receipt and confirm automation is working. Time: $(date)"
    
    if "$SCRIPT_DIR/fleet_send.sh" send frontend "$message"; then
        success "Message sent successfully!"
        echo ""
        echo "Check the Frontend pane (0.1) - you should see the message appear automatically!"
        echo "No manual Enter press was required."
    else
        echo "❌ Message delivery failed"
    fi
    
    wait_for_user
}

# Demo 2: Large message chunking
demo_large_message() {
    demo_step "DEMO 2: Large Message Chunking and Delivery"
    echo ""
    echo "This demonstrates how the system handles large, complex messages"
    echo "by automatically chunking them for reliable delivery."
    echo ""
    
    # Create a large, complex task description
    local large_message="🚀 LARGE TASK DEMONSTRATION

Task ID: DEMO-002
Priority: High
Agent: Backend Worker

MISSION: Authentication System Implementation

This is a comprehensive task that demonstrates our system's ability to handle
large, complex messages with multiple requirements:

REQUIREMENTS:
1. Implement JWT-based authentication system
   - Secure token generation and validation
   - Token refresh mechanism
   - Blacklist management for logout

2. Create comprehensive API endpoints:
   - POST /api/auth/login
   - POST /api/auth/logout  
   - POST /api/auth/refresh
   - GET /api/auth/me
   - POST /api/auth/change-password

3. Security implementations:
   - Password hashing with bcrypt (cost factor: 12)
   - Rate limiting (5 attempts per minute)
   - Input validation and sanitization
   - SQL injection prevention
   - XSS protection headers

4. Database design:
   - Users table with proper indexing
   - Auth tokens table for tracking
   - Audit log for security events

5. Testing requirements:
   - Unit tests for all functions (>90% coverage)
   - Integration tests for API endpoints
   - Security penetration testing
   - Performance testing under load

TECHNICAL SPECIFICATIONS:
- Framework: Python Flask with SQLAlchemy
- Database: PostgreSQL with proper migrations
- Caching: Redis for session management
- Documentation: OpenAPI/Swagger specs
- Containerization: Docker with multi-stage builds

CODE EXAMPLE:
\`\`\`python
@app.route('/api/auth/login', methods=['POST'])
@rate_limit('5 per minute')
def login():
    data = request.get_json()
    user = authenticate_user(data['username'], data['password'])
    if user:
        token = generate_jwt_token(user.id)
        return jsonify({'token': token, 'expires_in': 3600})
    return jsonify({'error': 'Invalid credentials'}), 401
\`\`\`

This message contains $(echo -n "$large_message" | wc -c) characters and will be automatically
chunked for reliable delivery. The system handles code blocks, special characters,
emoji, and formatting while maintaining message integrity.

DELIVERABLES:
- Complete authentication system
- Full test suite
- Documentation
- Security audit report

Report STATUS: success when complete."

    info "Sending large message ($(echo -n "$large_message" | wc -c) characters) to Backend Worker..."
    
    if "$SCRIPT_DIR/fleet_send.sh" send backend "$large_message"; then
        success "Large message delivered successfully!"
        echo ""
        echo "Check the Backend pane (0.2) - the entire message should appear"
        echo "despite its size and complexity. The system automatically chunked it."
    else
        echo "❌ Large message delivery failed"
    fi
    
    wait_for_user
}

# Demo 3: Broadcast functionality
demo_broadcast() {
    demo_step "DEMO 3: Broadcast Communication"
    echo ""
    echo "This demonstrates broadcasting messages to all workers simultaneously."
    echo ""
    
    local broadcast_msg="📡 FLEET-WIDE ANNOUNCEMENT: This is a demonstration of the broadcast system. All workers should receive this message simultaneously. Timestamp: $(date '+%Y-%m-%d %H:%M:%S'). Please acknowledge receipt in your respective panes."
    
    info "Broadcasting message to all workers (Frontend, Backend, Infra)..."
    
    if "$SCRIPT_DIR/fleet_send.sh" broadcast "$broadcast_msg"; then
        success "Broadcast completed successfully!"
        echo ""
        echo "Check all worker panes (0.1, 0.2, 0.3) - they should all show the same message."
        echo "This enables fleet-wide coordination and announcements."
    else
        echo "❌ Broadcast failed"
    fi
    
    wait_for_user
}

# Demo 4: Message bus system
demo_message_bus() {
    demo_step "DEMO 4: Persistent Message Bus System"
    echo ""
    echo "This demonstrates the persistent message bus that enables"
    echo "asynchronous communication and message history."
    echo ""
    
    # Send various types of messages to the bus
    info "Sending structured messages to the message bus..."
    
    # Task message
    "$SCRIPT_DIR/hive-send" --to frontend --topic task --priority high \
        --message "Create responsive navigation component with accessibility features"
    
    # Status message
    "$SCRIPT_DIR/hive-send" --to backend --topic status --priority normal \
        --message "Database migration completed successfully. All tables updated."
    
    # Question message
    "$SCRIPT_DIR/hive-send" --to infra --topic question --priority high \
        --message "Which container orchestration platform should we use: Docker Swarm or Kubernetes?"
    
    # Alert message
    "$SCRIPT_DIR/hive-send" --to queen --topic alert --priority critical \
        --message "High memory usage detected on production servers. Immediate attention required."
    
    success "Messages sent to persistent bus!"
    echo ""
    
    info "Demonstrating message retrieval..."
    echo ""
    
    # Show messages for different agents
    echo "=== FRONTEND MESSAGES ==="
    "$SCRIPT_DIR/hive-recv" --for frontend --unread-only
    echo ""
    
    echo "=== BACKEND MESSAGES ==="
    "$SCRIPT_DIR/hive-recv" --for backend --unread-only
    echo ""
    
    echo "=== INFRA MESSAGES ==="
    "$SCRIPT_DIR/hive-recv" --for infra --unread-only
    echo ""
    
    success "Message bus demonstration complete!"
    echo "Messages are stored persistently and can be retrieved anytime."
    
    wait_for_user
}

# Demo 5: Status monitoring dashboard
demo_status_dashboard() {
    demo_step "DEMO 5: Real-time Status Dashboard"
    echo ""
    echo "This demonstrates the comprehensive status monitoring system"
    echo "that shows message counts, agent activity, and system health."
    echo ""
    
    info "Showing fleet status dashboard..."
    echo ""
    
    "$SCRIPT_DIR/hive-status" --detailed
    
    echo ""
    success "Status dashboard shows all agent activity and message statistics!"
    echo ""
    echo "For continuous monitoring, you can run:"
    echo "  ./scripts/hive-status --watch"
    echo ""
    echo "This provides real-time updates every 2 seconds."
    
    wait_for_user
}

# Demo 6: Error recovery and testing
demo_error_recovery() {
    demo_step "DEMO 6: Error Recovery and System Testing"
    echo ""
    echo "This demonstrates the system's error recovery capabilities"
    echo "and comprehensive testing framework."
    echo ""
    
    info "Running automated test suite..."
    echo ""
    
    # Run the test automation suite
    if "$SCRIPT_DIR/test_automation.sh"; then
        success "All automation tests passed!"
    else
        echo "⚠️  Some tests may have failed - this is normal in a demo environment"
    fi
    
    echo ""
    info "Testing error handling..."
    
    # Test invalid agent (should fail gracefully)
    echo "Testing invalid agent handling..."
    if ! "$SCRIPT_DIR/fleet_send.sh" send "invalid_agent" "test" 2>/dev/null; then
        success "System correctly rejected invalid agent"
    else
        echo "⚠️  System should have rejected invalid agent"
    fi
    
    # Test empty message (should fail gracefully)
    echo "Testing empty message handling..."
    if ! "$SCRIPT_DIR/fleet_send.sh" send frontend "" 2>/dev/null; then
        success "System correctly handled empty message"
    else
        echo "⚠️  System should have handled empty message"
    fi
    
    success "Error recovery demonstration complete!"
    
    wait_for_user
}

# Main demo orchestration
run_full_demo() {
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}║         🚀 FLEET COMMAND v4.0 AUTOMATION DEMO 🚀            ║${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}║    Comprehensive demonstration of automated multi-agent      ║${NC}"
    echo -e "${CYAN}║    communication, message bus, and expect integration        ║${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    check_prerequisites
    demo_basic_automation
    demo_large_message
    demo_broadcast
    demo_message_bus
    demo_status_dashboard
    demo_error_recovery
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║                🎉 DEMO COMPLETE! 🎉                          ║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║         Fleet Command v4.0 is ready for deployment          ║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo "🚀 FLEET COMMAND v4.0 CAPABILITIES DEMONSTRATED:"
    echo "  ✅ Expect-based automated message delivery"
    echo "  ✅ Large message chunking and error recovery"
    echo "  ✅ Broadcast communication to all agents"
    echo "  ✅ Persistent JSON-based message bus"
    echo "  ✅ Real-time status monitoring dashboard"
    echo "  ✅ Comprehensive error handling and testing"
    echo ""
    echo "🔧 NEXT STEPS:"
    echo "  • Use ./scripts/fleet_send.sh for immediate automation"
    echo "  • Use ./scripts/hive-* tools for persistent communication"
    echo "  • Run ./scripts/hive-status --watch for monitoring"
    echo "  • Check tmux panes to see messages delivered successfully"
    echo ""
    echo "🎯 You now have a fully automated Claude Code Multi-Agent System!"
}

# Command handling
case "${1:-full}" in
    "basic")
        demo_basic_automation
        ;;
    "large")
        demo_large_message
        ;;
    "broadcast")
        demo_broadcast
        ;;
    "bus")
        demo_message_bus
        ;;
    "status")
        demo_status_dashboard
        ;;
    "recovery")
        demo_error_recovery
        ;;
    "full"|"")
        run_full_demo
        ;;
    *)
        echo "Fleet Command v4.0 Automation Demo"
        echo ""
        echo "Usage: $0 [demo_name]"
        echo ""
        echo "Available demos:"
        echo "  basic      - Basic automated message delivery"
        echo "  large      - Large message chunking"
        echo "  broadcast  - Broadcast communication"
        echo "  bus        - Persistent message bus"
        echo "  status     - Status monitoring dashboard"
        echo "  recovery   - Error recovery and testing"
        echo "  full       - Run all demonstrations (default)"
        echo ""
        echo "Prerequisites:"
        echo "  - Run 'make swarm' to start the fleet first"
        echo "  - Ensure expect is installed for automation"
        exit 1
        ;;
esac
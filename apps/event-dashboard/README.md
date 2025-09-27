# Hive Event Dashboard

Real-time visualization and monitoring dashboard for Hive V4.0 Event-Driven Architecture.

## Features

- **Live Event Stream**: Real-time display of events flowing through the system
- **Agent Activity Monitoring**: Track agent status, activity, and health
- **Workflow Tracing**: Monitor active workflows and their progression
- **System Statistics**: Overall system health and performance metrics
- **Interactive Dashboard**: Rich terminal-based interface with live updates

## Quick Start

```bash
# Start the dashboard
python apps/event-dashboard/start_dashboard.py

# Or run directly
python apps/event-dashboard/dashboard.py
```

## Dashboard Sections

### Recent Events (Live)
- Shows the last 20 events in real-time
- Displays event type, source agent, and key details
- Updates every 500ms with color-coded information

### Agent Activity
- Lists all agents that have published events
- Shows online/offline status based on recent activity
- Displays event counts and types per agent
- Color-coded status indicators:
  - 🟢 Active (last event < 1 minute)
  - 🟡 Idle (last event < 5 minutes)
  - 🔴 Offline (last event > 5 minutes)

### Active Workflows
- Tracks workflows using correlation IDs
- Shows workflow duration and event count
- Displays workflow status and last activity
- Automatically filters to recent workflows (last hour)

### System Statistics
- Total events processed
- Events per minute rate
- Active workflow count
- Online agent count
- Last system update time

## Event Types Monitored

The dashboard monitors all event types from the Hive event bus:

### Task Events
- `task.created` - New task created
- `task.assigned` - Task assigned to worker
- `task.started` - Task execution started
- `task.completed` - Task completed successfully
- `task.failed` - Task execution failed
- `task.review_requested` - Task sent for review
- `task.review_completed` - Review completed
- `task.escalated` - Task escalated to human

### Workflow Events
- `workflow.plan_generated` - Execution plan created
- `workflow.phase_started` - Workflow phase began
- `workflow.phase_completed` - Workflow phase finished
- `workflow.blocked` - Workflow blocked on dependency

### Agent Events
- `agent.started` - Agent came online
- `agent.stopped` - Agent stopped
- `agent.heartbeat` - Agent health check
- `agent.error` - Agent error occurred

## Architecture Integration

The dashboard integrates with:

- **Hive Event Bus**: Subscribes to all events using wildcard pattern `*`
- **Event Correlation**: Tracks workflows using correlation IDs
- **Agent Communication**: Monitors explicit agent-to-agent communication
- **Real-time Updates**: Provides live visibility into system behavior

## Technical Details

### Dependencies
- `rich` - Terminal UI library for rich text and layouts
- `asyncio` - Asynchronous event handling
- `hive-bus` - Hive event bus package
- `hive-logging` - Hive logging utilities

### Performance
- Lightweight event monitoring with minimal system impact
- Efficient memory usage with event history limits
- Optimized refresh rates for smooth real-time display
- Non-blocking event processing

### Configuration
- Max recent events: 20 (configurable)
- Refresh rate: 2 Hz (configurable)
- Activity window: 5 minutes for agent status
- Workflow window: 1 hour for active workflows

## Usage Examples

### Basic Monitoring
Start the dashboard to monitor system activity:
```bash
python apps/event-dashboard/start_dashboard.py
```

### Integration with Fleet Command
The dashboard can be run alongside the Fleet Command system to monitor agent activity:
```bash
# Terminal 1: Start Queen
python apps/hive-orchestrator/src/hive_orchestrator/queen.py

# Terminal 2: Start AI Planner
python apps/ai-planner/src/ai_planner/agent.py

# Terminal 3: Start Event Dashboard
python apps/event-dashboard/start_dashboard.py
```

### Development and Debugging
Use the dashboard during development to:
- Verify event publishing integration
- Debug agent communication patterns
- Monitor workflow progression
- Identify bottlenecks or failures

## Future Enhancements

Planned improvements for the dashboard:

### Phase 4.1 (Async Integration)
- Async event processing for higher throughput
- Real-time performance metrics
- Advanced filtering and search

### Phase 4.2 (Intelligence Layer)
- Event pattern analysis
- Anomaly detection
- Predictive workflow monitoring

### Phase 4.3 (Enterprise Features)
- Web-based dashboard interface
- Historical event analysis
- Alerting and notifications
- Export and reporting capabilities

## Troubleshooting

### Dashboard Won't Start
- Verify hive-bus package is installed and accessible
- Check that event bus database is initialized
- Ensure required dependencies are installed: `pip install rich`

### No Events Displayed
- Verify agents are running and publishing events
- Check event bus configuration in agents
- Ensure dashboard subscription is successful (check logs)

### Performance Issues
- Reduce refresh rate if terminal is slow
- Limit event history size for memory constraints
- Check system resources during high event volumes

## Integration with V4.0 Goals

This dashboard directly supports the V4.0 "Event-Driven Excellence" phase goals:

✅ **Explicit Communication**: Makes implicit database patterns visible
✅ **Real-time Monitoring**: Live visibility into agent interactions
✅ **Workflow Tracing**: End-to-end workflow visualization
✅ **System Health**: Overall system monitoring and diagnostics
✅ **Developer Experience**: Enhanced debugging and development workflow
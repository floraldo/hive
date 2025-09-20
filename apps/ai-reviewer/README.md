# AI Reviewer - Autonomous Code Review Agent

An intelligent, autonomous code review agent for the Hive App Factory platform. The AI Reviewer continuously monitors the `review_pending` queue and makes automated decisions about code quality, eliminating the need for manual review in most cases.

## Architecture

The AI Reviewer is designed as a completely autonomous, decoupled daemon that:

1. **Polls the Database**: Continuously monitors for tasks with `review_pending` status
2. **Analyzes Code**: Performs multi-dimensional quality assessment
3. **Makes Decisions**: Approves, rejects, or escalates based on quality metrics
4. **Updates Status**: Modifies task status in the database
5. **Operates Independently**: Runs as a peer to the Queen, not subordinate to it

## Key Features

### Autonomous Operation
- Runs continuously as a background daemon
- No human intervention required
- Self-manages workload from the review queue
- Graceful shutdown on signals

### Comprehensive Review Metrics
- **Code Quality** (30% weight): Complexity, nesting, code smells
- **Test Coverage** (25% weight): Test presence and results
- **Documentation** (15% weight): Docstring coverage
- **Security** (20% weight): Vulnerability detection
- **Architecture** (10% weight): Structure and organization

### Intelligent Decision Making
- **Approve** (score ≥ 80): Ready for integration
- **Rework** (score 60-79): Needs improvements
- **Reject** (score < 60): Significant issues
- **Escalate** (score 40-59): Requires human review

## Installation

```bash
# From the ai-reviewer directory
cd apps/ai-reviewer
poetry install
```

## Configuration

### Environment Variables
```bash
# Anthropic API key for AI capabilities (optional for now)
export ANTHROPIC_API_KEY="your-api-key"

# Database connection (uses Hive config by default)
export DATABASE_URL="postgresql://user:pass@localhost/hive"
```

### hive-app.toml Configuration
The app is configured via `hive-app.toml`:
- Daemon mode for continuous operation
- Automatic restart on failure
- Health monitoring and metrics

## Usage

### Start as Daemon (Production)
```bash
# Start the autonomous review agent
poetry run ai-reviewer-daemon

# Or using Poetry script
poetry run python src/ai_reviewer/agent.py
```

### Test Mode
```bash
# Run with shorter intervals for testing
poetry run python src/ai_reviewer/agent.py --test-mode
```

### Command Line Options
```bash
python src/ai_reviewer/agent.py --help

Options:
  --test-mode           Run with 5-second polling interval
  --api-key KEY         Override Anthropic API key
  --polling-interval N  Custom polling interval in seconds (default: 30)
```

## How It Works

### 1. Queue Monitoring
The agent polls the database every 30 seconds (configurable) for tasks with `review_pending` status.

### 2. Artifact Retrieval
For each task, it retrieves:
- Generated code files
- Test results
- Claude conversation transcripts
- Task metadata

### 3. AI Analysis
Performs comprehensive analysis across multiple dimensions:

```python
# Code Quality Checks
- Function length (penalize >50 lines)
- Nesting depth (penalize >3 levels)
- TODO comments (minus 2 points each)
- Magic numbers
- Duplicate code detection

# Security Scanning
- eval/exec usage
- Hardcoded passwords
- Shell injection risks
- Unsafe deserialization
```

### 4. Decision Execution
Based on the overall score and detected issues:
- Updates task status in database
- Stores detailed review report
- Triggers next phase if approved
- Maintains review history

### 5. Statistics Tracking
Maintains real-time statistics:
- Tasks reviewed
- Approval/rejection rates
- Processing speed
- Error tracking

## Integration with Hive Platform

### Database Schema
Uses the existing Hive database with no schema changes:
```python
# Task statuses used
TaskStatus.REVIEW_PENDING  # Input queue
TaskStatus.APPROVED        # Passed review
TaskStatus.REJECTED        # Failed review
TaskStatus.REWORK_NEEDED   # Needs improvements
TaskStatus.ESCALATED       # Requires human review
```

### Review Data Storage
Review results stored in `task.result_data`:
```json
{
  "review": {
    "task_id": "task-123",
    "decision": "approve",
    "metrics": {
      "code_quality": 85,
      "test_coverage": 90,
      "documentation": 75,
      "security": 95,
      "architecture": 80
    },
    "overall_score": 85.5,
    "issues": [],
    "suggestions": [],
    "confidence": 0.85
  },
  "review_timestamp": "2024-01-20T10:30:00Z",
  "reviewed_by": "ai-reviewer"
}
```

## Testing

### Run Tests
```bash
# Run all tests
poetry run pytest

# With coverage
poetry run pytest --cov=ai_reviewer --cov-report=html

# Specific test file
poetry run pytest tests/test_reviewer.py -v
```

### Test Coverage Areas
- Review engine logic
- Scoring algorithms
- Decision making
- Database operations
- Agent lifecycle
- Error handling

## Monitoring

### Health Check
The agent provides health monitoring:
- Heartbeat every 60 seconds
- Processing statistics
- Error tracking
- Queue depth monitoring

### Logs
```bash
# View agent logs
tail -f logs/ai-reviewer.log

# Log levels
export LOG_LEVEL=DEBUG  # For detailed debugging
export LOG_LEVEL=INFO   # Normal operation
```

### Metrics
Real-time statistics displayed every 10 tasks:
- Total reviewed
- Approval rate
- Processing speed (tasks/hour)
- Error count

## Troubleshooting

### Common Issues

**Agent not picking up tasks:**
- Check database connection
- Verify tasks have `review_pending` status
- Check agent logs for errors

**High rejection rate:**
- Review quality thresholds in `reviewer.py`
- Check if code standards are documented
- Verify test coverage requirements

**Agent crashes:**
- Check API key if using AI features
- Verify database permissions
- Review error logs

### Manual Intervention

For tasks that get escalated:
```bash
# View escalated tasks
hive list-tasks --status escalated

# Manually review and update
hive review-task <task-id>
hive complete-review <task-id> --decision approve
```

## Architecture Benefits

### True Decoupling
- Queen doesn't know AI Reviewer exists
- Communication only through database state
- Can run multiple reviewers in parallel

### Scalability
- Horizontal scaling: Run multiple agents
- Vertical scaling: Adjust polling frequency
- Queue-based: Natural load balancing

### Reliability
- Automatic restart on failure
- Graceful shutdown handling
- Error recovery with escalation

### Maintainability
- Clean separation of concerns
- Modular design
- Comprehensive test coverage

## Future Enhancements

### Planned Features
- [ ] Machine learning for decision improvement
- [ ] Custom review rules per project
- [ ] Webhook notifications
- [ ] Review explanation API
- [ ] Historical trend analysis
- [ ] Team-specific quality standards

### Integration Opportunities
- CI/CD pipeline integration
- Pull request automation
- Slack/Discord notifications
- Custom quality plugins

## Contributing

The AI Reviewer demonstrates the Hive App Factory pattern:
1. Standalone Poetry app
2. hive-app.toml contract
3. Database communication
4. Autonomous operation

To contribute:
1. Follow the app factory pattern
2. Maintain test coverage >80%
3. Update documentation
4. Add integration tests

## License

Part of the Hive App Factory platform.
# Hive Guardian Agent → Oracle Intelligence System

**The Evolution from Guardian to Oracle**: AI-powered code review agent that has evolved into a comprehensive platform intelligence system providing strategic insights, predictive analytics, and proactive recommendations.

## 🔮 The Hive Intelligence Initiative

The Guardian Agent has successfully evolved into the **Hive Oracle** - transforming from a reactive code protector into a proactive platform intelligence system that provides strategic wisdom for the entire Hive ecosystem.

## 🌟 Oracle Capabilities

### Core Intelligence Features
- **🎯 Strategic Recommendations**: Proactive insights for cost optimization, performance improvement, and risk mitigation
- **📊 Mission Control Dashboard**: Single-pane-of-glass view of platform health, costs, and developer velocity
- **🔍 Predictive Analytics**: Failure prediction, capacity planning, and trend analysis
- **💰 Cost Intelligence**: Real-time cost tracking, budget monitoring, and optimization recommendations
- **⚡ Performance Insights**: System performance analysis and bottleneck identification
- **🛡️ Security Intelligence**: Anomaly detection and security enhancement recommendations

### Original Guardian Features
- **Automated Code Review**: AI-powered comprehensive code analysis
- **Golden Rules Enforcement**: Platform compliance validation and reporting
- **Pattern Recognition**: Vector search for code patterns and anti-patterns
- **Intelligent Suggestions**: Context-aware fix recommendations
- **Learning System**: Continuous improvement through feedback processing

## Architecture

The Guardian Agent is built on the Hive platform's "Unassailable" infrastructure:

### Core Components

- **ReviewEngine**: Orchestrates the review process using `hive-ai` model management
- **CodeAnalyzer**: AST-based analysis for deep code understanding
- **ViolationDetector**: Integrates with Golden Rules framework for compliance checking
- **PromptOptimizer**: Dynamic prompt engineering for context-aware reviews

### Infrastructure Leverage

- **hive-ai**: Model client, vector search, prompt management
- **hive-async**: Concurrent review processing
- **hive-db**: Review history and learning persistence
- **hive-cache**: Performance optimization for repeated patterns
- **hive-tests**: Integration with AST-based autofix capabilities

## Installation

```bash
# Install dependencies
poetry install

# Configure AI models
export OPENAI_API_KEY=your-key-here
```

## Usage

### Oracle Intelligence Commands

```bash
# Start the Oracle Intelligence Service
guardian oracle start --daemon

# Get platform health and Oracle status
guardian oracle status

# Generate strategic insights and recommendations
guardian oracle insights --hours 24

# View Mission Control Dashboard
guardian oracle dashboard

# Force immediate platform analysis
guardian oracle analyze

# Get cost intelligence and optimization recommendations
guardian oracle costs
```

### Original Guardian Commands

```bash
# Review a single file
guardian review path/to/file.py

# Review directory
guardian review-dir ./src --recursive

# Get automatic fix preview
guardian autofix path/to/file.py

# Generate review report
guardian review --format=json > review.json
```

### Python API

#### Oracle Intelligence API

```python
from guardian_agent import OracleService, OracleConfig

# Initialize the Oracle
oracle_config = OracleConfig(
    enable_predictive_analysis=True,
    enable_github_integration=True
)
oracle = OracleService(oracle_config)

# Start intelligence gathering
await oracle.start_async()

# Get platform health
health = await oracle.get_platform_health_async()
print(f"Platform Health: {health['overall_score']}/100")

# Get strategic insights
insights = await oracle.get_strategic_insights_async(hours=24)

# Get cost intelligence
costs = await oracle.get_cost_intelligence_async()
print(f"Monthly cost: ${costs['monthly_cost']:.2f}")

# Generate recommendations
recommendations = await oracle.get_recommendations_async()
```

#### Original Guardian API

```python
from guardian_agent import ReviewEngine, GuardianConfig

# Initialize the review engine
config = GuardianConfig()
engine = ReviewEngine(config)

# Review code
result = await engine.review_file("path/to/file.py")

# Get suggestions
suggestions = result.get_suggestions()
```

## Configuration

### Oracle Intelligence Configuration

```yaml
# config/oracle.yaml
oracle:
  # Data collection settings
  collection_interval: 300  # 5 minutes
  analysis_interval: 3600   # 1 hour
  reporting_interval: 86400 # 24 hours

  # Intelligence settings
  min_confidence_threshold: 0.7
  prediction_horizon_hours: 24
  enable_predictive_analysis: true
  enable_github_integration: true

  # Storage settings
  data_retention_days: 90
  cache_ttl_seconds: 300

  # GitHub integration
  github_repository: "hive"
  github_labels: ["oracle", "intelligence", "automated"]

  # Dashboard settings
  dashboard_refresh_interval: 300
  dashboard_port: 8080
```

### Guardian Review Configuration

```yaml
# config/guardian.yaml
review:
  model: "gpt-4"
  temperature: 0.3
  max_tokens: 2000

analysis:
  enable_golden_rules: true
  enable_security_scan: true
  enable_performance_check: true

vector_search:
  index_path: "./vectors"
  similarity_threshold: 0.85

learning:
  enable_feedback_loop: true
  min_confidence: 0.7
```

## Development

### Project Structure

```
apps/guardian-agent/
├── src/guardian_agent/
│   ├── core/           # Core interfaces and configuration
│   ├── review/         # Review engine and orchestration
│   ├── analyzers/      # Code analysis components
│   ├── prompts/        # Prompt templates and optimization
│   └── cli/            # Command-line interface
├── tests/
│   ├── unit/           # Unit tests
│   └── integration/    # Integration tests
├── docs/               # Documentation
└── config/            # Configuration files
```

### Testing

```bash
# Run unit tests
pytest tests/unit

# Run integration tests
pytest tests/integration

# Run with coverage
pytest --cov=guardian_agent

# Type checking
mypy src

# Linting
ruff check src
black --check src
```

## Week 1 Milestones

- [x] Project structure and configuration
- [ ] Basic ReviewEngine implementation
- [ ] CodeAnalyzer with AST support
- [ ] ViolationDetector integration
- [ ] Simple CLI for testing

## Contributing

The Guardian Agent follows the Hive platform's contribution guidelines:

1. All code must pass Golden Rules validation
2. Use existing hive packages - don't reinvent
3. Maintain >90% test coverage
4. Follow the inherit→extend pattern

## License

MIT - See LICENSE file for details

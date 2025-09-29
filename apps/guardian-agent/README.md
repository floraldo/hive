# Hive Guardian Agent

AI-powered code review agent that automates code quality enforcement and provides intelligent feedback on pull requests.

## Features

- **Automated Code Review**: Analyzes code changes using AI to provide comprehensive reviews
- **Golden Rules Enforcement**: Validates code against the Hive platform's Golden Rules
- **Pattern Recognition**: Uses vector search to identify common code patterns and anti-patterns
- **Intelligent Suggestions**: Provides context-aware fix suggestions and improvements
- **Learning System**: Improves over time by learning from past reviews and team preferences

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

### CLI Interface

```bash
# Review a single file
guardian review path/to/file.py

# Review changes in a PR
guardian review-pr --repo=owner/repo --pr=123

# Run in watch mode
guardian watch --path=./src

# Generate review report
guardian report --format=markdown > review.md
```

### Python API

```python
from guardian_agent import ReviewEngine, CodeAnalyzer

# Initialize the review engine
engine = ReviewEngine()

# Review code
result = await engine.review_file("path/to/file.py")

# Get suggestions
suggestions = result.get_suggestions()

# Apply automatic fixes
fixes = await engine.apply_fixes(result.violations)
```

## Configuration

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
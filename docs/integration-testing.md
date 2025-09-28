# Hive Platform Integration Testing Suite

## Overview

The Hive Platform Integration Testing Suite provides comprehensive validation of the complete platform functionality across all components. The suite is designed to catch breaking changes, ensure platform reliability, and validate performance improvements.

## Test Categories

### 1. End-to-End Workflow Tests 🚀

**Purpose**: Test complete AI Planner → Queen → Worker → completion flow

**Coverage**:
- Complete autonomous task execution without manual intervention
- Task decomposition → execution → reporting pipeline
- Error handling and recovery across components
- Dependency resolution and workflow orchestration

**Key Tests**:
- `test_complete_autonomous_workflow()`: Full pipeline validation
- `test_task_decomposition_pipeline()`: Complex task breakdown
- `test_error_handling_and_recovery()`: Failure scenarios

### 2. Cross-App Communication Tests 📡

**Purpose**: Validate database communication and event bus between apps

**Coverage**:
- Database communication between apps using core/ services
- Event bus communication between components
- EcoSystemiser integration with Hive platform
- AI Planner and AI Reviewer integration with orchestrator

**Key Tests**:
- `test_database_communication_core_pattern()`: Core/ pattern compliance
- `test_event_bus_communication()`: Event publishing/consuming
- `test_ecosystemiser_integration()`: Climate data processing
- `test_ai_agents_integration()`: AI components workflow

### 3. Performance Integration Tests ⚡

**Purpose**: Validate async infrastructure and performance improvements

**Coverage**:
- Async infrastructure performance improvements
- Concurrent task processing capabilities
- Database connection pooling under load
- 3-5x performance improvement validation

**Key Tests**:
- `test_async_infrastructure_performance()`: Async operations
- `test_concurrent_task_processing()`: Parallel execution
- `test_database_connection_pooling()`: Database efficiency
- `test_performance_improvement_claims()`: Benchmark validation

### 4. Golden Rules Integration Tests 🏗️

**Purpose**: Ensure architectural standards and core/ pattern compliance

**Coverage**:
- All apps follow the core/ pattern correctly
- Architectural standards are maintained
- Import patterns follow guidelines
- No violations of the inherit → extend pattern

**Key Tests**:
- `test_core_pattern_compliance()`: Directory structure validation
- `test_architectural_standards()`: Import and module patterns
- `test_inherit_extend_pattern()`: Architecture compliance

### 5. Failure and Recovery Tests 🛠️

**Purpose**: Test component failure scenarios and recovery mechanisms

**Coverage**:
- Component failure scenarios (AI Planner, Queen, Worker failures)
- Database connection failures and recovery
- Task retry and escalation workflows
- System resilience under stress

**Key Tests**:
- `test_component_failure_scenarios()`: Individual component failures
- `test_task_retry_escalation()`: Retry logic validation
- `test_system_resilience_under_stress()`: High-load scenarios

### 6. Platform Integration Tests 🌍

**Purpose**: Test platform-wide integration scenarios

**Coverage**:
- EcoSystemiser climate data processing integration
- AI agents integration with task workflows
- Event dashboard displays correct information
- Cross-component status synchronization

**Key Tests**:
- `test_ecosystemiser_climate_integration()`: Weather data workflow
- `test_event_dashboard_integration()`: Dashboard data integrity
- `test_cross_component_status_sync()`: Status propagation

## Test Infrastructure

### Test Environment

The integration tests use an isolated test environment with:

- **Temporary Database**: Each test run uses a fresh SQLite database
- **Mock Services**: Simulated external services for reliable testing
- **Environment Isolation**: Tests don't interfere with each other
- **Performance Monitoring**: Metrics collection for performance validation

### Database Schema

The test database includes tables for all Hive components:

```sql
-- AI Planner
planning_queue, execution_plans

-- Orchestrator
tasks, runs, workers

-- Event Bus
events

-- EcoSystemiser
simulations, studies

-- AI Reviewer
reviews

-- Performance
performance_metrics
```

### Metrics Collection

Tests collect comprehensive metrics:

```python
@dataclass
class TestMetrics:
    tasks_created: int
    plans_generated: int
    subtasks_executed: int
    events_published: int
    database_operations: int
    async_operations: int
    errors_encountered: List[str]
    performance_samples: List[Dict]
```

## Running Tests

### Local Development

#### Quick Validation (2-3 minutes)
```bash
python scripts/run_integration_tests.py --mode quick
```

#### Full Integration Suite (30-45 minutes)
```bash
python scripts/run_integration_tests.py --mode full
```

#### Performance Tests Only (10-15 minutes)
```bash
python scripts/run_integration_tests.py --mode perf
```

#### Custom Test Selection
```bash
python scripts/run_integration_tests.py --mode custom --tests "platform_health,database,event_bus"
```

#### With Report Generation
```bash
python scripts/run_integration_tests.py --mode quick --report results.json
```

### CI/CD Pipeline

The GitHub Actions workflow runs automatically on:

- **Push to main/develop**: Full integration suite
- **Pull Requests**: Quick validation + comprehensive tests
- **Nightly Schedule**: Complete test matrix with performance benchmarks

#### Workflow Jobs

1. **Platform Validation** (5-10 minutes): Quick health checks
2. **Comprehensive Integration** (30-45 minutes): Full test suite
3. **Performance Benchmarks** (15-20 minutes): Performance validation
4. **Cross-Platform Compatibility** (10-15 minutes): Multi-OS testing
5. **Security Integration** (5-10 minutes): Security vulnerability checks

### Pytest Integration

Individual test categories can be run with pytest:

```bash
# Platform validation
pytest tests/test_hive_platform_validation.py -v

# Comprehensive integration
pytest tests/test_comprehensive_integration.py::ComprehensiveIntegrationTestSuite::test_comprehensive_integration -v

# Specific test categories
pytest tests/test_comprehensive_integration.py -k "performance" -v
```

## Test Design Patterns

### Test Isolation

Each test uses the `PlatformTestEnvironment` class for complete isolation:

```python
class PlatformTestEnvironment:
    def setup(self):
        # Create temporary directory and database
        # Initialize test schemas
        # Set environment variables

    def teardown(self):
        # Clean up temporary files
        # Reset environment
```

### Mock Services

External dependencies are mocked for reliability:

```python
# AI Planner simulation
def simulate_ai_planner_processing(self, task_id: str) -> str:
    # Generate realistic execution plan
    # Create subtasks with dependencies
    # Return plan ID

# Worker simulation
def simulate_worker_completion(self, task_id: str, success: bool = True):
    # Update task status
    # Create run records
    # Simulate execution time
```

### Performance Measurement

Performance tests measure actual execution time and throughput:

```python
def test_concurrent_task_processing(self) -> bool:
    start_time = time.time()

    # Execute concurrent operations
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_task, task_id) for task_id in task_ids]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    duration = time.time() - start_time
    throughput = task_count / duration

    # Record metrics
    self.env.metrics.performance_samples.append({
        "test": "concurrent_processing",
        "throughput": throughput,
        "duration": duration
    })
```

### Error Injection

Failure tests inject realistic error conditions:

```python
def test_component_failure_scenarios(self) -> bool:
    # Test AI Planner failure
    self._simulate_ai_planner_timeout()

    # Test Worker crash
    self._simulate_worker_crash()

    # Test Database connection failure
    self._simulate_database_failure()

    # Verify recovery mechanisms
    return self._verify_system_recovery()
```

## Performance Baselines

The integration tests validate specific performance targets:

### Throughput Targets

- **Task Processing**: >10 tasks/second for simple tasks
- **Event Publishing**: >50 events/second
- **Database Operations**: >100 operations/second
- **Concurrent Processing**: 3-5x improvement over sequential

### Latency Targets

- **End-to-End Workflow**: <60 seconds for complex plans
- **Task Assignment**: <5 seconds from queue to worker
- **Event Propagation**: <1 second across components
- **Database Queries**: <100ms for standard operations

### Scalability Targets

- **Concurrent Tasks**: Handle 50+ simultaneous tasks
- **Event Volume**: Process 1000+ events without degradation
- **Database Load**: Maintain performance under 10+ concurrent connections
- **Memory Usage**: Stable memory usage under sustained load

## Troubleshooting

### Common Issues

#### Test Database Connection Errors
```bash
# Check database permissions
ls -la /tmp/hive_integration_test_*

# Verify test isolation
echo $HIVE_TEST_MODE
```

#### Import Path Issues
```bash
# Verify PYTHONPATH
echo $PYTHONPATH

# Check module structure
find apps/ -name "__init__.py" | head -10
```

#### Performance Test Failures
```bash
# Check system resources
htop
df -h

# Run with verbose output
python scripts/run_integration_tests.py --mode perf --verbose
```

#### Mock Service Issues
```bash
# Check mock service logs
grep -r "mock" /tmp/hive_integration_test_*

# Verify test data
sqlite3 /tmp/hive_integration_test_*/test_hive.db ".tables"
```

### Debug Mode

Enable debug mode for detailed test execution:

```bash
export HIVE_TEST_DEBUG=true
python scripts/run_integration_tests.py --mode quick --verbose
```

This provides:
- Detailed SQL query logs
- Mock service interaction logs
- Performance timing breakdowns
- Memory usage tracking

## Contributing

### Adding New Tests

1. **Create Test Method**: Add to appropriate test class
2. **Update Test Runner**: Add to relevant test mode
3. **Document Test**: Update this documentation
4. **Add CI Integration**: Update GitHub Actions workflow

### Test Development Guidelines

1. **Isolation**: Each test must be completely isolated
2. **Determinism**: Tests must produce consistent results
3. **Performance**: Tests should complete within reasonable time
4. **Documentation**: Each test should have clear purpose and coverage
5. **Error Handling**: Tests must handle all failure scenarios gracefully

### Example New Test

```python
def test_new_integration_scenario(self) -> bool:
    """Test new integration scenario"""
    print("\n🧪 Testing New Integration Scenario...")

    try:
        # Setup test data
        test_id = self._create_test_scenario()

        # Execute scenario
        result = self._execute_scenario(test_id)

        # Verify results
        verification = self._verify_scenario_results(test_id)

        success = result and verification

        print(f"✅ New integration scenario test: {'PASSED' if success else 'FAILED'}")
        return success

    except Exception as e:
        self.env.metrics.errors_encountered.append(f"New scenario: {str(e)}")
        print(f"❌ New integration scenario test failed: {e}")
        return False
```

## Continuous Improvement

The integration testing suite is continuously improved based on:

- **Production Issues**: Tests added for bugs found in production
- **Performance Regressions**: Benchmarks updated for new performance targets
- **Architecture Changes**: Tests updated for new architectural patterns
- **User Feedback**: Tests added for user-reported integration issues

Regular review and updates ensure the test suite remains effective at catching issues before they reach production.
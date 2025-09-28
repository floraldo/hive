# Test Organization

This test directory follows a standardized structure:

## Directory Structure

- **`unit/`**: Unit tests that test individual functions/classes in isolation
  - Fast execution (<100ms per test)
  - No external dependencies (database, network, file system)
  - Heavy use of mocks and stubs

- **`integration/`**: Integration tests that test multiple components together
  - May use real databases or services
  - Tests component interactions
  - Slower than unit tests but faster than E2E

- **`e2e/`**: End-to-end tests that test complete user workflows
  - Tests the full stack
  - May use browser automation or API clients
  - Slowest but most comprehensive

## Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest unit/

# Run only integration tests
pytest integration/

# Run only E2E tests
pytest e2e/

# Run with coverage
pytest --cov=. --cov-report=html
```

## Test Naming Convention

- Test files: `test_<module>.py` or `<module>_test.py`
- Test classes: `Test<Feature>`
- Test methods: `test_<what_it_tests>`

## Adding New Tests

1. Determine the appropriate category (unit/integration/e2e)
2. Create your test file in the correct subdirectory
3. Follow existing patterns and conventions
4. Ensure tests are independent and reproducible

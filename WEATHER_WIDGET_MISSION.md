# Weather Widget Mission - First Production Test

## Mission Overview
Build a full-stack Weather Widget application that demonstrates the complete Hive v2 architecture, TDD protocol, and shared package system.

## Success Criteria
✅ **TDD Protocol**: All development follows RED→GREEN→REFACTOR cycle
✅ **Shared Package Integration**: Backend uses `hive-common` utilities
✅ **Token Vault Security**: API key accessed via `hivemind.config.tokens`
✅ **Full-Stack Integration**: React frontend → Flask API → OpenWeatherMap API
✅ **Docker Deployment**: Application runs in containerized environment
✅ **CI/CD Pipeline**: All tests pass in GitHub Actions

## Architecture Design

### Shared Package (hive-common)
```
packages/hive-common/hive_common/weather.py
- WeatherClient class
- Uses APIClient base class
- Accesses vault.OPENWEATHER_API_KEY
- Handles OpenWeatherMap API integration
```

### Backend API (Worker1-Backend)
```
apps/backend/app.py
- /api/weather?city=<name> endpoint
- Uses WeatherClient from hive-common
- Input validation and error handling
- pytest test coverage
```

### Frontend Component (Worker2-Frontend)
```
apps/frontend/src/components/WeatherWidget.js
- City input form
- Weather display component
- API integration with backend
- Jest/Testing Library tests
```

## Mission Command

When you're ready to test the complete system, give the Queen this exact command:

```
Build a Weather Widget application following TDD protocol with shared package integration
```

## Expected TDD Workflow

### Phase 1: Shared Package (RED→GREEN→REFACTOR)
1. **RED**: Create failing tests in `packages/hive-common/tests/test_weather.py`
2. **GREEN**: Implement `WeatherClient` class to make tests pass
3. **REFACTOR**: Optimize error handling and response parsing

### Phase 2: Backend API (RED→GREEN→REFACTOR)
1. **RED**: Create failing tests in `apps/backend/tests/test_weather_api.py`
2. **GREEN**: Implement Flask endpoint using `WeatherClient`
3. **REFACTOR**: Add proper validation and error handling

### Phase 3: Frontend Component (RED→GREEN→REFACTOR)
1. **RED**: Create failing React component tests
2. **GREEN**: Implement weather widget component
3. **REFACTOR**: Improve UX with loading states

### Phase 4: Integration Testing
1. Full-stack end-to-end testing
2. Docker deployment validation
3. CI/CD pipeline verification

## Pre-Mission Checklist

Before starting the mission, ensure:

- [ ] **OPENWEATHER_API_KEY** is set in environment
  - Run `setup_api_key.bat` to configure
  - Get free key from https://openweathermap.org/api
  
- [ ] **WSL Environment** is ready (for full tmux experience)
  - Follow `WSL_SETUP_GUIDE.md`
  - Or use Windows-only development mode

- [ ] **Agent Configuration** is complete
  - `.claude/CLAUDE.md` contains Hive Protocol ✅
  - Git worktrees are set up ✅
  - Directory structure is complete ✅

## Execution Options

### Option 1: Full Swarm Mode (Recommended)
```bash
# Terminal 1 (WSL)
make swarm

# Terminal 2 (WSL)  
make run
```

### Option 2: Windows Direct Development
Use this Claude Code instance to implement the mission directly:
1. Work in the worktree directories
2. Follow the TDD protocol manually
3. Test with `make docker-up`

### Option 3: Hybrid Approach
- Use this instance for development
- Use Docker for testing and deployment
- Manual coordination between components

## Validation Commands

```bash
# Test token vault access
python -c "from hivemind.config.tokens import vault; print('API Key:', vault.OPENWEATHER_API_KEY[:10] + '...' if vault.OPENWEATHER_API_KEY else 'Not set')"

# Run setup verification
python test_setup_simple.py

# Test Docker deployment
make docker-up

# Run all tests
pytest packages/hive-common/tests/ apps/backend/tests/
```

## Expected Outcomes

Upon successful completion:
1. **Functional Weather Widget**: Users can input city and get weather data
2. **Test Coverage**: >80% code coverage across all components  
3. **Security Compliance**: No hardcoded API keys, proper error handling
4. **Architecture Validation**: Shared package system proven effective
5. **Deployment Ready**: Application runs successfully in Docker

This mission will definitively prove that your Hive v2 architecture is not just theoretically sound, but practically exceptional.
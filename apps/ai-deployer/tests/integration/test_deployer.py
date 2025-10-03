"""
Tests for the deployment orchestrator
"""

from unittest.mock import AsyncMock, Mock

import pytest

from ai_deployer.deployer import DeploymentOrchestrator, DeploymentStrategy, HealthStatus


@pytest.fixture
def mock_strategies():
    """Create mock deployment strategies"""
    strategies = {}
    for strategy in DeploymentStrategy:
        mock_strategy = Mock()
        mock_strategy.strategy = strategy
        mock_strategy.pre_deployment_checks = AsyncMock(return_value={"success": True, "errors": []})
        mock_strategy.deploy = AsyncMock(return_value={"success": True, "metrics": {}})
        mock_strategy.post_deployment_actions = AsyncMock()
        mock_strategy.rollback = AsyncMock(return_value={"success": True})
        strategies[strategy] = mock_strategy
    return strategies


@pytest.fixture
def sample_task():
    """Create a sample deployment task"""
    return {
        "id": "task-deploy-001",
        "app_name": "test-app",
        "deployment_strategy": "direct",
        "source_path": "/tmp/app",
        "ssh_config": {"hostname": "test.example.com", "username": "deploy"},
        "environment": {"platform": "linux", "has_load_balancer": False},
    }


class TestDeploymentOrchestrator:
    """Test cases for the deployment orchestrator"""

    def test_orchestrator_initialization(self):
        """Test orchestrator initialization"""
        config = {"timeout": 300, "max_retries": 3}
        orchestrator = DeploymentOrchestrator(config)

        assert orchestrator.config == config
        assert orchestrator.default_strategy == DeploymentStrategy.DIRECT
        assert len(orchestrator.strategies) == 4  # All strategy types

    def test_select_strategy_from_task(self):
        """Test strategy selection from task configuration"""
        orchestrator = DeploymentOrchestrator()

        # Test direct strategy
        task = ({"deployment_strategy": "direct"},)
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.DIRECT

        # Test blue-green strategy
        task = ({"deployment_strategy": "blue-green"},)
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.BLUE_GREEN

        # Test unknown strategy defaults to direct
        task = ({"deployment_strategy": "unknown"},)
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.DIRECT

    def test_select_strategy_default(self):
        """Test default strategy selection"""
        orchestrator = (DeploymentOrchestrator(),)

        task = {}  # No strategy specified,
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.DIRECT

    def test_validate_strategy_compatibility_blue_green(self):
        """Test blue-green strategy compatibility"""
        orchestrator = DeploymentOrchestrator()

        # Blue-green requires load balancer
        task_with_lb = {"environment": {"has_load_balancer": True}}
        assert orchestrator._validate_strategy_compatibility(DeploymentStrategy.BLUE_GREEN, task_with_lb)

        # Blue-green without load balancer should fail
        task_without_lb = {"environment": {"has_load_balancer": False}}
        assert not orchestrator._validate_strategy_compatibility(DeploymentStrategy.BLUE_GREEN, task_without_lb)

    def test_validate_strategy_compatibility_canary(self):
        """Test canary strategy compatibility"""
        orchestrator = DeploymentOrchestrator()

        # Canary requires Kubernetes
        task_k8s = {"environment": {"platform": "kubernetes"}}
        assert orchestrator._validate_strategy_compatibility(DeploymentStrategy.CANARY, task_k8s)

        # Canary without Kubernetes should fail
        task_no_k8s = {"environment": {"platform": "linux"}}
        assert not orchestrator._validate_strategy_compatibility(DeploymentStrategy.CANARY, task_no_k8s)

    def test_validate_strategy_compatibility_direct_always_valid(self):
        """Test direct strategy is always compatible"""
        orchestrator = DeploymentOrchestrator()

        # Direct strategy should work with any environment
        task_empty = {"environment": {}}
        assert orchestrator._validate_strategy_compatibility(DeploymentStrategy.DIRECT, task_empty)

        task_any = {"environment": {"platform": "anything"}}
        assert orchestrator._validate_strategy_compatibility(DeploymentStrategy.DIRECT, task_any)

    @pytest.mark.asyncio
    async def test_deploy_success_async(self, mock_strategies, sample_task):
        """Test successful deployment"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.strategies = mock_strategies

        # Mock validation methods
        orchestrator._validate_deployment = AsyncMock(return_value=True)

        result = await orchestrator.deploy(sample_task)

        assert result.success is True
        assert result.strategy == DeploymentStrategy.DIRECT
        assert result.deployment_id is not None

        # Verify strategy was called
        strategy = mock_strategies[DeploymentStrategy.DIRECT]
        strategy.pre_deployment_checks.assert_called_once()
        strategy.deploy.assert_called_once()
        strategy.post_deployment_actions.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_pre_check_failure_async(self, mock_strategies, sample_task):
        """Test deployment with pre-check failure"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.strategies = mock_strategies

        # Configure pre-checks to fail
        strategy = mock_strategies[DeploymentStrategy.DIRECT]
        strategy.pre_deployment_checks.return_value = {"success": False, "errors": ["SSH connection failed"]}

        result = await orchestrator.deploy(sample_task)

        assert result.success is False
        assert "Pre-deployment checks failed" in result.error
        assert result.rollback_attempted is True

    @pytest.mark.asyncio
    async def test_deploy_strategy_failure_with_rollback_async(self, mock_strategies, sample_task):
        """Test deployment strategy failure with successful rollback"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.strategies = mock_strategies
        orchestrator._attempt_rollback = AsyncMock(return_value=True)

        # Configure strategy to fail
        strategy = mock_strategies[DeploymentStrategy.DIRECT]
        strategy.deploy.return_value = {"success": False, "error": "Deployment failed"}

        result = await orchestrator.deploy(sample_task)

        assert result.success is False
        assert result.rollback_attempted is True
        assert result.metrics["rollback_success"] is True

    @pytest.mark.asyncio
    async def test_deploy_incompatible_strategy_fallback_async(self, mock_strategies, sample_task):
        """Test fallback to direct strategy for incompatible strategy"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.strategies = mock_strategies

        # Request blue-green but no load balancer
        sample_task["deployment_strategy"] = "blue-green"
        sample_task["environment"] = {"has_load_balancer": False}

        orchestrator._validate_deployment = AsyncMock(return_value=True)

        result = await orchestrator.deploy(sample_task)

        # Should fall back to direct strategy
        assert result.success is True
        assert result.strategy == DeploymentStrategy.DIRECT

    @pytest.mark.asyncio
    async def test_execute_deployment_async(self, mock_strategies, sample_task):
        """Test deployment execution"""
        orchestrator = (DeploymentOrchestrator(),)

        strategy_impl = mock_strategies[DeploymentStrategy.DIRECT]
        strategy_impl.deploy.return_value = {
            "success": True,
            "metrics": {"files_deployed": 15, "deployment_time": 45.2},
        }

        result = await orchestrator._execute_deployment(strategy_impl, sample_task, "deploy-123")

        assert result.success is True
        assert result.deployment_id == "deploy-123"
        assert result.metrics["files_deployed"] == 15

    @pytest.mark.asyncio
    async def test_validate_deployment_healthy_async(self, sample_task):
        """Test deployment validation with healthy status"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.check_health = AsyncMock(return_value=HealthStatus(healthy=True, message="All checks passed"))

        result = await orchestrator._validate_deployment(sample_task, "deploy-123")
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_deployment_unhealthy_async(self, sample_task):
        """Test deployment validation with unhealthy status"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.check_health = AsyncMock(
            return_value=HealthStatus(healthy=False, message="Service not responding"),
        )

        result = await orchestrator._validate_deployment(sample_task, "deploy-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_deployment_with_smoke_tests_async(self, sample_task):
        """Test deployment validation with smoke tests"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.check_health = AsyncMock(return_value=HealthStatus(healthy=True))
        orchestrator._run_smoke_tests = AsyncMock(return_value=True)

        # Enable smoke tests
        sample_task["run_smoke_tests"] = True

        result = await orchestrator._validate_deployment(sample_task, "deploy-123")
        assert result is True

        orchestrator._run_smoke_tests.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_deployment_smoke_test_failure_async(self, sample_task):
        """Test deployment validation with smoke test failure"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.check_health = AsyncMock(return_value=HealthStatus(healthy=True))
        orchestrator._run_smoke_tests = AsyncMock(return_value=False)

        sample_task["run_smoke_tests"] = True

        result = await orchestrator._validate_deployment(sample_task, "deploy-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_attempt_rollback_success_async(self, mock_strategies, sample_task):
        """Test successful rollback"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.strategies = mock_strategies

        previous_deployment = {"deployment_info": {"version": "1.2.3", "image": "app:1.2.3"}}

        result = await orchestrator._attempt_rollback(sample_task, "deploy-456", previous_deployment)

        assert result is True

    @pytest.mark.asyncio
    async def test_attempt_rollback_no_previous_info_async(self, sample_task):
        """Test rollback with no previous deployment info"""
        orchestrator = (DeploymentOrchestrator(),)

        previous_deployment = {}  # No previous info,

        result = await orchestrator._attempt_rollback(sample_task, "deploy-456", previous_deployment)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_health_all_healthy_async(self, sample_task):
        """Test health check with all systems healthy"""
        orchestrator = DeploymentOrchestrator()
        orchestrator._check_endpoint = AsyncMock(return_value=True)
        orchestrator._check_dependency = AsyncMock(return_value=True)

        # Add health dependencies
        sample_task["health_dependencies"] = [
            {"name": "database", "url": "db.example.com"},
            {"name": "cache", "url": "cache.example.com"},
        ]

        health_status = await orchestrator.check_health(sample_task)

        assert health_status.healthy is True
        assert health_status.message == "All health checks passed"
        assert health_status.checks["application"] is True
        assert health_status.checks["database"] is True
        assert health_status.checks["cache"] is True

    @pytest.mark.asyncio
    async def test_check_health_some_failing_async(self, sample_task):
        """Test health check with some systems failing"""
        orchestrator = DeploymentOrchestrator()
        orchestrator._check_endpoint = AsyncMock(return_value=True)
        orchestrator._check_dependency = AsyncMock(side_effect=[True, False])

        sample_task["health_dependencies"] = [
            {"name": "database", "url": "db.example.com"},
            {"name": "cache", "url": "cache.example.com"},
        ]

        health_status = await orchestrator.check_health(sample_task)

        assert health_status.healthy is False
        assert health_status.message == "Some health checks failed"
        assert health_status.checks["application"] is True
        assert health_status.checks["database"] is True
        assert health_status.checks["cache"] is False

    @pytest.mark.asyncio
    async def test_check_health_exception_handling_async(self, sample_task):
        """Test health check with exception"""
        orchestrator = DeploymentOrchestrator()
        orchestrator._check_endpoint = AsyncMock(side_effect=Exception("Connection error"))

        health_status = await orchestrator.check_health(sample_task)

        assert health_status.healthy is False
        assert "Health check error" in health_status.message

    @pytest.mark.asyncio
    async def test_check_endpoint_placeholder_async(self, sample_task):
        """Test endpoint check placeholder implementation"""
        orchestrator = DeploymentOrchestrator()

        # Should return True (placeholder implementation)
        result = await orchestrator._check_endpoint(sample_task, "/health")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_dependency_placeholder_async(self):
        """Test dependency check placeholder implementation"""
        orchestrator = (DeploymentOrchestrator(),)

        dependency = {"name": "test", "url": "test.example.com"}

        # Should return True (placeholder implementation)
        result = await orchestrator._check_dependency(dependency)
        assert result is True

    @pytest.mark.asyncio
    async def test_run_smoke_tests_placeholder_async(self, sample_task):
        """Test smoke tests placeholder implementation"""
        orchestrator = DeploymentOrchestrator()

        # Should return True (placeholder implementation)
        result = await orchestrator._run_smoke_tests(sample_task)
        assert result is True

"""
Tests for the AI Deployer autonomous agent
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from ai_deployer.agent import DeploymentAgent
from ai_deployer.database_adapter import DatabaseAdapter
from ai_deployer.deployer import (
    DeploymentOrchestrator,
    DeploymentResult,
    DeploymentStrategy,
)


@pytest.fixture
def mock_db():
    """Create a mock database"""
    return Mock()


@pytest.fixture
def mock_orchestrator():
    """Create a mock deployment orchestrator"""
    orchestrator = Mock(spec=DeploymentOrchestrator)

    # Create a default successful deployment result
    result = DeploymentResult(
        success=True,
        strategy=DeploymentStrategy.DIRECT,
        deployment_id="test-deploy-001",
        metrics={"deployment_time": 10.5, "files_deployed": 25},
    )

    orchestrator.deploy = AsyncMock(return_value=result)
    orchestrator.check_health = AsyncMock(
        return_value=Mock(healthy=True, message="All systems healthy")
    )

    return orchestrator


@pytest.fixture
def mock_adapter():
    """Create a mock database adapter"""
    adapter = Mock(spec=DatabaseAdapter)
    adapter.get_deployment_pending_tasks.return_value = []
    adapter.update_task_status.return_value = True
    return adapter


@pytest.fixture
def sample_task():
    """Create a sample deployment task"""
    return {
        "id": "task-001",
        "title": "Deploy Web Application",
        "description": "Deploy the main web application to production",
        "status": "deployment_pending",
        "app_name": "web-app",
        "source_path": "/tmp/app-source",
        "ssh_config": {
            "hostname": "deploy.example.com",
            "username": "deploy",
            "key_file": "/path/to/key",
        },
        "deployment_strategy": "direct",
        "priority": 1,
        "metadata": {"environment": "production"},
    }


class TestDeploymentAgent:
    """Test cases for the deployment agent"""

    def test_agent_initialization(self, mock_orchestrator):
        """Test agent initialization"""
        agent = DeploymentAgent(
            orchestrator=mock_orchestrator,
            polling_interval=60,
            test_mode=True,
        )

        assert agent.orchestrator == mock_orchestrator
        assert agent.polling_interval == 5  # test_mode reduces interval
        assert agent.test_mode is True
        assert agent.running is False
        assert agent.stats["tasks_deployed"] == 0

    @pytest.mark.asyncio
    async def test_get_pending_tasks_with_async_db(self):
        """Test getting pending tasks with async database"""
        with patch("ai_deployer.agent.ASYNC_DB_AVAILABLE", True), patch(
            "ai_deployer.agent.get_tasks_by_status_async"
        ) as mock_get_tasks:

            mock_tasks = [{"id": "task-1", "status": "deployment_pending"}]
            mock_get_tasks.return_value = mock_tasks

            agent = DeploymentAgent(test_mode=True)
            tasks = await agent._get_pending_tasks()

            assert tasks == mock_tasks
            mock_get_tasks.assert_called_once_with("deployment_pending")

    @pytest.mark.asyncio
    async def test_get_pending_tasks_fallback_sync(self, mock_adapter):
        """Test falling back to sync database operations"""
        with patch("ai_deployer.agent.ASYNC_DB_AVAILABLE", False):
            agent = DeploymentAgent(test_mode=True)
            agent.adapter = mock_adapter

            mock_tasks = [{"id": "task-2", "status": "deployment_pending"}]
            mock_adapter.get_deployment_pending_tasks.return_value = mock_tasks

            tasks = await agent._get_pending_tasks()

            assert tasks == mock_tasks
            mock_adapter.get_deployment_pending_tasks.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_task_success(self, mock_orchestrator, sample_task):
        """Test successful task processing"""
        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)

        # Mock the update_task_status method
        agent._update_task_status = AsyncMock()
        agent._trigger_monitoring = AsyncMock()

        await agent._process_task(sample_task)

        # Verify deployment was attempted
        mock_orchestrator.deploy.assert_called_once_with(sample_task)

        # Verify status updates
        agent._update_task_status.assert_any_call("task-001", "deploying")
        agent._update_task_status.assert_any_call("task-001", "deployed")

        # Verify monitoring was triggered
        agent._trigger_monitoring.assert_called_once_with(sample_task)

        # Verify stats updated
        assert agent.stats["tasks_deployed"] == 1
        assert agent.stats["successful"] == 1

    @pytest.mark.asyncio
    async def test_process_task_deployment_failure(
        self, mock_orchestrator, sample_task
    ):
        """Test task processing with deployment failure"""
        # Configure orchestrator to return failure
        failed_result = DeploymentResult(
            success=False,
            strategy=DeploymentStrategy.DIRECT,
            deployment_id="test-deploy-002",
            error="SSH connection failed",
            rollback_attempted=False,
        )
        mock_orchestrator.deploy.return_value = failed_result

        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)
        agent._update_task_status = AsyncMock()

        await agent._process_task(sample_task)

        # Verify status updated to failed
        agent._update_task_status.assert_any_call("task-001", "deployment_failed")

        # Verify stats updated
        assert agent.stats["tasks_deployed"] == 1
        assert agent.stats["failed"] == 1
        assert agent.stats["successful"] == 0

    @pytest.mark.asyncio
    async def test_process_task_with_rollback(self, mock_orchestrator, sample_task):
        """Test task processing with rollback"""
        # Configure orchestrator to return failure with rollback
        failed_result = DeploymentResult(
            success=False,
            strategy=DeploymentStrategy.DIRECT,
            deployment_id="test-deploy-003",
            error="Health check failed",
            rollback_attempted=True,
        )
        mock_orchestrator.deploy.return_value = failed_result

        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)
        agent._update_task_status = AsyncMock()

        await agent._process_task(sample_task)

        # Verify status updated to rolled back
        agent._update_task_status.assert_any_call("task-001", "rolled_back")

        # Verify stats updated
        assert agent.stats["tasks_deployed"] == 1
        assert agent.stats["rolled_back"] == 1

    @pytest.mark.asyncio
    async def test_process_task_exception_handling(
        self, mock_orchestrator, sample_task
    ):
        """Test task processing with exception"""
        # Configure orchestrator to raise exception
        mock_orchestrator.deploy.side_effect = Exception("Unexpected error")

        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)
        agent._update_task_status = AsyncMock()

        await agent._process_task(sample_task)

        # Verify status updated to failed
        agent._update_task_status.assert_any_call("task-001", "deployment_failed")

        # Verify error stats updated
        assert agent.stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_update_task_status_async(self):
        """Test updating task status with async operations"""
        with patch("ai_deployer.agent.ASYNC_DB_AVAILABLE", True), patch(
            "ai_deployer.agent.update_task_status_async"
        ) as mock_update:

            agent = DeploymentAgent(test_mode=True)

            await agent._update_task_status(
                "task-001", "deployed", {"deployment_id": "deploy-123"}
            )

            mock_update.assert_called_once_with(
                "task-001", "deployed", {"deployment_id": "deploy-123"}
            )

    @pytest.mark.asyncio
    async def test_update_task_status_sync_fallback(self, mock_adapter):
        """Test updating task status with sync fallback"""
        with patch("ai_deployer.agent.ASYNC_DB_AVAILABLE", False):
            agent = DeploymentAgent(test_mode=True)
            agent.adapter = mock_adapter

            await agent._update_task_status("task-001", "deployed")

            mock_adapter.update_task_status.assert_called_once_with(
                "task-001", "deployed", None
            )

    @pytest.mark.asyncio
    async def test_trigger_monitoring_healthy(self, mock_orchestrator, sample_task):
        """Test post-deployment monitoring with healthy status"""
        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)

        # Health check returns healthy
        mock_orchestrator.check_health.return_value = Mock(
            healthy=True, message="All checks passed"
        )

        await agent._trigger_monitoring(sample_task)

        # Verify health check was called
        mock_orchestrator.check_health.assert_called_once_with(sample_task)

    @pytest.mark.asyncio
    async def test_trigger_monitoring_unhealthy(self, mock_orchestrator, sample_task):
        """Test post-deployment monitoring with unhealthy status"""
        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)

        # Health check returns unhealthy
        mock_orchestrator.check_health.return_value = Mock(
            healthy=False, message="Service not responding"
        )

        # Should not raise exception, just log warning
        await agent._trigger_monitoring(sample_task)

        mock_orchestrator.check_health.assert_called_once_with(sample_task)

    def test_handle_shutdown(self):
        """Test graceful shutdown handling"""
        agent = DeploymentAgent(test_mode=True)
        agent.running = True

        # Simulate SIGTERM
        agent._handle_shutdown(15, None)

        assert agent.running is False

    def test_create_status_panel(self):
        """Test status panel creation"""
        agent = DeploymentAgent(test_mode=True)
        agent.running = True
        agent.stats["start_time"] = datetime.now()
        agent.stats["tasks_deployed"] = 10
        agent.stats["successful"] = 8
        agent.stats["failed"] = 1
        agent.stats["rolled_back"] = 1

        panel = agent._create_status_panel()

        assert panel.title == "[bold blue]AI Deployment Agent[/bold blue]"
        # Panel should contain status information

    @pytest.mark.asyncio
    async def test_event_bus_integration(self, mock_orchestrator, sample_task):
        """Test event bus integration for deployment events"""
        with patch("ai_deployer.agent.get_event_bus") as mock_get_bus, patch(
            "ai_deployer.agent.create_task_event"
        ) as mock_create_event:

            mock_bus = Mock()
            mock_get_bus.return_value = mock_bus
            mock_event = Mock()
            mock_create_event.return_value = mock_event

            agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)
            agent._update_task_status = AsyncMock()
            agent._trigger_monitoring = AsyncMock()

            await agent._process_task(sample_task)

            # Verify event was published
            mock_bus.publish.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_main_loop_single_iteration(self, mock_orchestrator):
        """Test a single iteration of the main agent loop"""
        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)

        # Mock methods to control loop
        agent._get_pending_tasks = AsyncMock(return_value=[])
        agent.running = True

        # Run one iteration
        with patch("asyncio.sleep") as mock_sleep:
            # Make sleep break the loop
            mock_sleep.side_effect = lambda x: setattr(agent, "running", False)

            try:
                await agent.run()
            except AttributeError:
                # Expected when mocking signal handlers
                pass

        # Verify pending tasks were checked
        agent._get_pending_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_main_function():
    """Test the main function entry point"""
    with patch("ai_deployer.agent.DeploymentAgent") as mock_agent_class, patch(
        "ai_deployer.agent.asyncio.run"
    ) as mock_run, patch("sys.argv", ["agent.py", "--test-mode"]):

        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent

        # Import and call main (avoiding actual execution)
        from ai_deployer.agent import main

        try:
            main()
        except SystemExit:
            pass  # Expected for argument parsing

        # Verify agent was created with test mode
        mock_agent_class.assert_called_with(
            polling_interval=30,
            test_mode=True,
        )

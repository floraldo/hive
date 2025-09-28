"""
Integration tests for the complete AI Deployer system
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from ai_deployer import DatabaseAdapter, DeploymentAgent, DeploymentOrchestrator
from ai_deployer.deployer import DeploymentResult, DeploymentStrategy


@pytest.fixture
def sample_integration_task():
    """Create a comprehensive task for integration testing"""
    return {
        "id": "integration-task-001",
        "title": "Deploy Web Application",
        "description": "Full integration test deployment",
        "status": "deployment_pending",
        "app_name": "test-web-app",
        "source_path": "/tmp/test-app",
        "deployment_strategy": "direct",
        "ssh_config": {
            "hostname": "test-deploy.example.com",
            "username": "deploy",
            "key_file": "/tmp/test-key.pem",
        },
        "environment": {
            "platform": "linux",
            "has_load_balancer": False,
        },
        "health_endpoint": "/health",
        "priority": 1,
        "metadata": {"environment": "test"},
    }


class TestDeploymentIntegration:
    """Integration tests for the complete deployment system"""

    @pytest.mark.asyncio
    async def test_full_deployment_workflow_success_async(self, sample_integration_task):
        """Test complete successful deployment workflow"""
        # Create real orchestrator with mocked strategies
        orchestrator = DeploymentOrchestrator()

        # Mock the SSH strategy
        mock_ssh_strategy = Mock()
        mock_ssh_strategy.strategy = DeploymentStrategy.DIRECT
        mock_ssh_strategy.pre_deployment_checks = AsyncMock(return_value={"success": True, "errors": []})
        mock_ssh_strategy.deploy = AsyncMock(
            return_value={
                "success": True,
                "metrics": {"deployment_time": 30.5, "files_deployed": 42},
            }
        )
        mock_ssh_strategy.post_deployment_actions = AsyncMock()

        orchestrator.strategies[DeploymentStrategy.DIRECT] = mock_ssh_strategy

        # Mock validation and health checks
        orchestrator._validate_deployment = AsyncMock(return_value=True)
        orchestrator.check_health = AsyncMock(return_value=Mock(healthy=True, message="All systems healthy"))

        # Execute deployment
        result = await orchestrator.deploy(sample_integration_task)

        # Verify successful deployment
        assert result.success is True
        assert result.strategy == DeploymentStrategy.DIRECT
        assert result.deployment_id is not None
        assert result.metrics["deployment_time"] == 30.5
        assert result.metrics["files_deployed"] == 42

        # Verify all strategy methods were called
        mock_ssh_strategy.pre_deployment_checks.assert_called_once()
        mock_ssh_strategy.deploy.assert_called_once()
        mock_ssh_strategy.post_deployment_actions.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_deployment_workflow_with_rollback_async(self, sample_integration_task):
        """Test deployment workflow with failure and rollback"""
        orchestrator = DeploymentOrchestrator()

        # Mock the SSH strategy to fail deployment
        mock_ssh_strategy = Mock()
        mock_ssh_strategy.strategy = DeploymentStrategy.DIRECT
        mock_ssh_strategy.pre_deployment_checks = AsyncMock(return_value={"success": True, "errors": []})
        mock_ssh_strategy.deploy = AsyncMock(return_value={"success": False, "error": "Service startup failed"})
        mock_ssh_strategy.rollback = AsyncMock(
            return_value={"success": True, "rollback_info": {"backup_restored": True}}
        )

        orchestrator.strategies[DeploymentStrategy.DIRECT] = mock_ssh_strategy

        # Add previous deployment info for rollback
        sample_integration_task["previous_deployment"] = {"deployment_info": {"backup_id": "backup-123"}}

        # Execute deployment
        result = await orchestrator.deploy(sample_integration_task)

        # Verify failed deployment with successful rollback
        assert result.success is False
        assert result.rollback_attempted is True
        assert result.metrics["rollback_success"] is True
        assert "Service startup failed" in result.error

        # Verify rollback was attempted
        mock_ssh_strategy.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_orchestrator_integration_async(self, sample_integration_task):
        """Test integration between agent and orchestrator"""
        # Create mock database adapter
        mock_adapter = Mock(spec=DatabaseAdapter)
        mock_adapter.get_deployment_pending_tasks.return_value = [sample_integration_task]
        mock_adapter.update_task_status.return_value = True

        # Create mock orchestrator
        mock_orchestrator = Mock(spec=DeploymentOrchestrator)
        mock_orchestrator.deploy = AsyncMock(
            return_value=DeploymentResult(
                success=True,
                strategy=DeploymentStrategy.DIRECT,
                deployment_id="test-deploy-123",
                metrics={"deployment_time": 25.0},
            )
        )
        mock_orchestrator.check_health = AsyncMock(return_value=Mock(healthy=True, message="Healthy"))

        # Create agent with mocked components
        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)
        agent.adapter = mock_adapter

        # Mock status update methods
        agent._update_task_status = AsyncMock()
        agent._trigger_monitoring = AsyncMock()

        # Simulate single task processing
        await agent._process_task(sample_integration_task)

        # Verify orchestrator was called
        mock_orchestrator.deploy.assert_called_once_with(sample_integration_task)

        # Verify status updates
        agent._update_task_status.assert_any_call("integration-task-001", "deploying")
        agent._update_task_status.assert_any_call("integration-task-001", "deployed")

        # Verify monitoring was triggered
        agent._trigger_monitoring.assert_called_once()

        # Verify agent stats
        assert agent.stats["tasks_deployed"] == 1
        assert agent.stats["successful"] == 1

    @pytest.mark.asyncio
    async def test_database_adapter_integration_async(self):
        """Test database adapter integration with mocked database"""
        with patch("ai_deployer.database_adapter.get_pooled_connection") as mock_get_conn:
            # Setup mock connection and cursor
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_get_conn.return_value = mock_conn

            # Mock database responses
            mock_cursor.fetchall.return_value = [
                [
                    "test-task-001",
                    "Test Task",
                    "Test deployment",
                    "2024-01-15T10:00:00",
                    "2024-01-15T10:30:00",
                    "worker-001",
                    1,
                    '{"source_path": "/tmp/app"}',
                    '{"env": "test"}',
                    "deployment_pending",
                    1800,
                ]
            ]
            mock_cursor.rowcount = 1

            # Test adapter operations
            adapter = DatabaseAdapter()

            # Get pending tasks
            tasks = adapter.get_deployment_pending_tasks()
            assert len(tasks) == 1
            assert tasks[0]["id"] == "test-task-001"
            assert tasks[0]["status"] == "deployment_pending"

            # Update task status
            result = adapter.update_task_status("test-task-001", "deployed")
            assert result is True

            # Record deployment event
            event_result = adapter.record_deployment_event(
                "test-task-001",
                "deployment_completed",
                {"duration": 30.5, "success": True},
            )
            assert event_result is True

            # Verify database calls
            assert mock_cursor.execute.call_count >= 3

    @pytest.mark.asyncio
    async def test_strategy_selection_integration_async(self):
        """Test strategy selection logic integration"""
        orchestrator = DeploymentOrchestrator()

        # Test direct strategy selection
        task = {"deployment_strategy": "direct", "environment": {}}
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.DIRECT

        # Test blue-green strategy with compatible environment
        task = {
            "deployment_strategy": "blue-green",
            "environment": {"has_load_balancer": True},
        }
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.BLUE_GREEN

        # Test blue-green strategy with incompatible environment (should fallback)
        task = {
            "deployment_strategy": "blue-green",
            "environment": {"has_load_balancer": False},
        }
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.DIRECT

        # Test canary strategy with Kubernetes
        task = {
            "deployment_strategy": "canary",
            "environment": {"platform": "kubernetes"},
        }
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.CANARY

    @pytest.mark.asyncio
    async def test_health_check_integration_async(self):
        """Test health check integration across components"""
        orchestrator = DeploymentOrchestrator()

        # Mock health check methods
        orchestrator._check_endpoint = AsyncMock(return_value=True)
        orchestrator._check_dependency = AsyncMock(return_value=True)

        task = {
            "health_endpoint": "/api/health",
            "health_dependencies": [
                {"name": "database", "url": "db.test.com"},
                {"name": "cache", "url": "cache.test.com"},
            ],
        }

        health_status = await orchestrator.check_health(task)

        assert health_status.healthy is True
        assert health_status.message == "All health checks passed"
        assert health_status.checks["application"] is True
        assert health_status.checks["database"] is True
        assert health_status.checks["cache"] is True

        # Verify all checks were called
        orchestrator._check_endpoint.assert_called_once()
        assert orchestrator._check_dependency.call_count == 2

    @pytest.mark.asyncio
    async def test_event_bus_integration_async(self, sample_integration_task):
        """Test event bus integration for deployment notifications"""
        with patch("ai_deployer.agent.get_event_bus") as mock_get_bus, patch(
            "ai_deployer.agent.create_task_event"
        ) as mock_create_event:
            # Setup event bus mocks
            mock_bus = Mock()
            mock_get_bus.return_value = mock_bus
            mock_event = Mock()
            mock_create_event.return_value = mock_event

            # Create agent with event bus
            agent = DeploymentAgent(test_mode=True)

            # Mock successful deployment
            mock_orchestrator = Mock()
            mock_orchestrator.deploy = AsyncMock(
                return_value=DeploymentResult(
                    success=True,
                    strategy=DeploymentStrategy.DIRECT,
                    deployment_id="event-test-123",
                )
            )
            mock_orchestrator.check_health = AsyncMock(return_value=Mock(healthy=True))
            agent.orchestrator = mock_orchestrator

            # Mock status updates
            agent._update_task_status = AsyncMock()
            agent._trigger_monitoring = AsyncMock()

            # Process task
            await agent._process_task(sample_integration_task)

            # Verify event was created and published
            mock_create_event.assert_called_once()
            mock_bus.publish.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_error_handling_integration_async(self, sample_integration_task):
        """Test error handling integration across components"""
        # Create orchestrator that raises exception
        orchestrator = DeploymentOrchestrator()
        orchestrator.deploy = AsyncMock(side_effect=Exception("Critical deployment error"))

        # Create agent
        agent = DeploymentAgent(orchestrator=orchestrator, test_mode=True)
        agent._update_task_status = AsyncMock()

        # Process task with error
        await agent._process_task(sample_integration_task)

        # Verify error handling
        agent._update_task_status.assert_any_call("integration-task-001", "deployment_failed")
        assert agent.stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_deployment_handling_async(self):
        """Test handling multiple concurrent deployments"""
        # Create multiple tasks
        tasks = [
            {
                "id": f"concurrent-task-{i}",
                "app_name": f"app-{i}",
                "deployment_strategy": "direct",
                "ssh_config": {"hostname": f"host{i}.example.com"},
                "source_path": f"/tmp/app-{i}",
            }
            for i in range(3)
        ]

        # Mock orchestrator for concurrent deployments
        mock_orchestrator = Mock()

        # Create different results for each deployment
        async def mock_deploy_async(task):
            task_id = task["id"]
            await asyncio.sleep(0.1)  # Simulate deployment time
            return DeploymentResult(
                success=True,
                strategy=DeploymentStrategy.DIRECT,
                deployment_id=f"deploy-{task_id}",
            )

        mock_orchestrator.deploy = mock_deploy
        mock_orchestrator.check_health = AsyncMock(return_value=Mock(healthy=True))

        # Create agent
        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)
        agent._update_task_status = AsyncMock()
        agent._trigger_monitoring = AsyncMock()

        # Process all tasks concurrently
        deployment_tasks = [agent._process_task(task) for task in tasks]
        await asyncio.gather(*deployment_tasks)

        # Verify all deployments were processed
        assert agent.stats["tasks_deployed"] == 3
        assert agent.stats["successful"] == 3
        assert agent.stats["failed"] == 0

        # Verify status updates for all tasks
        assert agent._update_task_status.call_count == 6  # 2 calls per task

    @pytest.mark.asyncio
    async def test_deployment_metrics_collection_async(self, sample_integration_task):
        """Test deployment metrics collection integration"""
        orchestrator = DeploymentOrchestrator()

        # Mock strategy with detailed metrics
        mock_strategy = Mock()
        mock_strategy.strategy = DeploymentStrategy.DIRECT
        mock_strategy.pre_deployment_checks = AsyncMock(return_value={"success": True, "errors": []})
        mock_strategy.deploy = AsyncMock(
            return_value={
                "success": True,
                "metrics": {
                    "deployment_time": 45.7,
                    "files_deployed": 128,
                    "bytes_transferred": 1024 * 1024 * 5,  # 5MB
                    "services_restarted": 3,
                },
            }
        )
        mock_strategy.post_deployment_actions = AsyncMock()

        orchestrator.strategies[DeploymentStrategy.DIRECT] = mock_strategy
        orchestrator._validate_deployment = AsyncMock(return_value=True)

        # Execute deployment
        result = await orchestrator.deploy(sample_integration_task)

        # Verify metrics are preserved
        assert result.success is True
        assert result.metrics["deployment_time"] == 45.7
        assert result.metrics["files_deployed"] == 128
        assert result.metrics["bytes_transferred"] == 1024 * 1024 * 5
        assert result.metrics["services_restarted"] == 3

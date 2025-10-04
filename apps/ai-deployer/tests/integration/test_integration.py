"""
Integration tests for the complete AI Deployer system
"""
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import pytest
from ai_deployer import DatabaseAdapter, DeploymentAgent, DeploymentOrchestrator
from ai_deployer.deployer import DeploymentResult, DeploymentStrategy

@pytest.fixture
def sample_integration_task():
    """Create a comprehensive task for integration testing"""
    return {'id': 'integration-task-001', 'title': 'Deploy Web Application', 'description': 'Full integration test deployment', 'status': 'deployment_pending', 'app_name': 'test-web-app', 'source_path': '/tmp/test-app', 'deployment_strategy': 'direct', 'ssh_config': {'hostname': 'test-deploy.example.com', 'username': 'deploy', 'key_file': '/tmp/test-key.pem'}, 'environment': {'platform': 'linux', 'has_load_balancer': False}, 'health_endpoint': '/health', 'priority': 1, 'metadata': {'environment': 'test'}}

@pytest.mark.crust
class TestDeploymentIntegration:
    """Integration tests for the complete deployment system"""

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_full_deployment_workflow_success_async(self, sample_integration_task):
        """Test complete successful deployment workflow"""
        orchestrator = DeploymentOrchestrator()
        mock_ssh_strategy = Mock()
        mock_ssh_strategy.strategy = DeploymentStrategy.DIRECT
        mock_ssh_strategy.pre_deployment_checks = AsyncMock(return_value={'success': True, 'errors': []})
        mock_ssh_strategy.deploy = AsyncMock(return_value={'success': True, 'metrics': {'deployment_time': 30.5, 'files_deployed': 42}})
        mock_ssh_strategy.post_deployment_actions = AsyncMock()
        orchestrator.strategies[DeploymentStrategy.DIRECT] = mock_ssh_strategy
        orchestrator._validate_deployment = AsyncMock(return_value=True)
        orchestrator.check_health = AsyncMock(return_value=Mock(healthy=True, message='All systems healthy'))
        result = await orchestrator.deploy(sample_integration_task)
        assert result.success is True
        assert result.strategy == DeploymentStrategy.DIRECT
        assert result.deployment_id is not None
        assert result.metrics['deployment_time'] == 30.5
        assert result.metrics['files_deployed'] == 42
        mock_ssh_strategy.pre_deployment_checks.assert_called_once()
        mock_ssh_strategy.deploy.assert_called_once()
        mock_ssh_strategy.post_deployment_actions.assert_called_once()

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_full_deployment_workflow_with_rollback_async(self, sample_integration_task):
        """Test deployment workflow with failure and rollback"""
        orchestrator = DeploymentOrchestrator()
        mock_ssh_strategy = Mock()
        mock_ssh_strategy.strategy = DeploymentStrategy.DIRECT
        mock_ssh_strategy.pre_deployment_checks = AsyncMock(return_value={'success': True, 'errors': []})
        mock_ssh_strategy.deploy = AsyncMock(return_value={'success': False, 'error': 'Service startup failed'})
        mock_ssh_strategy.rollback = AsyncMock(return_value={'success': True, 'rollback_info': {'backup_restored': True}})
        orchestrator.strategies[DeploymentStrategy.DIRECT] = mock_ssh_strategy
        sample_integration_task['previous_deployment'] = {'deployment_info': {'backup_id': 'backup-123'}}
        result = await orchestrator.deploy(sample_integration_task)
        assert result.success is False
        assert result.rollback_attempted is True
        assert result.metrics['rollback_success'] is True
        assert 'Service startup failed' in result.error
        mock_ssh_strategy.rollback.assert_called_once()

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_agent_orchestrator_integration_async(self, sample_integration_task):
        """Test integration between agent and orchestrator"""
        mock_adapter = Mock(spec=DatabaseAdapter)
        mock_adapter.get_deployment_pending_tasks.return_value = [sample_integration_task]
        mock_adapter.update_task_status.return_value = True
        mock_orchestrator = Mock(spec=DeploymentOrchestrator)
        mock_orchestrator.deploy = AsyncMock(return_value=DeploymentResult(success=True, strategy=DeploymentStrategy.DIRECT, deployment_id='test-deploy-123', metrics={'deployment_time': 25.0}))
        mock_orchestrator.check_health = AsyncMock(return_value=Mock(healthy=True, message='Healthy'))
        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)
        agent.adapter = mock_adapter
        agent._update_task_status = AsyncMock()
        agent._trigger_monitoring = AsyncMock()
        await agent._process_task(sample_integration_task)
        mock_orchestrator.deploy.assert_called_once_with(sample_integration_task)
        agent._update_task_status.assert_any_call('integration-task-001', 'deploying')
        agent._update_task_status.assert_any_call('integration-task-001', 'deployed')
        agent._trigger_monitoring.assert_called_once()
        assert agent.stats['tasks_deployed'] == 1
        assert agent.stats['successful'] == 1

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_database_adapter_integration_async(self):
        """Test database adapter integration with mocked database"""
        with patch('ai_deployer.database_adapter.get_pooled_connection') as mock_get_conn:
            mock_conn = (Mock(),)
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_get_conn.return_value = mock_conn
            mock_cursor.fetchall.return_value = [['test-task-001', 'Test Task', 'Test deployment', '2024-01-15T10:00:00', '2024-01-15T10:30:00', 'worker-001', 1, '{"source_path": "/tmp/app"}', '{"env": "test"}', 'deployment_pending', 1800]]
            mock_cursor.rowcount = 1
            adapter = DatabaseAdapter()
            tasks = adapter.get_deployment_pending_tasks()
            assert len(tasks) == 1
            assert tasks[0]['id'] == 'test-task-001'
            assert tasks[0]['status'] == 'deployment_pending'
            result = adapter.update_task_status('test-task-001', 'deployed')
            assert result is True
            event_result = adapter.record_deployment_event('test-task-001', 'deployment_completed', {'duration': 30.5, 'success': True})
            assert event_result is True
            assert mock_cursor.execute.call_count >= 3

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_strategy_selection_integration_async(self):
        """Test strategy selection logic integration"""
        orchestrator = DeploymentOrchestrator()
        task = {'deployment_strategy': 'direct', 'environment': {}}
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.DIRECT
        task = {'deployment_strategy': 'blue-green', 'environment': {'has_load_balancer': True}}
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.BLUE_GREEN
        task = {'deployment_strategy': 'blue-green', 'environment': {'has_load_balancer': False}}
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.DIRECT
        task = {'deployment_strategy': 'canary', 'environment': {'platform': 'kubernetes'}}
        strategy = orchestrator._select_strategy(task)
        assert strategy == DeploymentStrategy.CANARY

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_health_check_integration_async(self):
        """Test health check integration across components"""
        orchestrator = DeploymentOrchestrator()
        orchestrator._check_endpoint = AsyncMock(return_value=True)
        orchestrator._check_dependency = AsyncMock(return_value=True)
        task = {'health_endpoint': '/api/health', 'health_dependencies': [{'name': 'database', 'url': 'db.test.com'}, {'name': 'cache', 'url': 'cache.test.com'}]}
        health_status = await orchestrator.check_health(task)
        assert health_status.healthy is True
        assert health_status.message == 'All health checks passed'
        assert health_status.checks['application'] is True
        assert health_status.checks['database'] is True
        assert health_status.checks['cache'] is True
        orchestrator._check_endpoint.assert_called_once()
        assert orchestrator._check_dependency.call_count == 2

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_event_bus_integration_async(self, sample_integration_task):
        """Test event bus integration for deployment notifications"""
        with patch('ai_deployer.agent.get_event_bus') as mock_get_bus, patch('ai_deployer.agent.create_task_event') as mock_create_event:
            mock_bus = Mock()
            mock_get_bus.return_value = mock_bus
            mock_event = Mock()
            mock_create_event.return_value = mock_event
            agent = DeploymentAgent(test_mode=True)
            mock_orchestrator = Mock()
            mock_orchestrator.deploy = AsyncMock(return_value=DeploymentResult(success=True, strategy=DeploymentStrategy.DIRECT, deployment_id='event-test-123'))
            mock_orchestrator.check_health = AsyncMock(return_value=Mock(healthy=True))
            agent.orchestrator = mock_orchestrator
            agent._update_task_status = AsyncMock()
            agent._trigger_monitoring = AsyncMock()
            await agent._process_task(sample_integration_task)
            mock_create_event.assert_called_once()
            mock_bus.publish.assert_called_once_with(mock_event)

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_error_handling_integration_async(self, sample_integration_task):
        """Test error handling integration across components"""
        orchestrator = DeploymentOrchestrator()
        orchestrator.deploy = AsyncMock(side_effect=Exception('Critical deployment error'))
        agent = DeploymentAgent(orchestrator=orchestrator, test_mode=True)
        agent._update_task_status = AsyncMock()
        await agent._process_task(sample_integration_task)
        agent._update_task_status.assert_any_call('integration-task-001', 'deployment_failed')
        assert agent.stats['errors'] == 1

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_concurrent_deployment_handling_async(self):
        """Test handling multiple concurrent deployments"""
        tasks = [{'id': f'concurrent-task-{i}', 'app_name': f'app-{i}', 'deployment_strategy': 'direct', 'ssh_config': {'hostname': f'host{i}.example.com'}, 'source_path': f'/tmp/app-{i}'} for i in range(3)]
        mock_orchestrator = Mock()

        async def mock_deploy_async(task):
            task_id = task['id']
            await asyncio.sleep(0.1)
            return DeploymentResult(success=True, strategy=DeploymentStrategy.DIRECT, deployment_id=f'deploy-{task_id}')
        mock_orchestrator.deploy = mock_deploy
        mock_orchestrator.check_health = AsyncMock(return_value=Mock(healthy=True))
        agent = DeploymentAgent(orchestrator=mock_orchestrator, test_mode=True)
        agent._update_task_status = AsyncMock()
        agent._trigger_monitoring = AsyncMock()
        deployment_tasks = [agent._process_task(task) for task in tasks]
        await asyncio.gather(*deployment_tasks)
        assert agent.stats['tasks_deployed'] == 3
        assert agent.stats['successful'] == 3
        assert agent.stats['failed'] == 0
        assert agent._update_task_status.call_count == 6

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deployment_metrics_collection_async(self, sample_integration_task):
        """Test deployment metrics collection integration"""
        orchestrator = DeploymentOrchestrator()
        mock_strategy = Mock()
        mock_strategy.strategy = DeploymentStrategy.DIRECT
        mock_strategy.pre_deployment_checks = AsyncMock(return_value={'success': True, 'errors': []})
        mock_strategy.deploy = AsyncMock(return_value={'success': True, 'metrics': {'deployment_time': 45.7, 'files_deployed': 128, 'bytes_transferred': 1024 * 1024 * 5, 'services_restarted': 3}})
        mock_strategy.post_deployment_actions = AsyncMock()
        orchestrator.strategies[DeploymentStrategy.DIRECT] = mock_strategy
        orchestrator._validate_deployment = AsyncMock(return_value=True)
        result = await orchestrator.deploy(sample_integration_task)
        assert result.success is True
        assert result.metrics['deployment_time'] == 45.7
        assert result.metrics['files_deployed'] == 128
        assert result.metrics['bytes_transferred'] == 1024 * 1024 * 5
        assert result.metrics['services_restarted'] == 3
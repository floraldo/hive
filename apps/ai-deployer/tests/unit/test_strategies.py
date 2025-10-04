"""
Tests for deployment strategies
"""
from unittest.mock import Mock, patch

import pytest

from ai_deployer.deployer import DeploymentStrategy
from ai_deployer.strategies.docker import DockerDeploymentStrategy
from ai_deployer.strategies.kubernetes import KubernetesDeploymentStrategy
from ai_deployer.strategies.ssh import SSHDeploymentStrategy


@pytest.fixture
def ssh_task():
    """Create a sample SSH deployment task"""
    return {'id': 'ssh-task-001', 'app_name': 'web-app', 'source_path': '/tmp/app-source', 'ssh_config': {'hostname': 'deploy.example.com', 'username': 'deploy', 'key_file': '/path/to/key.pem'}, 'deployment_strategy': 'direct'}

@pytest.fixture
def docker_task():
    """Create a sample Docker deployment task"""
    return {'id': 'docker-task-001', 'app_name': 'web-app', 'docker_image': {'name': 'web-app', 'tag': 'latest', 'build_context': '/tmp/app'}, 'container_config': {'ports': {'80': '8080'}, 'environment': {'ENV': 'production'}}}

@pytest.fixture
def k8s_task():
    """Create a sample Kubernetes deployment task"""
    return {'id': 'k8s-task-001', 'app_name': 'web-app', 'k8s_namespace': 'production', 'k8s_manifests': {'deployment': 'deployment.yaml', 'service': 'service.yaml', 'ingress': 'ingress.yaml'}, 'docker_image': {'name': 'web-app', 'tag': 'v1.0.0'}}

@pytest.mark.crust
class TestSSHDeploymentStrategy:
    """Test cases for SSH deployment strategy"""

    @pytest.mark.crust
    def test_initialization(self):
        """Test SSH strategy initialization"""
        config = ({'timeout': 300},)
        strategy = SSHDeploymentStrategy(config)
        assert strategy.config == config
        assert strategy.strategy == DeploymentStrategy.DIRECT

    @pytest.mark.crust
    def test_get_required_task_fields(self):
        """Test required fields for SSH deployment"""
        strategy = (SSHDeploymentStrategy({}),)
        fields = (strategy.get_required_task_fields(),)
        expected_fields = ['ssh_config', 'app_name', 'source_path']
        assert all(field in fields for field in expected_fields)

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_validate_configuration_async(self, ssh_task):
        """Test SSH task configuration validation"""
        strategy = SSHDeploymentStrategy({})
        assert await strategy.validate_configuration(ssh_task)
        incomplete_task = ssh_task.copy()
        del incomplete_task['ssh_config']
        assert not await strategy.validate_configuration(incomplete_task)

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_pre_deployment_checks_success_async(self, ssh_task):
        """Test successful pre-deployment checks"""
        strategy = SSHDeploymentStrategy({})
        with patch.object(strategy, 'validate_configuration', return_value=True), patch.object(strategy, '_check_ssh_connectivity', return_value=True), patch.object(strategy, '_check_remote_permissions', return_value=True), patch('pathlib.Path.exists', return_value=True):
            result = await strategy.pre_deployment_checks(ssh_task)
            assert result['success'] is True
            assert len(result['errors']) == 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_pre_deployment_checks_ssh_failure_async(self, ssh_task):
        """Test pre-deployment checks with SSH connectivity failure"""
        strategy = SSHDeploymentStrategy({})
        with patch.object(strategy, 'validate_configuration', return_value=True), patch.object(strategy, '_check_ssh_connectivity', return_value=False):
            result = await strategy.pre_deployment_checks(ssh_task)
            assert result['success'] is False
            assert any('SSH connectivity check failed' in error for error in result['errors'])

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_pre_deployment_checks_missing_source_async(self, ssh_task):
        """Test pre-deployment checks with missing source path"""
        strategy = SSHDeploymentStrategy({})
        with patch.object(strategy, 'validate_configuration', return_value=True), patch.object(strategy, '_check_ssh_connectivity', return_value=True), patch('pathlib.Path.exists', return_value=False):
            result = await strategy.pre_deployment_checks(ssh_task)
            assert result['success'] is False
            assert any('Source path does not exist' in error for error in result['errors'])

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deploy_success_async(self, ssh_task):
        """Test successful SSH deployment"""
        strategy = (SSHDeploymentStrategy({}),)
        mock_ssh_client = Mock()
        mock_ssh_client.close = Mock()
        with patch.object(strategy, '_connect_to_server', return_value=mock_ssh_client), patch.object(strategy, '_create_backup', return_value={'backup_id': 'backup-123'}), patch.object(strategy, '_deploy_application', return_value={'success': True, 'files_count': 25}), patch.object(strategy, '_manage_services', return_value=True), patch('ai_deployer.strategies.ssh.determine_deployment_paths', return_value={'remote_app_dir': '/apps/web-app'}):
            result = await strategy.deploy(ssh_task, 'deploy-123')
            assert result['success'] is True
            assert result['metrics']['files_deployed'] == 25
            assert 'backup' in result['deployment_info']
            mock_ssh_client.close.assert_called_once()

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deploy_ssh_connection_failure_async(self, ssh_task):
        """Test SSH deployment with connection failure"""
        strategy = SSHDeploymentStrategy({})
        with patch.object(strategy, '_connect_to_server', return_value=None):
            result = await strategy.deploy(ssh_task, 'deploy-123')
            assert result['success'] is False
            assert 'Failed to establish SSH connection' in result['error']

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deploy_service_start_failure_async(self, ssh_task):
        """Test SSH deployment with service start failure"""
        strategy = (SSHDeploymentStrategy({}),)
        mock_ssh_client = Mock()
        mock_ssh_client.close = Mock()
        with patch.object(strategy, '_connect_to_server', return_value=mock_ssh_client), patch.object(strategy, '_create_backup', return_value={'backup_id': 'backup-123'}), patch.object(strategy, '_deploy_application', return_value={'success': True}), patch.object(strategy, '_manage_services', return_value=False), patch('ai_deployer.strategies.ssh.determine_deployment_paths', return_value={}):
            result = await strategy.deploy(ssh_task, 'deploy-123')
            assert result['success'] is False
            assert 'failed to start services' in result['error']

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_rollback_success_async(self, ssh_task):
        """Test successful SSH rollback"""
        strategy = (SSHDeploymentStrategy({}),)
        mock_ssh_client = Mock()
        mock_ssh_client.close = Mock()
        previous_deployment = {'backup': {'backup_id': 'backup-123', 'backup_path': '/tmp/backup'}}
        with patch.object(strategy, '_connect_to_server', return_value=mock_ssh_client), patch.object(strategy, '_restore_from_backup', return_value=True), patch.object(strategy, '_manage_services', return_value=True):
            result = await strategy.rollback(ssh_task, 'deploy-456', previous_deployment)
            assert result['success'] is True
            assert result['rollback_info']['restored_from']['backup_id'] == 'backup-123'

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_rollback_no_backup_info_async(self, ssh_task):
        """Test rollback with no backup information"""
        strategy = (SSHDeploymentStrategy({}),)
        previous_deployment = {}
        result = await strategy.rollback(ssh_task, 'deploy-456', previous_deployment)
        assert result['success'] is False
        assert 'No backup available for rollback' in result['error']

@pytest.mark.crust
class TestDockerDeploymentStrategy:
    """Test cases for Docker deployment strategy"""

    @pytest.mark.crust
    def test_initialization(self):
        """Test Docker strategy initialization"""
        config = ({'registry': 'docker.io'},)
        strategy = DockerDeploymentStrategy(config)
        assert strategy.config == config
        assert strategy.strategy == DeploymentStrategy.ROLLING

    @pytest.mark.crust
    def test_get_required_task_fields(self):
        """Test required fields for Docker deployment"""
        strategy = (DockerDeploymentStrategy({}),)
        fields = (strategy.get_required_task_fields(),)
        expected_fields = ['docker_image', 'container_config']
        assert all(field in fields for field in expected_fields)

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_pre_deployment_checks_success_async(self, docker_task):
        """Test successful Docker pre-deployment checks"""
        strategy = DockerDeploymentStrategy({})
        with patch.object(strategy, 'validate_configuration', return_value=True), patch.object(strategy, '_check_docker_daemon', return_value=True), patch.object(strategy, '_validate_docker_image', return_value=True):
            result = await strategy.pre_deployment_checks(docker_task)
            assert result['success'] is True
            assert len(result['errors']) == 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_pre_deployment_checks_docker_unavailable_async(self, docker_task):
        """Test Docker pre-deployment checks with Docker daemon unavailable"""
        strategy = DockerDeploymentStrategy({})
        with patch.object(strategy, 'validate_configuration', return_value=True), patch.object(strategy, '_check_docker_daemon', return_value=False):
            result = await strategy.pre_deployment_checks(docker_task)
            assert result['success'] is False
            assert any('Docker daemon not accessible' in error for error in result['errors'])

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deploy_success_async(self, docker_task):
        """Test successful Docker deployment"""
        strategy = DockerDeploymentStrategy({})
        with patch.object(strategy, '_prepare_docker_image', return_value={'success': True, 'image_name': 'web-app:deploy-123'}), patch.object(strategy, '_stop_existing_containers', return_value=True), patch.object(strategy, '_run_container', return_value={'success': True, 'container_id': 'container-123'}), patch.object(strategy, '_wait_for_container_health', return_value=True), patch.object(strategy, '_update_load_balancer', return_value=True):
            result = await strategy.deploy(docker_task, 'deploy-123')
            assert result['success'] is True
            assert result['deployment_info']['image_name'] == 'web-app:deploy-123'
            assert result['deployment_info']['container_id'] == 'container-123'

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deploy_image_preparation_failure_async(self, docker_task):
        """Test Docker deployment with image preparation failure"""
        strategy = DockerDeploymentStrategy({})
        with patch.object(strategy, '_prepare_docker_image', return_value={'success': False, 'error': 'Image build failed'}):
            result = await strategy.deploy(docker_task, 'deploy-123')
            assert result['success'] is False
            assert 'Image preparation failed' in result['error']

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deploy_container_health_failure_async(self, docker_task):
        """Test Docker deployment with container health check failure"""
        strategy = DockerDeploymentStrategy({})
        with patch.object(strategy, '_prepare_docker_image', return_value={'success': True, 'image_name': 'web-app:deploy-123'}), patch.object(strategy, '_stop_existing_containers', return_value=True), patch.object(strategy, '_run_container', return_value={'success': True, 'container_id': 'container-123'}), patch.object(strategy, '_wait_for_container_health', return_value=False), patch.object(strategy, '_stop_container', return_value=True):
            result = await strategy.deploy(docker_task, 'deploy-123')
            assert result['success'] is False
            assert 'Container failed health check' in result['error']

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_rollback_success_async(self, docker_task):
        """Test successful Docker rollback"""
        strategy = (DockerDeploymentStrategy({}),)
        previous_deployment = {'deployment_info': {'image_name': 'web-app:previous', 'container_id': 'old-container'}}
        with patch.object(strategy, '_stop_container', return_value=True), patch.object(strategy, '_run_container', return_value={'success': True, 'container_id': 'rollback-container'}), patch.object(strategy, '_wait_for_container_health', return_value=True), patch.object(strategy, '_update_load_balancer', return_value=True):
            result = await strategy.rollback(docker_task, 'deploy-456', previous_deployment)
            assert result['success'] is True
            assert result['rollback_info']['rolled_back_to_image'] == 'web-app:previous'

@pytest.mark.crust
class TestKubernetesDeploymentStrategy:
    """Test cases for Kubernetes deployment strategy"""

    @pytest.mark.crust
    def test_initialization(self):
        """Test Kubernetes strategy initialization"""
        config = ({'kubeconfig': '/path/to/kubeconfig'},)
        strategy = KubernetesDeploymentStrategy(config)
        assert strategy.config == config
        assert strategy.strategy == DeploymentStrategy.CANARY

    @pytest.mark.crust
    def test_get_required_task_fields(self):
        """Test required fields for Kubernetes deployment"""
        strategy = (KubernetesDeploymentStrategy({}),)
        fields = (strategy.get_required_task_fields(),)
        expected_fields = ['k8s_manifests', 'app_name']
        assert all(field in fields for field in expected_fields)

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_pre_deployment_checks_success_async(self, k8s_task):
        """Test successful Kubernetes pre-deployment checks"""
        strategy = KubernetesDeploymentStrategy({})
        with patch.object(strategy, 'validate_configuration', return_value=True), patch.object(strategy, '_check_cluster_connectivity', return_value=True), patch.object(strategy, '_validate_manifests', return_value=True), patch.object(strategy, '_check_namespace_access', return_value=True), patch.object(strategy, '_check_image_access', return_value=True):
            result = await strategy.pre_deployment_checks(k8s_task)
            assert result['success'] is True
            assert len(result['errors']) == 0

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_pre_deployment_checks_cluster_unavailable_async(self, k8s_task):
        """Test Kubernetes pre-deployment checks with cluster unavailable"""
        strategy = KubernetesDeploymentStrategy({})
        with patch.object(strategy, 'validate_configuration', return_value=True), patch.object(strategy, '_check_cluster_connectivity', return_value=False):
            result = await strategy.pre_deployment_checks(k8s_task)
            assert result['success'] is False
            assert any('Kubernetes cluster not accessible' in error for error in result['errors'])

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_pre_deployment_checks_namespace_access_denied_async(self, k8s_task):
        """Test Kubernetes pre-deployment checks with namespace access denied"""
        strategy = KubernetesDeploymentStrategy({})
        with patch.object(strategy, 'validate_configuration', return_value=True), patch.object(strategy, '_check_cluster_connectivity', return_value=True), patch.object(strategy, '_validate_manifests', return_value=True), patch.object(strategy, '_check_namespace_access', return_value=False):
            result = await strategy.pre_deployment_checks(k8s_task)
            assert result['success'] is False
            assert any('No access to namespace: production' in error for error in result['errors'])

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deploy_success_async(self, k8s_task):
        """Test successful Kubernetes deployment"""
        strategy = KubernetesDeploymentStrategy({})
        with patch.object(strategy, '_apply_manifests', return_value={'success': True, 'pods_count': 3}), patch.object(strategy, '_wait_for_deployment_ready', return_value=True), patch.object(strategy, '_execute_canary_deployment', return_value={'success': True}), patch.object(strategy, '_update_ingress', return_value=True), patch.object(strategy, '_wait_for_health_checks', return_value=True):
            result = await strategy.deploy(k8s_task, 'deploy-123')
            assert result['success'] is True
            assert result['deployment_info']['namespace'] == 'production'
            assert result['deployment_info']['app_name'] == 'web-app'
            assert result['metrics']['pods_deployed'] == 3

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deploy_manifest_application_failure_async(self, k8s_task):
        """Test Kubernetes deployment with manifest application failure"""
        strategy = KubernetesDeploymentStrategy({})
        with patch.object(strategy, '_apply_manifests', return_value={'success': False, 'error': 'Invalid manifest'}):
            result = await strategy.deploy(k8s_task, 'deploy-123')
            assert result['success'] is False
            assert 'Manifest application failed' in result['error']

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_deploy_canary_failure_async(self, k8s_task):
        """Test Kubernetes deployment with canary failure"""
        strategy = KubernetesDeploymentStrategy({})
        with patch.object(strategy, '_apply_manifests', return_value={'success': True}), patch.object(strategy, '_wait_for_deployment_ready', return_value=True), patch.object(strategy, '_execute_canary_deployment', return_value={'success': False, 'error': 'Canary metrics failed'}), patch.object(strategy, '_cleanup_failed_deployment', return_value=None):
            result = await strategy.deploy(k8s_task, 'deploy-123')
            assert result['success'] is False
            assert 'Canary deployment failed' in result['error']

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_rollback_success_async(self, k8s_task):
        """Test successful Kubernetes rollback"""
        strategy = (KubernetesDeploymentStrategy({}),)
        previous_deployment = {'deployment_info': {'manifests_applied': ['deployment.yaml', 'service.yaml']}}
        with patch.object(strategy, '_rollback_deployment', return_value=True), patch.object(strategy, '_wait_for_deployment_ready', return_value=True), patch.object(strategy, '_wait_for_health_checks', return_value=True):
            result = await strategy.rollback(k8s_task, 'deploy-456', previous_deployment)
            assert result['success'] is True
            assert result['rollback_info']['rollback_method'] == 'kubectl_rollout'

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_rollback_with_manual_fallback_async(self, k8s_task):
        """Test Kubernetes rollback with manual fallback"""
        strategy = (KubernetesDeploymentStrategy({}),)
        previous_deployment = {'deployment_info': {'manifests_applied': ['deployment.yaml', 'service.yaml']}}
        with patch.object(strategy, '_rollback_deployment', return_value=False), patch.object(strategy, '_apply_previous_manifests', return_value=True), patch.object(strategy, '_wait_for_deployment_ready', return_value=True), patch.object(strategy, '_wait_for_health_checks', return_value=True):
            result = await strategy.rollback(k8s_task, 'deploy-456', previous_deployment)
            assert result['success'] is True
            assert result['rollback_info']['rollback_method'] == 'manifest_reapply'

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_execute_canary_deployment_async(self, k8s_task):
        """Test canary deployment execution"""
        strategy = KubernetesDeploymentStrategy({})
        with patch.object(strategy, '_deploy_canary_version', return_value=None), patch.object(strategy, '_monitor_canary_metrics', return_value=True), patch.object(strategy, '_gradually_increase_traffic', return_value=True):
            result = await strategy._execute_canary_deployment(k8s_task, 'deploy-123')
            assert result['success'] is True
            assert result['canary_info']['traffic_migrated'] is True

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_execute_canary_deployment_metrics_failure_async(self, k8s_task):
        """Test canary deployment with metrics failure"""
        strategy = KubernetesDeploymentStrategy({})
        with patch.object(strategy, '_deploy_canary_version', return_value=None), patch.object(strategy, '_monitor_canary_metrics', return_value=False):
            result = await strategy._execute_canary_deployment(k8s_task, 'deploy-123')
            assert result['success'] is False
            assert 'Canary metrics indicate failure' in result['error']

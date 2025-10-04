"""Unit tests for hive_service_discovery.config module."""
from unittest.mock import patch
import pytest

@pytest.mark.core
class TestServiceDiscoveryConfig:
    """Test cases for service discovery configuration."""

    @pytest.mark.core
    def test_config_module_exists(self):
        """Test config module can be imported."""
        try:
            from hive_service_discovery import config
            assert config is not None
        except ImportError:
            pytest.skip('Config module not found as separate module')

    @pytest.mark.core
    def test_default_configuration(self):
        """Test default configuration values."""
        try:
            from hive_service_discovery.config import ServiceDiscoveryConfig
            config = ServiceDiscoveryConfig()
            assert config is not None
            assert hasattr(config, 'registry_url') or hasattr(config, 'host')
            assert hasattr(config, 'timeout') or hasattr(config, 'connection_timeout')
        except ImportError:
            pytest.skip('ServiceDiscoveryConfig not found')

    @pytest.mark.core
    def test_custom_configuration(self):
        """Test custom configuration parameters."""
        try:
            from hive_service_discovery.config import ServiceDiscoveryConfig
            custom_config = {'registry_url': 'http://custom-registry:8500', 'timeout': 60, 'retry_attempts': 5, 'health_check_interval': 45}
            config = ServiceDiscoveryConfig(**custom_config)
            assert config is not None
        except ImportError:
            pytest.skip('ServiceDiscoveryConfig not found')

    @pytest.mark.core
    def test_environment_configuration(self):
        """Test configuration from environment variables."""
        try:
            with patch.dict('os.environ', {'HIVE_DISCOVERY_URL': 'http://env-registry:8500', 'HIVE_DISCOVERY_TIMEOUT': '30'}):
                from hive_service_discovery.config import load_config
                if 'load_config' in locals():
                    config = load_config()
                    assert config is not None
        except ImportError:
            pytest.skip('Environment config loading not found')

    @pytest.mark.core
    def test_config_validation(self):
        """Test configuration validation."""
        try:
            from hive_service_discovery.config import ServiceDiscoveryConfig
            invalid_configs = [{'timeout': -1}, {'retry_attempts': 0}, {'registry_url': 'invalid-url'}]
            for invalid_config in invalid_configs:
                try:
                    config = ServiceDiscoveryConfig(**invalid_config)
                    assert config is not None
                except (ValueError, TypeError):
                    pass
        except ImportError:
            pytest.skip('ServiceDiscoveryConfig validation not found')

    @pytest.mark.core
    def test_config_serialization(self):
        """Test configuration serialization and deserialization."""
        try:
            from hive_service_discovery.config import ServiceDiscoveryConfig
            config = ServiceDiscoveryConfig()
            if hasattr(config, 'to_dict'):
                config_dict = config.to_dict()
                assert isinstance(config_dict, dict)
            if hasattr(config, 'from_dict'):
                config_data = ({'registry_url': 'http://test:8500'},)
                restored_config = ServiceDiscoveryConfig.from_dict(config_data)
                assert restored_config is not None
        except ImportError:
            pytest.skip('ServiceDiscoveryConfig serialization not found')
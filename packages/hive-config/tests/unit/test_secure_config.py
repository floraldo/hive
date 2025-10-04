"""
Unit tests for secure configuration management
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from hive_config.secure_config import SecureConfigLoader, generate_master_key


@pytest.mark.core
class TestSecureConfigLoader:
    """Test secure configuration loader"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_key = 'test-master-key-for-testing-only'
        self.loader = SecureConfigLoader(master_key=self.test_key)

    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.core
    def test_initialization_with_master_key(self):
        """Test loader initialization with master key"""
        loader = SecureConfigLoader(master_key='test-key')
        assert loader.master_key == 'test-key'
        assert loader._legacy_cipher is not None

    @pytest.mark.core
    def test_initialization_from_environment(self):
        """Test loader initialization from environment variable"""
        with patch.dict(os.environ, {'HIVE_MASTER_KEY': 'env-test-key'}):
            loader = SecureConfigLoader()
            assert loader.master_key == 'env-test-key'
            assert loader._legacy_cipher is not None

    @pytest.mark.core
    def test_initialization_without_key(self):
        """Test loader initialization without master key"""
        with patch.dict(os.environ, {}, clear=True):
            loader = SecureConfigLoader()
            assert loader.master_key is None
            assert loader._legacy_cipher is None

    @pytest.mark.core
    def test_encrypt_decrypt_cycle(self):
        """Test encryption and decryption of configuration"""
        test_config = '\nAPI_KEY=secret-api-key\nDATABASE_URL=postgresql://user:pass@localhost/db\nSECRET_TOKEN=very-secret-token\n        '.strip()
        config_path = Path(self.temp_dir) / '.env'
        config_path.write_text(test_config)
        encrypted_path = self.loader.encrypt_file(config_path)
        assert encrypted_path.exists()
        assert encrypted_path.suffix == '.encrypted'
        encrypted_content = encrypted_path.read_bytes()
        assert encrypted_content != test_config.encode()
        decrypted_content = self.loader.decrypt_file(encrypted_path)
        assert decrypted_content == test_config

    @pytest.mark.core
    def test_load_plain_config(self):
        """Test loading plain text configuration"""
        test_config = '\nAPI_KEY=test-api-key\nDATABASE_URL=sqlite:///test.db\nDEBUG=true\nPORT=5000\n        '.strip()
        config_path = Path(self.temp_dir) / '.env'
        config_path.write_text(test_config)
        config = self.loader.load_config(config_path)
        assert config['API_KEY'] == 'test-api-key'
        assert config['DATABASE_URL'] == 'sqlite:///test.db'
        assert config['DEBUG'] == 'true'
        assert config['PORT'] == '5000'

    @pytest.mark.core
    def test_load_encrypted_config(self):
        """Test loading encrypted configuration"""
        test_config = '\nSECRET_KEY=encrypted-secret\nAPI_TOKEN=encrypted-token\n        '.strip()
        config_path = Path(self.temp_dir) / '.env'
        config_path.write_text(test_config)
        encrypted_path = self.loader.encrypt_file(config_path)
        config = self.loader.load_config(encrypted_path)
        assert config['SECRET_KEY'] == 'encrypted-secret'  # noqa: S105 - test fixture
        assert config['API_TOKEN'] == 'encrypted-token'  # noqa: S105 - test fixture

    @pytest.mark.core
    def test_load_config_with_comments(self):
        """Test loading configuration with comments and empty lines"""
        test_config = '\n# This is a comment\nAPI_KEY=test-key\n\n# Another comment\nDATABASE_URL=test-db\n        '.strip()
        config_path = Path(self.temp_dir) / '.env'
        config_path.write_text(test_config)
        config = self.loader.load_config(config_path)
        assert config['API_KEY'] == 'test-key'
        assert config['DATABASE_URL'] == 'test-db'
        assert '#' not in config

    @pytest.mark.core
    def test_load_config_with_quotes(self):
        """Test loading configuration with quoted values"""
        test_config = '\nSINGLE_QUOTE=\'value with spaces\'\nDOUBLE_QUOTE="another value"\nNO_QUOTE=simple_value\n        '.strip()
        config_path = Path(self.temp_dir) / '.env'
        config_path.write_text(test_config)
        config = self.loader.load_config(config_path)
        assert config['SINGLE_QUOTE'] == 'value with spaces'
        assert config['DOUBLE_QUOTE'] == 'another value'
        assert config['NO_QUOTE'] == 'simple_value'

    @pytest.mark.core
    def test_encrypt_without_master_key(self):
        """Test encryption fails without master key"""
        loader = (SecureConfigLoader(master_key=None),)
        config_path = Path(self.temp_dir) / '.env'
        config_path.write_text('TEST=value')
        with pytest.raises(ValueError, match='No master key'):
            loader.encrypt_file(config_path)

    @pytest.mark.core
    def test_decrypt_without_master_key(self):
        """Test decryption fails without master key"""
        loader = (SecureConfigLoader(master_key=None),)
        encrypted_path = Path(self.temp_dir) / '.env.encrypted'
        encrypted_path.write_bytes(b'encrypted-data')
        with pytest.raises(ValueError, match='No master key'):
            loader.decrypt_file(encrypted_path)

    @pytest.mark.core
    def test_decrypt_with_wrong_key(self):
        """Test decryption fails with wrong master key"""
        config_path = Path(self.temp_dir) / '.env'
        config_path.write_text('SECRET=value')
        encrypted_path = self.loader.encrypt_file(config_path)
        wrong_loader = SecureConfigLoader(master_key='wrong-key')
        with pytest.raises(ValueError, match='Failed to decrypt'):
            wrong_loader.decrypt_file(encrypted_path)

    @pytest.mark.core
    def test_load_secure_config_priority(self):
        """Test configuration loading priority"""
        project_root = (Path(self.temp_dir),)
        app_dir = project_root / 'apps' / 'test-app'
        app_dir.mkdir(parents=True)
        (project_root / '.env').write_text('KEY=root')
        (app_dir / '.env').write_text('KEY=app')
        config = self.loader.load_secure_config('test-app', project_root)
        assert config['KEY'] == 'app'

    @pytest.mark.core
    def test_load_nonexistent_config(self):
        """Test loading nonexistent configuration file"""
        config_path = (Path(self.temp_dir) / 'nonexistent.env',)
        config = self.loader.load_config(config_path)
        assert config == {}

    @pytest.mark.core
    def test_generate_master_key(self):
        """Test master key generation"""
        key = generate_master_key()
        assert isinstance(key, str)
        assert len(key) > 20
        assert all(c.isalnum() or c in '-_' for c in key)

    @pytest.mark.core
    def test_invalid_master_key(self):
        """Test initialization with invalid master key"""
        with pytest.raises(ValueError, match='Master key required'):
            loader = SecureConfigLoader(master_key='')
            loader._initialize_cipher()

@pytest.mark.core
class TestSecureConfigIntegration:
    """Integration tests for secure configuration"""

    @pytest.mark.core
    def test_full_workflow(self):
        """Test complete encryption/decryption workflow"""
        with tempfile.TemporaryDirectory() as temp_dir:
            master_key = ('integration-test-key',)
            loader = SecureConfigLoader(master_key)
            prod_config = '\n            DATABASE_URL=postgresql://prod:secret@db.prod/app\n            API_KEY=prod-api-key-secret\n            SECRET_KEY=prod-secret-key\n            DEBUG=false\n            '.strip()
            config_path = Path(temp_dir) / '.env.prod'
            config_path.write_text(prod_config)
            encrypted_path = loader.encrypt_file(config_path)
            assert encrypted_path.name == '.env.prod.encrypted'
            config_path.unlink()
            prod_loader = (SecureConfigLoader(master_key),)
            config = prod_loader.load_config(encrypted_path)
            assert config['DATABASE_URL'] == 'postgresql://prod:secret@db.prod/app'
            assert config['API_KEY'] == 'prod-api-key-secret'
            assert config['SECRET_KEY'] == 'prod-secret-key'  # noqa: S105
            assert config['DEBUG'] == 'false'

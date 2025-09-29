"""
Unit tests for secure configuration management
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from hive_config.secure_config import SecureConfigLoader, generate_master_key


class TestSecureConfigLoader:
    """Test secure configuration loader"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_key = "test-master-key-for-testing-only"
        self.loader = SecureConfigLoader(master_key=self.test_key)

    def teardown_method(self):
        """Cleanup test environment"""
        # Clean up temp files
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization_with_master_key(self):
        """Test loader initialization with master key"""
        loader = SecureConfigLoader(master_key="test-key")
        assert loader.master_key == "test-key"
        assert loader._cipher is not None

    def test_initialization_from_environment(self):
        """Test loader initialization from environment variable"""
        with patch.dict(os.environ, {"HIVE_MASTER_KEY": "env-test-key"}):
            loader = SecureConfigLoader()
            assert loader.master_key == "env-test-key"
            assert loader._cipher is not None

    def test_initialization_without_key(self):
        """Test loader initialization without master key"""
        with patch.dict(os.environ, {}, clear=True):
            loader = SecureConfigLoader()
            assert loader.master_key is None
            assert loader._cipher is None

    def test_encrypt_decrypt_cycle(self):
        """Test encryption and decryption of configuration"""
        # Create test config file
        test_config = """
API_KEY=secret-api-key
DATABASE_URL=postgresql://user:pass@localhost/db
SECRET_TOKEN=very-secret-token
        """.strip()

        config_path = Path(self.temp_dir) / ".env"
        config_path.write_text(test_config)

        # Encrypt file
        encrypted_path = self.loader.encrypt_file(config_path)
        assert encrypted_path.exists()
        assert encrypted_path.suffix == ".encrypted"

        # Verify encrypted content is different
        encrypted_content = encrypted_path.read_bytes()
        assert encrypted_content != test_config.encode()

        # Decrypt file
        decrypted_content = self.loader.decrypt_file(encrypted_path)
        assert decrypted_content == test_config

    def test_load_plain_config(self):
        """Test loading plain text configuration"""
        test_config = """
API_KEY=test-api-key
DATABASE_URL=sqlite:///test.db
DEBUG=true
PORT=5000
        """.strip()

        config_path = Path(self.temp_dir) / ".env"
        config_path.write_text(test_config)

        config = self.loader.load_config(config_path)

        assert config["API_KEY"] == "test-api-key"
        assert config["DATABASE_URL"] == "sqlite:///test.db"
        assert config["DEBUG"] == "true"
        assert config["PORT"] == "5000"

    def test_load_encrypted_config(self):
        """Test loading encrypted configuration"""
        test_config = """
SECRET_KEY=encrypted-secret
API_TOKEN=encrypted-token
        """.strip()

        # Create and encrypt config
        config_path = Path(self.temp_dir) / ".env"
        config_path.write_text(test_config)
        encrypted_path = self.loader.encrypt_file(config_path)

        # Load encrypted config
        config = self.loader.load_config(encrypted_path)

        assert config["SECRET_KEY"] == "encrypted-secret"
        assert config["API_TOKEN"] == "encrypted-token"

    def test_load_config_with_comments(self):
        """Test loading configuration with comments and empty lines"""
        test_config = """
# This is a comment
API_KEY=test-key

# Another comment
DATABASE_URL=test-db
        """.strip()

        config_path = Path(self.temp_dir) / ".env"
        config_path.write_text(test_config)

        config = self.loader.load_config(config_path)

        assert config["API_KEY"] == "test-key"
        assert config["DATABASE_URL"] == "test-db"
        assert "#" not in config

    def test_load_config_with_quotes(self):
        """Test loading configuration with quoted values"""
        test_config = """
SINGLE_QUOTE='value with spaces'
DOUBLE_QUOTE="another value"
NO_QUOTE=simple_value
        """.strip()

        config_path = Path(self.temp_dir) / ".env"
        config_path.write_text(test_config)

        config = self.loader.load_config(config_path)

        assert config["SINGLE_QUOTE"] == "value with spaces"
        assert config["DOUBLE_QUOTE"] == "another value"
        assert config["NO_QUOTE"] == "simple_value"

    def test_encrypt_without_master_key(self):
        """Test encryption fails without master key"""
        loader = SecureConfigLoader(master_key=None)
        config_path = Path(self.temp_dir) / ".env"
        config_path.write_text("TEST=value")

        with pytest.raises(ValueError, match="No master key"):
            loader.encrypt_file(config_path)

    def test_decrypt_without_master_key(self):
        """Test decryption fails without master key"""
        loader = SecureConfigLoader(master_key=None)
        encrypted_path = Path(self.temp_dir) / ".env.encrypted"
        encrypted_path.write_bytes(b"encrypted-data")

        with pytest.raises(ValueError, match="No master key"):
            loader.decrypt_file(encrypted_path)

    def test_decrypt_with_wrong_key(self):
        """Test decryption fails with wrong master key"""
        # Encrypt with one key
        config_path = Path(self.temp_dir) / ".env"
        config_path.write_text("SECRET=value")
        encrypted_path = self.loader.encrypt_file(config_path)

        # Try to decrypt with different key
        wrong_loader = SecureConfigLoader(master_key="wrong-key")
        with pytest.raises(ValueError, match="Failed to decrypt"):
            wrong_loader.decrypt_file(encrypted_path)

    def test_load_secure_config_priority(self):
        """Test configuration loading priority"""
        # Create multiple config files
        project_root = Path(self.temp_dir)
        app_dir = project_root / "apps" / "test-app"
        app_dir.mkdir(parents=True)

        # Root .env (lowest priority)
        (project_root / ".env").write_text("KEY=root")

        # App .env (higher priority)
        (app_dir / ".env").write_text("KEY=app")

        # Load config
        config = self.loader.load_secure_config("test-app", project_root)
        assert config["KEY"] == "app"  # App config overrides root

    def test_load_nonexistent_config(self):
        """Test loading nonexistent configuration file"""
        config_path = Path(self.temp_dir) / "nonexistent.env"
        config = self.loader.load_config(config_path)
        assert config == {}

    def test_generate_master_key(self):
        """Test master key generation"""
        with patch("builtins.print") as mock_print:
            key = generate_master_key()

        # Check key format
        assert isinstance(key, str)
        assert len(key) > 20  # Should be reasonably long

        # Check that instructions were printed
        assert mock_print.called
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("Generated master key" in str(call) for call in calls)
        assert any("HIVE_MASTER_KEY" in str(call) for call in calls)

    def test_invalid_master_key(self):
        """Test initialization with invalid master key"""
        with pytest.raises(ValueError, match="Invalid master key"):
            # This should fail during cipher initialization
            loader = SecureConfigLoader(master_key="")
            loader._initialize_cipher()


class TestSecureConfigIntegration:
    """Integration tests for secure configuration"""

    def test_full_workflow(self):
        """Test complete encryption/decryption workflow"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup
            master_key = "integration-test-key"
            loader = SecureConfigLoader(master_key)

            # Create production config
            prod_config = """
            DATABASE_URL=postgresql://prod:secret@db.prod/app
            API_KEY=prod-api-key-secret
            SECRET_KEY=prod-secret-key
            DEBUG=false
            """.strip()

            config_path = Path(temp_dir) / ".env.prod"
            config_path.write_text(prod_config)

            # Encrypt production config
            encrypted_path = loader.encrypt_file(config_path)
            assert encrypted_path.name == ".env.prod.encrypted"

            # Delete original (simulate production)
            config_path.unlink()

            # Load encrypted config in "production"
            prod_loader = SecureConfigLoader(master_key)
            config = prod_loader.load_config(encrypted_path)

            assert config["DATABASE_URL"] == "postgresql://prod:secret@db.prod/app"
            assert config["API_KEY"] == "prod-api-key-secret"
            assert config["SECRET_KEY"] == "prod-secret-key"
            assert config["DEBUG"] == "false"

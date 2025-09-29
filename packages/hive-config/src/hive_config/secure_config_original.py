"""
Secure Configuration Management for Production Environments

Provides encrypted secrets management for production deployments.
Supports both plain .env files (development) and encrypted .env.prod files (production).
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Dict

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from hive_logging import get_logger

logger = get_logger(__name__)


class SecureConfigLoader:
    """
    Secure configuration loader with encryption support

    Supports:
    - Plain .env files for development
    - Encrypted .env.prod files for production
    - Master key from HIVE_MASTER_KEY environment variable
    """

    def __init__(self, master_key: str | None = None) -> None:
        """
        Initialize secure config loader

        Args:
            master_key: Master key for decryption (defaults to HIVE_MASTER_KEY env var)
        """
        self.master_key = master_key or os.environ.get("HIVE_MASTER_KEY")
        self._cipher = None

        if self.master_key:
            self._initialize_cipher()

    def _initialize_cipher(self) -> None:
        """Initialize Fernet cipher from master key"""
        try:
            # Use PBKDF2 to derive a key from the master key
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"hive-platform-v3",  # Static salt for deterministic key derivation,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
            self._cipher = Fernet(key)
            logger.debug("Cipher initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize cipher: {e}")
            raise ValueError("Invalid master key provided")

    def encrypt_file(self, input_path: Path, output_path: Path | None = None) -> Path:
        """
        Encrypt a configuration file

        Args:
            input_path: Path to plain text config file
            output_path: Path for encrypted file (defaults to input_path + .encrypted)

        Returns:
            Path to encrypted file
        """
        if not self._cipher:
            raise ValueError("No master key provided for encryption")

        if not output_path:
            output_path = Path(str(input_path) + ".encrypted")

        try:
            # Read plain text config
            with open(input_path, "r") as f:
                plain_text = f.read()

            # Encrypt content
            encrypted_data = self._cipher.encrypt(plain_text.encode())

            # Write encrypted file
            with open(output_path, "wb") as f:
                f.write(encrypted_data)

            logger.info(f"Successfully encrypted {input_path} to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to encrypt file: {e}")
            raise

    def decrypt_file(self, encrypted_path: Path) -> str:
        """
        Decrypt a configuration file

        Args:
            encrypted_path: Path to encrypted config file

        Returns:
            Decrypted content as string
        """
        if not self._cipher:
            raise ValueError("No master key provided for decryption")

        try:
            # Read encrypted data
            with open(encrypted_path, "rb") as f:
                encrypted_data = f.read()

            # Decrypt content
            plain_text = self._cipher.decrypt(encrypted_data).decode()

            logger.debug(f"Successfully decrypted {encrypted_path}")
            return plain_text

        except Exception as e:
            logger.error(f"Failed to decrypt file: {e}")
            raise ValueError("Failed to decrypt configuration - invalid key or corrupted file")

    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """
        Load configuration from file (plain or encrypted)

        Args:
            config_path: Path to configuration file

        Returns:
            Dictionary of configuration values
        """
        config = {}

        # Check if this is an encrypted file
        if config_path.suffix == ".encrypted" or ".encrypted" in str(config_path):
            if not self._cipher:
                raise ValueError("Cannot load encrypted config without master key")

            # Decrypt and parse
            plain_text = self.decrypt_file(config_path)

            # Parse as env file
            for line in plain_text.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip().strip('"').strip("'")

        else:
            # Load plain text config
            if not config_path.exists():
                logger.warning(f"Config file not found: {config_path}")
                return config

            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip().strip('"').strip("'")

        return config

    def load_secure_config(self, app_name: str, project_root: Path) -> Dict[str, Any]:
        """
        Load configuration with production/development fallback

        Tries in order:
        1. .env.prod.encrypted (if master key available)
        2. .env.prod (if exists)
        3. .env (development default)

        Args:
            app_name: Name of the application
            project_root: Root directory of the project

        Returns:
            Merged configuration dictionary
        """
        config = {}

        # Define potential config files
        app_dir = project_root / "apps" / app_name
        config_files = [
            (project_root / ".env.prod.encrypted", True)(project_root / ".env.prod", False)(
                project_root / ".env", False
            )(app_dir / ".env.prod.encrypted", True)(app_dir / ".env.prod", False)(app_dir / ".env", False)
        ]

        # Load configs in priority order
        for config_path, is_encrypted in config_files:
            if config_path.exists():
                if is_encrypted and not self._cipher:
                    logger.debug(f"Skipping encrypted config {config_path} - no master key")
                    continue

                try:
                    file_config = self.load_config(config_path)
                    # Merge configs (later files override earlier ones)
                    config.update(file_config)
                    logger.debug(f"Loaded config from {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load config from {config_path}: {e}")

        return config


def encrypt_production_config(env_file: str = ".env.prod", output_file: str = None) -> None:
    """
    Utility function to encrypt production configuration

    Args:
        env_file: Path to plain text env file
        output_file: Path for encrypted output (defaults to env_file + .encrypted)
    """
    # Ensure master key is set
    master_key = os.environ.get("HIVE_MASTER_KEY")
    if not master_key:
        logger.info("ERROR: HIVE_MASTER_KEY environment variable not set")
        logger.info("Generate a key with: python -c 'import secrets; logger.info(secrets.token_urlsafe(32))'")
        return

    loader = SecureConfigLoader(master_key)

    input_path = Path(env_file)
    output_path = Path(output_file) if output_file else None

    try:
        encrypted_path = loader.encrypt_file(input_path, output_path)
        logger.info(f"Successfully encrypted {input_path} to {encrypted_path}")
        logger.info(f"To decrypt, ensure HIVE_MASTER_KEY is set to: {master_key[:8]}...")
    except Exception as e:
        logger.info(f"Encryption failed: {e}")


def generate_master_key() -> str:
    """
    Generate a secure master key for production use

    Returns:
        URL-safe base64 encoded key
    """
    import secrets

    key = secrets.token_urlsafe(32)
    logger.info(f"Generated master key: {key}")
    logger.info(f"Set this as environment variable: export HIVE_MASTER_KEY='{key}'")
    return key


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        logger.info("Usage:")
        logger.info("  python secure_config.py generate-key")
        logger.info("  python secure_config.py encrypt <env-file> [output-file]")
        logger.info("  python secure_config.py decrypt <encrypted-file>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate-key":
        generate_master_key()
    elif command == "encrypt":
        if len(sys.argv) < 3:
            logger.info("Usage: python secure_config.py encrypt <env-file> [output-file]")
            sys.exit(1)
        env_file = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else None
        encrypt_production_config(env_file, output_file)
    elif command == "decrypt":
        if len(sys.argv) < 3:
            logger.info("Usage: python secure_config.py decrypt <encrypted-file>")
            sys.exit(1)
        encrypted_file = sys.argv[2]
        loader = SecureConfigLoader()
        try:
            content = loader.decrypt_file(Path(encrypted_file))
            logger.info(content)
        except Exception as e:
            logger.info(f"Decryption failed: {e}")
            sys.exit(1)
    else:
        logger.info(f"Unknown command: {command}")
        sys.exit(1)

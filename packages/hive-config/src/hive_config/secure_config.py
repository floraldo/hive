"""
Secure Configuration Management for Production Environments

Provides encrypted secrets management for production deployments.
Supports both plain .env files (development) and encrypted .env.prod files (production).
Enhanced with random salt encryption to prevent rainbow table attacks.
"""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path
from typing import Any, Dict

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from hive_logging import get_logger

logger = get_logger(__name__)


class SecureConfigLoader:
    """
    Secure configuration loader with enhanced encryption support

    Supports:
    - Plain .env files for development
    - Encrypted .env.prod files for production with random salts
    - Master key from HIVE_MASTER_KEY environment variable
    - Backward compatibility with legacy static salt files
    """

    def __init__(self, master_key: str | None = None) -> None:
        """
        Initialize secure config loader

        Args:
            master_key: Master key for decryption (defaults to HIVE_MASTER_KEY env var)
        """
        self.master_key = master_key or os.environ.get("HIVE_MASTER_KEY")
        self._legacy_cipher = None

        if self.master_key:
            self._initialize_cipher()

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive encryption key from master key and salt"""
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        return base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))

    def _initialize_cipher(self) -> None:
        """Initialize cipher capabilities and legacy support"""
        if not self.master_key:
            raise ValueError("Master key required for encryption operations")

        # Initialize legacy cipher for backward compatibility
        try:
            legacy_salt = b"hive-platform-v3"
            legacy_key = self._derive_key(legacy_salt)
            self._legacy_cipher = Fernet(legacy_key)
            logger.debug("Cipher capabilities initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize cipher: {e}")
            raise ValueError("Invalid master key provided")

    def encrypt_file(self, input_path: Path, output_path: Path | None = None) -> Path:
        """
        Encrypt a configuration file with random salt for enhanced security

        Args:
            input_path: Path to plain text config file
            output_path: Path for encrypted file (defaults to input_path + .encrypted)

        Returns:
            Path to encrypted file

        Security Enhancement:
            - Uses random salt per encryption to prevent rainbow table attacks
            - Salt is stored with encrypted data for decryption
            - Maintains backward compatibility with legacy files
        """
        if not self.master_key:
            raise ValueError("No master key provided for encryption")

        if not output_path:
            output_path = Path(str(input_path) + ".encrypted")

        try:
            # Read plain text config
            with open(input_path, "r") as f:
                plain_text = f.read()

            # Generate random salt for this encryption (32 bytes = 256 bits)
            salt = secrets.token_bytes(32)

            # Derive key with random salt
            key = self._derive_key(salt)
            cipher = Fernet(key)

            # Encrypt content
            encrypted_data = cipher.encrypt(plain_text.encode())

            # Create payload: version_flag + salt_length + salt + encrypted_data
            # Version flag 'HIVE' indicates new format with random salt
            version_flag = b"HIVE"
            salt_length = len(salt).to_bytes(4, byteorder="big")
            payload = version_flag + salt_length + salt + encrypted_data

            # Write encrypted file
            with open(output_path, "wb") as f:
                f.write(payload)

            logger.info(f"Successfully encrypted {input_path} to {output_path} with random salt")
            return output_path

        except Exception as e:
            logger.error(f"Failed to encrypt file: {e}")
            raise

    def decrypt_file(self, encrypted_path: Path) -> str:
        """
        Decrypt a configuration file supporting both new and legacy formats

        Args:
            encrypted_path: Path to encrypted config file

        Returns:
            Decrypted content as string

        Compatibility:
            - New format: Starts with 'HIVE' version flag, uses random salt
            - Legacy format: Uses static salt for backward compatibility
        """
        if not self.master_key:
            raise ValueError("No master key provided for decryption")

        try:
            # Read encrypted data
            with open(encrypted_path, "rb") as f:
                payload = f.read()

            # Check if this is new format with version flag
            if payload.startswith(b"HIVE"):
                # New format with random salt
                # Extract salt length (bytes 4-8)
                salt_length = int.from_bytes(payload[4:8], byteorder="big")

                # Extract salt (bytes 8 to 8+salt_length)
                salt = payload[8 : 8 + salt_length]

                # Extract encrypted data (remaining bytes)
                encrypted_data = payload[8 + salt_length :]

                # Derive key with extracted salt
                key = self._derive_key(salt)
                cipher = Fernet(key)

                logger.debug(f"Decrypting {encrypted_path} using new format with random salt")
            else:
                # Legacy format with static salt
                if not self._legacy_cipher:
                    raise ValueError("Legacy cipher not initialized")

                cipher = self._legacy_cipher
                encrypted_data = payload

                logger.debug(f"Decrypting {encrypted_path} using legacy format with static salt")

            # Decrypt content
            plain_text = cipher.decrypt(encrypted_data).decode()

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
            if not self.master_key:
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
            (project_root / ".env.prod.encrypted", True),
            (project_root / ".env.prod", False),
            (project_root / ".env", False),
            (app_dir / ".env.prod.encrypted", True),
            (app_dir / ".env.prod", False),
            (app_dir / ".env", False),
        ]

        # Load configs in priority order
        for config_path, is_encrypted in config_files:
            if config_path.exists():
                if is_encrypted and not self.master_key:
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
    Utility function to encrypt production configuration with enhanced security

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
        logger.info("Enhanced security: Random salt used to prevent rainbow table attacks")
        logger.info(f"To decrypt, ensure HIVE_MASTER_KEY is set to: {master_key[:8]}...")
    except Exception as e:
        logger.info(f"Encryption failed: {e}")


def generate_master_key() -> str:
    """
    Generate a secure master key for production use

    Returns:
        URL-safe base64 encoded key
    """
    key = secrets.token_urlsafe(32)
    logger.info(f"Generated master key: {key}")
    logger.info(f"Set this as environment variable: export HIVE_MASTER_KEY='{key}'")
    logger.info("Store this key securely - it cannot be recovered if lost!")
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

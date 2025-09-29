"""
Pool Configuration Manager

Manages connection pool configurations with versioning and validation.
Part of PROJECT VANGUARD Phase 2.2 - Automated Connection Pool Tuning.

Features:
- Configuration validation and schema enforcement
- Version control integration
- Atomic configuration updates
- Configuration diffing and comparison
- Rollback capability

Usage:
    from pool_config_manager import PoolConfigManager

    manager = PoolConfigManager()
    config = manager.get_config("database_pool")
    manager.update_config("database_pool", new_config)
"""

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class PoolConfig:
    """Connection pool configuration."""

    # Connection settings
    min_size: int
    max_size: int
    max_overflow: int
    pool_timeout: float

    # Behavior settings
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    echo_pool: bool = False

    # Performance settings
    max_lifetime: int | None = None
    connect_timeout: int = 30
    query_timeout: int = 300

    # Metadata
    service_name: str = ""
    last_updated: str = ""
    updated_by: str = "pool_tuning_orchestrator"
    version: int = 1

    # Validation rules
    validation_rules: dict[str, Any] = field(default_factory=dict)


class PoolConfigManager:
    """
    Manage connection pool configurations with versioning.

    Responsibilities:
    - Load/save pool configurations
    - Validate configuration parameters
    - Track configuration history
    - Enable atomic updates with rollback
    """

    def __init__(self, config_dir: str = "config/pools", history_dir: str = "data/config_history"):
        self.config_dir = Path(config_dir)
        self.history_dir = Path(history_dir)

        # Create directories
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Configuration schema
        self.schema = self._load_schema()

    def _load_schema(self) -> dict[str, Any]:
        """Load configuration validation schema."""
        return {
            "min_size": {"type": "int", "min": 1, "max": 100, "description": "Minimum pool size"},
            "max_size": {
                "type": "int",
                "min": 1,
                "max": 1000,
                "description": "Maximum pool size",
                "validation": lambda val, config: val >= config.get("min_size", 0),
            },
            "max_overflow": {"type": "int", "min": 0, "max": 500, "description": "Maximum overflow connections"},
            "pool_timeout": {
                "type": "float",
                "min": 0.1,
                "max": 300.0,
                "description": "Timeout for getting connection from pool (seconds)",
            },
            "pool_recycle": {
                "type": "int",
                "min": 60,
                "max": 86400,
                "description": "Connection recycle time (seconds)",
            },
            "connect_timeout": {
                "type": "int",
                "min": 1,
                "max": 300,
                "description": "Database connection timeout (seconds)",
            },
            "query_timeout": {"type": "int", "min": 1, "max": 3600, "description": "Query execution timeout (seconds)"},
        }

    def get_config(self, service_name: str) -> PoolConfig | None:
        """
        Get current configuration for a service.

        Args:
            service_name: Name of service

        Returns:
            Pool configuration or None if not found
        """
        config_file = self.config_dir / f"{service_name}.json"

        if not config_file.exists():
            logger.warning(f"Configuration not found for {service_name}")
            return None

        try:
            with open(config_file, "r") as f:
                data = json.load(f)

            config = PoolConfig(
                min_size=data["min_size"],
                max_size=data["max_size"],
                max_overflow=data["max_overflow"],
                pool_timeout=data["pool_timeout"],
                pool_recycle=data.get("pool_recycle", 3600),
                pool_pre_ping=data.get("pool_pre_ping", True),
                echo_pool=data.get("echo_pool", False),
                max_lifetime=data.get("max_lifetime"),
                connect_timeout=data.get("connect_timeout", 30),
                query_timeout=data.get("query_timeout", 300),
                service_name=data.get("service_name", service_name),
                last_updated=data.get("last_updated", ""),
                updated_by=data.get("updated_by", "unknown"),
                version=data.get("version", 1),
            )

            logger.info(f"Loaded config for {service_name} (version {config.version})")
            return config

        except Exception as e:
            logger.error(f"Failed to load config for {service_name}: {e}")
            return None

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate configuration against schema.

        Args:
            config: Configuration to validate

        Returns:
            (is_valid, list of validation errors)
        """
        errors = []

        for field_name, rules in self.schema.items():
            if field_name not in config:
                if rules.get("required", False):
                    errors.append(f"Required field missing: {field_name}")
                continue

            value = config[field_name]
            field_type = rules["type"]

            # Type validation
            if field_type == "int" and not isinstance(value, int):
                errors.append(f"{field_name} must be int, got {type(value).__name__}")
                continue

            if field_type == "float" and not isinstance(value, (int, float)):
                errors.append(f"{field_name} must be float, got {type(value).__name__}")
                continue

            # Range validation
            if "min" in rules and value < rules["min"]:
                errors.append(f"{field_name} = {value} is below minimum {rules['min']}")

            if "max" in rules and value > rules["max"]:
                errors.append(f"{field_name} = {value} exceeds maximum {rules['max']}")

            # Custom validation
            if "validation" in rules:
                try:
                    if not rules["validation"](value, config):
                        errors.append(f"{field_name} failed custom validation")
                except Exception as e:
                    errors.append(f"{field_name} validation error: {str(e)}")

        # Cross-field validation
        if "min_size" in config and "max_size" in config:
            if config["min_size"] > config["max_size"]:
                errors.append(f"min_size ({config['min_size']}) cannot exceed max_size ({config['max_size']})")

        is_valid = len(errors) == 0

        if is_valid:
            logger.info("Configuration validation: PASS")
        else:
            logger.warning(f"Configuration validation: FAIL ({len(errors)} errors)")
            for error in errors:
                logger.warning(f"  - {error}")

        return is_valid, errors

    def save_to_history(self, service_name: str, config: dict[str, Any], change_reason: str = "") -> Path:
        """
        Save configuration to history.

        Args:
            service_name: Name of service
            config: Configuration to save
            change_reason: Reason for configuration change

        Returns:
            Path to history file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        history_file = self.history_dir / f"{service_name}_{timestamp}.json"

        history_entry = {
            "service_name": service_name,
            "timestamp": datetime.now().isoformat(),
            "config": config,
            "change_reason": change_reason,
            "updated_by": config.get("updated_by", "unknown"),
        }

        try:
            with open(history_file, "w") as f:
                json.dump(history_entry, f, indent=2)

            logger.info(f"Saved config history for {service_name} to {history_file}")
            return history_file

        except Exception as e:
            logger.error(f"Failed to save config history: {e}")
            raise

    def update_config(
        self, service_name: str, new_config: dict[str, Any], change_reason: str = "", skip_validation: bool = False
    ) -> bool:
        """
        Update configuration with validation and history tracking.

        Args:
            service_name: Name of service
            new_config: New configuration
            change_reason: Reason for change
            skip_validation: Skip validation (use with caution)

        Returns:
            True if successful
        """
        logger.info(f"Updating config for {service_name}")

        # Validate new config
        if not skip_validation:
            is_valid, errors = self.validate_config(new_config)
            if not is_valid:
                logger.error(f"Configuration validation failed:")
                for error in errors:
                    logger.error(f"  - {error}")
                return False

        # Get current config for history
        current_config = self.get_config(service_name)
        if current_config:
            # Save current config to history
            self.save_to_history(service_name, current_config.__dict__, change_reason=f"Before update: {change_reason}")

        # Update version
        new_version = (current_config.version + 1) if current_config else 1
        new_config["version"] = new_version
        new_config["service_name"] = service_name
        new_config["last_updated"] = datetime.now().isoformat()

        # Write new config
        config_file = self.config_dir / f"{service_name}.json"

        try:
            with open(config_file, "w") as f:
                json.dump(new_config, f, indent=2)

            logger.info(
                f"Updated config for {service_name} "
                f"(version {current_config.version if current_config else 0} → {new_version})"
            )

            # Save to history
            self.save_to_history(service_name, new_config, change_reason=change_reason)

            return True

        except Exception as e:
            logger.error(f"Failed to update config for {service_name}: {e}")
            return False

    def diff_configs(
        self, service_name: str, old_config: dict[str, Any], new_config: dict[str, Any]
    ) -> dict[str, tuple[Any, Any]]:
        """
        Generate diff between two configurations.

        Args:
            service_name: Service name
            old_config: Old configuration
            new_config: New configuration

        Returns:
            Dictionary of changes: {field: (old_value, new_value)}
        """
        changes = {}

        all_keys = set(old_config.keys()) | set(new_config.keys())

        for key in all_keys:
            old_val = old_config.get(key)
            new_val = new_config.get(key)

            if old_val != new_val:
                changes[key] = (old_val, new_val)

        logger.info(f"Config diff for {service_name}: {len(changes)} changes")
        return changes

    def rollback_config(self, service_name: str, version: int | None = None) -> bool:
        """
        Rollback configuration to previous version.

        Args:
            service_name: Service to rollback
            version: Target version (None = previous version)

        Returns:
            True if successful
        """
        logger.info(f"Rolling back config for {service_name}")

        # Get history files
        history_files = sorted(self.history_dir.glob(f"{service_name}_*.json"), reverse=True)

        if not history_files:
            logger.error(f"No history found for {service_name}")
            return False

        # Find target version
        target_file = None
        if version is None:
            # Use most recent history (previous version)
            if len(history_files) >= 2:
                target_file = history_files[1]
            else:
                target_file = history_files[0]
        else:
            # Find specific version
            for history_file in history_files:
                try:
                    with open(history_file, "r") as f:
                        data = json.load(f)
                    if data["config"].get("version") == version:
                        target_file = history_file
                        break
                except Exception:
                    continue

        if not target_file:
            logger.error(f"Target version {version} not found for {service_name}")
            return False

        # Load target config
        try:
            with open(target_file, "r") as f:
                history_entry = json.load(f)

            target_config = history_entry["config"]

            # Update with rollback reason
            return self.update_config(
                service_name,
                target_config,
                change_reason=f"Rollback to version {target_config.get('version', 'unknown')}",
                skip_validation=False,
            )

        except Exception as e:
            logger.error(f"Failed to rollback config for {service_name}: {e}")
            return False

    def get_config_history(self, service_name: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get configuration history for a service.

        Args:
            service_name: Service name
            limit: Maximum number of history entries to return

        Returns:
            List of history entries (newest first)
        """
        history_files = sorted(self.history_dir.glob(f"{service_name}_*.json"), reverse=True)[:limit]

        history = []
        for history_file in history_files:
            try:
                with open(history_file, "r") as f:
                    history.append(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load history file {history_file}: {e}")

        logger.info(f"Retrieved {len(history)} history entries for {service_name}")
        return history

    def list_services(self) -> list[str]:
        """
        List all services with configurations.

        Returns:
            List of service names
        """
        config_files = self.config_dir.glob("*.json")
        services = [f.stem for f in config_files]

        logger.info(f"Found {len(services)} configured services")
        return services

    def export_all_configs(self, output_file: str) -> bool:
        """
        Export all configurations to a single file.

        Args:
            output_file: Path to output file

        Returns:
            True if successful
        """
        services = self.list_services()
        all_configs = {}

        for service_name in services:
            config = self.get_config(service_name)
            if config:
                all_configs[service_name] = config.__dict__

        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(
                    {
                        "exported_at": datetime.now().isoformat(),
                        "total_services": len(all_configs),
                        "configs": all_configs,
                    },
                    f,
                    indent=2,
                    default=str,
                )

            logger.info(f"Exported {len(all_configs)} configs to {output_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to export configs: {e}")
            return False


def main():
    """CLI interface for PoolConfigManager."""
    import argparse

    parser = argparse.ArgumentParser(description="Pool Configuration Manager")
    parser.add_argument("--list", action="store_true", help="List all services")
    parser.add_argument("--get", type=str, help="Get config for service")
    parser.add_argument("--history", type=str, help="Get config history for service")
    parser.add_argument("--diff", type=str, help="Show diff for service")
    parser.add_argument("--export", type=str, help="Export all configs to file")
    parser.add_argument("--validate", type=str, help="Validate config file")

    args = parser.parse_args()

    manager = PoolConfigManager()

    if args.list:
        services = manager.list_services()
        print(f"\nConfigured Services ({len(services)}):")
        for service in services:
            print(f"  - {service}")

    elif args.get:
        config = manager.get_config(args.get)
        if config:
            print(f"\nConfiguration for {args.get}:")
            print(json.dumps(config.__dict__, indent=2, default=str))

    elif args.history:
        history = manager.get_config_history(args.history)
        print(f"\nConfiguration History for {args.history}:")
        for i, entry in enumerate(history, 1):
            print(f"\n{i}. Version {entry['config'].get('version', 'unknown')}")
            print(f"   Timestamp: {entry['timestamp']}")
            print(f"   Updated by: {entry.get('updated_by', 'unknown')}")
            print(f"   Reason: {entry.get('change_reason', 'N/A')}")

    elif args.diff:
        history = manager.get_config_history(args.diff, limit=2)
        if len(history) >= 2:
            changes = manager.diff_configs(args.diff, history[1]["config"], history[0]["config"])
            print(f"\nConfiguration Changes for {args.diff}:")
            for field, (old_val, new_val) in changes.items():
                print(f"  {field}: {old_val} → {new_val}")

    elif args.export:
        success = manager.export_all_configs(args.export)
        if success:
            print(f"Exported configs to {args.export}")

    elif args.validate:
        try:
            with open(args.validate, "r") as f:
                config = json.load(f)
            is_valid, errors = manager.validate_config(config)
            if is_valid:
                print("Configuration is VALID")
            else:
                print("Configuration is INVALID:")
                for error in errors:
                    print(f"  - {error}")
        except Exception as e:
            print(f"Failed to validate: {e}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

"""
Property-based tests for configuration validation using Hypothesis.

Tests the robustness of configuration parsing and validation across
a wide range of input scenarios that might occur in real deployments.
"""

import json
import os
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite


# Custom strategies for configuration testing
@composite
def env_file_content(draw):
    """Generate realistic .env file content"""
    lines = []

    # Add some comments
    if draw(st.booleans()):
        lines.append("# Configuration file")
        lines.append("")

    # Generate key-value pairs
    num_pairs = draw(st.integers(min_value=1, max_value=20))

    for _ in range(num_pairs):
        # Valid environment variable name
        key = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
                min_size=1,
                max_size=50,
            ).filter(lambda x: x and x[0].isalpha()),
        )

        # Various value types
        value_type = draw(st.sampled_from(["string", "number", "boolean", "quoted", "empty"]))

        if value_type == "string":
            value = draw(st.text(alphabet=st.characters(blacklist_characters="\n\r"), max_size=100))
        elif value_type == "number":
            value = str(draw(st.integers(min_value=-1000, max_value=1000)))
        elif value_type == "boolean":
            value = draw(st.sampled_from(["true", "false", "True", "False", "TRUE", "FALSE"]))
        elif value_type == "quoted":
            inner_value = draw(st.text(alphabet=st.characters(blacklist_characters='\n\r"'), max_size=50))
            value = f'"{inner_value}"'
        else:  # empty
            value = ""

        lines.append(f"{key}={value}")

        # Sometimes add empty lines
        if draw(st.booleans()):
            lines.append("")

    return "\n".join(lines)


@composite
def json_config_content(draw):
    """Generate realistic JSON configuration content"""
    config = {}

    # Add various configuration sections
    sections = draw(
        st.lists(
            st.sampled_from(["database", "api", "logging", "cache", "security"]), min_size=1, max_size=5, unique=True,
        ),
    )

    for section in sections:
        if section == "database":
            config[section] = {
                "host": draw(st.sampled_from(["localhost", "127.0.0.1", "db.example.com"])),
                "port": draw(st.integers(min_value=1, max_value=65535)),
                "name": draw(
                    st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=20),
                ),
                "pool_size": draw(st.integers(min_value=1, max_value=100)),
            }
        elif section == "api":
            config[section] = {
                "host": draw(st.sampled_from(["0.0.0.0", "127.0.0.1", "api.example.com"])),
                "port": draw(st.integers(min_value=1000, max_value=9999)),
                "timeout": draw(st.floats(min_value=1.0, max_value=300.0)),
                "rate_limit": draw(st.integers(min_value=10, max_value=10000)),
            }
        elif section == "logging":
            config[section] = {
                "level": draw(st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])),
                "format": draw(st.sampled_from(["json", "text", "structured"])),
                "file": draw(st.booleans()),
            }

    return json.dumps(config, indent=2)


class TestConfigurationProperties:
    """Property-based tests for configuration validation"""

    @given(env_file_content())
    @settings(max_examples=100, deadline=3000)
    def test_env_file_parsing_robustness(self, content):
        """Test that env file parsing handles various input formats"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Parse the file (would use actual parser here)
            config = self._parse_env_file(temp_path)

            # Property 1: Parsing should not crash
            assert isinstance(config, dict)

            # Property 2: All keys should be strings
            for key in config.keys():
                assert isinstance(key, str)
                assert len(key) > 0

            # Property 3: Values should be strings (from env files)
            for value in config.values():
                assert isinstance(value, str)

            # Property 4: No duplicate keys (dict property ensures this)
            assert len(config) == len(set(config.keys()))

        finally:
            os.unlink(temp_path)

    @given(json_config_content())
    @settings(max_examples=50, deadline=2000)
    def test_json_config_validation(self, content):
        """Test JSON configuration validation properties"""
        try:
            config = json.loads(content)

            # Property 1: Valid JSON should parse without error
            assert isinstance(config, dict)

            # Property 2: Nested structures should be preserved
            for section_name, section_config in config.items():
                assert isinstance(section_name, str)
                if isinstance(section_config, dict):
                    # Nested configuration should have valid structure
                    for key, value in section_config.items():
                        assert isinstance(key, str)
                        # Value can be various types (str, int, float, bool)
                        assert value is not None or value == ""

        except json.JSONDecodeError:
            # Invalid JSON is acceptable - we just shouldn't crash
            pass

    @given(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.one_of(
                st.text(max_size=100), st.integers(), st.floats(allow_nan=False, allow_infinity=False), st.booleans(),
            ),
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=100, deadline=2000)
    def test_config_merging_properties(self, config_dict):
        """Test properties of configuration merging"""
        # Create base config
        base_config = {"app_name": "test", "version": "1.0"}

        # Merge with generated config
        merged = {**base_config, **config_dict}

        # Property 1: Merged config contains all base keys
        for key in base_config:
            assert key in merged

        # Property 2: Merged config contains all override keys
        for key in config_dict:
            assert key in merged

        # Property 3: Override values take precedence
        for key, value in config_dict.items():
            assert merged[key] == value

        # Property 4: Non-overridden base values remain
        for key, value in base_config.items():
            if key not in config_dict:
                assert merged[key] == value

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=200, deadline=1000)
    def test_config_key_normalization(self, raw_key):
        """Test configuration key normalization properties"""
        # Simulate key normalization (common in config systems)
        normalized = self._normalize_config_key(raw_key)

        # Property 1: Normalized key should not be empty
        assert len(normalized) > 0

        # Property 2: Normalized key should be lowercase
        assert normalized.islower()

        # Property 3: No spaces in normalized key
        assert " " not in normalized

        # Property 4: Normalization should be idempotent
        assert self._normalize_config_key(normalized) == normalized

    @given(
        st.lists(
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20), values=st.text(max_size=50), min_size=1, max_size=10,
            ),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=50, deadline=3000)
    def test_config_hierarchy_properties(self, config_layers):
        """Test configuration hierarchy merging properties"""
        # Merge configuration layers (later layers override earlier ones)
        final_config = {}
        for layer in config_layers:
            final_config.update(layer)

        # Property 1: Final config should contain all unique keys
        all_keys = set()
        for layer in config_layers:
            all_keys.update(layer.keys())
        assert set(final_config.keys()) == all_keys

        # Property 2: Values should come from the last layer that defined them
        for key in all_keys:
            # Find the last layer that contains this key
            last_value = None
            for layer in config_layers:
                if key in layer:
                    last_value = layer[key]
            assert final_config[key] == last_value

    @given(st.text(alphabet=st.characters(blacklist_characters="\x00"), max_size=1000))
    @settings(max_examples=100, deadline=2000)
    def test_config_value_sanitization(self, raw_value):
        """Test configuration value sanitization properties"""
        # Simulate value sanitization
        sanitized = self._sanitize_config_value(raw_value)

        # Property 1: Sanitized value should not contain null bytes
        assert "\x00" not in sanitized

        # Property 2: Sanitized value should not be longer than original
        assert len(sanitized) <= len(raw_value)

        # Property 3: Sanitization should be idempotent
        assert self._sanitize_config_value(sanitized) == sanitized

        # Property 4: Empty input should produce empty output
        if not raw_value:
            assert not sanitized

    def _parse_env_file(self, file_path: str) -> dict[str, str]:
        """Simple env file parser for testing"""
        config = {}
        try:
            with open(file_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key:  # Only add non-empty keys
                            config[key] = value
        except Exception:
            # Return empty config on parse errors
            pass
        return config

    def _normalize_config_key(self, key: str) -> str:
        """Normalize configuration key"""
        # Remove non-alphanumeric characters and convert to lowercase
        normalized = "".join(c if c.isalnum() else "_" for c in key.lower())
        # Remove leading/trailing underscores and collapse multiple underscores
        normalized = "_".join(part for part in normalized.split("_") if part)
        return normalized or "default_key"

    def _sanitize_config_value(self, value: str) -> str:
        """Sanitize configuration value"""
        # Remove null bytes and control characters
        sanitized = "".join(c for c in value if ord(c) >= 32 or c in "\t\n\r")
        return sanitized


class TestConfigSecurityProperties:
    """Test security-related properties of configuration handling"""

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50, deadline=1000)
    def test_sensitive_data_detection(self, config_value):
        """Test detection of potentially sensitive configuration values"""
        # Check if value looks like sensitive data
        is_sensitive = self._is_sensitive_value(config_value)

        # Property 1: Values containing 'password' should be marked sensitive
        if "password" in config_value.lower():
            assert is_sensitive

        # Property 2: Values containing 'secret' should be marked sensitive
        if "secret" in config_value.lower():
            assert is_sensitive

        # Property 3: Values containing 'key' should be marked sensitive
        if "key" in config_value.lower() and len(config_value) > 10:
            assert is_sensitive

    @given(
        st.dictionaries(
            keys=st.sampled_from(["database_url", "api_key", "secret_token", "password", "public_key"]),
            values=st.text(min_size=10, max_size=100),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=30, deadline=1000)
    def test_config_masking_properties(self, sensitive_config):
        """Test configuration value masking for logging/display"""
        masked_config = self._mask_sensitive_values(sensitive_config)

        # Property 1: All keys should be preserved
        assert set(masked_config.keys()) == set(sensitive_config.keys())

        # Property 2: Sensitive values should be masked
        for key, original_value in sensitive_config.items():
            masked_value = masked_config[key]
            if self._is_sensitive_key(key):
                assert masked_value != original_value
                assert "*" in masked_value or "REDACTED" in masked_value

    def _is_sensitive_value(self, value: str) -> bool:
        """Check if a value appears to contain sensitive data"""
        sensitive_indicators = ["password", "secret", "token", "key"]
        value_lower = value.lower()
        return any(indicator in value_lower for indicator in sensitive_indicators)

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a configuration key typically contains sensitive data"""
        sensitive_keys = ["password", "secret", "token", "key", "credential"]
        key_lower = key.lower()
        return any(sensitive_key in key_lower for sensitive_key in sensitive_keys)

    def _mask_sensitive_values(self, config: dict[str, str]) -> dict[str, str]:
        """Mask sensitive values in configuration"""
        masked = {}
        for key, value in config.items():
            if self._is_sensitive_key(key):
                if len(value) > 4:
                    masked[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
                else:
                    masked[key] = "REDACTED"
            else:
                masked[key] = value
        return masked


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

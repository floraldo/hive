"""Test file for Guardian Agent validation.

This file deliberately includes Golden Rule violations to test the Guardian's
detection capabilities.
"""


def violate_golden_rule_print():
    """Function that violates Golden Rule: No print() statements."""
    # Violation: Golden Rule #2 - should use hive_logging
    print("This is a Golden Rule violation!")

    data = {"key": "value"}
    print(f"Data: {data}")

    return True


def violate_golden_rule_hardcoded_path():
    """Function that violates Golden Rule: No hardcoded paths."""
    # Violation: Golden Rule #5 - should use configuration
    config_path = "/home/user/config.yaml"

    return config_path


def proper_logging_example():
    """Example of proper logging using hive_logging."""
    from hive_logging import get_logger

    logger = get_logger(__name__)
    logger.info("This is the correct way to log")

    return True

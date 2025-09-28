# Basic tests for logger.py

import logging
import pytest
from Systemiser.utils.logger import setup_logging  # Assuming setup_logging is the main function


# Fixture to capture logs
@pytest.fixture
def log_capture(caplog):
    # Set a known logging level for the test
    caplog.set_level(logging.INFO)
    return caplog


def test_logger_setup():
    """Test if the logger can be set up without errors."""
    try:
        # Attempt to set up logging (adjust function call if needed)
        logger = setup_logging("test_system")
        assert logger is not None
        assert isinstance(logger, logging.Logger)
    except Exception as e:
        pytest.fail(f"Logger setup failed: {e}")


def test_logging_output(log_capture):
    """Test if messages are logged correctly."""
    logger = setup_logging("test_output")
    test_message = "This is an info test message."
    logger.info(test_message)

    # Check if the message appears in the captured logs
    assert test_message in log_capture.text
    # Check the log level
    assert log_capture.records[0].levelname == "INFO"


def test_debug_level(log_capture):
    """Test if debug messages are ignored when level is INFO."""
    logger = setup_logging("test_debug", level=logging.INFO)
    logger.debug("This debug message should not appear.")
    assert "This debug message should not appear." not in log_capture.text

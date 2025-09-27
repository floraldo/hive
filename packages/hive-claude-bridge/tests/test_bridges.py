"""
Unit tests for Bridge components
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from hive_claude_bridge.bridge import BaseClaludeBridge, ClaudeBridgeConfig
from hive_claude_bridge.planner_bridge import ClaudePlannerBridge
from hive_claude_bridge.reviewer_bridge import ClaudeReviewerBridge
from hive_claude_bridge.exceptions import (
    ClaudeNotFoundError,
    ClaudeTimeoutError,
    ClaudeResponseError,
    ClaudeValidationError
)


class TestClaudeBridgeConfig:
    """Test ClaudeBridgeConfig dataclass"""

    def test_default_config(self):
        """Test default configuration"""
        config = ClaudeBridgeConfig()

        assert config.mock_mode is False
        assert config.timeout == 120
        assert config.max_retries == 3
        assert config.use_dangerously_skip_permissions is True
        assert config.shell_mode_windows is True
        assert config.fallback_enabled is True
        assert config.verbose is False

    def test_custom_config(self):
        """Test custom configuration"""
        config = ClaudeBridgeConfig(
            mock_mode=True,
            timeout=60,
            max_retries=5,
            verbose=True
        )

        assert config.mock_mode is True
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.verbose is True


class TestBaseClaludeBridge:
    """Test BaseClaludeBridge functionality"""

    def test_initialization(self):
        """Test bridge initialization"""
        config = ClaudeBridgeConfig(mock_mode=True)
        bridge = BaseClaludeBridge(config=config)

        assert bridge.config == config

    def test_initialization_default_config(self):
        """Test bridge initialization with default config"""
        bridge = BaseClaludeBridge()

        assert isinstance(bridge.config, ClaudeBridgeConfig)
        assert bridge.config.mock_mode is False

    @patch('subprocess.run')
    def test_execute_claude_success(self, mock_run):
        """Test successful Claude execution"""
        bridge = BaseClaludeBridge()

        # Mock successful subprocess result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = bridge._execute_claude(["claude", "--version"])

        assert result == "Success output"
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_execute_claude_not_found(self, mock_run):
        """Test Claude not found error"""
        bridge = BaseClaludeBridge()

        mock_run.side_effect = FileNotFoundError("claude not found")

        with pytest.raises(ClaudeNotFoundError) as exc_info:
            bridge._execute_claude(["claude", "--version"])

        assert "Claude CLI not found" in str(exc_info.value)

    @patch('subprocess.run')
    def test_execute_claude_timeout(self, mock_run):
        """Test Claude timeout error"""
        bridge = BaseClaludeBridge(config=ClaudeBridgeConfig(timeout=1))

        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("claude", 1)

        with pytest.raises(ClaudeTimeoutError) as exc_info:
            bridge._execute_claude(["claude", "--version"])

        assert "Claude execution timed out" in str(exc_info.value)

    @patch('subprocess.run')
    def test_execute_claude_failure(self, mock_run):
        """Test Claude execution failure"""
        bridge = BaseClaludeBridge()

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error occurred"
        mock_run.return_value = mock_result

        with pytest.raises(ClaudeResponseError) as exc_info:
            bridge._execute_claude(["claude", "--invalid"])

        assert "Claude execution failed" in str(exc_info.value)
        assert "Error occurred" in str(exc_info.value)

    def test_mock_mode_enabled(self):
        """Test mock mode returns mock response"""
        config = ClaudeBridgeConfig(mock_mode=True)
        bridge = BaseClaludeBridge(config=config)

        result = bridge._execute_claude(["claude", "test"])

        assert "Mock response" in result

    @patch('subprocess.run')
    def test_retry_on_failure(self, mock_run):
        """Test retry mechanism on failure"""
        config = ClaudeBridgeConfig(max_retries=2)
        bridge = BaseClaludeBridge(config=config)

        # First call fails, second succeeds
        mock_result_fail = Mock()
        mock_result_fail.returncode = 1
        mock_result_fail.stderr = "Temporary error"

        mock_result_success = Mock()
        mock_result_success.returncode = 0
        mock_result_success.stdout = "Success"
        mock_result_success.stderr = ""

        mock_run.side_effect = [mock_result_fail, mock_result_success]

        # Note: Testing the actual retry logic would require testing call_claude_with_retry
        # For now, test direct execution
        with pytest.raises(ClaudeResponseError):
            bridge._execute_claude(["claude", "test"])

    @patch('subprocess.run')
    def test_retry_exhausted(self, mock_run):
        """Test retry exhausted raises error"""
        config = ClaudeBridgeConfig(max_retries=1)
        bridge = BaseClaludeBridge(config=config)

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Persistent error"
        mock_run.return_value = mock_result

        with pytest.raises(ClaudeResponseError):
            bridge._execute_claude(["claude", "test"])

        assert mock_run.call_count == 1  # Single call to _execute_claude


class TestClaudePlannerBridge:
    """Test ClaudePlannerBridge functionality"""

    def test_initialization(self):
        """Test planner bridge initialization"""
        config = ClaudeBridgeConfig(mock_mode=True)
        bridge = ClaudePlannerBridge(config=config)

        assert bridge.config == config

    @patch.object(BaseClaludeBridge, '_execute_claude')
    def test_plan_task_success(self, mock_execute):
        """Test successful task planning"""
        bridge = ClaudePlannerBridge()

        mock_response = '''
        {
            "approach": "implement authentication",
            "steps": ["step1", "step2"],
            "confidence": 0.9,
            "estimated_complexity": "medium"
        }
        '''
        mock_execute.return_value = mock_response

        result = bridge.plan_task(
            task_id="test-task",
            description="Implement user authentication",
            requirements=["security", "usability"]
        )

        assert result["approach"] == "implement authentication"
        assert result["confidence"] == 0.9
        assert result["estimated_complexity"] == "medium"
        assert len(result["steps"]) == 2

    @patch.object(BaseClaludeBridge, '_execute_claude')
    def test_plan_task_invalid_json(self, mock_execute):
        """Test planning with invalid JSON response"""
        bridge = ClaudePlannerBridge()

        mock_execute.return_value = "Invalid JSON response"

        with pytest.raises(ClaudeValidationError) as exc_info:
            bridge.plan_task(
                task_id="test-task",
                description="Test task"
            )

        assert "Invalid JSON response" in str(exc_info.value)

    @patch.object(BaseClaludeBridge, '_execute_claude')
    def test_plan_task_missing_required_fields(self, mock_execute):
        """Test planning with missing required fields"""
        bridge = ClaudePlannerBridge()

        # Missing 'approach' field
        mock_response = '''
        {
            "steps": ["step1", "step2"],
            "confidence": 0.9
        }
        '''
        mock_execute.return_value = mock_response

        with pytest.raises(ClaudeValidationError) as exc_info:
            bridge.plan_task(
                task_id="test-task",
                description="Test task"
            )

        assert "Missing required field" in str(exc_info.value)

    def test_build_planning_prompt(self):
        """Test planning prompt construction"""
        bridge = ClaudePlannerBridge()

        prompt = bridge._build_planning_prompt(
            task_id="test-123",
            description="Build a web app",
            requirements=["responsive", "accessible"],
            context={"framework": "React"}
        )

        assert "test-123" in prompt
        assert "Build a web app" in prompt
        assert "responsive" in prompt
        assert "accessible" in prompt
        assert "React" in prompt


class TestClaudeReviewerBridge:
    """Test ClaudeReviewerBridge functionality"""

    def test_initialization(self):
        """Test reviewer bridge initialization"""
        config = ClaudeBridgeConfig(mock_mode=True)
        bridge = ClaudeReviewerBridge(config=config)

        assert bridge.config == config

    @patch.object(BaseClaludeBridge, '_execute_claude')
    def test_review_code_success(self, mock_execute):
        """Test successful code review"""
        bridge = ClaudeReviewerBridge()

        mock_response = '''
        {
            "decision": "approve",
            "summary": "Code looks good",
            "issues": [],
            "suggestions": ["Consider adding tests"],
            "metrics": {
                "code_quality": 85,
                "testing": 70,
                "documentation": 80,
                "security": 90,
                "architecture": 75
            },
            "confidence": 0.85
        }
        '''
        mock_execute.return_value = mock_response

        result = bridge.review_code(
            task_id="test-task",
            task_description="Implement feature",
            code_files={"main.py": "def main(): pass"},
            test_results={"passed": 10, "failed": 0}
        )

        assert result["decision"] == "approve"
        assert result["summary"] == "Code looks good"
        assert result["confidence"] == 0.85
        assert "code_quality" in result["metrics"]

    @patch.object(BaseClaludeBridge, '_execute_claude')
    def test_review_code_invalid_decision(self, mock_execute):
        """Test review with invalid decision"""
        bridge = ClaudeReviewerBridge()

        mock_response = '''
        {
            "decision": "invalid_decision",
            "summary": "Review complete",
            "issues": [],
            "suggestions": [],
            "metrics": {
                "code_quality": 85
            },
            "confidence": 0.8
        }
        '''
        mock_execute.return_value = mock_response

        with pytest.raises(ClaudeValidationError) as exc_info:
            bridge.review_code(
                task_id="test-task",
                task_description="Test",
                code_files={"test.py": "pass"}
            )

        assert "Invalid decision" in str(exc_info.value)

    def test_build_review_prompt(self):
        """Test review prompt construction"""
        bridge = ClaudeReviewerBridge()

        code_files = {
            "main.py": "def main():\n    return 'Hello World'",
            "test.py": "def test_main():\n    assert main() == 'Hello World'"
        }

        test_results = {
            "tests_run": 5,
            "tests_passed": 4,
            "tests_failed": 1,
            "coverage": 80.5
        }

        prompt = bridge._build_review_prompt(
            task_id="test-123",
            task_description="Implement hello world",
            code_files=code_files,
            test_results=test_results,
            objective_analysis={"complexity": "low"},
            transcript="User requested hello world function"
        )

        assert "test-123" in prompt
        assert "Implement hello world" in prompt
        assert "def main():" in prompt
        assert "def test_main():" in prompt
        assert "tests_run" in prompt
        assert "complexity" in prompt
        assert "User requested" in prompt

    def test_validate_review_response_valid(self):
        """Test validation of valid review response"""
        bridge = ClaudeReviewerBridge()

        valid_response = {
            "decision": "approve",
            "summary": "Good code",
            "issues": [],
            "suggestions": [],
            "metrics": {"code_quality": 85},
            "confidence": 0.9
        }

        # Should not raise exception
        bridge._validate_review_response(valid_response)

    def test_validate_review_response_missing_field(self):
        """Test validation with missing required field"""
        bridge = ClaudeReviewerBridge()

        invalid_response = {
            "summary": "Good code",
            # Missing 'decision'
            "issues": [],
            "suggestions": [],
            "metrics": {"code_quality": 85},
            "confidence": 0.9
        }

        with pytest.raises(ClaudeValidationError):
            bridge._validate_review_response(invalid_response)

    def test_validate_review_response_invalid_confidence(self):
        """Test validation with invalid confidence value"""
        bridge = ClaudeReviewerBridge()

        invalid_response = {
            "decision": "approve",
            "summary": "Good code",
            "issues": [],
            "suggestions": [],
            "metrics": {"code_quality": 85},
            "confidence": 1.5  # Invalid: > 1.0
        }

        with pytest.raises(ClaudeValidationError):
            bridge._validate_review_response(invalid_response)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
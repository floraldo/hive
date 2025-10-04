"""Unit Tests for GoldenRulesWorkerCore

Tests Golden Rules worker capabilities:
- Violation detection and parsing
- Auto-fix for Rules 31, 32, 9
- Escalation for complex architectural rules
- Task processing workflow
- Git commit integration
"""

from unittest.mock import AsyncMock, patch

import pytest

from hive_orchestration.models.task import Task
from hive_orchestrator.golden_rules_worker import GoldenRulesWorkerCore


class TestGoldenRulesWorkerCore:
    """Test suite for Golden Rules Worker"""

    @pytest.fixture
    def mock_event_bus(self):
        """Mock event bus to avoid BaseBus instantiation"""
        mock_bus = AsyncMock()
        mock_bus.publish = AsyncMock()
        return mock_bus

    @pytest.fixture
    def worker(self, mock_event_bus, tmp_path):
        """Create Golden Rules worker instance with mocked dependencies"""
        # Mock get_async_event_bus to return our mock
        with patch('hive_orchestrator.qa_worker.get_async_event_bus', return_value=mock_event_bus):
            worker_instance = GoldenRulesWorkerCore(
                worker_id="gr-worker-1",
                workspace=tmp_path,  # Use actual tmp_path for file operations
                config={"database": {"path": ":memory:"}},
            )
            # Ensure event_bus is set (in case it wasn't by __init__)
            worker_instance.event_bus = mock_event_bus
            return worker_instance

    @pytest.fixture
    def sample_task(self):
        """Create sample Golden Rules task"""
        import uuid

        return Task(
            id=str(uuid.uuid4()),
            task_type="qa_golden_rules",
            title="Fix Golden Rules violations",
            description="Auto-fix Golden Rules violations in package",
            metadata={
                "qa_type": "golden_rules",
                "file_paths": ["packages/test-package/pyproject.toml"],
            },
        )

    @pytest.mark.asyncio
    async def test_worker_initialization(self, worker):
        """Test Golden Rules worker initializes correctly"""
        assert worker.worker_id == "gr-worker-1"
        assert worker.worker_type == "golden_rules"
        # Workspace is tmp_path fixture
        assert worker.workspace.exists()

    @pytest.mark.asyncio
    async def test_detect_violations_success(self, worker):
        """Test violation detection with violations found using registry API"""
        # Mock registry API results
        mock_results = {
            "Ruff Config Consistency": {
                "passed": False,
                "violations": ["packages/test-package/pyproject.toml: Missing [tool.ruff]"],
                "severity": "WARNING",
            },
            "Python Version Specification": {
                "passed": False,
                "violations": ["packages/test-package/pyproject.toml: Missing python version"],
                "severity": "INFO",
            },
            "Logging Standards": {
                "passed": False,
                "violations": ["packages/test-package/src/test.py:15: print() usage detected"],
                "severity": "ERROR",
            },
        }

        with patch("hive_orchestrator.golden_rules_worker.run_all_golden_rules") as mock_validate:
            mock_validate.return_value = (False, mock_results)

            result = await worker.detect_golden_rules_violations()

            assert result["total_count"] == 3
            assert result["auto_fixable_count"] == 3  # Rules 31, 32, 9 are all auto-fixable
            assert result["escalation_count"] == 0
            assert result["violations"][0]["rule_id"] == "31"
            assert result["violations"][0]["can_autofix"] is True

    @pytest.mark.asyncio
    async def test_detect_violations_clean(self, worker):
        """Test violation detection with no violations using registry API"""
        # Mock registry API results (all passed)
        mock_results = {}

        with patch("hive_orchestrator.golden_rules_worker.run_all_golden_rules") as mock_validate:
            mock_validate.return_value = (True, mock_results)

            result = await worker.detect_golden_rules_violations()

            assert result["total_count"] == 0
            assert result["auto_fixable_count"] == 0
            assert result["escalation_count"] == 0

    @pytest.mark.asyncio
    async def test_detect_violations_error(self, worker):
        """Test violation detection with validator error using registry API"""
        with patch("hive_orchestrator.golden_rules_worker.run_all_golden_rules") as mock_validate:
            mock_validate.side_effect = Exception("Validator registry failed")

            result = await worker.detect_golden_rules_violations()

            # Error cases return empty result
            assert result["total_count"] == 0
            assert result["auto_fixable_count"] == 0
            assert result["escalation_count"] == 0

    @pytest.mark.asyncio
    async def test_fix_rule_31_ruff_config(self, worker, tmp_path):
        """Test auto-fix for Rule 31 (Ruff Config)"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[tool.poetry]
name = "test-package"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.11"
""")

        success = await worker.fix_rule_31_ruff_config(pyproject)

        assert success is True
        content = pyproject.read_text()
        assert "[tool.ruff]" in content
        assert "line-length = 120" in content

    @pytest.mark.asyncio
    async def test_fix_rule_31_already_present(self, worker, tmp_path):
        """Test Rule 31 fix skips if config already present"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[tool.poetry]
name = "test-package"

[tool.ruff]
line-length = 100
""")

        success = await worker.fix_rule_31_ruff_config(pyproject)

        assert success is False  # No changes needed - returns False
        content = pyproject.read_text()
        assert content.count("[tool.ruff]") == 1  # Only one instance

    @pytest.mark.asyncio
    async def test_fix_rule_32_python_version_poetry(self, worker, tmp_path):
        """Test auto-fix for Rule 32 (Python Version) - Poetry format"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[tool.poetry]
name = "test-package"

[tool.poetry.dependencies]
requests = "^2.31.0"
""")

        success = await worker.fix_rule_32_python_version(pyproject)

        assert success is True
        content = pyproject.read_text()
        assert 'python = "^3.11"' in content

    @pytest.mark.asyncio
    async def test_fix_rule_32_python_version_pep621(self, worker, tmp_path):
        """Test auto-fix for Rule 32 (Python Version) - PEP 621 format"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "test-package"

[project.dependencies]
requests = ">=2.31.0"
""")

        success = await worker.fix_rule_32_python_version(pyproject)

        assert success is True
        content = pyproject.read_text()
        assert 'requires-python = ">=3.11"' in content

    @pytest.mark.asyncio
    async def test_fix_rule_32_already_present(self, worker, tmp_path):
        """Test Rule 32 fix skips if version already specified"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[tool.poetry.dependencies]
python = "^3.11"
""")

        success = await worker.fix_rule_32_python_version(pyproject)

        assert success is False  # No changes needed - returns False

    @pytest.mark.asyncio
    async def test_fix_rule_9_logging(self, worker, tmp_path):
        """Test auto-fix for Rule 9 (Logging Standards)"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""def process_data():
    print("Processing data")
    result = calculate()
    print(f"Result: {result}")
    return result
""")

        success = await worker.fix_rule_9_logging(test_file)

        assert success is True
        content = test_file.read_text()
        assert "from hive_logging import get_logger" in content
        assert "logger = get_logger(__name__)" in content
        assert 'logger.info("Processing data")' in content
        assert "print(" not in content

    @pytest.mark.asyncio
    async def test_fix_rule_9_already_using_logger(self, worker, tmp_path):
        """Test Rule 9 fix skips if already using logger"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""from hive_logging import get_logger

logger = get_logger(__name__)

def process():
    logger.info("Processing")
""")

        success = await worker.fix_rule_9_logging(test_file)

        assert success is False  # No changes needed - returns False
        content = test_file.read_text()
        assert content.count("from hive_logging import get_logger") == 1

    @pytest.mark.asyncio
    async def test_apply_fixes_multiple_rules(self, worker):
        """Test applying fixes for multiple rules"""
        violations = [
            {"rule_id": "31", "file": "pyproject.toml"},
            {"rule_id": "32", "file": "pyproject.toml"},
            {"rule_id": "9", "file": "test.py"},
        ]

        # Create test files in worker.workspace
        (worker.workspace / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'\n\n[tool.poetry.dependencies]\n")
        (worker.workspace / "test.py").write_text('print("test")')

        result = await worker.apply_golden_rules_fixes(violations)

        assert result["success"] is True
        assert result["violations_fixed"] >= 2  # At least Rule 31 and 32

    @pytest.mark.asyncio
    async def test_apply_fixes_with_escalations(self, worker):
        """Test applying fixes escalates complex rules"""
        violations = [
            {"rule_id": "37", "file": "config.py"},  # Complex - requires escalation
            {"rule_id": "31", "file": "pyproject.toml"},  # Simple - auto-fixable
        ]

        # Create files in workspace
        (worker.workspace / "config.py").write_text("# config file")
        (worker.workspace / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'")

        result = await worker.apply_golden_rules_fixes(violations)

        assert len(result["escalations"]) == 1  # Rule 37 escalated
        assert result["escalations"][0]["rule_id"] == "37"

    @pytest.mark.asyncio
    async def test_process_task_success(self, worker, sample_task):
        """Test complete task processing workflow"""
        with (
            patch.object(
                worker,
                "detect_golden_rules_violations",
                return_value={
                    "total_count": 2,
                    "auto_fixable_count": 2,
                    "escalation_count": 0,
                    "violations": [{"rule_id": "31", "file": "pyproject.toml"}],
                },
            ),
            patch.object(
                worker,
                "apply_golden_rules_fixes",
                return_value={
                    "success": True,
                    "violations_fixed": 2,
                    "violations_remaining": 0,
                    "fixed_files": ["pyproject.toml"],
                    "escalations": [],
                },
            ),
            patch.object(worker, "commit_fixes", return_value=True),
            patch.object(worker.event_bus, "publish", new=AsyncMock()),
        ):
            result = await worker.process_golden_rules_task(sample_task)

            assert result["status"] == "success"
            assert result["violations_fixed"] == 2
            assert len(result["escalations"]) == 0

    @pytest.mark.asyncio
    async def test_process_task_with_escalations(self, worker, sample_task):
        """Test task processing with escalations"""
        with (
            patch.object(
                worker,
                "detect_golden_rules_violations",
                return_value={
                    "total_count": 3,
                    "auto_fixable_count": 1,
                    "escalation_count": 2,
                    "violations": [
                        {"rule_id": "37", "file": "config.py"},
                        {"rule_id": "31", "file": "pyproject.toml"},
                    ],
                },
            ),
            patch.object(
                worker,
                "apply_golden_rules_fixes",
                return_value={
                    "success": True,
                    "violations_fixed": 1,
                    "violations_remaining": 2,
                    "fixed_files": ["pyproject.toml"],
                    "escalations": [
                        {"rule_id": "37", "reason": "Complex config migration"},
                        {"rule_id": "37", "reason": "Complex config migration"},
                    ],
                },
            ),
            patch.object(worker, "commit_fixes", return_value=True),
            patch.object(worker, "escalate_issue", new=AsyncMock()),
            patch.object(worker.event_bus, "publish", new=AsyncMock()),
        ):
            result = await worker.process_golden_rules_task(sample_task)

            assert result["status"] == "escalated"
            assert len(result["escalations"]) == 2
            assert worker.escalate_issue.call_count == 2

    @pytest.mark.asyncio
    async def test_process_task_no_violations(self, worker, sample_task):
        """Test task processing with clean codebase"""
        with (
            patch.object(
                worker,
                "detect_golden_rules_violations",
                return_value={
                    "total_count": 0,
                    "auto_fixable_count": 0,
                    "escalation_count": 0,
                    "violations": [],
                },
            ),
            patch.object(worker.event_bus, "publish", new=AsyncMock()),
        ):
            result = await worker.process_golden_rules_task(sample_task)

            assert result["status"] == "success"
            assert result["violations_fixed"] == 0
            assert result["violations_remaining"] == 0

    @pytest.mark.asyncio
    async def test_process_task_detection_error(self, worker, sample_task):
        """Test task processing when detection fails"""
        # Mock detect to raise exception (real error case)
        with (
            patch.object(
                worker,
                "detect_golden_rules_violations",
                side_effect=Exception("Validator script failed"),
            ),
            patch.object(worker.event_bus, "publish", new=AsyncMock()),
        ):
            result = await worker.process_golden_rules_task(sample_task)

            assert result["status"] == "failed"
            assert "error" in result
            assert "Validator script failed" in result["error"]

    @pytest.mark.asyncio
    async def test_commit_fixes_integration(self, worker, tmp_path):
        """Test git commit integration"""
        test_files = [tmp_path / "pyproject.toml", tmp_path / "test.py"]
        for f in test_files:
            f.write_text("# fixed content")

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            success = await worker.commit_fixes(test_files, "task-gr-123")

            assert success is True
            # Verify git commands called
            assert mock_subprocess.call_count >= 2  # git add + git commit

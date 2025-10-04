"""Unit Tests for QA Worker Core

Tests autonomous QA worker functionality:
- Violation detection
- Auto-fix logic
- Event bus integration
- Git commit operations
- Escalation handling
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from hive_orchestration.events import WorkerHeartbeat
from hive_orchestration.models.task import Task
from hive_orchestrator.qa_worker import QAWorkerCore


class TestQAWorkerCore:
    """Test suite for QAWorkerCore"""

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create temporary workspace directory"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return workspace

    @pytest.fixture
    def qa_worker(self, temp_workspace):
        """Create QA worker instance"""
        return QAWorkerCore(
            worker_id="test-qa-worker",
            workspace=temp_workspace,
            config={"test_mode": True},
        )

    @pytest.fixture
    def sample_python_file(self, temp_workspace):
        """Create sample Python file with violations"""
        file_path = temp_workspace / "sample.py"
        file_path.write_text(
            """
def test_function():
    x = 1  # F841: local variable 'x' is assigned to but never used
    print("Hello")  # Line will be flagged by some linters
    return True
""",
        )
        return file_path

    @pytest.mark.asyncio
    async def test_worker_initialization(self, qa_worker, temp_workspace):
        """Test worker initializes correctly"""
        assert qa_worker.worker_id == "test-qa-worker"
        assert qa_worker.workspace == temp_workspace
        assert qa_worker.tasks_completed == 0
        assert qa_worker.violations_fixed == 0
        assert qa_worker.escalations == 0

    @pytest.mark.asyncio
    async def test_emit_heartbeat(self, qa_worker):
        """Test worker emits heartbeat events"""
        with patch.object(qa_worker.event_bus, "publish", new=AsyncMock()) as mock_publish:
            await qa_worker.emit_heartbeat()

            mock_publish.assert_called_once()
            call_args = mock_publish.call_args[0][0]

            assert isinstance(call_args, WorkerHeartbeat)
            assert call_args.worker_id == "test-qa-worker"
            assert call_args.event_type == "heartbeat"
            assert "status" in call_args.payload
            assert "tasks_completed" in call_args.payload

    @pytest.mark.asyncio
    async def test_detect_violations_no_ruff(self, qa_worker, sample_python_file):
        """Test violation detection when ruff is not available"""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("ruff not found"),
        ):
            result = await qa_worker.detect_violations(sample_python_file)

            assert result["total_count"] == 0
            assert result["auto_fixable"] is False

    @pytest.mark.asyncio
    async def test_detect_violations_clean_file(self, qa_worker, temp_workspace):
        """Test violation detection on clean file"""
        clean_file = temp_workspace / "clean.py"
        clean_file.write_text(
            """
def clean_function():
    return True
""",
        )

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await qa_worker.detect_violations(clean_file)

            assert result["total_count"] == 0
            assert result["auto_fixable"] is True

    @pytest.mark.asyncio
    async def test_detect_violations_with_violations(self, qa_worker, sample_python_file):
        """Test violation detection with actual violations"""
        violations_json = json.dumps(
            [
                {
                    "code": "F841",
                    "message": "Local variable 'x' is assigned to but never used",
                    "location": {"row": 3, "column": 5},
                },
                {
                    "code": "E501",
                    "message": "Line too long (92 > 88 characters)",
                    "location": {"row": 4, "column": 1},
                },
            ],
        )

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (violations_json.encode(), b"")
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await qa_worker.detect_violations(sample_python_file)

            assert result["total_count"] == 2
            assert len(result["violations"]) == 2
            assert result["violations"][0]["code"] == "F841"
            assert result["violations"][1]["code"] == "E501"

    @pytest.mark.asyncio
    async def test_apply_auto_fixes_success(self, qa_worker, sample_python_file):
        """Test successful auto-fix application"""
        # Mock before violations
        before_violations = json.dumps([{"code": "F841", "location": {"row": 3, "column": 5}}])
        # Mock after violations (empty - all fixed)
        after_violations = json.dumps([])

        call_count = 0

        async def mock_subprocess(*args, **kwargs):
            nonlocal call_count
            mock_process = AsyncMock()

            if call_count == 0:
                # First call - detect_violations before fix
                mock_process.communicate.return_value = (before_violations.encode(), b"")
                mock_process.returncode = 1
            elif call_count == 1:
                # Second call - ruff --fix
                mock_process.communicate.return_value = (b"", b"")
                mock_process.returncode = 0
            else:
                # Third call - detect_violations after fix
                mock_process.communicate.return_value = (after_violations.encode(), b"")
                mock_process.returncode = 0

            call_count += 1
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await qa_worker.apply_auto_fixes(sample_python_file)

            assert result["success"] is True
            assert result["violations_fixed"] == 1
            assert result["violations_remaining"] == 0
            assert result["fix_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_apply_auto_fixes_partial_success(self, qa_worker, sample_python_file):
        """Test auto-fix with some violations remaining"""
        before_violations = json.dumps(
            [
                {"code": "F841", "location": {"row": 3, "column": 5}},
                {"code": "E501", "location": {"row": 4, "column": 1}},
                {"code": "C901", "location": {"row": 5, "column": 1}},
            ],
        )
        after_violations = json.dumps([{"code": "C901", "location": {"row": 5, "column": 1}}])

        call_count = 0

        async def mock_subprocess(*args, **kwargs):
            nonlocal call_count
            mock_process = AsyncMock()

            if call_count == 0:
                # Before fix
                mock_process.communicate.return_value = (before_violations.encode(), b"")
                mock_process.returncode = 1
            elif call_count == 1:
                # ruff --fix
                mock_process.communicate.return_value = (b"", b"")
                mock_process.returncode = 0
            else:
                # After fix
                mock_process.communicate.return_value = (after_violations.encode(), b"")
                mock_process.returncode = 1

            call_count += 1
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await qa_worker.apply_auto_fixes(sample_python_file)

            assert result["success"] is False
            assert result["violations_fixed"] == 2
            assert result["violations_remaining"] == 1

    @pytest.mark.asyncio
    async def test_commit_fixes_success(self, qa_worker, temp_workspace):
        """Test successful git commit of fixes"""
        test_file = temp_workspace / "test.py"
        test_file.write_text("# test")

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await qa_worker.commit_fixes([test_file], "task-123")

            assert result is True

    @pytest.mark.asyncio
    async def test_commit_fixes_failure(self, qa_worker, temp_workspace):
        """Test failed git commit"""
        test_file = temp_workspace / "test.py"
        test_file.write_text("# test")

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Commit failed")
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await qa_worker.commit_fixes([test_file], "task-123")

            assert result is False

    @pytest.mark.asyncio
    async def test_escalate_issue(self, qa_worker):
        """Test issue escalation"""
        with patch.object(qa_worker.event_bus, "publish", new=AsyncMock()) as mock_publish:
            await qa_worker.escalate_issue(
                task_id="task-123",
                reason="Cannot auto-fix C901 complexity",
                details={"violations": 1, "files": ["test.py"]},
            )

            mock_publish.assert_called_once()
            call_args = mock_publish.call_args[0][0]

            assert call_args.task_id == "task-123"
            assert call_args.event_type == "escalation_needed"
            assert "reason" in call_args.payload
            assert call_args.payload["reason"] == "Cannot auto-fix C901 complexity"

            assert qa_worker.escalations == 1

    @pytest.mark.asyncio
    async def test_process_qa_task_success(self, qa_worker, temp_workspace):
        """Test successful QA task processing"""
        test_file = temp_workspace / "test.py"
        test_file.write_text("# test")

        task = Task(
            id="task-123",
            title="Fix ruff violations",
            description="Auto-fix ruff violations in test.py",
            metadata={"file_paths": ["test.py"]},
        )

        # Mock all violations fixed
        violations_json = json.dumps([])

        call_count = 0

        async def mock_subprocess(*args, **kwargs):
            nonlocal call_count
            mock_process = AsyncMock()

            if call_count <= 1:
                # detect_violations calls (before and after)
                mock_process.communicate.return_value = (violations_json.encode(), b"")
                mock_process.returncode = 0
            else:
                # git operations
                mock_process.communicate.return_value = (b"", b"")
                mock_process.returncode = 0

            call_count += 1
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with patch.object(qa_worker.event_bus, "publish", new=AsyncMock()):
                result = await qa_worker.process_qa_task(task)

                assert result["status"] == "success"
                assert result["files_processed"] == 1
                assert qa_worker.tasks_completed == 1

    @pytest.mark.asyncio
    async def test_process_qa_task_with_escalation(self, qa_worker, temp_workspace):
        """Test QA task processing with escalation"""
        test_file = temp_workspace / "test.py"
        test_file.write_text("# test")

        task = Task(
            id="task-123",
            title="Fix ruff violations",
            description="Auto-fix ruff violations",
            metadata={"file_paths": ["test.py"]},
        )

        # Mock violations remaining after fix
        remaining_violations = json.dumps([{"code": "C901", "location": {"row": 1, "column": 1}}])

        before_violations = json.dumps(
            [
                {"code": "F841", "location": {"row": 1, "column": 1}},
                {"code": "C901", "location": {"row": 1, "column": 1}},
            ],
        )

        call_count = 0

        async def mock_subprocess(*args, **kwargs):
            nonlocal call_count
            mock_process = AsyncMock()

            if call_count == 0:
                # Before fix
                mock_process.communicate.return_value = (before_violations.encode(), b"")
                mock_process.returncode = 1
            elif call_count == 1:
                # ruff --fix
                mock_process.communicate.return_value = (b"", b"")
                mock_process.returncode = 0
            elif call_count == 2:
                # After fix
                mock_process.communicate.return_value = (remaining_violations.encode(), b"")
                mock_process.returncode = 1
            else:
                # git operations
                mock_process.communicate.return_value = (b"", b"")
                mock_process.returncode = 0

            call_count += 1
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with patch.object(qa_worker.event_bus, "publish", new=AsyncMock()):
                result = await qa_worker.process_qa_task(task)

                assert result["status"] == "escalated"
                assert result["violations_remaining"] == 1
                assert qa_worker.escalations == 1

    @pytest.mark.asyncio
    async def test_process_qa_task_file_not_found(self, qa_worker, temp_workspace):
        """Test QA task processing with missing file"""
        task = Task(
            id="task-123",
            title="Fix ruff violations",
            description="Auto-fix ruff violations",
            metadata={"file_paths": ["nonexistent.py"]},
        )

        with patch.object(qa_worker.event_bus, "publish", new=AsyncMock()):
            result = await qa_worker.process_qa_task(task)

            # Should complete but with no files processed
            assert result["status"] == "success"
            assert result["files_processed"] == 0
            assert result["violations_fixed"] == 0

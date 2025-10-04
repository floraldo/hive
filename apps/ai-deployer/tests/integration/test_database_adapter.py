"""Tests for the database adapter
"""
from unittest.mock import Mock, patch

import pytest

from ai_deployer.database_adapter import DatabaseAdapter, DeploymentDatabaseError


@pytest.fixture
def mock_connection():
    """Create a mock database connection"""
    conn = (Mock(),)
    cursor = Mock()
    conn.cursor.return_value = cursor
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=None)
    return (conn, cursor)

@pytest.fixture
def sample_task_row():
    """Create a sample task row from database"""
    return ["task-001", "Deploy App", "Deploy web application", "2024-01-15T10:00:00", "2024-01-15T10:30:00", "worker-001", 1, '{"source_path": "/tmp/app"}', '{"environment": "prod"}', "deployment_pending", 1800]

@pytest.mark.crust
class TestDatabaseAdapter:
    """Test cases for the database adapter"""

    @pytest.mark.crust
    def test_adapter_initialization(self):
        """Test adapter initialization"""
        with patch("ai_deployer.database_adapter.get_database") as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            adapter = DatabaseAdapter()
            assert adapter.db == mock_db

    @pytest.mark.crust
    def test_get_deployment_pending_tasks_success(self, mock_connection, sample_task_row):
        """Test successful retrieval of deployment pending tasks"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.fetchall.return_value = [sample_task_row]
            adapter = (DatabaseAdapter(),)
            tasks = adapter.get_deployment_pending_tasks()
            assert len(tasks) == 1
            task = tasks[0]
            assert task["id"] == "task-001"
            assert task["title"] == "Deploy App"
            assert task["status"] == "deployment_pending"
            assert task["task_data"]["source_path"] == "/tmp/app"
            assert task["metadata"]["environment"] == "prod"
            cursor.execute.assert_called_once()
            sql_call = cursor.execute.call_args[0][0]
            assert "deployment_pending" in sql_call
            assert "ORDER BY priority DESC" in sql_call

    @pytest.mark.crust
    def test_get_deployment_pending_tasks_empty(self, mock_connection):
        """Test retrieval with no pending tasks"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.fetchall.return_value = []
            adapter = (DatabaseAdapter(),)
            tasks = adapter.get_deployment_pending_tasks()
            assert len(tasks) == 0

    @pytest.mark.crust
    def test_get_deployment_pending_tasks_database_error(self, mock_connection):
        """Test handling of database errors"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.execute.side_effect = Exception("Database connection failed")
            adapter = DatabaseAdapter()
            with pytest.raises(DeploymentDatabaseError) as exc_info:
                adapter.get_deployment_pending_tasks()
            assert "Failed to get deployment tasks" in str(exc_info.value)

    @pytest.mark.crust
    def test_update_task_status_success(self, mock_connection):
        """Test successful task status update"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.rowcount = 1
            adapter = (DatabaseAdapter(),)
            result = adapter.update_task_status("task-001", "deployed")
            assert result is True
            cursor.execute.assert_called_once()
            conn.commit.assert_called_once()
            sql_call = cursor.execute.call_args
            assert "deployed" in sql_call[0][1]
            assert "task-001" in sql_call[0][1]

    @pytest.mark.crust
    def test_update_task_status_with_metadata(self, mock_connection):
        """Test task status update with metadata"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.fetchone.return_value = ['{"existing": "data"}']
            cursor.rowcount = 1
            adapter = (DatabaseAdapter(),)
            metadata = {"deployment_id": "deploy-123", "duration": 45.2}
            result = adapter.update_task_status("task-001", "deployed", metadata)
            assert result is True
            execute_calls = cursor.execute.call_args_list
            assert len(execute_calls) == 2
            update_call = execute_calls[1]
            assert "deployed" in update_call[0][1]

    @pytest.mark.crust
    def test_update_task_status_no_task_found(self, mock_connection):
        """Test task status update when task not found"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.rowcount = 0
            adapter = (DatabaseAdapter(),)
            result = adapter.update_task_status("nonexistent", "deployed")
            assert result is False

    @pytest.mark.crust
    def test_update_task_status_database_error(self, mock_connection):
        """Test task status update with database error"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.execute.side_effect = Exception("Database error")
            adapter = DatabaseAdapter()
            with pytest.raises(DeploymentDatabaseError):
                adapter.update_task_status("task-001", "deployed")

    @pytest.mark.crust
    def test_get_task_by_id_success(self, mock_connection, sample_task_row):
        """Test successful task retrieval by ID"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.fetchone.return_value = sample_task_row
            adapter = (DatabaseAdapter(),)
            task = adapter.get_task_by_id("task-001")
            assert task is not None
            assert task["id"] == "task-001"
            assert task["title"] == "Deploy App"
            cursor.execute.assert_called_once()
            sql_call = cursor.execute.call_args
            assert "task-001" in sql_call[0][1]

    @pytest.mark.crust
    def test_get_task_by_id_not_found(self, mock_connection):
        """Test task retrieval when task not found"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.fetchone.return_value = None
            adapter = (DatabaseAdapter(),)
            task = adapter.get_task_by_id("nonexistent")
            assert task is None

    @pytest.mark.crust
    def test_record_deployment_event_success(self, mock_connection):
        """Test successful deployment event recording"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            adapter = (DatabaseAdapter(),)
            details = {"deployment_id": "deploy-123", "strategy": "direct"}
            result = adapter.record_deployment_event("task-001", "deployment_started", details)
            assert result is True
            execute_calls = cursor.execute.call_args_list
            assert len(execute_calls) == 2
            create_table_call = execute_calls[0][0][0]
            assert "CREATE TABLE IF NOT EXISTS deployment_events" in create_table_call
            insert_call = execute_calls[1]
            assert "task-001" in insert_call[0][1]
            assert "deployment_started" in insert_call[0][1]

    @pytest.mark.crust
    def test_record_deployment_event_database_error(self, mock_connection):
        """Test deployment event recording with database error"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.execute.side_effect = Exception("Database error")
            adapter = DatabaseAdapter()
            with pytest.raises(DeploymentDatabaseError):
                adapter.record_deployment_event("task-001", "event", {})

    @pytest.mark.crust
    def test_get_deployment_history_success(self, mock_connection):
        """Test successful deployment history retrieval"""
        conn, cursor = mock_connection
        event_rows = [("deployment_started", '{"deployment_id": "deploy-123"}', "2024-01-15T10:00:00"), ("deployment_completed", '{"duration": 45.2}', "2024-01-15T10:05:00")]
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.fetchall.return_value = event_rows
            adapter = (DatabaseAdapter(),)
            history = adapter.get_deployment_history("task-001")
            assert len(history) == 2
            assert history[0]["event_type"] == "deployment_started"
            assert history[0]["details"]["deployment_id"] == "deploy-123"
            assert history[1]["event_type"] == "deployment_completed"
            cursor.execute.assert_called_once()
            sql_call = cursor.execute.call_args
            assert "task-001" in sql_call[0][1]

    @pytest.mark.crust
    def test_get_deployment_history_empty(self, mock_connection):
        """Test deployment history retrieval with no events"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.fetchall.return_value = []
            adapter = (DatabaseAdapter(),)
            history = adapter.get_deployment_history("task-001")
            assert len(history) == 0

    @pytest.mark.crust
    def test_get_deployment_stats_success(self, mock_connection):
        """Test successful deployment statistics retrieval"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.fetchall.return_value = [("deployed", 15), ("deployment_failed", 2), ("deploying", 1)]
            cursor.fetchone.return_value = [8]
            adapter = (DatabaseAdapter(),)
            stats = adapter.get_deployment_stats()
            assert stats["status_counts"]["deployed"] == 15
            assert stats["status_counts"]["deployment_failed"] == 2
            assert stats["recent_deployments"] == 8
            assert "timestamp" in stats
            assert cursor.execute.call_count == 2

    @pytest.mark.crust
    def test_parse_json_field_valid_json(self):
        """Test JSON field parsing with valid JSON"""
        adapter = (DatabaseAdapter(),)
        json_str = '{"key": "value", "number": 42}'
        result = adapter._parse_json_field(json_str)
        assert result == {"key": "value", "number": 42}

    @pytest.mark.crust
    def test_parse_json_field_invalid_json(self):
        """Test JSON field parsing with invalid JSON"""
        adapter = (DatabaseAdapter(),)
        invalid_json = ('{"invalid": json}',)
        result = adapter._parse_json_field(invalid_json)
        assert result == {}

    @pytest.mark.crust
    def test_parse_json_field_none_value(self):
        """Test JSON field parsing with None value"""
        adapter = (DatabaseAdapter(),)
        result = adapter._parse_json_field(None)
        assert result == {}

    @pytest.mark.crust
    def test_parse_json_field_empty_string(self):
        """Test JSON field parsing with empty string"""
        adapter = (DatabaseAdapter(),)
        result = adapter._parse_json_field("")
        assert result == {}

    @pytest.mark.crust
    @pytest.mark.integration
    def test_full_workflow_integration(self, mock_connection):
        """Integration test for full database workflow"""
        conn, cursor = mock_connection
        with patch("ai_deployer.database_adapter.get_pooled_connection", return_value=conn):
            cursor.fetchall.return_value = []
            cursor.rowcount = 1
            cursor.fetchone.return_value = [None]
            adapter = DatabaseAdapter()
            tasks = adapter.get_deployment_pending_tasks()
            assert len(tasks) == 0
            status_updated = adapter.update_task_status("task-001", "deployed")
            assert status_updated is True
            event_recorded = adapter.record_deployment_event("task-001", "deployment_completed", {"success": True})
            assert event_recorded is True

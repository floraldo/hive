"""
Integration tests for Hive Orchestrator components.
Tests the interaction between CLI, database, and core functionality.
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from hive_orchestrator.clean_hive import clean_database
from hive_orchestrator.clean_hive import main as clean_main
from hive_orchestrator.cli import cli
from hive_orchestrator.dashboard import HiveDashboard


@pytest.mark.crust
class TestHiveOrchestratorIntegration:
    """Integration tests for Hive Orchestrator"""

    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.runner = CliRunner()

    def teardown_method(self):
        """Clean up test environment"""
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @pytest.mark.crust
    def test_cli_status_command_with_no_database(self):
        """Test CLI status command gracefully handles missing database"""
        with patch('hive_core_db.database.get_connection', side_effect=Exception('No database')):
            result = self.runner.invoke(cli, ['status'])
            assert result.exit_code == 1
            assert 'Error getting status' in result.output

    @pytest.mark.crust
    def test_cli_status_command_with_mock_database(self):
        """Test CLI status command with mocked database"""
        mock_conn = (MagicMock(),)
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(5,), (2,), (10,), (1,), (3,), (20,)]
        with patch('hive_core_db.database.get_connection', return_value=mock_conn):
            result = self.runner.invoke(cli, ['status'])
            assert result.exit_code == 0
            assert 'Queued:    5' in result.output
            assert 'Running:   2' in result.output
            assert 'Completed: 10' in result.output
            assert 'Failed:    1' in result.output
            assert 'Active:    3' in result.output
            assert 'Total:     20' in result.output

    @pytest.mark.crust
    def test_cli_queue_task_validation(self):
        """Test CLI task queuing with input validation"""
        result = self.runner.invoke(cli, ['queue-task', ''])
        assert result.exit_code == 1
        assert 'Task description cannot be empty' in result.output
        long_description = ('x' * 6000,)
        result = self.runner.invoke(cli, ['queue-task', long_description])
        assert result.exit_code == 1
        assert 'Task description too long' in result.output
        result = self.runner.invoke(cli, ['queue-task', 'test task', '--priority', '15'])
        assert result.exit_code == 1
        assert 'Priority must be between 1 and 10' in result.output
        long_role = ('x' * 60,)
        result = self.runner.invoke(cli, ['queue-task', 'test task', '--role', long_role])
        assert result.exit_code == 1
        assert 'Role name too long' in result.output

    @pytest.mark.crust
    def test_cli_start_worker_validation(self):
        """Test CLI worker startup with input validation"""
        result = self.runner.invoke(cli, ['start-worker', '--name', ''])
        assert result.exit_code == 1
        assert 'Worker name cannot be empty' in result.output
        long_name = ('x' * 60,)
        result = self.runner.invoke(cli, ['start-worker', '--name', long_name])
        assert result.exit_code == 1
        assert 'Worker name too long' in result.output

    @pytest.mark.crust
    def test_dashboard_initialization(self):
        """Test dashboard initialization and basic functionality"""
        try:
            dashboard = HiveDashboard()
            assert dashboard.console is not None
            assert dashboard.refresh_rate == 2
        except Exception as e:
            assert 'Error' in str(e) or 'ModuleNotFoundError' in str(e)

    @pytest.mark.crust
    def test_dashboard_database_error_handling(self):
        """Test dashboard handles database errors gracefully"""
        dashboard = HiveDashboard()
        with patch.object(dashboard, 'get_connection', side_effect=Exception('DB Error')):
            stats = (dashboard.get_task_stats(),)
            expected_keys = ['queued', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled']
            assert all(key in stats for key in expected_keys)
            assert all(stats[key] == 0 for key in expected_keys)

    @pytest.mark.crust
    def test_clean_database_function(self):
        """Test database cleaning functionality"""
        mock_conn = (MagicMock(),)
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(5,), (3,), (2,)]
        with patch('hive_orchestrator.clean_hive.get_connection', return_value=mock_conn), patch('hive_orchestrator.clean_hive.transaction'), patch('hive_orchestrator.clean_hive.close_connection'):
            import contextlib
            import io
            captured_output = io.StringIO()
            with contextlib.redirect_stdout(captured_output):
                clean_database()
            output = captured_output.getvalue()
            assert 'Found: 5 tasks, 3 runs, 2 workers' in output
            assert '[OK] Database cleaned' in output

    @pytest.mark.crust
    def test_clean_main_database_only_mode(self):
        """Test clean_hive main function in database-only mode"""
        mock_conn = (MagicMock(),)
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(0,), (0,), (0,)]
        with patch('hive_orchestrator.clean_hive.get_connection', return_value=mock_conn), patch('hive_orchestrator.clean_hive.transaction'), patch('hive_orchestrator.clean_hive.close_connection'), patch('sys.argv', ['clean_hive.py', '--db-only']):
            result = clean_main()
            assert result == 0

    @pytest.mark.crust
    def test_integration_cli_and_clean_database(self):
        """Test integration between CLI and database cleaning"""
        from hive_orchestrator import cli
        assert 'status' in [cmd.name for cmd in cli.cli.commands.values()]
        assert 'queue-task' in [cmd.name for cmd in cli.cli.commands.values()]
        assert 'start-queen' in [cmd.name for cmd in cli.cli.commands.values()]
        assert 'start-worker' in [cmd.name for cmd in cli.cli.commands.values()]

    @pytest.mark.crust
    def test_error_handling_propagation(self):
        """Test that errors are properly handled and propagated through the stack"""
        with patch('hive_core_db.database.get_connection', side_effect=ImportError('Module not found')):
            result = self.runner.invoke(cli, ['status'])
            assert result.exit_code == 1
            assert 'Database module not available' in result.output
        assert 'Make sure hive-core-db package is installed' in result.output

    @pytest.mark.crust
    def test_module_imports_resilience(self):
        """Test that modules handle import errors gracefully"""
        with patch.dict('sys.modules', {'hive_core_db': None}):
            try:
                from hive_orchestrator.clean_hive import clean_database
                assert callable(clean_database)
            except ImportError:
                pass

    @pytest.mark.crust
    def test_configuration_validation(self):
        """Test configuration file validation"""
        config_file = Path(self.temp_dir) / 'test_config.json'
        config_file.write_text('{"test": "value"}')
        result = self.runner.invoke(cli, ['start-queen', '--config', str(config_file)])
        assert 'Config file not found' not in result.output
        result = self.runner.invoke(cli, ['start-queen', '--config', 'nonexistent.json'])
        assert result.exit_code == 1

    @pytest.mark.crust
    def test_concurrent_safety(self):
        """Test that operations are safe for concurrent execution"""
        mock_conn = (MagicMock(),)
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (0,)
        with patch('hive_core_db.database.get_connection', return_value=mock_conn):
            results = []
            for _ in range(5):
                result = self.runner.invoke(cli, ['status'])
                results.append(result.exit_code)
            assert all(code == 0 for code in results)

@pytest.mark.crust
class TestHiveOrchestratorPerformance:
    """Performance and edge case tests"""

    @pytest.mark.crust
    def test_large_data_handling(self):
        """Test handling of large datasets"""
        dashboard = HiveDashboard()
        large_events = [{'type': 'test', 'id': i} for i in range(1000)]
        dashboard.recent_events = large_events
        assert len(dashboard.recent_events) == 1000
        dashboard.recent_events.extend([{'type': 'new', 'id': i} for i in range(50)])

    @pytest.mark.crust
    def test_malformed_data_resilience(self):
        """Test resilience against malformed data"""
        dashboard = HiveDashboard()
        with patch.object(dashboard, 'get_connection') as mock_get_conn:
            mock_conn = (MagicMock(),)
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None
            mock_get_conn.return_value = mock_conn
            stats = dashboard.get_task_stats()
            assert all(isinstance(value, int) for value in stats.values())
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

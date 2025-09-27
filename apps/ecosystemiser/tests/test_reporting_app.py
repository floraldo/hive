"""Tests for reporting Flask application."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from EcoSystemiser.reporting.app import create_app, generate_plots


@pytest.fixture
def sample_results_data():
    """Sample simulation results for testing."""
    return {
        "components": {
            "battery": {
                "type": "battery",
                "technical": {"capacity_nominal": 100},
                "economic": {"capex_per_kwh": 500}
            }
        },
        "flows": {
            "grid_import": {"values": [10, 20, 30]}
        },
        "kpis": {
            "grid_self_sufficiency": 0.8,
            "renewable_fraction": 0.6
        },
        "solver_metrics": {
            "status": "optimal",
            "solve_time": 1.234
        }
    }


@pytest.fixture
def sample_analysis_results():
    """Sample analysis results for testing."""
    return {
        "metadata": {
            "analysis_timestamp": "2024-01-01T12:00:00",
            "strategies_executed": ["technical_kpi", "economic"]
        },
        "summary": {
            "successful_analyses": 2,
            "failed_analyses": 0,
            "key_metrics": {
                "grid_self_sufficiency": 0.8,
                "renewable_fraction": 0.6
            }
        },
        "analyses": {
            "technical_kpi": {
                "grid_self_sufficiency": 0.8,
                "renewable_fraction": 0.6,
                "system_efficiency": 0.9
            },
            "economic": {
                "lcoe": 0.12,
                "npv": 50000,
                "capex_total": 150000
            }
        }
    }


@pytest.fixture
def app():
    """Create Flask app for testing."""
    test_config = {
        'TESTING': True,
        'SECRET_KEY': 'test-key'
    }
    return create_app(test_config)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestFlaskApp:
    """Test suite for Flask reporting application."""

    def test_app_creation(self):
        """Test app creation with default config."""
        app = create_app()
        assert app is not None
        assert hasattr(app, 'analyser')
        assert hasattr(app, 'plot_factory')

    def test_app_creation_with_config(self):
        """Test app creation with custom config."""
        config = {
            'TESTING': True,
            'SECRET_KEY': 'custom-key'
        }
        app = create_app(config)
        assert app.config['TESTING'] is True
        assert app.config['SECRET_KEY'] == 'custom-key'

    def test_index_route(self, client):
        """Test index route."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'EcoSystemiser Reporting' in response.data

    def test_upload_get_route(self, client):
        """Test upload GET route."""
        response = client.get('/upload')
        assert response.status_code == 200
        assert b'Upload Simulation Results' in response.data

    def test_upload_post_no_file(self, client):
        """Test upload POST with no file."""
        response = client.post('/upload')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'No file uploaded' in data['error']

    def test_upload_post_empty_filename(self, client):
        """Test upload POST with empty filename."""
        response = client.post('/upload', data={'results_file': (None, '')})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    @patch('EcoSystemiser.reporting.app.AnalyserService')
    def test_upload_post_success(self, mock_analyser_class, client, sample_results_data, sample_analysis_results):
        """Test successful file upload and analysis."""
        # Mock analyser
        mock_analyser = Mock()
        mock_analyser.analyse.return_value = sample_analysis_results
        mock_analyser_class.return_value = mock_analyser

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_results_data, f)
            f.flush()

            # Upload file
            with open(f.name, 'rb') as upload_file:
                response = client.post('/upload', data={
                    'results_file': (upload_file, 'test.json')
                })

        # Cleanup
        Path(f.name).unlink(missing_ok=True)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'session_id' in data
        assert 'summary' in data

    @patch('EcoSystemiser.reporting.app.AnalyserService')
    def test_upload_post_analysis_error(self, mock_analyser_class, client, sample_results_data):
        """Test upload with analysis error."""
        # Mock analyser to raise error
        mock_analyser = Mock()
        mock_analyser.analyse.side_effect = ValueError("Analysis failed")
        mock_analyser_class.return_value = mock_analyser

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_results_data, f)
            f.flush()

            # Upload file
            with open(f.name, 'rb') as upload_file:
                response = client.post('/upload', data={
                    'results_file': (upload_file, 'test.json')
                })

        # Cleanup
        Path(f.name).unlink(missing_ok=True)

        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data

    def test_report_route_missing_session(self, client):
        """Test report route with missing session."""
        response = client.get('/report/nonexistent')
        assert response.status_code == 404
        assert b'Session not found' in response.data

    def test_api_analyze_no_json(self, client):
        """Test API analyze endpoint with no JSON."""
        response = client.post('/api/analyze')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    @patch('EcoSystemiser.reporting.app.AnalyserService')
    def test_api_analyze_success(self, mock_analyser_class, client, sample_results_data, sample_analysis_results):
        """Test successful API analyze."""
        mock_analyser = Mock()
        mock_analyser.analyse.return_value = sample_analysis_results
        mock_analyser_class.return_value = mock_analyser

        response = client.post('/api/analyze',
                              json=sample_results_data,
                              content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'metadata' in data
        assert 'analyses' in data

    def test_api_plot_no_json(self, client):
        """Test API plot endpoint with no JSON."""
        response = client.post('/api/plot/economic_summary')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_api_plot_unknown_type(self, client):
        """Test API plot endpoint with unknown plot type."""
        response = client.post('/api/plot/unknown_plot',
                              json={},
                              content_type='application/json')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Unknown plot type' in data['error']

    def test_404_handler(self, client):
        """Test 404 error handler."""
        response = client.get('/nonexistent')
        assert response.status_code == 404
        assert b'Page not found' in response.data

    def test_error_template_rendering(self, client):
        """Test error template rendering."""
        response = client.get('/report/nonexistent')
        assert response.status_code == 404
        # Should render error template
        assert b'error' in response.data.lower()


class TestPlotGeneration:
    """Test suite for plot generation functions."""

    def test_generate_plots_empty_data(self):
        """Test plot generation with empty data."""
        plot_factory = Mock()
        plot_factory.create_technical_kpi_gauges.return_value = {}
        plot_factory.create_economic_summary_plot.return_value = {}

        plots = generate_plots(plot_factory, {}, {'analyses': {}})

        assert plots == {}

    def test_generate_plots_with_analyses(self, sample_analysis_results):
        """Test plot generation with analysis results."""
        plot_factory = Mock()
        plot_factory.create_technical_kpi_gauges.return_value = {'test': 'kpi_plot'}
        plot_factory.create_economic_summary_plot.return_value = {'test': 'economic_plot'}
        plot_factory.create_sensitivity_heatmap.return_value = {'test': 'heatmap'}
        plot_factory.create_pareto_frontier_plot.return_value = {'test': 'pareto'}

        plots = generate_plots(plot_factory, {}, sample_analysis_results)

        # Should call appropriate plot methods
        plot_factory.create_technical_kpi_gauges.assert_called_once()
        plot_factory.create_economic_summary_plot.assert_called_once()

        assert 'kpi_gauges' in plots
        assert 'economic_summary' in plots

    def test_generate_plots_with_sensitivity(self):
        """Test plot generation with sensitivity analysis."""
        analysis_results = {
            'analyses': {
                'sensitivity': {
                    'parameter_sensitivities': {},
                    'trade_off_analysis': {}
                }
            }
        }

        plot_factory = Mock()
        plot_factory.create_sensitivity_heatmap.return_value = {'test': 'heatmap'}
        plot_factory.create_pareto_frontier_plot.return_value = {'test': 'pareto'}

        plots = generate_plots(plot_factory, {}, analysis_results)

        plot_factory.create_sensitivity_heatmap.assert_called_once()
        plot_factory.create_pareto_frontier_plot.assert_called_once()

        assert 'sensitivity_heatmap' in plots
        assert 'pareto_frontier' in plots

    def test_generate_plots_with_raw_data(self, sample_results_data):
        """Test plot generation with raw simulation data."""
        plot_factory = Mock()
        plot_factory.create_kpi_dashboard.return_value = {'test': 'dashboard'}
        plot_factory.create_optimization_convergence_plot.return_value = {'test': 'convergence'}

        plots = generate_plots(plot_factory, sample_results_data, {'analyses': {}})

        # Should generate plots from raw data
        plot_factory.create_kpi_dashboard.assert_called_once()
        plot_factory.create_optimization_convergence_plot.assert_called_once()

    def test_error_handling_in_plot_generation(self):
        """Test error handling in plot generation."""
        plot_factory = Mock()
        plot_factory.create_technical_kpi_gauges.side_effect = Exception("Plot error")

        analysis_results = {
            'analyses': {
                'technical_kpi': {}
            }
        }

        # Should not crash even if plot generation fails
        plots = generate_plots(plot_factory, {}, analysis_results)

        # Should still be a dict, just missing the failed plot
        assert isinstance(plots, dict)


class TestConfigurationHandling:
    """Test configuration and initialization."""

    def test_default_configuration(self):
        """Test default app configuration."""
        app = create_app()

        assert 'SECRET_KEY' in app.config
        assert 'MAX_CONTENT_LENGTH' in app.config
        assert app.config['MAX_CONTENT_LENGTH'] == 16 * 1024 * 1024

    def test_custom_configuration_override(self):
        """Test custom configuration override."""
        custom_config = {
            'SECRET_KEY': 'custom-secret',
            'MAX_CONTENT_LENGTH': 8 * 1024 * 1024,
            'TESTING': True
        }

        app = create_app(custom_config)

        assert app.config['SECRET_KEY'] == 'custom-secret'
        assert app.config['MAX_CONTENT_LENGTH'] == 8 * 1024 * 1024
        assert app.config['TESTING'] is True

    def test_service_initialization(self):
        """Test that services are properly initialized."""
        app = create_app()

        assert hasattr(app, 'analyser')
        assert hasattr(app, 'plot_factory')

        # Services should be properly instantiated
        assert app.analyser is not None
        assert app.plot_factory is not None
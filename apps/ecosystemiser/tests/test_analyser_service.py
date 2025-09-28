"""Tests for AnalyserService."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from ecosystemiser.analyser.service import AnalyserService
from ecosystemiser.analyser.strategies.base import BaseAnalysis


class MockStrategy(BaseAnalysis):
    """Mock strategy for testing."""

    def __init__(self, name="mock"):
        super().__init__(name=name)

    def run(self, results_data, metadata=None):
        return {"test_metric": 42.0, "status": "success"}


class FailingStrategy(BaseAnalysis):
    """Strategy that always fails for testing error handling."""

    def __init__(self):
        super().__init__(name="failing")

    def run(self, results_data, metadata=None):
        raise ValueError("Test failure")


@pytest.fixture
def sample_results_data():
    """Sample simulation results for testing."""
    return {
        "components": {
            "battery": {
                "type": "battery",
                "technical": {"capacity_nominal": 100},
                "economic": {"capex_per_kwh": 500, "opex_per_kwh_year": 10},
            },
            "solar_pv": {
                "type": "solar_pv",
                "technical": {"capacity_nominal": 200},
                "economic": {"capex_per_kw": 1200, "opex_per_kw_year": 20},
            },
        },
        "flows": {
            "battery_charge": {"values": [10, 20, 30, 0, 0], "type": "electricity"},
            "grid_import": {"values": [5, 15, 25, 35, 45], "type": "electricity"},
        },
        "kpis": {"grid_self_sufficiency": 0.8, "renewable_fraction": 0.6},
        "solver_metrics": {
            "status": "optimal",
            "solve_time": 1.234,
            "objective_value": 1000.0,
        },
    }


@pytest.fixture
def temp_results_file(sample_results_data):
    """Create temporary results file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_results_data, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestAnalyserService:
    """Test suite for AnalyserService."""

    def test_initialization(self):
        """Test service initialization."""
        service = AnalyserService()

        assert len(service.strategies) == 3  # technical_kpi, economic, sensitivity
        assert "technical_kpi" in service.strategies
        assert "economic" in service.strategies
        assert "sensitivity" in service.strategies

    def test_register_strategy(self):
        """Test strategy registration."""
        service = AnalyserService()
        mock_strategy = MockStrategy("test_strategy")

        service.register_strategy("test", mock_strategy)

        assert "test" in service.strategies
        assert service.strategies["test"] == mock_strategy

    def test_register_invalid_strategy(self):
        """Test registration of invalid strategy type."""
        service = AnalyserService()

        with pytest.raises(TypeError, match="Strategy must inherit from BaseAnalysis"):
            service.register_strategy("invalid", "not a strategy")

    def test_analyse_with_file(self, temp_results_file):
        """Test analysis with results file."""
        service = AnalyserService()

        # Replace with mock strategies for predictable testing
        service.strategies = {
            "mock1": MockStrategy("mock1"),
            "mock2": MockStrategy("mock2"),
        }

        results = service.analyse(temp_results_file)

        assert "metadata" in results
        assert "analyses" in results
        assert "summary" in results

        assert results["metadata"]["strategies_executed"] == ["mock1", "mock2"]
        assert len(results["analyses"]) == 2
        assert results["analyses"]["mock1"]["test_metric"] == 42.0
        assert results["summary"]["successful_analyses"] == 2
        assert results["summary"]["failed_analyses"] == 0

    def test_analyse_with_specific_strategies(self, temp_results_file):
        """Test analysis with specific strategy selection."""
        service = AnalyserService()
        service.strategies = {
            "mock1": MockStrategy("mock1"),
            "mock2": MockStrategy("mock2"),
        }

        results = service.analyse(temp_results_file, strategies=["mock1"])

        assert results["metadata"]["strategies_executed"] == ["mock1"]
        assert len(results["analyses"]) == 1
        assert "mock1" in results["analyses"]
        assert "mock2" not in results["analyses"]

    def test_analyse_with_unknown_strategy(self, temp_results_file):
        """Test analysis with unknown strategy."""
        service = AnalyserService()

        with pytest.raises(ValueError, match="Unknown strategy: unknown"):
            service.analyse(temp_results_file, strategies=["unknown"])

    def test_analyse_with_failing_strategy(self, temp_results_file):
        """Test analysis with failing strategy."""
        service = AnalyserService()
        service.strategies = {
            "mock": MockStrategy("mock"),
            "failing": FailingStrategy(),
        }

        results = service.analyse(temp_results_file)

        assert results["summary"]["successful_analyses"] == 1
        assert results["summary"]["failed_analyses"] == 1
        assert "error" in results["analyses"]["failing"]
        assert results["analyses"]["failing"]["status"] == "failed"

    def test_analyse_nonexistent_file(self):
        """Test analysis with non-existent file."""
        service = AnalyserService()

        with pytest.raises(FileNotFoundError):
            service.analyse("nonexistent.json")

    def test_analyse_parametric_study(self, sample_results_data):
        """Test parametric study analysis."""
        # Create parametric study data
        parametric_data = {
            "all_results": [
                {**sample_results_data, "status": "optimal"},
                {**sample_results_data, "status": "feasible"},
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(parametric_data, f)
            temp_path = f.name

        try:
            service = AnalyserService()
            # Use real strategies for parametric study or register them
            from ecosystemiser.analyser.strategies.economic import EconomicAnalysis
            from ecosystemiser.analyser.strategies.sensitivity import (
                SensitivityAnalysis,
            )
            from ecosystemiser.analyser.strategies.technical_kpi import (
                TechnicalKPIAnalysis,
            )

            service.register_strategy("sensitivity", SensitivityAnalysis())
            service.register_strategy("economic", EconomicAnalysis())
            service.register_strategy("technical_kpi", TechnicalKPIAnalysis())

            results = service.analyse_parametric_study(temp_path)

            assert "analyses" in results
            assert results["metadata"]["strategies_executed"] == [
                "sensitivity",
                "economic",
                "technical_kpi",
            ]

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_analyse_parametric_study_invalid_data(self, temp_results_file):
        """Test parametric study with invalid data."""
        service = AnalyserService()

        with pytest.raises(
            ValueError, match="does not contain parametric study results"
        ):
            service.analyse_parametric_study(temp_results_file)

    def test_save_analysis(self, temp_results_file):
        """Test saving analysis results."""
        service = AnalyserService()
        service.strategies = {"mock": MockStrategy("mock")}

        results = service.analyse(temp_results_file)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            service.save_analysis(results, output_path)

            assert Path(output_path).exists()

            # Verify saved content
            with open(output_path, "r") as f:
                saved_data = json.load(f)

            assert saved_data["metadata"] == results["metadata"]
            assert saved_data["analyses"] == results["analyses"]

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_create_summary(self):
        """Test summary creation."""
        service = AnalyserService()

        analyses = {
            "technical_kpi": {
                "grid_self_sufficiency": 0.8,
                "renewable_fraction": 0.6,
                "system_efficiency": 0.9,
            },
            "economic": {"lcoe": 0.12, "npv": 50000, "payback_period_years": 8.5},
            "failing": {"error": "Test error", "status": "failed"},
        }

        summary = service._create_summary(analyses)

        assert summary["successful_analyses"] == 2
        assert summary["failed_analyses"] == 1
        assert summary["key_metrics"]["grid_self_sufficiency"] == 0.8
        assert summary["key_metrics"]["lcoe"] == 0.12

    @patch("EcoSystemiser.analyser.service.logger")
    def test_logging(self, mock_logger, temp_results_file):
        """Test that appropriate logging occurs."""
        service = AnalyserService()
        service.strategies = {"mock": MockStrategy("mock")}

        service.analyse(temp_results_file)

        # Verify logging calls
        assert mock_logger.info.called
        mock_logger.info.assert_any_call("Executing strategy: mock")
        mock_logger.info.assert_any_call("Successfully executed strategy: mock")

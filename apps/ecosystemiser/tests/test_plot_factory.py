"""Tests for PlotFactory."""

from unittest.mock import Mock

import numpy as np
import pytest
from ecosystemiser.datavis.plot_factory import PlotFactory


@pytest.fixture
def sample_economic_data():
    """Sample economic analysis data for testing."""
    return {
        "capex_total": 150000,
        "opex_total": 50000,
        "opex_annual": 2500,
        "lcoe": 0.12,
        "npv": 50000,
        "payback_period_years": 8.5,
        "component_costs": {
            "battery": {"capex": 50000, "opex_annual": 1000},
            "solar_pv": {"capex": 100000, "opex_annual": 1500},
        },
    }


@pytest.fixture
def sample_sensitivity_data():
    """Sample sensitivity analysis data for testing."""
    return {
        "parameter_sensitivities": {
            "battery_capacity": {"total_cost": 0.8, "renewable_fraction": 0.3},
            "solar_capacity": {"total_cost": 0.6, "renewable_fraction": 0.9},
        },
        "most_influential_parameters": [
            {
                "parameter": "solar_capacity",
                "average_sensitivity": 0.75,
                "max_sensitivity": 0.9,
                "most_affected_kpi": "renewable_fraction",
            }
        ],
        "trade_off_analysis": {
            "cost_renewable_correlation": -0.7,
            "pareto_frontier": [
                {"cost": 100000, "renewable": 0.4},
                {"cost": 150000, "renewable": 0.6},
                {"cost": 200000, "renewable": 0.8},
            ],
        },
    }


@pytest.fixture
def sample_kpi_data():
    """Sample KPI data for testing."""
    return {
        "grid_self_sufficiency": 0.75,
        "renewable_fraction": 0.6,
        "battery_efficiency": 0.9,
        "load_factor": 0.65,
        "system_efficiency": 0.85,
    }


@pytest.fixture
def sample_solver_metrics():
    """Sample solver metrics for testing."""
    return {"status": "optimal", "solve_time": 1.234, "objective_value": 1000.0}


class TestPlotFactory:
    """Test suite for PlotFactory."""

    def test_initialization(self):
        """Test factory initialization."""
        factory = PlotFactory()
        assert hasattr(factory, "default_layout")
        assert factory.default_layout["template"] == "plotly_white"

    def test_economic_summary_plot(self, sample_economic_data):
        """Test economic summary plot generation."""
        factory = PlotFactory()
        plot_dict = factory.create_economic_summary_plot(sample_economic_data)

        assert isinstance(plot_dict, dict)
        assert "data" in plot_dict
        assert "layout" in plot_dict
        assert plot_dict["layout"]["title"]["text"] == "Economic Analysis Summary"

        # Check that data traces are present
        assert len(plot_dict["data"]) > 0

    def test_economic_summary_plot_missing_data(self):
        """Test economic summary plot with missing data."""
        factory = PlotFactory()
        plot_dict = factory.create_economic_summary_plot({})

        # Should still create a plot structure, even with empty data
        assert isinstance(plot_dict, dict)
        assert "data" in plot_dict
        assert "layout" in plot_dict

    def test_sensitivity_heatmap(self, sample_sensitivity_data):
        """Test sensitivity heatmap generation."""
        factory = PlotFactory()
        plot_dict = factory.create_sensitivity_heatmap(sample_sensitivity_data)

        assert isinstance(plot_dict, dict)
        assert "data" in plot_dict
        assert "layout" in plot_dict
        assert plot_dict["layout"]["title"]["text"] == "Parameter Sensitivity Analysis"

        # Check heatmap data
        heatmap_data = plot_dict["data"][0]
        assert heatmap_data["type"] == "heatmap"
        assert "z" in heatmap_data  # Matrix data
        assert "x" in heatmap_data  # KPI names
        assert "y" in heatmap_data  # Parameter names

    def test_sensitivity_heatmap_no_data(self):
        """Test sensitivity heatmap with no sensitivity data."""
        factory = PlotFactory()
        plot_dict = factory.create_sensitivity_heatmap({})

        assert plot_dict == {}

    def test_pareto_frontier_plot(self, sample_sensitivity_data):
        """Test Pareto frontier plot generation."""
        factory = PlotFactory()
        plot_dict = factory.create_pareto_frontier_plot(sample_sensitivity_data)

        assert isinstance(plot_dict, dict)
        assert "data" in plot_dict
        assert "layout" in plot_dict
        assert (
            plot_dict["layout"]["title"]["text"]
            == "Cost vs Renewable Fraction Trade-off"
        )

        # Check scatter plot data
        scatter_data = plot_dict["data"][0]
        assert scatter_data["type"] == "scatter"
        assert "x" in scatter_data  # Costs
        assert "y" in scatter_data  # Renewable fractions

    def test_pareto_frontier_plot_no_data(self):
        """Test Pareto frontier plot with no data."""
        factory = PlotFactory()

        # Test with empty trade-off data
        empty_data = {"trade_off_analysis": {"pareto_frontier": []}}
        plot_dict = factory.create_pareto_frontier_plot(empty_data)
        assert plot_dict == {}

        # Test with missing trade-off data
        plot_dict = factory.create_pareto_frontier_plot({})
        assert plot_dict == {}

    def test_technical_kpi_gauges(self, sample_kpi_data):
        """Test technical KPI gauge charts."""
        factory = PlotFactory()
        plot_dict = factory.create_technical_kpi_gauges(sample_kpi_data)

        assert isinstance(plot_dict, dict)
        assert "data" in plot_dict
        assert "layout" in plot_dict
        assert (
            plot_dict["layout"]["title"]["text"] == "Technical Performance Indicators"
        )

        # Check that gauge indicators are created
        gauge_count = len(
            [trace for trace in plot_dict["data"] if trace.get("type") == "indicator"]
        )
        assert gauge_count > 0

        # Verify gauge properties
        for trace in plot_dict["data"]:
            if trace.get("type") == "indicator":
                assert "mode" in trace
                assert "gauge" in trace
                assert "value" in trace

    def test_technical_kpi_gauges_no_data(self):
        """Test KPI gauges with no matching data."""
        factory = PlotFactory()
        plot_dict = factory.create_technical_kpi_gauges({})

        assert plot_dict == {}

    def test_optimization_convergence_plot(self, sample_solver_metrics):
        """Test optimization convergence plot."""
        factory = PlotFactory()
        plot_dict = factory.create_optimization_convergence_plot(sample_solver_metrics)

        assert isinstance(plot_dict, dict)
        assert "data" in plot_dict
        assert "layout" in plot_dict
        assert plot_dict["layout"]["title"]["text"] == "Optimization Results"

        # Check indicator data
        indicator_data = plot_dict["data"][0]
        assert indicator_data["type"] == "indicator"
        assert indicator_data["value"] == sample_solver_metrics["objective_value"]

    def test_kpi_dashboard(self):
        """Test KPI dashboard creation."""
        factory = PlotFactory()

        kpis = {
            "grid_import": 1000,
            "grid_export": 200,
            "solar_generation": 800,
            "self_consumption": 0.8,
            "renewable_fraction": 0.6,
            "capex_total": 150000,
            "co2_emissions": 500,
        }

        plot_dict = factory.create_kpi_dashboard(kpis)

        assert isinstance(plot_dict, dict)
        assert "data" in plot_dict
        assert "layout" in plot_dict
        assert plot_dict["layout"]["title"]["text"] == "KPI Dashboard"

    def test_load_profile_plot(self):
        """Test load profile plot creation."""
        factory = PlotFactory()

        profiles = {
            "electricity_demand": np.array([20, 30, 40, 35, 25]),
            "solar_generation": np.array([0, 10, 30, 20, 5]),
            "wind_generation": np.array([15, 20, 10, 15, 20]),
        }

        plot_dict = factory.create_load_profile_plot(profiles)

        assert isinstance(plot_dict, dict)
        assert "data" in plot_dict
        assert "layout" in plot_dict
        assert plot_dict["layout"]["title"]["text"] == "Load and Generation Profiles"

        # Should have traces for each profile
        assert len(plot_dict["data"]) == len(profiles)

    def test_color_schemes(self, sample_economic_data):
        """Test that plots use appropriate color schemes."""
        factory = PlotFactory()
        plot_dict = factory.create_economic_summary_plot(sample_economic_data)

        # Verify layout uses default styling
        assert plot_dict["layout"]["template"] == "plotly_white"
        assert "font" in plot_dict["layout"]

    def test_plot_responsiveness(self, sample_kpi_data):
        """Test that plots are configured for responsiveness."""
        factory = PlotFactory()
        plot_dict = factory.create_technical_kpi_gauges(sample_kpi_data)

        # Check that layout includes responsive settings
        assert "margin" in plot_dict["layout"]

    def test_gauge_thresholds(self):
        """Test gauge threshold coloring."""
        factory = PlotFactory()

        # High performance KPIs
        high_kpis = {
            "grid_self_sufficiency": 0.9,
            "renewable_fraction": 0.8,
            "battery_efficiency": 0.95,
        }

        plot_dict = factory.create_technical_kpi_gauges(high_kpis)

        # Check that gauges are created with proper threshold settings
        for trace in plot_dict["data"]:
            if trace.get("type") == "indicator":
                assert "gauge" in trace
                assert "threshold" in trace["gauge"]

    def test_annotation_formatting(self, sample_sensitivity_data):
        """Test that annotations are properly formatted."""
        factory = PlotFactory()
        plot_dict = factory.create_pareto_frontier_plot(sample_sensitivity_data)

        # Check for correlation annotation
        annotations = plot_dict["layout"].get("annotations", [])
        if annotations:
            correlation_annotation = annotations[0]
            assert "text" in correlation_annotation
            assert "Correlation:" in correlation_annotation["text"]

    def test_empty_system_handling(self):
        """Test handling of empty system data."""
        factory = PlotFactory()

        empty_system = Mock()
        empty_system.components = {}
        empty_system.flows = {}

        # Should return empty dict for unsupported operations
        plot_dict = factory.create_storage_animation(empty_system)
        assert plot_dict == {}

    def test_plot_data_types(self, sample_economic_data):
        """Test that plot data uses appropriate data types."""
        factory = PlotFactory()
        plot_dict = factory.create_economic_summary_plot(sample_economic_data)

        # Verify that numeric data is properly formatted
        for trace in plot_dict["data"]:
            if "values" in trace:
                for value in trace["values"]:
                    assert isinstance(value, (int, float))

    def test_layout_configuration(self):
        """Test plot layout configuration."""
        factory = PlotFactory()

        # Test default layout properties
        assert factory.default_layout["template"] == "plotly_white"
        assert factory.default_layout["font"]["size"] == 12
        assert "margin" in factory.default_layout
        assert factory.default_layout["hovermode"] == "x unified"

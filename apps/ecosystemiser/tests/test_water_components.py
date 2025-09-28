"""Test water components integration with registry pattern."""

import os
import sys

import numpy as np
import pytest
from ecosystemiser.system_model.components.shared.registry import (
    COMPONENT_REGISTRY,
    get_component_class,
    list_registered_components,
)
from ecosystemiser.system_model.components.water import (
    RainwaterSource,
    RainwaterSourceParams,
    WaterDemand,
    WaterDemandParams,
    WaterGrid,
    WaterGridParams,
    WaterStorage,
    WaterStorageParams,
)


def test_water_components_registered():
    """Test that all water components are registered."""
    registered = list_registered_components()

    # Check that water components are registered
    assert "WaterStorage" in registered
    assert "WaterDemand" in registered
    assert "WaterGrid" in registered
    assert "RainwaterSource" in registered

    # Verify correct class mapping
    assert get_component_class("WaterStorage") == WaterStorage
    assert get_component_class("WaterDemand") == WaterDemand
    assert get_component_class("WaterGrid") == WaterGrid
    assert get_component_class("RainwaterSource") == RainwaterSource


def test_water_storage_initialization():
    """Test WaterStorage component initialization."""
    params = WaterStorageParams(
        capacity_m3=20.0,
        initial_level_m3=10.0,
        min_level_m3=1.0,
        max_flow_in_m3h=5.0,
        max_flow_out_m3h=5.0,
    )

    storage = WaterStorage("tank1", params, n=24)

    assert storage.name == "tank1"
    assert storage.type == "storage"
    assert storage.medium == "water"
    assert storage.capacity_m3 == 20.0
    assert storage.initial_level_m3 == 10.0
    assert storage.water_level[0] == 10.0


def test_water_demand_initialization():
    """Test WaterDemand component initialization."""
    params = WaterDemandParams(base_demand_m3h=0.5, peak_factor=2.0, priority_level=1)

    demand = WaterDemand("demand1", params, n=24)

    assert demand.name == "demand1"
    assert demand.type == "consumption"
    assert demand.medium == "water"
    assert demand.base_demand_m3h == 0.5
    assert demand.priority_level == 1
    assert len(demand.daily_pattern) == 24  # Default pattern created


def test_water_grid_initialization():
    """Test WaterGrid component initialization."""
    params = WaterGridParams(
        max_supply_m3h=10.0, water_price_per_m3=1.5, supply_reliability=0.99
    )

    grid = WaterGrid("grid1", params, n=24)

    assert grid.name == "grid1"
    assert grid.type == "transmission"
    assert grid.medium == "water"
    assert grid.max_supply_m3h == 10.0
    assert grid.water_price_per_m3 == 1.5
    assert grid.supply_reliability == 0.99


def test_rainwater_source_initialization():
    """Test RainwaterSource component initialization."""
    params = RainwaterSourceParams(
        catchment_area_m2=150.0, runoff_coefficient=0.85, collection_efficiency=0.90
    )

    rain = RainwaterSource("rain1", params, n=24)

    assert rain.name == "rain1"
    assert rain.type == "generation"
    assert rain.medium == "water"
    assert rain.catchment_area_m2 == 150.0
    assert rain.runoff_coefficient == 0.85
    assert len(rain.seasonal_factor) == 12  # Monthly factors


def test_water_storage_operation():
    """Test WaterStorage rule-based operation."""
    params = WaterStorageParams(
        capacity_m3=10.0,
        initial_level_m3=5.0,
        min_level_m3=1.0,
        max_flow_in_m3h=2.0,
        max_flow_out_m3h=2.0,
    )

    storage = WaterStorage("tank", params, n=24)

    # Test filling
    outflow, inflow = storage.rule_based_operation(
        water_demand=0.0, water_supply=1.5, t=0  # No demand  # Supply available
    )

    assert inflow > 0  # Should store water
    assert outflow == 0.0  # No demand to meet

    # Test drawing
    outflow, inflow = storage.rule_based_operation(
        water_demand=1.0, water_supply=0.0, t=1  # Demand exists  # No supply
    )

    assert outflow > 0  # Should supply from storage
    assert inflow == 0.0  # No supply to store


def test_water_demand_profile():
    """Test WaterDemand profile generation."""
    params = WaterDemandParams(base_demand_m3h=1.0, seasonal_variation=0.2)

    demand = WaterDemand("demand", params, n=48)  # 2 days
    demand.set_demand_profile()

    assert demand.demand_profile is not None
    assert len(demand.demand_profile) == 48
    assert np.all(demand.demand_profile >= 0)  # All positive
    assert np.max(demand.demand_profile) > demand.base_demand_m3h  # Has peaks


def test_rainwater_collection():
    """Test RainwaterSource collection calculation."""
    params = RainwaterSourceParams(
        catchment_area_m2=100.0,
        runoff_coefficient=0.85,
        collection_efficiency=0.90,
        filtration_efficiency=0.95,
    )

    rain = RainwaterSource("rain", params, n=24)

    # Set a simple rainfall profile
    rain.rainfall_profile = np.array([5.0] * 24)  # 5mm/h constant

    # Test collection
    available = rain.rule_based_operation(t=0)

    # Calculate expected: 100m² * 5mm * 0.85 * 0.90 * 0.95 / 1000
    expected = 100 * 5 * 0.85 * 0.90 * 0.95 / 1000
    assert abs(available - expected) < 0.01  # Close to expected


def test_registry_pattern_with_params_model():
    """Test that PARAMS_MODEL attribute works correctly."""
    # Get class from registry
    WaterStorageClass = get_component_class("WaterStorage")

    # Check PARAMS_MODEL attribute
    assert hasattr(WaterStorageClass, "PARAMS_MODEL")
    assert WaterStorageClass.PARAMS_MODEL == WaterStorageParams

    # Create instance using registry pattern
    params = WaterStorageClass.PARAMS_MODEL(capacity_m3=15.0)
    instance = WaterStorageClass("test", params)

    assert instance.capacity_m3 == 15.0


if __name__ == "__main__":
    # Run basic tests
    test_water_components_registered()
    test_water_storage_initialization()
    test_water_demand_initialization()
    test_water_grid_initialization()
    test_rainwater_source_initialization()
    test_water_storage_operation()
    test_water_demand_profile()
    test_rainwater_collection()
    test_registry_pattern_with_params_model()

    print("SUCCESS: All water component tests passed!")

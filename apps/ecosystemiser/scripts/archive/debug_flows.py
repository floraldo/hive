#!/usr/bin/env python3
"""Debug flow creation and naming in the system.

# golden-rule-ignore: no-syspath-hacks - Legacy archive script for debugging
"""

import sys
from pathlib import Path

import numpy as np

# Add path for imports
eco_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(eco_path))

from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
from ecosystemiser.system_model.components.energy.battery import (
    Battery,
    BatteryParams,
    BatteryTechnicalParams,
)
from ecosystemiser.system_model.components.energy.grid import Grid, GridParams, GridTechnicalParams
from ecosystemiser.system_model.components.energy.power_demand import (
    PowerDemand,
    PowerDemandParams,
    PowerDemandTechnicalParams,
)
from ecosystemiser.system_model.components.energy.solar_pv import (
    SolarPV,
    SolarPVParams,
    SolarPVTechnicalParams,
)
from ecosystemiser.system_model.components.shared.archetypes import FidelityLevel
from ecosystemiser.system_model.system import System

# Create simple test system
system = System(system_id="debug_flows", n=24)

# Add grid
grid_params = GridParams(
    technical=GridTechnicalParams(
        capacity_nominal=100.0,
        import_tariff=0.25,
        export_tariff=0.10,
        fidelity_level=FidelityLevel.SIMPLE,
    )
)
grid = Grid("Grid", grid_params, 24)

# Add demand
demand_params = PowerDemandParams(
    technical=PowerDemandTechnicalParams(
        capacity_nominal=10.0,
        peak_demand=10.0,
        load_profile_type="variable",
        fidelity_level=FidelityLevel.SIMPLE,
    )
)
demand = PowerDemand("PowerDemand", demand_params, 24)
demand.profile = np.array([0.5] * 24)  # Constant 50% demand

system.add_component(grid)
system.add_component(demand)

# Connect components
system.connect("Grid", "PowerDemand", "electricity")

print("BEFORE SOLVING:")
print(f"System flows: {list(system.flows.keys())}")
print(f"Grid type: {grid.type}")
print(f"Demand type: {demand.type}")
print(f"Demand profile: {demand.profile[:5]}")
print(f"Demand P_max: {demand.P_max}")

# Test demand calculation directly
print(f"Demand at t=0: {demand.rule_based_demand(0)}")

# Solve system
solver = RuleBasedEngine(system)
result = solver.solve()

print(f"\nAFTER SOLVING:")
print(f"Solver status: {result.status}")
print(f"System flows: {list(system.flows.keys())}")

for flow_key, flow_data in system.flows.items():
    print(f"Flow {flow_key}:")
    print(f"  Source: {flow_data['source']}")
    print(f"  Target: {flow_data['target']}")
    print(f"  Values: {flow_data['value'][:5]} (first 5)")
    print(f"  Total: {np.sum(flow_data['value'])}")
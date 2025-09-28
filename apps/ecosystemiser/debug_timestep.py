"""Timestep-by-timestep debugging to find the exact source of discrepancy."""
import numpy as np
import json
import sys
from src.EcoSystemiser.system_model.system import System
from src.EcoSystemiser.solver.rule_based_engine import RuleBasedEngine
from hive_logging import get_logger

logger = get_logger(__name__)

# Load golden dataset
with open('tests/systemiser_golden_results.json', 'r') as f:
    golden = json.load(f)

# Create system
system = System('TestSystem', T=24)

# Components (same as validation script)
from src.EcoSystemiser.system_model.components.energy.solar_pv import SolarPV
from src.EcoSystemiser.system_model.components.energy.power_demand import PowerDemand
from src.EcoSystemiser.system_model.components.energy.battery import Battery
from src.EcoSystemiser.system_model.components.energy.grid import Grid

solar = SolarPV(name='SolarPV', P_max=50.0)
demand = PowerDemand(name='PowerDemand', P_max=10.0)
battery = Battery(
    name='Battery',
    E_max=10.0,
    E_init=5.0,
    P_max=100.0,
    eta=0.95
)
grid = Grid(name='Grid', P_max=1000.0)

# Add components
system.add_component(solar)
system.add_component(demand)
system.add_component(battery)
system.add_component(grid)

# Add flows (bidirectional for battery and grid)
system.add_flow('SolarPV', 'PowerDemand')
system.add_flow('SolarPV', 'Battery')
system.add_flow('SolarPV', 'Grid')
system.add_flow('Battery', 'PowerDemand')
system.add_flow('Battery', 'Grid')
system.add_flow('Grid', 'PowerDemand')
system.add_flow('Grid', 'Battery')
system.add_flow('PowerDemand', 'Grid')

# Create solver
solver = RuleBasedEngine(system)
solver.prepare_system()

# Get golden battery states
golden_battery_states = golden["E"]["Battery"]["value"]

logger.debug("=== TIMESTEP-BY-TIMESTEP DEBUGGING ===")
logger.info()

# Manual timestep solving with detailed output
for t in range(24):
    logger.info(f"TIMESTEP {t}:")
    logger.info("-" * 50)
    
    # Print initial state
    if t == 0:
        initial_state = battery.E_init
        logger.info(f"  Initial battery state: {initial_state:.6f} kWh (E_init)")
    else:
        initial_state = battery.E[t-1]
        logger.info(f"  Initial battery state: {initial_state:.6f} kWh (E[{t-1}])")
    
    # Solve this timestep
    solver._solve_timestep(t)
    
    # Get flows for this timestep
    charge_flows = []
    discharge_flows = []
    
    for flow_key, flow_data in system.flows.items():
        if flow_data['target'] == 'Battery' and flow_data['value'][t] > 0:
            charge_flows.append(f"{flow_data['source']}: {flow_data['value'][t]:.6f}")
        if flow_data['source'] == 'Battery' and flow_data['value'][t] > 0:
            discharge_flows.append(f"{flow_data['target']}: {flow_data['value'][t]:.6f}")
    
    logger.info(f"  Charge flows: {', '.join(charge_flows) if charge_flows else 'None'}")
    logger.info(f"  Discharge flows: {', '.join(discharge_flows) if discharge_flows else 'None'}")
    
    # Calculate expected next state manually
    total_charge = sum(flow_data['value'][t] for flow_key, flow_data in system.flows.items() 
                      if flow_data['target'] == 'Battery')
    total_discharge = sum(flow_data['value'][t] for flow_key, flow_data in system.flows.items() 
                         if flow_data['source'] == 'Battery')
    
    energy_gained = total_charge * battery.eta
    energy_lost = total_discharge / battery.eta
    net_change = energy_gained - energy_lost
    
    logger.info(f"  Net change: {net_change:.6f} kWh (charge: {energy_gained:.6f}, discharge: {energy_lost:.6f})")
    
    # Print calculated final state
    logger.info(f"  Calculated final state: {battery.E[t]:.6f} kWh (E[{t}])")
    logger.info(f"  Golden final state: {golden_battery_states[t]:.6f} kWh")
    
    # Check for discrepancy
    diff = abs(battery.E[t] - golden_battery_states[t])
    if diff > 1e-6:
        logger.error(f"  ❌ ERROR: Discrepancy of {diff:.9f} kWh detected!")
        logger.info(f"  Expected: initial ({initial_state:.6f}) + net_change ({net_change:.6f}) = {initial_state + net_change:.6f}")
        logger.info(f"  But E[{t}] = {battery.E[t]:.6f}")
        logger.info("\n  FOUND THE BUG! The calculation is using the wrong initial state.")
        break
    else:
        logger.info(f"  ✓ States match within tolerance")
    
    logger.info()


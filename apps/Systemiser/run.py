import sys
from pathlib import Path
import logging
import numpy as np
import cvxpy as cp

# -- REMOVED TEMPORARY PATH ADJUSTMENTS --

# --- NEW LOGGER SETUP ---
# Use the refactored logger from Systemiser/utils
from Systemiser.utils.logger import setup_logging
system_logger = setup_logging("SystemiserRun", level=logging.INFO) 
# --- END NEW LOGGER SETUP ---

# --- UPDATED IMPORTS ---
# Import the engine from its new location
from Systemiser.solver.rule_based_solver import ComponentBasedRuleEngine 
# Import create_system and save_system_results from their new locations
from Systemiser.utils.system_setup import create_system
from Systemiser.io.results import save_system_results
# --- END UPDATED IMPORTS ---

def _get_safe_value(data_array, index, default=0.0):
    """Safely get numerical value from NumPy array, handling None or NaN."""
    if data_array is None or index >= len(data_array):
        return default
    value = data_array[index]
    return default if value is None or np.isnan(value) else float(value)

def verify_energy_balance(system):
    """Verify energy balance for each timestep using system.flows."""
    system_logger.debug("Verifying energy balance...")
    for t in range(system.N):
        generation = 0.0
        consumption = 0.0
        grid_import = 0.0
        grid_export = 0.0
        conversion_in = 0.0  # Placeholder
        conversion_out = 0.0 # Placeholder

        for flow_key, flow in system.flows.items():
            flow_type = flow.get('type')
            if flow_type != 'electricity' and flow_type != 'heat':
                continue
                
            source_comp = system.components[flow['source']]
            target_comp = system.components[flow['target']]
            value = _get_safe_value(flow.get('value'), t)

            if source_comp.type == "generation":
                generation += value
            if target_comp.type == "consumption":
                consumption += value
            if source_comp.type == "transmission":
                grid_import += value
            if target_comp.type == "transmission":
                grid_export += value
            # TODO: Add logic for conversion components if needed

        storage_change = sum(
            (_get_safe_value(comp.E, t) - 
             (_get_safe_value(comp.E, t-1) if t > 0 else getattr(comp, 'E_init', 0.0)))
            for comp in system.components.values()
            if comp.type == "storage" and (comp.medium == 'electricity' or comp.medium == 'heat')
        )

        balance = generation + grid_import + conversion_in - consumption - grid_export - storage_change - conversion_out

        if abs(balance) > 1e-6:
            system_logger.warning(
                 f"Energy balance violation at t={t}: {balance:.4f}\n" +
                 f"  Generation        : {generation:.4f}\n" +
                 f"  Consumption       : {consumption:.4f}\n" +
                 f"  Storage Change    : {storage_change:.4f} (+ve = increase)\n" +
                 f"  Grid Import (+)   : {grid_import:.4f}\n" +
                 f"  Grid Export (-)   : {grid_export:.4f}\n" +
                 f"  Conversion In (+) : {conversion_in:.4f}\n" +
                 f"  Conversion Out (-): {conversion_out:.4f}"
            )

def verify_water_balance(system):
    """Verify water balance for each timestep using system.flows."""
    system_logger.debug("Verifying water balance...")
    for t in range(system.N):
        sources = 0.0
        demands = 0.0
        grid_import = 0.0
        grid_export = 0.0

        for flow_key, flow in system.flows.items():
            if flow.get('type') != 'water':
                continue
                
            source_comp = system.components[flow['source']]
            target_comp = system.components[flow['target']]
            value = _get_safe_value(flow.get('value'), t)

            if source_comp.type == "generation": # Or maybe specific 'source' type?
                sources += value
            if target_comp.type == "consumption":
                demands += value
            if source_comp.type == "transmission":
                grid_import += value
            if target_comp.type == "transmission":
                grid_export += value
        
        storage_change = sum(
            (_get_safe_value(comp.E, t) - 
             (_get_safe_value(comp.E, t-1) if t > 0 else getattr(comp, 'E_init', 0.0)))
            for comp in system.components.values()
            if comp.type == "storage" and comp.medium == "water"
        )
        
        grid_exchange = grid_import - grid_export
        balance = sources + grid_import - demands - grid_export - storage_change

        if abs(balance) > 1e-6:
            system_logger.warning(
                 f"Water balance violation at t={t}: {balance:.4f}\n" +
                 f"  Sources           : {sources:.4f}\n" +
                 f"  Demands           : {demands:.4f}\n" +
                 f"  Storage Change    : {storage_change:.4f}\n" +
                 f"  Grid Exchange     : {grid_exchange:.4f}"
            )

def run_simulation(output_dir: Path): # Renamed main function, added output_dir argument
    """Test that rule-based solution matches solve_system_simple setup."""
    N = 24
    
    # Create systems using the refactored create_system
    energy_system, energy_components = create_system('energy', N)
    water_system, water_components = create_system('water', N)
    
    system_logger.info("\nTesting Energy System:")
    system_logger.info("------------------------")
    system_logger.info("Components:")
    for name, comp in energy_components.items():
        system_logger.info(f"{name}: {comp.type} ({comp.medium})")
    
    # Create rule engines
    energy_engine = ComponentBasedRuleEngine(energy_system)
    water_engine = ComponentBasedRuleEngine(water_system)
    
    # Solve timestep by timestep
    for t in range(N):
        system_logger.info(f"\nTimestep {t}:")
        
        # Energy system timestep
        system_logger.info("\nEnergy System:")
        
        # Log initial storage levels
        for name, comp in energy_components.items():
            if comp.type == "storage":
                try:
                    # Handle None values in storage levels
                    if hasattr(comp.E[t], 'value'):
                        current_level = float(comp.E[t].value) if comp.E[t].value is not None else comp.E_init
                    else:
                        current_level = float(comp.E[t]) if comp.E[t] is not None else comp.E_init
                    system_logger.info(f"{name} level: {current_level:.2f}/{comp.E_max:.2f}")
                except (TypeError, AttributeError):
                    system_logger.info(f"{name} level: {comp.E_init:.2f}/{comp.E_max:.2f}")
        
        # Log generation
        for name, comp in energy_components.items():
            if comp.type == "generation":
                try:
                    available = sum(float(flow['value'][t].value) if hasattr(flow['value'][t], 'value') and flow['value'][t].value is not None
                                  else float(flow['value'][t]) if flow['value'][t] is not None else 0.0
                                  for flow in comp.flows['source'].values())
                    system_logger.info(f"{name} generation: {available:.2f}")
                except (TypeError, AttributeError):
                    system_logger.info(f"{name} generation: 0.00")
        
        # Log demands
        for name, comp in energy_components.items():
            if comp.type == "consumption":
                try:
                    demand = sum(float(flow['value'][t].value) if hasattr(flow['value'][t], 'value') and flow['value'][t].value is not None
                               else float(flow['value'][t]) if flow['value'][t] is not None else 0.0
                               for flow in comp.flows['sink'].values())
                    system_logger.info(f"{name} demand: {demand:.2f}")
                except (TypeError, AttributeError):
                    system_logger.info(f"{name} demand: 0.00")
        
        # Solve timestep
        energy_engine.solve_timestep(t)
        
        # Log results
        system_logger.info("\nResults:")
        for name, comp in energy_components.items():
            if comp.type == "storage":
                try:
                    if hasattr(comp.E[t], 'value'):
                        current_level = float(comp.E[t].value) if comp.E[t].value is not None else comp.E_init
                    else:
                        current_level = float(comp.E[t]) if comp.E[t] is not None else comp.E_init
                    system_logger.info(f"{name} final level: {current_level:.2f}")
                except (TypeError, AttributeError):
                    system_logger.info(f"{name} final level: {comp.E_init:.2f}")
                    
            for flow_type, flows in comp.flows.items():
                for flow_name, flow in flows.items():
                    try:
                        if isinstance(flow['value'], (np.ndarray, cp.Expression)):
                            value = float(flow['value'][t].value) if hasattr(flow['value'][t], 'value') else float(flow['value'][t])
                            system_logger.info(f"{name} {flow_type} {flow_name}: {value:.2f}")
                    except (TypeError, AttributeError, ValueError) as e:
                        system_logger.info(f"{name} {flow_type} {flow_name}: 0.00")
        
        # Water system timestep
        system_logger.info("\nWater System:")
        water_engine.solve_timestep(t)
        
        # Verify balances
        verify_energy_balance(energy_system)
        verify_water_balance(water_system)
    
    # Save results using refactored function and passed output_dir
    save_system_results(energy_system, output_dir)
    save_system_results(water_system, output_dir, "_water")
    system_logger.info("Simulation complete. Results saved.")

# Removed original verify_results function as it's likely redundant
# with verify_energy_balance and verify_water_balance

if __name__ == "__main__" or __name__ == "Systemiser.run": # Allow running as script or module
    # Create output directory relative to this file's parent (Systemiser folder)
    if __name__ == "Systemiser.run":
        # If run as module, __file__ might be different, adjust path finding
        # This assumes Systemiser is in the CWD or on PYTHONPATH
         output_path = Path("Systemiser/output") 
    else:
        # If run as script, path relative to script is fine
        output_path = Path(__file__).parent / 'output'
        
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Get logger instance (assuming setup_logging is defined above)
    logger = logging.getLogger("SystemiserRun") # Get the logger configured earlier
    logger.info(f"Starting simulation. Output will be saved to {output_path}")
    
    try:
        run_simulation(output_path) # Call the main simulation function, pass output path
    except Exception as e:
        logger.exception("An error occurred during simulation!")
        sys.exit(1) # Exit with error code 
from dataclasses import dataclass, field
from typing import Dict, List, Any
import numpy as np
from hive_logging import get_logger

# Use logger from Systemiser utils
try:
    from Systemiser.utils.logger import setup_logging
    system_logger = setup_logging("Systemiser", level=logging.DEBUG) # Specific logger
except ImportError:
    system_logger = get_logger("Systemiser_Fallback")
    system_logger.warning("Could not import Systemiser logger, using fallback.")
    # Basic fallback config if needed
    if not system_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        handler.setFormatter(formatter)
        system_logger.addHandler(handler)
        system_logger.setLevel(logging.DEBUG)

@dataclass
class SystemState:
    """Represents system state at a timestep."""
    t: int
    # Store *potential* output/input and current level for components during the timestep calculation
    components: Dict[str, Dict[str, Any]] = field(default_factory=dict) 
    # Store initial levels at the START of the timestep for final calculation
    initial_storage: Dict[str, float] = field(default_factory=dict) 

class ComponentBasedRuleEngine:
    def __init__(self, system):
        self.system = system
        # Rule priorities mapping component types
        # Lower number = higher priority
        self.priorities = {
            ("generation", "consumption"): 1,
            ("generation", "storage"): 2,
            ("storage", "consumption"): 3,
            ("transmission", "consumption"): 4,
            ("generation", "transmission"): 5, # E.g. Solar PV -> Grid feed-in
            ("storage", "transmission"): 6,      # E.g. Battery -> Grid feed-in
            ("transmission", "storage"): 7,      # E.g. Grid -> Battery charge
        }
        system_logger.info(f"Initialized ComponentBasedRuleEngine for system '{self.system.system_id}'")

    def _get_priority(self, from_comp_type: str, to_comp_type: str) -> int:
        """Get priority for a flow between component types."""
        return self.priorities.get((from_comp_type, to_comp_type), 99) # Default low priority

    def solve_timestep(self, t: int):
        """Solve system for timestep t using priority rules applied to system flows."""
        system_logger.debug(f"--- Solving Timestep t={t} ---")
        if t == 0:
            self._initialize_arrays()

        # Get initial state, including potentials and storage levels at the START of timestep t
        state = self._get_system_state(t)
        
        # --- Main processing loop based on system flows and priorities --- 
        # Get flow keys sorted by priority based on component types
        sorted_flow_keys = sorted(
            self.system.flows.keys(), 
            key=lambda k: self._get_priority(
                self.system.components[self.system.flows[k]['source']].type, 
                self.system.components[self.system.flows[k]['target']].type
            )
        )

        system_logger.debug(f"Processing flows in order: {sorted_flow_keys}")

        for flow_key in sorted_flow_keys:
            flow_data = self.system.flows[flow_key]
            from_name = flow_data['source']
            to_name = flow_data['target']
            from_comp = self.system.components[from_name]
            to_comp = self.system.components[to_name]
            
            priority = self._get_priority(from_comp.type, to_comp.type)
            system_logger.debug(f" Considering Flow: {flow_key} (Priority: {priority})")

            # Get available output and required input potentials from the *current* state
            # These state values are decremented as higher priority flows are processed
            available = state.components[from_name]['available_output']
            required = state.components[to_name]['required_input']
            
            if available <= 1e-6 or required <= 1e-6:
                system_logger.debug(f"  Skipping: Available={available:.3f}, Required={required:.3f}")
                continue # Skip if no remaining source or sink capacity for this step

            # Determine the actual flow amount for this specific connection
            flow_amount = min(available, required)
            
            if flow_amount > 1e-6: 
                system_logger.debug(f"  Executing Flow: {flow_amount:.3f}")
                # --- Record the flow in the central system flow array --- 
                # Ensure the value array exists and is the correct type/size
                if 'value' not in flow_data or not isinstance(flow_data['value'], np.ndarray) or len(flow_data['value']) != self.system.N:
                     flow_data['value'] = np.zeros(self.system.N)
                flow_data['value'][t] = flow_amount # Assign value for this timestep
                
                # --- Update intermediate state for subsequent calculations within this timestep --- 
                state.components[from_name]['available_output'] -= flow_amount
                state.components[to_name]['required_input'] -= flow_amount
                
                # Update the *temporary* intermediate storage levels in the state dict if applicable
                # This helps cascade limits (e.g., storage filling up) correctly
                if from_comp.type == "storage":
                    # Apply discharge efficiency: energy leaving storage = flow_amount / discharge_eff
                    eta_discharge = state.components[from_name].get('discharge_eff', 1.0)
                    energy_drawn = flow_amount / eta_discharge
                    state.components[from_name]['current_level'] -= energy_drawn
                    system_logger.debug(f"   {from_name} (Storage State) level reduced by {energy_drawn:.3f} (flow {flow_amount:.3f}, eta {eta_discharge:.3f}) -> {state.components[from_name]['current_level']:.3f}")
                        
                if to_comp.type == "storage":
                    # Apply charge efficiency: energy stored in state = flow_amount * charge_eff
                    eta_charge = state.components[to_name].get('charge_eff', 1.0)
                    energy_stored = flow_amount * eta_charge
                    state.components[to_name]['current_level'] += energy_stored
                    system_logger.debug(f"   {to_name} (Storage State) level increased by {energy_stored:.3f} (flow {flow_amount:.3f}, eta {eta_charge:.3f}) -> {state.components[to_name]['current_level']:.3f}")
                # -----------------------------------------------------------------------------------
            else:
                 # Ensure flow value is 0 if not executed
                 if 'value' in flow_data and isinstance(flow_data['value'], np.ndarray) and t < len(flow_data['value']):
                     flow_data['value'][t] = 0.0

        # --- Post-processing: Finalize Storage Levels --- 
        # Update the actual component storage arrays (comp.E) based on the sum of recorded flows
        for comp_name, comp in self.system.components.items():
            if comp.type == "storage":
                initial_level = state.initial_storage.get(comp_name, comp.E_init)
                
                # Sum recorded flows directly from system.flows for this component
                charge = sum(self.system.flows[key]['value'][t] 
                             for key in self.system.flows 
                             if self.system.flows[key]['target'] == comp_name)
                             
                discharge = sum(self.system.flows[key]['value'][t] 
                                for key in self.system.flows 
                                if self.system.flows[key]['source'] == comp_name)

                # Apply efficiencies consistently for the final state change calculation
                # Get efficiencies stored in the initial state calculation
                eta_charge = state.components[comp_name].get('charge_eff', 1.0)
                eta_discharge = state.components[comp_name].get('discharge_eff', 1.0)
                
                # Energy actually added to storage = charge * charge_eff
                # Energy actually removed from storage = discharge / discharge_eff 
                net_energy_change = (charge * eta_charge) - (discharge / eta_discharge)
                
                # Calculate final level for the *end* of timestep t
                final_level = initial_level + net_energy_change
                
                # Ensure level stays within bounds (0 to E_max)
                max_cap = getattr(comp, 'E_max', float('inf'))
                final_level = max(0, min(final_level, max_cap))
                
                # Update the component's official array
                if hasattr(comp, 'E') and isinstance(comp.E, np.ndarray) and t < len(comp.E):
                    comp.E[t] = final_level 
                else:
                    system_logger.error(f"Cannot update E[{t}] for component {comp_name}. Array missing or index out of bounds.")
                
                system_logger.debug(f"  Final Storage Update {comp_name} t={t}:")
                system_logger.debug(f"    Initial Level: {initial_level:.3f}")
                system_logger.debug(f"    Total Charge In (flow): {charge:.3f} (eff: {eta_charge:.3f})")
                system_logger.debug(f"    Total Discharge Out (flow): {discharge:.3f} (eff: {eta_discharge:.3f})")
                system_logger.debug(f"    Net Energy Change in Storage: {net_energy_change:.3f}")
                system_logger.debug(f"    Final Level E[{t}]: {comp.E[t] if hasattr(comp, 'E') and t < len(comp.E) else 'Error'}")

        # Propagate final storage level to next timestep's initial state (if not last step)
        if t < self.system.N - 1:
            for comp_name, comp in self.system.components.items():
                if comp.type == "storage":
                    if hasattr(comp, 'E') and isinstance(comp.E, np.ndarray) and t < len(comp.E) and not np.isnan(comp.E[t]):
                         # Prepare E for the *start* of the next step
                         if t + 1 < len(comp.E):
                             comp.E[t+1] = comp.E[t]
                         else:
                             system_logger.error(f"Index t+1 ({t+1}) out of bounds for {comp_name}.E array (len {len(comp.E)}). Cannot propagate.")
                    else:
                         system_logger.error(f"Storage level for {comp_name} is NaN or invalid at t={t}. Cannot propagate reliably.")
                         # Fallback propagation
                         fallback_level = comp.E[t-1] if t > 0 and hasattr(comp, 'E') and t < len(comp.E) and not np.isnan(comp.E[t-1]) else comp.E_init
                         if t + 1 < len(comp.E):
                             comp.E[t+1] = fallback_level
                         else:
                             system_logger.error(f"Index t+1 ({t+1}) out of bounds for {comp_name}.E array during fallback propagation.")
            
        system_logger.debug(f"--- Finished Timestep t={t} ---")

    def _get_system_state(self, t) -> SystemState:
        """Calculates the potential source/sink capacities and initial storage levels at the START of timestep t."""
        components_state = {}
        initial_storage_levels = {}
        system_logger.debug(f" Getting state for t={t}")
        
        for name, comp in self.system.components.items():
            # Determine initial storage level for this timestep
            current_storage_level = 0.0
            if comp.type == "storage":
                # Storage level E[t] should represent state at the START of timestep t
                if t == 0:
                    current_storage_level = getattr(comp, 'E_init', 0.0)
                    # Ensure E array exists and set E[0]
                    if not (hasattr(comp, 'E') and isinstance(comp.E, np.ndarray) and len(comp.E) == self.system.N):
                         comp.E = np.full(self.system.N, np.nan) # Array for levels at END of t=0 to t=N-1
                    # E[0] in the array represents state *after* t=0, so we just need E_init
                elif hasattr(comp, 'E') and isinstance(comp.E, np.ndarray) and t > 0 and t < len(comp.E) and not np.isnan(comp.E[t-1]):
                    # Use the final level from the previous step (E[t-1]) as the start level for t
                    current_storage_level = comp.E[t-1]
                elif hasattr(comp, 'E_init'): # Fallback if previous step data missing
                    current_storage_level = getattr(comp, 'E_init', 0.0)
                    system_logger.warning(f"Could not determine storage level for {name} at start of t={t} from E[{t-1}], using E_init.")
                else:
                    system_logger.error(f"Storage component {name} missing E and E_init.")
                
                initial_storage_levels[name] = current_storage_level
                system_logger.debug(f"  {name} (Storage) initial level at start of t={t} = {current_storage_level:.3f}")
            
            # Calculate available output / required input potentials for the timestep
            available_output = 0.0
            required_input = 0.0
            # Use more descriptive efficiency names if available, default to eta
            eta_charge = getattr(comp, 'eta_charge', getattr(comp, 'eta', 1.0))
            eta_discharge = getattr(comp, 'eta_discharge', getattr(comp, 'eta', 1.0))

            if comp.type == "generation":
                available_output = self._get_profile_value(comp, t)
            elif comp.type == "consumption":
                required_input = self._get_profile_value(comp, t)
            elif comp.type == "transmission":
                available_output = getattr(comp, 'P_max', float('inf')) # Grid supply potential
                required_input = getattr(comp, 'P_max', float('inf'))   # Grid feed-in potential
            elif comp.type == "storage":
                # Storage: Available output depends on current level and discharge efficiency
                # Required input depends on remaining capacity and charge efficiency
                current_storage_level = comp.E[t-1] if t > 0 else comp.E_init
                max_level = comp.E_max
                power_limit = getattr(comp, 'P_max', getattr(comp, 'W_cha_max', float('inf')))  # Use W_cha_max for water components
                # Use the fallback values we calculated above
                # eta_charge = getattr(comp, 'eta_charge', getattr(comp, 'eta', 1.0))
                # eta_discharge = getattr(comp, 'eta_discharge', getattr(comp, 'eta', 1.0))

                # Available Output (Discharge Potential) - CORRECTED LOGIC
                # Potential based on energy currently stored, limited by power rate
                discharge_potential_power = current_storage_level 
                available_output = min(discharge_potential_power, power_limit)
                
                # Required Input (Charge Potential) - CORRECTED LOGIC
                # Energy needed to fill = max_level - current_level
                # Input flow required = Energy needed / eta_charge
                # Power required = Input flow required (limited by P_max)
                if eta_charge > 1e-9: # Avoid division by zero
                    charge_potential_power = (max_level - current_storage_level) / eta_charge 
                else:
                    charge_potential_power = float('inf') # Assume infinite needed if efficiency is zero/invalid
                required_input = min(charge_potential_power, power_limit)

            state_data = {
                'type': comp.type,
                'medium': comp.medium,
                # Store the *potential* output/input rate for the whole step
                'available_output': max(0, available_output),
                'required_input': max(0, required_input),
                # Store efficiencies for later use
                'charge_eff': eta_charge,
                'discharge_eff': eta_discharge,
                # Store initial level for intermediate calculations
                'current_level': current_storage_level 
            }
            components_state[name] = state_data
            system_logger.debug(f"  {name} State Potentials: Avail={state_data['available_output']:.3f}, Req={state_data['required_input']:.3f}, EffC={eta_charge:.2f}, EffD={eta_discharge:.2f}")

        return SystemState(t=t, components=components_state, initial_storage=initial_storage_levels)

    def _get_profile_value(self, comp, t):
        """Safely get profile value, scaled by P_max if available."""
        profile = getattr(comp, 'profile', None)
        if profile is not None and t < len(profile):
            # Scale by P_max if it exists, otherwise use profile value directly
            scale = getattr(comp, 'P_max', 1.0) 
            # Handle potential None in profile data itself
            value = profile[t]
            return float(value * scale) if value is not None else 0.0
        return 0.0

    def _initialize_arrays(self):
        """Initialize flow and storage arrays."""
        system_logger.info("Initializing system flow and storage arrays.")
        # Initialize flow values in the central system dictionary
        for flow_key, flow_data in self.system.flows.items():
            # Ensure 'value' is a numpy array of the correct size N
            if not ('value' in flow_data and isinstance(flow_data['value'], np.ndarray) and len(flow_data['value']) == self.system.N):
                flow_data['value'] = np.zeros(self.system.N)
            else:
                flow_data['value'].fill(0.0) # Reset existing array
            system_logger.debug(f"  Initialized flow array for '{flow_key}'")

        # Initialize storage level arrays (size N for end-of-step values t=0 to N-1)
        for name, comp in self.system.components.items():
            if comp.type == "storage":
                # Ensure E array exists and is size N
                if not (hasattr(comp, 'E') and isinstance(comp.E, np.ndarray) and len(comp.E) == self.system.N):
                    comp.E = np.full(self.system.N, np.nan) 
                else:
                    comp.E.fill(np.nan) # Reset existing array
                # Note: E_init is handled in _get_system_state for t=0
                system_logger.debug(f"  Initialized storage array E (size {self.system.N}) for '{name}'")
                
    def _get_value(self, var, t):
        """Helper to safely get value from numpy array."""
        # Simplified: Assumes var is always a numpy array in rule-based mode
        if isinstance(var, np.ndarray) and t < len(var):
            val = var[t]
            return val if not np.isnan(val) else 0.0
        return 0.0

    def _validate_balance(self, state: SystemState):
        """Validate balance based on calculated flows and actual storage change for timestep t."""
        t = state.t
        media_components = {}
        for comp in self.system.components.values():
            if comp.medium not in media_components: media_components[comp.medium] = []
            media_components[comp.medium].append(comp)
        
        for medium, components in media_components.items():
            generation = 0.0
            consumption = 0.0
            storage_charge_effective = 0.0 # Energy delivered TO storage
            storage_discharge_effective = 0.0 # Energy delivered BY storage
            grid_import = 0.0
            grid_export = 0.0
            actual_storage_change = 0.0

            for comp in components:
                comp_name = comp.name
                # Sum flows based on type and direction recorded in the arrays
                if comp.type == "generation":
                    generation += sum(self._get_value(f['value'], t) for f in comp.flows.get('source', {}).values() if f['type'] == medium)
                elif comp.type == "consumption":
                    # Consumption is the sum of energy flowing INTO the component
                    consumption += sum(self._get_value(f['value'], t) for f in comp.flows.get('input', {}).values() if f['type'] == medium)
                elif comp.type == "transmission": # Grid
                    grid_import += sum(self._get_value(f['value'], t) for f_name, f in comp.flows.get('source', {}).items() if f['type'] == medium)
                    grid_export += sum(self._get_value(f['value'], t) for f_name, f in comp.flows.get('sink', {}).items() if f['type'] == medium)
                elif comp.type == "storage":
                    eta = getattr(comp, 'eta', 1.0)
                    # Energy DELIVERED BY storage (apply efficiency)
                    discharge_flow = sum(self._get_value(f['value'], t) 
                                         for f_name, f in comp.flows.get('source', {}).items() 
                                         if f['type'] == medium) # Sum all source flows for this medium
                    storage_discharge_effective += discharge_flow * eta 
                    # Energy DELIVERED TO storage 
                    charge_flow = sum(self._get_value(f['value'], t) 
                                      for f_name, f in comp.flows.get('sink', {}).items() 
                                      if f['type'] == medium) # Sum all sink flows for this medium
                    storage_charge_effective += charge_flow 
                    
                    # Calculate actual internal storage change
                    start_level = state.initial_storage.get(comp.name, comp.E_init)
                    end_level = self._get_value(comp.E, t) # Use final value for t
                    if not np.isnan(start_level) and not np.isnan(end_level):
                        actual_storage_change += (end_level - start_level)
                    else:
                        system_logger.warning(f"NaN detected for {comp.name} at t={t} in validation.")
                elif comp.type == "conversion":
                     # Conversions are tricky - they consume one medium and produce another.
                     # Their net effect should be captured by the Gen/Consumption terms of the *respective* mediums.
                     # For example, a HeatPump producing heat counts as 'generation' for the heat medium.
                     # The electricity it consumes counts as 'consumption' for the electricity medium.
                     # We rely on the component types being set correctly (e.g., HP is type 'generation' for medium 'heat').
                     pass 
            
            # Balance Check: Sum of inflows == Sum of outflows
            inflows = generation + grid_import + storage_discharge_effective
            outflows = consumption + grid_export + storage_charge_effective
            balance = inflows - outflows
            
            # Validate balance
            if abs(balance) > 1e-6:
                system_logger.warning(
                    f"Balance violation for {medium} at t={t}: {balance:.4f}\n" + 
                    f"  Inflows (Gen+GridIn+StorDisEff): {inflows:.4f}\n" +
                    f"  Outflows(Con+GridEx+StorChEff): {outflows:.4f}\n" +
                    f"  -> Generation : {generation:.4f}\n" +
                    f"  -> Consumption: {consumption:.4f}\n" +
                    f"  -> StorDisEff : {storage_discharge_effective:.4f}\n" +
                    f"  -> StorChEff  : {storage_charge_effective:.4f}\n" +
                    f"  -> Grid Import: {grid_import:.4f}\n" +
                    f"  -> Grid Export: {grid_export:.4f}\n" +
                    f"  -> StorChange : {actual_storage_change:.4f}"
                )
            assert abs(balance) < 1e-6, f"Balance failed for {medium} at t={t}"
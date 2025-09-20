from dataclasses import dataclass, field
from typing import Dict, Any
import numpy as np
import logging

# Integrate with existing logger setup
try:
    from Systemiser.utils.logger import setup_logging
    logger = setup_logging("GenericRuleEngine", level=logging.INFO) # Use specific logger
except ImportError:
    logger = logging.getLogger("GenericRuleEngine_Fallback") # Fallback logger
    logger.warning("Could not import Systemiser logger, using fallback.")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


@dataclass
class SystemState:
    t: int
    flows: Dict[str, float] = field(default_factory=dict)  # e.g. "GEN1_to_CON1": flow
    comps: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # Per-comp state: {source, sink, conv}
    init_store: Dict[str, float] = field(default_factory=dict)

class GenericRuleEngine:
    """A simplified rule-based engine focusing on component types.
    
    Handles flow based on predefined priority rules between component types.
    """
    def __init__(self, sys):
        self.sys = sys
        # Rules: (from_component_type, to_component_type, priority)
        # Lower priority number means higher priority
        self.rules = [
            ("generation", "consumption", 1),
            ("generation", "storage", 2),
            ("storage", "consumption", 3),
            ("transmission", "consumption", 4) # Assuming transmission (Grid) supplies last
            # Potential other rules: storage -> transmission (feed-in), transmission -> storage?
        ]
        logger.info(f"Initialized GenericRuleEngine for system '{self.sys.name}'")
    
    def solve_timestep(self, t: int):
        """Solves a single timestep t using the rule-based logic."""
        logger.debug(f"Solving timestep t={t}")
        if t == 0:
            self._init_arrays()
            # Initial storage level is set in _init_arrays

        # Get the current state (available sources, required sinks)
        state = self._get_state(t)
        
        # Process flows according to priority rules
        for fr_type, to_type, priority in sorted(self.rules, key=lambda r: r[2]):
            logger.debug(f"Processing rule: {fr_type} -> {to_type} (priority {priority})")
            # Find components matching the rule types
            from_comps = [n for n, c in self.sys.components.items() if c.type == fr_type]
            to_comps   = [n for n, c in self.sys.components.items() if c.type == to_type]
            
            # Attempt to satisfy flows between matching components
            for fn in from_comps:
                for tn in to_comps:
                    # Ensure components handle the same medium (e.g., electricity, heat)
                    if self.sys.components[fn].medium != self.sys.components[tn].medium:
                        continue
                        
                    # Determine potential flow (limited by source availability and sink capacity)
                    # Use max(0, ...) to avoid issues with float precision near zero
                    available_source = max(0, state.comps[fn]['source'])
                    required_sink = max(0, state.comps[tn]['sink'])
                    flow = min(available_source, required_sink)
                    
                    # If there's a meaningful flow, update state and record the flow
                    if flow > 1e-6: # Use a tolerance to avoid tiny flows
                        logger.debug(f"  Flow {fn} -> {tn}: {flow:.3f}")
                        state.comps[fn]['source'] -= flow
                        state.comps[tn]['sink'] -= flow
                        key = f"{fn}_to_{tn}"
                        # Record this specific flow value for the timestep
                        # Note: This assumes self.sys.flows is pre-initialized with ndarrays
                        if key in self.sys.flows:
                            self.sys.flows[key]['value'][t] = self.sys.flows[key]['value'][t] + flow
                        else:
                             logger.warning(f"Flow key '{key}' not found in system.flows. Cannot record value.")
                        # Also update the aggregated flow state for validation (optional)
                        state.flows[key] = state.flows.get(key, 0) + flow

        # Update storage levels based on flows that occurred
        for name, comp in self.sys.components.items():
            if comp.type == "storage":
                initial_level = state.init_store.get(name, comp.E_init) # Level at start of timestep
                
                # Find total energy flowing *into* the storage this timestep
                in_flow = sum(self.sys.flows[key]['value'][t]
                              for key in self.sys.flows 
                              if key.endswith(f"_to_{name}"))
                
                # Find total energy flowing *out of* the storage this timestep
                out_flow = sum(self.sys.flows[key]['value'][t]
                               for key in self.sys.flows 
                               if key.startswith(f"{name}_to_"))
                
                # Apply efficiency (eta is typically for charging/discharging, model needs clarity)
                # Assuming eta applies to charging: effective_in_flow = in_flow * eta
                # Assuming eta applies to discharging: effective_out_flow = out_flow / eta
                # Let's assume eta is overall round-trip for simplicity here, applied during state calc.
                # Or perhaps eta here represents standing loss (which isn't modeled yet).
                # For now, let's assume eta affects charging (energy stored = energy_in * eta)
                # and discharging (energy needed = energy_out / eta) -> handled in _get_state source/sink calc.
                
                # Update the storage level array for the *end* of timestep t
                comp.E[t] = max(0, min(
                    initial_level + in_flow - out_flow, 
                    getattr(comp, 'E_max', float('inf'))
                ))
                logger.debug(f"  Storage {name}: E_init={initial_level:.2f}, in={in_flow:.2f}, out={out_flow:.2f}, E_final={comp.E[t]:.2f}")

        # Prepare storage level for the *next* timestep (t+1) if not the last step
        # This makes E[t] available as the starting point for the next iteration's _get_state
        if t < self.sys.N - 1:
            for name, comp in self.sys.components.items():
                if comp.type == "storage":
                     # Carry over the calculated end-of-timestep level to the start of the next
                     comp.E[t + 1] = comp.E[t]

        # Validate the state after all flows are processed (optional)
        # self._validate(state) # Commented out as the provided validation is likely incorrect
    
    def _get_state(self, t: int) -> SystemState:
        """Calculates the available source and required sink for each component at timestep t."""
        comps_state = {}
        initial_storage_levels = {}
        
        for name, comp in self.sys.components.items():
            comp_eta = getattr(comp, 'eta', 1.0) # Get efficiency, default to 1
            source_avail = 0.0
            sink_req = 0.0
            
            if comp.type == "generation":
                source_avail = self._profile(comp, t)
            elif comp.type == "consumption":
                sink_req = self._profile(comp, t)
            elif comp.type == "transmission":
                # Grid can supply 'infinite' (up to P_max if defined) and potentially consume infinite (feed-in)
                source_avail = getattr(comp, 'P_max', float('inf')) # Max power draw *from* grid
                sink_req = getattr(comp, 'P_max', float('inf'))   # Max power feed *to* grid (if bidirectional)
            elif comp.type == "storage":
                # Determine level at the *start* of timestep t
                if t == 0:
                    current_level = comp.E_init
                elif not np.isnan(comp.E[t]): # Value might already be set (e.g., by previous timestep)
                    current_level = comp.E[t]
                elif t > 0 and not np.isnan(comp.E[t - 1]): # Fallback to previous end-of-step value
                    current_level = comp.E[t - 1]
                else:
                     current_level = comp.E_init # Ultimate fallback
                     logger.warning(f"Storage {name} level at t={t} couldn't be determined, using E_init.")
                
                initial_storage_levels[name] = current_level
                storage_max = getattr(comp, 'E_max', float('inf'))
                
                # Source: How much can be discharged (apply discharge efficiency)
                # Assuming eta applies symmetrically or mainly to discharge: available = level / eta ?
                # If eta is round-trip: sqrt(eta)? Let's assume eta applies to discharge.
                # source_avail = current_level / comp_eta # Energy available from storage
                # Let's assume eta = discharge efficiency for simplicity here.
                source_avail = current_level * comp_eta 

                # Sink: How much can be charged (apply charge efficiency)
                # Sink capacity = (Max capacity - current level)
                # Energy needed to fill = Sink capacity / charge_eta
                # Assuming eta applies to charging
                # sink_req = (storage_max - current_level) / comp_eta # Capacity available in storage
                sink_req = (storage_max - current_level) * comp_eta # Assuming eta = charge efficiency

                # Apply power limits (P_max for charge/discharge rate)
                power_limit = getattr(comp, 'P_max', float('inf'))
                source_avail = min(source_avail, power_limit)
                sink_req = min(sink_req, power_limit)
                
            else:
                logger.warning(f"Component {name} has unknown type '{comp.type}'")
                
            # Store calculated source/sink potential for this timestep
            comps_state[name] = {'source': max(0, source_avail), 'sink': max(0, sink_req), 'conv': comp_eta}
            logger.debug(f"  State t={t} {name}: src={comps_state[name]['source']:.2f}, sink={comps_state[name]['sink']:.2f}")
            
        return SystemState(t=t, flows={}, comps=comps_state, init_store=initial_storage_levels)
    
    def _profile(self, comp, t: int) -> float:
        """Gets the profile value for a component at timestep t, scaled by P_max."""
        # Check if profile exists and has data for the timestep
        if hasattr(comp, 'profile') and comp.profile is not None and t < len(comp.profile):
            # Ensure P_max exists, otherwise profile is unscaled
            p_max = getattr(comp, 'P_max', 1.0)
            return float(comp.profile[t] * p_max)
        return 0.0
    
    def _init_arrays(self):
        """Initializes numpy arrays for flows and storage levels in the system components."""
        logger.info("Initializing system arrays (flows and storage levels)")
        # Initialize flow values in the system's central flow dictionary
        for key, flow_data in self.sys.flows.items():
            # Ensure 'value' is a numpy array of the correct size
            if not (hasattr(flow_data, 'value') and 
                    isinstance(flow_data['value'], np.ndarray) and 
                    len(flow_data['value']) == self.sys.N):
                 flow_data['value'] = np.zeros(self.sys.N)
            else:
                 flow_data['value'].fill(0.0) # Reset existing array
            logger.debug(f"  Initialized flow array for '{key}'")

        # Initialize storage level arrays
        for name, comp in self.sys.components.items():
            if comp.type == "storage":
                # Ensure 'E' attribute exists, is numpy array, and correct size
                if not (hasattr(comp, 'E') and 
                        isinstance(comp.E, np.ndarray) and 
                        len(comp.E) == self.sys.N):
                    comp.E = np.full(self.sys.N, np.nan) # Use NaN to indicate uncalculated steps
                else:
                     # Reset existing array, except maybe E_init?
                     comp.E.fill(np.nan)
                
                # Set initial condition at t=0
                comp.E[0] = comp.E_init
                logger.debug(f"  Initialized storage array for '{name}' with E[0]={comp.E[0]}")
    
    def _validate(self, state: SystemState):
        """Basic validation (currently placeholder/likely incorrect)."""
        # This validation needs to be medium-specific and consider component balances.
        # The original verification functions in run.py are better suited.
        t = state.t
        logger.warning(f"GenericRuleEngine._validate at t={t} is a placeholder and likely incorrect.")
        # media = {}
        # for comp in self.sys.components.values():
        #     media.setdefault(comp.medium, []).append(comp)
        # for med, comps in media.items():
        #     # This sum is wrong - needs source/sink distinction per component
        #     total = sum(state.flows.values()) 
        #     if abs(total) > 1e-6:
        #           logger.error(f"Balance error for {med} at t={t}: {total}")
        #           # raise AssertionError(f"Balance error for {med} at t={t}: {total}") 
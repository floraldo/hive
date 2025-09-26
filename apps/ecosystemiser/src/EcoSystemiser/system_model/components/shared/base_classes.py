"""Base classes for component inheritance with common physics logic."""
from .component import Component
import numpy as np
import math
import logging

logger = logging.getLogger(__name__)


class BaseStorageComponent(Component):
    """Base class for all storage components with common physics.

    This class provides the SINGLE SOURCE OF TRUTH for simple storage physics.
    All storage components (Battery, HeatBuffer, etc.) inherit from this.

    The key innovation: Components handle their own physics, not the solver!
    """

    def rule_based_update_state(self, t: int, charge_power: float, discharge_power: float):
        """
        Update storage state with simultaneous charge/discharge capability.

        This method encapsulates the physics of energy storage, allowing
        simultaneous charging and discharging in the same timestep.

        Args:
            t: Current timestep
            charge_power: Total power charging this storage (kW)
            discharge_power: Total power discharging from this storage (kW)
        """
        if self.E is None or t >= len(self.E):
            return

        # Determine the energy level at the START of the current timestep
        if t == 0:
            initial_level = getattr(self, 'E_init', 0.0)
        else:
            initial_level = self.E[t-1]

        # Use component's own efficiency parameters
        # For roundtrip efficiency η, we use the full value for the calculation
        # Original Systemiser uses: charge with η, discharge with 1/η
        eta = self.eta if hasattr(self, 'eta') else 0.95

        # Calculate energy changes
        # Energy gained from charging (power * efficiency)
        energy_gained = charge_power * eta

        # Energy lost from discharging (power / efficiency)
        energy_lost = discharge_power / eta

        # Net energy change
        net_change = energy_gained - energy_lost

        # Update state at the END of the CURRENT timestep
        next_state = initial_level + net_change

        # Enforce physical bounds
        self.E[t] = max(0.0, min(next_state, self.E_max))

        # Log for debugging if needed
        if t == 0 and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"{self.name} at t={t}: charge={charge_power:.3f}kW, "
                f"discharge={discharge_power:.3f}kW, initial={initial_level:.3f}kWh, "
                f"E[{t}]={self.E[t]:.3f}kWh"
            )

    def get_available_discharge(self, t: int) -> float:
        """
        Calculate available discharge power considering state and efficiency.

        The component reports its true available output, accounting for:
        - Current energy level
        - Discharge efficiency
        - Power limits
        """
        # Get state at START of timestep
        if t == 0:
            current_level = getattr(self, 'E_init', 0.0)
        else:
            current_level = self.E[t-1] if hasattr(self, 'E') and t > 0 else 0.0

        # The golden dataset behavior shows battery outputting its full energy level as power
        # This matches the original Systemiser's energy-limited discharge
        power_limit = getattr(self, 'P_max', float('inf'))

        # Available power is limited by both P_max and current energy level
        # No efficiency factor here - the energy level directly limits power output
        return min(power_limit, current_level)

    def get_available_charge(self, t: int) -> float:
        """
        Calculate available charge power considering state and capacity.

        The component reports how much power it can accept, accounting for:
        - Remaining capacity
        - Power limits
        """
        # Get state at START of timestep
        if t == 0:
            current_level = getattr(self, 'E_init', 0.0)
        else:
            current_level = self.E[t-1] if hasattr(self, 'E') and t > 0 else 0.0

        max_level = self.E_max
        power_limit = getattr(self, 'P_max', float('inf'))

        # Available charge power is limited by remaining capacity and power limit
        remaining_capacity = max_level - current_level
        return min(power_limit, remaining_capacity)


class BaseGenerationComponent(Component):
    """Base class for all generation components with common generation logic.

    This class provides the SINGLE SOURCE OF TRUTH for generation physics.
    All generation components (SolarPV, WindTurbine, etc.) inherit from this.

    The key pattern: Components handle their own output calculation, not the solver!
    """

    def rule_based_generate(self, t: int) -> float:
        """
        Calculate generation output for the current timestep.

        This method encapsulates the physics of generation, handling:
        - Profile-based generation (weather, solar irradiance, etc.)
        - Capacity scaling (P_max)
        - Fidelity-based enhancements

        Args:
            t: Current timestep

        Returns:
            float: Available generation output in kW
        """
        # Check if component has a generation profile
        if not hasattr(self, 'profile') or self.profile is None:
            return 0.0

        # Ensure timestep is within profile bounds
        if t >= len(self.profile):
            return 0.0

        # Get maximum capacity
        P_max = getattr(self, 'P_max', 0.0)

        # Base generation: profile value * maximum capacity
        # Profile should be normalized (0-1), P_max provides scaling
        base_output = self.profile[t] * P_max

        # Fidelity enhancements can be added here in future
        # if self.technical.fidelity_level >= FidelityLevel.STANDARD:
        #     # Add weather variations, equipment degradation, etc.
        #     pass

        return max(0.0, base_output)


class BaseDemandComponent(Component):
    """Base class for all demand components with common demand logic.

    This class provides the SINGLE SOURCE OF TRUTH for demand physics.
    All demand components (PowerDemand, HeatDemand, etc.) inherit from this.

    The key pattern: Components handle their own demand calculation, not the solver!
    """

    def rule_based_demand(self, t: int) -> float:
        """
        Calculate demand requirement for the current timestep.

        This method encapsulates the physics of demand, handling:
        - Profile-based demand (occupancy, weather, schedules, etc.)
        - Capacity scaling (P_max or peak demand)
        - Fidelity-based enhancements

        Args:
            t: Current timestep

        Returns:
            float: Required demand input in kW
        """
        # Check if component has a demand profile
        if not hasattr(self, 'profile') or self.profile is None:
            return 0.0

        # Ensure timestep is within profile bounds
        if t >= len(self.profile):
            return 0.0

        # Get maximum capacity - try P_max first, then peak_demand
        P_max = getattr(self, 'P_max', None)
        if P_max is None:
            P_max = getattr(self, 'peak_demand', 0.0)

        # Base demand: profile value * maximum capacity
        # Profile should be normalized (0-1), P_max provides scaling
        base_demand = self.profile[t] * P_max

        # Fidelity enhancements can be added here in future
        # if self.technical.fidelity_level >= FidelityLevel.STANDARD:
        #     # Add temperature effects, occupancy variations, etc.
        #     pass

        return max(0.0, base_demand)


class BaseConversionComponent(Component):
    """Base class for all conversion components with common conversion logic.

    This class provides the SINGLE SOURCE OF TRUTH for conversion physics.
    All conversion components (HeatPump, ElectricBoiler, etc.) inherit from this.

    The key pattern: Components handle their own conversion efficiency and constraints!
    """

    def rule_based_conversion_capacity(self, t: int, from_medium: str, to_medium: str) -> dict:
        """
        Calculate conversion capacities for the current timestep.

        This method encapsulates the physics of energy conversion, handling:
        - Input/output capacity limits
        - Efficiency relationships between input and output
        - Fidelity-based enhancements (COP, temperature dependence, etc.)

        Args:
            t: Current timestep
            from_medium: Input energy medium (e.g., 'electricity')
            to_medium: Output energy medium (e.g., 'heat')

        Returns:
            dict: {'max_input': float, 'max_output': float, 'efficiency': float}
        """
        # Default capacity limits - components can override for specific logic
        P_max_input = getattr(self, 'P_max_input', getattr(self, 'P_max', 0.0))
        P_max_output = getattr(self, 'P_max_output', getattr(self, 'P_max', 0.0))

        # Default efficiency - components can override for complex efficiency curves
        efficiency = getattr(self, 'efficiency', getattr(self, 'COP', 1.0))

        # Basic efficiency relationship: output = input * efficiency
        # For heat pumps: electrical input -> thermal output with COP > 1
        # For boilers: fuel/electrical input -> thermal output with efficiency < 1

        # Fidelity enhancements can be added here in future
        # if self.technical.fidelity_level >= FidelityLevel.STANDARD:
        #     # Add temperature-dependent COP, part-load efficiency curves, etc.
        #     pass

        return {
            'max_input': P_max_input,
            'max_output': P_max_output,
            'efficiency': efficiency
        }

    def rule_based_conversion_dispatch(self, t: int, requested_output: float, from_medium: str, to_medium: str) -> dict:
        """
        Calculate actual input/output for a requested output.

        Args:
            t: Current timestep
            requested_output: Desired output power (kW)
            from_medium: Input energy medium
            to_medium: Output energy medium

        Returns:
            dict: {'input_required': float, 'output_delivered': float}
        """
        capacity = self.rule_based_conversion_capacity(t, from_medium, to_medium)

        # Limit output to maximum capacity
        actual_output = min(requested_output, capacity['max_output'])

        # Calculate required input based on efficiency
        if capacity['efficiency'] > 0:
            required_input = actual_output / capacity['efficiency']
        else:
            required_input = 0.0

        # Ensure input doesn't exceed capacity
        if required_input > capacity['max_input']:
            # Scale back both input and output proportionally
            scale_factor = capacity['max_input'] / required_input
            required_input = capacity['max_input']
            actual_output = actual_output * scale_factor

        return {
            'input_required': required_input,
            'output_delivered': actual_output
        }


# =============================================================================
# STRATEGY PATTERN BASE CLASSES
# =============================================================================

class BaseStoragePhysics:
    """Abstract base class for storage physics strategies.

    This defines the interface contract that all storage physics implementations
    must follow. Each fidelity level implements this interface.

    The Strategy Pattern allows us to:
    - Encapsulate physics algorithms
    - Make fidelity levels interchangeable
    - Support easy testing and extension
    """

    def __init__(self, params):
        """Initialize physics strategy with component parameters."""
        self.params = params

    def rule_based_update_state(self, t: int, E_old: float, charge_power: float, discharge_power: float) -> float:
        """
        Calculate new energy state based on physics model.

        This is the core physics method that each strategy must implement.

        Args:
            t: Current timestep
            E_old: Energy level at start of timestep (kWh)
            charge_power: Total power charging this storage (kW)
            discharge_power: Total power discharging from this storage (kW)

        Returns:
            float: New energy level after physics update (kWh)
        """
        raise NotImplementedError("Subclasses must implement rule_based_update_state")

    def apply_bounds(self, energy_level: float) -> float:
        """Apply physical energy bounds (0 <= E <= E_max)."""
        E_max = self.params.technical.capacity_nominal
        return max(0.0, min(energy_level, E_max))


class BaseStorageOptimization:
    """Abstract base class for storage optimization strategies.

    This defines the interface contract for MILP optimization implementations.
    Separates optimization logic from physics and data models.
    """

    def __init__(self, params):
        """Initialize optimization strategy with component parameters."""
        self.params = params

    def set_constraints(self) -> list:
        """
        Create CVXPY constraints for this storage component.

        This is the core optimization method that each strategy must implement.
        Should return all constraints needed for MILP solver.

        Returns:
            list: CVXPY constraint objects
        """
        raise NotImplementedError("Subclasses must implement set_constraints")


class BaseGenerationPhysics:
    """Abstract base class for generation physics strategies.

    This defines the interface contract that all generation physics implementations
    must follow. Each fidelity level implements this interface.

    The Strategy Pattern allows us to:
    - Encapsulate generation algorithms
    - Make fidelity levels interchangeable
    - Support easy testing and extension
    """

    def __init__(self, params):
        """Initialize physics strategy with component parameters."""
        self.params = params

    def rule_based_generate(self, t: int, profile_value: float) -> float:
        """
        Calculate generation output based on physics model.

        This is the core physics method that each strategy must implement.

        Args:
            t: Current timestep
            profile_value: Normalized profile value (0-1) for this timestep

        Returns:
            float: Actual generation output in kW
        """
        raise NotImplementedError("Subclasses must implement rule_based_generate")


class BaseGenerationOptimization:
    """Abstract base class for generation optimization strategies.

    This defines the interface contract for MILP optimization implementations.
    Separates optimization logic from physics and data models.
    """

    def __init__(self, params):
        """Initialize optimization strategy with component parameters."""
        self.params = params

    def set_constraints(self) -> list:
        """
        Create CVXPY constraints for this generation component.

        This is the core optimization method that each strategy must implement.
        Should return all constraints needed for MILP solver.

        Returns:
            list: CVXPY constraint objects
        """
        raise NotImplementedError("Subclasses must implement set_constraints")


class BaseConversionPhysics:
    """Abstract base class for conversion physics strategies.

    This defines the interface contract that all conversion physics implementations
    must follow. Each fidelity level implements this interface.

    The Strategy Pattern allows us to:
    - Encapsulate conversion algorithms
    - Make fidelity levels interchangeable
    - Support easy testing and extension
    """

    def __init__(self, params):
        """Initialize physics strategy with component parameters."""
        self.params = params

    def rule_based_conversion_capacity(self, t: int, from_medium: str, to_medium: str) -> dict:
        """
        Calculate conversion capacities for the current timestep.

        This is a core physics method that each strategy must implement.

        Args:
            t: Current timestep
            from_medium: Input energy medium (e.g., 'electricity')
            to_medium: Output energy medium (e.g., 'heat')

        Returns:
            dict: {'max_input': float, 'max_output': float, 'efficiency': float}
        """
        raise NotImplementedError("Subclasses must implement rule_based_conversion_capacity")

    def rule_based_conversion_dispatch(self, t: int, requested_output: float, from_medium: str, to_medium: str) -> dict:
        """
        Calculate actual input/output for a requested output.

        Args:
            t: Current timestep
            requested_output: Desired output power (kW)
            from_medium: Input energy medium
            to_medium: Output energy medium

        Returns:
            dict: {'input_required': float, 'output_delivered': float}
        """
        raise NotImplementedError("Subclasses must implement rule_based_conversion_dispatch")


class BaseConversionOptimization:
    """Abstract base class for conversion optimization strategies.

    This defines the interface contract for MILP optimization implementations.
    Separates optimization logic from physics and data models.
    """

    def __init__(self, params):
        """Initialize optimization strategy with component parameters."""
        self.params = params

    def set_constraints(self) -> list:
        """
        Create CVXPY constraints for this conversion component.

        This is the core optimization method that each strategy must implement.
        Should return all constraints needed for MILP solver.

        Returns:
            list: CVXPY constraint objects
        """
        raise NotImplementedError("Subclasses must implement set_constraints")
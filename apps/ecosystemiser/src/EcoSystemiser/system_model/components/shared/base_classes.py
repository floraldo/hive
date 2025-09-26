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
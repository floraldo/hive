import cvxpy as cp
import numpy as np
from .water_component import WaterComponent
from hive_logging import get_logger

logger = get_logger(__name__)

class EvaporationDemand(WaterComponent):
    def __init__(self, name, temp_profile, n, W_max=None, economic=None, environmental=None):
        """Evaporation demand model using temperature-based profile.
        
        Args:
            temp_profile (np.array): Temperature profile in °C
            W_max (float): Maximum evaporation rate in m³/hour
        """
        super().__init__(n, name, economic, environmental)
        self.type = "consumption"
        self.medium = "water"
        self.W_max = W_max
        
        # Create temperature-based evaporation profile
        # Using linear term (85%) and small quadratic term (15%) for temperature > 0
        T = np.maximum(0, temp_profile)  # Only positive temperatures
        evap_profile = 0.85 * (T/30) + 0.15 * (T/30)**2  # Normalized to typical max temp
        evap_profile = np.maximum(0.1, evap_profile)  # Minimum 10% evaporation
        
        # Create flow variable and set constraint
        self.flows['sink']['W_in'] = {
            'type': 'water',
            'value': cp.Variable(n, name='W_in')
        }
        
        # Set demand based on profile and max rate
        self.constraints += [
            self.flows['sink']['W_in']['value'] == evap_profile * W_max
        ]

if __name__ == "__main__":
    # Test code
    n = 24
    temp = np.linspace(0, 30, n)  # Test temperature range
    surface_area = 100  # m²
    evap = EvaporationDemand("TEST", temp, n, surface_area)
    logger.info("Evaporation profile created successfully")
    logger.info(f"Maximum evaporation rate: {evap.W_max:.3f} m³/hour")
    logger.info(f"Daily maximum evaporation: {evap.W_max * 24:.1f} m³/day")
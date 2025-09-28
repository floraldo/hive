import cvxpy as cp
import numpy as np
from .water_component import WaterComponent
from hive_logging import get_logger

logger = get_logger(__name__)


class RainwaterSource(WaterComponent):
    def __init__(self, name, W_profile, n, W_max=None, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "generation"
        self.medium = "water"
        self.W_max = W_max
        self.flows["source"]["W_out"] = {"type": "water", "value": cp.Variable(n, name="W_out")}
        self.constraints += [self.flows["source"]["W_out"]["value"] == W_profile * W_max]

    def get_water_collected(self):
        """Override to calculate total water collection."""
        if isinstance(self.flows["source"]["W_out"]["value"], cp.Variable):
            return np.sum(self.flows["source"]["W_out"]["value"].value) / 1e3
        return np.sum(self.flows["source"]["W_out"]["value"]) / 1e3

    def print_stats(self):
        """Print component-specific statistics."""
        logger.info(f"\nRainwater Collection Statistics for {self.name}:")
        logger.info(f"Maximum Collection Rate: {self.W_max:.3f} m³/hour")
        logger.info(f"Average Collection Rate: {np.mean(W_profile):.3f} m³/hour")
        logger.info(f"Total Annual Collection: {np.sum(W_profile):.1f} m³")

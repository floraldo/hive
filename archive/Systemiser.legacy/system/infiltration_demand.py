import cvxpy as cp
import numpy as np
from .water_component import WaterComponent

class InfiltrationDemand(WaterComponent):
    def __init__(self, name, n, W_max, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "consumption"
        self.medium = "water"
        self.W_max = W_max
        
        # Initialize with None - will be set by master component
        self.flows['sink']['W_in'] = {
            'type': 'water',
            'value': None
        }
        
        self.constraints = []  # Start with empty constraints

    def set_controlled_flow(self, controlling_flow):
        """Set the flow value from a controlling component.
        
        Args:
            controlling_flow: cvxpy Variable representing the controlled flow
        """
        self.flows['sink']['W_in']['value'] = controlling_flow
        # Update constraint for maximum rate
        self.constraints = [
            self.flows['sink']['W_in']['value'] <= self.W_max
        ]
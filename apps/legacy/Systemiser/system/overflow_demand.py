import cvxpy as cp
from .water_component import WaterComponent

class OverflowDemand(WaterComponent):
    def __init__(self, name, n, W_max, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "consumption"
        self.medium = "water"
        self.W_max = W_max
        
        # Overflow can handle unlimited input (no real upper bound)
        self.flows['sink']['W_in'] = {
            'type': 'water',
            'value': cp.Variable(n, nonneg=True, name=f'{name}_W_in')
        }
        
        # No upper bound constraint - can handle any overflow 
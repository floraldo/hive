import cvxpy as cp
from .water_component import WaterComponent

class WaterDemand(WaterComponent):
    def __init__(self, name, W_profile, n, W_max=None, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "consumption"
        self.medium = "water"
        self.W_max = W_max
        self.flows['sink']['W_in'] = {
            'type': 'water',
            'value': cp.Variable(n, name='W_in')
        }
        self.constraints += [
            self.flows['sink']['W_in']['value'] == W_profile * W_max
        ] 
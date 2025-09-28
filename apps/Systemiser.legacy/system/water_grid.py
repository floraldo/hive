import cvxpy as cp
from .water_component import WaterComponent

class WaterGrid(WaterComponent):
    def __init__(self, name, W_max, n, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "transmission"
        self.medium = "water"
        self.W_max = W_max
        self.bidirectional = True
        
        # Similar to electrical grid, but for water
        self.flows['sink']['W_feed'] = {
            'type': 'water',
            'value': cp.Variable(n, nonneg=True, name=f'{name}_W_feed')
        }
        self.flows['source']['W_draw'] = {
            'type': 'water',
            'value': cp.Variable(n, nonneg=True, name=f'{name}_W_draw')
        }
        
        self.constraints += [
            self.flows['sink']['W_feed']['value'] <= self.W_max,
            self.flows['source']['W_draw']['value'] <= self.W_max
        ] 
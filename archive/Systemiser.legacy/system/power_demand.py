import cvxpy as cp
from .component import Component


class PowerDemand(Component):
    def __init__(self, name, P_profile, n, P_max=None, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.P_max = P_max
        self.type = "consumption"
        self.medium = "electricity"
        self.profile = P_profile
        self.flows['sink']['P_in'] = {
            'type': 'electricity',
            'value': cp.Variable(n, name='P_in'),
            'profile': P_profile
        }
        self.constraints += [self.flows['sink']['P_in']['value'] == P_profile * P_max]

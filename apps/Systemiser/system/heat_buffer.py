import cvxpy as cp
import numpy as np
from .component import Component


class HeatBuffer(Component):
    def __init__(self, name, P_max, E_max, E_init, eta, n, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "storage"
        self.type2 = "heat"
        self.medium = "heat"
        self.P_max = P_max
        self.E_max = E_max
        self.E_init = E_init
        self.capacity = E_max
        self.eta = eta
        self.E = cp.Variable(self.N, name=f'{name}_E')
        self.flows['sink']['P_cha'] = {'type': 'heat', 'value': cp.Variable(n, nonneg=True, name=f'{name}_P_cha')}
        self.flows['source']['P_dis'] = {'type': 'heat', 'value': cp.Variable(n, nonneg=True, name=f'{name}_P_dis')}
        self.constraints += [
            self.E[0] == self.E_init,
            self.E >= 0,
            self.E <= self.E_max,
            self.flows['sink']['P_cha']['value'] <= self.P_max,
            self.flows['source']['P_dis']['value'] <= self.P_max,
        ]

    def set_constraints(self):
        super().set_constraints()
        for t in range(1, self.N):
            self.constraints += [
                self.E[t] == self.E[t - 1] + self.eta * (
                            self.flows['sink']['P_cha']['value'][t] - self.flows['source']['P_dis']['value'][t]),
            ]
        return self.constraints

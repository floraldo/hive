import cvxpy as cp
import numpy as np
from .water_component import WaterComponent


class WaterStorage(WaterComponent):
    def __init__(self, name, W_max, E_max, E_init, eta, n, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "storage"
        self.type2 = "water"
        self.medium = "water"
        self.W_max = W_max
        self.E_max = E_max
        self.E_init = E_init
        self.capacity = E_max
        self.eta = eta
        self.E = cp.Variable(self.N, name=f"{name}_E")
        self.flows["sink"]["W_in"] = {"type": "water", "value": cp.Variable(n, nonneg=True, name=f"{name}_W_in")}
        self.flows["source"]["W_out"] = {"type": "water", "value": cp.Variable(n, nonneg=True, name=f"{name}_W_out")}
        self.constraints += [
            self.E[0] == self.E_init,
            self.E >= 0,
            self.E <= self.E_max,
            self.flows["sink"]["W_in"]["value"] <= self.W_max,
            self.flows["source"]["W_out"]["value"] <= self.W_max,
        ]

    def set_constraints(self):
        super().set_constraints()
        for t in range(1, self.N):
            self.constraints += [
                self.E[t]
                == self.E[t - 1]
                + self.eta * (self.flows["sink"]["W_in"]["value"][t] - self.flows["source"]["W_out"]["value"][t]),
            ]
        return self.constraints

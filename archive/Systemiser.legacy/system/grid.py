import cvxpy as cp
from .component import Component


class Grid(Component):
    def __init__(self, name, P_max, n, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "transmission"
        self.medium = "electricity"
        self.P_max = P_max
        self.bidirectional = True
        self.flows["sink"]["P_feed"] = {
            "type": "electricity",
            "value": cp.Variable(n, nonneg=True, name=f"{name}_P_feed"),
        }
        self.flows["source"]["P_draw"] = {
            "type": "electricity",
            "value": cp.Variable(n, nonneg=True, name=f"{name}_P_draw"),
        }
        self.constraints += [
            self.flows["sink"]["P_feed"]["value"] <= self.P_max,
            self.flows["source"]["P_draw"]["value"] <= self.P_max,
        ]

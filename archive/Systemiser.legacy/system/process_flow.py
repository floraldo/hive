class ProcessFlow:
    """Represents a passive process flow like losses, infiltration, etc."""

    def __init__(self, name, flow_type, source, target, values):
        self.name = name
        self.flow_type = flow_type
        self.source = source
        self.target = target
        self.values = values
        self.is_process = True

    @property
    def total(self):
        return float(sum(self.values))

    @property
    def mean(self):
        return float(sum(self.values) / len(self.values))

    @property
    def max(self):
        return float(max(self.values))

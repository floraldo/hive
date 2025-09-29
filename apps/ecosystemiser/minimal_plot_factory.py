#!/usr/bin/env python3
"""Create a minimal working plot_factory.py to unblock imports."""

minimal_content = '''"""Plot factory for creating visualizations from simulation results."""

import json
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from hive_logging import get_logger
from plotly.subplots import make_subplots

logger = get_logger(__name__)


class PlotFactory:
    """Factory for creating various plot types from simulation data."""

    def __init__(self) -> None:
        """Initialize plot factory with default styling."""
        self.default_layout = {
            "template": "plotly_white",
            "font": {"size": 12},
            "margin": {"l": 60, "r": 30, "t": 60, "b": 60},
            "hovermode": "x unified"
        }

    def create_energy_flow_plot(self, system, timestep: int | None = None) -> Dict:
        """Create energy flow visualization - minimal implementation."""
        return {}

    def create_timeseries_plot(self, system, components: Optional[List[str]] = None) -> Dict:
        """Create time series plot - minimal implementation."""
        return {}

    def create_kpi_dashboard(self, kpis: Dict[str, float]) -> Dict:
        """Create KPI dashboard - minimal implementation."""
        return {}

    def create_load_profile_plot(self, profiles: Dict[str, np.ndarray]) -> Dict:
        """Create load profile plot - minimal implementation."""
        return {}
'''

with open("src/ecosystemiser/datavis/plot_factory.py", "w", encoding="utf-8") as f:
    f.write(minimal_content)

print("Created minimal plot_factory.py")

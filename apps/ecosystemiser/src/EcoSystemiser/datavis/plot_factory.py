"""Plot factory for creating visualizations from simulation results."""
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Union
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import logging

logger = logging.getLogger(__name__)

class PlotFactory:
    """Factory for creating various plot types from simulation data."""

    def __init__(self):
        """Initialize plot factory with default styling."""
        self.default_layout = {
            'template': 'plotly_white',
            'font': {'size': 12},
            'margin': {'l': 60, 'r': 30, 't': 60, 'b': 60},
            'hovermode': 'x unified'
        }

    def create_energy_flow_plot(self, system, timestep: Optional[int] = None) -> Dict:
        """Create energy flow visualization.

        Args:
            system: Solved system object
            timestep: Specific timestep to visualize (None for average)

        Returns:
            Plotly figure as dictionary
        """
        flows_data = []

        for flow_name, flow_info in system.flows.items():
            if flow_info['type'] == 'electricity':
                values = flow_info['value']
                if isinstance(values, np.ndarray):
                    if timestep is not None:
                        value = values[timestep] if timestep < len(values) else 0
                    else:
                        value = np.mean(values)

                    if value > 0.01:  # Only show significant flows
                        flows_data.append({
                            'source': flow_info['source'],
                            'target': flow_info['target'],
                            'value': float(value),
                            'label': f"{value:.1f} kW"
                        })

        # Create Sankey diagram
        if flows_data:
            # Get unique nodes
            nodes = set()
            for flow in flows_data:
                nodes.add(flow['source'])
                nodes.add(flow['target'])
            node_list = sorted(list(nodes))
            node_dict = {node: i for i, node in enumerate(node_list)}

            # Create Sankey
            fig = go.Figure(data=[go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=node_list,
                    color="lightblue"
                ),
                link=dict(
                    source=[node_dict[f['source']] for f in flows_data],
                    target=[node_dict[f['target']] for f in flows_data],
                    value=[f['value'] for f in flows_data],
                    label=[f['label'] for f in flows_data]
                )
            )])

            title = f"Energy Flows at t={timestep}" if timestep else "Average Energy Flows"
            fig.update_layout(title=title, **self.default_layout)

            return fig.to_dict()

        return {}

    def create_timeseries_plot(self, system, components: Optional[List[str]] = None) -> Dict:
        """Create time series plot of component states.

        Args:
            system: Solved system object
            components: List of component names to plot (None for all storage)

        Returns:
            Plotly figure as dictionary
        """
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("Power Flows", "Storage Levels"),
            shared_xaxes=True,
            vertical_spacing=0.1
        )

        time_axis = list(range(system.N))

        # Plot power flows
        for flow_name, flow_info in system.flows.items():
            if flow_info['type'] == 'electricity':
                values = flow_info['value']
                if isinstance(values, np.ndarray) and np.max(np.abs(values)) > 0.01:
                    fig.add_trace(
                        go.Scatter(
                            x=time_axis,
                            y=values,
                            mode='lines',
                            name=f"{flow_info['source']}→{flow_info['target']}",
                            hovertemplate='%{y:.2f} kW'
                        ),
                        row=1, col=1
                    )

        # Plot storage levels
        for comp_name, comp in system.components.items():
            if components and comp_name not in components:
                continue

            if comp.type == "storage" and hasattr(comp, 'E'):
                if isinstance(comp.E, np.ndarray):
                    fig.add_trace(
                        go.Scatter(
                            x=time_axis,
                            y=comp.E,
                            mode='lines',
                            name=f"{comp_name} Level",
                            hovertemplate='%{y:.2f} kWh'
                        ),
                        row=2, col=1
                    )

                    # Add capacity limit line
                    if hasattr(comp, 'E_max'):
                        fig.add_hline(
                            y=comp.E_max,
                            line_dash="dash",
                            line_color="red",
                            annotation_text=f"{comp_name} Max",
                            row=2, col=1
                        )

        # Update layout
        fig.update_xaxes(title_text="Hour", row=2, col=1)
        fig.update_yaxes(title_text="Power (kW)", row=1, col=1)
        fig.update_yaxes(title_text="Energy (kWh)", row=2, col=1)

        fig.update_layout(
            title="System Time Series",
            height=600,
            **self.default_layout
        )

        return fig.to_dict()

    def create_kpi_dashboard(self, kpis: Dict[str, float]) -> Dict:
        """Create a dashboard visualization of KPIs.

        Args:
            kpis: Dictionary of calculated KPIs

        Returns:
            Plotly figure as dictionary
        """
        # Categorize KPIs
        categories = {
            'Energy': ['grid_import', 'grid_export', 'generation', 'solar'],
            'Efficiency': ['self_consumption', 'renewable_fraction'],
            'Economic': ['capex', 'opex'],
            'Environmental': ['co2']
        }

        # Create subplots for different KPI categories
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=list(categories.keys()),
            specs=[[{'type': 'bar'}, {'type': 'bar'}],
                   [{'type': 'bar'}, {'type': 'indicator'}]]
        )

        row_col_map = [(1, 1), (1, 2), (2, 1), (2, 2)]

        for idx, (category, keywords) in enumerate(categories.items()):
            row, col = row_col_map[idx]

            # Filter KPIs for this category
            cat_kpis = {
                k: v for k, v in kpis.items()
                if any(kw in k.lower() for kw in keywords)
            }

            if cat_kpis:
                if category == 'Environmental' and len(cat_kpis) == 1:
                    # Use indicator for single value
                    value = list(cat_kpis.values())[0]
                    fig.add_trace(
                        go.Indicator(
                            mode="number+delta",
                            value=value,
                            title={'text': "Total CO2 (kg)"},
                            delta={'reference': value * 1.2},  # Compare to 20% higher
                            domain={'x': [0, 1], 'y': [0, 1]}
                        ),
                        row=row, col=col
                    )
                else:
                    # Use bar chart for multiple values
                    labels = [k.replace('_', ' ').title() for k in cat_kpis.keys()]
                    values = list(cat_kpis.values())

                    fig.add_trace(
                        go.Bar(
                            x=labels,
                            y=values,
                            name=category,
                            text=[f"{v:.2f}" for v in values],
                            textposition='auto'
                        ),
                        row=row, col=col
                    )

        fig.update_layout(
            title="KPI Dashboard",
            height=600,
            showlegend=False,
            **self.default_layout
        )

        return fig.to_dict()

    def create_load_profile_plot(self, profiles: Dict[str, np.ndarray]) -> Dict:
        """Create plot of load and generation profiles.

        Args:
            profiles: Dictionary of profile arrays

        Returns:
            Plotly figure as dictionary
        """
        fig = go.Figure()

        time_axis = list(range(len(next(iter(profiles.values())))))

        for name, profile in profiles.items():
            fig.add_trace(
                go.Scatter(
                    x=time_axis,
                    y=profile,
                    mode='lines',
                    name=name.replace('_', ' ').title(),
                    stackgroup='one' if 'demand' in name.lower() else None
                )
            )

        fig.update_layout(
            title="Load and Generation Profiles",
            xaxis_title="Hour",
            yaxis_title="Power (kW) / Demand (kWh)",
            **self.default_layout
        )

        return fig.to_dict()

    def create_storage_animation(self, system) -> Dict:
        """Create animated visualization of storage levels over time.

        Args:
            system: Solved system object

        Returns:
            Plotly figure as dictionary
        """
        frames = []
        storage_comps = [c for c in system.components.values() if c.type == "storage"]

        if not storage_comps:
            return {}

        # Create frames for each timestep
        for t in range(system.N):
            frame_data = []
            for comp in storage_comps:
                if hasattr(comp, 'E') and isinstance(comp.E, np.ndarray):
                    level = comp.E[t] if t < len(comp.E) else 0
                    max_level = getattr(comp, 'E_max', 100)
                    frame_data.append(
                        go.Bar(
                            x=[comp.name],
                            y=[level],
                            name=comp.name,
                            text=f"{level:.1f}/{max_level:.0f}",
                            textposition='auto'
                        )
                    )

            frames.append(go.Frame(data=frame_data, name=str(t)))

        # Initial data
        initial_data = []
        for comp in storage_comps:
            if hasattr(comp, 'E') and isinstance(comp.E, np.ndarray):
                level = comp.E[0]
                max_level = getattr(comp, 'E_max', 100)
                initial_data.append(
                    go.Bar(
                        x=[comp.name],
                        y=[level],
                        name=comp.name,
                        text=f"{level:.1f}/{max_level:.0f}",
                        textposition='auto'
                    )
                )

        # Create figure with animation
        fig = go.Figure(
            data=initial_data,
            frames=frames,
            layout=go.Layout(
                title="Storage Levels Animation",
                yaxis=dict(range=[0, max([getattr(c, 'E_max', 100) for c in storage_comps])]),
                updatemenus=[{
                    'type': 'buttons',
                    'showactive': False,
                    'buttons': [
                        {'label': 'Play', 'method': 'animate', 'args': [None, {'frame': {'duration': 100}}]},
                        {'label': 'Pause', 'method': 'animate', 'args': [[None], {'frame': {'duration': 0}, 'mode': 'immediate'}]}
                    ]
                }],
                sliders=[{
                    'steps': [{'args': [[f.name], {'frame': {'duration': 0}, 'mode': 'immediate'}],
                              'label': f"t={f.name}", 'method': 'animate'} for f in frames],
                    'active': 0,
                    'y': 0,
                    'len': 0.9,
                    'x': 0.1,
                    'xanchor': 'left',
                    'y': 0,
                    'yanchor': 'top'
                }],
                **self.default_layout
            )
        )

        return fig.to_dict()

    def export_plots_to_html(self, plots: List[Dict], output_path: str):
        """Export multiple plots to a single HTML file.

        Args:
            plots: List of plotly figure dictionaries
            output_path: Path for output HTML file
        """
        from plotly.subplots import make_subplots
        import plotly.offline as pyo

        # Convert dicts back to Figure objects
        figures = [go.Figure(plot) for plot in plots if plot]

        # Create HTML with all plots
        html_parts = []
        for i, fig in enumerate(figures):
            html_parts.append(pyo.plot(fig, output_type='div', include_plotlyjs=(i == 0)))

        # Combine into single HTML
        html_content = f"""
        <html>
        <head>
            <title>EcoSystemiser Simulation Results</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .plot-container {{ margin: 30px 0; }}
            </style>
        </head>
        <body>
            <h1>EcoSystemiser Simulation Results</h1>
            {''.join(f'<div class="plot-container">{html}</div>' for html in html_parts)}
        </body>
        </html>
        """

        with open(output_path, 'w') as f:
            f.write(html_content)

        logger.info(f"Exported {len(figures)} plots to {output_path}")
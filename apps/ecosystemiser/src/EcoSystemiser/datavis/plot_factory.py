"""Plot factory for creating visualizations from simulation results."""
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Union
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
from EcoSystemiser.hive_logging_adapter import get_logger
logger = get_logger(__name__)

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

    def create_economic_summary_plot(self, economic_data: Dict[str, Any]) -> Dict:
        """Create economic summary visualization.

        Args:
            economic_data: Economic analysis results

        Returns:
            Plotly figure as dictionary
        """
        # Create subplots for different economic metrics
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Cost Breakdown", "Component Costs",
                "Cash Flow Analysis", "Economic Indicators"
            ),
            specs=[
                [{'type': 'pie'}, {'type': 'bar'}],
                [{'type': 'scatter'}, {'type': 'indicator'}]
            ]
        )

        # Cost breakdown pie chart
        if 'capex_total' in economic_data and 'opex_total' in economic_data:
            labels = ['CAPEX', 'OPEX']
            values = [economic_data['capex_total'], economic_data['opex_total']]
            fig.add_trace(
                go.Pie(labels=labels, values=values, hole=0.3),
                row=1, col=1
            )

        # Component costs bar chart
        if 'component_costs' in economic_data:
            comp_names = list(economic_data['component_costs'].keys())
            capex_values = [c.get('capex', 0) for c in economic_data['component_costs'].values()]
            opex_values = [c.get('opex_annual', 0) for c in economic_data['component_costs'].values()]

            fig.add_trace(
                go.Bar(name='CAPEX', x=comp_names, y=capex_values),
                row=1, col=2
            )
            fig.add_trace(
                go.Bar(name='OPEX', x=comp_names, y=opex_values),
                row=1, col=2
            )

        # NPV cash flow over time (simplified projection)
        if 'npv' in economic_data and 'payback_period_years' in economic_data:
            years = list(range(21))  # 20-year project
            npv = economic_data['npv']
            payback = economic_data.get('payback_period_years', 10)

            # Simple linear approximation for visualization
            cash_flows = [-economic_data.get('capex_total', 0)]
            annual_benefit = economic_data.get('capex_total', 0) / max(payback, 1)
            for year in years[1:]:
                cash_flows.append(cash_flows[-1] + annual_benefit)

            fig.add_trace(
                go.Scatter(
                    x=years, y=cash_flows,
                    mode='lines+markers',
                    name='Cumulative Cash Flow',
                    line=dict(width=2)
                ),
                row=2, col=1
            )
            fig.add_hline(y=0, line_dash="dash", line_color="red", row=2, col=1)

        # Key economic indicators
        if 'lcoe' in economic_data:
            fig.add_trace(
                go.Indicator(
                    mode="number+delta",
                    value=economic_data['lcoe'],
                    title={'text': "LCOE ($/kWh)"},
                    delta={'reference': 0.15},  # Reference grid price
                    domain={'x': [0, 1], 'y': [0, 1]}
                ),
                row=2, col=2
            )

        fig.update_layout(
            title="Economic Analysis Summary",
            height=700,
            showlegend=True,
            **self.default_layout
        )

        return fig.to_dict()

    def create_sensitivity_heatmap(self, sensitivity_data: Dict[str, Any]) -> Dict:
        """Create sensitivity analysis heatmap.

        Args:
            sensitivity_data: Sensitivity analysis results

        Returns:
            Plotly figure as dictionary
        """
        if 'parameter_sensitivities' not in sensitivity_data:
            return {}

        # Extract sensitivity matrix
        param_sensitivities = sensitivity_data['parameter_sensitivities']

        # Create matrix for heatmap
        params = list(param_sensitivities.keys())
        kpis = set()
        for param_data in param_sensitivities.values():
            kpis.update(param_data.keys())
        kpis = sorted(list(kpis))

        # Build sensitivity matrix
        matrix = []
        for param in params:
            row = []
            for kpi in kpis:
                value = param_sensitivities[param].get(kpi, 0)
                row.append(value)
            matrix.append(row)

        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=matrix,
            x=kpis,
            y=params,
            colorscale='RdBu',
            zmid=0,
            text=[[f"{v:.3f}" for v in row] for row in matrix],
            texttemplate="%{text}",
            textfont={"size": 10}
        ))

        fig.update_layout(
            title="Parameter Sensitivity Analysis",
            xaxis_title="KPIs",
            yaxis_title="Parameters",
            height=max(400, len(params) * 30),
            **self.default_layout
        )

        return fig.to_dict()

    def create_pareto_frontier_plot(self, sensitivity_data: Dict[str, Any]) -> Dict:
        """Create Pareto frontier visualization for trade-off analysis.

        Args:
            sensitivity_data: Sensitivity analysis results with trade-off data

        Returns:
            Plotly figure as dictionary
        """
        trade_offs = sensitivity_data.get('trade_off_analysis', {})
        pareto_points = trade_offs.get('pareto_frontier', [])

        if not pareto_points:
            return {}

        # Extract cost and renewable values
        costs = [p['cost'] for p in pareto_points]
        renewables = [p['renewable'] for p in pareto_points]

        # Create scatter plot
        fig = go.Figure()

        # Add Pareto frontier points
        fig.add_trace(go.Scatter(
            x=costs,
            y=renewables,
            mode='markers+lines',
            name='Pareto Frontier',
            marker=dict(size=10, color='red'),
            line=dict(color='red', dash='dash'),
            text=[f"Cost: ${c:,.0f}<br>Renewable: {r:.2%}"
                  for c, r in zip(costs, renewables)],
            hovertemplate="%{text}<extra></extra>"
        ))

        # Add annotation for trade-off
        if 'cost_renewable_correlation' in trade_offs:
            correlation = trade_offs['cost_renewable_correlation']
            fig.add_annotation(
                text=f"Correlation: {correlation:.3f}",
                xref="paper", yref="paper",
                x=0.02, y=0.98,
                showarrow=False,
                font=dict(size=12),
                bgcolor="white",
                bordercolor="gray",
                borderwidth=1
            )

        fig.update_layout(
            title="Cost vs Renewable Fraction Trade-off",
            xaxis_title="Total Cost ($)",
            yaxis_title="Renewable Fraction",
            yaxis_tickformat='.0%',
            height=500,
            **self.default_layout
        )

        return fig.to_dict()

    def create_technical_kpi_gauges(self, kpi_data: Dict[str, float]) -> Dict:
        """Create gauge charts for technical KPIs.

        Args:
            kpi_data: Technical KPI analysis results

        Returns:
            Plotly figure as dictionary
        """
        # Define KPIs to display as gauges
        gauge_kpis = [
            ('grid_self_sufficiency', 'Grid Self-Sufficiency', 0, 1, 0.7),
            ('renewable_fraction', 'Renewable Fraction', 0, 1, 0.5),
            ('battery_efficiency', 'Battery Efficiency', 0, 1, 0.85),
            ('load_factor', 'Load Factor', 0, 1, 0.6)
        ]

        # Filter available KPIs
        available_gauges = [(k, n, mi, ma, t) for k, n, mi, ma, t in gauge_kpis
                           if k in kpi_data]

        if not available_gauges:
            return {}

        # Create subplots
        cols = min(len(available_gauges), 2)
        rows = (len(available_gauges) + 1) // 2

        fig = make_subplots(
            rows=rows, cols=cols,
            subplot_titles=[g[1] for g in available_gauges],
            specs=[[{'type': 'indicator'} for _ in range(cols)] for _ in range(rows)]
        )

        # Add gauge charts
        for idx, (key, name, min_val, max_val, threshold) in enumerate(available_gauges):
            row = idx // cols + 1
            col = idx % cols + 1

            value = kpi_data[key]

            # Determine color based on threshold
            if value >= threshold:
                bar_color = "green"
            elif value >= threshold * 0.7:
                bar_color = "yellow"
            else:
                bar_color = "red"

            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=value,
                    gauge={
                        'axis': {'range': [min_val, max_val]},
                        'bar': {'color': bar_color},
                        'threshold': {
                            'line': {'color': "black", 'width': 2},
                            'thickness': 0.75,
                            'value': threshold
                        }
                    },
                    number={'valueformat': '.1%' if max_val == 1 else '.2f'}
                ),
                row=row, col=col
            )

        fig.update_layout(
            title="Technical Performance Indicators",
            height=300 * rows,
            **self.default_layout
        )

        return fig.to_dict()

    def create_optimization_convergence_plot(self, solver_metrics: Dict[str, Any]) -> Dict:
        """Create optimization convergence visualization.

        Args:
            solver_metrics: Solver metrics including convergence data

        Returns:
            Plotly figure as dictionary
        """
        # This would be enhanced if we had iteration data from the solver
        # For now, create a simple status indicator

        fig = go.Figure()

        status = solver_metrics.get('status', 'unknown')
        solve_time = solver_metrics.get('solve_time', 0)
        objective_value = solver_metrics.get('objective_value', 0)

        # Create status indicator
        status_color = {
            'optimal': 'green',
            'feasible': 'yellow',
            'infeasible': 'red',
            'unknown': 'gray'
        }.get(status, 'gray')

        fig.add_trace(go.Indicator(
            mode="number+delta+gauge",
            value=objective_value,
            title={'text': f"Optimization Status: {status.upper()}"},
            gauge={
                'axis': {'visible': False},
                'bar': {'color': status_color}
            },
            domain={'x': [0.25, 0.75], 'y': [0.3, 0.7]}
        ))

        # Add solve time annotation
        fig.add_annotation(
            text=f"Solve Time: {solve_time:.2f}s",
            xref="paper", yref="paper",
            x=0.5, y=0.15,
            showarrow=False,
            font=dict(size=14)
        )

        fig.update_layout(
            title="Optimization Results",
            height=400,
            **self.default_layout
        )

        return fig.to_dict()
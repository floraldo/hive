"""Plot factory for creating visualizations from simulation results."""

import json
from typing import Any, Dict, List

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
            "font": {"size": 12}
            "margin": {"l": 60, "r": 30, "t": 60, "b": 60}
            "hovermode": "x unified"
        }

    def create_energy_flow_plot(self, system, timestep: int | None = None) -> Dict:
        """Create energy flow visualization.

        Args:
            system: Solved system object
            timestep: Specific timestep to visualize (None for average)

        Returns:
            Plotly figure as dictionary
        """
        flows_data = []

        for flow_name, flow_info in system.flows.items():
            if flow_info["type"] == "electricity":
                values = flow_info["value"]
                if isinstance(values, np.ndarray):
                    if timestep is not None:
                        value = values[timestep] if timestep < len(values) else 0
                    else:
                        value = np.mean(values)

                    if value > 0.01:  # Only show significant flows
                        flows_data.append(
                            {
                                "source": flow_info["source"],
                                "target": flow_info["target"],
                                "value": float(value),
                                "label": f"{value:.1f} kW"
                            }
                        )

        # Create Sankey diagram
        if flows_data:
            # Get unique nodes
            nodes = set()
            for flow in flows_data:
                nodes.add(flow["source"])
                nodes.add(flow["target"])
            node_list = sorted(list(nodes))
            node_dict = {node: i for i, node in enumerate(node_list)}

            # Create Sankey
            fig = go.Figure(
                data=[
                    go.Sankey(
                        node=dict(
                            pad=15
                            thickness=20
                            line=dict(color="black", width=0.5)
                            label=node_list
                            color="lightblue"
                        )
                        link=dict(
                            source=[node_dict[f["source"]] for f in flows_data]
                            target=[node_dict[f["target"]] for f in flows_data]
                            value=[f["value"] for f in flows_data]
                            label=[f["label"] for f in flows_data]
                        )
                    )
                ]
            )

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
            rows=2
            cols=1
            subplot_titles=("Power Flows", "Storage Levels")
            shared_xaxes=True
            vertical_spacing=0.1
        )

        time_axis = list(range(system.N))

        # Plot power flows
        for flow_name, flow_info in system.flows.items():
            if flow_info["type"] == "electricity":
                values = flow_info["value"]
                if isinstance(values, np.ndarray) and np.max(np.abs(values)) > 0.01:
                    fig.add_trace(
                        go.Scatter(
                            x=time_axis
                            y=values
                            mode="lines"
                            name=f"{flow_info['source']}→{flow_info['target']}"
                            hovertemplate="%{y:.2f} kW"
                        )
                        row=1
                        col=1
                    )

        # Plot storage levels
        for comp_name, comp in system.components.items():
            if components and comp_name not in components:
                continue

            if comp.type == "storage" and hasattr(comp, "E"):
                if isinstance(comp.E, np.ndarray):
                    fig.add_trace(
                        go.Scatter(
                            x=time_axis
                            y=comp.E
                            mode="lines"
                            name=f"{comp_name} Level"
                            hovertemplate="%{y:.2f} kWh"
                        )
                        row=2
                        col=1
                    )

                    # Add capacity limit line
                    if hasattr(comp, "E_max"):
                        fig.add_hline(
                            y=comp.E_max
                            line_dash="dash"
                            line_color="red"
                            annotation_text=f"{comp_name} Max"
                            row=2
                            col=1
                        )

        # Update layout
        fig.update_xaxes(title_text="Hour", row=2, col=1)
        fig.update_yaxes(title_text="Power (kW)", row=1, col=1)
        fig.update_yaxes(title_text="Energy (kWh)", row=2, col=1)

        fig.update_layout(title="System Time Series", height=600, **self.default_layout)

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
            "Energy": ["grid_import", "grid_export", "generation", "solar"],
            "Efficiency": ["self_consumption", "renewable_fraction"],
            "Economic": ["capex", "opex"],
            "Environmental": ["co2"]
        }

        # Create subplots for different KPI categories
        fig = make_subplots(
            rows=2
            cols=2
            subplot_titles=list(categories.keys())
            specs=[
                [{"type": "bar"}, {"type": "bar"}]
                [{"type": "bar"}, {"type": "indicator"}]
            ]
        )

        row_col_map = [(1, 1), (1, 2), (2, 1), (2, 2)]

        for idx, (category, keywords) in enumerate(categories.items()):
            row, col = row_col_map[idx]

            # Filter KPIs for this category
            cat_kpis = {k: v for k, v in kpis.items() if any(kw in k.lower() for kw in keywords)}

            if cat_kpis:
                if category == "Environmental" and len(cat_kpis) == 1:
                    # Use indicator for single value
                    value = list(cat_kpis.values())[0]
                    fig.add_trace(
                        go.Indicator(
                            mode="number+delta"
                            value=value
                            title={"text": "Total CO2 (kg)"}
                            delta={"reference": value * 1.2},  # Compare to 20% higher
                            domain={"x": [0, 1], "y": [0, 1]}
                        )
                        row=row
                        col=col
                    )
                else:
                    # Use bar chart for multiple values
                    labels = [k.replace("_", " ").title() for k in cat_kpis.keys()]
                    values = list(cat_kpis.values())

                    fig.add_trace(
                        go.Bar(
                            x=labels
                            y=values
                            name=category
                            text=[f"{v:.2f}" for v in values]
                            textposition="auto"
                        )
                        row=row
                        col=col
                    )

        fig.update_layout(title="KPI Dashboard", height=600, showlegend=False, **self.default_layout)

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
                    x=time_axis
                    y=profile
                    mode="lines"
                    name=name.replace("_", " ").title()
                    stackgroup="one" if "demand" in name.lower() else None
                )
            )

        fig.update_layout(
            title="Load and Generation Profiles"
            xaxis_title="Hour"
            yaxis_title="Power (kW) / Demand (kWh)"
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
                if hasattr(comp, "E") and isinstance(comp.E, np.ndarray):
                    level = comp.E[t] if t < len(comp.E) else 0
                    max_level = getattr(comp, "E_max", 100)
                    frame_data.append(
                        go.Bar(
                            x=[comp.name]
                            y=[level]
                            name=comp.name
                            text=f"{level:.1f}/{max_level:.0f}"
                            textposition="auto"
                        )
                    )

            frames.append(go.Frame(data=frame_data, name=str(t)))

        # Initial data
        initial_data = []
        for comp in storage_comps:
            if hasattr(comp, "E") and isinstance(comp.E, np.ndarray):
                level = comp.E[0]
                max_level = getattr(comp, "E_max", 100)
                initial_data.append(
                    go.Bar(
                        x=[comp.name]
                        y=[level]
                        name=comp.name
                        text=f"{level:.1f}/{max_level:.0f}"
                        textposition="auto"
                    )
                )

        # Create figure with animation
        fig = go.Figure(
            data=initial_data
            frames=frames
            layout=go.Layout(
                title="Storage Levels Animation"
                yaxis=dict(range=[0, max([getattr(c, "E_max", 100) for c in storage_comps])])
                updatemenus=[
                    {
                        "type": "buttons",
                        "showactive": False,
                        "buttons": [
                            {
                                "label": "Play",
                                "method": "animate",
                                "args": [None, {"frame": {"duration": 100}}]
                            }
                            {
                                "label": "Pause",
                                "method": "animate",
                                "args": [
                                    [None]
                                    {"frame": {"duration": 0}, "mode": "immediate"}
                                ]
                            }
                        ]
                    }
                ]
                sliders=[
                    {
                        "steps": [
                            {
                                "args": [
                                    [f.name]
                                    {"frame": {"duration": 0}, "mode": "immediate"}
                                ]
                                "label": f"t={f.name}",
                                "method": "animate"
                            }
                            for f in frames
                        ]
                        "active": 0,
                        "y": 0,
                        "len": 0.9,
                        "x": 0.1,
                        "xanchor": "left",
                        "y": 0,
                        "yanchor": "top"
                    }
                ]
                **self.default_layout
            )
        )

        return fig.to_dict()

    def export_plots_to_html(self, plots: List[Dict], output_path: str) -> None:
        """Export multiple plots to a single HTML file.

        Args:
            plots: List of plotly figure dictionaries
            output_path: Path for output HTML file
        """
        import plotly.offline as pyo
        from plotly.subplots import make_subplots

        # Convert dicts back to Figure objects
        figures = [go.Figure(plot) for plot in plots if plot]

        # Create HTML with all plots
        html_parts = []
        for i, fig in enumerate(figures):
            html_parts.append(pyo.plot(fig, output_type="div", include_plotlyjs=(i == 0)))

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

        with open(output_path, "w") as f:
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
            rows=2
            cols=2
            subplot_titles=(
                "Cost Breakdown"
                "Component Costs"
                "Cash Flow Analysis"
                "Economic Indicators"
            )
            specs=[
                [{"type": "pie"}, {"type": "bar"}]
                [{"type": "scatter"}, {"type": "indicator"}]
            ]
        )

        # Cost breakdown pie chart
        if "capex_total" in economic_data and "opex_total" in economic_data:
            labels = ["CAPEX", "OPEX"]
            values = [economic_data["capex_total"], economic_data["opex_total"]]
            fig.add_trace(go.Pie(labels=labels, values=values, hole=0.3), row=1, col=1)

        # Component costs bar chart
        if "component_costs" in economic_data:
            comp_names = list(economic_data["component_costs"].keys())
            capex_values = [c.get("capex", 0) for c in economic_data["component_costs"].values()]
            opex_values = [c.get("opex_annual", 0) for c in economic_data["component_costs"].values()]

            fig.add_trace(go.Bar(name="CAPEX", x=comp_names, y=capex_values), row=1, col=2)
            fig.add_trace(go.Bar(name="OPEX", x=comp_names, y=opex_values), row=1, col=2)

        # NPV cash flow over time (simplified projection)
        if "npv" in economic_data and "payback_period_years" in economic_data:
            years = list(range(21))  # 20-year project
            npv = economic_data["npv"]
            payback = economic_data.get("payback_period_years", 10)

            # Simple linear approximation for visualization
            cash_flows = [-economic_data.get("capex_total", 0)]
            annual_benefit = economic_data.get("capex_total", 0) / max(payback, 1)
            for year in years[1:]:
                cash_flows.append(cash_flows[-1] + annual_benefit)

            fig.add_trace(
                go.Scatter(
                    x=years
                    y=cash_flows
                    mode="lines+markers"
                    name="Cumulative Cash Flow"
                    line=dict(width=2)
                )
                row=2
                col=1
            )
            fig.add_hline(y=0, line_dash="dash", line_color="red", row=2, col=1)

        # Key economic indicators
        if "lcoe" in economic_data:
            fig.add_trace(
                go.Indicator(
                    mode="number+delta"
                    value=economic_data["lcoe"]
                    title={"text": "LCOE ($/kWh)"}
                    delta={"reference": 0.15},  # Reference grid price
                    domain={"x": [0, 1], "y": [0, 1]}
                )
                row=2
                col=2
            )

        fig.update_layout(
            title="Economic Analysis Summary"
            height=700
            showlegend=True
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
        if "parameter_sensitivities" not in sensitivity_data:
            return {}

        # Extract sensitivity matrix
        param_sensitivities = sensitivity_data["parameter_sensitivities"]

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
        fig = go.Figure(
            data=go.Heatmap(
                z=matrix
                x=kpis
                y=params
                colorscale="RdBu"
                zmid=0
                text=[[f"{v:.3f}" for v in row] for row in matrix]
                texttemplate="%{text}"
                textfont={"size": 10}
            )
        )

        fig.update_layout(
            title="Parameter Sensitivity Analysis"
            xaxis_title="KPIs"
            yaxis_title="Parameters"
            height=max(400, len(params) * 30)
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
        trade_offs = sensitivity_data.get("trade_off_analysis", {})
        pareto_points = trade_offs.get("pareto_frontier", [])

        if not pareto_points:
            return {}

        # Extract cost and renewable values
        costs = [p["cost"] for p in pareto_points]
        renewables = [p["renewable"] for p in pareto_points]

        # Create scatter plot
        fig = go.Figure()

        # Add Pareto frontier points
        fig.add_trace(
            go.Scatter(
                x=costs
                y=renewables
                mode="markers+lines"
                name="Pareto Frontier"
                marker=dict(size=10, color="red")
                line=dict(color="red", dash="dash")
                text=[f"Cost: ${c:,.0f}<br>Renewable: {r:.2%}" for c, r in zip(costs, renewables)]
                hovertemplate="%{text}<extra></extra>"
            )
        )

        # Add annotation for trade-off
        if "cost_renewable_correlation" in trade_offs:
            correlation = trade_offs["cost_renewable_correlation"]
            fig.add_annotation(
                text=f"Correlation: {correlation:.3f}"
                xref="paper"
                yref="paper"
                x=0.02
                y=0.98
                showarrow=False
                font=dict(size=12)
                bgcolor="white"
                bordercolor="gray"
                borderwidth=1
            )

        fig.update_layout(
            title="Cost vs Renewable Fraction Trade-off"
            xaxis_title="Total Cost ($)"
            yaxis_title="Renewable Fraction"
            yaxis_tickformat=".0%"
            height=500
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
            ("grid_self_sufficiency", "Grid Self-Sufficiency", 0, 1, 0.7)
            ("renewable_fraction", "Renewable Fraction", 0, 1, 0.5)
            ("battery_efficiency", "Battery Efficiency", 0, 1, 0.85)
            ("load_factor", "Load Factor", 0, 1, 0.6)
        ]

        # Filter available KPIs
        available_gauges = [(k, n, mi, ma, t) for k, n, mi, ma, t in gauge_kpis if k in kpi_data]

        if not available_gauges:
            return {}

        # Create subplots
        cols = min(len(available_gauges), 2)
        rows = (len(available_gauges) + 1) // 2

        fig = make_subplots(
            rows=rows
            cols=cols
            subplot_titles=[g[1] for g in available_gauges]
            specs=[[{"type": "indicator"} for _ in range(cols)] for _ in range(rows)]
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
                    mode="gauge+number"
                    value=value
                    gauge={
                        "axis": {"range": [min_val, max_val]}
                        "bar": {"color": bar_color}
                        "threshold": {,
                            "line": {"color": "black", "width": 2}
                            "thickness": 0.75,
                            "value": threshold
                        }
                    }
                    number={"valueformat": ".1%" if max_val == 1 else ".2f"}
                )
                row=row
                col=col
            )

        fig.update_layout(
            title="Technical Performance Indicators"
            height=300 * rows
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

        status = solver_metrics.get("status", "unknown")
        solve_time = solver_metrics.get("solve_time", 0)
        objective_value = solver_metrics.get("objective_value", 0)

        # Create status indicator
        status_color = {
            "optimal": "green",
            "feasible": "yellow",
            "infeasible": "red",
            "unknown": "gray"
        }.get(status, "gray")

        fig.add_trace(
            go.Indicator(
                mode="number+delta+gauge"
                value=objective_value
                title={"text": f"Optimization Status: {status.upper()}"}
                gauge={"axis": {"visible": False}, "bar": {"color": status_color}}
                domain={"x": [0.25, 0.75], "y": [0.3, 0.7]}
            )
        )

        # Add solve time annotation
        fig.add_annotation(
            text=f"Solve Time: {solve_time:.2f}s"
            xref="paper"
            yref="paper"
            x=0.5
            y=0.15
            showarrow=False
            font=dict(size=14)
        )

        fig.update_layout(title="Optimization Results", height=400, **self.default_layout)

        return fig.to_dict()

    def create_ga_pareto_front_plot(self, ga_result: Dict[str, Any]) -> Dict:
        """Create Pareto front visualization for multi-objective GA results.

        Args:
            ga_result: Genetic algorithm optimization result

        Returns:
            Plotly figure as dictionary
        """
        if not ga_result.get("pareto_front") or not ga_result.get("pareto_objectives"):
            return {}

        pareto_objectives = ga_result["pareto_objectives"]
        if not pareto_objectives or len(pareto_objectives[0]) < 2:
            return {}

        # Extract objectives (assuming 2D for now)
        obj1 = [obj[0] for obj in pareto_objectives]
        obj2 = [obj[1] for obj in pareto_objectives]

        fig = go.Figure()

        # Add Pareto front points
        fig.add_trace(
            go.Scatter(
                x=obj1
                y=obj2
                mode="markers+lines"
                name="Pareto Front"
                marker=dict(
                    size=10
                    color=np.arange(len(obj1))
                    colorscale="Viridis"
                    showscale=True
                    colorbar=dict(title="Solution Index")
                )
                line=dict(color="rgba(0,0,0,0.3)", width=1)
                text=[
                    f"Solution {i}<br>Obj1: {o1:.4f}<br>Obj2: {o2:.4f}" for i, (o1, o2) in enumerate(zip(obj1, obj2))
                ]
                hovertemplate="%{text}<extra></extra>"
            )
        )

        # Add best compromise solution if available
        if ga_result.get("best_solution"):
            best_obj = ga_result.get("best_objectives", [])
            if len(best_obj) >= 2:
                fig.add_trace(
                    go.Scatter(
                        x=[best_obj[0]]
                        y=[best_obj[1]]
                        mode="markers"
                        name="Best Compromise"
                        marker=dict(size=15, color="red", symbol="star")
                        text=f"Best Compromise<br>Obj1: {best_obj[0]:.4f}<br>Obj2: {best_obj[1]:.4f}"
                        hovertemplate="%{text}<extra></extra>"
                    )
                )

        fig.update_layout(
            title="Multi-Objective Optimization: Pareto Front"
            xaxis_title="Objective 1 (minimize)"
            yaxis_title="Objective 2 (minimize)"
            height=500
            **self.default_layout
        )

        return fig.to_dict()

    def create_ga_convergence_plot(self, ga_result: Dict[str, Any]) -> Dict:
        """Create convergence visualization for genetic algorithm.

        Args:
            ga_result: Genetic algorithm optimization result

        Returns:
            Plotly figure as dictionary
        """
        convergence_history = ga_result.get("convergence_history", [])
        if not convergence_history:
            return {}

        generations = list(range(len(convergence_history)))

        fig = go.Figure()

        # Add convergence line
        fig.add_trace(
            go.Scatter(
                x=generations
                y=convergence_history
                mode="lines+markers"
                name="Best Fitness"
                line=dict(color="blue", width=2)
                marker=dict(size=6)
            )
        )

        # Add final value annotation
        final_fitness = convergence_history[-1]
        fig.add_annotation(
            x=generations[-1]
            y=final_fitness
            text=f"Final: {final_fitness:.4f}"
            showarrow=True
            arrowhead=2
            bgcolor="white"
            bordercolor="blue"
            borderwidth=1
        )

        fig.update_layout(
            title="Genetic Algorithm Convergence"
            xaxis_title="Generation"
            yaxis_title="Best Fitness"
            height=400
            **self.default_layout
        )

        return fig.to_dict()

    def create_parameter_space_heatmap(self, mc_result: Dict[str, Any], param_names: List[str] = None) -> Dict:
        """Create parameter space exploration heatmap.

        Args:
            mc_result: Monte Carlo analysis result
            param_names: Names of parameters for labeling

        Returns:
            Plotly figure as dictionary
        """
        uncertainty_analysis = mc_result.get("uncertainty_analysis", {})
        sensitivity_data = uncertainty_analysis.get("sensitivity", {})

        if not sensitivity_data:
            return {}

        # Extract sensitivity indices for the first objective
        first_obj = list(sensitivity_data.keys())[0]
        param_sensitivities = sensitivity_data[first_obj]

        if not param_sensitivities:
            return {}

        # Prepare data for heatmap
        params = list(param_sensitivities.keys())
        sensitivities = [param_sensitivities[p].get("sensitivity_index", 0) for p in params]

        # Use provided names or default parameter names
        if param_names and len(param_names) >= len(params):
            display_names = param_names[: len(params)]
        else:
            display_names = [p.replace("param_", "Parameter ") for p in params]

        # Sort by sensitivity
        sorted_data = sorted(zip(display_names, sensitivities), key=lambda x: abs(x[1]), reverse=True)
        sorted_names, sorted_sens = zip(*sorted_data)

        fig = go.Figure()

        # Create horizontal bar chart
        fig.add_trace(
            go.Bar(
                y=sorted_names
                x=sorted_sens
                orientation="h"
                marker=dict(
                    color=sorted_sens
                    colorscale="RdBu"
                    showscale=True
                    colorbar=dict(title="Sensitivity Index")
                )
                text=[f"{s:.3f}" for s in sorted_sens]
                textposition="outside"
            )
        )

        fig.update_layout(
            title="Parameter Sensitivity Analysis"
            xaxis_title="Sensitivity Index"
            yaxis_title="Parameters"
            height=max(400, len(params) * 30)
            **self.default_layout
        )

        return fig.to_dict()

    def create_uncertainty_distribution_plot(self, mc_result: Dict[str, Any]) -> Dict:
        """Create uncertainty distribution plots for Monte Carlo results.

        Args:
            mc_result: Monte Carlo analysis result

        Returns:
            Plotly figure as dictionary
        """
        uncertainty_analysis = mc_result.get("uncertainty_analysis", {})
        statistics = uncertainty_analysis.get("statistics", {})

        if not statistics:
            return {}

        # Create subplots for each objective
        objectives = list(statistics.keys())
        n_objectives = len(objectives)

        if n_objectives == 0:
            return {}

        # Create subplot configuration
        if n_objectives == 1:
            fig = go.Figure()
            single_plot = True
        else:
            cols = min(n_objectives, 2)
            rows = (n_objectives + 1) // 2
            fig = make_subplots(rows=rows, cols=cols, subplot_titles=objectives, vertical_spacing=0.1)
            single_plot = False

        for idx, (obj_name, obj_stats) in enumerate(statistics.items()):
            mean = obj_stats.get("mean", 0)
            std = obj_stats.get("std", 1)
            min_val = obj_stats.get("min", mean - 3 * std)
            max_val = obj_stats.get("max", mean + 3 * std)

            # Generate normal distribution for comparison
            x_range = np.linspace(min_val, max_val, 100)
            normal_dist = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_range - mean) / std) ** 2)

            if single_plot:
                # Single histogram
                fig.add_trace(
                    go.Histogram(
                        x=np.random.normal(mean, std, 1000),  # Simulated data for visualization
                        nbinsx=30
                        name=f"{obj_name} Distribution"
                        opacity=0.7
                        histnorm="probability density"
                    )
                )

                # Add normal distribution overlay
                fig.add_trace(
                    go.Scatter(
                        x=x_range
                        y=normal_dist
                        mode="lines"
                        name="Normal Fit"
                        line=dict(color="red", width=2)
                    )
                )

                # Add statistics
                fig.add_vline(
                    x=mean
                    line_dash="dash"
                    line_color="green"
                    annotation_text=f"Mean: {mean:.3f}"
                )
                fig.add_vline(
                    x=mean + std
                    line_dash="dot"
                    line_color="orange"
                    annotation_text=f"+1σ: {mean+std:.3f}"
                )
                fig.add_vline(
                    x=mean - std
                    line_dash="dot"
                    line_color="orange"
                    annotation_text=f"-1σ: {mean-std:.3f}"
                )
            else:
                # Multiple subplots
                row = idx // cols + 1
                col = idx % cols + 1

                fig.add_trace(
                    go.Histogram(
                        x=np.random.normal(mean, std, 1000)
                        nbinsx=20
                        name=obj_name
                        opacity=0.7
                        histnorm="probability density"
                    )
                    row=row
                    col=col
                )

                fig.add_trace(
                    go.Scatter(
                        x=x_range
                        y=normal_dist
                        mode="lines"
                        name=f"{obj_name} Normal Fit"
                        line=dict(color="red", width=2)
                        showlegend=False
                    )
                    row=row
                    col=col
                )

        title = "Output Uncertainty Distributions" if n_objectives > 1 else f"{objectives[0]} Uncertainty Distribution"

        fig.update_layout(
            title=title
            height=400 if single_plot else 300 * rows
            **self.default_layout
        )

        if single_plot:
            fig.update_xaxis(title=objectives[0])
            fig.update_yaxis(title="Probability Density")

        return fig.to_dict()

    def create_risk_analysis_plot(self, mc_result: Dict[str, Any]) -> Dict:
        """Create risk analysis visualization with VaR and CVaR.

        Args:
            mc_result: Monte Carlo analysis result

        Returns:
            Plotly figure as dictionary
        """
        uncertainty_analysis = mc_result.get("uncertainty_analysis", {})
        risk_metrics = uncertainty_analysis.get("risk", {})

        if not risk_metrics:
            return {}

        # Take the first objective for risk analysis
        first_obj = list(risk_metrics.keys())[0]
        risk_data = risk_metrics[first_obj]

        # Create risk metrics chart
        fig = go.Figure()

        # Risk metrics
        var_95 = risk_data.get("var_95", 0)
        cvar_95 = risk_data.get("cvar_95", 0)
        mean_val = mc_result.get("uncertainty_analysis", {}).get("statistics", {}).get(first_obj, {}).get("mean", 0)

        # Create risk indicator
        fig.add_trace(
            go.Indicator(
                mode="number+gauge"
                value=var_95
                title={"text": "Value at Risk (95%)"}
                gauge={
                    "axis": {"range": [None, max(var_95, cvar_95) * 1.2]}
                    "bar": {"color": "darkred"}
                    "steps": [,
                        {"range": [0, mean_val], "color": "lightgray"}
                        {"range": [mean_val, var_95], "color": "yellow"}
                        {"range": [var_95, max(var_95, cvar_95) * 1.2], "color": "red"}
                    ]
                    "threshold": {,
                        "line": {"color": "red", "width": 4}
                        "thickness": 0.75,
                        "value": var_95
                    }
                }
                domain={"x": [0, 0.5], "y": [0, 1]}
            )
        )

        fig.add_trace(
            go.Indicator(
                mode="number+gauge"
                value=cvar_95
                title={"text": "Conditional VaR (95%)"}
                gauge={
                    "axis": {"range": [None, max(var_95, cvar_95) * 1.2]}
                    "bar": {"color": "darkred"}
                    "steps": [,
                        {"range": [0, mean_val], "color": "lightgray"}
                        {"range": [mean_val, cvar_95], "color": "orange"}
                        {
                            "range": [cvar_95, max(var_95, cvar_95) * 1.2],
                            "color": "red"
                        }
                    ]
                    "threshold": {,
                        "line": {"color": "red", "width": 4}
                        "thickness": 0.75,
                        "value": cvar_95
                    }
                }
                domain={"x": [0.5, 1], "y": [0, 1]}
            )
        )

        fig.update_layout(title=f"Risk Analysis: {first_obj}", height=400, **self.default_layout)

        return fig.to_dict()

    def create_sensitivity_tornado_plot(self, mc_result: Dict[str, Any]) -> Dict:
        """
        Create a tornado plot for sensitivity analysis showing parameter importance.

        Args:
            mc_result: Monte Carlo result with sensitivity analysis

        Returns:
            Plotly figure data for tornado plot
        """
        # Extract sensitivity data
        sensitivity_data = mc_result.get("sensitivity_analysis") or mc_result.get("sensitivity", {})

        if not sensitivity_data:
            return {}

        # Collect sensitivity indices for each parameter
        parameters = []
        sensitivities = []
        colors = []

        for param, data in sensitivity_data.items():
            if isinstance(data, dict):
                # Extract first-order sensitivity index
                si = data.get("first_order") or data.get("sensitivity_index", 0)
                parameters.append(param.replace("_", " ").title())
                sensitivities.append(abs(si))  # Use absolute value for magnitude
                # Color based on positive/negative correlation
                correlation = data.get("correlation", 0)
                colors.append("#d32f2f" if correlation < 0 else "#388e3c")
            elif isinstance(data, (int, float)):
                parameters.append(param.replace("_", " ").title())
                sensitivities.append(abs(data))
                colors.append("#1976d2")  # Default blue

        # Sort by sensitivity magnitude
        sorted_indices = sorted(range(len(sensitivities)), key=lambda i: sensitivities[i], reverse=True)
        parameters = [parameters[i] for i in sorted_indices]
        sensitivities = [sensitivities[i] for i in sorted_indices]
        colors = [colors[i] for i in sorted_indices]

        # Create tornado plot
        fig = go.Figure()

        # Add bars
        fig.add_trace(
            go.Bar(
                y=parameters
                x=sensitivities
                orientation="h"
                marker=dict(color=colors, line=dict(width=1, color="rgba(0,0,0,0.3)"))
                text=[f"{s:.3f}" for s in sensitivities]
                textposition="outside"
                hovertemplate="<b>%{y}</b><br>" + "Sensitivity: %{x:.3f}<br>" + "<extra></extra>"
            )
        )

        # Update layout
        fig.update_layout(
            title=dict(
                text="Sensitivity Analysis - Parameter Importance"
                font=dict(size=20, color="#333")
            )
            xaxis=dict(
                title="Sensitivity Index"
                titlefont=dict(size=14)
                showgrid=True
                gridwidth=1
                gridcolor="lightgray"
                range=[0, max(sensitivities) * 1.1] if sensitivities else [0, 1]
            )
            yaxis=dict(title="Parameters", titlefont=dict(size=14), showgrid=False)
            height=max(400, len(parameters) * 40),  # Dynamic height based on parameters
            margin=dict(l=150, r=50, t=50, b=50)
            paper_bgcolor="white"
            plot_bgcolor="rgba(0,0,0,0)"
            font=dict(family="Segoe UI", size=12)
        )

        # Add reference line at 0.5 if applicable
        if max(sensitivities) > 0.5:
            fig.add_shape(
                type="line"
                x0=0.5
                y0=-0.5
                x1=0.5
                y1=len(parameters) - 0.5
                line=dict(color="red", width=2, dash="dash")
            )
            fig.add_annotation(
                x=0.5
                y=len(parameters) - 1
                text="High Sensitivity Threshold"
                showarrow=False
                font=dict(size=10, color="red")
                textangle=90
                xanchor="right"
                yanchor="top"
            )

        return fig.to_dict()

    def create_scenario_comparison_plot(self, mc_result: Dict[str, Any]) -> Dict:
        """Create scenario comparison visualization.

        Args:
            mc_result: Monte Carlo analysis result

        Returns:
            Plotly figure as dictionary
        """
        uncertainty_analysis = mc_result.get("uncertainty_analysis", {})
        scenarios = uncertainty_analysis.get("scenarios", {})

        if not scenarios:
            return {}

        # Take first objective for scenario analysis
        first_obj = list(scenarios.keys())[0]
        scenario_data = scenarios[first_obj]

        scenario_names = list(scenario_data.keys())
        scenario_means = [scenario_data[s].get("mean_objective", 0) for s in scenario_names]

        fig = go.Figure()

        # Create bar chart for scenarios
        fig.add_trace(
            go.Bar(
                x=scenario_names
                y=scenario_means
                marker=dict(
                    color=["green", "yellow", "red"][: len(scenario_names)]
                    line=dict(color="black", width=1)
                )
                text=[f"{m:.3f}" for m in scenario_means]
                textposition="auto"
            )
        )

        fig.update_layout(
            title=f"Scenario Analysis: {first_obj}"
            xaxis_title="Scenario"
            yaxis_title=first_obj
            height=400
            **self.default_layout
        )

        return fig.to_dict()

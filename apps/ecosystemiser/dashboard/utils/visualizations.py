"""
Visualization utilities for the EcoSystemiser dashboard
"""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def create_comparison_plot(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    variables: List[str],
    labels: tuple[str, str] = ("Dataset 1", "Dataset 2"),
) -> go.Figure:
    """
    Create a comparison plot between two datasets.

    Args:
        df1: First dataset
        df2: Second dataset
        variables: Variables to compare
        labels: Labels for the two datasets

    Returns:
        Plotly figure with comparison plots
    """
    fig = go.Figure()

    # Add traces for each variable from both datasets
    for var in variables:
        if var in df1.columns:
            fig.add_trace(
                go.Scatter(
                    x=df1.index,
                    y=df1[var],
                    mode="lines",
                    name=f"{labels[0]} - {var}",
                    legendgroup=labels[0],
                )
            )

        if var in df2.columns:
            fig.add_trace(
                go.Scatter(
                    x=df2.index,
                    y=df2[var],
                    mode="lines",
                    name=f"{labels[1]} - {var}",
                    legendgroup=labels[1],
                    line=dict(dash="dash"),
                )
            )

    fig.update_layout(
        title="Dataset Comparison",
        xaxis_title="Time",
        yaxis_title="Value",
        hovermode="x unified",
        height=600,
        showlegend=True,
    )

    return fig


def create_heatmap(df: pd.DataFrame, variable: str, time_resolution: str = "1D") -> go.Figure:
    """
    Create a heatmap visualization for a single variable.

    Args:
        df: Input dataframe with time index
        variable: Variable name to plot
        time_resolution: Time aggregation resolution

    Returns:
        Plotly heatmap figure
    """
    # Resample data if needed
    if time_resolution != df.index.freq:
        df_resampled = df[[variable]].resample(time_resolution).mean()
    else:
        df_resampled = df[[variable]]

    # Extract date components
    df_resampled["hour"] = df_resampled.index.hour
    df_resampled["day"] = df_resampled.index.day_name()
    df_resampled["month"] = df_resampled.index.month_name()
    df_resampled["day_of_month"] = df_resampled.index.day

    # Create pivot table for heatmap
    if len(df_resampled) <= 7 * 24:  # Less than a week of hourly data
        pivot = df_resampled.pivot_table(values=variable, index="hour", columns="day", aggfunc="mean")
        x_label = "Day of Week"
        y_label = "Hour of Day"
    else:  # Longer periods
        pivot = df_resampled.pivot_table(values=variable, index="day_of_month", columns="month", aggfunc="mean")
        x_label = "Month"
        y_label = "Day of Month"

    # Create heatmap
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale="Viridis",
            colorbar=dict(title=variable),
        )
    )

    fig.update_layout(
        title=f"{variable} Heatmap",
        xaxis_title=x_label,
        yaxis_title=y_label,
        height=500,
    )

    return fig


def create_correlation_matrix(df: pd.DataFrame) -> go.Figure:
    """
    Create a correlation matrix heatmap for all numeric variables.

    Args:
        df: Input dataframe

    Returns:
        Plotly correlation matrix figure
    """
    # Calculate correlation matrix
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    corr_matrix = df[numeric_cols].corr()

    # Create heatmap
    fig = go.Figure(
        data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.index,
            colorscale="RdBu",
            zmid=0,
            text=corr_matrix.round(2).values,
            texttemplate="%{text}",
            textfont={"size": 10},
            colorbar=dict(title="Correlation"),
        )
    )

    fig.update_layout(
        title="Variable Correlation Matrix",
        height=600,
        width=800,
        xaxis={"side": "bottom"},
        yaxis={"side": "left"},
    )

    return fig


def format_statistics_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Format a statistics table with proper units and formatting.

    Args:
        df: Raw dataframe with climate data

    Returns:
        Formatted statistics dataframe
    """
    # Get basic statistics
    stats = df.describe().T

    # Add additional statistics
    stats["missing"] = df.isnull().sum()
    stats["missing_pct"] = stats["missing"] / len(df) * 100
    stats["zeros"] = (df == 0).sum()
    stats["zeros_pct"] = stats["zeros"] / len(df) * 100

    # Add data quality indicators
    stats["quality"] = 100 - stats["missing_pct"]

    # Round values appropriately
    for col in ["mean", "std", "min", "25%", "50%", "75%", "max"]:
        if col in stats.columns:
            stats[col] = stats[col].round(2)

    stats["missing_pct"] = stats["missing_pct"].round(1)
    stats["zeros_pct"] = stats["zeros_pct"].round(1)
    stats["quality"] = stats["quality"].round(0)

    return stats


def create_wind_rose(df: pd.DataFrame) -> Optional[go.Figure]:
    """
    Create a wind rose plot if wind data is available.

    Args:
        df: Dataframe with wind_speed and wind_dir columns

    Returns:
        Plotly wind rose figure or None if data unavailable
    """
    if "wind_speed" not in df.columns or "wind_dir" not in df.columns:
        return None

    # Prepare wind data
    wind_data = df[["wind_speed", "wind_dir"]].dropna()

    if wind_data.empty:
        return None

    # Create wind speed bins
    speed_bins = [0, 2, 4, 6, 8, 10, float("inf")]
    speed_labels = ["0-2", "2-4", "4-6", "6-8", "8-10", ">10"]
    wind_data["speed_bin"] = pd.cut(wind_data["wind_speed"], bins=speed_bins, labels=speed_labels)

    # Create direction bins (16 compass points)
    dir_bins = np.arange(0, 361, 22.5)
    dir_labels = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    wind_data["dir_bin"] = pd.cut(wind_data["wind_dir"], bins=dir_bins, labels=dir_labels)

    # Calculate frequencies
    wind_rose = wind_data.groupby(["dir_bin", "speed_bin"]).size().unstack(fill_value=0)

    # Create polar bar chart
    fig = go.Figure()

    for speed_label in speed_labels:
        if speed_label in wind_rose.columns:
            fig.add_trace(
                go.Barpolar(
                    r=wind_rose[speed_label],
                    theta=dir_labels,
                    name=f"{speed_label} m/s",
                    marker_color=px.colors.sequential.Viridis[speed_labels.index(speed_label)],
                )
            )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, wind_rose.values.max()])),
        showlegend=True,
        title="Wind Rose",
        height=500,
    )

    return fig


def create_daily_profile(df: pd.DataFrame, variables: List[str], aggregation: str = "mean") -> go.Figure:
    """
    Create average daily profiles for selected variables.

    Args:
        df: Input dataframe with hourly or sub-hourly data
        variables: List of variables to plot
        aggregation: Aggregation method (mean, median, etc.)

    Returns:
        Plotly figure with daily profiles
    """
    # Extract hour of day
    df_hourly = df.copy()
    df_hourly["hour"] = df_hourly.index.hour

    # Group by hour and aggregate
    if aggregation == "mean":
        daily_profile = df_hourly.groupby("hour")[variables].mean()
    elif aggregation == "median":
        daily_profile = df_hourly.groupby("hour")[variables].median()
    else:
        daily_profile = df_hourly.groupby("hour")[variables].mean()

    # Create plot
    fig = go.Figure()

    for var in variables:
        if var in daily_profile.columns:
            fig.add_trace(
                go.Scatter(
                    x=daily_profile.index,
                    y=daily_profile[var],
                    mode="lines+markers",
                    name=var,
                )
            )

    fig.update_layout(
        title=f"Average Daily Profile ({aggregation})",
        xaxis_title="Hour of Day",
        yaxis_title="Value",
        xaxis=dict(tickmode="linear", dtick=3, range=[0, 23]),
        height=400,
        hovermode="x unified",
    )

    return fig

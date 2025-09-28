"""
EcoSystemiser Climate Dashboard (Isolated Version)
Interactive web interface that reads from output artifacts
No direct imports from ecosystemiser package - maintains architectural isolation
"""

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="EcoSystemiser Climate Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
<style>
    .stAlert {
        margin-top: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "dataset" not in st.session_state:
    st.session_state.dataset = None
if "loaded_file" not in st.session_state:
    st.session_state.loaded_file = None


def get_available_sources() -> List[str]:
    """Get list of available climate data sources from configuration."""
    # In isolated mode, we hardcode the known sources
    return [
        "nasa_power",
        "meteostat",
        "era5",
        "pvgis",
        "file_epw",
    ]


def get_canonical_variables() -> Dict[str, Dict[str, Any]]:
    """Get canonical variable definitions."""
    # In isolated mode, we define the essential variables
    return {
        "temp_air": {"name": "Air Temperature", "unit": "°C", "category": "Temperature"},
        "rel_humidity": {"name": "Relative Humidity", "unit": "%", "category": "Humidity"},
        "wind_speed": {"name": "Wind Speed", "unit": "m/s", "category": "Wind"},
        "wind_dir": {"name": "Wind Direction", "unit": "degrees", "category": "Wind"},
        "ghi": {"name": "Global Horizontal Irradiance", "unit": "W/m²", "category": "Solar"},
        "dni": {"name": "Direct Normal Irradiance", "unit": "W/m²", "category": "Solar"},
        "dhi": {"name": "Diffuse Horizontal Irradiance", "unit": "W/m²", "category": "Solar"},
        "precip": {"name": "Precipitation", "unit": "mm", "category": "Precipitation"},
        "pressure": {"name": "Atmospheric Pressure", "unit": "hPa", "category": "Pressure"},
        "cloud_cover": {"name": "Cloud Cover", "unit": "%", "category": "Clouds"},
    }


def load_climate_data_from_file(file_path: Path) -> Optional[pd.DataFrame]:
    """Load climate data from a JSON or CSV file."""
    try:
        if file_path.suffix == ".json":
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Handle different JSON structures
            if isinstance(data, dict):
                if "data" in data:
                    # Nested structure with metadata
                    df = pd.DataFrame(data["data"])
                elif "time" in data:
                    # Time-indexed data
                    df = pd.DataFrame(data)
                else:
                    # Try to create DataFrame from dict
                    df = pd.DataFrame([data])
            else:
                df = pd.DataFrame(data)

        elif file_path.suffix == ".csv":
            df = pd.read_csv(file_path)

        else:
            st.error(f"Unsupported file format: {file_path.suffix}")
            return None

        # Try to parse time column if exists
        time_columns = ["time", "timestamp", "datetime", "date"]
        for col in time_columns:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col])
                    df = df.set_index(col)
                except:
                    pass
                break

        return df

    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return None


def find_output_files(base_dir: Path = None) -> List[Path]:
    """Find available climate data output files."""
    if base_dir is None:
        # Default to results directory relative to dashboard
        base_dir = Path(__file__).parent.parent / "results"

    files = []

    if base_dir.exists():
        # Look for climate data files
        patterns = ["*climate*.json", "*climate*.csv", "*weather*.json", "*weather*.csv"]
        for pattern in patterns:
            files.extend(base_dir.glob(pattern))
            files.extend(base_dir.glob(f"**/{pattern}"))  # Recursive search

    return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:20]  # Most recent 20


def plot_time_series(df: pd.DataFrame, variables: List[str], title: str = "Time Series"):
    """Create time series plot for selected variables."""
    fig = go.Figure()

    for var in variables:
        if var in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index if isinstance(df.index, pd.DatetimeIndex) else df.index,
                y=df[var],
                mode='lines',
                name=var,
            ))

    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Value",
        hovermode='x unified',
        height=400
    )

    return fig


def plot_correlation_matrix(df: pd.DataFrame, variables: List[str]):
    """Create correlation matrix heatmap."""
    numeric_vars = [v for v in variables if v in df.columns and pd.api.types.is_numeric_dtype(df[v])]

    if len(numeric_vars) > 1:
        corr_matrix = df[numeric_vars].corr()

        fig = px.imshow(
            corr_matrix,
            labels=dict(x="Variable", y="Variable", color="Correlation"),
            x=numeric_vars,
            y=numeric_vars,
            color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1,
            title="Variable Correlation Matrix"
        )

        return fig
    return None


def plot_distribution(df: pd.DataFrame, variable: str):
    """Create distribution plot for a variable."""
    if variable in df.columns:
        fig = px.histogram(
            df,
            x=variable,
            nbins=30,
            title=f"Distribution of {variable}",
            labels={variable: variable, "count": "Frequency"}
        )
        return fig
    return None


# Main app
def main():
    st.title("🌍 EcoSystemiser Climate Dashboard")
    st.markdown("### Isolated Data Viewer - Reads from Output Files")

    # Sidebar for configuration
    with st.sidebar:
        st.header("Data Source")

        # File selection
        st.subheader("Load Data File")

        # Option 1: Select from existing files
        output_files = find_output_files()

        if output_files:
            selected_file = st.selectbox(
                "Select from existing outputs",
                options=["None"] + output_files,
                format_func=lambda x: "None" if x == "None" else f"{x.name} ({x.parent.name})"
            )

            if selected_file != "None":
                if st.button("Load Selected File"):
                    df = load_climate_data_from_file(selected_file)
                    if df is not None:
                        st.session_state.dataset = df
                        st.session_state.loaded_file = selected_file
                        st.success(f"Loaded {selected_file.name}")

        # Option 2: Upload file
        st.subheader("Or Upload File")
        uploaded_file = st.file_uploader(
            "Choose a climate data file",
            type=["json", "csv"],
            help="Upload JSON or CSV file with climate data"
        )

        if uploaded_file is not None:
            # Save uploaded file temporarily
            temp_path = Path(f"/tmp/{uploaded_file.name}")
            temp_path.write_bytes(uploaded_file.read())

            df = load_climate_data_from_file(temp_path)
            if df is not None:
                st.session_state.dataset = df
                st.session_state.loaded_file = uploaded_file.name
                st.success(f"Loaded {uploaded_file.name}")

        # Variable selection
        if st.session_state.dataset is not None:
            st.subheader("Variable Selection")

            df = st.session_state.dataset
            available_vars = [col for col in df.columns if not col.startswith('_')]

            selected_vars = st.multiselect(
                "Select variables to visualize",
                options=available_vars,
                default=available_vars[:3] if len(available_vars) > 3 else available_vars
            )

    # Main content area
    if st.session_state.dataset is not None:
        df = st.session_state.dataset

        # Display file info
        if st.session_state.loaded_file:
            st.info(f"📁 Loaded file: {st.session_state.loaded_file}")

        # Data overview
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", len(df))
        with col2:
            st.metric("Variables", len(df.columns))
        with col3:
            if isinstance(df.index, pd.DatetimeIndex):
                st.metric("Start Date", df.index[0].strftime("%Y-%m-%d"))
        with col4:
            if isinstance(df.index, pd.DatetimeIndex):
                st.metric("End Date", df.index[-1].strftime("%Y-%m-%d"))

        # Tabs for different views
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["📈 Time Series", "📊 Statistics", "🔍 Data Explorer", "📉 Distributions", "🔗 Correlations"]
        )

        with tab1:
            if selected_vars:
                fig = plot_time_series(df, selected_vars)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Please select variables to visualize")

        with tab2:
            if selected_vars:
                st.subheader("Summary Statistics")
                stats_df = df[selected_vars].describe()
                st.dataframe(stats_df)

                # Additional metrics
                st.subheader("Data Quality Metrics")
                quality_data = []
                for var in selected_vars:
                    if var in df.columns:
                        quality_data.append({
                            "Variable": var,
                            "Missing Values": df[var].isna().sum(),
                            "Missing %": f"{df[var].isna().sum() / len(df) * 100:.1f}%",
                            "Unique Values": df[var].nunique(),
                            "Data Type": str(df[var].dtype)
                        })

                if quality_data:
                    quality_df = pd.DataFrame(quality_data)
                    st.dataframe(quality_df)
            else:
                st.warning("Please select variables to analyze")

        with tab3:
            st.subheader("Raw Data")

            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                n_rows = st.slider("Number of rows to display", 10, min(1000, len(df)), 100)
            with col2:
                if isinstance(df.index, pd.DatetimeIndex):
                    date_range = st.date_input(
                        "Date range",
                        value=(df.index[0].date(), df.index[-1].date()),
                        min_value=df.index[0].date(),
                        max_value=df.index[-1].date()
                    )

            # Display data
            display_df = df.head(n_rows)
            if selected_vars:
                display_df = display_df[selected_vars]

            st.dataframe(display_df, use_container_width=True)

            # Download button
            csv = display_df.to_csv()
            st.download_button(
                label="Download displayed data as CSV",
                data=csv,
                file_name=f"climate_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

        with tab4:
            if selected_vars:
                st.subheader("Variable Distributions")

                # Create distribution plots
                cols = st.columns(2)
                for i, var in enumerate(selected_vars):
                    with cols[i % 2]:
                        fig = plot_distribution(df, var)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Please select variables to visualize distributions")

        with tab5:
            if selected_vars:
                st.subheader("Correlation Analysis")

                fig = plot_correlation_matrix(df, selected_vars)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Need at least 2 numeric variables for correlation analysis")
            else:
                st.warning("Please select variables for correlation analysis")

    else:
        # Welcome message when no data is loaded
        st.info("👈 Please load a climate data file from the sidebar to begin")

        st.markdown("""
        ### About This Dashboard

        This is the **isolated version** of the EcoSystemiser Climate Dashboard.
        It maintains architectural separation by:
        - ✅ **No imports** from the ecosystemiser package
        - ✅ **Reads only** from output JSON/CSV files
        - ✅ **Self-contained** with no dependencies on the main codebase

        ### How to Use

        1. **Load Data**: Use the sidebar to either:
           - Select from existing output files in the results directory
           - Upload your own JSON or CSV file

        2. **Explore**: Once loaded, use the tabs to:
           - View time series plots
           - Analyze statistics
           - Explore raw data
           - Examine distributions
           - Study correlations

        3. **Export**: Download filtered data as CSV for further analysis
        """)


if __name__ == "__main__":
    main()
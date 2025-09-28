"""
EcoSystemiser Climate Dashboard
Interactive web interface for the Climate Profile API
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import json
import sys
from pathlib import Path

# Add parent directory to path to import EcoSystemiser
import os
parent_dir = str(Path(__file__).parent.parent / "src")
if parent_dir not in sys.path:
# Also add parent for direct imports
parent_parent_dir = str(Path(__file__).parent.parent.parent)
if parent_parent_dir not in sys.path:
# Now try imports with better path
try:
    # Try relative import first
    from apps.EcoSystemiser.src.EcoSystemiser.profile_loader.climate import (
        get_profile_sync, 
        ClimateRequest,
        ClimateResponse
    )
    from apps.EcoSystemiser.src.EcoSystemiser.profile_loader.climate.data_models import CANONICAL_VARIABLES
    from apps.EcoSystemiser.src.EcoSystemiser.profile_loader.climate.adapters.factory import list_available_adapters
except ImportError:
    # Try direct import
    from EcoSystemiser.profile_loader.climate import (
        get_profile_sync, 
        ClimateRequest,
        ClimateResponse
    )
    from EcoSystemiser.profile_loader.climate.data_models import CANONICAL_VARIABLES
    from EcoSystemiser.profile_loader.climate.adapters.factory import list_available_adapters

# Page configuration
st.set_page_config(
    page_title="EcoSystemiser Climate Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
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
""", unsafe_allow_html=True)

# Initialize session state
if 'api_response' not in st.session_state:
    st.session_state.api_response = None
if 'dataset' not in st.session_state:
    st.session_state.dataset = None

# Title and description
st.title("🌍 EcoSystemiser Climate Dashboard")
st.markdown("**Interactive interface for exploring climate data from multiple sources**")

# Sidebar configuration
with st.sidebar:
    st.header("📍 Query Configuration")
    
    # Location input section
    st.subheader("Location")
    location_type = st.radio("Input type:", ["Coordinates", "City Name"], horizontal=True)
    
    if location_type == "Coordinates":
        col1, col2 = st.columns(2)
        with col1:
            latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=38.7, step=0.01)
        with col2:
            longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=-9.1, step=0.01)
        location = (latitude, longitude)
    else:
        location = st.text_input("City name", value="Lisbon, PT")
    
    # Common location presets
    preset = st.selectbox("Or select a preset:", 
                        ["Custom", "Lisbon, PT", "Berlin, DE", "New York, US", "Tokyo, JP", "Sydney, AU"],
                        key="location_preset_unique")
    if preset != "Custom":
        location = preset
    
    st.divider()
    
    # Time period selection
    st.subheader("Time Period")
    period_type = st.radio("Period type:", ["Year", "Date Range"], horizontal=True)
    
    if period_type == "Year":
        year = st.number_input("Year", min_value=1980, max_value=2024, value=2023, step=1)
        period = {"year": year}
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date", value=date(2023, 1, 1))
        with col2:
            end_date = st.date_input("End date", value=date(2023, 12, 31))
        period = {"start": start_date.strftime("%Y-%m-%d"), "end": end_date.strftime("%Y-%m-%d")}
    
    st.divider()
    
    # Data configuration
    st.subheader("Data Configuration")
    
    # Data source
    try:
        available_sources = list_available_adapters()
    except Exception as e:
        available_sources = ["nasa_power", "meteostat", "pvgis", "era5", "epw"]
    
    source = st.selectbox("Data Source", available_sources, index=0)
    
    # Mode
    mode = st.selectbox("Mode", ["observed", "tmy", "average", "synthetic"], index=0)
    
    # Resolution
    resolution = st.selectbox("Resolution", ["15min", "30min", "1H", "3H", "1D"], index=2)
    
    # Variables selection
    st.subheader("Variables")
    
    # Group variables by category
    temp_vars = [v for v in CANONICAL_VARIABLES.keys() if "temp" in v or "dewpoint" in v]
    solar_vars = [v for v in CANONICAL_VARIABLES.keys() if any(s in v for s in ["ghi", "dni", "dhi", "solar", "sunshine"])]
    wind_vars = [v for v in CANONICAL_VARIABLES.keys() if "wind" in v]
    humidity_vars = [v for v in CANONICAL_VARIABLES.keys() if "humidity" in v]
    precip_vars = [v for v in CANONICAL_VARIABLES.keys() if any(p in v for p in ["precip", "rain", "snow"])]
    other_vars = [v for v in CANONICAL_VARIABLES.keys() 
                 if v not in temp_vars + solar_vars + wind_vars + humidity_vars + precip_vars]
    
    # Default selection
    default_vars = ["temp_air", "ghi", "wind_speed", "rel_humidity"]
    available_defaults = [v for v in default_vars if v in CANONICAL_VARIABLES]
    
    selected_vars = st.multiselect(
        "Select variables:",
        options=list(CANONICAL_VARIABLES.keys()),
        default=available_defaults,
        help="Choose the climate variables to retrieve"
    )
    
    # Quick select buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🌡️ Temperature set"):
            selected_vars = temp_vars
    with col2:
        if st.button("☀️ Solar set"):
            selected_vars = solar_vars
    
    st.divider()
    
    # Submit button
    submit = st.button("🚀 Get Climate Profile", type="primary", use_container_width=True)

# Main panel
if submit:
    # Create request
    try:
        with st.spinner("🔄 Fetching climate data..."):
            # Build the request
            request = ClimateRequest(
                location=location,
                variables=selected_vars,
                source=source,
                period=period,
                mode=mode,
                resolution=resolution,
                timezone="UTC"
            )
            
            # Make API call
            dataset, response = get_profile_sync(request)
            
            # Store in session state
            st.session_state.api_response = response
            st.session_state.dataset = dataset
            
            st.success("✅ Data retrieved successfully!")
            
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.info("💡 Try adjusting your query parameters or selecting a different data source.")
        st.stop()

# Display results if available
if st.session_state.dataset is not None and st.session_state.api_response is not None:
    
    # Header with location info
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if isinstance(location, tuple):
            st.markdown(f"### 📍 Location: {location[0]:.2f}°, {location[1]:.2f}°")
        else:
            st.markdown(f"### 📍 Location: {location}")
    with col2:
        st.markdown(f"**Source:** {source}")
    with col3:
        st.markdown(f"**Mode:** {mode}")
    
    # Convert xarray dataset to pandas for easier manipulation
    df = st.session_state.dataset.to_dataframe()
    
    # Main metrics row
    st.markdown("### 📊 Summary Statistics")
    metrics_cols = st.columns(4)
    
    if "temp_air" in df.columns:
        with metrics_cols[0]:
            st.metric(
                "Mean Temperature",
                f"{df['temp_air'].mean():.1f}°C",
                f"σ = {df['temp_air'].std():.1f}°C"
            )
    
    if "ghi" in df.columns:
        with metrics_cols[1]:
            st.metric(
                "Avg Solar Radiation",
                f"{df['ghi'].mean():.0f} W/m²",
                f"Max: {df['ghi'].max():.0f} W/m²"
            )
    
    if "wind_speed" in df.columns:
        with metrics_cols[2]:
            st.metric(
                "Mean Wind Speed",
                f"{df['wind_speed'].mean():.1f} m/s",
                f"Max: {df['wind_speed'].max():.1f} m/s"
            )
    
    if "rel_humidity" in df.columns:
        with metrics_cols[3]:
            st.metric(
                "Mean Humidity",
                f"{df['rel_humidity'].mean():.0f}%",
                f"σ = {df['rel_humidity'].std():.0f}%"
            )
    
    # Time series plot
    st.markdown("### 📈 Time Series Visualization")
    
    # Variable selector for plot
    plot_vars = st.multiselect(
        "Select variables to plot:",
        options=[col for col in df.columns if col != 'time'],
        default=[col for col in df.columns if col != 'time'][:3]  # Default to first 3 variables
    )
    
    if plot_vars:
        # Create plotly figure with secondary y-axis if needed
        fig = go.Figure()
        
        # Determine which variables need secondary axis (different units)
        primary_vars = []
        secondary_vars = []
        
        for var in plot_vars:
            if var in CANONICAL_VARIABLES:
                unit = CANONICAL_VARIABLES[var].get('unit', '')
                if unit in ['W/m2', 'W/m²']:
                    secondary_vars.append(var)
                else:
                    primary_vars.append(var)
            else:
                primary_vars.append(var)
        
        # Add traces for primary axis
        for var in primary_vars:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[var],
                    mode='lines',
                    name=var,
                    yaxis='y'
                )
            )
        
        # Add traces for secondary axis
        for var in secondary_vars:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[var],
                    mode='lines',
                    name=var,
                    yaxis='y2'
                )
            )
        
        # Update layout with dual axes
        fig.update_layout(
            title="Climate Variables Over Time",
            xaxis_title="Time",
            yaxis=dict(title="Primary Variables"),
            yaxis2=dict(
                title="Solar Radiation (W/m²)",
                overlaying='y',
                side='right'
            ) if secondary_vars else None,
            hovermode='x unified',
            height=500,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Tabbed interface for detailed data
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Raw Data", "📋 Manifest", "📈 Statistics", "💾 Download"])
    
    with tab1:
        st.markdown("#### Raw Time Series Data")
        
        # Show first/last N rows selector
        col1, col2 = st.columns([1, 3])
        with col1:
            n_rows = st.number_input("Show rows:", min_value=10, max_value=len(df), value=100, step=10)
        
        # Display dataframe
        st.dataframe(
            df.head(n_rows).style.format({
                col: "{:.2f}" for col in df.columns if df[col].dtype in ['float64', 'float32']
            }),
            use_container_width=True
        )
        
        st.caption(f"Showing {min(n_rows, len(df))} of {len(df)} total rows")
    
    with tab2:
        st.markdown("#### API Response Manifest")
        
        # Display manifest as formatted JSON
        if hasattr(st.session_state.api_response, 'manifest'):
            st.json(st.session_state.api_response.manifest)
        
        # Display response metadata
        st.markdown("#### Response Metadata")
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"**Shape:** {st.session_state.api_response.shape}")
            st.info(f"**Start:** {st.session_state.api_response.start_time}")
        
        with col2:
            st.info(f"**Variables:** {len(st.session_state.api_response.variables)}")
            st.info(f"**End:** {st.session_state.api_response.end_time}")
    
    with tab3:
        st.markdown("#### Variable Statistics")
        
        # Create statistics summary
        stats_df = df.describe().T
        stats_df['missing'] = df.isnull().sum()
        stats_df['missing_pct'] = (stats_df['missing'] / len(df) * 100).round(2)
        
        # Display statistics table
        st.dataframe(
            stats_df.style.format({
                'count': '{:.0f}',
                'mean': '{:.2f}',
                'std': '{:.2f}',
                'min': '{:.2f}',
                '25%': '{:.2f}',
                '50%': '{:.2f}',
                '75%': '{:.2f}',
                'max': '{:.2f}',
                'missing': '{:.0f}',
                'missing_pct': '{:.1f}%'
            }),
            use_container_width=True
        )
        
        # Data quality summary
        if hasattr(st.session_state.api_response, 'stats') and st.session_state.api_response.stats:
            st.markdown("#### Data Quality")
            quality_data = st.session_state.api_response.stats
            if isinstance(quality_data, dict):
                if 'quality_score' in quality_data:
                    st.progress(quality_data['quality_score'] / 100)
                    st.caption(f"Quality Score: {quality_data['quality_score']}/100")
    
    with tab4:
        st.markdown("#### Download Data")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # CSV download
            csv = df.to_csv()
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"climate_data_{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # JSON download (manifest)
            if hasattr(st.session_state.api_response, 'manifest'):
                try:
                    # Convert manifest to serializable format
                    manifest_data = st.session_state.api_response.manifest
                    if isinstance(manifest_data, dict):
                        # Convert any non-serializable objects to strings
                        import copy
                        serializable_manifest = copy.deepcopy(manifest_data)
                        
                        def make_serializable(obj):
                            if isinstance(obj, dict):
                                return {k: make_serializable(v) for k, v in obj.items()}
                            elif isinstance(obj, list):
                                return [make_serializable(item) for item in obj]
                            elif hasattr(obj, '__dict__'):
                                return str(obj)
                            else:
                                return obj
                        
                        serializable_manifest = make_serializable(serializable_manifest)
                        json_str = json.dumps(serializable_manifest, indent=2, default=str)
                    else:
                        json_str = json.dumps({"manifest": str(manifest_data)}, indent=2)
                    
                    st.download_button(
                        label="📥 Download Manifest (JSON)",
                        data=json_str,
                        file_name=f"climate_manifest_{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
                except Exception as e:
                    st.warning(f"Manifest download unavailable: {str(e)}")
        
        with col3:
            # Parquet download
            parquet_buffer = df.to_parquet()
            st.download_button(
                label="📥 Download Parquet",
                data=parquet_buffer,
                file_name=f"climate_data_{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet",
                mime="application/octet-stream",
                use_container_width=True
            )
        
        st.markdown("---")
        st.caption("💡 **Tip:** Parquet format is recommended for large datasets and maintains data types.")

# Footer
st.markdown("---")
st.caption("🌍 EcoSystemiser Climate Dashboard | Built with Streamlit | [Documentation](https://github.com/yourusername/ecosystemiser)")
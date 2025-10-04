"""Results Explorer - Interactive dashboard for simulation archive exploration.

This dashboard provides a powerful UI for browsing, filtering, and analyzing
1000s of simulation runs stored in the database.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import using importlib to avoid import chain issues
import importlib.util

import streamlit as st

spec = importlib.util.spec_from_file_location(
    "database_metadata_service",
    Path(__file__).parent.parent / "src" / "ecosystemiser" / "services" / "database_metadata_service.py",
)
db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_module)
DatabaseMetadataService = db_module.DatabaseMetadataService

# Page configuration
st.set_page_config(
    page_title="EcoSystemiser - Results Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database connection
@st.cache_resource
def get_db_service():
    """Get cached database service instance."""
    db_path = Path(__file__).parent.parent / "data" / "simulation_index.sqlite"
    if not db_path.exists():
        st.warning(f"Database not found at {db_path}. Using in-memory database for demo.")
        return DatabaseMetadataService(":memory:")
    return DatabaseMetadataService(str(db_path))

# Main application
def main():
    """Main application entry point."""
    # Header
    st.title("🔍 Simulation Results Explorer")
    st.markdown("Explore and analyze your simulation archive")
    st.divider()

    # Get database service
    try:
        db_service = get_db_service()
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        return

    # Sidebar filters
    st.sidebar.header("Filters")

    # Get database stats for filter options
    try:
        stats = db_service.get_database_stats()
        total_runs = stats.get("total_runs", 0)
        total_studies = stats.get("total_studies", 0)

        st.sidebar.metric("Total Runs", total_runs)
        st.sidebar.metric("Total Studies", total_studies)
        st.sidebar.divider()

    except Exception as e:
        st.sidebar.error(f"Could not load stats: {e}")
        total_runs = 0

    # Filter inputs
    study_id_filter = st.sidebar.text_input("Study ID", placeholder="All studies")
    solver_type_filter = st.sidebar.selectbox(
        "Solver Type",
        options=["All", "hybrid", "milp", "rule_based", "rolling_horizon"],
        index=0,
    )

    cost_range = st.sidebar.slider(
        "Total Cost Range ($)",
        min_value=0,
        max_value=500000,
        value=(0, 500000),
        step=10000,
    )

    renewable_min = st.sidebar.slider(
        "Min Renewable Fraction",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.05,
    )

    limit = st.sidebar.number_input(
        "Max Results",
        min_value=10,
        max_value=1000,
        value=100,
        step=10,
    )

    # Query button
    if st.sidebar.button("Apply Filters", type="primary"):
        st.rerun()

    # Main content area
    if total_runs == 0:
        st.info("No simulation runs found in database. Run some simulations to see results here!")
        st.markdown("""
        ### Getting Started

        To populate the database with simulation results:

        1. Run a simulation with database logging enabled
        2. Results will automatically be indexed here
        3. Use filters to explore your results

        See `START_HERE.md` for more information.
        """)
        return

    # Query simulation runs
    try:
        # Build query parameters
        query_params = {
            "limit": limit,
            "order_by": "timestamp",
            "order_desc": True,
        }

        if study_id_filter:
            query_params["study_id"] = study_id_filter

        if solver_type_filter != "All":
            query_params["solver_type"] = solver_type_filter

        if cost_range[0] > 0:
            query_params["min_cost"] = float(cost_range[0])

        if cost_range[1] < 500000:
            query_params["max_cost"] = float(cost_range[1])

        if renewable_min > 0:
            query_params["min_renewable_fraction"] = renewable_min

        # Execute query
        runs = db_service.query_simulation_runs(**query_params)

        # Display results count
        st.subheader(f"Found {len(runs)} simulation runs")

        if len(runs) == 0:
            st.warning("No runs match your filter criteria. Try adjusting the filters.")
            return

        # Display results table
        import pandas as pd

        df = pd.DataFrame(runs)

        # Select and format columns
        display_columns = [
            "run_id", "study_id", "solver_type", "total_cost",
            "renewable_fraction", "simulation_status", "timestamp",
        ]

        # Only include columns that exist
        display_columns = [col for col in display_columns if col in df.columns]
        df_display = df[display_columns].copy()

        # Format numbers
        if "total_cost" in df_display.columns:
            df_display["total_cost"] = df_display["total_cost"].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A",
            )

        if "renewable_fraction" in df_display.columns:
            df_display["renewable_fraction"] = df_display["renewable_fraction"].apply(
                lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A",
            )

        # Display as interactive dataframe
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
        )

        # Export button
        if st.button("Export Results to CSV"):
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="simulation_results.csv",
                mime="text/csv",
            )

    except Exception as e:
        st.error(f"Error querying database: {e}")
        import traceback
        with st.expander("Error Details"):
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()

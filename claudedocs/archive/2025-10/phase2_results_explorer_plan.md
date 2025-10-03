# Phase 2: Results Explorer Dashboard - Implementation Plan

**Status**: Ready to Begin (pending Phase 1 syntax fixes)
**Estimated Effort**: 16-20 hours
**Dependencies**: Phase 1 completion (database logging validated)
**Target**: Production-ready dashboard for simulation archive exploration

---

## Mission Statement

Create a powerful, intuitive UI for exploring the simulation archive, enabling users to:
- Browse and filter 1000s of simulation runs instantly
- Compare performance across studies, solvers, and parameters
- Extract insights through visual analytics
- Demonstrate the platform's "Operational Metadata" competitive advantage

---

## Phase 2 Architecture

### Component Structure

```
dashboard/
├── results_explorer.py          # Main Streamlit app (NEW)
├── components/                   # UI components (NEW)
│   ├── __init__.py
│   ├── filters.py               # Filter sidebar
│   ├── run_table.py             # Main results table
│   ├── run_detail.py            # Detailed run view
│   └── stats_panel.py           # Database statistics
├── utils/                        # Utilities (NEW)
│   ├── __init__.py
│   ├── data_loader.py           # Database query wrapper
│   └── formatters.py            # Display formatting
└── app_isolated.py              # Existing dashboard (keep)
```

---

## Detailed Implementation Steps

### Step 1: Core Dashboard Setup (2-3 hours)

**File**: `dashboard/results_explorer.py`

**Features**:
```python
import streamlit as st
from ecosystemiser.services.database_metadata_service import DatabaseMetadataService

# Page config
st.set_page_config(
    page_title="EcoSystemiser - Results Explorer",
    page_icon="📊",
    layout="wide"
)

# Initialize database connection
@st.cache_resource
def get_db_service():
    return DatabaseMetadataService("data/simulation_index.sqlite")

# Main layout
st.title("🔍 Simulation Results Explorer")
st.markdown("Explore and analyze your simulation archive")
```

**Success Criteria**:
- ✅ App launches without errors
- ✅ Database connection established
- ✅ Page layout renders correctly

---

### Step 2: Main Results Table (3-4 hours)

**File**: `dashboard/components/run_table.py`

**Features**:
- Display all simulation runs in paginated table
- Columns: run_id, study_id, solver_type, total_cost, renewable_fraction, timestamp
- Sortable by any column
- Click row to view details

**Implementation**:
```python
import streamlit as st
import pandas as pd

def display_results_table(runs_data):
    """Display simulation runs in interactive table."""

    # Convert to DataFrame
    df = pd.DataFrame(runs_data)

    # Format columns
    df['total_cost'] = df['total_cost'].apply(lambda x: f"${x:,.2f}" if x else "N/A")
    df['renewable_fraction'] = df['renewable_fraction'].apply(lambda x: f"{x*100:.1f}%" if x else "N/A")
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Display with selection
    selected = st.dataframe(
        df,
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun"
    )

    return selected
```

**Success Criteria**:
- ✅ Table displays 100+ runs smoothly
- ✅ Sorting works on all columns
- ✅ Row selection triggers detail view
- ✅ Performance <1 second for 1000+ runs

---

### Step 3: Filter Sidebar (2-3 hours)

**File**: `dashboard/components/filters.py`

**Features**:
- Filter by study_id (multiselect)
- Filter by solver_type (multiselect)
- Filter by cost range (slider)
- Filter by renewable fraction range (slider)
- Filter by date range (date picker)
- Clear all filters button

**Implementation**:
```python
def render_filter_sidebar(db_service):
    """Render filter controls in sidebar."""

    st.sidebar.header("🔍 Filters")

    # Get available options from database
    all_runs = db_service.query_simulation_runs()
    studies = sorted(set(r['study_id'] for r in all_runs))
    solvers = sorted(set(r['solver_type'] for r in all_runs))

    # Study filter
    selected_studies = st.sidebar.multiselect(
        "Studies",
        options=studies,
        default=None
    )

    # Solver filter
    selected_solvers = st.sidebar.multiselect(
        "Solver Types",
        options=solvers,
        default=None
    )

    # Cost filter
    cost_range = st.sidebar.slider(
        "Total Cost ($)",
        min_value=0.0,
        max_value=500000.0,
        value=(0.0, 500000.0)
    )

    # Renewable fraction filter
    renewable_range = st.sidebar.slider(
        "Renewable Fraction (%)",
        min_value=0.0,
        max_value=100.0,
        value=(0.0, 100.0)
    )

    # Clear filters button
    if st.sidebar.button("Clear All Filters"):
        st.rerun()

    return {
        'studies': selected_studies,
        'solvers': selected_solvers,
        'cost_range': cost_range,
        'renewable_range': (renewable_range[0]/100, renewable_range[1]/100)
    }
```

**Success Criteria**:
- ✅ Filters update table instantly
- ✅ Multiple filters combine correctly (AND logic)
- ✅ Clear filters resets to full dataset
- ✅ Filter state persists during session

---

### Step 4: Detailed Run View (3-4 hours)

**File**: `dashboard/components/run_detail.py`

**Features**:
- Full KPI panel (all metrics)
- System configuration display
- Solver performance metrics
- Links to result files (Parquet, JSON)
- "Open Results Folder" button

**Implementation**:
```python
def display_run_details(run_data, db_service):
    """Display detailed view of selected run."""

    st.header(f"📋 Run Details: {run_data['run_id']}")

    # KPI Metrics (3 columns)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Cost", f"${run_data['total_cost']:,.2f}")
        st.metric("Renewable Fraction", f"{run_data['renewable_fraction']*100:.1f}%")
        st.metric("Self-Sufficiency", f"{run_data.get('self_sufficiency_rate', 0)*100:.1f}%")

    with col2:
        st.metric("Total Generation", f"{run_data.get('total_generation_kwh', 0):,.0f} kWh")
        st.metric("Total Demand", f"{run_data.get('total_demand_kwh', 0):,.0f} kWh")
        st.metric("Grid Usage", f"{run_data.get('net_grid_usage_kwh', 0):,.0f} kWh")

    with col3:
        st.metric("Solver Type", run_data['solver_type'])
        st.metric("Timesteps", f"{run_data['timesteps']:,}")
        st.metric("Status", run_data['simulation_status'])

    # System Configuration
    with st.expander("🔧 System Configuration"):
        st.json(run_data.get('system_config', {}))

    # File Paths
    st.subheader("📂 Result Files")
    st.code(run_data.get('results_path', 'N/A'), language=None)

    if st.button("📁 Open Results Folder"):
        import subprocess
        subprocess.Popen(f'explorer "{run_data["results_path"]}"')
```

**Success Criteria**:
- ✅ All KPIs displayed correctly
- ✅ System config shows full details
- ✅ File paths are clickable/copyable
- ✅ Open folder button works on Windows

---

### Step 5: Database Statistics Dashboard (2-3 hours)

**File**: `dashboard/components/stats_panel.py`

**Features**:
- Total runs count
- Studies count
- Solver distribution (pie chart)
- Cost distribution (histogram)
- Renewable fraction distribution (histogram)
- Recent activity timeline
- Storage metrics

**Implementation**:
```python
import plotly.express as px
import plotly.graph_objects as go

def display_statistics_panel(db_service):
    """Display database statistics and visualizations."""

    st.header("📊 Database Statistics")

    # Get stats from database
    stats = db_service.get_database_stats()
    all_runs = db_service.query_simulation_runs()

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Runs", stats['total_runs'])
    col2.metric("Total Studies", stats['total_studies'])
    col3.metric("Avg Cost", f"${stats.get('avg_cost', 0):,.2f}")
    col4.metric("Avg Renewable", f"{stats.get('avg_renewable', 0)*100:.1f}%")

    # Solver distribution (pie chart)
    solver_counts = {}
    for run in all_runs:
        solver = run['solver_type']
        solver_counts[solver] = solver_counts.get(solver, 0) + 1

    fig_solvers = px.pie(
        values=list(solver_counts.values()),
        names=list(solver_counts.keys()),
        title="Solver Distribution"
    )
    st.plotly_chart(fig_solvers, use_container_width=True)

    # Cost distribution
    costs = [r['total_cost'] for r in all_runs if r.get('total_cost')]
    fig_costs = px.histogram(
        x=costs,
        nbins=50,
        title="Cost Distribution",
        labels={'x': 'Total Cost ($)', 'y': 'Count'}
    )
    st.plotly_chart(fig_costs, use_container_width=True)

    # Renewable fraction distribution
    renewables = [r['renewable_fraction'] for r in all_runs if r.get('renewable_fraction')]
    fig_renewables = px.histogram(
        x=[r*100 for r in renewables],
        nbins=50,
        title="Renewable Fraction Distribution",
        labels={'x': 'Renewable Fraction (%)', 'y': 'Count'}
    )
    st.plotly_chart(fig_renewables, use_container_width=True)
```

**Success Criteria**:
- ✅ Statistics calculate correctly
- ✅ Charts render smoothly
- ✅ Interactive visualizations work
- ✅ Performance remains fast with 1000+ runs

---

### Step 6: Integration & Polish (2-3 hours)

**Tasks**:
1. Connect all components in main app
2. Add error handling and edge cases
3. Improve styling and UX
4. Add loading states and progress indicators
5. Create README for dashboard usage
6. Test with large dataset (1000+ runs)

**Main App Structure**:
```python
# dashboard/results_explorer.py

def main():
    """Main Results Explorer application."""

    # Initialize
    db_service = get_db_service()

    # Sidebar filters
    filters = render_filter_sidebar(db_service)

    # Apply filters and get runs
    runs = apply_filters(db_service, filters)

    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📋 Results Table", "📊 Statistics", "ℹ️ About"])

    with tab1:
        # Results table
        selected = display_results_table(runs)

        # Detail view if row selected
        if selected:
            run_id = runs[selected]['run_id']
            run_data = db_service.get_run_details(run_id)
            display_run_details(run_data, db_service)

    with tab2:
        # Statistics dashboard
        display_statistics_panel(db_service)

    with tab3:
        # About/help
        display_about_page()

if __name__ == "__main__":
    main()
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/unit/test_results_explorer_components.py`

```python
def test_filter_logic():
    """Test filter application logic."""
    # Test single filter
    # Test multiple filters
    # Test empty results
    # Test edge cases

def test_data_formatting():
    """Test data display formatting."""
    # Test cost formatting
    # Test percentage formatting
    # Test date formatting
```

### Integration Tests

**File**: `tests/integration/test_results_explorer_integration.py`

```python
def test_end_to_end_workflow():
    """Test complete user workflow."""
    # 1. Load dashboard
    # 2. Apply filters
    # 3. Select run
    # 4. View details
    # 5. Navigate to stats
```

### Performance Tests

**File**: `tests/performance/test_dashboard_performance.py`

```python
def test_large_dataset_performance():
    """Test performance with 1000+ runs."""
    # Test table rendering time
    # Test filter application time
    # Test chart generation time
```

---

## Phase 2 Success Criteria

### Functional Requirements

✅ Dashboard loads simulation archive from database
✅ Table displays all runs with sortable columns
✅ Filters work correctly (study, solver, cost, renewable)
✅ Detailed view shows all KPIs and metadata
✅ Statistics panel provides visual insights
✅ Performance <2 seconds for 1000+ runs

### User Experience Requirements

✅ Intuitive navigation and controls
✅ Responsive layout (works on different screen sizes)
✅ Clear visual hierarchy
✅ Helpful error messages
✅ Loading indicators for long operations

### Technical Requirements

✅ Clean separation of concerns (components, utils)
✅ Efficient database queries (no N+1 queries)
✅ Proper error handling
✅ Code follows Hive golden rules
✅ Comprehensive test coverage

---

## Deployment

### Local Development

```bash
cd apps/ecosystemiser

# Install dependencies (if needed)
poetry install

# Run dashboard
poetry run streamlit run dashboard/results_explorer.py

# Access at http://localhost:8501
```

### Production Deployment

```bash
# Option 1: Local server
nohup streamlit run dashboard/results_explorer.py --server.port 8501 &

# Option 2: Docker
docker build -t ecosystemiser-dashboard .
docker run -p 8501:8501 -v $(pwd)/data:/app/data ecosystemiser-dashboard

# Option 3: Streamlit Cloud
# Push to GitHub and connect via Streamlit Cloud dashboard
```

---

## Phase 2 Timeline

| Week | Task | Hours | Deliverable |
|------|------|-------|-------------|
| 1 | Core setup + table | 5-7 | Basic dashboard working |
| 1 | Filters + detail view | 6-8 | Full functionality |
| 2 | Statistics + polish | 5-7 | Production-ready UI |

**Total**: 16-22 hours (~2 weeks part-time)

---

## Phase 3 Preview: Head-to-Head Comparison

After Phase 2, the next capability:

### Multi-Run Comparison Feature

- Select 2-10 runs via checkboxes
- "Compare Selected" button
- Side-by-side KPI table with delta columns
- Overlayed time-series charts (battery SOC, grid usage)
- Export comparison report as PDF

**Estimated Effort**: 12-16 hours

---

## Resources & References

### Streamlit Documentation

- [Streamlit API Reference](https://docs.streamlit.io/library/api-reference)
- [Data Display](https://docs.streamlit.io/library/api-reference/data)
- [Plotly Integration](https://docs.streamlit.io/library/api-reference/charts/st.plotly_chart)

### Internal Documentation

- Phase 1 Status: `claudedocs/phase1_database_integration_status.md`
- Database Schema: `apps/ecosystemiser/src/ecosystemiser/services/database_metadata_service.py`
- Validation: `apps/ecosystemiser/scripts/validate_database_logging.py`

### Example Dashboards

- Existing: `apps/ecosystemiser/dashboard/app_isolated.py`
- Reference: Streamlit gallery examples

---

## Next Steps After Phase 2

1. **Phase 3**: Head-to-Head Comparison (12-16 hours)
2. **Phase 4**: GA/MC Study Dashboards (16-20 hours)
   - Pareto front visualization
   - Convergence plots
   - Uncertainty analysis
3. **Phase 5**: Automated Insights (20-24 hours)
   - Anomaly detection
   - Recommendation engine
   - Pattern recognition

---

## Contact & Coordination

**Prerequisites**: Phase 1 validation passing (100%)
**Start Date**: Immediately after Phase 1 complete
**Estimated Completion**: 2 weeks from start
**Agent**: ecosystemiser

**Validation Command**:
```bash
# Confirm Phase 1 before starting Phase 2
cd apps/ecosystemiser
poetry run python scripts/validate_database_logging.py
# Expected: [OK] All validation tests passed!
```

---

*Phase 2 transforms the simulation archive from a passive database into an interactive, insightful exploration tool. It makes the "Operational Metadata" moat visible and valuable to users.*

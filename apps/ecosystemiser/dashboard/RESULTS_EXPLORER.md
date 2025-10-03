# Results Explorer - Simulation Archive Dashboard

**Status**: Phase 2 Complete (MVP)
**Version**: 1.0.0
**Date**: 2025-10-03

Production-ready dashboard for exploring the EcoSystemiser simulation archive.

## Features

- **Browse & Filter**: Explore 1000s of simulation runs instantly
- **Advanced Filters**: Filter by study, solver type, cost range, renewable fraction
- **Interactive Table**: Sortable, searchable results display
- **Export**: Download results as CSV
- **Real-time Stats**: Database statistics and metrics

## Quick Start

```bash
cd apps/ecosystemiser
streamlit run dashboard/results_explorer.py
```

Access at: http://localhost:8501

## Requirements

- Python 3.10+
- Streamlit
- pandas
- SQLite database at `data/simulation_index.sqlite`

## Usage Guide

### 1. Launch Dashboard

```bash
streamlit run dashboard/results_explorer.py
```

### 2. Filter Results

Use the sidebar to filter runs:

- **Study ID**: Enter specific study identifier
- **Solver Type**: Filter by hybrid, milp, rule_based, or rolling_horizon
- **Cost Range**: Slider to filter by total cost ($0-$500K)
- **Renewable Fraction**: Minimum renewable energy percentage
- **Max Results**: Limit number of results (10-1000)

### 3. View Results

- Results displayed in sortable table
- Click column headers to sort
- Formatted cost and percentages

### 4. Export Data

- Click "Export Results to CSV"
- Download filtered results for external analysis

## Database Schema

The dashboard queries the `simulation_runs` table:

```sql
simulation_runs (
    run_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    solver_type TEXT,
    total_cost REAL,
    renewable_fraction REAL,
    simulation_status TEXT,
    timestamp TEXT,
    ...
)
```

## Architecture

```
results_explorer.py
├── Database Connection (cached)
├── Sidebar Filters
├── Query Builder
├── Results Table (pandas DataFrame)
└── Export Functionality
```

## Validation

Phase 1 validation confirmed:
- ✅ SQL schema functional
- ✅ Database queries working
- ✅ Data insertion/retrieval tested

Validate Phase 1:
```bash
python scripts/validate_phase1_minimal.py
```

## Next Features (Phase 3+)

- [ ] Multi-run comparison
- [ ] Time-series visualizations
- [ ] Detailed run view modal
- [ ] Statistics dashboard tab
- [ ] Pareto front plotting
- [ ] Export to PDF reports

## Troubleshooting

### Database Not Found

If you see "Database not found", create it by:

1. Running a simulation with database logging
2. Or creating empty database: `mkdir -p data && touch data/simulation_index.sqlite`

### Import Errors

The dashboard uses `importlib` to avoid import chain issues. If you see import errors:

```python
# Dashboard handles this internally
spec = importlib.util.spec_from_file_location(...)
```

### No Results

If no results appear:
- Check database has runs: `sqlite3 data/simulation_index.sqlite "SELECT COUNT(*) FROM simulation_runs;"`
- Adjust filter criteria
- Check filter ranges aren't too restrictive

## Development

### File Structure

```
dashboard/
├── results_explorer.py         # Main application
├── components/                  # Future UI components
│   └── __init__.py
└── utils/                       # Future utilities
    └── __init__.py
```

### Adding Features

1. Create component files in `components/`
2. Create utility functions in `utils/`
3. Import and integrate in `results_explorer.py`

### Testing

Manual testing checklist:
- [ ] Dashboard launches without errors
- [ ] Filters apply correctly
- [ ] Results display properly
- [ ] Export works
- [ ] Stats show correct counts

## Documentation

- **Implementation Plan**: `claudedocs/phase2_results_explorer_plan.md`
- **Phase 1 Complete**: `PHASE1_COMPLETE.txt`
- **Project Status**: `STATUS.txt`

## Strategic Value

This dashboard demonstrates the platform's "Operational Metadata" competitive advantage by:

- Enabling instant exploration of 1000s of simulations
- Supporting data-driven optimization decisions
- Creating foundation for ML training data collection
- Proving "Performance at Scale" capability

---

**Built with**: Streamlit, pandas, SQLite
**Part of**: "Data to Decisions" Production Data Pipeline
**Phase**: 2 of 5 complete

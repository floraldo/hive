"""
EcoSystemiser Climate Dashboard - Redirect to Isolated Version

This file redirects to the isolated version to maintain architectural separation.
The isolated version (app_isolated.py) does not import from the ecosystemiser package.
"""

import streamlit as st

st.set_page_config(
    page_title="EcoSystemiser Dashboard - Redirect",
    page_icon="🔄",
)

st.warning("""
### Dashboard Architecture Update

The dashboard has been refactored to maintain **architectural isolation** from the main ecosystemiser package.

Please use one of the following:

1. **Run the isolated dashboard:**
   ```bash
   streamlit run app_isolated.py
   ```

2. **Why this change?**
   - ✅ Maintains clean architecture boundaries
   - ✅ No direct imports from ecosystemiser package
   - ✅ Works with output artifacts (JSON/CSV files)
   - ✅ Can be deployed independently

3. **Benefits:**
   - Dashboard can run without the full ecosystemiser installation
   - Cleaner separation of concerns
   - Easier to deploy and scale independently
   - Follows the dual-frontend strategy (Streamlit as "The Lab")

This change is part of the EcoSystemiser v3.0 architectural refactoring to ensure
proper separation between the presentation layer (dashboard) and the core business logic.
""")

st.info("💡 **Tip:** The isolated dashboard can load any climate data JSON/CSV file from the results directory.")

if st.button("Open app_isolated.py documentation"):
    with open("app_isolated.py", "r") as f:
        lines = f.readlines()[:30]
    st.code("".join(lines), language="python")
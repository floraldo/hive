"""Final debug to identify the remaining 4.77e-05 kW discrepancy."""
import json
import numpy as np
from hive_logging import get_logger

logger = get_logger(__name__)

# Load golden results for comparison
with open('tests/systemiser_minimal_golden.json', 'r') as f:
    golden = json.load(f)

# Run our validation to get our results
from validate_systemiser_equivalence import main as run_validation

# Capture our results by running the validation
try:
    run_validation()
except SystemExit:
    pass

# The issue is likely in the get_available_discharge method
# Let's test the exact calculation

logger.debug("=== FINAL DEBUG ANALYSIS ===")
logger.info()

# Key insight: The discrepancy of 4.77e-05 might be due to a small calculation error
# Let's check if it's related to the efficiency factor

# In our implementation: available_discharge = min(P_max, current_level)
# But maybe the golden dataset expects: available_discharge = min(P_max, current_level * eta)

logger.info("Testing different discharge calculation methods:")
logger.info()

E_init = 5.0
P_max = 5.0
eta = 0.95

method1 = min(P_max, E_init)  # Our current method
method2 = min(P_max, E_init * eta)  # Alternative with efficiency
method3 = min(P_max, E_init / eta)  # Alternative with inverse efficiency

logger.info(f"Method 1 (current): min({P_max}, {E_init}) = {method1}")
logger.info(f"Method 2 (with eta): min({P_max}, {E_init} * {eta}) = {method2}")  
logger.info(f"Method 3 (with 1/eta): min({P_max}, {E_init} / {eta}) = {method3}")
logger.info()

golden_grid_battery_t0 = golden['flows']['Grid_P_Battery']['values'][0]
logger.info(f"Golden Grid_P_Battery[0] = {golden_grid_battery_t0}")
logger.info()

# Check which method matches
diff1 = abs(method1 - golden_grid_battery_t0)
diff2 = abs(method2 - golden_grid_battery_t0)
diff3 = abs(method3 - golden_grid_battery_t0)

logger.info(f"Difference method1: {diff1:.9f}")
logger.info(f"Difference method2: {diff2:.9f}")
logger.info(f"Difference method3: {diff3:.9f}")


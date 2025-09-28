#!/usr/bin/env python3
"""
Quick test script for the EcoSystemiser dashboard
"""

import sys

# Test imports
try:
    from EcoSystemiser.profile_loader.climate import (
        get_profile_sync, 
        ClimateRequest,
        ClimateResponse
    )
    from EcoSystemiser.profile_loader.climate.data_models import CANONICAL_VARIABLES
    from EcoSystemiser.profile_loader.climate.adapters.factory import list_available_adapters
    
    print("[OK] All EcoSystemiser imports successful")
    
    # Test getting adapter list
    adapters = list_available_adapters()
    print(f"[OK] Found {len(adapters)} adapters: {', '.join(adapters)}")
    
    # Test canonical variables
    print(f"[OK] Found {len(CANONICAL_VARIABLES)} canonical variables")
    
    # Test creating a request (without executing)
    request = ClimateRequest(
        location=(38.7, -9.1),
        variables=["temp_air", "ghi"],
        source="nasa_power",
        period={"year": 2023},
        mode="observed",
        resolution="1H"
    )
    print("[OK] Successfully created ClimateRequest")
    
    print("\n[SUCCESS] All tests passed! Dashboard dependencies are working.")
    print("\nTo run the dashboard:")
    print("  cd apps/EcoSystemiser/dashboard")
    print("  streamlit run app.py")
    
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Error: {e}")
    sys.exit(1)
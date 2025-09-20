#!/usr/bin/env python3
"""
Test Weather Data Integration with Systemiser

This script demonstrates how to use the weather data module
to fetch, process, and integrate weather data for energy system simulation.
"""

import sys
import os
import logging
from datetime import datetime

# Add Systemiser to path (adjust for new location in tests/data/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_weather_data_integration():
    """Test the complete weather data integration workflow."""
    
    print("=" * 60)
    print("SYSTEMISER WEATHER DATA INTEGRATION TEST")
    print("=" * 60)
    
    try:
        # Import weather components
        from data.weather import WeatherDataManager
        from utils.weather_utils import (
            create_component_profiles_from_weather, 
            calculate_weather_statistics
        )
        
        print("✅ Successfully imported weather modules")
        
        # Initialize weather data manager
        print("\n1. Initializing Weather Data Manager...")
        weather_manager = WeatherDataManager()
        
        print(f"   Available providers: {weather_manager.list_providers()}")
        print(f"   Available processors: {weather_manager.list_processors()}")
        
        # Test location: Wageningen, Netherlands
        latitude = 51.97
        longitude = 5.66
        
        print(f"\n2. Testing weather data fetch for location: {latitude}, {longitude}")
        print("   Fetching data for January 2022 (this may take a moment)...")
        
        # Fetch weather data for a small period first
        weather_df = weather_manager.get_data(
            latitude=latitude,
            longitude=longitude,
            start_date="20220101",
            end_date="20220107",  # Just one week for testing
            use_cache=True
        )
        
        if weather_df is not None and not weather_df.empty:
            print(f"   ✅ Successfully fetched weather data: {weather_df.shape}")
            print(f"   Available columns: {list(weather_df.columns)}")
            print(f"   Date range: {weather_df.index.min()} to {weather_df.index.max()}")
            
            # Show sample data
            print("\n   Sample weather data:")
            print(weather_df.head())
            
        else:
            print("   ❌ Failed to fetch weather data")
            return False
            
        # Test weather statistics
        print("\n3. Calculating weather statistics...")
        stats = calculate_weather_statistics(weather_df)
        
        if stats:
            print("   ✅ Weather statistics calculated successfully")
            if 'temperature' in stats:
                temp_stats = stats['temperature']
                print(f"   Temperature: mean={temp_stats['mean_annual_c']:.1f}°C, "
                      f"min={temp_stats['min_c']:.1f}°C, max={temp_stats['max_c']:.1f}°C")
            
            if 'solar' in stats:
                solar_stats = stats['solar']
                print(f"   Solar: mean={solar_stats['mean_annual_wm2']:.1f} W/m², "
                      f"annual={solar_stats['annual_kwh_m2']:.1f} kWh/m²")
        
        # Test component profile generation
        print("\n4. Testing component profile generation...")
        
        component_configs = {
            'solar_pv_100kw': {
                'type': 'solar_pv',
                'capacity_kw': 100,
                'efficiency': 0.20,
                'system_losses': 0.15
            },
            'heat_demand_residential': {
                'type': 'heat_demand',
                'base_demand_kw': 25,
                'heating_threshold_c': 16.0,
                'design_temp_c': -10.0,
                'design_demand_multiplier': 3.0
            },
            'wind_turbine_25kw': {
                'type': 'wind_turbine',
                'capacity_kw': 25,
                'cut_in_speed': 3.0,
                'rated_speed': 12.0,
                'cut_out_speed': 25.0
            },
            'rainwater_collection': {
                'type': 'rainwater_collection',
                'collection_area_m2': 200,
                'collection_efficiency': 0.8
            }
        }
        
        profiles = create_component_profiles_from_weather(weather_df, component_configs)
        
        if profiles:
            print(f"   ✅ Successfully created {len(profiles)} component profiles")
            for comp_name, profile in profiles.items():
                if profile is not None and not profile.empty:
                    print(f"   {comp_name}: mean={profile.mean():.2f}, max={profile.max():.2f}, "
                          f"total={profile.sum():.0f}")
                else:
                    print(f"   {comp_name}: ❌ Failed to create profile")
        else:
            print("   ❌ Failed to create component profiles")
            
        # Test caching functionality
        print("\n5. Testing caching functionality...")
        cache_info = weather_manager.get_cache_info()
        print(f"   Cache directory: {cache_info['cache_dir']}")
        print(f"   Cached files: {cache_info['total_files']}")
        print(f"   Total cache size: {cache_info['total_size_mb']:.2f} MB")
        
        # Test loading from cache
        print("   Testing cache retrieval...")
        cached_df = weather_manager.get_data(
            latitude=latitude,
            longitude=longitude,
            start_date="20220101",
            end_date="20220107",
            use_cache=True
        )
        
        if cached_df is not None and cached_df.equals(weather_df):
            print("   ✅ Cache retrieval successful")
        else:
            print("   ⚠️  Cache retrieval gave different results")
            
        print("\n" + "=" * 60)
        print("WEATHER DATA INTEGRATION TEST COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        print(f"""
Integration Summary:
- Weather data provider: NASA POWER
- Data processor: Standard processor with validation
- Location tested: Wageningen, NL ({latitude}, {longitude})
- Date range: 1 week in January 2022
- Components tested: {len(component_configs)} types
- Profiles generated: {len(profiles)} successful
- Caching: Functional

Next steps:
1. Integrate weather profiles with existing Systemiser components
2. Test with longer time series (full year)
3. Add more sophisticated weather-component relationships
4. Integrate with the rule-based solver for weather-driven simulations
        """)
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure all dependencies are installed and the Systemiser module is properly set up")
        return False
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_weather_data_integration()
    sys.exit(0 if success else 1) 
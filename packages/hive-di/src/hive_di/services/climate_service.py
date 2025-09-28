"""
Climate Service Implementation

Injectable climate service that replaces the global climate service singleton.
Provides weather data integration with proper dependency injection.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from ..interfaces import IClimateService, IConfigurationService, IDatabaseConnectionService, IDisposable


class ClimateService(IClimateService, IDisposable):
    """
    Injectable climate service

    Replaces the global climate service singleton with a proper service that can be
    configured and injected independently.
    """

    def __init__(self,
                 configuration_service: IConfigurationService,
                 database_service: IDatabaseConnectionService,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize climate service

        Args:
            configuration_service: Configuration service for getting climate settings
            database_service: Database service for data caching
            config: Optional override configuration
        """
        self._config_service = configuration_service
        self._db_service = database_service
        self._override_config = config or {}

        # Get climate configuration
        climate_config = self._config_service.get_climate_config()
        self._config = {**climate_config, **self._override_config}

        # Climate service settings
        self.default_adapter = self._config.get('default_adapter', 'meteostat')
        self.cache_enabled = self._config.get('cache_enabled', True)
        self.cache_ttl = self._config.get('cache_ttl', 3600)
        self.max_parallel_requests = self._config.get('max_parallel_requests', 5)

        # Available adapters (placeholder - would be loaded from actual adapters)
        self._available_adapters = ['meteostat', 'era5', 'nasa_power', 'pvgis', 'file_epw']

        # Initialize cache tables if needed
        if self.cache_enabled:
            self._ensure_cache_tables()

    def _ensure_cache_tables(self) -> None:
        """Ensure climate data cache tables exist"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()

            # Climate data cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS climate_data_cache (
                    cache_key TEXT PRIMARY KEY,
                    adapter_name TEXT NOT NULL,
                    location_data TEXT NOT NULL,
                    date_range_data TEXT NOT NULL,
                    cached_data TEXT NOT NULL,
                    cache_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)

            # Index for cleanup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_climate_cache_expires
                ON climate_data_cache(expires_at)
            """)

            conn.commit()

    def _generate_cache_key(self, adapter: str, location: Dict[str, Any], date_range: Dict[str, Any]) -> str:
        """Generate cache key for weather data request"""
        import hashlib
        import json

        key_data = {
            'adapter': adapter,
            'location': location,
            'date_range': date_range
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_cached_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached weather data if available and not expired"""
        if not self.cache_enabled:
            return None

        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cached_data FROM climate_data_cache
                WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP
            """, (cache_key,))
            row = cursor.fetchone()

        if row:
            import json
            return json.loads(row[0])
        return None

    def _cache_data(self, cache_key: str, adapter: str, location: Dict[str, Any],
                   date_range: Dict[str, Any], data: Dict[str, Any]) -> None:
        """Cache weather data"""
        if not self.cache_enabled:
            return

        import json
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.cache_ttl)

        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO climate_data_cache (
                    cache_key, adapter_name, location_data, date_range_data,
                    cached_data, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                cache_key,
                adapter,
                json.dumps(location),
                json.dumps(date_range),
                json.dumps(data),
                expires_at.isoformat()
            ))
            conn.commit()

    def _fetch_weather_data(self, adapter: str, location: Dict[str, Any],
                           date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch weather data from adapter (placeholder implementation)"""
        # This would be the actual adapter integration
        # For now, return placeholder data

        start_date = date_range.get('start_date', '2024-01-01')
        end_date = date_range.get('end_date', '2024-01-02')
        lat = location.get('latitude', 0.0)
        lon = location.get('longitude', 0.0)

        # Placeholder weather data
        return {
            'adapter': adapter,
            'location': {
                'latitude': lat,
                'longitude': lon,
                'name': location.get('name', f"Location {lat}, {lon}")
            },
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            },
            'data': {
                'temperature': [20.5, 21.0, 19.8, 22.1],  # Sample data
                'humidity': [65, 68, 72, 60],
                'precipitation': [0.0, 2.5, 0.0, 1.2],
                'wind_speed': [5.2, 6.1, 4.8, 7.3]
            },
            'metadata': {
                'units': {
                    'temperature': 'celsius',
                    'humidity': 'percent',
                    'precipitation': 'mm',
                    'wind_speed': 'km/h'
                },
                'data_points': 4,
                'quality': 'good'
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    # IClimateService interface implementation

    def get_weather_data(self, location: Dict[str, Any],
                        date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather data for location and date range"""
        adapter = self.default_adapter
        cache_key = self._generate_cache_key(adapter, location, date_range)

        # Try cache first
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            cached_data['from_cache'] = True
            return cached_data

        # Fetch from adapter
        data = self._fetch_weather_data(adapter, location, date_range)
        data['from_cache'] = False

        # Cache the data
        self._cache_data(cache_key, adapter, location, date_range, data)

        return data

    async def get_weather_data_async(self, location: Dict[str, Any],
                                    date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather data asynchronously"""
        # For now, just call the sync version
        # In a real implementation, this would use async HTTP clients for adapters
        return self.get_weather_data(location, date_range)

    def get_available_adapters(self) -> List[str]:
        """Get list of available climate data adapters"""
        return self._available_adapters.copy()

    def get_adapter_capabilities(self, adapter_name: str) -> Dict[str, Any]:
        """Get capabilities for a specific adapter"""
        if adapter_name not in self._available_adapters:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        # Placeholder capabilities - would be loaded from actual adapters
        capabilities = {
            'meteostat': {
                'global_coverage': True,
                'historical_data': True,
                'forecast_data': False,
                'data_types': ['temperature', 'humidity', 'precipitation', 'wind'],
                'max_date_range_days': 365,
                'rate_limit': 1000  # requests per day
            },
            'era5': {
                'global_coverage': True,
                'historical_data': True,
                'forecast_data': False,
                'data_types': ['temperature', 'humidity', 'precipitation', 'wind', 'pressure'],
                'max_date_range_days': 1000,
                'rate_limit': 500
            },
            'nasa_power': {
                'global_coverage': True,
                'historical_data': True,
                'forecast_data': False,
                'data_types': ['temperature', 'humidity', 'solar_radiation'],
                'max_date_range_days': 365,
                'rate_limit': 1000
            },
            'pvgis': {
                'global_coverage': True,
                'historical_data': True,
                'forecast_data': False,
                'data_types': ['solar_radiation', 'temperature'],
                'max_date_range_days': 365,
                'rate_limit': 500
            },
            'file_epw': {
                'global_coverage': False,
                'historical_data': True,
                'forecast_data': False,
                'data_types': ['temperature', 'humidity', 'precipitation', 'wind', 'solar_radiation'],
                'max_date_range_days': 365,
                'rate_limit': None  # File-based, no API limits
            }
        }

        return capabilities.get(adapter_name, {})

    # IDisposable interface implementation

    def dispose(self) -> None:
        """Clean up climate service resources"""
        # Clean up cache if needed
        if self.cache_enabled:
            self.cleanup_expired_cache()

    # Additional utility methods

    def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries"""
        if not self.cache_enabled:
            return 0

        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM climate_data_cache WHERE expires_at <= CURRENT_TIMESTAMP
            """)
            deleted_count = cursor.rowcount
            conn.commit()

        return deleted_count

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.cache_enabled:
            return {'cache_enabled': False}

        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()

            # Total cache entries
            cursor.execute("SELECT COUNT(*) FROM climate_data_cache")
            total_entries = cursor.fetchone()[0]

            # Expired entries
            cursor.execute("""
                SELECT COUNT(*) FROM climate_data_cache WHERE expires_at <= CURRENT_TIMESTAMP
            """)
            expired_entries = cursor.fetchone()[0]

            # Entries by adapter
            cursor.execute("""
                SELECT adapter_name, COUNT(*) FROM climate_data_cache
                GROUP BY adapter_name
            """)
            by_adapter = dict(cursor.fetchall())

        return {
            'cache_enabled': True,
            'total_entries': total_entries,
            'expired_entries': expired_entries,
            'active_entries': total_entries - expired_entries,
            'by_adapter': by_adapter,
            'cache_ttl': self.cache_ttl
        }

    def clear_cache(self) -> int:
        """Clear all cache entries"""
        if not self.cache_enabled:
            return 0

        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM climate_data_cache")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM climate_data_cache")
            conn.commit()

        return count

    def get_weather_data_with_adapter(self, adapter: str, location: Dict[str, Any],
                                     date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather data using a specific adapter"""
        if adapter not in self._available_adapters:
            raise ValueError(f"Unknown adapter: {adapter}")

        cache_key = self._generate_cache_key(adapter, location, date_range)

        # Try cache first
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            cached_data['from_cache'] = True
            return cached_data

        # Fetch from specified adapter
        data = self._fetch_weather_data(adapter, location, date_range)
        data['from_cache'] = False

        # Cache the data
        self._cache_data(cache_key, adapter, location, date_range, data)

        return data
"""
Shared base adapter with unified HTTP client, caching, and retry logic.

This module provides the foundation for all climate data adapters with:
- Async HTTP client with connection pooling
- Retry logic with exponential backoff
- Rate limiting per data source
- Layered caching strategy
- Standardized error handling
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from EcoSystemiser.hive_logging_adapter import get_logger
import httpx
import xarray as xr
import numpy as np
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

# Import centralized settings
from EcoSystemiser.settings import get_settings, Settings
# Import config models from centralized location to avoid circular dependency
from EcoSystemiser.profile_loader.config_models import HTTPConfig, RateLimitConfig, CacheConfig, RateLimitStrategy

logger = get_logger(__name__)

class CacheLevel(Enum):
    """Cache tier levels"""
    MEMORY = "memory"
    DISK = "disk"
    REDIS = "redis"

# Config dataclasses are now imported from config_models.py

class RateLimiter:
    """Token bucket rate limiter implementation"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.burst_size
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
        
    async def acquire(self):
        """Acquire permission to make a request"""
        async with self.lock:
            await self._refill()
            
            if self.tokens > 0:
                self.tokens -= 1
                return True
                
            # Calculate wait time until next token
            tokens_per_second = self.config.requests_per_minute / 60
            wait_time = 1.0 / tokens_per_second
            
            await asyncio.sleep(wait_time)
            await self._refill()
            
            if self.tokens > 0:
                self.tokens -= 1
                return True
            
            return False
    
    async def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        
        tokens_per_second = self.config.requests_per_minute / 60
        new_tokens = elapsed * tokens_per_second
        
        if new_tokens >= 1:
            self.tokens = min(
                self.config.burst_size,
                self.tokens + int(new_tokens)
            )
            self.last_refill = now

class LayeredCache:
    """Three-tier caching system: memory -> disk -> redis"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self._memory_cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_order: List[str] = []  # For LRU eviction
        
        # Initialize disk cache if diskcache available
        self._disk_cache = None
        try:
            import diskcache
            self._disk_cache = diskcache.Cache(
                config.cache_dir,
                eviction_policy='least-recently-used'
            )
        except ImportError:
            logger.warning("diskcache not installed, disk caching disabled")
        
        # Initialize Redis cache if configured
        self._redis_cache = None
        if config.redis_url:
            try:
                import redis
                self._redis_cache = redis.from_url(config.redis_url)
            except (ImportError, Exception) as e:
                logger.warning(f"Redis cache initialization failed: {e}")
    
    def _make_key(self, **kwargs) -> str:
        """Generate cache key from request parameters"""
        # Sort kwargs for consistent hashing
        sorted_kwargs = sorted(kwargs.items())
        key_str = json.dumps(sorted_kwargs, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    async def get(self, **kwargs) -> Optional[Any]:
        """Get value from cache hierarchy"""
        key = self._make_key(**kwargs)
        
        # Check memory cache
        if key in self._memory_cache:
            value, expiry = self._memory_cache[key]
            if time.time() < expiry:
                # Move to end for LRU
                self._cache_order.remove(key)
                self._cache_order.append(key)
                logger.debug(f"Memory cache hit: {key[:8]}...")
                return value
            else:
                # Expired, remove it
                del self._memory_cache[key]
                self._cache_order.remove(key)
        
        # Check disk cache
        if self._disk_cache:
            try:
                value = self._disk_cache.get(key)
                if value is not None:
                    logger.debug(f"Disk cache hit: {key[:8]}...")
                    # Promote to memory cache
                    await self._set_memory(key, value)
                    return value
            except Exception as e:
                logger.error(f"Disk cache error: {e}")
        
        # Check Redis cache
        if self._redis_cache:
            try:
                value_bytes = self._redis_cache.get(key)
                if value_bytes:
                    import pickle
                    value = pickle.loads(value_bytes)
                    logger.debug(f"Redis cache hit: {key[:8]}...")
                    # Promote to memory and disk cache
                    await self._set_memory(key, value)
                    if self._disk_cache:
                        self._disk_cache.set(
                            key, value, 
                            expire=self.config.disk_ttl
                        )
                    return value
            except Exception as e:
                logger.error(f"Redis cache error: {e}")
        
        logger.debug(f"Cache miss: {key[:8]}...")
        return None
    
    async def set(self, value: Any, **kwargs):
        """Set value in cache hierarchy"""
        key = self._make_key(**kwargs)
        
        # Set in all cache levels
        await self._set_memory(key, value)
        
        if self._disk_cache:
            try:
                self._disk_cache.set(
                    key, value, 
                    expire=self.config.disk_ttl
                )
            except Exception as e:
                logger.error(f"Disk cache write error: {e}")
        
        if self._redis_cache:
            try:
                import pickle
                self._redis_cache.setex(
                    key,
                    self.config.redis_ttl,
                    pickle.dumps(value)
                )
            except Exception as e:
                logger.error(f"Redis cache write error: {e}")
    
    async def _set_memory(self, key: str, value: Any):
        """Set value in memory cache with LRU eviction"""
        # Evict if at capacity
        if len(self._memory_cache) >= self.config.memory_size:
            if self._cache_order:
                oldest = self._cache_order.pop(0)
                del self._memory_cache[oldest]
        
        expiry = time.time() + self.config.memory_ttl
        self._memory_cache[key] = (value, expiry)
        if key in self._cache_order:
            self._cache_order.remove(key)
        self._cache_order.append(key)

class SharedHTTPClient:
    """Shared async HTTP client with retry and rate limiting"""
    
    def __init__(
        self,
        config: HTTPConfig = HTTPConfig(),
        rate_limit_config: Optional[RateLimitConfig] = None
    ):
        self.config = config
        self.rate_limiter = RateLimiter(rate_limit_config) if rate_limit_config else None
        
        # Create connection pool with limits
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            limits=httpx.Limits(
                max_connections=config.connection_pool_size,
                max_keepalive_connections=config.connection_pool_size // 2,
                keepalive_expiry=config.keepalive_expiry
            ),
            verify=config.verify_ssl,
            follow_redirects=config.follow_redirects
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def get(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> httpx.Response:
        """Make GET request with retry and rate limiting"""
        if self.rate_limiter:
            await self.rate_limiter.acquire()
        
        response = await self._client.get(
            url,
            params=params,
            headers=headers,
            **kwargs
        )
        response.raise_for_status()
        return response
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def post(
        self,
        url: str,
        json: Optional[Dict] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> httpx.Response:
        """Make POST request with retry and rate limiting"""
        if self.rate_limiter:
            await self.rate_limiter.acquire()
        
        response = await self._client.post(
            url,
            json=json,
            data=data,
            headers=headers,
            **kwargs
        )
        response.raise_for_status()
        return response
    
    async def close(self):
        """Close HTTP client connections"""
        await self._client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

class BaseAdapter(ABC):
    """
    Base adapter with shared functionality for all climate data sources.
    
    This class provides:
    - Unified async HTTP client with pooling and retry
    - Rate limiting per source
    - Layered caching (memory -> disk -> redis)
    - Common data transformations
    - Standardized error handling
    """
    
    def __init__(
        self,
        name: str,
        http_config: Optional[HTTPConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        cache_config: Optional[CacheConfig] = None
    ):
        self.name = name
        self.logger = get_logger(f"{__name__}.{name}")
        
        # Initialize configurations with defaults
        self.http_config = http_config or HTTPConfig()
        self.rate_limit_config = rate_limit_config
        self.cache_config = cache_config or CacheConfig()
        
        # Initialize shared components
        self.http_client = SharedHTTPClient(
            self.http_config,
            self.rate_limit_config
        )
        self.cache = LayeredCache(self.cache_config)
        
        # Metrics
        self.request_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
    
    async def fetch(
        self,
        location: Tuple[float, float],
        variables: List[str],
        period: Dict[str, Any],
        **kwargs
    ) -> Optional[xr.Dataset]:
        """
        Main entry point for fetching climate data.
        
        Implements the unified pipeline:
        1. Check cache
        2. Fetch from source if needed
        3. Transform to xarray Dataset
        4. Validate data
        5. Cache results
        """
        self.request_count += 1
        
        # Check cache first
        cached = await self.cache.get(
            source=self.name,
            location=location,
            variables=variables,
            period=period,
            **kwargs
        )
        
        if cached is not None:
            self.cache_hits += 1
            self.logger.debug(f"Cache hit for {location}, {period}")
            return cached
        
        self.cache_misses += 1
        
        try:
            # Fetch raw data from source
            raw_data = await self._fetch_raw(
                location, variables, period, **kwargs
            )
            
            if raw_data is None:
                return None
            
            # Transform to xarray Dataset
            ds = await self._transform_data(raw_data, location, variables)
            
            # Validate data
            ds = await self._validate_data(ds)
            
            # Cache results
            await self.cache.set(
                ds,
                source=self.name,
                location=location,
                variables=variables,
                period=period,
                **kwargs
            )
            
            return ds
            
        except Exception as e:
            self.logger.error(f"Failed to fetch data: {e}")
            raise
    
    @abstractmethod
    async def _fetch_raw(
        self,
        location: Tuple[float, float],
        variables: List[str],
        period: Dict[str, Any],
        **kwargs
    ) -> Optional[Any]:
        """Fetch raw data from the specific source"""
        pass
    
    @abstractmethod
    async def _transform_data(
        self,
        raw_data: Any,
        location: Tuple[float, float],
        variables: List[str]
    ) -> xr.Dataset:
        """Transform raw data to xarray Dataset"""
        pass
    
    async def _validate_data(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Common validation applicable to all sources.
        
        Can be overridden for source-specific validation.
        """
        # Check for required dimensions
        if 'time' not in ds.dims:
            raise ValueError("Dataset missing required 'time' dimension")
        
        # Check for empty variables
        for var_name in ds.data_vars:
            if ds[var_name].isnull().all():
                self.logger.warning(f"Variable '{var_name}' contains only null values")
        
        # Ensure time is sorted
        if not ds.time.to_pandas().is_monotonic_increasing:
            ds = ds.sortby('time')
        
        return ds
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get adapter metrics"""
        cache_hit_rate = (
            self.cache_hits / max(self.cache_hits + self.cache_misses, 1)
        )
        
        return {
            'adapter': self.name,
            'request_count': self.request_count,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': cache_hit_rate
        }
    
    async def close(self):
        """Clean up resources"""
        await self.http_client.close()
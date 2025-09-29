"""Cost control and rate limiting for AI API usage."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Dict, Optional

from hive_cache import CacheClient
from hive_logging import get_logger

logger = get_logger(__name__)


class ModelPricing(Enum):
    """Pricing per 1K tokens for different models."""

    GPT_4 = 0.03  # $0.03 per 1K tokens
    GPT_4_32K = 0.06  # $0.06 per 1K tokens
    GPT_35_TURBO = 0.002  # $0.002 per 1K tokens
    GPT_35_TURBO_16K = 0.003  # $0.003 per 1K tokens
    EMBEDDING = 0.0001  # $0.0001 per 1K tokens


@dataclass
class CostTracker:
    """Tracks AI API costs and usage."""

    daily_limit: float = 100.0  # $100 per day
    monthly_limit: float = 2000.0  # $2000 per month
    per_review_limit: float = 1.0  # $1 per review

    daily_usage: float = field(default_factory=float)
    monthly_usage: float = field(default_factory=float)
    usage_history: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=10000))

    _last_reset_daily: datetime = field(default_factory=datetime.now)
    _last_reset_monthly: datetime = field(default_factory=datetime.now)
    _cache: Optional[CacheClient] = field(default=None, init=False)

    def __post_init__(self):
        """Initialize cache for persistence."""
        self._cache = CacheClient(ttl_seconds=86400)  # 24 hour TTL
        self._load_from_cache()

    def _load_from_cache(self) -> None:
        """Load usage data from cache."""
        try:
            cached_data = self._cache.get("cost_tracker")
            if cached_data:
                self.daily_usage = cached_data.get("daily_usage", 0.0)
                self.monthly_usage = cached_data.get("monthly_usage", 0.0)
                self._last_reset_daily = datetime.fromisoformat(
                    cached_data.get("last_reset_daily", datetime.now().isoformat())
                )
                self._last_reset_monthly = datetime.fromisoformat(
                    cached_data.get("last_reset_monthly", datetime.now().isoformat())
                )
        except Exception as e:
            logger.warning(f"Failed to load cost tracker from cache: {e}")

    def _save_to_cache(self) -> None:
        """Save usage data to cache."""
        try:
            self._cache.set(
                "cost_tracker",
                {
                    "daily_usage": self.daily_usage,
                    "monthly_usage": self.monthly_usage,
                    "last_reset_daily": self._last_reset_daily.isoformat(),
                    "last_reset_monthly": self._last_reset_monthly.isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to save cost tracker to cache: {e}")

    def _check_and_reset_limits(self) -> None:
        """Check if limits need to be reset based on time."""
        now = datetime.now()

        # Reset daily limit
        if (now - self._last_reset_daily).days >= 1:
            logger.info(f"Resetting daily usage. Previous: ${self.daily_usage:.2f}")
            self.daily_usage = 0.0
            self._last_reset_daily = now

        # Reset monthly limit
        if (now - self._last_reset_monthly).days >= 30:
            logger.info(f"Resetting monthly usage. Previous: ${self.monthly_usage:.2f}")
            self.monthly_usage = 0.0
            self._last_reset_monthly = now

    def calculate_cost(self, model: str, tokens: int) -> float:
        """Calculate cost for token usage."""
        pricing_map = {
            "gpt-4": ModelPricing.GPT_4,
            "gpt-4-32k": ModelPricing.GPT_4_32K,
            "gpt-3.5-turbo": ModelPricing.GPT_35_TURBO,
            "gpt-3.5-turbo-16k": ModelPricing.GPT_35_TURBO_16K,
            "text-embedding-ada-002": ModelPricing.EMBEDDING,
        }

        model_pricing = pricing_map.get(model.lower(), ModelPricing.GPT_35_TURBO)
        cost = (tokens / 1000) * model_pricing.value

        return cost

    def can_proceed(self, estimated_tokens: int, model: str) -> tuple[bool, str]:
        """Check if request can proceed within budget limits."""
        self._check_and_reset_limits()

        estimated_cost = self.calculate_cost(model, estimated_tokens)

        # Check per-review limit
        if estimated_cost > self.per_review_limit:
            return False, f"Estimated cost ${estimated_cost:.2f} exceeds per-review limit ${self.per_review_limit:.2f}"

        # Check daily limit
        if self.daily_usage + estimated_cost > self.daily_limit:
            return False, f"Daily limit ${self.daily_limit:.2f} would be exceeded (current: ${self.daily_usage:.2f})"

        # Check monthly limit
        if self.monthly_usage + estimated_cost > self.monthly_limit:
            return (
                False,
                f"Monthly limit ${self.monthly_limit:.2f} would be exceeded (current: ${self.monthly_usage:.2f})",
            )

        return True, "OK"

    def record_usage(self, model: str, tokens: int, file_path: Optional[str] = None) -> None:
        """Record actual token usage."""
        cost = self.calculate_cost(model, tokens)

        self.daily_usage += cost
        self.monthly_usage += cost

        # Record in history
        self.usage_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "tokens": tokens,
                "cost": cost,
                "file_path": file_path,
            }
        )

        # Save to cache
        self._save_to_cache()

        logger.info(f"Recorded usage: {tokens} tokens (${cost:.4f}) for {model}. Daily total: ${self.daily_usage:.2f}")

    def get_usage_report(self) -> Dict[str, Any]:
        """Get current usage report."""
        self._check_and_reset_limits()

        return {
            "daily": {
                "usage": self.daily_usage,
                "limit": self.daily_limit,
                "remaining": self.daily_limit - self.daily_usage,
                "percentage": (self.daily_usage / self.daily_limit * 100) if self.daily_limit > 0 else 0,
            },
            "monthly": {
                "usage": self.monthly_usage,
                "limit": self.monthly_limit,
                "remaining": self.monthly_limit - self.monthly_usage,
                "percentage": (self.monthly_usage / self.monthly_limit * 100) if self.monthly_limit > 0 else 0,
            },
            "recent_requests": list(self.usage_history)[-10:],  # Last 10 requests
        }


@dataclass
class RateLimiter:
    """Rate limiter for API requests."""

    max_requests_per_minute: int = 20
    max_requests_per_hour: int = 100
    max_concurrent_requests: int = 5

    _minute_window: Deque[float] = field(default_factory=lambda: deque())
    _hour_window: Deque[float] = field(default_factory=lambda: deque())
    _semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self):
        """Initialize semaphore for concurrent requests."""
        self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)

    def _clean_windows(self) -> None:
        """Remove expired timestamps from windows."""
        now = time.time()

        # Clean minute window (60 seconds)
        while self._minute_window and now - self._minute_window[0] > 60:
            self._minute_window.popleft()

        # Clean hour window (3600 seconds)
        while self._hour_window and now - self._hour_window[0] > 3600:
            self._hour_window.popleft()

    async def acquire(self) -> bool:
        """Acquire rate limit permission."""
        self._clean_windows()

        # Check minute limit
        if len(self._minute_window) >= self.max_requests_per_minute:
            wait_time = 60 - (time.time() - self._minute_window[0])
            if wait_time > 0:
                logger.warning(f"Rate limit: minute limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                return await self.acquire()  # Retry after wait

        # Check hour limit
        if len(self._hour_window) >= self.max_requests_per_hour:
            wait_time = 3600 - (time.time() - self._hour_window[0])
            if wait_time > 0:
                logger.warning(f"Rate limit: hour limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(min(wait_time, 300))  # Max 5 minute wait
                return False  # Don't retry for hour limit

        # Record request
        now = time.time()
        self._minute_window.append(now)
        self._hour_window.append(now)

        return True

    async def __aenter__(self):
        """Async context manager entry."""
        await self._semaphore.acquire()
        success = await self.acquire()
        if not success:
            self._semaphore.release()
            raise Exception("Rate limit exceeded")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self._semaphore.release()


class ReviewSizeLimiter:
    """Limits the size of reviews to control costs."""

    def __init__(
        self,
        max_file_size_mb: float = 1.0,
        max_files_per_review: int = 50,
        max_lines_per_file: int = 5000,
        max_total_lines: int = 20000,
    ):
        """Initialize size limiter."""
        self.max_file_size_mb = max_file_size_mb
        self.max_files_per_review = max_files_per_review
        self.max_lines_per_file = max_lines_per_file
        self.max_total_lines = max_total_lines

    def check_file(self, file_path: Path) -> tuple[bool, str]:
        """Check if file is within size limits."""
        if not file_path.exists():
            return False, "File does not exist"

        # Check file size
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            return False, f"File too large: {size_mb:.2f}MB > {self.max_file_size_mb}MB"

        # Check line count
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                line_count = sum(1 for _ in f)

            if line_count > self.max_lines_per_file:
                return False, f"Too many lines: {line_count} > {self.max_lines_per_file}"
        except Exception as e:
            return False, f"Error reading file: {e}"

        return True, "OK"

    def check_review(self, files: list[Path]) -> tuple[bool, str]:
        """Check if review is within size limits."""
        if len(files) > self.max_files_per_review:
            return False, f"Too many files: {len(files)} > {self.max_files_per_review}"

        total_lines = 0
        for file_path in files:
            if file_path.exists():
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        total_lines += sum(1 for _ in f)
                except (OSError, UnicodeDecodeError):
                    # Skip files that can't be read
                    pass

        if total_lines > self.max_total_lines:
            return False, f"Too many total lines: {total_lines} > {self.max_total_lines}"

        return True, "OK"


class CostControlManager:
    """Manages all cost control mechanisms."""

    def __init__(
        self,
        daily_limit: float = 100.0,
        monthly_limit: float = 2000.0,
        per_review_limit: float = 1.0,
    ):
        """Initialize cost control manager."""
        self.cost_tracker = CostTracker(
            daily_limit=daily_limit,
            monthly_limit=monthly_limit,
            per_review_limit=per_review_limit,
        )
        self.rate_limiter = RateLimiter()
        self.size_limiter = ReviewSizeLimiter()

        logger.info(f"CostControlManager initialized with daily limit ${daily_limit:.2f}")

    async def pre_request_check(
        self,
        estimated_tokens: int,
        model: str,
        files: Optional[list[Path]] = None,
    ) -> tuple[bool, str]:
        """Check all limits before making a request."""
        # Check cost limits
        can_proceed, reason = self.cost_tracker.can_proceed(estimated_tokens, model)
        if not can_proceed:
            return False, reason

        # Check file size limits if files provided
        if files:
            can_proceed, reason = self.size_limiter.check_review(files)
            if not can_proceed:
                return False, reason

        return True, "All checks passed"

    def record_usage(self, model: str, tokens: int, file_path: Optional[str] = None) -> None:
        """Record actual usage after request."""
        self.cost_tracker.record_usage(model, tokens, file_path)

    def get_status(self) -> Dict[str, Any]:
        """Get current cost control status."""
        return {
            "usage": self.cost_tracker.get_usage_report(),
            "limits": {
                "daily": self.cost_tracker.daily_limit,
                "monthly": self.cost_tracker.monthly_limit,
                "per_review": self.cost_tracker.per_review_limit,
                "max_files": self.size_limiter.max_files_per_review,
                "max_file_size_mb": self.size_limiter.max_file_size_mb,
            },
        }

"""
Céal: Abstract Scraper Framework

This module defines the base scraper that all source-specific scrapers
inherit from. It provides:

  1. Managed aiohttp.ClientSession with connection pooling
  2. Semaphore-based concurrency control (rate limiting)
  3. Exponential backoff retries via tenacity
  4. User-Agent rotation for basic stealth
  5. Request metrics for observability
  6. Structured logging on every request

Architecture — why it's built this way:

  "Adding a new data source (Glassdoor, Google Jobs, a paid API) is a
  single class that implements two methods: `scrape_jobs()` and
  `parse_listing()`. The base class handles all the HTTP plumbing,
  rate limiting, and retry logic. This is the Template Method pattern —
  the framework defines the skeleton, subclasses fill in the details."

  This is the exact answer to "How would you extend this system?"
  in a Google L5 or Stripe interview.

Interview vocabulary this file earns you:
  - Template Method Pattern (GoF design pattern)
  - Connection Pooling (aiohttp.TCPConnector)
  - Semaphore-based Rate Limiting (asyncio.Semaphore)
  - Exponential Backoff with Jitter (tenacity)
  - Async Context Manager Protocol (__aenter__ / __aexit__)
"""

from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
import structlog

from src.models.entities import RawJobListing

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# User-Agent Pool
# ---------------------------------------------------------------------------
# Why rotate? LinkedIn/Indeed block requests with the default aiohttp UA.
# A pool of real browser UAs makes us look like organic traffic.
# In an interview: "I implemented UA rotation as a basic anti-detection
# measure. For production, I'd add proxy rotation and request fingerprint
# randomization, but this was sufficient for the data volume I needed."

USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


# ---------------------------------------------------------------------------
# Scrape Metrics — tracks per-run performance
# ---------------------------------------------------------------------------

@dataclass
class ScrapeMetrics:
    """
    Operational metrics collected during a scrape run.
    Fed into scrape_log table for observability.

    Interview point: "Every scrape run produces a metrics object that
    records success rate, error breakdown, and latency. I can tell you
    the p50 response time and retry rate for any historical run."
    """
    requests_made: int = 0
    requests_succeeded: int = 0
    requests_failed: int = 0
    retries: int = 0
    jobs_found: int = 0
    jobs_parsed: int = 0
    parse_errors: int = 0
    start_time: float = field(default_factory=time.monotonic)
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return round(time.monotonic() - self.start_time, 2)

    @property
    def success_rate(self) -> float:
        if self.requests_made == 0:
            return 0.0
        return round(self.requests_succeeded / self.requests_made, 3)

    def to_dict(self) -> dict:
        return {
            "requests_made": self.requests_made,
            "requests_succeeded": self.requests_succeeded,
            "requests_failed": self.requests_failed,
            "retries": self.retries,
            "jobs_found": self.jobs_found,
            "jobs_parsed": self.jobs_parsed,
            "parse_errors": self.parse_errors,
            "duration_seconds": self.duration_seconds,
            "success_rate": self.success_rate,
        }


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class ScraperError(Exception):
    """Base exception for scraper errors."""


class RateLimitError(ScraperError):
    """Raised when we receive HTTP 429 Too Many Requests."""

    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limited. Retry after: {retry_after}s"
            if retry_after
            else "Rate limited."
        )


class BlockedError(ScraperError):
    """Raised when the target detects us as a bot (403, CAPTCHA, etc.)."""


# ---------------------------------------------------------------------------
# Abstract Base Scraper
# ---------------------------------------------------------------------------

class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.

    Implements the Template Method pattern:
      - The base class handles HTTP mechanics (session, retries, rate limiting)
      - Subclasses implement `scrape_jobs()` and `parse_listing()`

    Usage:
        async with LinkedInScraper(concurrency=5) as scraper:
            jobs = await scraper.scrape_jobs("Technical Solutions Engineer", "Boston, MA")

    Interview point: "The scraper uses the async context manager protocol
    so the aiohttp session lifecycle is deterministic. Connection pooling
    is handled by TCPConnector with a configurable limit. The semaphore
    ensures we never exceed N concurrent requests regardless of how many
    coroutines are awaiting."
    """

    # Subclasses set this to identify the source
    SOURCE_NAME: str = "base"

    def __init__(
        self,
        concurrency: int = 5,
        request_delay: float = 1.0,
        max_retries: int = 3,
        timeout_seconds: int = 30,
    ):
        """
        Args:
            concurrency: Max concurrent HTTP requests (semaphore limit).
            request_delay: Min seconds between requests (politeness delay).
            max_retries: Max retry attempts on transient failures.
            timeout_seconds: Per-request timeout.
        """
        self.concurrency = concurrency
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

        self._semaphore = asyncio.Semaphore(concurrency)
        self._session: Optional[aiohttp.ClientSession] = None
        self._metrics = ScrapeMetrics()

    # -------------------------------------------------------------------
    # Async Context Manager — session lifecycle
    # -------------------------------------------------------------------

    async def __aenter__(self) -> "BaseScraper":
        """
        Create the aiohttp session with connection pooling.

        TCPConnector params:
          - limit: total connection pool size (matches concurrency)
          - limit_per_host: per-host limit (prevents hammering one server)
          - ttl_dns_cache: cache DNS lookups for 5 minutes
          - force_close: False = keep-alive connections (reuse TCP handshakes)

        Interview point: "I configured the connector to match the semaphore
        limit so there's a 1:1 mapping between concurrency slots and pooled
        connections. This prevents connection starvation."
        """
        connector = aiohttp.TCPConnector(
            limit=self.concurrency * 2,        # headroom for redirects
            limit_per_host=self.concurrency,   # never exceed semaphore
            ttl_dns_cache=300,                 # 5 min DNS cache
            force_close=False,                 # keep-alive
        )

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        self._metrics = ScrapeMetrics()

        logger.info(
            "scraper_session_started",
            source=self.SOURCE_NAME,
            concurrency=self.concurrency,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close the session and log final metrics."""
        if self._session:
            await self._session.close()
            # Allow time for SSL connections to close gracefully
            await asyncio.sleep(0.25)

        logger.info(
            "scraper_session_closed",
            source=self.SOURCE_NAME,
            **self._metrics.to_dict(),
        )
        return None  # Don't suppress exceptions

    # -------------------------------------------------------------------
    # HTTP Request — the core fetch with rate limiting + retries
    # -------------------------------------------------------------------

    async def fetch(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> str:
        """
        Fetch a URL with rate limiting, retries, and metrics.

        Flow:
          1. Acquire semaphore slot (blocks if at concurrency limit)
          2. Apply politeness delay (jittered to avoid thundering herd)
          3. Send request with rotated User-Agent
          4. Handle response codes (429 → RateLimitError, 403 → BlockedError)
          5. Return response body as text
          6. Release semaphore slot (even on failure)

        Retries are handled by the @retry decorator from tenacity:
          - Retries on: 5xx errors, timeouts, connection errors
          - Does NOT retry on: 429 (handled by caller), 403, 404
          - Strategy: exponential backoff with jitter (1s → 2s → 4s + random)
        """
        if not self._session:
            raise ScraperError("Session not initialized. Use 'async with' context manager.")

        async with self._semaphore:
            return await self._fetch_with_retry(url, params, headers)

    @retry(
        retry=retry_if_exception_type((aiohttp.ServerTimeoutError, aiohttp.ClientError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
        before_sleep=lambda retry_state: logger.warning(
            "scraper_retry",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep if retry_state.next_action else 0,
        ),
    )
    async def _fetch_with_retry(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> str:
        """
        Internal fetch with tenacity retry decorator.

        Why separate from fetch()? The semaphore must wrap the entire
        retry sequence — if we put @retry on fetch(), each retry attempt
        would re-acquire the semaphore, potentially deadlocking.
        """
        # Politeness delay with jitter (±30%)
        jitter = self.request_delay * random.uniform(0.7, 1.3)
        await asyncio.sleep(jitter)

        # Build headers with rotated User-Agent
        request_headers = {"User-Agent": random.choice(USER_AGENTS)}
        if headers:
            request_headers.update(headers)

        self._metrics.requests_made += 1

        try:
            async with self._session.get(
                url,
                params=params,
                headers=request_headers,
                allow_redirects=True,
            ) as response:
                # Handle error status codes
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After")
                    self._metrics.requests_failed += 1
                    raise RateLimitError(
                        retry_after=int(retry_after) if retry_after else None
                    )

                if response.status == 403:
                    self._metrics.requests_failed += 1
                    raise BlockedError(
                        f"Blocked by {url} (HTTP 403). "
                        "May need proxy rotation or different approach."
                    )

                if response.status >= 500:
                    self._metrics.requests_failed += 1
                    # Raise a generic client error so tenacity retries it
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"Server error {response.status}",
                    )

                if response.status == 404:
                    self._metrics.requests_failed += 1
                    logger.warning("scraper_404", url=url)
                    return ""

                response.raise_for_status()
                self._metrics.requests_succeeded += 1

                text = await response.text()

                logger.debug(
                    "scraper_fetch_ok",
                    url=url[:80],
                    status=response.status,
                    size=len(text),
                )
                return text

        except (RateLimitError, BlockedError):
            raise  # Don't wrap these — they have specific handling

        except aiohttp.ClientError:
            self._metrics.requests_failed += 1
            raise  # Let tenacity handle the retry

    # -------------------------------------------------------------------
    # Abstract methods — subclasses implement these
    # -------------------------------------------------------------------

    @abstractmethod
    async def scrape_jobs(
        self,
        query: str,
        location: str,
        max_results: int = 100,
    ) -> list[RawJobListing]:
        """
        Scrape job listings for the given query and location.

        Args:
            query: Job title or keywords (e.g., "Technical Solutions Engineer")
            location: City/region (e.g., "Boston, MA")
            max_results: Maximum listings to fetch

        Returns:
            List of RawJobListing Pydantic models ready for the normalizer.
        """
        ...

    @abstractmethod
    def parse_listing(self, raw_html: str) -> Optional[RawJobListing]:
        """
        Parse a single job listing from raw HTML/JSON.

        Returns None if the listing can't be parsed (bad data, not a job, etc.)
        The caller handles the None — this keeps parse logic clean.
        """
        ...

    # -------------------------------------------------------------------
    # Utility methods available to all scrapers
    # -------------------------------------------------------------------

    @property
    def metrics(self) -> ScrapeMetrics:
        """Access current metrics for this scrape run."""
        return self._metrics

    async def fetch_many(
        self,
        urls: list[str],
        params: Optional[dict] = None,
    ) -> list[tuple[str, str]]:
        """
        Fetch multiple URLs concurrently (respecting the semaphore).

        Returns list of (url, response_text) tuples.
        Failed requests return (url, "").

        Interview point: "fetch_many fires all requests concurrently
        via asyncio.gather, but the semaphore ensures only N are in-flight
        at any time. This is how you get async throughput without
        overwhelming the target server."
        """
        async def _safe_fetch(url: str) -> tuple[str, str]:
            try:
                text = await self.fetch(url, params=params)
                return (url, text)
            except Exception as e:
                # Catch broadly — tenacity wraps failures in RetryError,
                # and we want fetch_many to be resilient to ANY failure.
                self._metrics.errors.append(f"{url}: {e}")
                return (url, "")

        results = await asyncio.gather(
            *[_safe_fetch(u) for u in urls],
            return_exceptions=False,
        )
        return results

"""
Céal: LinkedIn Job Scraper

Scrapes LinkedIn's public guest job search endpoint to find listings
matching a query and location. Uses the guest API which returns HTML
fragments — no authentication required.

Architecture:
  1. Hit the search endpoint with pagination (25 results per page)
  2. Parse each result card into a RawJobListing
  3. Optionally fetch full job descriptions via the detail endpoint
  4. Return validated Pydantic models for the normalizer stage

Why LinkedIn Guest API?
  LinkedIn has two paths to job data:
  - Authenticated API (LinkedIn API Partners) → requires business agreement
  - Guest job search → public, no auth, returns HTML fragments
  We use the guest path because it's publicly accessible and sufficient
  for Phase 1. The architecture is designed so swapping in an official
  API later only requires changing this one file.

Interview point: "I chose the public guest endpoint over the authenticated
API because it was sufficient for my data volume and avoided API key
management complexity. The scraper is behind an abstract interface, so
migrating to an official API is a single-class swap."
"""

from __future__ import annotations

import re

import structlog
from bs4 import BeautifulSoup

from src.models.entities import JobSource, RawJobListing, RemoteType
from src.scrapers.base import BaseScraper, BlockedError, RateLimitError

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# LinkedIn guest job search — returns HTML fragments with job cards
SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

# LinkedIn guest job detail — returns full description HTML
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

# Results per page (LinkedIn's fixed page size)
PAGE_SIZE = 25


class LinkedInScraper(BaseScraper):
    """
    LinkedIn job scraper using the public guest search endpoint.

    Usage:
        async with LinkedInScraper(concurrency=3) as scraper:
            jobs = await scraper.scrape_jobs(
                query="Technical Solutions Engineer",
                location="Boston, MA",
                max_results=50,
            )
    """

    SOURCE_NAME = "linkedin"

    def __init__(
        self,
        concurrency: int = 3,
        request_delay: float = 2.0,
        fetch_descriptions: bool = True,
        **kwargs,
    ):
        """
        Args:
            concurrency: Max concurrent requests. LinkedIn is sensitive —
                         keep this low (3-5). Higher risks 429s.
            request_delay: Min seconds between requests. 2s is polite.
            fetch_descriptions: Whether to fetch full job descriptions
                                (slower but needed for skill extraction).
        """
        super().__init__(
            concurrency=concurrency,
            request_delay=request_delay,
            **kwargs,
        )
        self.fetch_descriptions = fetch_descriptions

    # -------------------------------------------------------------------
    # Main scrape method
    # -------------------------------------------------------------------

    async def scrape_jobs(
        self,
        query: str,
        location: str,
        max_results: int = 100,
    ) -> list[RawJobListing]:
        """
        Scrape LinkedIn for jobs matching the query and location.

        Pagination: LinkedIn returns 25 results per page. We iterate
        through pages until we hit max_results or run out of listings.

        Flow:
          1. Build search URL with query params
          2. Fetch page of results (25 job cards)
          3. Parse each card into RawJobListing
          4. Optionally fetch full descriptions in parallel
          5. Continue until max_results reached or no more pages
        """
        jobs: list[RawJobListing] = []
        start = 0
        pages_fetched = 0

        logger.info(
            "linkedin_scrape_started",
            query=query,
            location=location,
            max_results=max_results,
        )

        while len(jobs) < max_results:
            # Build search parameters
            params = {
                "keywords": query,
                "location": location,
                "start": str(start),
                "f_TPR": "r604800",      # Last 7 days (fresh listings)
                "position": "1",
                "pageNum": "0",
            }

            try:
                html = await self.fetch(SEARCH_URL, params=params)
            except RateLimitError as e:
                logger.warning(
                    "linkedin_rate_limited",
                    page=pages_fetched,
                    jobs_so_far=len(jobs),
                    retry_after=e.retry_after,
                )
                break  # Stop gracefully, return what we have
            except BlockedError:
                logger.error(
                    "linkedin_blocked",
                    page=pages_fetched,
                    jobs_so_far=len(jobs),
                )
                break

            if not html or len(html.strip()) < 100:
                logger.info(
                    "linkedin_no_more_results",
                    page=pages_fetched,
                    total_jobs=len(jobs),
                )
                break

            # Parse the search results page
            page_jobs = self._parse_search_results(html)

            if not page_jobs:
                logger.info(
                    "linkedin_empty_page",
                    page=pages_fetched,
                    start=start,
                )
                break

            self._metrics.jobs_found += len(page_jobs)
            pages_fetched += 1

            # Optionally fetch full descriptions for each job
            if self.fetch_descriptions:
                page_jobs = await self._enrich_with_descriptions(page_jobs)

            jobs.extend(page_jobs)
            start += PAGE_SIZE

            logger.info(
                "linkedin_page_scraped",
                page=pages_fetched,
                jobs_on_page=len(page_jobs),
                total_jobs=len(jobs),
            )

        # Trim to max_results
        jobs = jobs[:max_results]
        self._metrics.jobs_parsed = len(jobs)

        logger.info(
            "linkedin_scrape_complete",
            total_jobs=len(jobs),
            pages=pages_fetched,
            **self._metrics.to_dict(),
        )

        return jobs

    # -------------------------------------------------------------------
    # Search result parsing
    # -------------------------------------------------------------------

    def _parse_search_results(self, html: str) -> list[RawJobListing]:
        """
        Parse a page of LinkedIn search results into RawJobListing objects.

        Each result is a <li> containing a job card with structured data.
        We extract what we can from the card and optionally fetch the
        full description separately.
        """
        soup = BeautifulSoup(html, "lxml")
        job_cards = soup.find_all("li")

        results: list[RawJobListing] = []

        for card in job_cards:
            try:
                parsed = self.parse_listing(str(card))
                if parsed:
                    results.append(parsed)
            except Exception as exc:
                self._metrics.parse_errors += 1
                logger.warning(
                    "linkedin_parse_error",
                    error=str(exc)[:200],
                )

        return results

    # -------------------------------------------------------------------
    # Single listing parser (implements abstract method)
    # -------------------------------------------------------------------

    def parse_listing(self, raw_html: str) -> RawJobListing | None:
        """
        Parse a single LinkedIn job card HTML into a RawJobListing.

        LinkedIn job cards contain:
          - data-entity-urn: unique job ID (e.g., "urn:li:jobPosting:3847291")
          - Title in an <a> tag with class "base-card__full-link"
          - Company in <h4> with class "base-search-card__subtitle"
          - Location in <span> with class "job-search-card__location"
          - URL in the <a> href

        Returns None if essential fields are missing (defensive parsing).
        """
        soup = BeautifulSoup(raw_html, "lxml")

        # Extract job ID from data-entity-urn attribute
        entity_urn = soup.find(attrs={"data-entity-urn": True})
        if not entity_urn:
            return None

        urn = entity_urn.get("data-entity-urn", "")
        # Extract numeric ID from "urn:li:jobPosting:3847291"
        job_id = urn.split(":")[-1] if ":" in urn else ""
        if not job_id:
            return None

        # Title
        title_elem = soup.find("a", class_=re.compile(r"base-card__full-link"))
        if not title_elem:
            # Fallback: try sr-only span
            title_elem = soup.find("span", class_="sr-only")
        title = title_elem.get_text(strip=True) if title_elem else None

        if not title:
            return None

        # Company name
        company_elem = soup.find("h4", class_=re.compile(r"base-search-card__subtitle"))
        if not company_elem:
            company_elem = soup.find("a", class_=re.compile(r"hidden-nested-link"))
        company = company_elem.get_text(strip=True) if company_elem else "Unknown"

        # URL
        url_elem = soup.find("a", class_=re.compile(r"base-card__full-link"))
        url = url_elem.get("href", "").split("?")[0] if url_elem else ""
        if not url:
            url = f"https://www.linkedin.com/jobs/view/{job_id}"

        # Ensure URL is absolute
        if url and not url.startswith("http"):
            url = "https://www.linkedin.com" + url

        # Location
        location_elem = soup.find("span", class_=re.compile(r"job-search-card__location"))
        location = location_elem.get_text(strip=True) if location_elem else None

        # Remote type detection
        remote_type = self._detect_remote_type(title, location)

        # Salary (sometimes shown on cards)
        salary_text = None
        salary_elem = soup.find("span", class_=re.compile(r"job-search-card__salary"))
        if salary_elem:
            salary_text = salary_elem.get_text(strip=True)

        # Posted date
        date_elem = soup.find("time")
        date_elem.get("datetime", "") if date_elem else None

        return RawJobListing(
            external_id=job_id,
            source=JobSource.LINKEDIN,
            title=title,
            company_name=company,
            url=url,
            location=location,
            remote_type=remote_type,
            salary_text=salary_text,
        )

    # -------------------------------------------------------------------
    # Description enrichment
    # -------------------------------------------------------------------

    async def _enrich_with_descriptions(
        self,
        jobs: list[RawJobListing],
    ) -> list[RawJobListing]:
        """
        Fetch full job descriptions for a batch of listings.

        Uses fetch_many() for concurrent fetching (bounded by semaphore).
        Jobs that fail to fetch keep their existing data (graceful degradation).

        Interview point: "Description fetching is a separate, optional stage.
        If it fails for some jobs, we still have the card-level data. This is
        graceful degradation — the pipeline continues with partial data rather
        than failing entirely."
        """
        urls = [
            DETAIL_URL.format(job_id=job.external_id)
            for job in jobs
        ]

        results = await self.fetch_many(urls)

        # Map URL → response text for quick lookup
        url_to_html = {url: html for url, html in results}

        enriched: list[RawJobListing] = []
        for job in jobs:
            detail_url = DETAIL_URL.format(job_id=job.external_id)
            detail_html = url_to_html.get(detail_url, "")

            if detail_html:
                description = self._extract_description(detail_html)
                if description:
                    # Create a new RawJobListing with the description added
                    job = job.model_copy(
                        update={"description_raw": description}
                    )

            enriched.append(job)

        return enriched

    def _extract_description(self, html: str) -> str | None:
        """
        Extract the job description text from a LinkedIn job detail page.

        The description lives in a <div> with class "description__text".
        We extract the text content, preserving paragraph breaks.
        """
        soup = BeautifulSoup(html, "lxml")

        desc_div = soup.find("div", class_=re.compile(r"description__text"))
        if not desc_div:
            # Fallback: try the main content section
            desc_div = soup.find("section", class_=re.compile(r"description"))

        if not desc_div:
            return None

        # Get text with newlines for paragraph separation
        return desc_div.get_text(separator="\n", strip=True)

    # -------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------

    @staticmethod
    def _detect_remote_type(
        title: str | None,
        location: str | None,
    ) -> RemoteType:
        """
        Detect remote/hybrid/onsite from title and location strings.

        LinkedIn encodes this in different places depending on the listing.
        We check both title and location for keywords.
        """
        text = f"{title or ''} {location or ''}".lower()

        if "remote" in text:
            return RemoteType.REMOTE
        if "hybrid" in text:
            return RemoteType.HYBRID
        if any(word in text for word in ("on-site", "onsite", "in-office")):
            return RemoteType.ONSITE

        return RemoteType.UNKNOWN

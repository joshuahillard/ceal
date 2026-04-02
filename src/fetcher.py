"""
Ceal Phase 2: URL-to-Text Job Description Fetcher

Fetches a job description from a URL and extracts plain text.
Security: NEVER sends API keys or credentials in requests.
Only fetches from HTTP/HTTPS URLs.
"""
from __future__ import annotations

from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

_USER_AGENT = "Ceal/2.0 (Career Signal Engine)"
_TIMEOUT = 15.0


async def fetch_job_description(url: str) -> str:
    """
    Fetch a job description from a URL and return clean text.

    Args:
        url: HTTP or HTTPS URL to fetch.

    Returns:
        Clean plain text extracted from the HTML page.

    Raises:
        ValueError: If URL scheme is not http or https.
        httpx.HTTPError: If the request fails.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Only http and https URLs are supported, got: {parsed.scheme}"
        )

    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Strip excessive whitespace
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)

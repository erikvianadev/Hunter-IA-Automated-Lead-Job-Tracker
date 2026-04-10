"""
Scraper utility helpers.

Intentionally kept dependency-free (stdlib only + requests) so they can be
imported without side-effects anywhere in the Django project.
"""

import random
import re
import time
from typing import Dict

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

# Rotate through a small pool of realistic User-Agent strings so repeated
# requests look less uniform to basic bot-detection heuristics.
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
]


def build_headers(extra: Dict[str, str] | None = None) -> Dict[str, str]:
    """
    Return a request headers dict with a randomly chosen User-Agent plus
    sensible browser-like defaults.

    Parameters
    ----------
    extra : Optional mapping of additional/override headers.

    Returns
    -------
    Dict[str, str]
    """
    headers: Dict[str, str] = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra:
        headers.update(extra)
    return headers


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------


def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """
    Sleep for a uniformly random duration between *min_seconds* and
    *max_seconds* to reduce the likelihood of rate-limiting.

    Parameters
    ----------
    min_seconds : Lower bound of the delay range (inclusive).
    max_seconds : Upper bound of the delay range (inclusive).
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_text(value: str | None) -> str:
    """
    Strip leading/trailing whitespace and collapse internal runs of
    whitespace characters (including newlines and tabs) to a single space.

    Returns an empty string when *value* is None or blank.

    Parameters
    ----------
    value : Raw text extracted from HTML.
    """
    if not value:
        return ""
    return _WHITESPACE_RE.sub(" ", value).strip()


def extract_text(tag: object, default: str = "") -> str:
    """
    Safely extract ``.get_text()`` from a BS4 Tag (or ``None``).

    Parameters
    ----------
    tag     : A BeautifulSoup Tag, NavigableString, or None.
    default : Value to return when *tag* is None.
    """
    if tag is None:
        return default
    text: str = getattr(tag, "get_text", lambda **_: str(tag))(separator=" ")
    return sanitize_text(text)


def absolute_url(base: str, path: str) -> str:
    """
    Ensure *path* is an absolute URL by prepending *base* when necessary.

    Parameters
    ----------
    base : Root URL of the scraped site, e.g. ``"https://www.example.com"``.
    path : Raw href value which may be relative or already absolute.
    """
    path = path.strip()
    if path.startswith("http"):
        return path
    # urljoin handles leading slashes and relative paths correctly.
    from urllib.parse import urljoin
    return urljoin(base, path)

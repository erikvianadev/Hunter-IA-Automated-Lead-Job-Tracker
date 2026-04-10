"""
Indeed job scraper – undetected_chromedriver + infinite scroll.

Indeed aggressively blocks plain HTTP clients and headless Selenium via
Cloudflare and JS-based bot-detection.  This implementation uses
``undetected_chromedriver`` (which patches Chrome to avoid automation
fingerprinting) combined with an infinite-scroll strategy: instead of
building ``?start=N`` URLs, the page is scrolled down repeatedly and new
job cards are collected as they load dynamically.

URL pattern (initial page only):
    https://www.indeed.com/jobs?q=<query>&l=<location>

Usage
-----
::

    from hunter.scrapers import IndeedScraper

    with IndeedScraper(headless=True) as scraper:
        jobs = scraper.scrape("Python Developer", location="Remote", max_pages=5)

    for job in jobs:
        print(job["title"], "–", job["company"])

Django integration
------------------
Each ``JobResult`` dict contains ``title``, ``company``, ``location``,
``description``, ``link``, and ``source="indeed"``.
``max_pages`` is repurposed as the maximum number of scroll iterations.
"""

import logging
from os import link
import random
from pathlib import Path
import time
from typing import List, Optional
from urllib.parse import quote_plus

import undetected_chromedriver as uc
from bs4 import BeautifulSoup, Tag
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .base import BaseScraper, JobResult
from .utils import absolute_url, extract_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RESULTS_PER_PAGE = 10  # kept for _build_search_url offset math

_USER_AGENTS: List[str] = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
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

# CSS selectors for job cards, ordered from most to least reliable.
_CARD_SELECTORS: List[str] = [
    "div.job_seen_beacon",
    "div[data-jk]",
    "a[data-jk]",
    "div[data-testid='slider_item']",
    "div.cardOutline",
    "[data-jk]",
]

# Primary selector used by WebDriverWait (fast, reliable).
_WAIT_SELECTOR: str = "div.job_seen_beacon, div[data-jk], a[data-jk]"

# Keywords in the page <title> that indicate a block or challenge page.
_BLOCK_TITLE_KEYWORDS: tuple = (
    "sign in",
    "log in",
    "login",
    "cloudflare",
    "access denied",
    "403 forbidden",
    "just a moment",
    "security check",
    "captcha",
    "are you a human",
    "robot",
    "verify",
)

# URL fragments that indicate an auth redirect or challenge redirect.
_BLOCK_URL_PATTERNS: tuple = (
    "/account/login",
    "/account/signin",
    "auth.indeed.com",
    "challenge",
    "/login",
)


class IndeedScraper(BaseScraper):
    """
    Indeed job scraper powered by ``undetected_chromedriver`` and infinite scroll.

    Instead of navigating paginated ``?start=N`` URLs, this scraper loads the
    first search-results page and scrolls down to trigger dynamic loading until
    no new job cards appear or ``max_pages`` scroll rounds are exhausted.

    Parameters
    ----------
    headless : bool
        Run Chrome without a visible window (default: ``True``).
    fetch_descriptions : bool
        When ``True``, visit each job's page to extract the full description.
        Significantly slower. Default: ``False``.
    debug : bool
        When ``True``, save the final page HTML to ``debug_indeed.html`` in
        the working directory for inspection. Default: ``False``.
    **kwargs
        Forwarded to :class:`BaseScraper` (``timeout``, ``min_delay``,
        ``max_delay``, ``max_retries``).
    """

    base_url = "https://www.indeed.com"

    def __init__(
        self,
        headless: bool = True,
        fetch_descriptions: bool = False,
        debug: bool = False,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.headless = headless
        self.fetch_descriptions = fetch_descriptions
        self.debug = debug
        self._driver: Optional[uc.Chrome] = None

    # ------------------------------------------------------------------
    # Public API – fully overrides BaseScraper.scrape()
    # ------------------------------------------------------------------

    def scrape(
        self,
        query: str,
        location: str = "",
        max_pages: int = 5,
    ) -> List[JobResult]:
        """
        Scrape Indeed and return a normalised list of job dicts.

        ``max_pages`` controls the maximum number of scroll iterations rather
        than the number of paginated URLs.  Each scroll round may surface
        ~10 new cards, so ``max_pages=5`` yields up to ~50 results.

        Parameters
        ----------
        query     : Search keywords, e.g. ``"Python Developer"``.
        location  : Location filter, e.g. ``"Remote"`` or ``"New York"``.
        max_pages : Maximum scroll rounds (default 5).

        Returns
        -------
        List[JobResult]
            Each dict: ``title``, ``company``, ``location``, ``description``,
            ``link``, ``source="indeed"``.
        """
        logger.info(
            "IndeedScraper.scrape started  query=%r  location=%r  max_scrolls=%d",
            query,
            location,
            max_pages,
        )

        self._setup_driver()
        results: List[JobResult] = []

        try:
            url = self._build_search_url(query, location, page=1)
            results = self._scrape_page(url, max_scrolls=max_pages)
        finally:
            self._teardown_driver()

        logger.info(
            "IndeedScraper.scrape finished  total_results=%d",
            len(results),
        )
        return results

    def close(self) -> None:
        """Quit the Chrome driver and release the HTTP session."""
        self._teardown_driver()
        super().close()

    # ------------------------------------------------------------------
    # Driver lifecycle
    # ------------------------------------------------------------------

    def _setup_driver(self) -> None:
        if self._driver is not None:
            return

        options = uc.ChromeOptions()

        if self.headless:
            options.add_argument("--headless=new")

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # IMPORTANTE: remover profile fixo
        # options.add_argument("--user-data-dir=./chrome_profile")  ← REMOVE

        # random user agent
        options.add_argument(f"--user-agent={random.choice(_USER_AGENTS)}")

        options.add_argument("--start-maximized")

        self._driver = uc.Chrome(
            options=options,
            use_subprocess=True
        )

        # esconder webdriver
        self._driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
                """
            },
        )

        logger.debug("Chrome anti-bot driver initialized")

    def _teardown_driver(self) -> None:
        """
        Gracefully quit the Chrome driver and nullify the reference.

        Guaranteed to complete even if ``quit()`` raises an exception, ensuring
        the browser process is not left orphaned.
        """
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Error quitting Chrome driver: %s", exc)
            finally:
                self._driver = None
            logger.debug("Chrome driver closed.")

    # ------------------------------------------------------------------
    # Page scraping with infinite scroll
    # ------------------------------------------------------------------

    def _scrape_page(self, url: str, max_scrolls: int) -> List[JobResult]:
        assert self._driver is not None

        # abrir homepage primeiro
        self._driver.get("https://www.indeed.com/")
        time.sleep(random.uniform(3, 5))

        # mover mouse (simula humano)
        from selenium.webdriver import ActionChains
        actions = ActionChains(self._driver)
        actions.move_by_offset(300, 300).perform()
        time.sleep(random.uniform(1, 2))

        # agora sim pesquisar
        self._driver.get(url)
        time.sleep(random.uniform(3, 5))

        # AGUARDAR JOB CARDS
        try:
            WebDriverWait(self._driver, self.timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, _WAIT_SELECTOR)
                )
            )
        except TimeoutException:
            logger.warning("Indeed carregou mas nenhum job card encontrado.")
            if self.debug:
                self._save_debug_html()
            return []

        logger.debug("Initial job cards found – starting scroll loop.")
        self._do_scroll_loading(max_scrolls)

        # DEBUG HTML
        if self.debug:
            self._save_debug_html()

        # PARSE HTML
        soup = BeautifulSoup(self._driver.page_source, "html.parser")
        raw_cards = self._parse_jobs(soup)
        logger.debug("Raw cards found: %d", len(raw_cards))

        results: List[JobResult] = []

        for raw in raw_cards:
            try:
                job = self._parse_job(raw)

                if job.is_valid():
                    results.append(job)
                else:
                    logger.debug("Skipping incomplete job entry: %s", dict(job))

            except Exception as exc:
                logger.warning("Failed to parse job card: %s", exc)

        logger.info(
            "_scrape_page: %d valid jobs collected after %d scroll rounds.",
            len(results),
            max_scrolls,
        )

        return results
    def _do_scroll_loading(self, max_scrolls: int) -> None:
        assert self._driver is not None

        last_height = self._driver.execute_script(
            "return document.body.scrollHeight"
        )

        for _ in range(max_scrolls):

            # scroll humano
            for _ in range(random.randint(2, 5)):
                self._driver.execute_script(
                    f"window.scrollBy(0, {random.randint(300, 900)});"
                )
                time.sleep(random.uniform(0.6, 1.4))

            # pausa humana
            time.sleep(random.uniform(2, 4))

            new_height = self._driver.execute_script(
                "return document.body.scrollHeight"
            )

            if new_height == last_height:
                break

            last_height = new_height

    # ------------------------------------------------------------------
    # Block / challenge detection
    # ------------------------------------------------------------------

    def _is_blocked(self) -> bool:
        """
        Return ``True`` when the current page is a bot-challenge, login wall,
        or error page.

        Checks both the document ``<title>`` and the current URL against
        well-known patterns produced by Cloudflare, Indeed's WAF, and generic
        auth redirects.
        """
        assert self._driver is not None
        title = self._driver.title.lower()
        current_url = self._driver.current_url.lower()

        if any(kw in title for kw in _BLOCK_TITLE_KEYWORDS):
            logger.warning(
                "Block detected via page title: %r", self._driver.title
            )
            return True

        if any(pattern in current_url for pattern in _BLOCK_URL_PATTERNS):
            logger.warning(
                "Block detected via URL redirect: %s", self._driver.current_url
            )
            return True

        if "captcha" in self._driver.page_source.lower():
            return True
        return False

    # ------------------------------------------------------------------
    # Debug helper
    # ------------------------------------------------------------------

    def _save_debug_html(self) -> None:
        """Write the current page source to ``debug_indeed.html``."""
        assert self._driver is not None
        try:
            path = Path("debug_indeed.html")
            path.write_text(self._driver.page_source, encoding="utf-8")
            logger.info("Debug HTML saved → %s", path.resolve())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not save debug HTML: %s", exc)

    # ------------------------------------------------------------------
    # BaseScraper abstract interface
    # ------------------------------------------------------------------

    def _build_search_url(self, query: str, location: str, page: int) -> str:
        """
        Construct an Indeed search URL.

        The scroll strategy always starts at page 1 so ``offset`` is always 0.
        The ``page`` parameter is preserved to satisfy the abstract interface
        and to allow fallback to offset-based pagination if needed.

        Examples
        --------
        >>> s._build_search_url("Python", "Remote", 1)
        'https://www.indeed.com/jobs?q=Python&l=Remote'
        """
        offset = (page - 1) * _RESULTS_PER_PAGE
        q = quote_plus(query.strip())
        url = f"{self.base_url}/jobs?q={q}"
        if location:
            url += f"&l={quote_plus(location.strip())}"
        if offset:
            url += f"&start={offset}"
        return url

    def _parse_jobs(self, soup: BeautifulSoup) -> List[Tag]:
        """
        Extract job card tags from *soup* using ``_CARD_SELECTORS`` in order.

        Returns the first selector result that is non-empty, so the most
        reliable selector wins.
        """
        for selector in _CARD_SELECTORS:
            cards: List[Tag] = soup.select(selector)
            if cards:
                logger.debug(
                    "_parse_jobs: %d cards matched selector %r",
                    len(cards),
                    selector,
                )
                return cards

        logger.warning("_parse_jobs: no job cards found with any known selector.")
        return []

    def _parse_job(self, raw: Tag) -> JobResult:
        """Delegate to :meth:`_normalize` and stamp ``source="indeed"``."""
        job = self._normalize(raw)
        return JobResult(job, source="indeed")

    def _normalize(self, raw: Tag) -> JobResult:
        title = self._extract_title(raw)
        company = self._extract_company(raw)
        location = self._extract_location(raw)
        description = self._extract_description(raw)
        link = self._extract_link(raw)

        return JobResult.create(
            title=title,
            company=company,
            location=location,
            description=description,
            link=link,
        )

    def _get_next_page_url(
        self, soup: BeautifulSoup, current_page: int
    ) -> Optional[str]:
        """
        Not used – infinite scroll replaces URL-based pagination.

        Exists only to satisfy the :class:`BaseScraper` abstract interface.
        """
        return None

    # ------------------------------------------------------------------
    # Field extractors with fallbacks
    # ------------------------------------------------------------------

    def _extract_title(self, card: Tag) -> str:
        candidates = [
            card.find("h2", class_=lambda c: c and "jobTitle" in c),
            card.find("span", class_=lambda c: c and "jobTitle" in c),
            card.find("a", class_=lambda c: c and "jcs-JobTitle" in (c or "")),
            card.find("span", attrs={"title": True}),
            card.find("h2"),
        ]
        for tag in candidates:
            if tag:
                # Indeed often nests the visible text in a child <span title="…">.
                inner = tag.find("span", attrs={"title": True})
                text = extract_text(inner if inner else tag)
                if text:
                    return text
        return ""

    def _extract_company(self, card: Tag) -> str:
        candidates = [
            card.find(attrs={"data-testid": "company-name"}),
            card.find(attrs={"data-testid": "companyName"}),
            card.find("span", class_="companyName"),
            card.find("span", class_=lambda c: c and "company" in (c or "").lower()),
        ]
        for tag in candidates:
            text = extract_text(tag)
            if text:
                return text
        return ""

    def _extract_location(self, card: Tag) -> str:
        candidates = [
            card.find(attrs={"data-testid": "text-location"}),
            card.find(attrs={"data-testid": "job-location"}),
            card.find("div", class_="companyLocation"),
            card.find(class_=lambda c: c and "location" in (c or "").lower()),
        ]
        for tag in candidates:
            text = extract_text(tag)
            if text:
                return text
        return ""

    def _extract_link(self, card: Tag) -> str:
        # ``data-jk`` is Indeed's stable job key – most reliable source for link.
        job_key = card.get("data-jk")
        if job_key:
            return absolute_url(self.base_url, f"/viewjob?jk={job_key}")

        # Check nested elements carrying the job key.
        inner = card.find(attrs={"data-jk": True})
        if inner:
            job_key = inner.get("data-jk")
            if job_key:
                return absolute_url(self.base_url, f"/viewjob?jk={job_key}")

        # Fall through to href-based anchors.
        anchor_candidates = [
            card.find("a", class_=lambda c: c and "jcs-JobTitle" in (c or "")),
            card.find("a", href=lambda h: h and "/viewjob" in (h or "")),
            card.find("a", href=lambda h: h and "/rc/clk" in (h or "")),
            card.find("a", href=True),
        ]
        for anchor in anchor_candidates:
            if anchor and anchor.get("href"):
                return absolute_url(self.base_url, str(anchor["href"]))

        return ""

    def _extract_description(self, card: Tag) -> str:
        # Try the historical snippet selectors first (may match on older Indeed layouts)
        candidates = [
            card.find("div", class_=lambda c: c and "job-snippet" in (c or "")),
            card.find("div", attrs={"data-testid": "job-snippet"}),
            card.find("ul", class_=lambda c: c and "jobCardShelfContainer" in (c or "")),
            card.find("div", class_=lambda c: c and "snippet" in (c or "").lower()),
        ]

        for tag in candidates:
            text = extract_text(tag)
            if text:
                return text

        # Fallback: use the metadata/benefits list present on current Indeed cards
        # (e.g. "Health insurance · 401(k) · Paid time off")
        meta = card.find("ul", class_=lambda c: c and "metadataContainer" in (c or ""))
        if meta:
            items = [extract_text(li) for li in meta.find_all("li") if extract_text(li)]
            if items:
                return " · ".join(items)

        # Final fallback: fetch the individual job page when enabled
        if not self.fetch_descriptions:
            return ""

        link = self._extract_link(card)
        if not link:
            return ""

        return self._fetch_full_description(link) or ""

    def _fetch_full_description(self, url: str) -> str:
        """
        Navigate to the job's individual page and extract the description text.

        Only triggered when ``fetch_descriptions=True``.  Reuses the running
        driver so no extra HTTP session is required.
        """
        assert self._driver is not None
        logger.debug("Fetching full description from %s", url)

        try:
            self._driver.get(url)
            time.sleep(random.uniform(2, 4))  # brief pause to mimic human reading
            WebDriverWait(self._driver, self.timeout).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "#jobDescriptionText, .jobsearch-jobDescriptionText",
                    )
                )
            )
        except (TimeoutException, WebDriverException) as exc:
            logger.warning(
                "Could not load description page %s: %s", url, exc
            )
            return ""

        soup = BeautifulSoup(self._driver.page_source, "html.parser")
        desc_tag = soup.find("div", id="jobDescriptionText") or soup.find(
            "div",
            class_=lambda c: c and "jobsearch-jobDescriptionText" in (c or ""),
        )
        return extract_text(desc_tag)

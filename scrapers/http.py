"""HTTP layer: retries with exponential backoff, rate limiting, safe returns."""
import logging
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class Fetcher:
    def __init__(self, timeout=15.0, max_retries=3, backoff_base=1.0,
                 delay=0.3, user_agent="scraping-assignment/1.0"):
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.delay = delay
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.failed_urls: list[str] = []
        self._last_request = 0.0

    def _throttle(self):
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get(self, url: str) -> Optional[str]:
        """Return page HTML, or None if the page could not be fetched.

        Never raises: a failed page must not stop the whole run.
        """
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                log.warning("Attempt %d/%d failed for %s: %s",
                            attempt + 1, self.max_retries, url, exc)
            except requests.RequestException as exc:
                log.error("Unrecoverable request error for %s: %s", url, exc)
                break
            else:
                if resp.status_code == 200:
                    # books.toscrape.com omits the charset; force UTF-8 so
                    # "£" is not decoded as "Â£".
                    resp.encoding = "utf-8"
                    return resp.text
                if resp.status_code in RETRYABLE_STATUS:
                    log.warning("HTTP %d for %s (attempt %d/%d)",
                                resp.status_code, url, attempt + 1,
                                self.max_retries)
                else:
                    log.error("HTTP %d for %s - not retrying",
                              resp.status_code, url)
                    break
            if attempt < self.max_retries - 1:
                time.sleep(self.backoff_base * (2 ** attempt))
        self.failed_urls.append(url)
        log.error("Giving up on %s", url)
        return None

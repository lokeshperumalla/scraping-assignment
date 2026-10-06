"""Quotes to Scrape scraper.

Pagination follows the 'Next' link (li.next a) until absent. Author bios are
fetched once per author (cached) and used as the record description.
"""
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

SOURCE = "Quotes to Scrape"
log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_quotes_page(html: str, page_url: str):
    """Parse one page -> (raw_records, next_page_url or None)."""
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for q in soup.select("div.quote"):
        try:
            text_el = q.select_one("span.text")
            author_el = q.select_one("small.author")
            about = q.select_one("a[href^='/author/']")
            tags = [t.get_text() for t in q.select("div.tags a.tag")]
            records.append({
                "source": SOURCE,
                # quotes have no per-item page; the listing page is the origin
                "source_url": page_url,
                "name_or_title": text_el.get_text() if text_el else None,
                "category": None,
                "price": None,
                "rating": None,
                "availability": None,
                "author": author_el.get_text() if author_el else None,
                "tags": tags,
                "description": None,
                "author_url": urljoin(page_url, about["href"]) if about else None,
                "scraped_at": _now(),
            })
        except Exception as exc:
            log.warning("Skipping malformed quote on %s: %s", page_url, exc)
    nxt = soup.select_one("li.next a")
    next_url = urljoin(page_url, nxt["href"]) if nxt and nxt.get("href") else None
    return records, next_url


def parse_author_bio(html: str) -> str | None:
    el = BeautifulSoup(html, "html.parser").select_one("div.author-description")
    return el.get_text() if el else None


def scrape_quotes(fetch, base_url: str, max_pages: int | None = None,
                  fetch_authors: bool = True):
    stats = {"pages_fetched": 0, "pages_failed": 0, "author_pages_failed": 0}
    records: list[dict] = []
    url, pages = base_url, 0
    while url and (max_pages is None or pages < max_pages):
        html = fetch(url)
        if html is None:
            stats["pages_failed"] += 1
            break
        page_records, url = parse_quotes_page(html, url)
        records.extend(page_records)
        stats["pages_fetched"] += 1
        pages += 1

    if fetch_authors:
        bios: dict[str, str | None] = {}
        for rec in records:
            a_url = rec.get("author_url")
            if not a_url:
                continue
            if a_url not in bios:
                a_html = fetch(a_url)
                if a_html is None:
                    stats["author_pages_failed"] += 1
                    bios[a_url] = None
                else:
                    bios[a_url] = parse_author_bio(a_html)
            rec["description"] = bios[a_url]
    for rec in records:
        rec.pop("author_url", None)
    log.info("Quotes: %d raw records from %d pages (%d failed)",
             len(records), stats["pages_fetched"], stats["pages_failed"])
    return records, stats

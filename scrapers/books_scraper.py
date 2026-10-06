"""Books to Scrape scraper.

Strategy: category listing pages are crawled instead of visiting every
product page. The category name comes from the sidebar link being crawled,
which avoids ~1000 extra detail-page requests. Pagination follows the
"next" link on each listing page until it disappears.

Only raw strings are returned; all cleaning lives in processing/cleaning.py.
"""
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

SOURCE = "Books to Scrape"
log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_categories(html: str, base_url: str) -> list[tuple[str, str]]:
    """Return [(category_name, category_url)] from the sidebar (skips 'Books')."""
    soup = BeautifulSoup(html, "html.parser")
    cats = []
    for a in soup.select("div.side_categories ul ul li a"):
        href = a.get("href")
        name = a.get_text(strip=True)
        if href and name:
            cats.append((name, urljoin(base_url, href)))
    return cats


def parse_listing(html: str, page_url: str, category: str | None):
    """Parse one listing page -> (raw_records, next_page_url or None)."""
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for art in soup.select("article.product_pod"):
        try:
            link = art.select_one("h3 a")
            rating_el = art.select_one("p.star-rating")
            price_el = art.select_one("p.price_color")
            avail_el = art.select_one("p.availability")
            records.append({
                "source": SOURCE,
                # product links are relative; resolve against the page URL
                "source_url": urljoin(page_url, link["href"]) if link and link.get("href") else None,
                # full title is in the title attribute (link text is truncated)
                "name_or_title": (link.get("title") or link.get_text()) if link else None,
                "category": category,
                "price": price_el.get_text() if price_el else None,
                "rating": " ".join(rating_el.get("class", [])) if rating_el else None,
                "availability": avail_el.get_text() if avail_el else None,
                "author": None,
                "tags": None,
                "description": None,
                "scraped_at": _now(),
            })
        except Exception as exc:  # one bad product must not kill the page
            log.warning("Skipping malformed product on %s: %s", page_url, exc)
    nxt = soup.select_one("li.next a")
    next_url = urljoin(page_url, nxt["href"]) if nxt and nxt.get("href") else None
    return records, next_url


def scrape_books(fetch, base_url: str, max_pages: int | None = None):
    """Crawl every category and every page of it. Returns (records, stats)."""
    stats = {"pages_fetched": 0, "pages_failed": 0, "categories": 0}
    records: list[dict] = []

    index_html = fetch(base_url)
    if index_html is None:
        log.error("Books index page unavailable; no books scraped")
        stats["pages_failed"] += 1
        return records, stats

    categories = parse_categories(index_html, base_url)
    stats["categories"] = len(categories)
    log.info("Books: found %d categories", len(categories))

    for name, cat_url in categories:
        url, pages = cat_url, 0
        while url and (max_pages is None or pages < max_pages):
            html = fetch(url)
            if html is None:
                stats["pages_failed"] += 1
                break  # cannot discover the next link without this page
            page_records, url = parse_listing(html, url, name)
            records.extend(page_records)
            stats["pages_fetched"] += 1
            pages += 1
    log.info("Books: %d raw records from %d pages (%d failed)",
             len(records), stats["pages_fetched"], stats["pages_failed"])
    return records, stats

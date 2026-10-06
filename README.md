# Multi-Source Web Scraping & Data Consolidation

A Python pipeline that scrapes **Books to Scrape** and **Quotes to Scrape**, cleans each record into one shared schema, validates, deduplicates, and writes a consolidated CSV plus a JSON summary.

```
Books ─┐
       ├─> Scrape ─> Clean ─> Validate ─> Deduplicate ─> final_dataset.csv + summary_report.json
Quotes ┘
```

## Setup
- Python 3.10+ (developed on 3.13)
- Dependencies: `requests`, `beautifulsoup4` (`pytest` for tests)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q          # 1. optional: offline tests
python main.py --max-pages 2 # 2. optional: quick smoke run
python main.py               # 3. full run -> output/ and logs/scrape.log
```
CLI options: `--max-pages N`, `--no-author-details`, `--delay SECONDS`, `--output-dir DIR`. Other settings (timeout, retries, backoff, URLs) live in `config.py`.

## Layout
```
scrapers/   http.py (retry/backoff/rate limit), books_scraper.py, quotes_scraper.py
processing/ cleaning.py, validation.py, deduplication.py
main.py     orchestration + output     config.py  settings
tests/      test_pipeline.py           logs/ output/
```
Scrapers return raw strings only; all transformation lives in `processing/`.

## Source observations (Step 1)
- **Books**: 50 listing pages ("next" link) of 20 books. Titles are truncated in link text, so the full title is read from the `title` attribute. Rating is a CSS class (`star-rating Three`). The site sends no charset, so `£` can decode as `Â£`; the HTTP layer forces UTF-8 and the price parser also tolerates `Â£`. Category appears only on detail pages/sidebar.
- **Quotes**: 10 pages with a "Next" button. Quotes have no per-item page, authors have an `/author/...` page with a bio, tags are repeated links.

## How pagination works
Neither site has its page count hard-coded. Each scraper follows the `li.next a` link until it disappears. Books is crawled **per category** (sidebar links, each paginated) so the category is known without ~1000 detail-page requests. If a page fails, that listing stops (the next link can't be discovered) but other categories/sources continue. `--max-pages` caps pages per listing for testing.

## Data model
`source, source_url, name_or_title, category, price, currency, rating, availability, author, tags, description, scraped_at`

| Field | Books | Quotes |
|---|---|---|
| name_or_title | full title | quote text (surrounding quote marks stripped) |
| source_url | product page URL | listing page the quote was found on |
| category / price / currency / rating / availability | filled | empty |
| author | empty | filled |
| tags | empty | `a\|b\|c` (lower-case, de-duplicated) |
| description | empty (not scraped, to avoid 1000 extra requests) | author bio |

Missing or inapplicable values are empty/null; nothing is invented. `rating` is an integer 1–5, `price` a float, `scraped_at` UTC ISO-8601.

## Cleaning
NFKC normalisation, whitespace collapse (incl. non-breaking spaces), placeholder tokens (`n/a`, `none`, `-`…) → null, price → float + currency, rating word → int, URLs resolved/lower-cased host/fragment dropped and rejected if not http(s), tags normalised.

## Validation
Rejected (not silently dropped) with reasons in `output/rejected_records.csv`: unrecognised source, missing title, missing/malformed URL, price present but non-numeric or negative, rating outside 1–5, a book with no price, a quote with no author. Reason counts appear in the summary.

## Deduplication
Comparison keys use aggressive normalisation (NFKC, casefold, punctuation → space, whitespace collapsed), so `"Example Book Title"`, `" Example Book Title "` and `"EXAMPLE BOOK TITLE"` match.
- **Books**: normalised title + price (same title at a different price is treated as a different product).
- **Quotes**: normalised text + normalised author.
- Source is part of the key, so records from different sources are never merged.

Duplicates are **removed** (first occurrence kept) because the deliverable is a consolidated dataset; removed rows are written to `output/duplicates_removed.csv` with a `duplicate_of` URL so every decision is auditable.

## Error handling
`Fetcher.get` retries connection errors, timeouts, 429 and 5xx up to 3 times with exponential backoff, does not retry other 4xx, and returns `None` instead of raising. Missing HTML elements yield nulls; a malformed item is skipped without losing the page; a failure in one source doesn't stop the other. Failed URLs are listed in the summary; everything is logged to console and `logs/scrape.log`. A ~0.3 s delay between requests keeps traffic polite; robots/CAPTCHAs/auth are not touched.

## Output
- `output/final_dataset.csv`: consolidated records
- `output/summary_report.json`: per-source collected / after cleaning / rejected / duplicates / final, totals, rejection reasons, failed URLs, runtime
- `output/rejected_records.csv`, `output/duplicates_removed.csv`: audit trails

## Assumptions & limitations
- Books description/availability detail beyond the listing is not fetched; Books `source_url` is the product URL.
- Sequential (no async) by design, because the polite rate limit matters more than speed at this scale.
- Selectors target the sites' current markup; a redesign would need `scrapers/` updates only.
- Not implemented: DB storage, checkpoint/resume, incremental runs. For production I'd add those, plus scheduling and alerts on selector breakage.

## AI usage
See `AI_USAGE.md`.

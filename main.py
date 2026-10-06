"""Entry point: scrape -> clean -> validate -> deduplicate -> consolidate -> write."""
import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path

from config import Settings
from processing.cleaning import CSV_FIELDS, clean_record
from processing.deduplication import deduplicate
from processing.validation import validate_all
from scrapers.books_scraper import scrape_books
from scrapers.http import Fetcher
from scrapers.quotes_scraper import scrape_quotes

log = logging.getLogger("pipeline")


def setup_logging(log_dir: str) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO, format=fmt, force=True,
        handlers=[logging.FileHandler(Path(log_dir) / "scrape.log", mode="w",
                                      encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def process(raw_by_source: dict[str, list[dict]]):
    """Clean, validate, dedupe. Returns (final, rejected, duplicates, per_source)."""
    cleaned_all, per_source = [], {}
    for source, raws in raw_by_source.items():
        cleaned = []
        for raw in raws:
            try:
                cleaned.append(clean_record(raw))
            except Exception as exc:  # unexpected format: drop, don't crash
                log.warning("Cleaning failed for %s record: %s", source, exc)
        per_source[source] = {"collected": len(raws), "after_cleaning": len(cleaned)}
        cleaned_all.extend(cleaned)

    valid, rejected = validate_all(cleaned_all)
    final, duplicates = deduplicate(valid)

    for source, stats in per_source.items():
        stats["rejected_validation"] = sum(r["source"] == source for r in rejected)
        stats["duplicates_removed"] = sum(d["source"] == source for d in duplicates)
        stats["final"] = sum(r["source"] == source for r in final)
    return final, rejected, duplicates, per_source


def run(settings: Settings, fetch=None, scrape_stats_out: dict | None = None):
    start = time.time()
    fetcher = None
    if fetch is None:
        fetcher = Fetcher(settings.request_timeout, settings.max_retries,
                          settings.backoff_base, settings.delay_between_requests,
                          settings.user_agent)
        fetch = fetcher.get

    raw_by_source, scrape_stats = {}, {}
    for name, fn in (
        ("Books to Scrape", lambda: scrape_books(
            fetch, settings.books_base_url, settings.max_pages)),
        ("Quotes to Scrape", lambda: scrape_quotes(
            fetch, settings.quotes_base_url, settings.max_pages,
            settings.fetch_author_details)),
    ):
        try:
            raw_by_source[name], scrape_stats[name] = fn()
        except Exception:  # one source failing must not stop the other
            log.exception("Source %s failed entirely", name)
            raw_by_source[name], scrape_stats[name] = [], {"fatal_error": True}

    final, rejected, duplicates, per_source = process(raw_by_source)

    out = Path(settings.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "final_dataset.csv", final, CSV_FIELDS)
    write_csv(out / "rejected_records.csv", rejected, CSV_FIELDS + ["reject_reasons"])
    write_csv(out / "duplicates_removed.csv", duplicates, CSV_FIELDS + ["duplicate_of"])

    reasons: dict[str, int] = {}
    for r in rejected:
        for reason in r["reject_reasons"].split(";"):
            reasons[reason] = reasons.get(reason, 0) + 1

    summary = {
        "per_source": {s: {**per_source[s], "scrape": scrape_stats.get(s, {})}
                       for s in per_source},
        "totals": {
            "collected": sum(v["collected"] for v in per_source.values()),
            "after_cleaning": sum(v["after_cleaning"] for v in per_source.values()),
            "rejected_validation": len(rejected),
            "duplicates_removed": len(duplicates),
            "final": len(final),
        },
        "rejection_reasons": reasons,
        "failed_urls": fetcher.failed_urls if fetcher else [],
        "execution_time_seconds": round(time.time() - start, 2),
    }
    with open(out / "summary_report.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    log.info("Done: %s", summary["totals"])
    return summary


def parse_args(argv=None) -> Settings:
    p = argparse.ArgumentParser(description="Multi-source scraping pipeline")
    p.add_argument("--max-pages", type=int, help="limit pages per listing (testing)")
    p.add_argument("--no-author-details", action="store_true",
                   help="skip fetching author pages for quote descriptions")
    p.add_argument("--delay", type=float, help="seconds between requests")
    p.add_argument("--output-dir", default=None)
    a = p.parse_args(argv)
    s = Settings()
    if a.max_pages:
        s.max_pages = a.max_pages
    if a.no_author_details:
        s.fetch_author_details = False
    if a.delay is not None:
        s.delay_between_requests = a.delay
    if a.output_dir:
        s.output_dir = a.output_dir
    return s


if __name__ == "__main__":
    cfg = parse_args()
    setup_logging(cfg.log_dir)
    run(cfg)

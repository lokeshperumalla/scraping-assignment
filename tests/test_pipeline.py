"""Offline tests. HTML fixtures mimic the markup of the two practice sites;
they are NOT scraped data and are never written to the final dataset."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Settings  # noqa: E402
from main import run  # noqa: E402
from processing.cleaning import (clean_record, clean_text, normalize_key,  # noqa: E402
                                 normalize_tags, normalize_url, parse_price,
                                 parse_rating)
from processing.deduplication import deduplicate  # noqa: E402
from processing.validation import validate_record  # noqa: E402
from scrapers.books_scraper import parse_listing  # noqa: E402

BOOKS = "https://books.toscrape.com/"
QUOTES = "https://quotes.toscrape.com/"


def book(title, price="£51.77", rating="Three", href="a-book_1/index.html"):
    return f"""<article class="product_pod"><p class="star-rating {rating}"></p>
    <h3><a href="{href}" title="{title}">{title[:10]}...</a></h3>
    <div class="product_price"><p class="price_color">{price}</p>
    <p class="instock availability">  In stock  </p></div></article>"""


def books_index():
    return """<html><body><div class="side_categories"><ul><li><a href="catalogue/category/books_1/index.html">Books</a>
    <ul><li><a href="catalogue/category/books/travel_2/index.html"> Travel </a></li></ul></li></ul></div></body></html>"""


def books_page(items, nxt=None):
    n = f'<li class="next"><a href="{nxt}">next</a></li>' if nxt else ""
    return f"<html><body>{''.join(items)}<ul class='pager'>{n}</ul></body></html>"


def quote(text, author, tags):
    t = "".join(f'<a class="tag" href="/tag/{x}/">{x}</a>' for x in tags)
    return f"""<div class="quote"><span class="text">“{text}”</span>
    <span>by <small class="author">{author}</small><a href="/author/{author.replace(' ', '-')}">(about)</a></span>
    <div class="tags">{t}</div></div>"""


def quotes_page(items, nxt=None):
    n = f'<li class="next"><a href="{nxt}">Next</a></li>' if nxt else ""
    return f"<html><body>{''.join(items)}<ul class='pager'>{n}</ul></body></html>"


# ---------- cleaning ----------
def test_clean_text_whitespace_and_missing():
    assert clean_text("  a \n  b\xa0c ") == "a b c"
    assert clean_text("N/A") is None and clean_text("   ") is None and clean_text(None) is None


def test_parse_price_handles_mojibake_and_commas():
    assert parse_price("Â£51.77") == (51.77, "GBP")
    assert parse_price("£1,051.50") == (1051.5, "GBP")
    assert parse_price("free") == (None, None)
    assert parse_price(None) == (None, None)


def test_parse_rating():
    assert parse_rating("star-rating Four") == 4
    assert parse_rating("5") == 5
    assert parse_rating("star-rating") is None


def test_normalize_url_and_tags():
    assert normalize_url("HTTPS://Example.COM/a#frag") == "https://example.com/a"
    assert normalize_url("/rel", base="https://x.com/y/") == "https://x.com/rel"
    assert normalize_url("ftp://x.com") is None and normalize_url("not a url") is None
    assert normalize_tags(["Love", " love ", "Life"]) == "love|life"
    assert normalize_tags([]) is None


# ---------- dedup ----------
def test_dedup_normalised_titles():
    base = dict(source="Books to Scrape", price=10.0, source_url="https://a.com/1")
    recs = [{**base, "name_or_title": "Example Book Title"},
            {**base, "name_or_title": " Example Book Title ", "source_url": "https://a.com/2"},
            {**base, "name_or_title": "EXAMPLE BOOK TITLE!", "source_url": "https://a.com/3"},
            {**base, "name_or_title": "Example Book Title", "price": 11.0}]  # different price -> distinct
    unique, removed = deduplicate(recs)
    assert len(unique) == 2 and len(removed) == 2
    assert removed[0]["duplicate_of"] == "https://a.com/1"


def test_dedup_quotes_use_author():
    base = dict(source="Quotes to Scrape", source_url="https://q.com/")
    recs = [{**base, "name_or_title": "Hello world", "author": "A B"},
            {**base, "name_or_title": "hello  WORLD", "author": "a b"},
            {**base, "name_or_title": "Hello world", "author": "C D"}]
    unique, removed = deduplicate(recs)
    assert len(unique) == 2 and len(removed) == 1


def test_normalize_key():
    assert normalize_key("  Don't  STOP! ") == "don t stop"


# ---------- validation ----------
def good_book():
    return clean_record({"source": "Books to Scrape", "source_url": BOOKS + "x/index.html",
                         "name_or_title": "T", "price": "£5.00", "rating": "star-rating Two"})


def test_validation_accepts_good_and_rejects_bad():
    assert validate_record(good_book()) == []
    bad = good_book() | {"name_or_title": None}
    assert "missing_name_or_title" in validate_record(bad)
    assert "unrecognised_source" in validate_record(good_book() | {"source": "Other"})
    assert "missing_or_invalid_url" in validate_record(good_book() | {"source_url": None})
    nonnum = clean_record({"source": "Books to Scrape", "source_url": BOOKS, "name_or_title": "T",
                           "price": "abc", "rating": "Two"})
    assert "price_not_numeric" in validate_record(nonnum)
    badrating = clean_record({"source": "Books to Scrape", "source_url": BOOKS, "name_or_title": "T",
                              "price": "£1", "rating": "9"})
    assert "rating_out_of_range" in validate_record(badrating)


def test_quote_requires_author():
    r = clean_record({"source": "Quotes to Scrape", "source_url": QUOTES, "name_or_title": "“x”"})
    assert r["name_or_title"] == "x"
    assert "quote_missing_author" in validate_record(r)


# ---------- parsing ----------
def test_parse_listing_missing_elements_do_not_crash():
    html = books_page([book("Full Title Here"),
                       '<article class="product_pod"><h3></h3></article>'])
    recs, nxt = parse_listing(html, BOOKS + "catalogue/category/x/index.html", "Travel")
    assert len(recs) == 2 and nxt is None
    assert recs[0]["source_url"].startswith(BOOKS + "catalogue/category/x/")
    assert recs[1]["price"] is None and recs[1]["name_or_title"] is None


# ---------- end to end with fake fetcher ----------
def make_fake():
    cat = BOOKS + "catalogue/category/books/travel_2/index.html"
    pages = {
        BOOKS: books_index(),
        cat: books_page([book("Book One", href="one_1/index.html"),
                         book("Book Two", price="Â£20.00", href="two_2/index.html")], "page-2.html"),
        BOOKS + "catalogue/category/books/travel_2/page-2.html": books_page(
            [book("BOOK ONE ", href="one_1b/index.html"),
             book("Broken Price", price="n/a", href="bp_3/index.html")]),
        QUOTES: quotes_page([quote("Be kind", "Ann Lee", ["kindness", "life"])], "/page/2/"),
        QUOTES + "page/2/": quotes_page([quote("be  KIND", "ann lee", ["Life"]),
                                         quote("Another", "Bob Ray", [])]),
        QUOTES + "author/Ann-Lee": '<div class="author-description">  Ann was born. </div>',
        # Bob Ray's author page deliberately missing -> simulates failure
    }
    calls = []

    def fetch(url):
        calls.append(url)
        return pages.get(url)
    return fetch, calls


def test_end_to_end(tmp_path):
    fetch, calls = make_fake()
    s = Settings(output_dir=str(tmp_path))
    summary = run(s, fetch=fetch)

    t = summary["totals"]
    assert t["collected"] == 4 + 3
    assert t["after_cleaning"] == 7
    assert t["rejected_validation"] == 1          # Broken Price (book without price)
    assert t["duplicates_removed"] == 2           # BOOK ONE dup + be KIND dup (different price? see key)
    assert t["final"] == t["after_cleaning"] - 1 - 2

    rows = list(csv.DictReader(open(tmp_path / "final_dataset.csv", encoding="utf-8")))
    assert len(rows) == t["final"]
    assert all(r["source"] and r["source_url"] for r in rows)
    assert {r["source"] for r in rows} == {"Books to Scrape", "Quotes to Scrape"}
    ann = next(r for r in rows if r["author"] == "Ann Lee")
    assert ann["description"] == "Ann was born." and ann["tags"] == "kindness|life"
    bob = next(r for r in rows if r["author"] == "Bob Ray")
    assert bob["description"] == "" and bob["tags"] == ""   # missing, not invented
    two = next(r for r in rows if r["name_or_title"] == "Book Two")
    assert two["price"] == "20.0" and two["rating"] == "3" and two["category"] == "Travel"
    assert json.load(open(tmp_path / "summary_report.json"))["totals"] == t
    # pagination followed to page 2 without hard-coded URLs
    assert BOOKS + "catalogue/category/books/travel_2/page-2.html" in calls
    assert QUOTES + "page/2/" in calls


def test_failed_source_does_not_stop_other(tmp_path):
    fetch, _ = make_fake()
    s = Settings(output_dir=str(tmp_path))
    summary = run(s, fetch=lambda u: None if u.startswith(BOOKS) else fetch(u))
    assert summary["per_source"]["Books to Scrape"]["collected"] == 0
    assert summary["per_source"]["Quotes to Scrape"]["collected"] == 3
    assert summary["totals"]["final"] == 2

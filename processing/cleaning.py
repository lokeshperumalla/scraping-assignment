"""Reusable cleaning helpers. No scraping logic here."""
import re
import unicodedata
from urllib.parse import urljoin, urlsplit, urlunsplit

MISSING_TOKENS = {"", "n/a", "na", "none", "null", "nan", "-", "--"}
RATING_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
QUOTE_CHARS = "“”\"‘’'"

CSV_FIELDS = [
    "source", "source_url", "name_or_title", "category", "price", "currency",
    "rating", "availability", "author", "tags", "description", "scraped_at",
]


def clean_text(value) -> str | None:
    """Unicode-normalise (NFKC), collapse whitespace, map missing tokens to None."""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return None if text.lower() in MISSING_TOKENS else text


def parse_price(value) -> tuple[float | None, str | None]:
    """'Â£51.77' / '£1,051.77' -> (51.77, 'GBP'). Unparseable -> (None, None)."""
    text = clean_text(value)
    if text is None:
        return None, None
    currency = "GBP" if "£" in text else "USD" if "$" in text else "EUR" if "€" in text else None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if not m:
        return None, None
    try:
        return round(float(m.group().replace(",", "")), 2), currency
    except ValueError:
        return None, None


def parse_rating(value) -> int | None:
    """'star-rating Three' / 'Three' / '3' -> 3. Anything else -> None."""
    text = clean_text(value)
    if text is None:
        return None
    for token in text.lower().split():
        if token in RATING_WORDS:
            return RATING_WORDS[token]
        if token.isdigit():
            return int(token)
    return None


def normalize_url(url, base: str | None = None) -> str | None:
    """Resolve relative URLs, lower-case scheme/host, drop fragment."""
    text = clean_text(url)
    if text is None:
        return None
    if base:
        text = urljoin(base, text)
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                       parts.path, parts.query, ""))


def normalize_tags(tags) -> str | None:
    """List (or delimited string) -> 'a|b|c' (lower-case, de-duplicated, ordered)."""
    if tags is None:
        return None
    if isinstance(tags, str):
        tags = re.split(r"[|,;]", tags)
    seen, out = set(), []
    for t in tags:
        t = clean_text(t)
        if t:
            t = t.lower()
            if t not in seen:
                seen.add(t)
                out.append(t)
    return "|".join(out) if out else None


def strip_quote_marks(text: str | None) -> str | None:
    return clean_text(text.strip(QUOTE_CHARS)) if text else text


def normalize_key(value) -> str:
    """Aggressive normalisation used ONLY for duplicate comparison.

    NFKC, casefold, punctuation -> space, whitespace collapsed.
    """
    text = clean_text(value) or ""
    text = text.casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_record(raw: dict) -> dict:
    """Turn one raw scraped dict into the standardised schema."""
    price, currency = parse_price(raw.get("price"))
    title = clean_text(raw.get("name_or_title"))
    if raw.get("source") == "Quotes to Scrape":
        title = strip_quote_marks(title)
    return {
        "source": clean_text(raw.get("source")),
        "source_url": normalize_url(raw.get("source_url")),
        "name_or_title": title,
        "category": clean_text(raw.get("category")),
        "price": price,
        "currency": currency,
        "rating": parse_rating(raw.get("rating")),
        "availability": clean_text(raw.get("availability")),
        "author": clean_text(raw.get("author")),
        "tags": normalize_tags(raw.get("tags")),
        "description": clean_text(raw.get("description")),
        "scraped_at": clean_text(raw.get("scraped_at")),
        # carried so validation can tell "no price on page" from "bad price"
        "_raw_price": clean_text(raw.get("price")),
        "_raw_rating": clean_text(raw.get("rating")),
    }

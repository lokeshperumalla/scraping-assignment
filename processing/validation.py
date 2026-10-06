"""Record validation. Returns reasons instead of raising."""
import re

KNOWN_SOURCES = {"Books to Scrape", "Quotes to Scrape"}
URL_RE = re.compile(r"^https?://[^\s/]+\.[^\s/]+(/\S*)?$|^https?://localhost(:\d+)?(/\S*)?$")


def validate_record(rec: dict) -> list[str]:
    """Return a list of validation errors (empty list = valid)."""
    errors = []
    if rec.get("source") not in KNOWN_SOURCES:
        errors.append("unrecognised_source")
    if not rec.get("name_or_title"):
        errors.append("missing_name_or_title")
    url = rec.get("source_url")
    if not url:
        errors.append("missing_or_invalid_url")
    elif not URL_RE.match(url):
        errors.append("malformed_url")

    # price: if the page showed one it must have parsed and be non-negative
    if rec.get("_raw_price") is not None:
        if rec.get("price") is None:
            errors.append("price_not_numeric")
        elif rec["price"] < 0:
            errors.append("negative_price")
    # rating: must be 1-5 when present
    if rec.get("_raw_rating") is not None:
        r = rec.get("rating")
        if r is None or not 1 <= r <= 5:
            errors.append("rating_out_of_range")

    # source-specific requirements
    if rec.get("source") == "Books to Scrape":
        if rec.get("price") is None and "price_not_numeric" not in errors:
            errors.append("book_missing_price")
    if rec.get("source") == "Quotes to Scrape" and not rec.get("author"):
        errors.append("quote_missing_author")
    return errors


def validate_all(records: list[dict]):
    """Split into (valid, rejected). Rejected rows get a 'reject_reasons' field."""
    valid, rejected = [], []
    for rec in records:
        errs = validate_record(rec)
        if errs:
            rejected.append({**rec, "reject_reasons": ";".join(errs)})
        else:
            valid.append(rec)
    return valid, rejected

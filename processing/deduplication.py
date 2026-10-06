"""Duplicate detection on normalised keys.

Key per source (see README for rationale):
  Books  : (source, normalised title, price)
  Quotes : (source, normalised quote text, normalised author)

Normalisation = NFKC + casefold + punctuation removal + whitespace collapse,
so "Example Book Title", " Example Book Title " and "EXAMPLE BOOK TITLE"
collapse to one key. The first occurrence is kept; later ones are removed and
reported in a separate file so the decision is auditable.
"""
from .cleaning import normalize_key


def dedup_key(rec: dict) -> tuple:
    source = rec.get("source")
    title = normalize_key(rec.get("name_or_title"))
    if source == "Quotes to Scrape":
        return (source, title, normalize_key(rec.get("author")))
    if source == "Books to Scrape":
        return (source, title, rec.get("price"))
    return (source, title)


def deduplicate(records: list[dict]):
    """Return (unique_records, removed_duplicates)."""
    seen: dict[tuple, dict] = {}
    unique, removed = [], []
    for rec in records:
        key = dedup_key(rec)
        if key in seen:
            removed.append({**rec, "duplicate_of": seen[key].get("source_url")})
        else:
            seen[key] = rec
            unique.append(rec)
    return unique, removed

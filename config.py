"""Central, overridable settings for the pipeline."""
from dataclasses import dataclass


@dataclass
class Settings:
    books_base_url: str = "https://books.toscrape.com/"
    quotes_base_url: str = "https://quotes.toscrape.com/"
    request_timeout: float = 15.0      # seconds per request
    max_retries: int = 3               # attempts per URL (exponential backoff)
    backoff_base: float = 1.0          # sleep = backoff_base * 2**attempt
    delay_between_requests: float = 0.3  # polite rate limit (seconds)
    max_pages: int | None = None       # cap pages per listing (None = all)
    fetch_author_details: bool = True  # quotes: visit author pages for bio
    output_dir: str = "output"
    log_dir: str = "logs"
    user_agent: str = (
        "scraping-assignment/1.0 (interview take-home; polite crawler)"
    )

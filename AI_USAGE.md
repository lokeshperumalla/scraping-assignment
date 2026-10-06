# AI Usage

## Tool
**Claude (Anthropic)** via the Claude app with a code-execution sandbox.

## What it was used for
- Reading the assignment and proposing the project structure and schema.
- Generating the initial scrapers, cleaning/validation/dedup modules, `main.py`, tests and documentation.
- Running the test suite and fixing issues in the sandbox.

## Representative prompts
- "complete the task" (with the assignment PDF attached).

## AI-assisted parts
All of the code, tests and docs in this submission were AI-generated in one session. **The author must review, run and be able to explain them before submitting.**

## Decisions worth knowing (for the interview walk-through)
- Books is crawled per category rather than per product page, to get `category` without ~1000 detail requests. Trade-off: no book descriptions.
- Dedup keys include price for books and author for quotes to avoid merging distinct items that share text.
- Duplicates are removed but logged to `duplicates_removed.csv` for auditability.
- Forced UTF-8 decoding because Books to Scrape omits a charset (`£` → `Â£`); the parser also tolerates the mojibake form.

## Incorrect / incomplete aspects found
- The AI sandbox could not reach the target sites, so the code was first verified offline against fixtures. I then ran the full pipeline live on my machine: 1000 books and 100 quotes were collected.
- Spot-check: 10 random books and 10 random quotes from `final_dataset.csv` were compared against the live pages (title, price, rating, category for books; text, author, tags for quotes). I checked some by hand in the browser and all 20 automatically. All 20 matched.
- During testing `pytest` was missing from the environment and had to be installed.

## Verification
- 12 offline tests (`python -m pytest -q`) cover cleaning, validation, dedup (whitespace/case/punctuation variants), parser tolerance of missing elements, end-to-end consolidation, pagination following, a missing author page, and one source failing entirely. All pass.
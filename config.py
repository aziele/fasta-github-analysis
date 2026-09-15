import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

RESULTS_DIR = BASE_DIR / "results"
CACHE_DIR = BASE_DIR / "cache"
LOG_DIR = BASE_DIR / "logs"
REVIEW_DIR = BASE_DIR / "review"
PAPER_DIR = BASE_DIR / "paper"

for directory in [
    RESULTS_DIR,
    CACHE_DIR,
    LOG_DIR,
    REVIEW_DIR,
    PAPER_DIR,
]:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# Analysis snapshot
SEARCH_START_DATE = "2008-01-01"
ANALYSIS_END_DATE = "2026-09-15"


# GitHub
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"


# Paths
BIGQUERY_RESULTS = RESULTS_DIR / "01_bigquery.csv"

FILTERED_BIGQUERY_RESULTS = RESULTS_DIR / "02_bigquery.tsv"
EXCLUDED_BIGQUERY_RESULTS = RESULTS_DIR / "02_bigquery_excluded.tsv"

REPO_RESULTS = RESULTS_DIR / "03_repositories.tsv"
REPO_CACHE = CACHE_DIR / "03_repositories.json"
REPO_LOG = LOG_DIR / "03_repositories.log"

FILTERED_REPO_RESULTS = RESULTS_DIR / "04_repositories.tsv"
EXCLUDED_REPO_RESULTS = RESULTS_DIR / "04_repositories_excluded.tsv"

CODE_RESULTS = RESULTS_DIR / "05_code.tsv"
CODE_CACHE = CACHE_DIR / "05_code.json"
CODE_LOG = LOG_DIR / "05_code.log"

FILTERED_CODE_RESULTS = RESULTS_DIR / "06_code.tsv"
EXCLUDED_CODE_RESULTS = RESULTS_DIR / "06_code_excluded.tsv"

MERGED_RESULTS = RESULTS_DIR / "07_merged.tsv"

METADATA_RESULTS = RESULTS_DIR / "08_metadata.tsv"
METADATA_CACHE = CACHE_DIR / "08_metadata.json"
METADATA_LOG = LOG_DIR / "08_metadata.log"

BROAD_REVIEW = REVIEW_DIR / "broad_fasta_review.tsv"

FILTERED_RESULTS = RESULTS_DIR / "09_repositories.tsv"
EXCLUDED_RESULTS = RESULTS_DIR / "09_excluded.tsv"


SUPPLEMENTARY_TABLE = PAPER_DIR / "Supplementary_Table_1.xlsx"

FIGURE = PAPER_DIR / "Figure_1.pdf"


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def require_github_token() -> None:
    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Export a GitHub token before running API searches: "
            "export GITHUB_TOKEN='...'"
        )


"""Search GitHub repositories for FASTA-related terms."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
import logging
from pathlib import Path

import pandas as pd
from tqdm import tqdm

import config
import queries
from github_api import GitHubClient


SEARCH_URL = (
    f"{config.GITHUB_API_BASE_URL}"
    "/search/repositories"
)

# GitHub exposes at most 1,000 results for a search query.
# Stay below that limit to avoid incomplete result sets.
SAFE_RESULT_LIMIT = 900


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Search GitHub repositories for "
            "FASTA-related terms."
        )
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Ignore cached query results and "
            "retrieve all searches again."
        ),
    )

    return parser.parse_args()


def load_cache(path: Path) -> dict:
    """Load cached repository-search results."""

    if not path.exists():
        return {"queries": {}}

    with path.open(
        encoding="utf-8"
    ) as handle:
        cache = json.load(handle)

    if not isinstance(cache, dict):
        raise ValueError(
            f"Invalid cache format: {path}"
        )

    queries_cache = cache.get("queries")

    if not isinstance(
        queries_cache,
        dict,
    ):
        raise ValueError(
            f"Invalid cache format: {path}"
        )

    return {
        "queries": queries_cache,
    }


def save_cache(
    cache: dict,
    path: Path,
) -> None:
    """Save repository-search results to cache."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            cache,
            handle,
            indent=2,
            sort_keys=True,
        )


def fetch_partition(
    query: str,
    start: date,
    end: date,
    client: GitHubClient,
) -> set[str]:
    """
    Exhaustively retrieve repositories for one date partition.

    Date ranges are recursively subdivided whenever a query approaches
    GitHub's 1,000-result search limit.
    """

    search_query = (
        f"{query} "
        f"created:{start.isoformat()}"
        f"..{end.isoformat()}"
    )

    params = {
        "q": search_query,
        "per_page": 100,
        "page": 1,
    }

    logging.info(
        "Probe partition query=%s",
        search_query,
    )

    status, data = client.get(
        SEARCH_URL,
        config.github_headers(),
        params,
    )

    if (
        status != 200
        or not isinstance(data, dict)
    ):
        raise RuntimeError(
            "Repository search failed: "
            f"status={status}, "
            f"query={search_query}"
        )

    total = int(
        data.get(
            "total_count",
            0,
        )
    )

    logging.info(
        "Partition total=%s query=%s",
        total,
        search_query,
    )

    if total >= SAFE_RESULT_LIMIT:
        if start >= end:
            raise RuntimeError(
                "Single-day repository partition "
                f"contains {total} results and "
                "cannot be safely exhausted below "
                "GitHub's search limit: "
                f"{search_query}"
            )

        span_days = (
            end - start
        ).days

        midpoint = start + timedelta(
            days=span_days // 2
        )

        logging.info(
            "Split partition at %s query=%s",
            midpoint.isoformat(),
            query,
        )

        left = fetch_partition(
            query,
            start,
            midpoint,
            client,
        )

        right = fetch_partition(
            query,
            midpoint + timedelta(days=1),
            end,
            client,
        )

        return left | right

    repositories: set[str] = set()

    pages = (
        total + 99
    ) // 100

    for page in range(
        1,
        pages + 1,
    ):
        if page == 1:
            page_data = data

        else:
            params["page"] = page

            status, page_data = client.get(
                SEARCH_URL,
                config.github_headers(),
                params,
            )

            if (
                status != 200
                or not isinstance(
                    page_data,
                    dict,
                )
            ):
                raise RuntimeError(
                    "Repository pagination failed: "
                    f"status={status}, "
                    f"page={page}, "
                    f"query={search_query}"
                )

        for item in page_data.get(
            "items",
            [],
        ):
            full_name = item.get(
                "full_name"
            )

            if full_name:
                repositories.add(
                    full_name
                    .strip()
                    .lower()
                )

    return repositories


def main() -> None:
    args = parse_arguments()

    config.require_github_token()

    # --------------------------------------------------------------
    # Configure logging
    # --------------------------------------------------------------

    config.REPO_LOG.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    logging.basicConfig(
        filename=config.REPO_LOG,
        filemode="w",
        level=logging.INFO,
        format=(
            "%(asctime)s - "
            "%(levelname)s - "
            "%(message)s"
        ),
    )

    # --------------------------------------------------------------
    # Analysis interval
    # --------------------------------------------------------------

    start = datetime.strptime(
        config.SEARCH_START_DATE,
        "%Y-%m-%d",
    ).date()

    end = datetime.strptime(
        config.ANALYSIS_END_DATE,
        "%Y-%m-%d",
    ).date()

    if start > end:
        raise ValueError(
            "SEARCH_START_DATE must not be "
            "after ANALYSIS_END_DATE"
        )

    # --------------------------------------------------------------
    # Cache
    # --------------------------------------------------------------

    if args.refresh:
        cache = {
            "queries": {},
        }

        logging.info(
            "Ignoring existing cache"
        )

    else:
        cache = load_cache(
            config.REPO_CACHE
        )

    # --------------------------------------------------------------
    # Search
    # --------------------------------------------------------------

    client = GitHubClient(
        min_sleep=2.0,
        max_attempts=5,
        buffer=2.0,
    )

    results: dict[
        str,
        dict[str, int],
    ] = {}

    for label, query in tqdm(
        queries.REPOSITORY_SEARCH_QUERIES,
        desc="Repository queries",
    ):
        signature = {
            "query": query,
            "start": (
                config.SEARCH_START_DATE
            ),
            "end": (
                config.ANALYSIS_END_DATE
            ),
        }

        cached = (
            cache["queries"]
            .get(label)
        )

        if (
            cached
            and cached.get(
                "signature"
            ) == signature
        ):
            repositories = set(
                cached.get(
                    "repos",
                    [],
                )
            )

            logging.info(
                "Cache hit label=%s repos=%s",
                label,
                len(repositories),
            )

        else:
            repositories = fetch_partition(
                query,
                start,
                end,
                client,
            )

            cache["queries"][label] = {
                "signature": signature,
                "repos": sorted(
                    repositories
                ),
            }

            save_cache(
                cache,
                config.REPO_CACHE,
            )

            logging.info(
                "Completed label=%s repos=%s",
                label,
                len(repositories),
            )

        for repository in repositories:
            results.setdefault(
                repository,
                {},
            )[label] = 1

    # --------------------------------------------------------------
    # Build repository-level evidence table
    # --------------------------------------------------------------

    labels = [
        label
        for label, _
        in queries.REPOSITORY_SEARCH_QUERIES
    ]

    df = pd.DataFrame.from_dict(
        results,
        orient="index",
    )

    df = (
        df
        .reindex(columns=labels)
        .fillna(0)
        .astype(int)
    )

    df.index.name = "repo_name"

    df = (
        df
        .reset_index()
        .sort_values("repo_name")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------------
    # Validate
    # --------------------------------------------------------------

    if not df["repo_name"].is_unique:
        raise ValueError(
            "Repository names are not unique"
        )

    evidence_columns = labels

    invalid_values = (
        ~df[evidence_columns]
        .isin([0, 1])
    )

    if invalid_values.any().any():
        raise ValueError(
            "Repository-search evidence "
            "contains values other than 0 or 1"
        )

    if (
        df[evidence_columns]
        .sum(axis=1)
        .eq(0)
        .any()
    ):
        raise ValueError(
            "Repository without search evidence found"
        )

    # --------------------------------------------------------------
    # Save
    # --------------------------------------------------------------

    config.REPO_RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        config.REPO_RESULTS,
        sep="\t",
        index=False,
    )

    # --------------------------------------------------------------
    # Report
    # --------------------------------------------------------------

    logging.info(
        "Search complete: repositories=%s requests=%s",
        len(df),
        client.total_requests,
    )

    print(
        f"Analysis interval              : "
        f"{config.SEARCH_START_DATE} "
        f"to {config.ANALYSIS_END_DATE}"
    )
    print(
        f"Repository-search FASTA hits  : "
        f"{len(df):,}"
    )
    print(
        f"GitHub API requests           : "
        f"{client.total_requests:,}"
    )
    print(
        f"Output                        : "
        f"{config.REPO_RESULTS}"
    )


if __name__ == "__main__":
    main()
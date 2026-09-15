"""Search GitHub code for FASTA-related programming interfaces and commands."""

from __future__ import annotations

import argparse
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
    "/search/code"
)

MAX_GITHUB_INDEXED_FILE_SIZE = 384_000

# GitHub exposes at most 1,000 results for a search query.
# Stay below that limit to avoid incomplete result sets.
SAFE_RESULT_LIMIT = 900


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Search GitHub code for "
            "FASTA-related programming interfaces "
            "and commands."
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
    """Load cached code-search results."""

    if not path.exists():
        return {"queries": {}}

    with path.open(
        encoding="utf-8",
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
    """Save code-search results to cache."""

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


def fetch_size_partition(
    query: str,
    min_size: int,
    max_size: int,
    client: GitHubClient,
) -> set[str]:
    """
    Exhaustively retrieve repositories for one file-size partition.

    Size ranges are recursively subdivided whenever a query approaches
    GitHub's 1,000-result search limit.
    """

    search_query = (
        f"{query} "
        f"size:{min_size}..{max_size}"
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
            "Code search failed: "
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
        if min_size >= max_size:
            raise RuntimeError(
                "Exact-size code partition "
                f"contains {total} results and "
                "cannot be safely exhausted below "
                "GitHub's search limit: "
                f"{search_query}"
            )

        midpoint = (
            min_size + max_size
        ) // 2

        left = fetch_size_partition(
            query,
            min_size,
            midpoint,
            client,
        )

        right = fetch_size_partition(
            query,
            midpoint + 1,
            max_size,
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
                    "Code pagination failed: "
                    f"status={status}, "
                    f"page={page}, "
                    f"query={search_query}"
                )

        for item in page_data.get(
            "items",
            [],
        ):
            repository = (
                item.get(
                    "repository",
                    {},
                )
                .get(
                    "full_name"
                )
            )

            if repository:
                repositories.add(
                    repository
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

    config.CODE_LOG.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    logging.basicConfig(
        filename=config.CODE_LOG,
        filemode="w",
        level=logging.INFO,
        format=(
            "%(asctime)s - "
            "%(levelname)s - "
            "%(message)s"
        ),
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
            config.CODE_CACHE
        )

    # --------------------------------------------------------------
    # Search
    # --------------------------------------------------------------

    client = GitHubClient(
        min_sleep=6.5,
        max_attempts=5,
        buffer=2.0,
    )

    results: dict[
        str,
        dict[str, int],
    ] = {}

    for label, query in tqdm(
        queries.CODE_SEARCH_QUERIES,
        desc="Code queries",
    ):
        signature = {
            "query": query,
            "min_size": 0,
            "max_size": (
                MAX_GITHUB_INDEXED_FILE_SIZE
            ),
            "safe_result_limit": (
                SAFE_RESULT_LIMIT
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
            repositories = fetch_size_partition(
                query,
                0,
                MAX_GITHUB_INDEXED_FILE_SIZE,
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
                config.CODE_CACHE,
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
        in queries.CODE_SEARCH_QUERIES
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

    invalid_values = (
        ~df[labels]
        .isin([0, 1])
    )

    if invalid_values.any().any():
        raise ValueError(
            "Code-search evidence contains "
            "values other than 0 or 1"
        )

    if (
        df[labels]
        .sum(axis=1)
        .eq(0)
        .any()
    ):
        raise ValueError(
            "Repository without code-search "
            "evidence found"
        )

    # --------------------------------------------------------------
    # Save
    # --------------------------------------------------------------

    config.CODE_RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        config.CODE_RESULTS,
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
        f"Code-search FASTA hits         : "
        f"{len(df):,}"
    )
    print(
        f"GitHub API requests           : "
        f"{client.total_requests:,}"
    )
    print(
        f"Output                        : "
        f"{config.CODE_RESULTS}"
    )


if __name__ == "__main__":
    main()
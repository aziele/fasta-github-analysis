import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from tqdm import tqdm

import config
from github_api import GitHubClient


URL = f"{config.GITHUB_API_BASE_URL}/repos"

def get_args():
    parser = argparse.ArgumentParser(
        description="Step 8: fetch metadata for candidate repositories"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore existing metadata cache and fetch all repositories again",
    )
    return parser.parse_args()


def empty_cache() -> dict:
    return {"repositories": {}}


def load_cache(path: Path) -> dict:
    if not path.exists():
        return empty_cache()

    with path.open() as f:
        cache = json.load(f)

    if "repositories" not in cache:
        raise ValueError(f"Invalid metadata cache: {path}")

    return cache


def save_cache(cache: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w") as f:
        json.dump(
            cache,
            f,
            indent=2,
            sort_keys=True,
        )


def metadata_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    args = get_args()

    config.require_github_token()

    config.METADATA_LOG.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=config.METADATA_LOG,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    df = pd.read_csv(config.MERGED_RESULTS, sep="\t")

    if "repo_name" not in df.columns:
        raise ValueError(f"Missing repo_name column in {config.MERGED_RESULTS}")

    df["repo_name"] = (
        df["repo_name"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    if df["repo_name"].duplicated().any():
        raise ValueError(
            f"Input contains duplicated repository names: {config.MERGED_RESULTS}"
        )

    if args.refresh:
        cache = empty_cache()
    else:
        cache = load_cache(config.METADATA_CACHE)

    repo_cache = cache["repositories"]

    client = GitHubClient(
        min_sleep=0.75,
        max_attempts=5,
        buffer=2.0,
    )

    repositories = sorted(df["repo_name"].unique())

    missing = [
        repo_name
        for repo_name in repositories
        if repo_name not in repo_cache
    ]

    print(f"Candidate repositories: {len(repositories):,}")
    print(f"Already cached: {len(repositories) - len(missing):,}")
    print(f"To retrieve: {len(missing):,}")

    failures = []

    for i, repo_name in enumerate(
        tqdm(missing, desc="Metadata", unit="repo"),
        start=1,
    ):
        status, data = client.get(
            f"{URL}/{repo_name}",
            config.github_headers(),
            params={},
        )

        retrieved_at = metadata_timestamp()

        if status == 200 and isinstance(data, dict):
            created = data.get("created_at")
            updated = data.get("updated_at")
            pushed = data.get("pushed_at")

            is_fork = bool(data.get("fork"))

            parent = data.get("parent") or {}
            source = data.get("source") or {}

            owner = data.get("owner") or {}

            repo_cache[repo_name] = {
                "api_status": 200,
                "accessible": 1,

                "canonical_name": data.get("full_name"),

                "date_created": created[:10] if created else None,
                "date_updated": updated[:10] if updated else None,
                "date_pushed": pushed[:10] if pushed else None,

                "description": data.get("description"),

                "stars": data.get("stargazers_count", 0),
                "forks_count": data.get("forks_count", 0),

                "language": data.get("language"),
                "topics": ";".join(data.get("topics") or []),

                "size_kb": data.get("size"),

                "owner_type": owner.get("type"),

                "is_fork": int(is_fork),

                "parent_name": (
                    parent.get("full_name")
                    if is_fork
                    else None
                ),

                "source_name": (
                    source.get("full_name")
                    if is_fork
                    else None
                ),

                "archived": int(bool(data.get("archived"))),
                "disabled": int(bool(data.get("disabled"))),

                "metadata_retrieved_at": retrieved_at,
            }

        elif status == 404:
            repo_cache[repo_name] = {
                "api_status": 404,
                "accessible": 0,

                "canonical_name": None,

                "date_created": None,
                "date_updated": None,
                "date_pushed": None,

                "description": None,

                "stars": None,
                "forks_count": None,

                "language": None,
                "topics": None,

                "size_kb": None,

                "owner_type": None,

                "is_fork": None,
                "parent_name": None,
                "source_name": None,

                "archived": None,
                "disabled": None,

                "metadata_retrieved_at": retrieved_at,
            }

        else:
            failures.append((repo_name, status))

            logging.error(
                "Metadata failure repo=%s status=%s",
                repo_name,
                status,
            )

        if i % 100 == 0:
            save_cache(cache, config.METADATA_CACHE)

    save_cache(cache, config.METADATA_CACHE)

    if failures:
        preview = ", ".join(
            f"{repo_name} ({status})"
            for repo_name, status in failures[:10]
        )

        raise RuntimeError(
            f"Metadata retrieval incomplete for "
            f"{len(failures)} repositories. "
            f"No final metadata table was written. "
            f"First failures: {preview}"
        )

    meta_df = pd.DataFrame.from_dict(
        repo_cache,
        orient="index",
    )

    meta_df.index.name = "repo_name"
    meta_df.reset_index(inplace=True)

    final_df = df.merge(
        meta_df,
        on="repo_name",
        how="left",
        validate="one_to_one",
    )

    config.METADATA_RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_df.to_csv(
        config.METADATA_RESULTS,
        sep="\t",
        index=False,
    )

    accessible = int(
        (final_df["accessible"] == 1).sum()
    )

    inaccessible = int(
        (final_df["accessible"] == 0).sum()
    )

    accessible_nonfork = int(
        (
            (final_df["accessible"] == 1)
            & (final_df["is_fork"] == 0)
        ).sum()
    )

    accessible_fork = int(
        (
            (final_df["accessible"] == 1)
            & (final_df["is_fork"] == 1)
        ).sum()
    )

    print()
    print(f"Discovered repositories: {len(final_df):,}")
    print(f"Currently accessible: {accessible:,}")
    print(f"Currently inaccessible: {inaccessible:,}")
    print(f"Accessible non-forks: {accessible_nonfork:,}")
    print(f"Accessible forks: {accessible_fork:,}")
    print(f"Output: {config.METADATA_RESULTS}")


if __name__ == "__main__":
    main()
"""Filter known lexical false positives from GitHub code-search results."""

from __future__ import annotations

import re

import pandas as pd

import config


LEXICAL_COLLISION_RE = re.compile(
    r"fastapi|fastai|fastalign",
    re.IGNORECASE,
)


# Queries for which lexical FASTA false positives were observed.
SUSCEPTIBLE_QUERIES = {
    "code_py_fastaio",
    "code_emboss_seqret_fasta",
}


def main() -> None:
    # --------------------------------------------------------------
    # Load
    # --------------------------------------------------------------

    if not config.CODE_RESULTS.exists():
        raise FileNotFoundError(
            f"Missing required input: {config.CODE_RESULTS}"
        )

    df = pd.read_csv(
        config.CODE_RESULTS,
        sep="\t",
    )

    if "repo_name" not in df.columns:
        raise ValueError(
            "Missing required column: repo_name"
        )

    if not df["repo_name"].is_unique:
        raise ValueError(
            "repo_name is not unique"
        )

    code_columns = [
        column
        for column in df.columns
        if column.startswith("code_")
    ]

    if not code_columns:
        raise ValueError(
            "No code-search evidence columns found"
        )

    missing_susceptible = (
        SUSCEPTIBLE_QUERIES
        - set(code_columns)
    )

    if missing_susceptible:
        raise ValueError(
            "Missing susceptible query column(s): "
            + ", ".join(
                sorted(missing_susceptible)
            )
        )

    # --------------------------------------------------------------
    # Normalize evidence
    # --------------------------------------------------------------

    df[code_columns] = (
        df[code_columns]
        .fillna(0)
        .astype(int)
    )

    invalid_values = (
        ~df[code_columns]
        .isin([0, 1])
    )

    if invalid_values.any().any():
        raise ValueError(
            "Code-search evidence columns contain "
            "values other than 0/1"
        )

    hit_count = (
        df[code_columns]
        .sum(axis=1)
    )

    if hit_count.eq(0).any():
        raise ValueError(
            f"{hit_count.eq(0).sum():,} repositories "
            "have no code-search evidence"
        )

    # --------------------------------------------------------------
    # Identify known lexical collisions
    # --------------------------------------------------------------

    repo_basename = (
        df["repo_name"]
        .fillna("")
        .astype(str)
        .str.rsplit("/", n=1)
        .str[-1]
    )

    lexical_collision = (
        repo_basename
        .str.contains(
            LEXICAL_COLLISION_RE,
            na=False,
        )
    )

    susceptible_columns = sorted(
        SUSCEPTIBLE_QUERIES
    )

    susceptible_hit_count = (
        df[susceptible_columns]
        .sum(axis=1)
    )

    # Exclude only repositories found by exactly one code-search
    # query when that query is one of the known susceptible searches
    # and the repository name contains a known lexical collision.
    susceptible_only = (
        hit_count.eq(1)
        & susceptible_hit_count.eq(1)
    )

    exclude = (
        lexical_collision
        & susceptible_only
    )

    # --------------------------------------------------------------
    # Split
    # --------------------------------------------------------------

    filtered = df.loc[
        ~exclude
    ].copy()

    excluded = df.loc[
        exclude
    ].copy()

    excluded["exclusion_reason"] = (
        "lexical FASTA collision in single "
        "susceptible code-search query"
    )

    # --------------------------------------------------------------
    # Validate
    # --------------------------------------------------------------

    if not filtered["repo_name"].is_unique:
        raise ValueError(
            "Filtered repositories are not unique"
        )

    if not excluded["repo_name"].is_unique:
        raise ValueError(
            "Excluded repositories are not unique"
        )

    if (
        len(filtered)
        + len(excluded)
        != len(df)
    ):
        raise ValueError(
            "Filtered and excluded rows do not "
            "reconstruct input"
        )

    overlap = (
        set(filtered["repo_name"])
        & set(excluded["repo_name"])
    )

    if overlap:
        raise ValueError(
            f"{len(overlap)} repositories occur "
            "in both outputs"
        )

    if not excluded.empty:
        excluded_basename = (
            excluded["repo_name"]
            .fillna("")
            .astype(str)
            .str.rsplit("/", n=1)
            .str[-1]
        )

        excluded_collision = (
            excluded_basename
            .str.contains(
                LEXICAL_COLLISION_RE,
                na=False,
            )
        )

        if not excluded_collision.all():
            raise ValueError(
                "Excluded repository without "
                "lexical collision"
            )

        excluded_hit_count = (
            excluded[code_columns]
            .sum(axis=1)
        )

        if not excluded_hit_count.eq(1).all():
            raise ValueError(
                "Excluded repository has more than "
                "one code-search hit"
            )

        excluded_susceptible_count = (
            excluded[susceptible_columns]
            .sum(axis=1)
        )

        if not (
            excluded_susceptible_count
            .eq(1)
            .all()
        ):
            raise ValueError(
                "Excluded repository was not found "
                "solely by a susceptible query"
            )

    # --------------------------------------------------------------
    # Deterministic ordering
    # --------------------------------------------------------------

    filtered = (
        filtered
        .sort_values(
            "repo_name",
            key=lambda x: x.str.lower(),
        )
        .reset_index(drop=True)
    )

    excluded = (
        excluded
        .sort_values(
            "repo_name",
            key=lambda x: x.str.lower(),
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------------
    # Save
    # --------------------------------------------------------------

    config.FILTERED_CODE_RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    filtered.to_csv(
        config.FILTERED_CODE_RESULTS,
        sep="\t",
        index=False,
    )

    excluded.to_csv(
        config.EXCLUDED_CODE_RESULTS,
        sep="\t",
        index=False,
    )

    # --------------------------------------------------------------
    # Report
    # --------------------------------------------------------------

    print(
        f"Input repositories             : "
        f"{len(df):,}"
    )
    print(
        f"Lexical-collision repositories : "
        f"{lexical_collision.sum():,}"
    )
    print(
        f"Single susceptible-query hits  : "
        f"{susceptible_only.sum():,}"
    )
    print(
        f"Repositories excluded          : "
        f"{exclude.sum():,}"
    )
    print(
        f"Repositories retained          : "
        f"{len(filtered):,}"
    )

    if not excluded.empty:
        print(
            "\nExcluded repositories:"
        )

        for _, row in excluded.iterrows():
            hits = [
                column
                for column in code_columns
                if row[column] == 1
            ]

            print(
                f"  {row['repo_name']} "
                f"({', '.join(hits)})"
            )

    print()
    print(
        f"Saved repositories             : "
        f"{config.FILTERED_CODE_RESULTS}"
    )
    print(
        f"Saved exclusions               : "
        f"{config.EXCLUDED_CODE_RESULTS}"
    )


if __name__ == "__main__":
    main()
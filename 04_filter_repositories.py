"""Filter direct GitHub repository-search results."""

from __future__ import annotations

import re

import pandas as pd

import config


FASTA_NAME_RE = re.compile(
    r"""
    (?:^|[-_.])fasta(?:$|[-_.]|\d)
    |
    fasta$
    """,
    re.IGNORECASE | re.VERBOSE,
)


LEXICAL_COLLISION_RE = re.compile(
    r"fastapi|fastai|fastalign",
    re.IGNORECASE,
)


def flag_is_true(value) -> bool:
    """Interpret common serialized truth values as booleans."""

    if pd.isna(value):
        return False

    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
        }

    return bool(value)


def main() -> None:
    # --------------------------------------------------------------
    # Load
    # --------------------------------------------------------------

    if not config.REPO_RESULTS.exists():
        raise FileNotFoundError(
            f"Missing required input: {config.REPO_RESULTS}"
        )

    df = pd.read_csv(
        config.REPO_RESULTS,
        sep="\t",
    )

    required_columns = {
        "repo_name",
        "repo_fasta",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(sorted(missing))
        )

    targeted_columns = [
        column
        for column in df.columns
        if column.startswith("repo_")
        and column not in {
            "repo_name",
            "repo_fasta",
        }
    ]

    if not targeted_columns:
        raise ValueError(
            "No targeted repository-search columns found"
        )

    evidence_columns = [
        "repo_fasta",
        *targeted_columns,
    ]

    # Normalize evidence columns to booleans for filtering.
    for column in evidence_columns:
        df[column] = df[column].map(
            flag_is_true
        )

    print(
        f"Input repositories             : "
        f"{len(df):,}"
    )

    # --------------------------------------------------------------
    # 1. Identify targeted-query repositories
    # --------------------------------------------------------------

    targeted_hit = df[
        targeted_columns
    ].any(axis=1)

    print(
        f"Targeted-query repositories    : "
        f"{targeted_hit.sum():,}"
    )

    # --------------------------------------------------------------
    # 2. Identify repositories found only by broad `fasta`
    # --------------------------------------------------------------

    broad_hit = df["repo_fasta"]

    broad_only = (
        broad_hit
        & ~targeted_hit
    )

    print(
        f"Broad 'fasta'-only             : "
        f"{broad_only.sum():,}"
    )

    # --------------------------------------------------------------
    # 3. Analyze repository names
    # --------------------------------------------------------------

    repo_basename = (
        df["repo_name"]
        .fillna("")
        .astype(str)
        .str.rsplit("/", n=1)
        .str[-1]
    )

    valid_fasta_name = (
        repo_basename
        .str.contains(
            FASTA_NAME_RE,
            na=False,
        )
    )

    lexical_collision = (
        repo_basename
        .str.contains(
            LEXICAL_COLLISION_RE,
            na=False,
        )
    )

    # Known lexical collisions such as FastAPI, fastai or fastalign
    # do not count as independent FASTA-name evidence unless the
    # repository name also contains a valid FASTA-like token.
    lexical_false_positive = (
        lexical_collision
        & ~valid_fasta_name
    )

    print(
        f"Lexical-collision repositories : "
        f"{lexical_collision.sum():,}"
    )
    print(
        f"Lexical false positives        : "
        f"{lexical_false_positive.sum():,}"
    )

    # --------------------------------------------------------------
    # 4. Rescue plausible broad-only FASTA repositories by name
    # --------------------------------------------------------------

    rescued = (
        broad_only
        & valid_fasta_name
    )

    broad_excluded = (
        broad_only
        & ~valid_fasta_name
    )

    print(
        f"Broad-only rescued by name     : "
        f"{rescued.sum():,}"
    )
    print(
        f"Broad-only excluded            : "
        f"{broad_excluded.sum():,}"
    )

    # --------------------------------------------------------------
    # 5. Apply Step 04 exclusion rule
    # --------------------------------------------------------------

    retained = df.loc[
        ~broad_excluded
    ].copy()

    excluded = df.loc[
        broad_excluded
    ].copy()

    excluded["exclusion_reason"] = (
        "broad_fasta_without_fasta_name"
    )

    lexical_reason_mask = (
        lexical_false_positive.loc[
            excluded.index
        ]
    )

    excluded.loc[
        lexical_reason_mask,
        "exclusion_reason",
    ] = "fasta_lexical_collision"

    print(
        f"Repositories retained          : "
        f"{len(retained):,}"
    )

    # --------------------------------------------------------------
    # 6. Validate
    # --------------------------------------------------------------

    if df["repo_name"].duplicated().any():
        duplicates = (
            df.loc[
                df["repo_name"].duplicated(
                    keep=False
                ),
                "repo_name",
            ]
            .drop_duplicates()
            .tolist()
        )

        raise ValueError(
            "Duplicate repository names in input: "
            f"{duplicates[:10]}"
        )

    if retained["repo_name"].duplicated().any():
        raise ValueError(
            "Duplicate repository names remain "
            "in filtered results"
        )

    if excluded["repo_name"].duplicated().any():
        raise ValueError(
            "Duplicate repository names occur "
            "in excluded results"
        )

    if (
        len(retained)
        + len(excluded)
        != len(df)
    ):
        raise ValueError(
            "Filtered and excluded repository counts "
            "do not sum to input count"
        )

    overlap = (
        set(retained["repo_name"])
        & set(excluded["repo_name"])
    )

    if overlap:
        raise ValueError(
            "Repositories occur in both retained "
            "and excluded outputs: "
            f"{sorted(overlap)[:10]}"
        )

    broad_excluded_names = set(
        df.loc[
            broad_excluded,
            "repo_name",
        ]
    )

    actual_excluded_names = set(
        excluded["repo_name"]
    )

    missing_broad_excluded = (
        broad_excluded_names
        - actual_excluded_names
    )

    if missing_broad_excluded:
        raise ValueError(
            f"{len(missing_broad_excluded)} broad-only "
            "repositories that failed the rescue rule "
            "were retained"
        )

    retained_names = set(
        retained["repo_name"]
    )

    rescued_names = set(
        df.loc[
            rescued,
            "repo_name",
        ]
    )

    missing_rescued = (
        rescued_names
        - retained_names
    )

    if missing_rescued:
        raise ValueError(
            f"{len(missing_rescued)} rescued repositories "
            "were incorrectly excluded: "
            f"{sorted(missing_rescued)[:10]}"
        )

    # Step 04 retains every repository found by at least one
    # targeted query. Lexical-collision adjudication happens later.
    expected_targeted_retained = set(
        df.loc[
            targeted_hit,
            "repo_name",
        ]
    )

    missing_targeted = (
        expected_targeted_retained
        - retained_names
    )

    if missing_targeted:
        raise ValueError(
            f"{len(missing_targeted)} targeted-query "
            "repositories were incorrectly excluded: "
            f"{sorted(missing_targeted)[:10]}"
        )

    # --------------------------------------------------------------
    # 7. Deterministic ordering
    # --------------------------------------------------------------

    retained = (
        retained
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

    # Store evidence flags as 0/1 in intermediate TSV files.
    retained[evidence_columns] = (
        retained[evidence_columns]
        .astype(int)
    )

    excluded[evidence_columns] = (
        excluded[evidence_columns]
        .astype(int)
    )

    # --------------------------------------------------------------
    # 8. Save
    # --------------------------------------------------------------

    config.FILTERED_REPO_RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    retained.to_csv(
        config.FILTERED_REPO_RESULTS,
        sep="\t",
        index=False,
    )

    excluded.to_csv(
        config.EXCLUDED_REPO_RESULTS,
        sep="\t",
        index=False,
    )

    print()
    print(
        f"Saved repositories             : "
        f"{config.FILTERED_REPO_RESULTS}"
    )
    print(
        f"Saved exclusions               : "
        f"{config.EXCLUDED_REPO_RESULTS}"
    )


if __name__ == "__main__":
    main()
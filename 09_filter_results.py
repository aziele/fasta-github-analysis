"""Apply final repository filtering and manual review."""

from __future__ import annotations

import re
import sys

import pandas as pd

import config
import queries


LEXICAL_COLLISION_RE = re.compile(
    r"fastapi|fastai|fastalign",
    re.IGNORECASE,
)

EXPLICIT_FASTA_RE = re.compile(
    r"(?<![a-z0-9])fasta(?![a-z0-9])",
    re.IGNORECASE,
)

VALID_REVIEW_DECISIONS = {
    "include",
    "exclude",
}


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


def repository_query_columns() -> list[str]:
    """Return repository-search evidence columns."""

    return [
        label
        for label, _
        in queries.REPOSITORY_SEARCH_QUERIES
    ]


def code_query_columns() -> list[str]:
    """Return code-search evidence columns."""

    return [
        label
        for label, _
        in queries.CODE_SEARCH_QUERIES
    ]


def get_evidence_columns(
    df: pd.DataFrame,
) -> list[str]:
    """Return search and source-evidence columns present in the table."""

    expected = [
        "bigquery_hit",
        "repo_hit",
        "code_hit",
        *repository_query_columns(),
        *code_query_columns(),
    ]

    return [
        column
        for column in expected
        if column in df.columns
    ]


def get_specific_repo_columns(
    df: pd.DataFrame,
) -> list[str]:
    """
    Return targeted repository-search evidence columns other than
    the unrestricted broad `fasta` query.
    """

    return [
        column
        for column in repository_query_columns()
        if (
            column != queries.BROAD_REPOSITORY_QUERY
            and column in df.columns
        )
    ]


def get_repository_basename(
    df: pd.DataFrame,
) -> pd.Series:
    """Return repository basename from owner/repository."""

    return (
        df["repo_name"]
        .fillna("")
        .astype(str)
        .str.rsplit("/", n=1)
        .str[-1]
    )


def get_context_text(
    df: pd.DataFrame,
) -> pd.Series:
    """Combine repository basename, description, and topics."""

    repo_name = get_repository_basename(df)

    description = (
        df["description"]
        .fillna("")
        .astype(str)
        if "description" in df.columns
        else pd.Series(
            "",
            index=df.index,
            dtype=str,
        )
    )

    topics = (
        df["topics"]
        .fillna("")
        .astype(str)
        if "topics" in df.columns
        else pd.Series(
            "",
            index=df.index,
            dtype=str,
        )
    )

    return (
        repo_name
        + " "
        + description
        + " "
        + topics
    )


def get_explicit_fasta_context(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Identify a standalone FASTA mention after masking known
    lexical-collision strings.
    """

    context = get_context_text(df)

    context_without_collisions = (
        context.str.replace(
            LEXICAL_COLLISION_RE,
            " ",
            regex=True,
        )
    )

    return (
        context_without_collisions
        .str.contains(
            EXPLICIT_FASTA_RE,
            na=False,
        )
    )


def merge_canonical_repositories(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge repository aliases resolving to the same current GitHub repository.

    Evidence columns are combined by logical OR. Metadata are taken from
    the first row in each canonical group. Original discovery names are
    retained in `search_names`.
    """

    df = df.copy()

    evidence_columns = get_evidence_columns(
        df
    )

    for column in evidence_columns:
        df[column] = df[column].map(
            flag_is_true
        )

    search_names = (
        df.groupby(
            "canonical_name",
            sort=False,
        )["repo_name"]
        .agg(
            lambda values: "; ".join(
                sorted(
                    {
                        str(value)
                        for value in values
                        if pd.notna(value)
                    },
                    key=str.lower,
                )
            )
        )
        .rename("search_names")
    )

    metadata_columns = [
        column
        for column in df.columns
        if column not in evidence_columns
        and column not in {
            "repo_name",
            "canonical_name",
        }
    ]

    metadata = (
        df.drop_duplicates(
            subset="canonical_name",
            keep="first",
        )
        .set_index(
            "canonical_name"
        )[metadata_columns]
    )

    evidence = (
        df.groupby(
            "canonical_name",
            sort=False,
        )[evidence_columns]
        .any()
    )

    out = pd.concat(
        [
            search_names,
            metadata,
            evidence,
        ],
        axis=1,
    ).reset_index()

    out = out.rename(
        columns={
            "canonical_name": "repo_name",
        }
    )

    original_columns = list(
        df.columns
    )

    final_columns = [
        "repo_name",
        "search_names",
    ]

    for column in original_columns:
        if column in {
            "repo_name",
            "canonical_name",
        }:
            continue

        if column not in final_columns:
            final_columns.append(
                column
            )

    return out[
        final_columns
    ]


def make_review_table(
    broad_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construct the table used for manual review of broad `fasta`-only hits.
    """

    preferred_columns = [
        "repo_name",
        "description",
        "topics",
        "language",
        "stars",
        "archived",
        "is_fork",
        "search_names",
    ]

    columns = [
        column
        for column in preferred_columns
        if column in broad_df.columns
    ]

    review = broad_df[
        columns
    ].copy()

    review.insert(
        1,
        "decision",
        "",
    )

    review.insert(
        2,
        "note",
        "",
    )

    return (
        review
        .sort_values(
            "repo_name",
            key=lambda x: x.str.lower(),
        )
        .reset_index(drop=True)
    )


def load_review(
    expected_repo_names: set[str],
) -> pd.DataFrame:
    """Load and validate the completed manual-review table."""

    if not config.BROAD_REVIEW.exists():
        raise FileNotFoundError(
            f"Missing review file: {config.BROAD_REVIEW}"
        )

    review = pd.read_csv(
        config.BROAD_REVIEW,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    required_columns = {
        "repo_name",
        "decision",
    }

    missing = (
        required_columns
        - set(review.columns)
    )

    if missing:
        raise ValueError(
            "Missing columns in broad-review file: "
            + ", ".join(
                sorted(missing)
            )
        )

    review["repo_name"] = (
        review["repo_name"]
        .astype(str)
        .str.strip()
    )

    review["decision"] = (
        review["decision"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    if review["repo_name"].duplicated().any():
        duplicates = (
            review.loc[
                review["repo_name"].duplicated(
                    keep=False
                ),
                "repo_name",
            ]
            .drop_duplicates()
            .tolist()
        )

        raise ValueError(
            "Duplicate repositories in broad-review file: "
            + ", ".join(
                duplicates[:10]
            )
        )

    review_repo_names = set(
        review["repo_name"]
    )

    missing_repositories = (
        expected_repo_names
        - review_repo_names
    )

    unexpected_repositories = (
        review_repo_names
        - expected_repo_names
    )

    if missing_repositories:
        raise ValueError(
            f"Broad-review file is missing "
            f"{len(missing_repositories):,} repositories. "
            f"Examples: "
            f"{sorted(missing_repositories)[:10]}"
        )

    if unexpected_repositories:
        raise ValueError(
            f"Broad-review file contains "
            f"{len(unexpected_repositories):,} unexpected repositories. "
            f"Examples: "
            f"{sorted(unexpected_repositories)[:10]}"
        )

    invalid_decisions = (
        ~review[
            "decision"
        ].isin(
            VALID_REVIEW_DECISIONS
        )
    )

    if invalid_decisions.any():
        bad = review.loc[
            invalid_decisions,
            [
                "repo_name",
                "decision",
            ],
        ]

        raise ValueError(
            f"{len(bad):,} broad-review decisions are "
            f"missing or invalid. "
            f"Allowed values: "
            f"{sorted(VALID_REVIEW_DECISIONS)}. "
            f"Examples: "
            f"{bad.head(10).to_dict('records')}"
        )

    return review


def convert_evidence_to_int(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Store evidence flags as 0/1 in intermediate TSV files."""

    df = df.copy()

    evidence_columns = get_evidence_columns(
        df
    )

    for column in evidence_columns:
        df[column] = (
            df[column]
            .map(flag_is_true)
            .astype(int)
        )

    return df


def main() -> None:
    # --------------------------------------------------------------
    # Load
    # --------------------------------------------------------------

    if not config.METADATA_RESULTS.exists():
        raise FileNotFoundError(
            f"Missing required input: {config.METADATA_RESULTS}"
        )

    df = pd.read_csv(
        config.METADATA_RESULTS,
        sep="\t",
    )

    required_columns = {
        "repo_name",
        "canonical_name",
        "accessible",
        "bigquery_hit",
        "repo_hit",
        "repo_fasta",
        "code_hit",
    }

    missing = (
        required_columns
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(
                sorted(missing)
            )
        )

    specific_repo_columns = (
        get_specific_repo_columns(
            df
        )
    )

    if not specific_repo_columns:
        raise ValueError(
            "No targeted repository-search "
            "evidence columns found"
        )

    print(
        f"Input repositories             : "
        f"{len(df):,}"
    )

    # --------------------------------------------------------------
    # 1. Diagnostic: targeted lexical collisions before alias merging
    # --------------------------------------------------------------

    original_basename = (
        get_repository_basename(
            df
        )
    )

    original_specific_hit = (
        df[specific_repo_columns]
        .apply(
            lambda row: any(
                flag_is_true(value)
                for value in row
            ),
            axis=1,
        )
    )

    original_targeted_collision = (
        original_specific_hit
        & original_basename.str.contains(
            LEXICAL_COLLISION_RE,
            na=False,
        )
    )

    print(
        f"Targeted lexical collisions    : "
        f"{original_targeted_collision.sum():,}"
    )

    # --------------------------------------------------------------
    # 2. Exclude inaccessible repositories
    # --------------------------------------------------------------

    inaccessible_mask = (
        ~df["accessible"].map(
            flag_is_true
        )
    )

    inaccessible = df.loc[
        inaccessible_mask
    ].copy()

    inaccessible[
        "exclusion_reason"
    ] = "inaccessible"

    retained = df.loc[
        ~inaccessible_mask
    ].copy()

    print(
        f"Inaccessible repositories      : "
        f"{len(inaccessible):,}"
    )

    # --------------------------------------------------------------
    # 3. Merge aliases resolving to the same canonical repository
    # --------------------------------------------------------------

    if retained[
        "canonical_name"
    ].isna().any():
        raise ValueError(
            "Accessible repository without canonical_name"
        )

    canonical_count = (
        retained[
            "canonical_name"
        ].nunique()
    )

    duplicate_rows = retained[
        retained[
            "canonical_name"
        ].duplicated(
            keep=False
        )
    ]

    duplicated_canonical = (
        duplicate_rows[
            "canonical_name"
        ].nunique()
    )

    print(
        f"Canonical repositories         : "
        f"{canonical_count:,}"
    )
    print(
        f"Rows in canonical duplicates   : "
        f"{len(duplicate_rows):,}"
    )
    print(
        f"Duplicated canonical repos     : "
        f"{duplicated_canonical:,}"
    )

    before_merge = len(
        retained
    )

    retained = (
        merge_canonical_repositories(
            retained
        )
    )

    merged_aliases = (
        before_merge
        - len(retained)
    )

    print(
        f"Repository aliases merged      : "
        f"{merged_aliases:,}"
    )

    # --------------------------------------------------------------
    # 4. Reconstruct evidence classes
    # --------------------------------------------------------------

    bigquery_hit = (
        retained["bigquery_hit"]
        .map(flag_is_true)
    )

    code_hit = (
        retained["code_hit"]
        .map(flag_is_true)
    )

    broad_fasta_hit = (
        retained["repo_fasta"]
        .map(flag_is_true)
    )

    specific_repo_hit = (
        retained[
            specific_repo_columns
        ]
        .apply(
            lambda row: any(
                flag_is_true(value)
                for value in row
            ),
            axis=1,
        )
    )

    independent_evidence = (
        bigquery_hit
        | code_hit
    )

    repository_basename = (
        get_repository_basename(
            retained
        )
    )

    lexical_collision_name = (
        repository_basename
        .str.contains(
            LEXICAL_COLLISION_RE,
            na=False,
        )
    )

    targeted_lexical_collision = (
        specific_repo_hit
        & lexical_collision_name
    )

    clean_targeted_hit = (
        specific_repo_hit
        & ~targeted_lexical_collision
    )

    strong_evidence = (
        independent_evidence
        | clean_targeted_hit
    )

    # --------------------------------------------------------------
    # 5. Identify broad unrestricted `fasta`-only candidates
    # --------------------------------------------------------------

    broad_only = (
        broad_fasta_hit
        & ~independent_evidence
        & ~specific_repo_hit
    )

    broad_candidates = retained.loc[
        broad_only
    ].copy()

    print(
        f"Broad 'fasta'-only candidates  : "
        f"{len(broad_candidates):,}"
    )

    # --------------------------------------------------------------
    # 6. Create or load manual review
    # --------------------------------------------------------------

    if not config.BROAD_REVIEW.exists():
        review = make_review_table(
            broad_candidates
        )

        config.BROAD_REVIEW.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        review.to_csv(
            config.BROAD_REVIEW,
            sep="\t",
            index=False,
        )

        print()
        print(
            f"Broad-review template created  : "
            f"{config.BROAD_REVIEW}"
        )
        print(
            f"Repositories to review         : "
            f"{len(review):,}"
        )
        print()
        print(
            "Fill the 'decision' column with "
            "'include' or 'exclude', then rerun Step 09."
        )

        sys.exit(0)

    review = load_review(
        set(
            broad_candidates[
                "repo_name"
            ]
        )
    )

    include_names = set(
        review.loc[
            review["decision"] == "include",
            "repo_name",
        ]
    )

    exclude_names = set(
        review.loc[
            review["decision"] == "exclude",
            "repo_name",
        ]
    )

    broad_only_included = (
        broad_only
        & retained[
            "repo_name"
        ].isin(
            include_names
        )
    )

    broad_only_excluded = (
        broad_only
        & retained[
            "repo_name"
        ].isin(
            exclude_names
        )
    )

    print(
        f"Broad-only included by review  : "
        f"{broad_only_included.sum():,}"
    )
    print(
        f"Broad-only excluded by review  : "
        f"{broad_only_excluded.sum():,}"
    )

    if (
        broad_only_included
        & broad_only_excluded
    ).any():
        raise ValueError(
            "Broad-review include and exclude "
            "sets overlap"
        )

    if not (
        (
            broad_only_included
            | broad_only_excluded
        )
        == broad_only
    ).all():
        raise ValueError(
            "Broad-review decisions do not "
            "partition broad-only candidates"
        )

    # --------------------------------------------------------------
    # 7. Handle known targeted lexical collisions
    # --------------------------------------------------------------

    collision_candidate = (
        targeted_lexical_collision
        & ~independent_evidence
    )

    explicit_fasta_context = (
        get_explicit_fasta_context(
            retained
        )
    )

    collision_corroborated = (
        collision_candidate
        & explicit_fasta_context
    )

    collision_excluded = (
        collision_candidate
        & ~explicit_fasta_context
    )

    print(
        f"Lexical-collision candidates   : "
        f"{collision_candidate.sum():,}"
    )
    print(
        f"Collision hits corroborated    : "
        f"{collision_corroborated.sum():,}"
    )
    print(
        f"Collision hits excluded        : "
        f"{collision_excluded.sum():,}"
    )

    if (
        collision_corroborated
        & collision_excluded
    ).any():
        raise ValueError(
            "Collision corroborated and excluded "
            "sets overlap"
        )

    if not (
        (
            collision_corroborated
            | collision_excluded
        )
        == collision_candidate
    ).all():
        raise ValueError(
            "Collision decisions do not partition "
            "collision candidates"
        )

    # --------------------------------------------------------------
    # 8. Final retained and excluded populations
    # --------------------------------------------------------------

    final_retain = (
        strong_evidence
        | broad_only_included
        | collision_corroborated
    )

    final_exclude = (
        broad_only_excluded
        | collision_excluded
    )

    if (
        final_retain
        & final_exclude
    ).any():
        raise ValueError(
            "Retained and excluded repository "
            "classes overlap"
        )

    unresolved = (
        ~final_retain
        & ~final_exclude
    )

    if unresolved.any():
        bad = retained.loc[
            unresolved,
            "repo_name",
        ].tolist()

        raise ValueError(
            f"{len(bad):,} canonical repositories "
            f"were not classified: "
            f"{bad[:10]}"
        )

    final_retained = retained.loc[
        final_retain
    ].copy()

    broad_excluded_df = retained.loc[
        broad_only_excluded
    ].copy()

    broad_excluded_df[
        "exclusion_reason"
    ] = (
        "excluded after review of broad "
        "'fasta'-only search hit"
    )

    collision_excluded_df = retained.loc[
        collision_excluded
    ].copy()

    collision_excluded_df[
        "exclusion_reason"
    ] = (
        "uncorroborated lexical-collision "
        "repository-search hit"
    )

    excluded = pd.concat(
        [
            inaccessible,
            broad_excluded_df,
            collision_excluded_df,
        ],
        ignore_index=True,
        sort=False,
    )

    print(
        f"Strong-evidence repositories   : "
        f"{strong_evidence.sum():,}"
    )
    print(
        f"Repositories after filtering   : "
        f"{len(final_retained):,}"
    )

    # --------------------------------------------------------------
    # 9. Validation
    # --------------------------------------------------------------

    if final_retained[
        "repo_name"
    ].duplicated().any():
        raise ValueError(
            "Duplicate canonical repository "
            "names remain"
        )

    source_columns = [
        "bigquery_hit",
        "repo_hit",
        "code_hit",
    ]

    has_evidence = (
        final_retained[
            source_columns
        ]
        .apply(
            lambda row: any(
                flag_is_true(value)
                for value in row
            ),
            axis=1,
        )
    )

    if not has_evidence.all():
        bad = final_retained.loc[
            ~has_evidence,
            "repo_name",
        ].tolist()

        raise ValueError(
            f"{len(bad):,} repositories have no "
            f"FASTA evidence: "
            f"{bad[:10]}"
        )

    expected_final = (
        strong_evidence.sum()
        + broad_only_included.sum()
        + collision_corroborated.sum()
    )

    if len(final_retained) != expected_final:
        raise ValueError(
            "Final retained repository count "
            "does not match evidence classes"
        )

    expected_excluded = (
        len(inaccessible)
        + broad_only_excluded.sum()
        + collision_excluded.sum()
    )

    if len(excluded) != expected_excluded:
        raise ValueError(
            "Final excluded repository count "
            "does not match exclusion classes"
        )

    # --------------------------------------------------------------
    # 10. Convert evidence flags back to 0/1
    # --------------------------------------------------------------

    final_retained = (
        convert_evidence_to_int(
            final_retained
        )
    )

    excluded = (
        convert_evidence_to_int(
            excluded
        )
    )

    # --------------------------------------------------------------
    # 11. Deterministic ordering
    # --------------------------------------------------------------

    final_retained = (
        final_retained
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
    # 12. Save
    # --------------------------------------------------------------

    config.FILTERED_RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_retained.to_csv(
        config.FILTERED_RESULTS,
        sep="\t",
        index=False,
    )

    excluded.to_csv(
        config.EXCLUDED_RESULTS,
        sep="\t",
        index=False,
    )

    print()
    print(
        f"Final canonical repositories   : "
        f"{len(final_retained):,}"
    )
    print(
        f"Excluded repositories          : "
        f"{len(excluded):,}"
    )
    print(
        f"Saved repositories             : "
        f"{config.FILTERED_RESULTS}"
    )
    print(
        f"Saved exclusions               : "
        f"{config.EXCLUDED_RESULTS}"
    )


if __name__ == "__main__":
    main()
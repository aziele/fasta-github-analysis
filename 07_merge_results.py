"""Merge repository-level evidence from BigQuery, repository, and code searches."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import config


def load_table(
    path: Path,
    source_col: str,
) -> pd.DataFrame:
    """Load and validate one repository-level evidence table."""

    if not path.exists():
        raise FileNotFoundError(
            f"Missing required input: {path}"
        )

    df = pd.read_csv(
        path,
        sep="\t",
    )

    if "repo_name" not in df.columns:
        raise ValueError(
            f"Missing repo_name column in {path}"
        )

    if source_col in df.columns:
        raise ValueError(
            f"Reserved source column already exists in {path}: {source_col}"
        )

    df["repo_name"] = (
        df["repo_name"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    if df["repo_name"].eq("").any():
        raise ValueError(
            f"Empty repo_name found in {path}"
        )

    if df["repo_name"].duplicated().any():
        duplicated = (
            df.loc[
                df["repo_name"].duplicated(keep=False),
                "repo_name",
            ]
            .drop_duplicates()
            .tolist()
        )

        raise ValueError(
            f"{len(duplicated):,} duplicate repositories "
            f"found in {path}: {duplicated[:10]}"
        )

    evidence_columns = [
        column
        for column in df.columns
        if column != "repo_name"
    ]

    if evidence_columns:
        df[evidence_columns] = (
            df[evidence_columns]
            .fillna(0)
            .astype(int)
        )

        invalid = (
            ~df[evidence_columns]
            .isin([0, 1])
        )

        if invalid.any().any():
            raise ValueError(
                f"Non-binary evidence values found in {path}"
            )

    df[source_col] = 1

    return df


def main() -> None:
    # --------------------------------------------------------------
    # Load filtered evidence tables
    # --------------------------------------------------------------

    df_bigquery = load_table(
        config.FILTERED_BIGQUERY_RESULTS,
        "bigquery_hit",
    )

    df_repository = load_table(
        config.FILTERED_REPO_RESULTS,
        "repo_hit",
    )

    df_code = load_table(
        config.FILTERED_CODE_RESULTS,
        "code_hit",
    )

    # --------------------------------------------------------------
    # Merge
    # --------------------------------------------------------------

    master = df_bigquery.merge(
        df_repository,
        on="repo_name",
        how="outer",
    )

    master = master.merge(
        df_code,
        on="repo_name",
        how="outer",
    )

    evidence_columns = [
        column
        for column in master.columns
        if column != "repo_name"
    ]

    master[evidence_columns] = (
        master[evidence_columns]
        .fillna(0)
        .astype(int)
    )

    source_columns = [
        "bigquery_hit",
        "repo_hit",
        "code_hit",
    ]

    # --------------------------------------------------------------
    # Validate
    # --------------------------------------------------------------

    if not master["repo_name"].is_unique:
        raise ValueError(
            "Merged repository names are not unique"
        )

    invalid = (
        ~master[evidence_columns]
        .isin([0, 1])
    )

    if invalid.any().any():
        raise ValueError(
            "Merged evidence columns contain values other than 0/1"
        )

    no_source = (
        master[source_columns]
        .sum(axis=1)
        .eq(0)
    )

    if no_source.any():
        raise ValueError(
            f"{no_source.sum():,} repositories have no source evidence"
        )

    expected_union = (
        set(df_bigquery["repo_name"])
        | set(df_repository["repo_name"])
        | set(df_code["repo_name"])
    )

    actual_union = set(master["repo_name"])

    if actual_union != expected_union:
        raise ValueError(
            "Merged repository set does not match input union"
        )

    # --------------------------------------------------------------
    # Column ordering
    # --------------------------------------------------------------

    first_columns = [
        "repo_name",
        *source_columns,
    ]

    remaining_columns = [
        column
        for column in master.columns
        if column not in first_columns
    ]

    master = (
        master[
            first_columns
            + remaining_columns
        ]
        .sort_values(
            "repo_name",
            key=lambda x: x.str.lower(),
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------------
    # Save
    # --------------------------------------------------------------

    config.MERGED_RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    master.to_csv(
        config.MERGED_RESULTS,
        sep="\t",
        index=False,
    )

    # --------------------------------------------------------------
    # Report
    # --------------------------------------------------------------

    print(
        f"BigQuery repositories          : "
        f"{len(df_bigquery):,}"
    )
    print(
        f"Repository-search repositories : "
        f"{len(df_repository):,}"
    )
    print(
        f"Code-search repositories       : "
        f"{len(df_code):,}"
    )
    print(
        f"Unique merged repositories     : "
        f"{len(master):,}"
    )

    print("\nSource overlap:")

    overlap_counts = (
        master[source_columns]
        .sum(axis=1)
        .value_counts()
        .sort_index()
    )

    for n_sources, count in overlap_counts.items():
        label = (
            "source"
            if n_sources == 1
            else "sources"
        )

        print(
            f"{n_sources} {label:<7} "
            f": {count:,}"
        )

    print(
        f"\nSaved merged results           : "
        f"{config.MERGED_RESULTS}"
    )


if __name__ == "__main__":
    main()
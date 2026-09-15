"""Filter BigQuery FASTA-file hits and collapse them to repository-level evidence."""

from __future__ import annotations

import re

import pandas as pd

from config import (
    BIGQUERY_RESULTS,
    EXCLUDED_BIGQUERY_RESULTS,
    FILTERED_BIGQUERY_RESULTS,
)


EXPECTED_EXTENSIONS = {
    "fa",
    "fa.gz",
    "fasta",
    "fasta.gz",
    "fna",
    "fna.gz",
    "faa",
    "faa.gz",
    "ffn",
    "ffn.gz",
}


# Strong indicators that a .fa file is a localization/resource file
# rather than a biological FASTA file.
LOCALIZATION_PATH_RE = re.compile(
    r"""
    (?:^|/)
    (?:
        i18n
        |
        l10n
        |
        locales?
        |
        translations?
    )
    (?:/|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)


LOCALIZATION_FILENAME_RE = re.compile(
    r"""
    (?:^|/)
    (?:
        messages
        |
        translation
        |
        translations
    )
    \.fa
    (?:\.gz)?
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)


def main() -> None:
    # --------------------------------------------------------------
    # Load
    # --------------------------------------------------------------

    if not BIGQUERY_RESULTS.exists():
        raise FileNotFoundError(
            f"Missing required input: {BIGQUERY_RESULTS}"
        )

    df = pd.read_csv(BIGQUERY_RESULTS)

    required_columns = {
        "repo_name",
        "path",
        "extension",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            "Missing required column(s): "
            + ", ".join(sorted(missing))
        )

    # --------------------------------------------------------------
    # Normalize
    # --------------------------------------------------------------

    df["repo_name"] = (
        df["repo_name"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["path"] = (
        df["path"]
        .astype(str)
        .str.strip()
    )

    df["extension"] = (
        df["extension"]
        .astype(str)
        .str.strip()
        .str.lower()
        .str.removeprefix(".")
    )

    if df["repo_name"].eq("").any():
        raise ValueError("Empty repo_name found")

    if df["path"].eq("").any():
        raise ValueError("Empty path found")

    unexpected_extensions = (
        set(df["extension"].dropna())
        - EXPECTED_EXTENSIONS
    )

    if unexpected_extensions:
        raise ValueError(
            "Unexpected extension(s): "
            + ", ".join(sorted(unexpected_extensions))
        )

    # Step 01 uses SELECT DISTINCT, so duplicate repository/path
    # combinations should not occur.
    duplicated = df.duplicated(
        subset=["repo_name", "path"]
    )

    if duplicated.any():
        raise ValueError(
            f"{duplicated.sum():,} duplicate repository/path rows found"
        )

    # --------------------------------------------------------------
    # Identify non-biological .fa files
    # --------------------------------------------------------------

    is_fa = df["extension"].isin(
        {
            "fa",
            "fa.gz",
        }
    )

    localization_path = df["path"].str.contains(
        LOCALIZATION_PATH_RE,
        na=False,
    )

    localization_filename = df["path"].str.contains(
        LOCALIZATION_FILENAME_RE,
        na=False,
    )

    localization_artifact = (
        is_fa
        & (
            localization_path
            | localization_filename
        )
    )

    # --------------------------------------------------------------
    # Split file-level evidence
    # --------------------------------------------------------------

    retained_files = df.loc[
        ~localization_artifact
    ].copy()

    excluded_files = df.loc[
        localization_artifact
    ].copy()

    excluded_files["exclusion_reason"] = (
        "localization file using .fa extension"
    )

    # --------------------------------------------------------------
    # Collapse retained files to repository-level evidence
    # --------------------------------------------------------------

    filtered = (
        retained_files[["repo_name"]]
        .drop_duplicates()
        .sort_values("repo_name")
        .reset_index(drop=True)
    )

    filtered["bigquery_fasta_file"] = 1

    # --------------------------------------------------------------
    # Validate
    # --------------------------------------------------------------

    if not filtered["repo_name"].is_unique:
        raise ValueError(
            "Filtered repository names are not unique"
        )

    retained_repo_names = set(
        retained_files["repo_name"]
    )

    filtered_repo_names = set(
        filtered["repo_name"]
    )

    if retained_repo_names != filtered_repo_names:
        raise ValueError(
            "Repository aggregation does not match retained files"
        )

    # A repository may contain both an excluded localization .fa file
    # and a retained biological FASTA file. The retained and excluded
    # repository sets therefore need not be disjoint.

    input_repo_count = df["repo_name"].nunique()

    removed_repo_count = (
        input_repo_count - len(filtered)
    )

    # --------------------------------------------------------------
    # Sort exclusions
    # --------------------------------------------------------------

    excluded_files = (
        excluded_files
        .sort_values(
            ["repo_name", "path"],
            key=lambda x: x.str.lower(),
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------------
    # Save
    # --------------------------------------------------------------

    FILTERED_BIGQUERY_RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    filtered.to_csv(
        FILTERED_BIGQUERY_RESULTS,
        sep="\t",
        index=False,
    )

    excluded_files.to_csv(
        EXCLUDED_BIGQUERY_RESULTS,
        sep="\t",
        index=False,
    )

    # --------------------------------------------------------------
    # Report
    # --------------------------------------------------------------

    print(
        f"Input files                   : "
        f"{len(df):,}"
    )
    print(
        f"Input repositories            : "
        f"{input_repo_count:,}"
    )
    print(
        f".fa/.fa.gz files              : "
        f"{is_fa.sum():,}"
    )
    print(
        f"Localization files excluded   : "
        f"{localization_artifact.sum():,}"
    )
    print(
        f"Repositories removed entirely : "
        f"{removed_repo_count:,}"
    )
    print(
        f"Repositories retained         : "
        f"{len(filtered):,}"
    )

    print("\nFiles by extension:")

    extension_counts = (
        df["extension"]
        .value_counts()
        .sort_index()
    )

    for extension, count in extension_counts.items():
        print(
            f"  {extension:<10} {count:>8,}"
        )

    if not excluded_files.empty:
        print("\nExcluded localization files:")

        for _, row in excluded_files.head(50).iterrows():
            print(
                f"  {row['repo_name']}: "
                f"{row['path']}"
            )

        if len(excluded_files) > 50:
            print(
                f"  ... and "
                f"{len(excluded_files) - 50:,} more"
            )

    print(
        f"\nSaved repositories           : "
        f"{FILTERED_BIGQUERY_RESULTS}"
    )
    print(
        f"Saved excluded files         : "
        f"{EXCLUDED_BIGQUERY_RESULTS}"
    )


if __name__ == "__main__":
    main()
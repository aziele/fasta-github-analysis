"""Create Supplementary Table 1 from the final repository dataset."""

from __future__ import annotations

import ast

import pandas as pd

import config


COLUMN_MAP = {
    "repo_name": "Repository",
    "date_created": "Created",
    "date_updated": "Last updated",
    "date_pushed": "Last pushed",
    "description": "Description",
    "language": "Language",
    "topics": "Topics",
    "stars": "Stars",
    "forks_count": "Forks",
    "size_kb": "Size (KB)",
    "owner_type": "Owner type",
    "is_fork": "Fork",
    "archived": "Archived",
    "bigquery_hit": "FASTA file",
    "repo_hit": "FASTA reference",
    "code_hit": "FASTA-handling code",
}


BOOLEAN_COLUMNS = [
    "Fork",
    "Archived",
    "FASTA file",
    "FASTA reference",
    "FASTA-handling code",
]


DATE_COLUMNS = [
    "Created",
    "Last updated",
    "Last pushed",
]


NUMERIC_COLUMNS = [
    "Stars",
    "Forks",
    "Size (KB)",
]


EVIDENCE_COLUMNS = [
    "FASTA file",
    "FASTA reference",
    "FASTA-handling code",
]


def parse_boolean(value) -> bool | None:
    """Convert serialized truth values to booleans."""

    if pd.isna(value):
        return None

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {
            "true",
            "1",
            "yes",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
        }:
            return False

        raise ValueError(
            f"Invalid boolean value: {value!r}"
        )

    if isinstance(value, bool):
        return value

    if value == 1:
        return True

    if value == 0:
        return False

    raise ValueError(
        f"Invalid boolean value: {value!r}"
    )


def format_topics(value) -> str:
    """Format repository topics as a semicolon-separated string."""

    if pd.isna(value):
        return ""

    value = str(value).strip()

    if not value:
        return ""

    if (
        value.startswith("[")
        and value.endswith("]")
    ):
        try:
            topics = ast.literal_eval(
                value
            )
        except (
            ValueError,
            SyntaxError,
        ):
            return value

        if isinstance(
            topics,
            (list, tuple),
        ):
            return "; ".join(
                str(topic)
                for topic in topics
            )

    return value


def main() -> None:
    # --------------------------------------------------------------
    # Load
    # --------------------------------------------------------------

    if not config.FILTERED_RESULTS.exists():
        raise FileNotFoundError(
            f"Missing required input: "
            f"{config.FILTERED_RESULTS}"
        )

    df = pd.read_csv(
        config.FILTERED_RESULTS,
        sep="\t",
    )

    missing = [
        column
        for column in COLUMN_MAP
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(
                missing
            )
        )

    # --------------------------------------------------------------
    # Select and rename columns
    # --------------------------------------------------------------

    out = (
        df[
            list(COLUMN_MAP)
        ]
        .rename(
            columns=COLUMN_MAP
        )
        .copy()
    )

    # --------------------------------------------------------------
    # Dates
    # --------------------------------------------------------------

    for column in DATE_COLUMNS:
        out[column] = (
            pd.to_datetime(
                out[column],
                errors="coerce",
            )
            .dt.strftime(
                "%Y-%m-%d"
            )
        )

    # --------------------------------------------------------------
    # Boolean fields
    # --------------------------------------------------------------

    for column in BOOLEAN_COLUMNS:
        out[column] = (
            out[column]
            .map(parse_boolean)
            .astype("boolean")
        )

    # --------------------------------------------------------------
    # Topics
    # --------------------------------------------------------------

    out["Topics"] = (
        out["Topics"]
        .map(format_topics)
    )

    # --------------------------------------------------------------
    # Numeric metadata
    # --------------------------------------------------------------

    for column in NUMERIC_COLUMNS:
        out[column] = (
            pd.to_numeric(
                out[column],
                errors="coerce",
            )
            .astype("Int64")
        )

    # --------------------------------------------------------------
    # Validate
    # --------------------------------------------------------------

    if out[
        "Repository"
    ].duplicated().any():
        raise ValueError(
            "Duplicate repositories found"
        )

    evidence = out[
        EVIDENCE_COLUMNS
    ]

    if evidence.isna().any().any():
        raise ValueError(
            "Missing FASTA evidence value"
        )

    has_evidence = (
        evidence
        .any(axis=1)
    )

    if not has_evidence.all():
        raise ValueError(
            f"{(~has_evidence).sum():,} repositories "
            "have no FASTA evidence"
        )

    if len(out) != len(df):
        raise ValueError(
            "Row count changed while preparing "
            "Supplementary Table 1"
        )

    # --------------------------------------------------------------
    # Format Boolean fields as Yes/No
    # --------------------------------------------------------------

    for column in BOOLEAN_COLUMNS:
        out[column] = (
            out[column]
            .map({
                True: "Yes",
                False: "No",
            })
        )

    # --------------------------------------------------------------
    # Deterministic ordering
    # --------------------------------------------------------------

    out = (
        out
        .sort_values(
            "Repository",
            key=lambda x: x.str.casefold(),
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------------
    # Blank textual/date cells instead of NaN
    # --------------------------------------------------------------

    text_columns = [
        column
        for column in out.columns
        if column not in NUMERIC_COLUMNS
    ]

    out[text_columns] = (
        out[text_columns]
        .fillna("")
    )

    # --------------------------------------------------------------
    # Save
    # --------------------------------------------------------------

    config.SUPPLEMENTARY_TABLE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_excel(
        config.SUPPLEMENTARY_TABLE,
        index=False,
        sheet_name="Repositories",
    )

    print(
        f"Repositories : {len(out):,}"
    )
    print(
        f"Columns      : {len(out.columns)}"
    )
    print(
        f"Saved to     : "
        f"{config.SUPPLEMENTARY_TABLE}"
    )


if __name__ == "__main__":
    main()
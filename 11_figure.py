"""Generate Figure 1 showing FASTA-related GitHub repositories by year."""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

import config


ANALYSIS_END_DATE = pd.Timestamp(
    config.ANALYSIS_END_DATE,
    tz="UTC",
)

END_EXCLUSIVE = (
    ANALYSIS_END_DATE
    + pd.Timedelta(days=1)
)

# Nature-style single-column figure dimensions.
MM_TO_INCH = 1 / 25.4
FIG_WIDTH = 89 * MM_TO_INCH
FIG_HEIGHT = 62 * MM_TO_INCH


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

    if "date_created" not in df.columns:
        raise ValueError(
            "Missing required column: date_created"
        )

    df["date_created"] = pd.to_datetime(
        df["date_created"],
        errors="coerce",
        utc=True,
    )

    missing_dates = (
        df["date_created"]
        .isna()
    )

    if missing_dates.any():
        raise ValueError(
            f"{missing_dates.sum():,} repositories "
            "have no valid creation date"
        )

    # --------------------------------------------------------------
    # Apply publication snapshot cutoff
    # --------------------------------------------------------------

    after_cutoff = (
        df["date_created"]
        >= END_EXCLUSIVE
    )

    if after_cutoff.any():
        print(
            f"Repositories created after cutoff: "
            f"{after_cutoff.sum():,}"
        )

    df = df.loc[
        ~after_cutoff
    ].copy()

    if df.empty:
        raise ValueError(
            "No repositories remain after applying "
            "the analysis cutoff"
        )

    # --------------------------------------------------------------
    # Count repositories by year
    # --------------------------------------------------------------

    df["year"] = (
        df["date_created"]
        .dt.year
    )

    counts = (
        df["year"]
        .value_counts()
        .sort_index()
    )

    first_year = int(
        counts.index.min()
    )

    final_year = (
        ANALYSIS_END_DATE.year
    )

    years = range(
        first_year,
        final_year + 1,
    )

    counts = counts.reindex(
        years,
        fill_value=0,
    )

    # --------------------------------------------------------------
    # Publication-style settings
    # --------------------------------------------------------------

    mpl.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 8,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, ax = plt.subplots(
        figsize=(
            FIG_WIDTH,
            FIG_HEIGHT,
        )
    )

    # --------------------------------------------------------------
    # Bars
    # --------------------------------------------------------------

    complete_years = (
        counts.index
        < final_year
    )

    ax.bar(
        counts.index[
            complete_years
        ],
        counts.loc[
            complete_years
        ],
        width=0.72,
        color="black",
        linewidth=0,
    )

    # The final year is incomplete because the analysis ends
    # before 31 December.
    ax.bar(
        final_year,
        counts.loc[
            final_year
        ],
        width=0.72,
        facecolor="white",
        edgecolor="black",
        linewidth=0.7,
        hatch="//",
    )

    # --------------------------------------------------------------
    # Axes
    # --------------------------------------------------------------

    ax.set_xlabel(
        "Year"
    )

    ax.set_ylabel(
        "Number of GitHub repositories"
    )

    first_tick = (
        first_year
        if first_year % 2 == 0
        else first_year + 1
    )

    ax.set_xticks(
        list(
            range(
                first_tick,
                final_year + 1,
                2,
            )
        )
    )

    ax.set_xlim(
        first_year - 0.6,
        final_year + 0.6,
    )

    ymax = counts.max()

    ax.set_ylim(
        0,
        ymax * 1.08,
    )

    ax.spines[
        "top"
    ].set_visible(
        False
    )

    ax.spines[
        "right"
    ].set_visible(
        False
    )

    ax.tick_params(
        axis="both",
        direction="out",
    )

    ax.yaxis.set_major_formatter(
        mpl.ticker.StrMethodFormatter(
            "{x:,.0f}"
        )
    )

    # --------------------------------------------------------------
    # Layout
    # --------------------------------------------------------------

    # Explicit margins preserve the exact 89 × 62 mm figure size.
    fig.subplots_adjust(
        left=0.19,
        right=0.98,
        bottom=0.20,
        top=0.97,
    )

    # --------------------------------------------------------------
    # Export
    # --------------------------------------------------------------

    config.FIGURE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fig.savefig(
        config.FIGURE,
        transparent=False,
    )

    png_output = (
        config.FIGURE
        .with_suffix(".png")
    )

    fig.savefig(
        png_output,
        dpi=600,
        transparent=False,
    )

    plt.close(
        fig
    )

    # --------------------------------------------------------------
    # Report
    # --------------------------------------------------------------

    print(
        counts.to_string()
    )

    print(
        f"\nTotal repositories plotted : "
        f"{counts.sum():,}"
    )

    print(
        f"Analysis cutoff             : "
        f"{ANALYSIS_END_DATE.date()}"
    )

    print(
        f"Saved PDF                  : "
        f"{config.FIGURE}"
    )

    print(
        f"Saved PNG                  : "
        f"{png_output}"
    )


if __name__ == "__main__":
    main()
# FASTA sequence format use in GitHub repositories

This repository contains the analysis pipeline used to identify public GitHub repositories that use, reference or process the **FASTA sequence format**. FASTA is the widely used plain-text format for representing nucleotide and protein sequences.

To capture different ways in which FASTA appears on GitHub, the analysis uses three complementary approaches:

1. files with commonly used FASTA filename extensions, identified using Google BigQuery;
2. repositories explicitly referring to FASTA, identified using GitHub repository search; and
3. code for reading, writing or otherwise handling FASTA sequences, identified using GitHub code search.

The results are combined at the repository level and supplemented with repository metadata from the GitHub REST API. Known false positives and ambiguous search hits are then filtered to produce the final set of repositories with evidence of FASTA use.

The analysis represents a snapshot of public GitHub repositories as of **15 September 2026**.

## Repository structure

```text
.
├── README.md
├── LICENSE
├── requirements.txt
│
├── config.py                            # Defines analysis settings and file paths
├── queries.py                           # Defines GitHub search queries
├── github_api.py                        # Provides GitHub API request handling
│
├── 01_search_bigquery.sql
├── 02_filter_bigquery.py
├── 03_search_repositories.py
├── 04_filter_repositories.py
├── 05_search_code.py
├── 06_filter_code.py
├── 07_merge_results.py
├── 08_search_metadata.py
├── 09_filter_results.py
├── 10_supplementary_table.py
├── 11_figure.py
│
├── review/                              # Contains manual review decisions
│   └── broad_fasta_review.tsv
├── results/                             # Contains analysis outputs
│   └── ...
├── paper/                               # Contains publication-ready outputs
│   ├── Figure_1.pdf
│   ├── Figure_1.png
│   └── Supplementary_Table_1.xlsx
├── cache/                               # Stores GitHub API responses
│   └── ...
└── logs/                                # Records API-search progress
    └── ...
```

## Requirements

The pipeline requires **Python 3.10 or later**. Install the required Python packages with:

```bash
python -m pip install -r requirements.txt
```

GitHub searches require a **GitHub personal access token**. Set the token as an environment variable before running the API-dependent steps:

```bash
export GITHUB_TOKEN="your_token_here"
```

## Methods

The analysis covers public GitHub repositories created from **1 January 2008 through 15 September 2026**. The date range is defined in `config.py`, and all GitHub search queries are defined in `queries.py`.

### 1. FASTA files in Google BigQuery

**The first evidence stream identifies repositories containing files with FASTA-associated extensions.** `01_search_bigquery.sql` searches the public `bigquery-public-data.github_repos` dataset for paths ending in:

```text
.fa
.fa.gz
.fasta
.fasta.gz
.fna
.fna.gz
.faa
.faa.gz
.ffn
.ffn.gz
```

The query can be run in the Google BigQuery SQL workspace and exported as `results/01_bigquery.csv`. A snapshot generated on **15 September 2026** is included in the repository, allowing this step to be skipped.

`02_filter_bigquery.py` removes non-biological `.fa` and `.fa.gz` files associated with localization resources and collapses the remaining file-level hits to unique repositories.

### 2. GitHub repository search

**The second evidence stream identifies repositories that explicitly refer to FASTA.** `03_search_repositories.py` runs the queries defined in `REPOSITORY_SEARCH_QUERIES` in `queries.py`.

The search uses one unrestricted query, `fasta`, to maximize sensitivity, together with 19 targeted queries. Searches are partitioned by repository creation date when necessary to remain below GitHub result limits. Evidence from individual queries is retained for subsequent filtering.

API responses are cached to support interrupted or repeated runs.

### 3. Repository-search filtering

**Broad and targeted search hits are filtered differently.** `04_filter_repositories.py` provisionally retains all repositories identified by at least one targeted query. Repositories found only by the unrestricted `fasta` query are retained at this stage only if their repository name contains a FASTA-like term, reducing obvious false positives before metadata-based review.

Known lexical collisions involving `FastAPI`, `fastai` and `FastAlign` are identified, but targeted hits are not yet removed. Their final classification is deferred until independent file and code evidence and repository metadata are available.

### 4. GitHub code search

**The third evidence stream identifies code that explicitly handles FASTA sequences.** `05_search_code.py` runs `CODE_SEARCH_QUERIES` from `queries.py`, targeting FASTA parsers, readers, writers, indexing interfaces and sequence-processing operations across multiple programming languages and selected command-line tools.

Because GitHub code search limits the number of results returned for a query, large result sets are recursively partitioned by indexed file size. Evidence from individual queries is retained for subsequent filtering.

API responses are cached to support interrupted or repeated runs.

### 5. Code-search filtering

**Code-search hits are filtered conservatively.** `06_filter_code.py` excludes a repository only when its name matches a known lexical collision (`fastapi`, `fastai` or `fastalign`), it was identified by exactly one code-search query, and that query is susceptible to the collision.

Repositories supported by additional code-search evidence are retained.

### 6. Evidence integration

**The three evidence streams are combined at the repository level.** `07_merge_results.py` merges the filtered BigQuery, repository-search and code-search results while preserving both source-level and individual query evidence for final filtering.

### 7. GitHub metadata and canonical identity

**Repository identities and metadata are resolved through the GitHub REST API.** `08_search_metadata.py` retrieves each repository's current canonical name, dates, description, language, topics, statistics, fork and archive status, and accessibility.

API requests use the pacing, retry and rate-limit handling implemented in `github_api.py` and are cached to support interrupted or repeated runs.

### 8. Final filtering and manual review

**Final filtering combines all available evidence.** `09_filter_results.py` excludes inaccessible repositories and consolidates historical repository names that resolve to the same current GitHub repository, combining their evidence.

Repositories are then handled in three groups:

**Strong evidence.** Repositories with FASTA file evidence, FASTA-handling code evidence, or a targeted repository-search hit without a known lexical collision are retained automatically.

**Broad `fasta`-only candidates.** Repositories identified only by the unrestricted `fasta` query undergo manual review based on their name, description and topics. Repositories are retained when these metadata provide sufficient evidence of biological FASTA use; ambiguous and unrelated cases are excluded.

The manual classifications used in the published analysis are provided in `review/broad_fasta_review.tsv`. Step 09 verifies that the reviewed repositories exactly match the current set of broad `fasta`-only candidates before applying the classifications.

**Targeted lexical collisions.** Targeted repository-search hits containing `fastapi`, `fastai` or `fastalign` in the repository name require additional evidence when no FASTA file or code evidence is available. After masking the collision term, the repository name, description and topics are checked for an explicit standalone FASTA reference. Corroborated repositories are retained; the remaining hits are excluded.

The final retained and excluded repository sets are written to `results/09_repositories.tsv` and `results/09_excluded.tsv`, respectively.

### 9. Publication outputs

`10_supplementary_table.py` generates `paper/Supplementary_Table_1.xlsx` from the final repository set.

`11_figure.py` groups the final repositories by year of creation and generates `paper/Figure_1.pdf` and `paper/Figure_1.png`. The 2026 count includes repositories created through **15 September 2026**.

## Reproducibility

**Run the pipeline in numerical order.** To reproduce the analysis from the included BigQuery snapshot:

```bash
python 02_filter_bigquery.py
python 03_search_repositories.py --refresh
python 04_filter_repositories.py
python 05_search_code.py --refresh
python 06_filter_code.py
python 07_merge_results.py
python 08_search_metadata.py --refresh
python 09_filter_results.py
python 10_supplementary_table.py
python 11_figure.py
```

The repository includes the manual classifications used in the published analysis in `review/broad_fasta_review.tsv`. If the set of broad `fasta`-only candidates matches the reviewed set, Step 09 validates these classifications and applies them automatically.

To repeat the manual review from scratch, remove `review/broad_fasta_review.tsv` before running Step 09. The script will generate a new review file and stop. Classify each candidate as `include` or `exclude`, then rerun:

```bash
python 09_filter_results.py
python 10_supplementary_table.py
python 11_figure.py
```

To reproduce the analysis entirely from source data, first rerun `01_search_bigquery.sql` as described in Methods and replace `results/01_bigquery.csv`.

The `--refresh` option reruns the GitHub searches and metadata retrieval rather than reusing cached API responses.

GitHub is a dynamic resource, so rerunning the pipeline at a later date may produce different results even with the same queries. If the resulting set of broad `fasta`-only candidates differs from the included reviewed set, a new manual review is required.

## Citation

Associated article:

> **[Article]**

## License

See `LICENSE` for licensing information.
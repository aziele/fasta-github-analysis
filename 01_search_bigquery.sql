-- Retrieve files with commonly used FASTA filename extensions
-- from public GitHub repositories indexed by Google BigQuery.

SELECT DISTINCT
  LOWER(TRIM(repo_name)) AS repo_name,
  TRIM(path) AS path,
  REGEXP_EXTRACT(
    LOWER(TRIM(path)),
    r'\.(fasta\.gz|fna\.gz|faa\.gz|ffn\.gz|fa\.gz|fasta|fna|faa|ffn|fa)$'
  ) AS extension
FROM `bigquery-public-data.github_repos.files`
WHERE REGEXP_CONTAINS(
  LOWER(TRIM(path)),
  r'\.(fasta\.gz|fna\.gz|faa\.gz|ffn\.gz|fa\.gz|fasta|fna|faa|ffn|fa)$'
)
ORDER BY repo_name, path;
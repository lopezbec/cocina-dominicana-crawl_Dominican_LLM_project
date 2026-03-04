# Notebook Development Guidelines

This document defines practical standards for notebooks in this repository.

## Scope and Purpose

- `notebooks/01_generate_metrics.py`: deterministic metric generation from processed corpus artifacts; writes reusable CSV outputs for analysis.
- `notebooks/02_metrics_eda.py`: exploratory analysis and visualization of generated metrics; consumes CSV artifacts and presents findings.

## Artifact Contract

`01_generate_metrics.py` is the producer of the metrics contract under `data/processed/eda_metrics/`.

- `meta_enriched.csv`: document-level metadata with core size/count fields and derived ratios.
- `top50_words.csv`: top token frequencies with counts and corpus share.
- `tfidf_top30_terms.csv`: top TF-IDF terms with aggregate TF-IDF scores.
- `tfidf_heatmap_sample.csv`: sampled document labels plus TF-IDF term columns for heatmap input.
- `quality_shortest_10.csv`: 10 shortest documents (quality triage view).
- `quality_longest_10.csv`: 10 longest documents (quality triage view).

High-level column expectations:

- identity/context fields (for example: file or URL identifiers)
- numeric metric fields (for example: counts, ratios, scores)
- analysis-specific label fields (for example: term names, document labels)

If artifact names or semantic meaning change, update both notebooks together and keep this contract in sync.

## Style Rules

- No progress-style `print` output (for example: "loaded X rows", "saved file Y").
- Keep cells concise and focused.
- One responsibility per cell (load, validate, transform, visualize, or summarize).
- Add markdown narrative immediately before compute/plot blocks.
- Show only essential outputs (key tables/figures used for decisions).

## Reliability Rules

- Use deterministic randomness (`seed=...`) for all sampling or stochastic steps.
- Fail fast with explicit input and schema checks before expensive computation.
- Read/write text and CSV artifacts with UTF-8 explicitly.
- Avoid hidden state: notebooks must run cleanly from top to bottom after kernel restart.

## Maintenance Rules

Use notebooks for analysis flow, interpretation, and presentation. Move reusable logic into `src/`.

Change the notebook when:

- adjusting narrative, visualizations, or analysis framing
- changing experiment parameters that are analysis-specific
- adding/removing non-reusable exploratory views

Change `src/` code when:

- logic is shared by CLI, pipelines, tests, or multiple notebooks
- behavior needs unit tests or stable API boundaries
- transformations become non-trivial enough to require maintainable modules

When in doubt: keep orchestration in notebooks, keep business logic in `src/`.

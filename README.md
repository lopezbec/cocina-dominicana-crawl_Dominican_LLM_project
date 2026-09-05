# Dominican Spanish corpus pipeline

This repository collects web pages related to Dominican culture and language, converts the scraped Markdown into plain text, identifies duplicate material, and measures how causal language models handle the resulting documents.

The documentation follows that same path through the repository:

1. **Crawling** explains how seed URLs become raw Markdown and metadata.
2. **Cleaning and deduplication** explains every text transformation and duplicate-detection stage.
3. **Model evaluation** explains context windows, teacher-forced quality metrics, and Ollama runtime measurements.

Each section is collapsed so that this README can serve as both a short entry point and a detailed implementation guide. Open a section for commands, data contracts, code links, and limitations. Generated corpus data and evaluation outputs are intentionally ignored by Git; the repository contains the pipeline, not a published dataset snapshot.

```text
config/urls.yml
      │
      ▼
local Firecrawl ──► data/raw/*.md + metadata.jsonl
                              │
                              ▼
                  text normalization pipeline
                              │
                              ▼
              data/processed/*.txt + metadata_plaintext.jsonl
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
             dedup_report.json    model evaluation JSONL
```

<details>
<summary><strong>Repository map:</strong> where each part lives</summary>

## Repository map

The crawler and evaluator are separate Python projects. Run their commands from their own directories so that relative configuration and output paths resolve correctly.

```text
.
├── crawler/
│   ├── config/
│   │   ├── config.yml                 # paths, crawl timing, and URL filters
│   │   └── urls.yml                   # crawl seeds and processed flags
│   ├── firecrawl/
│   │   └── docker-compose.yml         # local Firecrawl stack
│   ├── src/dominican_llm_scraper/
│   │   ├── cli/commands.py            # scrape and process commands
│   │   ├── core/crawler.py            # discovery, scraping, and persistence
│   │   └── core/processor/            # cleaning and deduplication
│   ├── scripts/                       # comparison and validation reports
│   ├── tests/                         # cleaning and deduplication tests
│   ├── Makefile                       # common crawler commands
│   └── pyproject.toml                 # crawler environment, Python >= 3.9
└── model-evaluation/
    ├── evaluate_corpus.py             # Hugging Face corpus scoring
    ├── run_ollama_runtime_eval.py     # Ollama generation/runtime evaluation
    ├── run_hf_math_eval.py            # fixed continuation-sample evaluator
    ├── llm_eval_common.py             # shared scoring and JSONL helpers
    ├── tests/                         # context and metric-accounting tests
    ├── README.md                      # extended metric reference
    └── pyproject.toml                 # evaluator environment, Python 3.10–3.12
```

The important generated paths are:

| Path | Produced by | Contents |
|---|---|---|
| `crawler/data/raw/` | crawler | Firecrawl Markdown plus `metadata.jsonl` |
| `crawler/data/processed/` | cleaning pipeline | plain-text documents, metadata, and the current deduplication report |
| `crawler/reports/` | report scripts | optional PDF comparisons; ignored by Git |
| `model-evaluation/outputs/` | evaluation scripts | JSONL results, summaries, and optional tensors; ignored by Git |

</details>

<details>
<summary><strong>1. Crawling:</strong> from seed URLs to raw Markdown</summary>

## Crawling

The crawler uses a locally hosted Firecrawl API. A seed can be handled in either of two ways:

- a URL passed directly on the command line is scraped once;
- an entry loaded from `config/urls.yml` is treated as a discovery root, and matching links are followed up to its configured depth.

To people running the crawler, the normal workflow looks like this:

```console
$ cd crawler
$ make setup
$ make firecrawl-test
$ make scrape
$ make firecrawl-stop
```

`make setup` runs `uv sync` and starts the Docker Compose stack. The stack contains the Firecrawl API, Playwright service, Redis, RabbitMQ, and PostgreSQL; its exact definition is in [`crawler/firecrawl/docker-compose.yml`](crawler/firecrawl/docker-compose.yml). The API is exposed at `http://localhost:3002` unless `FIRECRAWL_API_URL` overrides it.

### Configuration

[`crawler/config/urls.yml`](crawler/config/urls.yml) is the crawl registry. Each entry provides a seed URL, its domain, a display name, a `processed` flag, and a maximum discovery depth.

```yaml
urls:
  - url: https://www.cocinadominicana.com/recetas/postres
    domain: cocinadominicana.com
    name: Postres
    processed: false
    max_depth: 2
```

[`crawler/config/config.yml`](crawler/config/config.yml) supplies the shared settings:

```yaml
output_dir: data/raw
plaintext_output_dir: data/processed

crawler:
  max_depth: 2
  delay_seconds: 5
  skip_existing: true
  max_retries: 3
  base_retry_delay: 2

processing:
  min_content_length: 50
```

It also contains regular expressions that reject media, feeds, comment pages, social-media links, fragments, and other unwanted URL shapes. [`load_config()`](crawler/src/dominican_llm_scraper/core/config_loader.py) can merge an optional `config/sites/<domain_slug>/config.yml` over the global file. Scalars override, dictionaries merge recursively, and lists append. No site-specific configuration files are currently checked in, so the shared configuration is the active configuration in this repository.

### What happens during a configured crawl

The command begins in [`cli/commands.py`](crawler/src/dominican_llm_scraper/cli/commands.py) and delegates the network and file work to [`Crawler`](crawler/src/dominican_llm_scraper/core/crawler.py):

1. The CLI loads the registry and, unless `--force` is present, selects entries whose `processed` value is false.
2. `load_config(url)` preserves the seed's protocol, derives its domain and base URL, and builds regular expressions for same-site Markdown links.
3. `crawl_category()` scrapes the seed through Firecrawl and extracts links from Firecrawl's Markdown response.
4. Global include/exclude rules filter the discovered links. Discovery repeats breadth-first until `max_depth` is reached or no new links are found.
5. Each unique discovered URL is scraped as Markdown. Existing URLs found in `data/raw/metadata.jsonl` are skipped during configured crawls.
6. The Markdown is written to `data/raw/`, and one metadata object is appended to `metadata.jsonl`.
7. The seed entry is marked `processed: true` unless `--no-update` was used.

Network failures are attempted up to `max_retries` times. The current implementation waits the configured `base_retry_delay` between attempts; the delay is fixed rather than exponential. A separate `delay_seconds` pause is applied between article requests.

### Raw output contract

A saved page has no synthetic front matter. The `.md` file contains Firecrawl's Markdown response exactly as returned, while provenance lives in the adjacent JSONL metadata file.

```text
data/raw/
├── 0001_cocinadominicana_com_example.md
├── 0002_cocinadominicana_com_another-page.md
└── metadata.jsonl
```

File names follow:

```text
{four_digit_doc_id}_{domain_with_underscores}_{safe_url_slug}.md
```

A metadata line contains the page title and description reported by Firecrawl, the source URL, URL slug, domain, scrape timestamp, raw word and character counts, document ID, and, when discovered from a configured seed, the category name.

```json
{
  "title": "Example title",
  "description": "Example description",
  "url": "https://www.cocinadominicana.com/example",
  "url_slug": "example",
  "domain": "cocinadominicana.com",
  "scraped_at": "2026-01-15T14:15:30.123456",
  "word_count": 450,
  "char_count": 2847,
  "doc_id": "0001",
  "category": "Postres"
}
```

### Other ways to invoke it

```console
# Scrape one page directly; no link discovery
$ uv run python -m dominican_llm_scraper scrape \
    https://www.cocinadominicana.com/example

# Read seed entries from another YAML file
$ uv run python -m dominican_llm_scraper scrape \
    --urls-file custom_urls.yml

# Revisit every registry seed, including entries marked processed
$ uv run python -m dominican_llm_scraper scrape --force

# Do not change config/urls.yml after the configured crawl
$ uv run python -m dominican_llm_scraper scrape --no-update
```

A few details matter:

- `--force` bypasses the registry's `processed` filter, but configured crawling still skips article URLs already present in raw metadata. It is useful for discovering newly linked pages; it is not an overwrite operation.
- Direct URL mode does not perform the existing-URL check. Repeating a direct URL can append another document with a new ID.
- A seed is marked processed after `crawl_category()` returns even when individual child pages failed. Treat `processed` as “this seed was visited,” not as proof that every discovered page succeeded.
- Document IDs come from the final line of `metadata.jsonl`. Concurrent crawler processes are therefore not safe writers to the same output directory.

### Files worth reading

- [`cli/commands.py`](crawler/src/dominican_llm_scraper/cli/commands.py): argument handling, registry selection, summaries, and exit codes.
- [`core/config_loader.py`](crawler/src/dominican_llm_scraper/core/config_loader.py): domain detection, configuration merging, and registry updates.
- [`core/crawler.py`](crawler/src/dominican_llm_scraper/core/crawler.py): Firecrawl calls, discovery, retries, filters, and persistence.
- [`utils/logging.py`](crawler/src/dominican_llm_scraper/utils/logging.py): session IDs and `key=value` event logs.
- [`crawler/Makefile`](crawler/Makefile): the commands actually available to operators.

</details>

<details>
<summary><strong>2. Cleaning and deduplication:</strong> from Markdown to reviewable duplicate evidence</summary>

## Cleaning and deduplication

Cleaning is deterministic text transformation followed by four duplicate-detection stages. The order is intentional: inexpensive exact checks remove obvious repetitions before embedding-based comparisons are attempted.

```console
$ cd crawler
$ ollama pull qwen3-embedding:0.6b
$ ollama serve

# In another terminal
$ make process
```

`make process` reads raw metadata, converts each referenced Markdown file, writes plain text, and then runs all four deduplication stages. The semantic stage fails fast if Ollama is unavailable or if `qwen3-embedding:0.6b` is not installed.

### Plain-text transformation

[`process_markdown_to_plain_text()`](crawler/src/dominican_llm_scraper/core/processor/pipeline.py) applies five functions in this exact order:

```text
Markdown
  │
  ├─ 1. render Markdown as HTML, then extract visible text
  ├─ 2. remove a small set of generic navigation/noise lines
  ├─ 3. normalize newlines, spaces, tabs, and blank lines
  ├─ 4. join lines that look like wrapped prose
  └─ 5. remove isolated Markdown punctuation and trim lines
      │
      ▼
plain text
```

| Step | Implementation | What it does |
|---|---|---|
| Markdown to text | [`step_01_markdown_to_text.py`](crawler/src/dominican_llm_scraper/core/processor/step_01_markdown_to_text.py) | Renders Markdown with Mistune, including tables, then extracts text with Beautiful Soup. |
| Generic noise | [`step_02_generic_noise.py`](crawler/src/dominican_llm_scraper/core/processor/step_02_generic_noise.py) | Removes narrowly defined lines such as “skip to,” language toggles, table-of-contents labels, display controls, and separator-only lines. |
| Whitespace | [`step_03_whitespace.py`](crawler/src/dominican_llm_scraper/core/processor/step_03_whitespace.py) | Converts line endings, collapses spaces and tabs, limits consecutive blank lines, and removes trailing whitespace. |
| Wrapped lines | [`step_04_line_joiner.py`](crawler/src/dominican_llm_scraper/core/processor/step_04_line_joiner.py) | Joins likely prose continuations while preserving list items and sentence-ending boundaries. |
| Inline punctuation | [`step_05_inline_punctuation.py`](crawler/src/dominican_llm_scraper/core/processor/step_05_inline_punctuation.py) | Removes isolated `*`, `_`, and backtick markers and trims the result. |

An experimental English-word filter exists in [`step_06_english_filter.py`](crawler/src/dominican_llm_scraper/core/processor/step_06_english_filter.py), but the active pipeline does not import or invoke it. English tokens are **not** removed by the current `make process` path.

[`process_all_files()`](crawler/src/dominican_llm_scraper/core/processor/batch.py) uses `data/raw/metadata.jsonl` as its source of truth. For each metadata row it reconstructs the expected raw filename, runs the pipeline, and skips output whose stripped length is 50 characters or fewer under the default configuration.

The result is:

```text
data/processed/
├── 0001_cocinadominicana_com_example.txt
├── 0002_cocinadominicana_com_another-page.txt
├── metadata_plaintext.jsonl
└── dedup_report.json
```

`metadata_plaintext.jsonl` preserves the document ID, source URL, domain, title, raw filename, processed filename, and recalculated plain-text word and character counts.

### Duplicate detection

The stages return evidence and canonical IDs; they do not delete or rewrite the `.txt` files.

#### Stage 1: exact normalized text

[`stage_01_exact.py`](crawler/src/dominican_llm_scraper/core/processor/deduplication/stage_01_exact.py) normalizes line endings, trims the document, and computes a SHA-256 hash. The first document with a hash is canonical; later documents with the same hash are duplicates.

```text
normalization: line endings + outer whitespace
comparison:    SHA-256 equality
short-doc skip: none
```

#### Stage 2: near-duplicate wording

[`stage_02_near_duplicate.py`](crawler/src/dominican_llm_scraper/core/processor/deduplication/stage_02_near_duplicate.py) receives only Stage 1 survivors. It lowercases and whitespace-normalizes each document, tokenizes words, and builds five-token shingles. MinHash LSH proposes candidates; exact Jaccard similarity makes the final decision.

```text
shingle size:       5 words
MinHash signatures: 128 permutations
Jaccard threshold:  0.85
minimum length:     30 tokens
```

Connected candidate pairs form groups, and the earliest document in processing order becomes canonical. Documents below the minimum length are reported as skipped rather than duplicated.

#### Stage 3: semantic similarity

[`stage_03_semantic.py`](crawler/src/dominican_llm_scraper/core/processor/deduplication/stage_03_semantic.py) receives Stage 2 survivors and asks local Ollama for embeddings:

1. Normalize and tokenize each document.
2. Skip documents shorter than 50 tokens.
3. Divide each document into non-overlapping 200-token chunks.
4. Embed every chunk with `qwen3-embedding:0.6b` and average the chunk vectors into one document vector.
5. L2-normalize the document vectors and group them with spherical FAISS k-means.
6. Compute cosine similarities between documents inside each cluster.
7. Build duplicate groups independently at cosine thresholds `0.90`, `0.92`, and `0.95`.

The default duplicate rows use the strictest configured threshold, `0.95`. The report retains per-document, per-cluster, per-pair, and per-threshold diagnostics. FAISS uses a GPU when one is available unless the caller explicitly selects CPU; the default macOS installation normally uses CPU FAISS.

Clustering is a candidate-reduction step. Documents assigned to different clusters are not compared, so this stage can miss a semantically similar pair that falls across a cluster boundary.

#### Stage 4: exact repeated sentence spans

[`stage_04_sentence_spans.py`](crawler/src/dominican_llm_scraper/core/processor/deduplication/stage_04_sentence_spans.py) does not compare every pair in the corpus. It starts from Stage 3 pair edges with cosine similarity at or above `0.90`, keeps same-domain pairs by default, and looks for an identical run of three consecutive sentences.

Whitespace is normalized before span hashing, but case, punctuation, and accents remain significant. A match therefore supplies concrete copied-span evidence for a pair that semantic similarity had already nominated.

```text
candidate source:      Stage 3 pair edges
candidate similarity:  >= 0.90
domain restriction:    same domain
match requirement:     exact 3-sentence span
```

### Consolidated report

[`report.py`](crawler/src/dominican_llm_scraper/core/processor/deduplication/report.py) combines all stages into `data/processed/dedup_report.json`. It contains:

- overall scanned, duplicate, kept, and group counts;
- each stage's parameters and counts;
- duplicate rates by domain;
- one selected duplicate record per document, including canonical source and evidence;
- Stage 3 diagnostic tables.

When more than one stage flags the same document, the later stage has reporting priority: exact, near-duplicate, semantic, then sentence span. This changes which evidence is displayed; it does not mean that an earlier match was invalid.

The checked-in [`crawler/dedup_report.json`](crawler/dedup_report.json) is a snapshot from an earlier run, not a file kept in sync with local `data/processed/`. It records 2,394 scanned documents, 844 flagged duplicates, and 1,550 kept documents. Re-run `make process` to produce a report for the data currently present on a machine.

### Reviewing the transformation

A side-by-side PDF is useful before accepting a cleaning rule:

```console
$ cd crawler
$ make compare-pdf IDS=0002,0080,0809
```

[`generate_comparison_pdf.py`](crawler/scripts/generate_comparison_pdf.py) resolves matching raw and processed files and renders them in review blocks. Stage 3 also has a runtime estimator and synthetic coherence tools:

- [`estimate_stage3_runtime.py`](crawler/scripts/estimate_stage3_runtime.py)
- [`run_synthetic_stage3_validation.py`](crawler/scripts/run_synthetic_stage3_validation.py)
- [`generate_semantic_pairs_pdf.py`](crawler/scripts/generate_semantic_pairs_pdf.py)

### What the cleaning does not guarantee

- The generic noise rules are deliberately narrow; site-specific widgets, subscription prompts, ratings, and comment controls can remain.
- Line joining is heuristic and should be checked on new source families.
- A duplicate flag is a review decision aid, not an automatic deletion.
- Semantic similarity depends on the embedding model, clustering, and thresholds.
- Re-running processing overwrites same-named `.txt` files and metadata, but it does not remove stale files already present in the output directory.

</details>

<details>
<summary><strong>3. Model evaluation:</strong> quality metrics from Hugging Face, runtime metrics from Ollama</summary>

## Model evaluation

The evaluator treats Hugging Face and Ollama as complementary backends:

- **Hugging Face** exposes logits, so it can measure how much probability a model assigns to every actual source token.
- **Ollama** exposes native prompt and generation timings, but not the source-token logits needed for perplexity.

Both scripts emit one JSON object per source file with a nested `chunks` array. They use 80% of the model's declared context capacity by default.

Install the evaluator separately:

```console
$ cd model-evaluation
$ uv sync
```

### Hugging Face corpus scoring

```console
$ uv run python evaluate_corpus.py \
    --model-id Qwen/Qwen3-4B-Instruct-2507 \
    --input-path ../crawler/data/processed \
    --output-jsonl outputs/qwen3_metrics.jsonl \
    --overwrite
```

[`evaluate_corpus.py`](model-evaluation/evaluate_corpus.py) accepts a directory of `.txt` files, one `.txt` file, or a CSV/JSON/JSONL table. Tabular inputs use `text` and `document_id` columns by default; `--text-column` and `--id-column` change them.

The script chooses CUDA first, then Apple MPS, then CPU when `--device auto` is used. CUDA can optionally load a model with bitsandbytes NF4 4-bit quantization. On Apple MPS it uses FP16; CPU uses FP32.

#### Context-window policy

The evaluator inspects context declarations in the model configuration and tokenizer, ignores Hugging Face's sentinel “unknown” tokenizer limits, and selects the smallest valid declaration as the safe maximum.

```text
utilized_context_length = floor(maximum_context_length × 0.80)
default_stride          = utilized_context_length // 2
```

`--max-length` can impose a lower hard cap. `--stride` can replace the default 50% advance. If a document is longer than the effective context, windows overlap. The overlapping prefix supplies context but its labels are masked, so every document token after the first contributes to the file metrics exactly once.

For a 32,768-token window and a 16,384-token stride:

```text
window 1: input  0..32767      score 1..32767
window 2: input  16384..49151  score 32768..49151
                  └─ context ─┘
```

#### Teacher-forced next-token scoring

If a source tokenizes to `[A, B, C, D]`, a causal model supplies these predictions in one forward pass:

```text
A       → B
A B     → C
A B C   → D
```

The evaluator looks up the probabilities assigned to the actual source tokens:

```text
P(B | A), P(C | A,B), P(D | A,B,C)
```

This is called teacher forcing because each prediction receives the correct source prefix, not the model's previous generated guess. It is used here because NLL and perplexity ask a precise question: *how surprising was this fixed document to this model?* Free-running generation answers a different question and introduces decoding choices such as temperature and sampling.

For each actual token `x_t`:

```text
token_nll        = -log P(x_t | source prefix)
total_nll        = sum(token_nll)
cross_entropy    = total_nll / scored_token_count
perplexity       = exp(cross_entropy)
bits_per_byte    = total_nll / (log(2) × source_utf8_bytes)
token_fertility  = tokenizer_tokens / whitespace_delimited_words
```

Lower NLL, cross-entropy, perplexity, and bits per byte mean that the model found the text more predictable. These values are most useful when models are compared on exactly the same documents; they are not standalone corpus-quality pass/fail scores.

#### Hugging Face output

The requested JSONL contains file-level metrics and nested metrics for each window. A weighted corpus summary is written beside it as `<output-stem>_summary.json`.

```json
{
  "record_type": "document",
  "sample_id": "0001_example",
  "status": "success",
  "model_id": "Qwen/Qwen3-4B-Instruct-2507",
  "maximum_context_length": 40960,
  "context_utilization": 0.8,
  "effective_context_length": 32768,
  "stride": 16384,
  "token_count": 42000,
  "predicted_token_count": 41999,
  "total_negative_log_likelihood": 123456.0,
  "per_token_cross_entropy_loss": 2.94,
  "perplexity": 18.92,
  "bits_per_byte": 1.21,
  "window_count": 2,
  "chunks": [
    {
      "chunk_index": 1,
      "token_start_index": 0,
      "token_end_index_exclusive": 32768,
      "context_token_count": 0,
      "predicted_token_count": 32767,
      "runtime_seconds": 12.5,
      "scoring_tokens_per_second": 2621.36
    }
  ]
}
```

The summary combines total NLL and scored-token counts before calculating cross-entropy and perplexity. It does **not** average file or chunk perplexities.

`top_k_next_token_predictions` is separate from the teacher-forced document score: it reports likely tokens after the final source token. Optional flags can also save every target-token log probability, the final logit vector, and the final probability vector.

```console
$ uv run python evaluate_corpus.py \
    --input-path ../crawler/data/processed/0001_example.txt \
    --save-token-logprobs \
    --save-final-logits \
    --save-final-probability-vector \
    --overwrite
```

### Ollama runtime evaluation

Start Ollama and install both the runtime model and its matching Hugging Face tokenizer files:

```console
$ ollama pull qwen3:4b
$ ollama serve

$ cd model-evaluation
$ uv run python run_ollama_runtime_eval.py \
    --model qwen3:4b \
    --tokenizer-id Qwen/Qwen3-4B \
    --input-path ../crawler/data/processed \
    --output-jsonl outputs/qwen3_ollama_runtime.jsonl \
    --limit 0 \
    --overwrite
```

[`run_ollama_runtime_eval.py`](model-evaluation/run_ollama_runtime_eval.py) verifies that the Ollama model is installed, reads its context length from `/api/show`, and loads the corresponding Hugging Face **fast** tokenizer. The tokenizer is used only to plan chunks and recover exact character offsets; it must correspond to the Ollama model.

Ollama needs room for the continuation and any backend-added tokens, so its source budget is smaller than the effective context:

```text
effective_context = floor(maximum_context × 0.80)
prompt_budget      = effective_context - max_new_tokens - special_token_reserve
```

With the defaults, each chunk reserves 64 generated tokens and 32 template/special tokens. The script sets Ollama's `num_ctx` to the full effective context and rejects a response if the actual prompt count plus reserved generation exceeds that allocation.

Each chunk is sent to `/api/generate` with temperature `0`, thinking disabled, and a fixed seed. Ollama performs prompt evaluation (prefill), then generates one token at a time. The nested chunk record retains:

- planned token and exact source-character boundaries;
- a SHA-256 hash of the submitted source text;
- Ollama's actual prompt and generated token counts;
- model-load, prompt-evaluation, generation, total, and client wall-clock durations;
- prompt and generation throughput;
- the generated continuation and completion reason;
- any chunk-level error.

The file-level values sum successful chunk counts and durations, then recompute throughput from those totals. Because source chunks overlap, aggregate prompt tokens describe compute performed, not unique corpus tokens.

The Ollama command defaults to `--limit 3` as a development safeguard. Pass `--limit 0` explicitly for the whole input directory. Unlike the Hugging Face corpus evaluator, the Ollama script currently writes per-file JSONL records but no separate corpus-summary file.

### Why the two outputs should not be collapsed into one score

Ollama's `/api/generate` response reports how many prompt tokens it processed, but not the complete probability distribution assigned to each actual prompt token. The evaluator therefore does not invent Ollama NLL, cross-entropy, perplexity, or bits-per-byte values.

Likewise, these throughput fields measure different work:

```text
Hugging Face scoring throughput  = actual source tokens scored per second
Ollama prompt throughput         = prompt tokens processed per second
Ollama generation throughput     = new tokens generated autoregressively per second
```

Model format matters too. A Hugging Face FP16 checkpoint and an Ollama quantized GGUF build with the same model family are different runtime representations. Report their device, dtype, and quantization before interpreting timing differences.

### Auxiliary continuation evaluator

[`run_hf_math_eval.py`](model-evaluation/run_hf_math_eval.py) is a separate evaluator for fixed prompt/expected-continuation samples. It validates that every sample is copied from adjacent lines in a source file, masks the prompt, scores only the expected continuation, and also generates a deterministic continuation. It is not used by the full-document corpus command and requires a caller-provided JSONL sample file matching the schema in [`llm_eval_common.py`](model-evaluation/llm_eval_common.py).

For a field-by-field metric reference, see [`model-evaluation/README.md`](model-evaluation/README.md).

### Files worth reading

- [`evaluate_corpus.py`](model-evaluation/evaluate_corpus.py): input loading, context resolution, overlapping-window accounting, metrics, artifacts, and summary weighting.
- [`run_ollama_runtime_eval.py`](model-evaluation/run_ollama_runtime_eval.py): Ollama preflight, token-offset chunk planning, requests, and duration aggregation.
- [`llm_eval_common.py`](model-evaluation/llm_eval_common.py): causal-shift scoring and shared numerical helpers.
- [`tests/test_evaluate_corpus.py`](model-evaluation/tests/test_evaluate_corpus.py): executable examples for the 80% policy, overlap masking, offsets, and weighted summaries.

</details>

<details>
<summary><strong>Development and verification:</strong> tests, reports, and working assumptions</summary>

## Development and verification

Use each project's locked environment:

```console
$ cd crawler
$ uv sync
$ uv run python -m pytest tests/core
$ uv run ruff check src tests scripts

$ cd ../model-evaluation
$ uv sync
$ uv run pytest
```

The crawler core tests focus on text conversion, minimum-length handling, exact/near/semantic/sentence-span deduplication, and report consolidation. Real Ollama integration tests skip when the service or embedding model is unavailable. The separate `tests/scripts` harness expects a persistent fixture under `crawler/data/synthetic_stage3/`; that generated fixture is ignored and is not included in a fresh checkout. There is not currently an automated end-to-end test of the live Firecrawl crawl path.

The evaluation tests use a small deterministic causal model and fake tokenizer data; they verify token accounting and formulas without downloading a production model. Real model runs remain hardware- and checkpoint-dependent integration work.

Before changing a heuristic:

1. Add a focused unit test showing the source text and expected output.
2. Run the raw-versus-processed PDF on representative documents.
3. Re-run deduplication and compare stage/domain counts, not only the overall duplicate count.
4. Evaluate the same fixed file set before comparing language-model metrics.
5. Record model revision, tokenizer, device, dtype or quantization, context policy, and command-line overrides with any reported result.

The repository's generated directories are ignored. Preserve any result needed for a paper or review in a versioned artifact store together with the exact Git commit and command used to produce it.

</details>

<details>
<summary><strong>Responsible use:</strong> scope and source obligations</summary>

## Responsible use

This project is intended for educational and research use. A technically successful scrape does not establish permission to redistribute or train on the result. Review each source's terms, robots policy, copyright status, personal information, and licensing before collection or publication.

The cleaning pipeline removes formatting and some recurring interface text; it does not perform legal review, personal-data detection, factual validation, or license classification.

</details>

<details>
<summary><strong>Credits</strong></summary>

## Acknowledgment

This project has been partially supported by the Ministerio de Educación Superior, Ciencia y Tecnología (MESCyT) of the Dominican Republic through the FONDOCYT grant. The authors gratefully acknowledge this support.

Any opinions, findings, conclusions, or recommendations expressed in this material are those of the authors and do not necessarily reflect the views of MESCyT.

---

**Built for preserving Dominican culinary culture and linguistic heritage**

</details>

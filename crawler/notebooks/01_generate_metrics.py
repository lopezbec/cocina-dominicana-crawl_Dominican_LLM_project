# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: dominican-llm-scraper (3.12.12)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 01 - Generate Metrics

# %%
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal, cast

import nltk
import numpy as np
import pandas as pd
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer

nltk.download("stopwords", quiet=True)

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

SPANISH_STOPWORDS = set(stopwords.words("spanish"))
TOKEN_RE = re.compile(r"[a-záéíóúüñ]+", re.IGNORECASE)
SUPPORTED_SELECTION_MODES = {"full", "doc_ids", "filenames", "urls", "domain"}
SelectionMode = Literal["full", "doc_ids", "filenames", "urls", "domain"]


SELECTION: dict[str, Any] = {
    "mode": "full",
    "values": [],
    "label": "full_corpus",
}


def get_project_root() -> Path:
    """Locate project root from notebook or repo root execution."""
    cwd = Path.cwd()
    if (cwd / "data" / "processed").exists():
        return cwd
    if (cwd.parent / "data" / "processed").exists():
        return cwd.parent
    raise FileNotFoundError("Could not find data/processed from current directory")


def require_columns(frame: pd.DataFrame, required: list[str], label: str) -> None:
    """Fail early when a required input schema is missing columns."""
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"{label} is missing required columns: {missing_list}")


def validate_selection_config(selection: dict[str, Any]) -> tuple[SelectionMode, list[str], str]:
    """Validate and normalize notebook selection settings."""
    mode_raw = str(selection.get("mode", "full")).strip().lower()
    if mode_raw not in SUPPORTED_SELECTION_MODES:
        supported = ", ".join(sorted(SUPPORTED_SELECTION_MODES))
        raise ValueError(f"Unsupported SELECTION['mode']: {mode_raw}. Expected one of: {supported}")

    values_raw = selection.get("values", [])
    if values_raw is None:
        values_raw = []
    if not isinstance(values_raw, list):
        raise ValueError("SELECTION['values'] must be a list of strings.")

    values = [str(value).strip() for value in values_raw if str(value).strip()]
    mode = cast(SelectionMode, mode_raw)
    if mode != "full" and not values:
        raise ValueError(f"SELECTION['values'] must contain at least one value when mode='{mode}'.")

    label = str(selection.get("label", "")).strip() or "full_corpus"
    safe_label = re.sub(r"[^a-z0-9_-]+", "_", label.lower()).strip("_")
    if not safe_label:
        raise ValueError("SELECTION['label'] must contain at least one alphanumeric character.")

    return mode, values, safe_label


def filter_metadata(meta: pd.DataFrame, mode: SelectionMode, values: list[str]) -> pd.DataFrame:
    """Return the metadata slice requested by the notebook selection."""
    if mode == "full":
        return meta.copy()

    selector_map = {
        "doc_ids": "doc_id",
        "filenames": "filename",
        "urls": "url",
        "domain": "domain",
    }
    column = selector_map[mode]
    require_columns(meta, [column], "metadata_plaintext.jsonl")

    selected = meta[meta[column].astype(str).isin(values)].copy()
    if selected.empty:
        value_preview = ", ".join(values[:5])
        raise ValueError(f"Selection mode '{mode}' matched zero rows for values: {value_preview}")

    return selected


def build_selected_text_paths(processed_dir: Path, meta: pd.DataFrame) -> list[Path]:
    """Resolve filtered plaintext filenames into existing text file paths."""
    require_columns(meta, ["filename"], "filtered metadata")

    txt_files = [processed_dir / filename for filename in meta["filename"].astype(str).tolist()]
    missing = [path.name for path in txt_files if not path.exists()]
    if missing:
        preview = ", ".join(missing[:5])
        raise FileNotFoundError(f"Selected plaintext files are missing from {processed_dir}: {preview}")

    return txt_files


def get_metrics_output_dir(metrics_root: Path, label: str) -> Path:
    """Create and return the selection-specific metrics output directory."""
    output_dir = metrics_root / label
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


PROJECT_ROOT = get_project_root()
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
METADATA_FILE = PROCESSED_DIR / "metadata_plaintext.jsonl"
METRICS_ROOT = PROCESSED_DIR / "eda_metrics"
METRICS_ROOT.mkdir(parents=True, exist_ok=True)

if not METADATA_FILE.exists():
    raise FileNotFoundError(f"Missing metadata file: {METADATA_FILE}. Run the plaintext processing step first.")

# %% [markdown]
# ## Inputs
#
# Read metadata and plaintext files from `data/processed`.

# %%
records = []
with open(METADATA_FILE, "r", encoding="utf-8") as f:
    for line in f:
        records.append(json.loads(line))

meta = pd.DataFrame(records)
require_columns(meta, ["doc_id", "domain", "filename", "url", "word_count", "char_count"], "metadata_plaintext.jsonl")

selection_mode, selection_values, selection_label = validate_selection_config(SELECTION)
meta = filter_metadata(meta, selection_mode, selection_values)
METRICS_DIR = get_metrics_output_dir(METRICS_ROOT, selection_label)

txt_files = build_selected_text_paths(PROCESSED_DIR, meta)
if not txt_files:
    raise FileNotFoundError(f"No selected .txt files found in {PROCESSED_DIR}")

all_texts = [p.read_text(encoding="utf-8") for p in txt_files]

# %% [markdown]
# ## 1) `meta_enriched.csv`
#
# Add a compact readability ratio (`chars_per_word`).

# %%
meta_enriched = meta.copy()
meta_enriched["chars_per_word"] = (meta_enriched["char_count"] / meta_enriched["word_count"].replace(0, np.nan)).round(
    2
)
meta_enriched.to_csv(METRICS_DIR / "meta_enriched.csv", index=False, encoding="utf-8")

# %% [markdown]
# ## 2) `top50_words.csv`
#
# Build a stopword-filtered corpus frequency table.


# %%
def extract_tokens(text: str) -> list[str]:
    raw_tokens = TOKEN_RE.findall(text.lower())
    return [token for token in raw_tokens if token not in SPANISH_STOPWORDS and len(token) >= 3]


def build_top_ngrams(token_lists: list[list[str]], n: int, top_k: int = 20) -> pd.DataFrame:
    ngrams = [" ".join(tokens[i : i + n]) for tokens in token_lists for i in range(len(tokens) - n + 1)]
    if not ngrams:
        return pd.DataFrame(columns=["ngram", "count", "pct_of_corpus"])

    freq = Counter(ngrams)
    top_df = pd.DataFrame(freq.most_common(top_k), columns=["ngram", "count"])
    top_df["pct_of_corpus"] = (top_df["count"] / len(ngrams) * 100).round(3)
    return top_df


filtered_token_lists = [extract_tokens(text) for text in all_texts]
all_tokens = [token for tokens in filtered_token_lists for token in tokens]

freq = Counter(all_tokens)
top50_df = pd.DataFrame(freq.most_common(50), columns=["word", "count"])

if len(all_tokens) == 0:
    logger.warning("No valid tokens found after filtering; writing empty top50_words.csv")
    top50_df = pd.DataFrame(columns=["word", "count", "pct_of_corpus"])
else:
    top50_df["pct_of_corpus"] = (top50_df["count"] / len(all_tokens) * 100).round(3)

top50_df.to_csv(METRICS_DIR / "top50_words.csv", index=False, encoding="utf-8")

# %% [markdown]
# ## 3) `top20_bigrams.csv` and `top20_trigrams.csv`
#
# Build corpus-level n-gram tables from the filtered tokens.

# %%
build_top_ngrams(filtered_token_lists, n=2).to_csv(METRICS_DIR / "top20_bigrams.csv", index=False, encoding="utf-8")
build_top_ngrams(filtered_token_lists, n=3).to_csv(METRICS_DIR / "top20_trigrams.csv", index=False, encoding="utf-8")

# %% [markdown]
# ## 4) TF-IDF outputs
#
# Write both `tfidf_top30_terms.csv` and `tfidf_heatmap_sample.csv`.

# %%
vectorizer = TfidfVectorizer(
    token_pattern=r"[a-záéíóúüñ]{3,}",
    stop_words=list(SPANISH_STOPWORDS),
    max_features=5000,
    sublinear_tf=True,
)

try:
    tfidf_matrix = cast(Any, vectorizer.fit_transform(all_texts))
    feature_names = vectorizer.get_feature_names_out()

    mean_tfidf = np.asarray(tfidf_matrix.mean(axis=0)).flatten()
    top30_idx = mean_tfidf.argsort()[::-1][:30]

    top30_terms = pd.DataFrame(
        {
            "term": feature_names[top30_idx],
            "mean_tfidf": mean_tfidf[top30_idx].round(5),
        }
    )

    rng = np.random.default_rng(seed=42)
    sample_size = min(40, tfidf_matrix.shape[0])
    sample_idx = np.sort(rng.choice(tfidf_matrix.shape[0], size=sample_size, replace=False))

    heatmap_data = pd.DataFrame(
        tfidf_matrix[sample_idx][:, top30_idx].toarray(),
        columns=feature_names[top30_idx],
    )
    heatmap_data.insert(0, "doc_label", [txt_files[i].stem[:30] for i in sample_idx])
except ValueError:
    logger.warning("TF-IDF vocabulary is empty; writing empty TF-IDF artifacts")
    top30_terms = pd.DataFrame(columns=["term", "mean_tfidf"])
    heatmap_data = pd.DataFrame(columns=["doc_label"])

top30_terms.to_csv(METRICS_DIR / "tfidf_top30_terms.csv", index=False, encoding="utf-8")
heatmap_data.to_csv(METRICS_DIR / "tfidf_heatmap_sample.csv", index=False, encoding="utf-8")

# %% [markdown]
# ## 5) Quality slices
#
# Export shortest and longest documents by `word_count`.

# %%
quality_cols = ["filename", "word_count", "char_count"]
meta_sorted_words = meta.sort_values("word_count")

meta_sorted_words[quality_cols].head(10).to_csv(METRICS_DIR / "quality_shortest_10.csv", index=False, encoding="utf-8")
meta_sorted_words[quality_cols].tail(10).to_csv(METRICS_DIR / "quality_longest_10.csv", index=False, encoding="utf-8")

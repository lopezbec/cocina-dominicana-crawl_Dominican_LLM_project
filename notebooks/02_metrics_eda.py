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
# # 02 - Metrics EDA

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import Markdown, display


def get_project_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "data" / "processed").exists():
        return cwd
    if (cwd.parent / "data" / "processed").exists():
        return cwd.parent
    raise FileNotFoundError("Could not find data/processed from current directory")


PROJECT_ROOT = get_project_root()
METRICS_DIR = PROJECT_ROOT / "data" / "processed" / "eda_metrics"

sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams["figure.dpi"] = 120
plt.rcParams["figure.figsize"] = (10, 5)

required_files = [
    "meta_enriched.csv",
    "top50_words.csv",
    "tfidf_top30_terms.csv",
    "tfidf_heatmap_sample.csv",
    "quality_shortest_10.csv",
    "quality_longest_10.csv",
]
missing_files = [name for name in required_files if not (METRICS_DIR / name).exists()]
if missing_files:
    missing_text = ", ".join(missing_files)
    raise FileNotFoundError(f"Missing metrics files: {missing_text}. Run notebooks/01_generate_metrics.py.")

# %% [markdown]
# ## Load metrics CSVs

# %%
meta = pd.read_csv(METRICS_DIR / "meta_enriched.csv", encoding="utf-8")
top50_df = pd.read_csv(METRICS_DIR / "top50_words.csv", encoding="utf-8")
top30_terms = pd.read_csv(METRICS_DIR / "tfidf_top30_terms.csv", encoding="utf-8")
heatmap_df = pd.read_csv(METRICS_DIR / "tfidf_heatmap_sample.csv", encoding="utf-8")
shortest_10 = pd.read_csv(METRICS_DIR / "quality_shortest_10.csv", encoding="utf-8")
longest_10 = pd.read_csv(METRICS_DIR / "quality_longest_10.csv", encoding="utf-8")

# %% [markdown]
# ## Corpus overview

# %%
n_files = len(meta)
total_words = meta["word_count"].sum()
total_chars = meta["char_count"].sum()
total_urls = meta["url"].nunique()

summary = pd.DataFrame({
    "Metric": ["Total files (.txt)", "Total words", "Total characters", "Unique URLs"],
    "Value": [f"{n_files:,}", f"{total_words:,}", f"{total_chars:,}", f"{total_urls:,}"],
})

display(summary)

# %%
desc = meta[["word_count", "char_count"]].describe().round(1)
desc.index.name = "stat"
display(desc)

# %%
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

p95_words = meta["word_count"].quantile(0.95)
p95_chars = meta["char_count"].quantile(0.95)
n_beyond_words = int((meta["word_count"] > p95_words).sum())
n_beyond_chars = int((meta["char_count"] > p95_chars).sum())
wc_clipped = meta.loc[meta["word_count"] <= p95_words, "word_count"]
cc_clipped = meta.loc[meta["char_count"] <= p95_chars, "char_count"]

wc_bins = np.histogram_bin_edges(wc_clipped, bins="fd")
cc_bins = np.histogram_bin_edges(cc_clipped, bins="fd")

# --- Plot 1: Word Count ---
axes[0].hist(wc_clipped, bins=wc_bins, color="steelblue", edgecolor="white", linewidth=0.4)
axes[0].axvline(
    meta["word_count"].median(),
    color="tomato",
    linestyle="--",
    linewidth=1.5,
    label=f"Median {meta['word_count'].median():,.0f}",
)
axes[0].axvline(
    p95_words,
    color="black",
    linestyle=":",
    linewidth=1.2,
    label=f"P95 {p95_words:,.0f}",
)
sns.kdeplot(wc_clipped, ax=axes[0], color="black", linewidth=1.0)
axes[0].set_title(
    f"Word Count - 95th Percentile View\nP95 cutoff, 5% of docs (N={n_beyond_words}) beyond",
    fontsize=11,
)
axes[0].set_xlabel("Words")
axes[0].set_ylabel("Number of Documents")
axes[0].set_xlim(0, p95_words)
axes[0].legend()

# --- Plot 2: Character Count ---
axes[1].hist(cc_clipped, bins=cc_bins, color="mediumseagreen", edgecolor="white", linewidth=0.4)
axes[1].axvline(
    meta["char_count"].median(),
    color="tomato",
    linestyle="--",
    linewidth=1.5,
    label=f"Median {meta['char_count'].median():,.0f}",
)
axes[1].axvline(
    p95_chars,
    color="black",
    linestyle=":",
    linewidth=1.2,
    label=f"P95 {p95_chars:,.0f}",
)
sns.kdeplot(cc_clipped, ax=axes[1], color="black", linewidth=1.0)
axes[1].set_title(
    f"Character Count - 95th Percentile View\nP95 cutoff, 5% of docs (N={n_beyond_chars}) beyond",
    fontsize=11,
)
axes[1].set_xlabel("Characters")
axes[1].set_ylabel("Number of Documents")
axes[1].set_xlim(0, p95_chars)
axes[1].legend()

plt.tight_layout()
plt.show()


# %%
fig, ax = plt.subplots(figsize=(10, 4))
chars_per_word_values = [float(value) for value in meta["chars_per_word"].dropna().tolist()]
chars_per_word_mean = sum(chars_per_word_values) / len(chars_per_word_values)
ax.hist(chars_per_word_values, bins=40, color="mediumpurple", edgecolor="white", linewidth=0.4)
ax.axvline(
    chars_per_word_mean,
    color="tomato",
    linestyle="--",
    linewidth=1.5,
    label=f"Mean {chars_per_word_mean:.2f} chars/word",
)
ax.set_title("Average Characters per Word (per Document)")
ax.set_xlabel("Chars / Word")
ax.set_ylabel("Number of Documents")
ax.legend()
plt.tight_layout()
plt.show()

# %% [markdown]
# ## Word frequency

# %%
display(top50_df.head(15))

# %%
fig, ax = plt.subplots(figsize=(14, 7))

bars = ax.barh(top50_df["word"][::-1], top50_df["count"][::-1], color="steelblue")
ax.bar_label(bars, fmt="{:,.0f}", padding=4, fontsize=8)
ax.set_title("Top 50 Words by Frequency (Spanish stopwords removed)")
ax.set_xlabel("Count")
ax.set_ylabel("Word")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
plt.tight_layout()
plt.show()

# %% [markdown]
# ## TF-IDF

# %%
display(top30_terms.head(15))

# %%
fig, ax = plt.subplots(figsize=(13, 6))
sns.barplot(data=top30_terms, y="term", x="mean_tfidf", color="steelblue", ax=ax)
ax.set_title("Top 30 Terms by Mean TF-IDF (corpus-wide)")
ax.set_xlabel("Mean TF-IDF Score")
ax.set_ylabel("Term")
plt.tight_layout()
plt.show()

# %%
heatmap_data = heatmap_df.set_index("doc_label")
if heatmap_data.shape[1] == 0:
    display(Markdown("**TF-IDF heatmap skipped:** no TF-IDF term columns are available."))
else:
    fig, ax = plt.subplots(figsize=(16, 12))
    sns.heatmap(
        heatmap_data,
        cmap="YlOrRd",
        linewidths=0.3,
        linecolor="white",
        ax=ax,
        cbar_kws={"label": "TF-IDF Score"},
    )
    ax.set_title("TF-IDF Heatmap - Top 30 Terms x 40 Random Documents")
    ax.set_xlabel("Term")
    ax.set_ylabel("Document")
    ax.tick_params(axis="x", rotation=45)
    ax.tick_params(axis="y", labelsize=7)
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ## Data quality notes

# %%
display(shortest_10)

# %%
display(longest_10)

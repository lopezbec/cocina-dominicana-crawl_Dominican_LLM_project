# Crawler package

The crawler is responsible for the first two stages of the Dominican Spanish corpus pipeline:

1. discovering and scraping pages through a local Firecrawl service;
2. converting Firecrawl Markdown to plain text and producing duplicate evidence.

The repository-level [`README.md`](../README.md) is the documentation entry point. Its collapsed **Crawling** and **Cleaning and deduplication** sections describe the implementation, output contracts, commands, and known limitations.

```console
$ uv sync
$ make firecrawl-start
$ make firecrawl-test
$ make scrape
```

Cleaning also runs semantic deduplication and therefore requires local Ollama with `qwen3-embedding:0.6b`:

```console
$ ollama pull qwen3-embedding:0.6b
$ ollama serve

# In another terminal, from crawler/
$ make process
```

Run `make help` for the commands implemented by the current [`Makefile`](Makefile).

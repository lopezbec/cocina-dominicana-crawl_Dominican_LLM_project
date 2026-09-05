# Processor package

This project converts the crawler's Firecrawl Markdown into plain text and runs the four-stage duplicate analysis.

The repository-level [`README.md`](../README.md) is the documentation entry point. Open **Cleaning and deduplication** there for the processing order, thresholds, report schema, implementation links, and limitations.

```console
$ uv sync
$ ollama pull qwen3-embedding:0.6b
$ ollama serve

# In another terminal, from processor/
$ make process
```

Defaults are defined in [`config/config.yml`](config/config.yml): raw input comes from `../crawler/data/raw`, and processed files are written to `data/processed`.

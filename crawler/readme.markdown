# Crawler package

This project discovers and scrapes web pages through a locally hosted Firecrawl service. It writes raw Markdown and source metadata to `data/raw`.

The repository-level [`README.md`](../README.md) is the documentation entry point. Open **Crawling** there for configuration, discovery behavior, output contracts, implementation links, and limitations.

```console
$ uv sync
$ make firecrawl-start
$ make firecrawl-test
$ make scrape
```

Run `make help` for the commands implemented by the current [`Makefile`](Makefile). Plain-text cleaning and deduplication now live in the peer [`processor`](../processor) project.

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import mistune
from bs4 import BeautifulSoup
from wordfreq import get_frequency_dict

from dominican_llm_scraper.utils.file_utils import create_safe_filename


# ---------------------------------------------------------------------------
# Universal boilerplate patterns — applied to PLAIN TEXT after mistune
# conversion. Each pattern verified across 3+ domains. All line-scoped
# (re.MULTILINE, no DOTALL) to avoid eating past line boundaries.
# ---------------------------------------------------------------------------
_BOILERPLATE_PATTERNS: list[re.Pattern] = [
    # "In English" navigation line
    re.compile(r"^In English\s*$", re.MULTILINE),
    # Skip-navigation lines (WordPress Genesis "Saltar a…")
    re.compile(r"^Saltar a[^\n]{0,80}$", re.MULTILINE),
    # Inline SVG placeholder alt text left by mistune (data:image/svg lines)
    re.compile(r"^data:image/svg[^\n]*$", re.MULTILINE),
    # Copyright line
    re.compile(r"^©\s*\d{4}[^\n]*$", re.MULTILINE),
    # Privacy/cookie policy nav items
    re.compile(r"^Política de (?:privacidad|cookies)[^\n]*$", re.MULTILINE),
    # "Follow us" social prompt lines
    re.compile(r"^Síguenos en[:\s][^\n]*$", re.MULTILINE),
    # "Suscríbete … para recibir" newsletter line
    re.compile(r"^[^\n]*Suscríbete[^\n]*para recibir[^\n]*$", re.MULTILINE),
    # Lone dash/bullet lines (empty list artifacts from mistune)
    re.compile(r"^\s*[-•]\s*$", re.MULTILINE),
    # Greek delta — WordPress anti-spam hidden field
    re.compile(r"Δ"),
    # Bare social platform name lines left after link stripping
    re.compile(
        r"^(?:Facebook|Instagram|YouTube|WhatsApp|Twitter|X|Reddit|LinkedIn)\s*$",
        re.MULTILINE | re.IGNORECASE,
    ),
]

# ---------------------------------------------------------------------------
# Footer truncation anchors — markers confirmed to appear at or near document
# end across the corpus.  Cut point = earliest match among all anchors.
# ---------------------------------------------------------------------------
_FOOTER_ANCHORS: tuple[str, ...] = (
    "Suscríbete para recibir",  # newsletter CTA — multi-domain (one, bancentral, cocinadominicana)
    "©",  # copyright line — multi-domain (minpre, minerd, los-poetas, …)
    "wpDiscuz",  # WordPress comment plugin footer — always terminal
    "Este sitio usa Akismet",  # Akismet anti-spam notice — always in WP comment section
    "Rating Receta",  # WordPress recipe-rating widget — always in comment form, never prose
)


class ContentProcessor:
    """Single-pass Markdown → plain-text cleaner for the Dominican LLM corpus.

    Pipeline (in order):
        1. Strip YAML frontmatter
        2. Apply universal boilerplate regexes (line-scoped, no DOTALL)
        3. Convert Markdown → plain text via mistune + BeautifulSoup
        4. Truncate at footer anchors
        5. Normalize whitespace
        6. Optionally filter English words (wordfreq large dicts, pre-loaded)

    All steps are universal — no site-specific logic.
    """

    def __init__(self, config: Optional[Any] = None) -> None:
        # Pre-load frequency dicts once (~50 ms) for 200x faster per-word lookup.
        # Large wordlist covers Dominican vocabulary: sancocho, mangú, habichuela…
        self._en_freq: dict = get_frequency_dict("en", wordlist="large")
        self._es_freq: dict = get_frequency_dict("es", wordlist="large")
        # config kept for call-site compatibility; not used internally.
        _ = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(
        self,
        markdown_content: str,
        filter_english: bool = True,
    ) -> Tuple[Dict, str]:
        """Convert raw Firecrawl markdown to clean plain text.

        Pipeline:
            1. Strip YAML frontmatter
            2. Convert Markdown → plain text (mistune + BeautifulSoup)
            3. Remove universal boilerplate patterns (on plain text)
            4. Truncate at footer anchors
            5. Normalize whitespace
            6. Optionally filter English words

        Args:
            markdown_content: Raw markdown string (may include YAML frontmatter).
            filter_english: Remove words that are more English than Spanish.

        Returns:
            (frontmatter_dict, plain_text)
        """
        frontmatter, body = self._extract_frontmatter(markdown_content)
        text = self._markdown_to_text(body)
        text = self._remove_boilerplate(text)
        text = self._truncate_at_footer(text)
        text = self._normalize_whitespace(text)
        if filter_english:
            text = self.filter_english_words(text)
        return frontmatter, text

    # Backward-compatible alias used by process_all_files and existing tests.
    def process_markdown_to_plain_text(
        self,
        markdown_content: str,
        filter_english: bool = True,
    ) -> Tuple[Dict, str]:
        return self.clean(markdown_content, filter_english=filter_english)

    # ------------------------------------------------------------------
    # Private pipeline steps
    # ------------------------------------------------------------------

    def _extract_frontmatter(self, content: str) -> Tuple[Dict, str]:
        """Strip YAML frontmatter block and return (metadata_dict, body)."""
        frontmatter: Dict = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        frontmatter[key.strip()] = value.strip().strip('"')
                body = parts[2].strip()

        return frontmatter, body

    def _remove_boilerplate(self, text: str) -> str:
        """Remove universal navigation / UI boilerplate from plain text.

        Operates on plain text (post-mistune), using line-scoped patterns only.
        """
        for pattern in _BOILERPLATE_PATTERNS:
            text = pattern.sub("", text)
        return text

    def _markdown_to_text(self, text: str) -> str:
        """Convert Markdown to plain text using mistune + BeautifulSoup.

        This replaces ~20 hand-rolled regexes and correctly handles:
        - Nested formatting (bold+link, em+code)
        - Tables → cell text (preserves content, removes pipes)
        - Escaped characters per CommonMark spec
        - Emoji and Unicode passthrough (no normalization)
        """
        html = mistune.create_markdown()(text)
        return BeautifulSoup(html, "html.parser").get_text(separator="\n")

    def _truncate_at_footer(self, text: str) -> str:
        """Truncate text at the first footer anchor occurrence.

        Only anchors confirmed to appear at document-end (≥ 95th percentile
        position) across multiple domains are used.  A trailing bare "Label"
        line (empty HTML widget) is stripped after truncation.
        """
        cut = len(text)
        for anchor in _FOOTER_ANCHORS:
            pos = text.find(anchor)
            if 0 < pos < cut:
                cut = pos
        text = text[:cut]
        # Strip trailing bare "Label" line left by empty <label> HTML element
        text = re.sub(r"\n+Label\s*$", "", text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Collapse excessive blank lines, trailing spaces, and stray brackets."""
        # Unwrap any remaining [text] brackets (leftover from partial link stripping).
        # Limit inner match to 200 chars to avoid backtracking on large tables.
        text = re.sub(r"\[\s*\]", "", text)
        text = re.sub(r"\[(.{1,200}?)\]", r"\1", text, flags=re.DOTALL)
        # Remove orphaned opening brackets and image-link prefixes not caught above
        text = re.sub(r"!\s*\[", "", text)
        text = re.sub(r"\[\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        lines = [line.rstrip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    # ------------------------------------------------------------------
    # English word filter (public — used by tests)
    # ------------------------------------------------------------------

    def is_likely_english_word(self, word: str, threshold: float = 1e-6) -> bool:
        """Return True if word is more English than Spanish.

        Uses pre-loaded large wordfreq dicts for O(1) lookup per word.
        """
        w = word.lower()
        if len(w) <= 2:
            return False

        en = self._en_freq.get(w, 0.0)
        es = self._es_freq.get(w, 0.0)

        if en == 0.0 and es == 0.0:
            return False
        if es >= en * 2:
            return False
        return en > threshold and en > es

    def filter_english_words(
        self,
        text: str,
        preserve_proper_nouns: bool = True,
    ) -> str:
        """Remove English words from Spanish text, line by line.

        Args:
            text: Input plain text.
            preserve_proper_nouns: Keep capitalized tokens (acronyms, names).

        Returns:
            Text with English-dominant words removed.
        """
        _TOKEN = re.compile(r"\b[\w\u00C0-\u017F]+\b|\S")
        _IS_WORD = re.compile(r"\b[\w\u00C0-\u017F]+\b")

        filtered_lines = []
        for line in text.split("\n"):
            if not line.strip():
                filtered_lines.append(line)
                continue

            kept = []
            for token in _TOKEN.findall(line):
                if not _IS_WORD.match(token):
                    kept.append(token)
                    continue
                if preserve_proper_nouns and token[0].isupper():
                    kept.append(token)
                    continue
                if not self.is_likely_english_word(token):
                    kept.append(token)

            joined = " ".join(kept)
            joined = re.sub(r"\s+([.,;:!?)])", r"\1", joined)
            joined = re.sub(r"([¿¡(])\s+", r"\1", joined)
            joined = re.sub(r" {2,}", " ", joined)
            if joined.strip():
                filtered_lines.append(joined)

        return "\n".join(filtered_lines)

    # ------------------------------------------------------------------
    # Legacy public methods — kept so existing call sites don't break.
    # New code should call clean() instead.
    # ------------------------------------------------------------------

    def extract_frontmatter(self, content: str) -> Tuple[Dict, str]:
        return self._extract_frontmatter(content)

    def remove_excessive_whitespace(self, text: str) -> str:
        return self._normalize_whitespace(text)


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------


def process_all_files(
    input_dir: Path,
    output_dir: Path,
    config: Any,
    processing_patterns: Any = None,  # Deprecated, kept for compatibility
) -> None:
    """Process all scraped markdown files to plaintext.

    Args:
        input_dir: Directory containing scraped markdown files.
        output_dir: Directory to save processed plaintext files.
        config: Config object (used for min_content_length only).
        processing_patterns: Deprecated, unused.
    """
    processor = ContentProcessor()

    metadata_file = input_dir / "metadata.jsonl"
    if not metadata_file.exists():
        print(f"Error: {metadata_file} not found")
        print("Please run the scraper first to generate scraped content")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_entries: list[Dict] = []
    with open(metadata_file, "r", encoding="utf-8") as f:
        for line in f:
            metadata_entries.append(json.loads(line))

    print(f"Found {len(metadata_entries)} documents to process")

    processed_metadata: list[Dict] = []
    stats: Dict = {
        "total_processed": 0,
        "total_words": 0,
        "total_chars": 0,
        "categories": {},
        "domains": {},
    }

    min_content_length: int = config.processing.get("min_content_length", 100)

    for meta in metadata_entries:
        doc_id = meta["doc_id"]
        domain = meta.get("domain", "unknown")
        domain_slug = domain.replace(".", "_")
        safe_slug = create_safe_filename(meta["url_slug"])
        filename = f"{meta['doc_id']}_{domain_slug}_{safe_slug}.md"
        category = meta.get("category", "unknown")

        md_file = input_dir / filename
        if not md_file.exists():
            print(f"Warning: File not found: {filename}")
            continue

        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            _frontmatter, plain_text = processor.clean(content)

            if len(plain_text.strip()) < min_content_length:
                print(f"Skipping {filename}: content too short")
                continue

            output_filename = f"{doc_id}_{domain_slug}_{safe_slug}.txt"
            output_file = output_dir / output_filename

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(plain_text)

            word_count = len(plain_text.split())
            char_count = len(plain_text)

            plain_meta: Dict = {
                "doc_id": doc_id,
                "domain": domain,
                "filename": output_filename,
                "source_md": filename,
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
                "category": category,
                "word_count": word_count,
                "char_count": char_count,
                "original_word_count": meta.get("word_count", 0),
            }

            processed_metadata.append(plain_meta)

            stats["total_processed"] += 1
            stats["total_words"] += word_count
            stats["total_chars"] += char_count

            cat_stats = stats["categories"].setdefault(category, {"count": 0, "words": 0, "chars": 0})
            cat_stats["count"] += 1
            cat_stats["words"] += word_count
            cat_stats["chars"] += char_count

            dom_stats = stats["domains"].setdefault(domain, {"count": 0, "words": 0, "chars": 0})
            dom_stats["count"] += 1
            dom_stats["words"] += word_count
            dom_stats["chars"] += char_count

            print(f"Processed: {filename} -> {output_filename} ({word_count} words)")

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue

    plain_metadata_file = output_dir / "metadata_plaintext.jsonl"
    with open(plain_metadata_file, "w", encoding="utf-8") as f:
        for meta in processed_metadata:
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")

    stats_file = output_dir / "corpus_stats_plaintext.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print("Processing Complete!")
    print(f"{'=' * 70}")
    print(f"Total documents processed: {stats['total_processed']}")
    print(f"Total words:               {stats['total_words']:,}")
    print(f"Total characters:          {stats['total_chars']:,}")

    print("\nBy domain:")
    for domain, ds in stats["domains"].items():
        print(f"  {domain}: {ds['count']} docs, {ds['words']:,} words")

    print("\nBy category:")
    for cat, cs in stats["categories"].items():
        print(f"  {cat}: {cs['count']} docs, {cs['words']:,} words")

    print("\nOutput:")
    print(f"  Plain text files: {output_dir}/")
    print(f"  Metadata:         {plain_metadata_file}")
    print(f"  Statistics:       {stats_file}")


if __name__ == "__main__":
    import sys

    from dominican_llm_scraper.core.config_loader import load_config

    try:
        config = load_config()

        input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(config.get("output_dir", "data/raw"))
        output_dir = (
            Path(sys.argv[2]) if len(sys.argv) > 2 else Path(config.get("plaintext_output_dir", "data/processed"))
        )

        if not input_dir.exists():
            print(f"Error: Input directory '{input_dir}' does not exist")
            print("Usage: python -m dominican_llm_scraper.core.processor [input_dir] [output_dir]")
            sys.exit(1)

        print(f"Input directory:  {input_dir}")
        print(f"Output directory: {output_dir}")
        print()

        process_all_files(input_dir, output_dir, config)

    except (ValueError, FileNotFoundError) as e:
        print(str(e))
        sys.exit(1)

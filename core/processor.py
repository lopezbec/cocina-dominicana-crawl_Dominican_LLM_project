import re
import json
from pathlib import Path
from typing import Dict, Tuple, Optional, Any
from wordfreq import word_frequency


class ContentProcessor:
    def __init__(
        self, config: Any, processing_patterns: Optional[Dict[str, Any]] = None
    ):
        self.config = config
        self.processing_patterns = processing_patterns or {}

    def extract_frontmatter(self, content: str) -> Tuple[Dict, str]:
        frontmatter = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1].strip()
                body = parts[2].strip()

                for line in frontmatter_text.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        frontmatter[key.strip()] = value.strip().strip('"')

        return frontmatter, body

    def remove_navigation_elements(self, text: str) -> str:
        patterns_to_remove = [
            r"\*\s+\[Saltar a[^\]]+\]\([^\)]+\)",
            r"\[In English\]\([^\)]+\)",
            r"!\[.*?\]\(data:image/svg\+xml[^\)]+\)",
            r"\*\*SALTAR A:\*\*[^\n]+",
            r"\[mostrar[^\]]*\]\([^\)]+\)",
            r"Revisado:[^\n]+Publicado:[^\n]+",
            r"\[❤\]\([^\)]+\)",
            r"\[?\]\s*\([^\)]*facebook[^\)]*\)",
            r"\[?\]\s*\([^\)]*instagram[^\)]*\)",
            r"\[?\]\s*\([^\)]*youtube[^\)]*\)",
            r"\[?\]\s*\([^\)]*whatsapp[^\)]*\)",
            r"\[?\]\s*\([^\)]*twitter[^\)]*\)",
            r"\[?\]\s*\([^\)]*reddit[^\)]*\)",
            r"\[?\]\s*\(mailto:[^\)]+\)",
            r"Share on (Facebook|WhatsApp|Reddit).*",
            r"Send over email.*",
            r"Label.*",
            r"Rating Receta.*",
            r"Nombre\\*?.*",
            r"Email\\*?.*",
            r"wpDiscuz.*",
            r"Insert.*",
            r"View all comments.*",
            r"Load More Comments.*",
            r"Inline Feedbacks.*",
            r"You are going to send email.*",
            r"Move Comment.*",
            r"Move \].*",
            r"Este sitio usa Akismet.*",
            r"Aprende cómo se procesan.*",
            r"\d+ Commentario.*",
            r"Populares.*",
            r"Recientes Viejos.*",
            r"Δ",
            r"^\s*-\s*$",
        ]

        custom_patterns = self.processing_patterns.get("navigation_patterns", [])
        patterns_to_remove.extend(custom_patterns)

        cleaned = text
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE | re.DOTALL)

        return cleaned

    def clean_markdown_syntax(self, text: str) -> str:
        text = re.sub(r"[\U0001F300-\U0001F9FF]", "", text)
        text = re.sub(r"[\U0001F600-\U0001F64F]", "", text)
        text = re.sub(r"[\U0001F680-\U0001F6FF]", "", text)
        text = re.sub(r"[\U0001F1E0-\U0001F1FF]", "", text)
        text = re.sub(r"[\u2600-\u26FF]", "", text)
        text = re.sub(r"[\u2700-\u27BF]", "", text)
        text = re.sub(r"[\U0001F900-\U0001F9FF]", "", text)

        text = re.sub(r"\[\(https?://[^\)]+\)\]", "", text)
        text = re.sub(r"\(https?://[^\)]+\)", "", text)

        text = re.sub(r"\[\s*\]", "", text)

        text = re.sub(r"\*\*\s*-\s*", "", text)
        text = re.sub(r"^\*\*\s*$", "", text, flags=re.MULTILINE)

        text = re.sub(r"\[\\?\d+\\?\]", "", text)

        text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        text = re.sub(r"#{1,6}\s+", "", text)
        text = re.sub(r"\*\*\*([^\*]+)\*\*\*", r"\1", text)
        text = re.sub(r"\*\*([^\*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^\*]+)\*", r"\1", text)
        text = re.sub(r"_([^_]+)_", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"^[-\*]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\|\s*.*\s*\|$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\|[-:\s|]+\|$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[-*_]{3,}$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\\", "", text)

        return text

    def remove_footer_sections(self, text: str) -> str:
        footer_markers = [
            "Referencias",
            "Fuentes",
        ]

        custom_markers = self.processing_patterns.get("footer_markers", [])
        footer_markers.extend(custom_markers)

        min_pos = len(text)
        for marker in footer_markers:
            pos = text.find(marker)
            if pos != -1 and pos < min_pos:
                min_pos = pos

        if min_pos < len(text):
            text = text[:min_pos]

        return text

    def remove_excessive_whitespace(self, text: str) -> str:
        text = re.sub(r"\[\s*\n*\s*\]", "", text)
        text = re.sub(r"\[([^\]]+)\]", r"\1", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)
        return text.strip()

    def is_likely_english_word(self, word: str, threshold: float = 1e-6) -> bool:
        word_lower = word.lower()

        if len(word_lower) <= 2:
            return False

        en_freq = word_frequency(word_lower, "en")
        es_freq = word_frequency(word_lower, "es")

        if en_freq == 0 and es_freq == 0:
            return False

        if es_freq >= en_freq * 2:
            return False

        return en_freq > threshold and en_freq > es_freq

    def filter_english_words(
        self, text: str, preserve_proper_nouns: bool = True
    ) -> str:
        lines = text.split("\n")
        filtered_lines = []

        for line in lines:
            if not line.strip():
                filtered_lines.append(line)
                continue

            words = re.findall(r"\b[\w\u00C0-\u017F]+\b|\S", line)
            filtered_words = []

            for word in words:
                if not re.match(r"\b[\w\u00C0-\u017F]+\b", word):
                    filtered_words.append(word)
                    continue

                if preserve_proper_nouns and word[0].isupper():
                    filtered_words.append(word)
                    continue

                if not self.is_likely_english_word(word):
                    filtered_words.append(word)

            filtered_line = " ".join(filtered_words)
            filtered_line = re.sub(r"\s+([.,;:!?)])", r"\1", filtered_line)
            filtered_line = re.sub(r"([¿¡(])\s+", r"\1", filtered_line)
            filtered_line = re.sub(r" {2,}", " ", filtered_line)

            if filtered_line.strip():
                filtered_lines.append(filtered_line)

        return "\n".join(filtered_lines)

    def process_markdown_to_plain_text(
        self, markdown_content: str, filter_english: Optional[bool] = None
    ) -> Tuple[Dict, str]:
        _filter_english = (
            filter_english
            if filter_english is not None
            else self.config.processing.get("filter_english", True)
        )

        frontmatter, body = self.extract_frontmatter(markdown_content)

        cleaned = self.remove_navigation_elements(body)
        cleaned = self.clean_markdown_syntax(cleaned)
        cleaned = self.remove_footer_sections(cleaned)
        cleaned = self.remove_excessive_whitespace(cleaned)

        if _filter_english:
            cleaned = self.filter_english_words(cleaned)

        return frontmatter, cleaned


def process_all_files(
    input_dir: Path,
    output_dir: Path,
    config: Any,
    processing_patterns: Optional[Dict[str, Any]] = None,
):
    processor = ContentProcessor(config, processing_patterns)

    metadata_file = input_dir / "metadata.jsonl"

    if not metadata_file.exists():
        print(f"Error: {metadata_file} not found")
        print("Please run the scraper first to generate scraped content")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_entries = []
    with open(metadata_file, "r", encoding="utf-8") as f:
        for line in f:
            metadata_entries.append(json.loads(line))

    print(f"Found {len(metadata_entries)} documents to process")

    processed_metadata = []
    stats = {
        "total_processed": 0,
        "total_words": 0,
        "total_chars": 0,
        "categories": {},
        "domains": {},
    }

    min_content_length = config.processing.get("min_content_length", 100)

    for meta in metadata_entries:
        doc_id = meta["doc_id"]
        domain = meta.get("domain", "unknown")
        domain_slug = domain.replace(".", "_")
        filename = f"{meta['doc_id']}_{domain_slug}_{meta['url_slug']}.md"
        category = meta.get("category", "unknown")

        md_file = input_dir / filename

        if not md_file.exists():
            print(f"Warning: File not found: {filename}")
            continue

        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            frontmatter, plain_text = processor.process_markdown_to_plain_text(content)

            if len(plain_text.strip()) < min_content_length:
                print(f"Skipping {filename}: content too short")
                continue

            url_slug = meta["url_slug"]
            output_filename = f"{doc_id}_{domain_slug}_{url_slug}.txt"
            output_file = output_dir / output_filename

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(plain_text)

            word_count = len(plain_text.split())
            char_count = len(plain_text)

            plain_meta = {
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

            if category not in stats["categories"]:
                stats["categories"][category] = {"count": 0, "words": 0, "chars": 0}
            stats["categories"][category]["count"] += 1
            stats["categories"][category]["words"] += word_count
            stats["categories"][category]["chars"] += char_count

            if domain not in stats["domains"]:
                stats["domains"][domain] = {"count": 0, "words": 0, "chars": 0}
            stats["domains"][domain]["count"] += 1
            stats["domains"][domain]["words"] += word_count
            stats["domains"][domain]["chars"] += char_count

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
    print(f"Processing Complete!")
    print(f"{'=' * 70}")
    print(f"Total documents processed: {stats['total_processed']}")
    print(f"Total words: {stats['total_words']:,}")
    print(f"Total characters: {stats['total_chars']:,}")

    print(f"\nBy domain:")
    for domain, domain_stats in stats["domains"].items():
        print(
            f"  {domain}: {domain_stats['count']} docs, {domain_stats['words']:,} words"
        )

    print(f"\nBy category:")
    for cat, cat_stats in stats["categories"].items():
        print(f"  {cat}: {cat_stats['count']} docs, {cat_stats['words']:,} words")

    print(f"\nOutput:")
    print(f"  Plain text files: {output_dir}/")
    print(f"  Metadata: {plain_metadata_file}")
    print(f"  Statistics: {stats_file}")


if __name__ == "__main__":
    import sys
    from core import load_config, load_processing_patterns

    try:
        config = load_config()
        domain = config.domain
        processing_patterns = load_processing_patterns(domain)

        if len(sys.argv) > 1:
            input_dir = Path(sys.argv[1])
        else:
            input_dir = Path(config.get("output_dir", "scraped_content"))

        if len(sys.argv) > 2:
            output_dir = Path(sys.argv[2])
        else:
            output_dir = Path(config.get("plaintext_output_dir", "scrapped_plain_text"))

        if not input_dir.exists():
            print(f"Error: Input directory '{input_dir}' does not exist")
            print(f"Usage: python -m core.processor [input_dir] [output_dir]")
            sys.exit(1)

        print(f"Domain: {domain}")
        print(f"Input directory: {input_dir}")
        print(f"Output directory: {output_dir}")
        print()

        process_all_files(input_dir, output_dir, config, processing_patterns)

    except ValueError as e:
        print(str(e))
        sys.exit(1)
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)

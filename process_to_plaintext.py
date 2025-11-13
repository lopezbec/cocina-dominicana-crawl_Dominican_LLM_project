"""
Process scraped markdown files to plain text for MLM training
Removes frontmatter, markdown syntax, navigation elements, and extracts clean Dominican Spanish content
"""

import re
import json
from pathlib import Path
from typing import Dict, Tuple


def extract_frontmatter(content: str) -> Tuple[Dict, str]:
    """Extract YAML frontmatter and return metadata dict + body"""
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


def remove_navigation_elements(text: str) -> str:
    """Remove navigation links and UI elements"""
    patterns_to_remove = [
        r"\*\s+\[Saltar a[^\]]+\]\([^\)]+\)",
        r"\[In English\]\([^\)]+\)",
        r"!\[.*?\]\(data:image/svg\+xml[^\)]+\)",
        r"\*\*SALTAR A:\*\*[^\n]+",
        r"\[mostrar[^\]]*\]\([^\)]+\)",
        r"Por \*\*\[Clara Gonzalez\][^\n]+",
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
        
        r"Más Historia, Tradiciones, y Cultura.*",
        r"¡Hola, gracias por visitarnos!.*",
        r"Soy Tía Clara.*",
        r"Aprende más sobre mi.*",
        r"Comparte tus preguntas.*",
        r"Suscríbete.*para recibir.*",
        r"¡No pierdas el contacto!.*",
        r"Síguenos en:.*",
        
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

    cleaned = text
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE | re.DOTALL)

    return cleaned


def clean_markdown_syntax(text: str) -> str:
    """Remove markdown formatting"""
    text = re.sub(r'[\U0001F300-\U0001F9FF]', '', text)
    text = re.sub(r'[\U0001F600-\U0001F64F]', '', text)
    text = re.sub(r'[\U0001F680-\U0001F6FF]', '', text)
    text = re.sub(r'[\U0001F1E0-\U0001F1FF]', '', text)
    text = re.sub(r'[\u2600-\u26FF]', '', text)
    text = re.sub(r'[\u2700-\u27BF]', '', text)
    text = re.sub(r'[\U0001F900-\U0001F9FF]', '', text)
    
    text = re.sub(r'\[\(https?://[^\)]+\)\]', '', text)
    text = re.sub(r'\(https?://[^\)]+\)', '', text)
    
    text = re.sub(r'\[\s*\]', '', text)
    
    text = re.sub(r'\*\*\s*-\s*', '', text)
    text = re.sub(r'^\*\*\s*$', '', text, flags=re.MULTILINE)
    
    text = re.sub(r'\[\\?\d+\\?\]', '', text)
    
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


def remove_footer_sections(text: str) -> str:
    """Remove footer and end-of-article sections"""
    footer_markers = [
        "¡Hola, gracias por visitarnos",
        "Más Historia, Tradiciones",
        "Suscríbete para recibir",
        "Referencias",
        "Fuentes",
    ]
    
    min_pos = len(text)
    for marker in footer_markers:
        pos = text.find(marker)
        if pos != -1 and pos < min_pos:
            min_pos = pos
    
    if min_pos < len(text):
        text = text[:min_pos]
    
    return text


def remove_excessive_whitespace(text: str) -> str:
    """Clean up whitespace"""
    text = re.sub(r'\[\s*\n*\s*\]', '', text)
    
    text = re.sub(r'\[([^\]]+)\]', r'\1', text)
    
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text.strip()


def process_markdown_to_plain_text(markdown_content: str) -> Tuple[Dict, str]:
    """Process markdown to plain text, return frontmatter and cleaned content"""
    frontmatter, body = extract_frontmatter(markdown_content)

    cleaned = remove_navigation_elements(body)
    cleaned = clean_markdown_syntax(cleaned)
    cleaned = remove_footer_sections(cleaned)
    cleaned = remove_excessive_whitespace(cleaned)

    return frontmatter, cleaned


def process_all_files(input_dir: Path, output_dir: Path):
    """Process all markdown files to plain text"""

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
    stats = {"total_processed": 0, "total_words": 0,
             "total_chars": 0, "categories": {}}

    for meta in metadata_entries:
        doc_id = meta["doc_id"]
        filename = f"{meta['doc_id']}_{meta['url_slug']}.md"
        category = meta.get("category", "unknown")

        md_file = input_dir / filename

        if not md_file.exists():
            print(f"Warning: File not found: {filename}")
            continue

        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            frontmatter, plain_text = process_markdown_to_plain_text(content)

            if len(plain_text.strip()) < 100:
                print(f"Skipping {filename}: content too short")
                continue

            url_slug = meta["url_slug"]
            output_filename = f"{doc_id}_{url_slug}.txt"
            output_file = output_dir / output_filename

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(plain_text)

            word_count = len(plain_text.split())
            char_count = len(plain_text)

            plain_meta = {
                "doc_id": doc_id,
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
                stats["categories"][category] = {
                    "count": 0, "words": 0, "chars": 0}
            stats["categories"][category]["count"] += 1
            stats["categories"][category]["words"] += word_count
            stats["categories"][category]["chars"] += char_count

            print(f"Processed: {
                  filename} -> {output_filename} ({word_count} words)")

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
    print(f"\nBy category:")
    for cat, cat_stats in stats["categories"].items():
        print(f"  {cat}: {cat_stats['count']} docs, {
              cat_stats['words']:,} words")
    print(f"\nOutput:")
    print(f"  Plain text files: {output_dir}/")
    print(f"  Metadata: {plain_metadata_file}")
    print(f"  Statistics: {stats_file}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        input_dir = Path(sys.argv[1])
    else:
        input_dir = Path("scraped_content")

    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])
    else:
        output_dir = Path("scrapped_plain_text")

    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist")
        print(f"Usage: python {sys.argv[0]} [input_dir] [output_dir]")
        sys.exit(1)

    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print()

    process_all_files(input_dir, output_dir)

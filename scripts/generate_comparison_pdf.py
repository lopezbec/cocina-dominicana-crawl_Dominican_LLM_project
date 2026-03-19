#!/usr/bin/env python3
import argparse
import asyncio
import html
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.async_api import async_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "reports"
CHUNK_SIZE = 32


@dataclass(frozen=True)
class ComparisonPair:
    requested_id: str
    stem: str
    raw_path: Path
    processed_path: Path
    raw_text: str
    processed_text: str

    @property
    def raw_lines(self) -> list[str]:
        return self.raw_text.splitlines()

    @property
    def processed_lines(self) -> list[str]:
        return self.processed_text.splitlines()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a side-by-side raw vs processed PDF comparison report.")
    parser.add_argument(
        "--ids",
        required=True,
        help="Comma-separated ids or stems to compare, e.g. 0002,0080,0809",
    )
    parser.add_argument(
        "--output",
        help="Output PDF path. Defaults to reports/comparison_<timestamp>.pdf",
    )
    return parser.parse_args()


def normalize_ids(raw_ids: str) -> list[str]:
    items = [item.strip() for item in raw_ids.split(",")]
    ids = [item for item in items if item]
    if not ids:
        raise ValueError("No ids provided. Pass a comma-separated IDS value.")

    seen: set[str] = set()
    duplicates: list[str] = []
    for item in ids:
        key = item.casefold()
        if key in seen:
            duplicates.append(item)
        seen.add(key)

    if duplicates:
        duplicate_list = ", ".join(sorted(set(duplicates), key=str.casefold))
        raise ValueError(f"Duplicate ids provided: {duplicate_list}")

    return ids


def is_numeric_prefix(value: str) -> bool:
    return bool(re.fullmatch(r"\d+", value))


def resolve_unique_file(directory: Path, suffix: str, requested_id: str) -> Path:
    if is_numeric_prefix(requested_id):
        pattern = f"{requested_id}_*{suffix}"
    else:
        pattern = f"{requested_id}{suffix}"

    matches = sorted(directory.glob(pattern))
    if not matches:
        raise ValueError(f"Could not find {suffix} file for id '{requested_id}' in {directory}")
    if len(matches) > 1:
        match_list = ", ".join(path.name for path in matches[:5])
        extra = "" if len(matches) <= 5 else f" ... (+{len(matches) - 5} more)"
        raise ValueError(f"Ambiguous id '{requested_id}' in {directory}: {match_list}{extra}")
    return matches[0]


def read_non_empty_text(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not read file {path}: {exc}") from exc

    if not content.strip():
        raise ValueError(f"File is empty: {path}")
    return content


def build_pairs(ids: list[str]) -> list[ComparisonPair]:
    pairs: list[ComparisonPair] = []
    for requested_id in ids:
        raw_path = resolve_unique_file(RAW_DIR, ".md", requested_id)
        processed_path = resolve_unique_file(PROCESSED_DIR, ".txt", requested_id)
        raw_text = read_non_empty_text(raw_path)
        processed_text = read_non_empty_text(processed_path)

        raw_stem = raw_path.stem
        processed_stem = processed_path.stem
        if raw_stem != processed_stem:
            raise ValueError(f"Resolved files do not share the same stem: {raw_path.name} vs {processed_path.name}")

        pairs.append(
            ComparisonPair(
                requested_id=requested_id,
                stem=raw_stem,
                raw_path=raw_path,
                processed_path=processed_path,
                raw_text=raw_text,
                processed_text=processed_text,
            )
        )
    return pairs


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_DIR / f"comparison_{timestamp}.pdf"


def format_percent(raw_len: int, processed_len: int) -> str:
    if raw_len == 0:
        return "0.0%"
    reduction = ((raw_len - processed_len) / raw_len) * 100
    return f"{reduction:.1f}%"


def escape_text(value: str) -> str:
    return html.escape(value, quote=False)


def render_line_block(lines: list[str], start_index: int) -> str:
    if not lines:
        return '<div class="line empty"><span class="ln">&nbsp;</span><span class="txt">&nbsp;</span></div>'

    rows: list[str] = []
    for offset, line in enumerate(lines, start=start_index):
        text = escape_text(line) if line else "&nbsp;"
        rows.append(f'<div class="line"><span class="ln">{offset}</span><span class="txt">{text}</span></div>')
    return "".join(rows)


def chunk_lines(lines: list[str], chunk_size: int) -> list[list[str]]:
    return [lines[index : index + chunk_size] for index in range(0, len(lines), chunk_size)] or [[]]


def build_comparison_sections(pairs: list[ComparisonPair]) -> str:
    sections: list[str] = []
    for pair in pairs:
        raw_chunks = chunk_lines(pair.raw_lines, CHUNK_SIZE)
        processed_chunks = chunk_lines(pair.processed_lines, CHUNK_SIZE)
        total_chunks = max(len(raw_chunks), len(processed_chunks))

        blocks: list[str] = []
        for index in range(total_chunks):
            raw_block = raw_chunks[index] if index < len(raw_chunks) else []
            processed_block = processed_chunks[index] if index < len(processed_chunks) else []
            raw_start = index * CHUNK_SIZE + 1
            processed_start = index * CHUNK_SIZE + 1
            blocks.append(
                "".join(
                    [
                        '<section class="chunk">',
                        '<div class="panel raw">',
                        '<div class="panel-header">Raw</div>',
                        '<div class="code">',
                        render_line_block(raw_block, raw_start),
                        "</div></div>",
                        '<div class="panel processed">',
                        '<div class="panel-header">Processed</div>',
                        '<div class="code">',
                        render_line_block(processed_block, processed_start),
                        "</div></div>",
                        "</section>",
                    ]
                )
            )

        sections.append(
            f"""
            <section class="comparison">
              <div class="comparison-header">
                <div>
                  <div class="eyebrow">Comparison</div>
                  <h2>{escape_text(pair.stem)}</h2>
                </div>
                <div class="requested-id">requested: {escape_text(pair.requested_id)}</div>
              </div>

              <div class="meta-grid">
                <div><span>Raw file</span><code>{escape_text(pair.raw_path.relative_to(ROOT_DIR).as_posix())}</code></div>
                <div><span>Processed file</span><code>{escape_text(pair.processed_path.relative_to(ROOT_DIR).as_posix())}</code></div>
              </div>

              <div class="stats">
                <div class="stat"><span>Raw chars</span><strong>{len(pair.raw_text):,}</strong></div>
                <div class="stat"><span>Processed chars</span><strong>{len(pair.processed_text):,}</strong></div>
                <div class="stat"><span>Raw lines</span><strong>{len(pair.raw_lines):,}</strong></div>
                <div class="stat"><span>Processed lines</span><strong>{len(pair.processed_lines):,}</strong></div>
                <div class="stat"><span>Reduction</span><strong>{format_percent(len(pair.raw_text), len(pair.processed_text))}</strong></div>
              </div>

              {"".join(blocks)}
            </section>
            """
        )
    return "".join(sections)


def build_html_document(pairs: list[ComparisonPair]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    comparison_list = "".join(f"<li><code>{escape_text(pair.stem)}</code></li>" for pair in pairs)
    sections = build_comparison_sections(pairs)
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Raw vs Processed Comparison Report</title>
  <style>
    @page {{
      size: A4;
      margin: 14mm 10mm 14mm 10mm;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #1f2937;
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 11px;
      line-height: 1.45;
      background: #ffffff;
    }}
    .cover {{
      page-break-after: always;
      min-height: 250mm;
      padding: 10mm 8mm;
      background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
      border: 1px solid #dbe3ec;
      border-radius: 12px;
    }}
    .cover h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.1;
    }}
    .cover p {{
      margin: 0 0 10px;
      max-width: 720px;
      color: #475569;
      font-size: 13px;
    }}
    .cover ul {{
      margin: 10px 0 0;
      padding-left: 20px;
      columns: 2;
    }}
    .eyebrow {{
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 10px;
      font-weight: 700;
      margin-bottom: 8px;
    }}
    .comparison {{
      page-break-before: always;
    }}
    .comparison:first-of-type {{
      page-break-before: auto;
    }}
    .comparison-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .comparison-header h2 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
      word-break: break-word;
    }}
    .requested-id {{
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid #cbd5e1;
      color: #475569;
      background: #f8fafc;
      white-space: nowrap;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 6px;
      margin-bottom: 12px;
    }}
    .meta-grid div {{
      display: flex;
      flex-direction: column;
      gap: 4px;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 8px 10px;
      background: #fbfdff;
    }}
    .meta-grid span,
    .stat span {{
      color: #64748b;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-weight: 700;
    }}
    code {{
      font-family: Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 10px;
      overflow-wrap: anywhere;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 8px;
      margin-bottom: 12px;
    }}
    .stat {{
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 8px 10px;
      background: #ffffff;
    }}
    .stat strong {{
      display: block;
      margin-top: 3px;
      font-size: 15px;
      line-height: 1.2;
      color: #0f172a;
    }}
    .chunk {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 12px;
      break-inside: avoid;
    }}
    .panel {{
      border: 1px solid #dbe3ec;
      border-radius: 12px;
      overflow: hidden;
      background: #ffffff;
    }}
    .panel.raw {{
      border-color: #efc4c8;
      background: #fff6f7;
    }}
    .panel.processed {{
      border-color: #b8dfc4;
      background: #f3fff6;
    }}
    .panel-header {{
      padding: 7px 10px;
      font-size: 11px;
      font-weight: 700;
      border-bottom: 1px solid rgba(148, 163, 184, 0.28);
      background: rgba(255, 255, 255, 0.72);
    }}
    .code {{
      padding: 8px 0;
      font-family: Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 9px;
      line-height: 1.45;
    }}
    .line {{
      display: grid;
      grid-template-columns: 34px 1fr;
      gap: 8px;
      padding: 0 10px;
      min-height: 1.45em;
    }}
    .line:nth-child(odd) {{
      background: rgba(255, 255, 255, 0.28);
    }}
    .ln {{
      text-align: right;
      color: #94a3b8;
      user-select: none;
    }}
    .txt {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: break-word;
      color: #1e293b;
    }}
  </style>
</head>
<body>
  <section class="cover">
    <div class="eyebrow">Raw vs Processed Report</div>
    <h1>Scraped Content Comparison</h1>
    <p>Side-by-side review of raw markdown versus processed plaintext. Each section starts on a new page and shows the full content in readable review blocks.</p>
    <p><strong>Generated:</strong> {escape_text(generated_at)}<br><strong>Total comparisons:</strong> {len(pairs)}</p>
    <ul>{comparison_list}</ul>
  </section>
  {sections}
</body>
</html>
    """


async def render_pdf(html_text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="comparison_report_") as temp_dir:
        html_path = Path(temp_dir) / "report.html"
        html_path.write_text(html_text, encoding="utf-8")

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto(html_path.as_uri(), wait_until="load")
            await page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={"top": "14mm", "right": "10mm", "bottom": "14mm", "left": "10mm"},
            )
            await browser.close()


def main() -> int:
    try:
        args = parse_args()
        ids = normalize_ids(args.ids)
        pairs = build_pairs(ids)
        output_path = Path(args.output).expanduser() if args.output else default_output_path()
        if not output_path.is_absolute():
            output_path = ROOT_DIR / output_path

        html_text = build_html_document(pairs)
        asyncio.run(render_pdf(html_text, output_path))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"Error: failed to generate comparison PDF: {exc}", file=sys.stderr)
        return 1

    print(output_path.relative_to(ROOT_DIR) if output_path.is_relative_to(ROOT_DIR) else output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

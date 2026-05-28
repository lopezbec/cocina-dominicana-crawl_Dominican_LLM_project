#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURE = ROOT / "data" / "synthetic_stage3"
DEFAULT_INPUT_DIR = DEFAULT_FIXTURE / "output"
DEFAULT_MANIFEST = DEFAULT_FIXTURE / "manifest.json"
DEFAULT_OUTPUT = ROOT / "reports" / f"semantic_pairs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"


@dataclass(frozen=True)
class PairResult:
    left_id: str
    right_id: str
    expected_duplicate: bool
    epsilon: float
    left_text: str
    right_text: str
    left_row: dict
    right_row: dict
    observed_duplicate: bool
    canonical_doc_id: str | None
    semantic_similarity: float | None
    verdict: str
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate semantic pairwise Stage-3 coherence PDF report")
    parser.add_argument("--pairs", required=True, help="Comma-separated pair ids, e.g. 9001:9002,9003:9004")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--expected-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--epsilon", type=float, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def parse_pairs(raw: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in [x.strip() for x in raw.split(",") if x.strip()]:
        if ":" not in item:
            raise ValueError(f"Malformed pair '{item}'. Expected id1:id2")
        left, right = [x.strip() for x in item.split(":", 1)]
        if not left or not right:
            raise ValueError(f"Malformed pair '{item}'. Empty id")
        pairs.append((left, right))
    if not pairs:
        raise ValueError("No pairs provided")
    return pairs


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_map(manifest: dict) -> dict[tuple[str, str], bool]:
    out: dict[tuple[str, str], bool] = {}
    for pair in manifest.get("pairs", []):
        left = str(pair["left_doc_id"])
        right = str(pair["right_doc_id"])
        expected = bool(pair.get("expected_duplicate", False))
        out[(left, right)] = expected
        out[(right, left)] = expected
    return out


def _load_text_for_doc(input_dir: Path, doc_id: str) -> str:
    metadata = _load_jsonl(input_dir / "metadata_plaintext.jsonl")
    by_id = {str(row["doc_id"]): row for row in metadata}
    row = by_id.get(str(doc_id))
    if row is None:
        raise ValueError(f"doc_id '{doc_id}' not found in metadata_plaintext.jsonl")
    path = input_dir / row["filename"]
    if not path.exists():
        raise ValueError(f"Missing text file for doc_id '{doc_id}': {path}")
    return path.read_text(encoding="utf-8")


def build_pair_results(args: argparse.Namespace) -> tuple[list[PairResult], bool]:
    pairs = parse_pairs(args.pairs)
    manifest = _load_manifest(args.expected_manifest)
    expected = _expected_map(manifest)

    rows = _load_jsonl(args.input_dir / "dedup_stage_03_semantic.jsonl")
    rows_by_id = {str(row["doc_id"]): row for row in rows}

    if not rows:
        raise ValueError("dedup_stage_03_semantic.jsonl is empty")

    default_eps = float(rows[0].get("threshold", manifest.get("default_epsilon", 0.9)))
    epsilon = float(args.epsilon) if args.epsilon is not None else default_eps

    results: list[PairResult] = []
    all_pass = True

    for left_id, right_id in pairs:
        if left_id not in rows_by_id or right_id not in rows_by_id:
            raise ValueError(f"Pair contains unknown id(s): {left_id}:{right_id}")

        left_row = rows_by_id[left_id]
        right_row = rows_by_id[right_id]

        left_dup = bool(left_row.get("is_duplicate", False))
        right_dup = bool(right_row.get("is_duplicate", False))
        left_canonical = str(left_row.get("canonical_doc_id", left_id))
        right_canonical = str(right_row.get("canonical_doc_id", right_id))

        observed_duplicate = (
            left_canonical == right_canonical and (left_dup or right_dup or left_id != right_id)
        )
        canonical_doc_id = left_canonical if left_canonical == right_canonical else None

        expected_dup = expected.get((left_id, right_id))
        if expected_dup is None:
            raise ValueError(f"Pair {left_id}:{right_id} is not declared in manifest")

        coherent = observed_duplicate == expected_dup
        verdict = "coherent" if coherent else "incoherent"
        if not coherent:
            all_pass = False

        similarity_candidates = [
            left_row.get("semantic_similarity"),
            right_row.get("semantic_similarity"),
        ]
        semantic_similarity = next((float(x) for x in similarity_candidates if x is not None), None)

        notes = ""
        if args.epsilon is not None and abs(epsilon - default_eps) > 1e-9:
            notes = (
                f"Requested epsilon={epsilon}, but stage output threshold is {default_eps}. "
                "Re-run synthetic validation with matching --epsilon for strict interpretation."
            )

        results.append(
            PairResult(
                left_id=left_id,
                right_id=right_id,
                expected_duplicate=expected_dup,
                epsilon=epsilon,
                left_text=_load_text_for_doc(args.input_dir, left_id),
                right_text=_load_text_for_doc(args.input_dir, right_id),
                left_row=left_row,
                right_row=right_row,
                observed_duplicate=observed_duplicate,
                canonical_doc_id=canonical_doc_id,
                semantic_similarity=semantic_similarity,
                verdict=verdict,
                notes=notes,
            )
        )

    return results, all_pass


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def build_html(results: list[PairResult], all_pass: bool) -> str:
    summary_rows = "".join(
        f"<tr><td>{_esc(r.left_id)}:{_esc(r.right_id)}</td><td>{'duplicate' if r.expected_duplicate else 'distinct'}</td><td>{'duplicate' if r.observed_duplicate else 'distinct'}</td><td class='{r.verdict}'>{r.verdict}</td></tr>"
        for r in results
    )

    pair_sections = []
    for r in results:
        pair_sections.append(
            f"""
            <section class='pair'>
              <h2>Pair {r.left_id}:{r.right_id}</h2>
              <div class='meta'>
                <div><strong>expected:</strong> {'duplicate' if r.expected_duplicate else 'distinct'}</div>
                <div><strong>observed:</strong> {'duplicate' if r.observed_duplicate else 'distinct'}</div>
                <div><strong>epsilon:</strong> {r.epsilon}</div>
                <div><strong>verdict:</strong> <span class='{r.verdict}'>{r.verdict}</span></div>
              </div>
              <div class='grid'>
                <article>
                  <h3>{_esc(r.left_id)}</h3>
                  <pre>{_esc(r.left_text)}</pre>
                </article>
                <article>
                  <h3>{_esc(r.right_id)}</h3>
                  <pre>{_esc(r.right_text)}</pre>
                </article>
              </div>
              <div class='decision'>
                <p><strong>Stage 3 fields</strong></p>
                <p>left: is_duplicate={r.left_row.get('is_duplicate')} canonical={_esc(str(r.left_row.get('canonical_doc_id')))} candidate={_esc(str(r.left_row.get('candidate_doc_id')))} similarity={r.left_row.get('semantic_similarity')}</p>
                <p>right: is_duplicate={r.right_row.get('is_duplicate')} canonical={_esc(str(r.right_row.get('canonical_doc_id')))} candidate={_esc(str(r.right_row.get('candidate_doc_id')))} similarity={r.right_row.get('semantic_similarity')}</p>
                <p><strong>pair conclusion</strong>: canonical_doc_id={_esc(str(r.canonical_doc_id))} semantic_similarity={r.semantic_similarity}</p>
                {f"<p class='note'>{_esc(r.notes)}</p>" if r.notes else ''}
              </div>
            </section>
            """
        )

    return f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <title>Semantic Pairwise Report</title>
  <style>
    @page {{
      size: A4;
      margin: 10mm;
      background: #fbf5ea;
    }}
    html {{
      background: #fbf5ea;
    }}
    body {{
      margin: 0;
      background: #fbf5ea;
      color: #1f2f46;
      font-family: Charter, Georgia, 'Times New Roman', serif;
      line-height: 1.5;
      font-size: 11pt;
      padding: 14mm 12mm;
    }}
    h1, h2, h3 {{
      color: #183153;
      margin: 0 0 6px 0;
    }}
    .report-root {{ width: 100%; }}
    .summary {{
      padding-bottom: 12px;
      border-bottom: 1px solid #d7c7a7;
      margin-bottom: 14px;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid #b9a37b;
      background: #efe2cb;
      margin-top: 6px;
      font-weight: 600;
    }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ border-bottom: 1px solid #d7c7a7; text-align: left; padding: 8px 6px; }}
    .pair {{
      page-break-inside: avoid;
      border-top: 1px solid #d7c7a7;
      padding-top: 12px;
      margin-top: 14px;
    }}
    .meta {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; font-size: 10pt; margin: 6px 0 8px; }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-top: 4px;
      padding: 4px 0 8px;
    }}
    article {{
      padding: 0;
      margin: 0;
      background: transparent;
      border: none;
    }}
    article:nth-child(2) {{
      border-left: 1px solid #d7c7a7;
      padding-left: 12px;
    }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; font-family: Charter, Georgia, 'Times New Roman', serif; }}
    .decision {{
      margin-top: 8px;
      border-left: 2px solid #c8ab79;
      padding-left: 10px;
      background: transparent;
    }}
    .coherent {{ color: #1e5b3a; font-weight: 700; }}
    .incoherent {{ color: #8c1d18; font-weight: 700; }}
    .note {{ font-size: 10pt; color: #7b5e33; }}
  </style>
</head>
<body>
  <main class='report-root'>
    <section class='summary'>
      <h1>semantic deduplication</h1>
      <div class='badge'>overall: {'PASS' if all_pass else 'FAIL'}</div>
      <table>
        <thead><tr><th>Pair</th><th>Expected</th><th>Observed</th><th>Verdict</th></tr></thead>
        <tbody>{summary_rows}</tbody>
      </table>
    </section>
    {''.join(pair_sections)}
  </main>
</body>
</html>
"""


async def render_pdf(html_text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html_text, wait_until="networkidle")
        await page.pdf(path=str(output_path), format="A4", print_background=True)
        await browser.close()


def main() -> int:
    args = parse_args()
    results, all_pass = build_pair_results(args)
    html_report = build_html(results, all_pass)
    asyncio.run(render_pdf(html_report, args.output))

    print("[report] output:", args.output)
    print("[report] overall:", "PASS" if all_pass else "FAIL")
    for row in results:
        print(f"[report] {row.left_id}:{row.right_id} expected={'dup' if row.expected_duplicate else 'distinct'} observed={'dup' if row.observed_duplicate else 'distinct'} verdict={row.verdict}")
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())

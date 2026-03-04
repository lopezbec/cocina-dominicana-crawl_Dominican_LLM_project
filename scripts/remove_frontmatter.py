#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import Iterable, Tuple


def _strip_frontmatter(content: str) -> Tuple[bool, str]:
    if not content.startswith("---\n"):
        return False, content

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return False, content

    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break

    if end_index is None:
        return False, content

    remainder = "".join(lines[end_index + 1 :])
    if remainder.startswith("\n"):
        remainder = remainder[1:]
    return True, remainder


def _iter_markdown_files(path: Path) -> Iterable[Path]:
    return sorted(path.glob("*.md"))


def _preview(text: str, lines: int = 12) -> str:
    return "".join(text.splitlines(keepends=True)[:lines])


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove YAML frontmatter from markdown files.")
    parser.add_argument("--path", default="data/raw", help="Directory containing .md files")
    parser.add_argument("--dry-run", action="store_true", help="Do not modify files")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files processed (0 = all)")
    args = parser.parse_args()

    input_dir = Path(args.path)
    if not input_dir.exists():
        print(f"Error: directory not found: {input_dir}")
        return 1

    files = list(_iter_markdown_files(input_dir))
    if args.limit > 0:
        files = files[: args.limit]

    changed = 0
    examined = 0

    for file_path in files:
        examined += 1
        content = file_path.read_text(encoding="utf-8")
        has_frontmatter, updated = _strip_frontmatter(content)
        if not has_frontmatter:
            continue

        changed += 1
        if args.dry_run:
            print(f"[DRY RUN] Would update: {file_path}")
            print("--- before (preview) ---")
            print(_preview(content))
            print("--- after (preview) ---")
            print(_preview(updated))
            continue

        file_path.write_text(updated, encoding="utf-8")

    print(f"Examined: {examined}")
    print(f"Frontmatter removed: {changed}")
    if args.dry_run:
        print("Dry run only - no files modified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

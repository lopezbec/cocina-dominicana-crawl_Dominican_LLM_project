import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from dominican_llm_processor.batch import process_all_files
from dominican_llm_processor.config_loader import load_config, resolve_project_path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    config = load_config()
    parser = argparse.ArgumentParser(
        description="Convert Firecrawl Markdown to plain text and run deduplication."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser(
        "process",
        help="Process raw Markdown and run all deduplication stages.",
    )
    process_parser.add_argument(
        "--input",
        default=str(config.get("input_dir", "../crawler/data/raw")),
        help="Raw Markdown directory, relative to processor/ unless absolute.",
    )
    process_parser.add_argument(
        "--output",
        default=str(config.get("output_dir", "data/processed")),
        help="Processed output directory, relative to processor/ unless absolute.",
    )
    process_parser.add_argument(
        "--min-content-length",
        type=int,
        default=int(config.get("min_content_length", 50)),
        help="Skip documents whose stripped plain text has this many characters or fewer.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command != "process":
        raise ValueError(f"Unsupported command: {args.command}")
    if args.min_content_length < 0:
        print("Error: --min-content-length cannot be negative", file=sys.stderr)
        return 1

    input_dir = resolve_project_path(args.input)
    output_dir = resolve_project_path(args.output)
    if not input_dir.is_dir():
        print(f"Error: input directory does not exist: {input_dir}", file=sys.stderr)
        return 1

    print("Processing content to plain text")
    print(f"Input: {input_dir}")
    print(f"Output: {output_dir}\n")
    try:
        process_all_files(
            input_dir=Path(input_dir),
            output_dir=Path(output_dir),
            min_content_length=args.min_content_length,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0

"""Command-line interface: `metamapy` / `python -m metamapy`.

Only the most useful options are exposed (free-text input; MMI + JSON output).
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from metamapy import __version__
from metamapy.config import Config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="metamapy",
        description="Map free biomedical text to UMLS Metathesaurus concepts.",
    )
    p.add_argument("inputs", nargs="*", metavar="INPUT",
                   help="Free-text file(s), or - for stdin.")
    p.add_argument("--output-format", choices=["mmi", "json"], default="mmi",
                   help="Output format (default: mmi).")
    p.add_argument("-o", "--output", metavar="PATH",
                   help="Output file/dir; writes to stdout if omitted.")
    p.add_argument("--restrict-to-sts", metavar="LIST",
                   help="Comma-separated semantic types/groups to keep.")
    p.add_argument("--restrict-to-sources", metavar="LIST",
                   help="Comma-separated source vocabularies to keep (e.g. SNOMEDCT_US,MSH).")
    p.add_argument("--segmentation", choices=["sentences", "blanklines", "lines"],
                   default="sentences", help="Text segmentation method (default: sentences).")
    p.add_argument("--overlapping", action="store_true",
                   help="Allow overlapping concepts (default: longest-match only).")
    p.add_argument("--no-negation", action="store_true",
                   help="Disable NegEx negation detection.")
    p.add_argument("--index-dir", metavar="PATH",
                   help="Directory of built UMLS indexes (default: $MML_INDEXDIR).")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    p.add_argument("--silent", action="store_true", help="Suppress progress output.")
    p.add_argument("--version", action="version", version=f"metamapy {__version__}")
    return p


def _read_inputs(paths: List[str]) -> List[tuple]:
    """Return list of (doc_id, text). '-' or empty reads stdin."""
    docs = []
    if not paths or paths == ["-"]:
        docs.append(("stdin", sys.stdin.read()))
        return docs
    for path in paths:
        if path == "-":
            docs.append(("stdin", sys.stdin.read()))
        else:
            with open(path, "r", encoding="utf-8") as fh:
                docs.append((path, fh.read()))
    return docs


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = Config.from_args(args)

    # Imported lazily so --help/--version work without loading spaCy/indexes.
    from metamapy.pipeline import Pipeline
    from metamapy.output import format_documents

    pipeline = Pipeline(config)
    documents = [pipeline.process(doc_id, text)
                 for doc_id, text in _read_inputs(args.inputs)]

    # MMI needs MeSH tree codes (for the treecodes field + score); use the store.
    treecode_lookup = pipeline.store().treecodes if config.output_format == "mmi" else None
    rendered = format_documents(documents, config, treecode_lookup=treecode_lookup)
    if config.output:
        with open(config.output, "w", encoding="utf-8") as fh:
            fh.write(rendered)
    else:
        sys.stdout.write(rendered)
    return 0

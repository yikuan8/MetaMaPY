"""Runtime configuration, resolved from CLI args + environment defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


def _split(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.replace(";", ",").split(",") if v.strip()]


@dataclass
class Config:
    output_format: str = "mmi"              # {mmi, json}
    output: Optional[str] = None            # path or None for stdout
    restrict_to_sts: List[str] = field(default_factory=list)
    restrict_to_sources: List[str] = field(default_factory=list)
    segmentation: str = "sentences"         # {sentences, blanklines, lines}
    overlapping: bool = False               # allow overlapping concepts
    negation: bool = True                   # NegEx on by default
    index_dir: Optional[str] = None
    excluded_terms_file: Optional[str] = None   # None -> bundled starter list
    verbose: bool = False
    silent: bool = False

    @classmethod
    def from_args(cls, args) -> "Config":
        return cls(
            output_format=args.output_format,
            output=args.output,
            restrict_to_sts=_split(args.restrict_to_sts),
            restrict_to_sources=_split(args.restrict_to_sources),
            segmentation=args.segmentation,
            overlapping=args.overlapping,
            negation=not args.no_negation,
            index_dir=args.index_dir or os.environ.get("MML_INDEXDIR"),
            excluded_terms_file=os.environ.get("METAMAPY_EXCLUDED_TERMS"),
            verbose=args.verbose,
            silent=args.silent,
        )

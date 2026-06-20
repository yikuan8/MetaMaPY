"""Output formatting. Only MMI (parity) and JSON (rich) are supported."""

from __future__ import annotations

from typing import List

from metamapy.config import Config
from metamapy.model import Document


def format_documents(documents: List[Document], config: Config,
                     treecode_lookup=None) -> str:
    if config.output_format == "mmi":
        from metamapy.output.mmi import format_mmi
        return "".join(format_mmi(doc, treecode_lookup) for doc in documents)
    elif config.output_format == "json":
        from metamapy.output.json_output import format_json
        return format_json(documents)
    raise ValueError(f"unknown output format: {config.output_format}")

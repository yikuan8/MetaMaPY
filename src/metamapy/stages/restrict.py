"""Filter entities by semantic type and/or source vocabulary.

An Ev survives if it has a matching semantic type (when ``restrict_to_sts`` is
set) AND a matching source (when ``restrict_to_sources`` is set). An Entity
survives if at least one Ev survives; its evidence list is filtered in place.

Semantic types are matched against the SRDEF abbreviations stored in the index
(e.g. "dsyn"). Source matching is case-insensitive against the SAB set.
(Semantic-*group* expansion, e.g. "disorders" -> member types, is a TODO that
needs the SRDEF group map.)
"""

from __future__ import annotations

from typing import List

from metamapy.config import Config
from metamapy.model import Entity


def apply(entities: List[Entity], config: Config) -> List[Entity]:
    sts = {s.lower() for s in config.restrict_to_sts}
    sources = {s.upper() for s in config.restrict_to_sources}
    if not sts and not sources:
        return entities

    kept: List[Entity] = []
    for ent in entities:
        surviving = []
        for ev in ent.evidence:
            ev_sts = {s.lower() for s in ev.concept.semantic_types}
            ev_src = {s.upper() for s in ev.concept.sources}
            if sts and ev_sts.isdisjoint(sts):
                continue
            if sources and ev_src.isdisjoint(sources):
                continue
            surviving.append(ev)
        if surviving:
            ent.evidence = surviving
            kept.append(ent)
    return kept

"""JSON output — rich format carrying the full candidate lattice.

Unlike MMI (which flattens to one line per concept), the JSON output keeps every
entity's N-best evidence list and the four score components, so downstream
consumers get the alternatives, offsets, sources, semantic types, and
(optionally) definitions.

Schema (per document):
  {
    "doc_id": str,
    "text": str,
    "entities": [
      {
        "span": {"start": int, "end": int},
        "matched_text": str,
        "negated": bool,
        "evidence": [
          {
            "cui": str, "preferred_name": str,
            "semantic_types": [str], "sources": [str],
            "matched_term": str, "span": {"start": int, "end": int},
            "score": float,
            "score_components": {"centrality":.., "variation":.., "coverage":.., "cohesiveness":..},
            "variant_level": int
          }
        ]
      }
    ]
  }
"""

from __future__ import annotations

import json
from typing import List

from metamapy.model import Document, Entity


def _entity_dict(e: Entity) -> dict:
    return {
        "span": {"start": e.span.start, "end": e.span.end},
        "matched_text": e.matched_text,
        "negated": e.negated,
        "evidence": [
            {
                "cui": ev.concept.cui,
                "preferred_name": ev.concept.preferred_name,
                "semantic_types": sorted(ev.concept.semantic_types),
                "sources": sorted(ev.concept.sources),
                "matched_term": ev.concept.matched_term,
                "span": {"start": ev.span.start, "end": ev.span.end},
                "score": ev.score,
                "score_components": ev.score_components,
                "variant_level": ev.variant_level,
            }
            for ev in e.evidence
        ],
    }


def format_json(documents: List[Document]) -> str:
    payload = [
        {
            "doc_id": doc.doc_id,
            "text": doc.text,
            "entities": [_entity_dict(e) for e in doc.entities],
        }
        for doc in documents
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

"""Abbreviation detection (Schwartz-Hearst) + linking short forms to concepts.

Detects ``long form (SHORT)`` definitions in the document, then links every
occurrence of the short form to the long form's UMLS concepts — so e.g. once
"acute kidney injury (AKI)" is defined, later "AKI" mentions resolve to the
acute-kidney-injury concept. This mirrors MetaMapLite's MarkAbbreviations
(Hirschman/Schwartz-Hearst via BioC ExtractAbbrev).

Reference: Schwartz & Hearst (2003), "A simple algorithm for identifying
abbreviation definitions in biomedical text."
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from metamapy.model import ConceptInfo, Document, Entity, Ev, Span
from metamapy.stages import scoring
from metamapy.stages.normalization import normalize_lookup

_PAREN = re.compile(r"\(([^()]+)\)")


def _find_best_long_form(short: str, long_cand: str):
    """Schwartz-Hearst findBestLongForm: validate short as an abbrev of long_cand."""
    s = len(short) - 1
    l = len(long_cand) - 1
    while s >= 0:
        ch = short[s].lower()
        if not ch.isalnum():
            s -= 1
            continue
        while ((l >= 0 and long_cand[l].lower() != ch) or
               (s == 0 and l > 0 and long_cand[l - 1].isalnum())):
            l -= 1
        if l < 0:
            return None
        l -= 1
        s -= 1
    l = long_cand.rfind(" ", 0, l + 1) + 1
    return long_cand[l:]


def _valid_short(short: str) -> bool:
    if not (2 <= len(short) <= 10):
        return False
    if len(short.split()) > 2:
        return False
    if not any(c.isalpha() for c in short):
        return False
    return short[0].isalnum()


def detect_definitions(text: str) -> Dict[str, str]:
    """Return {short_form: long_form} from 'long (SHORT)' definitions in text."""
    defs: Dict[str, str] = {}
    for m in _PAREN.finditer(text):
        short = m.group(1).strip()
        if not _valid_short(short):
            continue
        # long-form candidate: the text just before the paren, bounded in length
        before = text[:m.start()].rstrip()
        n_chars = min(len(short) + 5, len(short) * 2)
        # take up to n_chars words worth of preceding text (token-ish bound)
        long_window = before[-(len(short) * 3 + 10):]
        # trim to start at a clause boundary
        long_window = re.split(r"[;:,.]\s", long_window)[-1].strip()
        best = _find_best_long_form(short, long_window)
        if best and len(best) > len(short):
            defs[short] = best.strip()
    return defs


def link(document: Document, entities: List[Entity], store,
         allowed_first_pos=None) -> List[Entity]:
    """Add entities for short-form occurrences, using the long form's concepts."""
    defs = detect_definitions(document.text)
    if not defs:
        return entities

    # resolve each long form to concepts once
    long_concepts: Dict[str, list] = {}
    for short, long in defs.items():
        recs = store.lookup(long)
        if recs:
            long_concepts[short] = recs

    extra: List[Entity] = []
    for sent in document.sentences:
        for tok in sent.tokens:
            if not tok.is_alphanumeric:
                continue
            recs = long_concepts.get(tok.text)
            if recs is None:
                continue
            seen = set()
            ev_list = []
            sources: Dict[str, set] = {}
            for r in recs:
                sources.setdefault(r["cui"], set()).add(r["sab"])
            for r in recs:
                key = (r["cui"], r["str"])
                if key in seen:
                    continue
                seen.add(key)
                concept = ConceptInfo(
                    cui=r["cui"],
                    preferred_name=store.preferred_name(r["cui"]),
                    semantic_types=set(store.semantic_types(r["cui"])),
                    sources=sources[r["cui"]],
                    matched_term=r["str"])
                score, comps = scoring.score_match(
                    is_head=True, variant_levels=[0],
                    phrase_span=1, n_phrase_words=1, meta_span=1, n_meta_words=1)
                ev_list.append(Ev(concept=concept, span=tok.span,
                                  matched_text=tok.text, score=score,
                                  score_components=comps, part_of_speech=tok.pos or ""))
            if ev_list:
                ev_list.sort(key=lambda e: e.score, reverse=True)
                extra.append(Entity(span=tok.span, matched_text=tok.text,
                                    evidence=ev_list, lexical_category=tok.pos or ""))
    return entities + extra

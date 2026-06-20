"""NegEx negation detection.

Faithful port of MetaMapLite's NegEx (NegEx.java + NegExKeyMap.java):

  * Work over the sentence tokens minus whitespace and periods (filterTokenList).
  * Match trigger phrases (NEGATION_TRIGGERS), keeping the longest where they
    overlap (so pseudo-negations shadow the real triggers inside them).
  * Mark an entity negated when a pre-negation ("nega") trigger precedes it, or a
    post-negation ("negb") trigger follows it, within ``token_window`` tokens and
    with no conjunction ("conj") between trigger and entity.
  * Pseudo types (pnega/pnegb) are matched (to shadow real triggers) but never
    negate by themselves.

Reference: MetaMapLite/.../lite/NegEx.java
"""

from __future__ import annotations

from typing import List

from metamapy.model import Document, Entity, Token
from metamapy.stages.negex_triggers import NEGATION_TRIGGERS

DEFAULT_TOKEN_WINDOW = 6
_MAX_PHRASE_LEN = max(len(k) for k in NEGATION_TRIGGERS)


def _filtered_tokens(tokens: List[Token]) -> List[Token]:
    """filterTokenList: drop whitespace and period tokens (keep words + punct)."""
    return [t for t in tokens if t.token_class not in ("ws", "pd")]


def _find_phrases(ftokens: List[Token]):
    """Return [(type, [positions])] for every trigger-phrase occurrence."""
    texts = [t.text.lower() for t in ftokens]
    n = len(texts)
    matches = []
    for i in range(n):
        for length in range(min(_MAX_PHRASE_LEN, n - i), 0, -1):
            typ = NEGATION_TRIGGERS.get(tuple(texts[i:i + length]))
            if typ:
                matches.append((typ, list(range(i, i + length)), length))
    return matches


def _keep_longest(matches):
    """keepLongestNegationPhrases: greedily keep longest, drop overlapping shorter."""
    matches.sort(key=lambda m: m[2], reverse=True)
    kept = []
    used = set()
    for typ, positions, _length in matches:
        if any(p in used for p in positions):
            continue
        kept.append((typ, positions))
        used.update(positions)
    return kept


def _entity_token_pos(entity: Entity, ftokens: List[Token]) -> int:
    for i, t in enumerate(ftokens):
        if t.span.start <= entity.span.start < t.span.end:
            return i
    for i, t in enumerate(ftokens):       # fallback: first token at/after entity
        if t.span.start >= entity.span.start:
            return i
    return -1


def mark(document: Document, entities: List[Entity],
         token_window: int = DEFAULT_TOKEN_WINDOW) -> None:
    """Set entity.negated in place, per sentence."""
    for sent in document.sentences:
        ftokens = _filtered_tokens(sent.tokens)
        if not ftokens:
            continue
        kept = _keep_longest(_find_phrases(ftokens))
        conj_positions = [p for typ, positions in kept if typ == "conj" for p in positions]
        nega = [positions for typ, positions in kept if typ == "nega"]
        negb = [positions for typ, positions in kept if typ == "negb"]

        sent_entities = [e for e in entities
                         if sent.span.start <= e.span.start < sent.span.end]
        for entity in sent_entities:
            epos = _entity_token_pos(entity, ftokens)
            if epos < 0:
                continue
            # pre-negation: trigger before entity
            for positions in nega:
                for npos in positions:
                    if entity.span.start >= ftokens[npos].span.start \
                       and abs(epos - npos) <= token_window \
                       and not any(npos < c < epos for c in conj_positions):
                        entity.negated = True
            # post-negation: trigger after entity
            for positions in negb:
                for npos in positions:
                    if entity.span.start < ftokens[npos].span.start \
                       and abs(epos - npos) <= token_window \
                       and not any(epos < c < npos for c in conj_positions):
                        entity.negated = True

"""Candidate generation via dictionary longest-match over the UMLS indexes.

Faithful port of MetaMapLite's EntityLookup5 / FindLongestMatch:
  * createSubListsOpt: for each start token, generate contiguous sublists
    (longest-first); whitespace/punct tokens are filtered out by the char checks.
  * For each sublist: first token not "other" and (POS allowed, if POS present);
    originalTerm = concatenation of token texts (reconstructs the substring);
    len > 2, first char alphabetic, last char alphanumeric.
  * lookup() the term in the store (which unions original + normalized matches).
  * Build an Ev per (cui, matched-string); group Evs by span into an Entity.
  * Longest-match: drop subsumed spans unless overlapping (scoring.resolve_overlap).

Scoring note (from EntityLookup5.scoreTerm): MetaMapLite sets phraseSpan =
phrase size and metaSpan = #meta words, so coverage = cohesiveness = 1.0 and the
score is driven by centrality (head involvement) and variation. Without a vars
index, variation defaults to exact (distance 0). We reproduce that here.

Reference: MetaMapLite/.../lite/EntityLookup5.java,
           MetaMapLite/.../lite/FindLongestMatch.java
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from metamapy.model import ConceptInfo, Entity, Ev, Span, Token
from metamapy.stages import scoring
from metamapy.stages.normalization import normalize_lookup

MIN_TERM_LENGTH = 3            # originalTerm.length() > 2
DEFAULT_MAX_WORD_TOKENS = 15   # entitylookup.maxtokensize

# MetaMapLite default allowed head POS (EntityLookup5.defaultAllowedPartOfSpeech).
# "" = untagged token is allowed (accept everything when no POS).
DEFAULT_ALLOWED_POS = {
    "CD", "FW", "RB", "IN", "NN", "NNS", "NNP", "NNPS",
    "JJ", "JJR", "JJS", "LS", "",
}


def _is_word(tok: Token) -> bool:
    return tok.is_alphanumeric


def _head_index(tokens: List[Token]) -> int:
    """Approximate the phrase head as the last word token (no parser, like MML)."""
    for i in range(len(tokens) - 1, -1, -1):
        if _is_word(tokens[i]):
            return i
    return len(tokens) - 1


def _build_concepts(records: List[dict], store) -> Dict[str, Tuple[ConceptInfo, str]]:
    """Group store records by (cui, matched-string) -> (ConceptInfo, conceptString).

    Sources are aggregated per CUI; one ConceptInfo per distinct (cui, str).
    """
    # aggregate sources per cui first
    sources: Dict[str, Set[str]] = {}
    for r in records:
        sources.setdefault(r["cui"], set()).add(r["sab"])

    concepts: Dict[Tuple[str, str], ConceptInfo] = {}
    for r in records:
        cui, strv = r["cui"], r["str"]
        key = (cui, strv)
        if key not in concepts:
            concepts[key] = ConceptInfo(
                cui=cui,
                preferred_name=store.preferred_name(cui),
                semantic_types=set(store.semantic_types(cui)),
                sources=sources[cui],
                matched_term=strv,
            )
    return concepts


def find_candidates(tokens: List[Token], store,
                    allowed_pos: Optional[Set[str]] = None,
                    overlapping: bool = False,
                    excluded_terms=None,
                    max_word_tokens: int = DEFAULT_MAX_WORD_TOKENS) -> List[Entity]:
    """Generate scored candidate entities for one phrase/sentence token list.

    ``tokens`` is the full mm-token list (incl. whitespace/punct) for the span,
    with offsets already document-relative. ``allowed_pos`` filters the head
    token by POS when POS tags are present (None = no POS filtering yet).
    """
    head_pos = _head_index(tokens)
    head_token = tokens[head_pos] if tokens else None
    n_phrase_words = sum(1 for t in tokens if _is_word(t))
    span_map: Dict[Tuple[int, int], Entity] = {}

    n = len(tokens)
    for i in range(n):
        first = tokens[i]
        # first token must be a word, not "other", and (if POS present) allowed
        if not _is_word(first):
            continue
        if first.text.lower() == "other":
            continue
        if allowed_pos is not None and first.pos is not None and first.pos not in allowed_pos:
            continue

        word_count = 0
        for j in range(i + 1, n + 1):
            sub = tokens[i:j]
            last = sub[-1]
            if _is_word(last):
                word_count += 1
                if word_count > max_word_tokens:
                    break
            if not _is_word(last):
                continue  # sublist must end on a word token

            original_term = "".join(t.text for t in sub)
            if len(original_term) < MIN_TERM_LENGTH:
                continue
            if not (original_term[0].isalpha() and original_term[-1].isalnum()):
                continue

            records = store.lookup(original_term)
            if not records:
                continue

            norm_term = normalize_lookup(original_term)
            start = first.span.start
            end = last.span.end
            span = (start, end)
            concepts = _build_concepts(records, store)

            # centrality: does this span cover the phrase head?
            is_head = (head_token is not None and
                       start <= head_token.span.start and head_token.span.end <= end)
            # variation depends on the matched text words (same for all concepts here)
            matched_words = [t.text for t in sub if t.is_alphanumeric]
            variant_levels = [store.lookup_variant(w) for w in matched_words] or [0]
            n_meta_words_cache: Dict[str, int] = {}
            ev_list: List[Ev] = []
            for (cui, strv), concept in concepts.items():
                if excluded_terms is not None and excluded_terms.is_excluded(cui, norm_term):
                    continue
                n_meta = n_meta_words_cache.get(strv)
                if n_meta is None:
                    n_meta = max(1, sum(1 for w in strv.split() if w))
                    n_meta_words_cache[strv] = n_meta
                score, components = scoring.score_match(
                    is_head=is_head,
                    variant_levels=variant_levels,        # per matched-word inflection distance
                    phrase_span=n_phrase_words, n_phrase_words=max(1, n_phrase_words),
                    meta_span=n_meta, n_meta_words=n_meta,
                )
                ev_list.append(Ev(
                    concept=concept,
                    span=Span(start, end),
                    matched_text=original_term,
                    score=score,
                    score_components=components,
                    part_of_speech=first.pos or "",
                ))

            if not ev_list:
                continue
            ev_list.sort(key=lambda e: e.score, reverse=True)
            if span in span_map:
                span_map[span].evidence.extend(ev_list)
            else:
                span_map[span] = Entity(span=Span(start, end),
                                        matched_text=original_term,
                                        evidence=ev_list,
                                        lexical_category=first.pos or "")

    entities = list(span_map.values())
    for ent in entities:
        ent.evidence.sort(key=lambda e: e.score, reverse=True)
    return scoring.resolve_overlap(entities, overlapping=overlapping)

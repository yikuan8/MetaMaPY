"""MetaMap 4-component scoring + overlap resolution.

Faithful port of MetaMapLite's
``gov.nih.nlm.nls.metamap.evaluation.Scoring`` (see
MetaMapLite/src/main/java/gov/nih/nlm/nls/metamap/evaluation/Scoring.java).

    score = 1000 * (int)(centrality + variation + 2*(coverage + cohesiveness)) / 6

PARITY NOTE — DO NOT "fix" the integer arithmetic below. Java's Scoring.java
computes several of these with **integer division** and an `(int)` truncation.
Those truncations change the output values, so to stay byte-compatible with
MetaMapLite we reproduce them exactly with Python ``//`` and ``int()``:

  * computeVariation:  ``4/(D+4)`` and ``sum/n`` are int divisions -> variation
    is 1 only when every token is an exact (distance-0) match, else 0.
  * computeCoverage / computeCohesiveness: the per-string ratios are int
    divisions before the final ``/3.0``.
  * combineValues: the bracket is cast to ``(int)`` before ``/6.0``.

Variant distance table (lower = closer):
    spelling 0 | inflectional 1 | synonym/acronym/abbrev 2 | spelling-variant 3
"""

from __future__ import annotations

from typing import List

from metamapy.model import Entity


# --- the four components (faithful ports) ---------------------------------

def compute_centrality(is_head: bool) -> int:
    """1 if the match involves the phrase head, else 0."""
    return 1 if is_head else 0


def compute_variation(variant_levels: List[int]) -> int:
    """Average of 4/(D+4) over matched tokens, with Java integer semantics.

    Both ``4/(D+4)`` and the final ``sum/n`` are integer divisions in Java, so
    the result is effectively 1 iff every token has distance 0, else 0.
    """
    n = len(variant_levels)
    if n == 0:
        return 0
    total = 0
    for d in variant_levels:
        total += 4 // (d + 4)          # int division (1 iff d == 0)
    return total // n                  # int division


def compute_coverage(phrase_span: int, n_phrase_words: int,
                     meta_span: int, n_meta_words: int) -> float:
    """Weighted coverage; Metathesaurus string weighted 2x. Inner ratios are int."""
    return ((phrase_span // n_phrase_words) + (2 * (meta_span // n_meta_words))) / 3.0


def compute_cohesiveness(phrase_span: int, n_phrase_words: int,
                         meta_span: int, n_meta_words: int) -> float:
    """Like coverage but uses squared spans (emphasizes connected components)."""
    return (((phrase_span * phrase_span) // (n_phrase_words * n_phrase_words))
            + (2 * (meta_span * meta_span) // (n_meta_words * n_meta_words))) / 3.0


def compute_involvement(size_of_phrase: int, num_phrase_span: int,
                        num_candidate_span: int, num_words: int) -> float:
    """Ported for completeness; not used by combine_values (matches Java)."""
    return ((num_phrase_span * 1.0) / (size_of_phrase * 1.0)) + \
           ((num_candidate_span * 1.0) / (num_words * 1.0)) / 2.0


def combine_values(centrality: float, variation: float,
                   coverage: float, cohesiveness: float) -> float:
    """Final MMI mapping score in [0, 1000].

    Mirrors ``1000*((int)(c + v + 2.0*(cov+coh))/6.0)`` — note the (int) cast
    truncates the bracket before dividing by 6.
    """
    bracket = centrality + variation + (2.0 * (coverage + cohesiveness))
    return 1000 * (int(bracket) / 6.0)


# --- convenience scorer ----------------------------------------------------

def score_match(is_head: bool, variant_levels: List[int],
                phrase_span: int, n_phrase_words: int,
                meta_span: int, n_meta_words: int) -> tuple:
    """Compute (score, components) for one candidate match.

    Returns the final score and the four components so the JSON output and
    downstream consumers can inspect exactly how a score was reached.
    """
    centrality = compute_centrality(is_head)
    variation = compute_variation(variant_levels)
    coverage = compute_coverage(phrase_span, n_phrase_words, meta_span, n_meta_words)
    cohesiveness = compute_cohesiveness(phrase_span, n_phrase_words, meta_span, n_meta_words)
    score = combine_values(centrality, variation, coverage, cohesiveness)
    components = {
        "centrality": centrality,
        "variation": variation,
        "coverage": coverage,
        "cohesiveness": cohesiveness,
    }
    return score, components


# --- overlap resolution (data-independent) ---------------------------------

def resolve_overlap(entities: List[Entity], overlapping: bool = False) -> List[Entity]:
    """Apply longest-match selection unless ``overlapping`` is set.

    Longest-match: when two entities overlap in the source text, keep the one
    with the wider span; break ties by best evidence score. Entities fully
    subsumed by a kept entity are dropped. With ``overlapping=True`` all
    entities are kept (only exact-duplicate spans are de-duplicated).
    """
    if not entities:
        return []

    def best_score(e: Entity) -> float:
        return e.best.score if e.best else 0.0

    # Prefer wider spans, then higher score.
    ordered = sorted(entities,
                     key=lambda e: (e.span.length, best_score(e)),
                     reverse=True)
    kept: List[Entity] = []
    for ent in ordered:
        if overlapping:
            if not any(k.span == ent.span for k in kept):
                kept.append(ent)
            continue
        subsumed = any(k.span.start <= ent.span.start and ent.span.end <= k.span.end
                       for k in kept)
        if not subsumed:
            kept.append(ent)
    kept.sort(key=lambda e: e.span.start)
    return kept

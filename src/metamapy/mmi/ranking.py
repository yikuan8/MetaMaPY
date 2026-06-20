"""MMI ranking — faithful port of gov.nih.nlm.nls.metamap.mmi.Ranking.

Computes the MMI score shown in field 3 of the MMI output:
``score = -10000 * negNRank = 10000 * normalizedRank``.

See docs/MMI_FORMAT.md. Only the MetaMap mapping score and MeSH tree depth
influence the result (word/char weights ``ww``/``wc`` are 0).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

# --- processing parameters (Ranking.java constants) ------------------------
NC = 0.0      # character normalization index
NF = -5.0     # frequency normalization index
NM = 0.0      # MeSH normalization index
NMM = -10.0   # MetaMap normalization index
NW = 0.0      # word normalization index
NZ = 0.0      # final normalization index
WC = 0.0      # character count weight
WD = 1.0      # default tree depth
WM = 14.0     # MeSH tree depth weight
WMM = 1.0     # MetaMap weight
WW = 0.0      # word count weight

MMI_TREE_DEPTH_SPECIFICITY_DIVISOR = 8
MMI_WORD_SPECIFICITY_DIVISOR = 26
MMI_CHARACTER_SPECIFICITY_DIVISOR = 102

MAX_FREQ = 1000.0


@dataclass
class AATF:
    """Aggregated concept with its computed rank, ready to render."""
    neg_n_rank: float
    concept: str
    semantic_types: List[str]
    cui: str
    tuple_list: list
    tree_codes: List[str]

    def sort_key(self):
        # AATF.compareTo: primarily by negNRank ascending (best score first).
        return (self.neg_n_rank, self.concept, self.cui)


@dataclass
class TermFrequency:
    meta_concept: str
    semantic_types: List[str]
    tuple_set: list
    title_flag: bool
    cui: str
    frequency_count: int
    average_value: float           # mapping score (0..1000) of the FIRST ev
    treecodes: List[str] = field(default_factory=list)


# --- math (Ranking.java) ---------------------------------------------------

def compute_tree_depth(treecode: str) -> int:
    return len(treecode.split("."))


def set_value1(value: float) -> float:
    if value > 1.0:
        return 1.0
    if value < 0.0:
        return 0.0
    return value


def normalize_value(n: float, value: float) -> float:
    if n == 0.0:
        return value
    if n > 0.0:
        value1 = set_value1(value)
        en = math.exp(n)
        a = en + 1
        b = en - 1
        c = (-n) * value1
        ec = math.exp(c)
        return (a / b) * ((1 - ec) / (1 + ec))
    # n < 0
    value1 = set_value1(value)
    m = -n
    em = math.exp(m)
    a = em + 1
    b = em - 1
    c = (a + (b * value1)) / (a - (b * value1))
    return math.log(c) / m


def compute_tree_depth_specificity(treecodes: List[str], wd: float) -> float:
    return max(wd, sum(compute_tree_depth(tc) for tc in treecodes))


def _word_count(concept: str) -> int:
    # Zero-weighted (ww=0), so exact tokenization is irrelevant to the score.
    return len([w for w in concept.split() if w])


def compute_specificities(concept: str, mm_value: float, treecodes: List[str],
                          wd: float, nmm: float, nm: float,
                          nw: float, nc: float) -> List[float]:
    mm_spec = mm_value / 1000.0
    nmm_spec = normalize_value(nmm, mm_spec)
    m_value = compute_tree_depth_specificity(treecodes, wd)
    m_spec = m_value / MMI_TREE_DEPTH_SPECIFICITY_DIVISOR
    nm_spec = normalize_value(nm, m_spec)
    w_value = _word_count(concept)
    w_spec = w_value / MMI_WORD_SPECIFICITY_DIVISOR
    nw_spec = normalize_value(nw, w_spec)
    c_value = len(concept)
    c_spec = c_value // MMI_CHARACTER_SPECIFICITY_DIVISOR   # int in Java
    nc_spec = normalize_value(nc, c_spec)
    return [nmm_spec, nm_spec, nw_spec, nc_spec]


def set_aatf_rank(title_flag: bool, spec: float, n_freq: float) -> float:
    return spec if title_flag else n_freq * spec


def compute_weighted_value(frequencies: List[float], values: List[float]) -> float:
    products = [frequencies[i] * values[i] for i in range(min(len(frequencies), len(values)))]
    return sum(products) / sum(frequencies)


def process_tf(tf_list: List[TermFrequency], max_freq: float = MAX_FREQ) -> List[AATF]:
    aatf_list: List[AATF] = []
    for tf in tf_list:
        freq = tf.frequency_count / max_freq
        n_freq = normalize_value(NF, freq)
        specificities = compute_specificities(
            tf.meta_concept, tf.average_value, tf.treecodes,
            WD, NMM, NM, NW, NC)
        frequencies = [WMM, WM, WW, WC]
        spec = compute_weighted_value(frequencies, specificities)
        rank = set_aatf_rank(tf.title_flag, spec, n_freq)
        normalized_rank = normalize_value(NZ, rank)
        neg_n_rank = -1 * normalized_rank
        aatf_list.append(AATF(neg_n_rank, tf.meta_concept, tf.semantic_types,
                              tf.cui, tf.tuple_set, tf.treecodes))
    return aatf_list


def mmi_score(aatf: AATF) -> float:
    """Field-3 score: -10000 * negNRank."""
    return -10000.0 * aatf.neg_n_rank

"""Core data model.

The whole pipeline carries character offsets end to end. Nothing collapses to a
single best answer until output formatting: an ``Entity`` keeps its full N-best
list of ``Ev`` (evidence) so downstream consumers can inspect and re-rank
alternatives. This mirrors MetaMapLite's Entity/Ev/ConceptInfo types
(see MetaMapLite .../lite/types/) plus MetaMap's notion of a
candidate mapping lattice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass(frozen=True)
class Span:
    """A character span into the original document text (0-based, [start, end))."""

    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class Token:
    text: str
    span: Span
    pos: Optional[str] = None          # Penn Treebank tag from scispaCy
    token_class: str = ""              # mm class: ws/an/uc/lc/ic/nu/gr/op/cp/ob/cb/cm/pd/pn/unknown
    is_alphanumeric: bool = True


@dataclass
class Sentence:
    text: str
    span: Span
    tokens: List[Token] = field(default_factory=list)


@dataclass
class Phrase:
    """A noun-phrase chunk (replaces MetaMap's minimal-commitment parse)."""

    text: str
    span: Span
    tokens: List[Token] = field(default_factory=list)
    head_index: Optional[int] = None   # index into tokens of the phrase head


@dataclass
class ConceptInfo:
    """A UMLS concept record (from the cuiconcept / cuist / cuisourceinfo indexes)."""

    cui: str
    preferred_name: str
    semantic_types: Set[str] = field(default_factory=set)
    sources: Set[str] = field(default_factory=set)
    matched_term: str = ""             # the UMLS string that matched
    definition: Optional[str] = None   # from MRDEF; concept definition, for downstream use


@dataclass
class Ev:
    """Evidence: one concept matched against one text span, with its score.

    ``score_components`` holds the four MetaMap components so the final score is
    fully reproducible and inspectable.
    """

    concept: ConceptInfo
    span: Span
    matched_text: str
    score: float = 0.0
    score_components: dict = field(default_factory=dict)  # centrality/variation/coverage/cohesiveness
    variant_level: int = 0
    part_of_speech: str = ""           # head POS / lexical category, for MMI trigger info


@dataclass
class Entity:
    """A text mention and its N-best competing concepts (the candidate lattice)."""

    span: Span
    matched_text: str
    evidence: List[Ev] = field(default_factory=list)   # sorted best-first; len>1 = ambiguity
    negated: bool = False
    field_id: str = "text"             # MMI location field (free text -> "text")
    sentence_number: int = 0           # utterance number within the field
    lexical_category: str = ""         # head lexical category (POS)

    @property
    def best(self) -> Optional[Ev]:
        return self.evidence[0] if self.evidence else None


@dataclass
class Document:
    doc_id: str
    text: str
    sentences: List[Sentence] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)

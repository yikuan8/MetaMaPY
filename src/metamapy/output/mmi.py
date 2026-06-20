"""MMI (Fielded MetaMap Indexing) output — byte-parity port.

Faithful port of MetaMapLite's live MMI path:
``MMI.renderEntityList(PrintWriter, ...)`` (see docs/MMI_FORMAT.md). Evidence is
aggregated per document by CUI, ranked via mmi.ranking, and rendered as:

    docid|MMI|score|concept|cui|[semtypes]|triggerinfo|fields|posinfo|treecodes|

Reference: MetaMapLite/.../resultformats/mmi/MMI.java
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from metamapy.model import Document, Entity
from metamapy.mmi.ranking import TermFrequency, process_tf, mmi_score


@dataclass
class _Tuple:
    """Tuple7 analogue used for trigger/position rendering."""
    concept_string: str
    field: str
    nsent: int
    matched_text: str
    lexcat: str
    neg: int
    posinfo: List[Tuple[int, int]] = field(default_factory=list)  # (start, end)

    def key(self):
        return (self.concept_string, self.field, self.nsent,
                self.matched_text, self.lexcat, self.neg, tuple(self.posinfo))


def _flatten_ws(s: str) -> str:
    """Collapse internal whitespace (incl. newlines) so the field stays on one line."""
    return " ".join(s.split())


def _render_tuple_info(t: _Tuple) -> str:
    return (f'"{_flatten_ws(t.concept_string)}"-{t.field}-{t.nsent}-'
            f'"{_flatten_ws(t.matched_text)}"-{t.lexcat}-{t.neg}')


def _render_position_info(t: _Tuple) -> str:
    # PositionImpl.toStringStartLength(): start + "/" + (end - start)
    return ",".join(f"{start}/{end - start}" for start, end in t.posinfo)


def _semantic_types_str(semtypes: List[str]) -> str:
    # Java List.toString(): "[a, b]" (brackets, comma-space).
    return "[" + ", ".join(semtypes) + "]"


def _entities_to_term_frequencies(entities: List[Entity],
                                  treecode_lookup: Callable[[str], List[str]]):
    """Mirror MMI.entityToTermFrequencyInfo: aggregate evidence by CUI."""
    tf_map = {}
    for entity in entities:
        field_id = entity.field_id or "text"
        title_flag = field_id in ("title", "TI")
        neg = 1 if entity.negated else 0
        for ev in entity.evidence:
            cui = ev.concept.cui
            tup = _Tuple(
                concept_string=ev.concept.matched_term or ev.concept.preferred_name,
                field=field_id,
                nsent=entity.sentence_number,
                matched_text=ev.matched_text,
                lexcat=entity.lexical_category or ev.part_of_speech,
                neg=neg,
                posinfo=[(ev.span.start, ev.span.end)],
            )
            if cui in tf_map:
                tf = tf_map[cui]
                # LinkedHashSet semantics: dedup tuples, but freq increments always.
                if tup.key() not in {x.key() for x in tf.tuple_set}:
                    tf.tuple_set.append(tup)
                tf.frequency_count += 1
            else:
                preferred = ev.concept.preferred_name
                tf_map[cui] = TermFrequency(
                    meta_concept=preferred,
                    semantic_types=list(ev.concept.semantic_types),
                    tuple_set=[tup],
                    title_flag=title_flag,
                    cui=cui,
                    frequency_count=1,
                    average_value=ev.score,                  # FIRST ev's score (parity)
                    treecodes=treecode_lookup(preferred),
                )
    return list(tf_map.values())


def format_mmi(document: Document,
               treecode_lookup: Optional[Callable[[str], List[str]]] = None) -> str:
    """Render one document's entities as MMI lines."""
    if treecode_lookup is None:
        treecode_lookup = lambda _name: []   # noqa: E731

    tf_list = _entities_to_term_frequencies(document.entities, treecode_lookup)
    aatf_list = process_tf(tf_list, 1000)
    aatf_list.sort(key=lambda a: a.sort_key())

    lines = []
    for aatf in aatf_list:
        tuples: List[_Tuple] = aatf.tuple_list
        fields_seen = []
        for t in tuples:
            if t.field not in fields_seen:
                fields_seen.append(t.field)
        score = f"{mmi_score(aatf):.2f}"
        line = "|".join([
            document.doc_id,
            "MMI",
            score,
            aatf.concept,
            aatf.cui,
            _semantic_types_str(aatf.semantic_types),
            ",".join(_render_tuple_info(t) for t in tuples),
            ";".join(fields_seen),
            ";".join(_render_position_info(t) for t in tuples),
            ";".join(aatf.tree_codes),
        ]) + "|\n"
        lines.append(line)
    return "".join(lines)

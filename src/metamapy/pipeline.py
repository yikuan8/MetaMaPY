"""The processing pipeline (wired).

    segment + POS  ->  candidate lookup (longest-match)  ->  [refine_candidates]
    ->  negation  ->  restrict (sts/sources)  ->  [refine_mappings]  ->  MMI | JSON

The ``refine_*`` methods are identity by default — extension points where a
downstream consumer can filter or re-rank entities without changing the core.
"""

from __future__ import annotations

from metamapy.config import Config
from metamapy.model import Document


class Pipeline:
    def __init__(self, config: Config):
        self.config = config
        self._store = None
        self._excluded = None

    def excluded_terms(self):
        if self._excluded is None:
            from metamapy.stages.special_terms import SpecialTerms, default_special_terms
            self._excluded = (SpecialTerms(self.config.excluded_terms_file)
                              if self.config.excluded_terms_file
                              else default_special_terms())
        return self._excluded

    def store(self):
        if self._store is None:
            if not self.config.index_dir:
                raise RuntimeError(
                    "No index directory. Pass --index-dir or set $MML_INDEXDIR "
                    "(build it with: python -m metamapy.index.build ...).")
            from metamapy.index.store import UmlsStore
            self._store = UmlsStore(self.config.index_dir)
        return self._store

    def process(self, doc_id: str, text: str) -> Document:
        from metamapy.stages import frontend, lookup, restrict
        from metamapy.stages.lookup import DEFAULT_ALLOWED_POS

        doc = Document(doc_id=doc_id, text=text)
        doc.sentences = frontend.analyze(text, self.config.segmentation)

        entities = []
        for i, sent in enumerate(doc.sentences):
            ents = lookup.find_candidates(
                sent.tokens, self.store(),
                allowed_pos=DEFAULT_ALLOWED_POS,
                overlapping=self.config.overlapping,
                excluded_terms=self.excluded_terms())
            for e in ents:
                e.sentence_number = i
            entities.extend(ents)

        from metamapy.stages import abbreviations
        entities = abbreviations.link(doc, entities, self.store())

        entities = self.refine_candidates(entities)
        if self.config.negation:
            from metamapy.stages import negation
            negation.mark(doc, entities)
        entities = restrict.apply(entities, self.config)
        doc.entities = self.refine_mappings(entities)
        return doc

    # --- extension seams (identity by default) ------------------------------
    def refine_candidates(self, entities):
        """Hook: filter/validate candidate concepts. Default: identity."""
        return entities

    def refine_mappings(self, entities):
        """Hook: re-rank/correct mappings with sentence context. Default: identity."""
        return entities

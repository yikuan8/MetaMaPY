"""Excluded-terms filtering (port of MetaMapLite SpecialTerms).

A concept match is excluded if its key is in the list. Keys are
``CUI:term`` (exclude that concept for that term) or ``*:term`` (exclude that
term for any concept), where ``term`` is the *normalized* lookup form
(normalize_lookup). This matches MetaMapLite's makeKey/isExcluded.

The official ``specialterms.txt`` ships only with the NLM data package (not the
source, and currently unavailable). We bundle a small, conservative starter list
that users can extend or replace via ``metamaplite.excluded.termsfile`` /
Config.excluded_terms_file. Lines starting with ``#`` and blank lines are ignored.

Reference: MetaMapLite/.../lite/SpecialTerms.java
"""

from __future__ import annotations

import os
from typing import Optional, Set

_BUNDLED = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data", "specialterms.txt")


class SpecialTerms:
    def __init__(self, filename: Optional[str] = None):
        self.keys: Set[str] = set()
        if filename:
            self.add_terms(filename)

    def add_terms(self, filename: str) -> None:
        if not filename or not os.path.exists(filename):
            return
        with open(filename, "r", encoding="utf-8") as fh:
            for line in fh:
                entry = line.strip()
                if entry and not entry.startswith("#"):
                    self.keys.add(entry)

    @staticmethod
    def _key(cui: str, term: str) -> str:
        return f"{cui}:{term}"

    def is_excluded(self, cui: str, term: str) -> bool:
        return self._key(cui, term) in self.keys or self._key("*", term) in self.keys


def default_special_terms() -> SpecialTerms:
    """SpecialTerms loaded from the bundled starter list (empty if absent)."""
    return SpecialTerms(_BUNDLED if os.path.exists(_BUNDLED) else None)

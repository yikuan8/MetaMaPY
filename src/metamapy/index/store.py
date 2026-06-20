"""Read-only access to the built LMDB UMLS indexes.

Mirrors MetaMapLite's IVFLookup: given a (normalized) term, return the matching
concept records; plus preferred-name and semantic-type lookups by CUI.
"""

from __future__ import annotations

from typing import Dict, List

import lmdb

from metamapy.stages.normalization import normalize_lookup


class UmlsStore:
    def __init__(self, path: str):
        self.env = lmdb.open(path, readonly=True, max_dbs=8, lock=False,
                             readahead=False)
        self.cuiconcept = self.env.open_db(b"cuiconcept")
        self.cuist = self.env.open_db(b"cuist")
        self.cuisourceinfo = self.env.open_db(b"cuisourceinfo", dupsort=True)
        try:
            self.meshtc = self.env.open_db(b"meshtc", dupsort=True, create=False)
        except lmdb.Error:
            self.meshtc = None     # index built without tree codes
        try:
            self.vars = self.env.open_db(b"vars", create=False)
        except lmdb.Error:
            self.vars = None       # index built without variants

    def close(self) -> None:
        self.env.close()

    def lookup(self, term: str) -> List[Dict[str, str]]:
        """Return source records for a term (matches EntityLookup: original + normalized)."""
        keys = {term, normalize_lookup(term)}
        records: List[Dict[str, str]] = []
        with self.env.begin(db=self.cuisourceinfo) as txn:
            cur = txn.cursor()
            for key in keys:
                if not key:
                    continue
                if cur.set_key(key.encode()):
                    for val in cur.iternext_dup():
                        cui, sui, strv, sab, tty = val.decode().split("|", 4)
                        records.append({"cui": cui, "sui": sui, "str": strv,
                                        "sab": sab, "tty": tty})
        return records

    def preferred_name(self, cui: str) -> str:
        with self.env.begin(db=self.cuiconcept) as txn:
            v = txn.get(cui.encode())
        return v.decode() if v else ""

    def semantic_types(self, cui: str) -> List[str]:
        with self.env.begin(db=self.cuist) as txn:
            v = txn.get(cui.encode())
        return v.decode().split(",") if v else []

    def lookup_variant(self, word: str) -> int:
        """Variant distance of a word: 1 if a known inflectional variant, else 0.

        Feeds Scoring.computeVariation; 0 = exact (unknown words default to exact).
        """
        if self.vars is None:
            return 0
        with self.env.begin(db=self.vars) as txn:
            v = txn.get(word.lower().encode())
        return int(v) if v else 0

    def treecodes(self, name: str) -> List[str]:
        """MeSH tree codes for a term (looked up by normalized name).

        Returns whatever is stored, including the ``x.x.x.x`` placeholder for
        MeSH concepts lacking a real tree number (matches MetaMapLite).
        """
        if self.meshtc is None:
            return []
        key = normalize_lookup(name).encode()
        out: List[str] = []
        with self.env.begin(db=self.meshtc) as txn:
            cur = txn.cursor()
            if cur.set_key(key):
                for v in cur.iternext_dup():
                    out.append(v.decode())
        return out

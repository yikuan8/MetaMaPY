"""Term normalization for dictionary lookup.

Faithful port of MetaMapLite ``Normalization.normalizeLiteMetaString`` and the
``NLSStrings`` / ``MetamapTokenization`` helpers it calls. This is the function
used to build the index keys AND to normalize query terms, so it must match
exactly for lookups to hit.

Steps (order matters):
  1. removeLeftParentheticals  — strip a leading [X]/[V]/[D]/[M]/[EDTA]/[SO]/[Q]
  2. toLowerCase
  3. removeHyphens             — '-' -> ' '
  4. stripPossessives          — drop trailing "'s" / "'" per token

Note: unlike the *full* normalizeMetaString, the Lite variant does NOT do
syntactic uninversion, so "Cancer, Lung" -> "cancer, lung" (comma retained).

Reference: MetaMapLite/.../lite/Normalization.java
           MetaMapLite/.../nlsstrings/NLSStrings.java
           MetaMapLite/.../nlsstrings/MetamapTokenization.java
"""

from __future__ import annotations

from typing import List

_LEFT_PARENTHETICALS = ["[X]", "[V]", "[D]", "[M]", "[EDTA]", "[SO]", "[Q]"]
# MetamapTokenization.TOKEN_DELIMITERS (used by stripPossessives)
_TOKEN_DELIMITERS = " \t\n\r\f$|~"


def _string_tokenizer(s: str, delimiters: str) -> List[str]:
    """Mimic java.util.StringTokenizer: split on any delimiter char, skip empties."""
    dset = set(delimiters)
    tokens: List[str] = []
    cur: List[str] = []
    for ch in s:
        if ch in dset:
            if cur:
                tokens.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    return tokens


def remove_extra_blanks(s: str) -> str:
    """NLSStrings.removeExtraBlanks: collapse spaces; note the trailing space."""
    toks = _string_tokenizer(s, " ")
    return "".join(t + " " for t in toks)   # Java appends a space after each token


def remove_left_parentheticals(s: str) -> str:
    for p in _LEFT_PARENTHETICALS:
        if s.startswith(p):                 # Java: indexOf(p) == 0
            return s[len(p):]               # returns WITHOUT removeExtraBlanks
    return remove_extra_blanks(s)


def remove_hyphens(s: str) -> str:
    return remove_extra_blanks(s.replace("-", " "))


def remove_possessives(token: str) -> str:
    """MetamapTokenization.removePossessives (preserves Java's if/else-if flow)."""
    pos = token.rfind("'s")
    if pos >= 0 and pos == len(token) - 2:
        if pos - 1 >= 0 and token[pos - 1].isalnum():
            return token[:pos] + token[pos + 2:]
        # inner condition false -> fall through to return token (else-if skipped)
    else:
        pos = token.rfind("'")
        if pos >= 0 and pos == len(token) - 1 and pos != 0 and token[pos - 1] == "s":
            return token[:pos] + token[pos + 1:]
    return token


def strip_possessives(s: str) -> str:
    toks = _string_tokenizer(s, _TOKEN_DELIMITERS)
    return " ".join(remove_possessives(t) for t in toks)


def normalize(term: str) -> str:
    """normalizeLiteMetaString: parentheticals, lowercase, hyphens->space, possessives."""
    s = remove_left_parentheticals(term)
    s = s.lower()
    s = remove_hyphens(s)
    s = strip_possessives(s)
    return s


def normalize_lookup(term: str) -> str:
    """normalizeUtf8AsciiString: the key used by EntityLookup (NormalizedStringCache).

    Same as normalize() but WITHOUT hyphen removal (and with greek->ascii, which we
    approximate as identity pending the GreekCharacters table). This is the function
    used to build cuisourceinfo keys AND to normalize query terms, so both sides match.
    """
    # TODO: greek_to_ascii(term) once the GreekCharacters expansion table is ported.
    s = remove_left_parentheticals(term)
    s = s.lower()
    s = strip_possessives(s)
    return s

"""Tokenization — PARITY-CRITICAL (token offsets drive the MMI posinfo field).

Faithful port of MetaMapLite's tokenizer pipeline as used by lookup:
``Scanner.analyzeText`` = addOffsets(classifyTokenList(mmPosTokenize(text, 0))).

  * mmTokenize(text, KEEP_WHITE_SPACE): splits on whitespace and treats every
    punctuation char as its own token; words are maximal runs. Whitespace and
    punctuation are KEPT as 1-char tokens (style 0), so concatenating tokens
    reconstructs the text and cumulative offsets are exact.
  * classify_token: regex classification into mm classes (precedence matters).
  * add_offsets: assign each token a cumulative character offset.

scispaCy is used elsewhere for sentence splitting / POS / chunks; this mm-regime
tokenizer governs spans so they match MetaMapLite byte-for-byte.

Reference: MetaMapLite/.../prefix/Tokenize.java (mmTokenize)
           MetaMapLite/.../prefix/Scanner.java (classify/offsets)
           MetaMapLite/.../prefix/CharUtils.java (isPunct/isWhiteSpace)
"""

from __future__ import annotations

import re
from typing import List

from metamapy.model import Sentence, Span, Token

KEEP_WHITE_SPACE = 0
STRIP_WHITE_SPACE = 2

# CharUtils.isPunct
_PUNCT = set("~!@#$%^&*()_+-=|\\<>?/,.`';:[]{}\"")

# CharUtils.isWhiteSpace (ASCII + the listed unicode spaces)
_WHITESPACE = set(" \r\t\n\f") | {
    " ", " ", "᠎", " ", " ", " ", " ",
    " ", " ", " ", " ", " ", " ", " ",
    "​", " ", " ", "　", "﻿",
}

# Java also treats Character.isWhitespace / isSpaceChar; the explicit set above
# covers the documented cases. \f (form feed) included.

_ALNUM_CLASSES = {"an", "uc", "lc", "ic", "nu", "gr"}


def _is_ws(ch: str) -> bool:
    return ch in _WHITESPACE or ch.isspace()


def _is_punct(ch: str) -> bool:
    return ch in _PUNCT


def mm_tokenize(term: str, style: int = KEEP_WHITE_SPACE) -> List[str]:
    """Port of Tokenize.mmTokenize. Returns token strings in order."""
    wl: List[str] = []
    cur: List[str] = []
    word_boundary = 0
    punct_boundary = 0

    for ch in term:
        if _is_ws(ch) or _is_punct(ch):
            # (Java has a redundant inner `if` with identical condition.)
            if cur:
                wl.append("".join(cur))
            cur = []
            word_boundary = 1
            punct_boundary = 0
            if style == STRIP_WHITE_SPACE and _is_ws(ch):
                pass
            else:
                cur.append(ch)
        else:
            if word_boundary == 1 or punct_boundary == 1:
                if cur:
                    wl.append("".join(cur))
                cur = []
                word_boundary = 0
                punct_boundary = 0
            cur.append(ch)

    wl.append("".join(cur))   # Java adds final token unconditionally
    return wl


# --- classification (Scanner.classifyToken, precedence order) --------------

_WS = re.compile(r"^\s$")
_AN = re.compile(r"^[A-Za-z]+[0-9]+$")
_UC = re.compile(r"^[A-Z][A-Z0-9]+$")
_LC = re.compile(r"^[a-z]+$")
_IC = re.compile(r"^[A-Za-z]+$")
_NU = re.compile(r"^[0-9]+$")
_GR = re.compile(r"^[Ͱ-Ͽ]+$")     # approximation of \p{InGreek}
_OP = re.compile(r"^\($")
_CP = re.compile(r"^\)$")
_OB = re.compile(r"^\[$")
_CB = re.compile(r"^\]$")
_CM = re.compile(r"^,$")
_PD = re.compile(r"^\.$")
_PN = re.compile(r"^[\(\)!@#$%^&*\+\=\-\_\[\]\{\}\.\,\?\/\']+$")

_CLASSIFIERS = [
    (_WS, "ws"), (_AN, "an"), (_UC, "uc"), (_LC, "lc"), (_IC, "ic"),
    (_NU, "nu"), (_GR, "gr"), (_OP, "op"), (_CP, "cp"), (_OB, "ob"),
    (_CB, "cb"), (_CM, "cm"), (_PD, "pd"), (_PN, "pn"),
]


def classify_token(text: str) -> str:
    for pattern, label in _CLASSIFIERS:
        if pattern.match(text):
            return label
    return "unknown"


def analyze_text(text: str, start: int = 0) -> List[Token]:
    """Scanner.analyzeText: tokenize (KEEP_WHITE_SPACE), classify, add offsets."""
    tokens: List[Token] = []
    offset = start
    for tok_text in mm_tokenize(text, KEEP_WHITE_SPACE):
        cls = classify_token(tok_text)
        tokens.append(Token(
            text=tok_text,
            span=Span(offset, offset + len(tok_text)),
            token_class=cls,
            is_alphanumeric=cls in _ALNUM_CLASSES,
        ))
        offset += len(tok_text)
    return tokens


def tokenize(sentence: Sentence) -> None:
    """Pipeline hook: populate sentence.tokens with document-relative offsets."""
    sentence.tokens = analyze_text(sentence.text, sentence.span.start)

"""scispaCy front-end: sentence segmentation + POS tagging.

scispaCy provides sentence boundaries and Penn POS tags (``token.tag_``). We pair
these with our mm-regime tokenizer (which owns the parity-exact offsets): POS
tags are attached to mm tokens by character span.

Like MetaMapLite's default (no chunker) configuration, candidate lookup runs over
the whole sentence token list with POS filtering on the head token — this avoids
depending on a dependency parser's noun-chunk quality and won't miss hyphenated or
multiword terms.

Model is configurable via $METAMAPY_SPACY_MODEL (default en_core_sci_sm); falls
back to en_core_web_sm.
"""

from __future__ import annotations

import os
from typing import List, Tuple

from metamapy.model import Sentence, Span, Token
from metamapy.stages.tokenization import analyze_text

_DEFAULT_MODELS = [os.environ.get("METAMAPY_SPACY_MODEL", "en_core_sci_sm"),
                   "en_core_web_sm"]
_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        last_err = None
        for name in _DEFAULT_MODELS:
            try:
                _nlp = spacy.load(name, disable=["ner", "lemmatizer"])
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
        if _nlp is None:
            raise RuntimeError(
                f"No spaCy model available (tried {_DEFAULT_MODELS}): {last_err}")
    return _nlp


def _segment_spans(text: str, method: str) -> List[Tuple[int, int]]:
    spans = []
    if method == "lines":
        pos = 0
        for line in text.splitlines(keepends=True):
            stripped = line.rstrip("\n\r")
            if stripped.strip():
                spans.append((pos, pos + len(stripped)))
            pos += len(line)
    elif method == "blanklines":
        pos = 0
        for block in text.split("\n\n"):
            if block.strip():
                start = pos + (len(block) - len(block.lstrip()))
                spans.append((start, start + len(block.strip())))
            pos += len(block) + 2
    return spans


def _assign_pos(tokens: List[Token], spacy_doc, base: int) -> None:
    """Attach Penn POS tags (token.tag_) to mm word tokens by span containment."""
    intervals = [(base + t.idx, base + t.idx + len(t.text), t.tag_) for t in spacy_doc]
    for tok in tokens:
        if not tok.is_alphanumeric:
            continue
        for s, e, tag in intervals:
            if s <= tok.span.start < e:
                tok.pos = tag
                break


def analyze(text: str, method: str = "sentences") -> List[Sentence]:
    """Segment + POS-tag. Returns Sentences with mm tokens carrying Penn POS tags."""
    nlp = get_nlp()
    sentences: List[Sentence] = []

    if method == "sentences":
        doc = nlp(text)
        for i, sent in enumerate(doc.sents):
            lo, hi = sent.start_char, sent.end_char
            toks = analyze_text(text[lo:hi], lo)
            _assign_pos(toks, doc, 0)          # whole-doc tokens are doc-relative
            sentences.append(Sentence(text=text[lo:hi], span=Span(lo, hi), tokens=toks))
    else:
        for lo, hi in _segment_spans(text, method):
            seg = text[lo:hi]
            doc = nlp(seg)
            toks = analyze_text(seg, lo)
            _assign_pos(toks, doc, lo)
            sentences.append(Sentence(text=seg, span=Span(lo, hi), tokens=toks))
    return sentences

"""Sentence / text segmentation.

Modes (parity with MetaMapLite's segmentation.method):
  - sentences  : scispaCy sentence segmenter
  - blanklines : split on blank lines
  - lines      : one segment per line

Must preserve exact character offsets back into the original document text.
"""

from __future__ import annotations

from typing import List

from metamapy.model import Sentence


def segment(text: str, method: str = "sentences") -> List[Sentence]:
    raise NotImplementedError("segmentation pending (scispaCy backbone).")

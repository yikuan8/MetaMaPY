# MMI Output Format — Decoded Spec

Authoritative decode of MetaMapLite's MMI output, from:
- `MMI.java` → `renderEntityList(PrintWriter, ...)` (the **live** path: MetaMapLite
  calls `entityListFormatter(pw, list)` → this method)
- `mmi/Ranking.java` (score), `mmi/AATF.java`, `lite/types/PositionImpl.java`

## Line shape (10 fields, **trailing pipe**, then newline)

```
docid|MMI|score|concept|cui|semantictypes|triggerinfo|fields|posinfo|treecodes|
```

Built per **document**, with one line per CUI (evidence aggregated across the
document by CUI), sorted by `negNRank` ascending (i.e. best score first).

| # | Field | Value / format |
|---|---|---|
| 1 | docid | document id |
| 2 | `MMI` | literal |
| 3 | score | `NumberFormat`, exactly **2 decimals**, no grouping; `= -10000 * negNRank` (see below) |
| 4 | concept | preferred name |
| 5 | cui | CUI |
| 6 | semantictypes | Java `List.toString()` → `[dsyn, neop]` — **brackets, `", "` (comma-space) separator** |
| 7 | triggerinfo | trigger strings joined by `,` |
| 8 | fields | distinct field labels joined by `;` (free text → `text`) |
| 9 | posinfo | per-trigger position groups joined by `;` |
| 10 | treecodes | MeSH tree codes joined by `;` (empty if none) |

> Note: the live (Tuple-based) path emits the field label `text` for free text,
> **not** `tx`/`ti`/`ab` (those appear only in the deprecated methods and the
> class Javadoc).

## Trigger info (field 7) — `renderTupleInfo`

```
"concept_string"-field-nsent-"matched_text"-lexical_category-neg
```
- `concept_string` — the matched UMLS string (quoted)
- `field` — `text` for free text
- `nsent` — sentence number within the field
- `matched_text` — actual text matched (quoted)
- `lexical_category` — head lexical category (POS); may be empty
- `neg` — `1` if negated else `0`

Example: `"Heart"-text-1-"heart"-noun-0`

## Position info (field 9) — `renderPositionInfo`

Each position is `start/length` (`PositionImpl.toStringStartLength()` =
`start + "/" + (end-start)`). Within one trigger, positions join by `,`;
across triggers, groups join by `;`.

## Score (field 3) — the MMI ranking, ported in `mmi/ranking.py`

`score = -10000 * negNRank`, where `negNRank = -normalizedRank`, so
`score = 10000 * normalizedRank`. With the default constants:

```
nmm=-10, nm=0, nf=-5, nz=0, nc=nw=0          (normalization indices)
wmm=1,  wm=14, ww=0,  wc=0,  wd=1            (weights)
maxFreq=1000, MMI_TREE_DEPTH_SPECIFICITY_DIVISOR=8
```

Because `ww=wc=0`, **word-count and character-count specificities do not affect
the score** — only the MetaMap mapping score and MeSH tree depth do:

```
mmSpec   = averageValue / 1000           # averageValue = mapping score (0..1000) of FIRST ev for the CUI
nmmSpec  = normalizeValue(-10, mmSpec)
mValue   = max(1, sum(tree_depths))      # tree depth = #dot-separated fields of each treecode
nmSpec   = normalizeValue(0, mValue/8) = mValue/8
spec     = (1*nmmSpec + 14*nmSpec) / 15
freq     = frequencyCount / 1000
nFreq    = normalizeValue(-5, freq)
rank     = spec               if titleFlag else nFreq * spec
score    = 10000 * normalizeValue(0, rank) = 10000 * rank
```

`normalizeValue(n, value)` (logistic-style remap):
```
n == 0 : value
n  > 0 : (e^n+1)/(e^n-1) * (1 - e^c)/(1 + e^c),  c = -n*clamp01(value)
n  < 0 : ln( (a + b*v1)/(a - b*v1) ) / m,  m=-n, a=e^m+1, b=e^m-1, v1=clamp01(value)
```

## Aggregation quirks to preserve (parity)
- **averageValue is the FIRST ev's score** for a CUI, not a true average:
  later occurrences only add a tuple and increment `frequencyCount`.
- `frequencyCount` = number of evidence items for that CUI in the document.
- Lines are de-duplicated by the surrounding `LinkedHashSet` logic; ordering is
  by `AATF.compareTo` (negNRank ascending, then by other fields).

## Still to confirm against real output (once indexes are built)
- Exact `NumberFormat` locale behavior (decimal point vs comma) — assume `.`.
- Treecode index field layout (`fields[1]` of `meshTcRelaxed` hits).
- Whether any empty-field edge cases differ.

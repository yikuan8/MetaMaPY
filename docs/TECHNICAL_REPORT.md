# MetaMaPy — Technical Report

How MetaMaPy is implemented, and how it differs from NLM's MetaMap and
MetaMapLite. For installation and usage, see the [README](../README.md).

---

## 1. Motivation

MetaMap and MetaMapLite map free biomedical text to UMLS Metathesaurus concepts.
MetaMap (Prolog) is being discontinued, and even MetaMapLite's runtime artifacts
(NLM-hosted Maven dependencies, prebuilt data, the LVG tool) are no longer
reliably available. MetaMaPy is a from-source Python re-implementation built so
the pipeline runs on modern infrastructure and exposes its internals (a full
candidate lattice) for downstream extension.

It targets **MetaMapLite's** algorithm (fast dictionary longest-match), not full
MetaMap's Prolog parser + WSD.

## 2. Pipeline

```
text
 └─ sentence segmentation (scispaCy)
     └─ POS tagging (scispaCy)            ─┐ tags attach to mm tokens by offset
     └─ mm-regime tokenization            ─┘ (mm tokenizer owns the offsets)
         └─ longest-match candidate lookup (UMLS LMDB indexes)
             └─ 4-component scoring (+ inflectional variation)
                 └─ overlap resolution (longest-match, unless --overlapping)
                     └─ abbreviation linking (Schwartz-Hearst)
                         └─ NegEx negation
                             └─ semantic-type / source restriction
                                 └─ output:  MMI  |  JSON (candidate lattice)
```

Each stage is a pure function over a small data model (`src/metamapy/model.py`):
`Document → Sentence → Token`, and `Entity` holding an N-best list of `Ev`
(evidence) with character `Span`s. **Nothing collapses to a single answer until
output** — the candidate lattice survives into JSON for downstream use.

## 3. Components and how they were built

Every component is a faithful port of the corresponding MetaMapLite Java source,
ported by reading the source directly (the original runs on UMLS 2026AA here).

| Stage | Module | Ported from |
| --- | --- | --- |
| mm tokenization | `stages/tokenization.py` | `prefix/Tokenize.java`, `Scanner.java`, `CharUtils.java` |
| Normalization | `stages/normalization.py` | `lite/Normalization.java`, `NLSStrings.java`, `MetamapTokenization.java` |
| Candidate lookup | `stages/lookup.py` | `lite/EntityLookup5.java`, `FindLongestMatch.java`, `TokenListUtils.java` |
| Scoring | `stages/scoring.py` | `evaluation/Scoring.java` |
| MMI ranking | `mmi/ranking.py` | `mmi/Ranking.java`, `AATF.java` |
| MMI output | `output/mmi.py` | `resultformats/mmi/MMI.java` |
| Negation | `stages/negation.py`, `stages/negex_triggers.py` | `lite/NegEx.java`, `NegExKeyMap.java` |
| Abbreviations | `stages/abbreviations.py` | `lite/MarkAbbreviations.java` (Schwartz-Hearst) |
| Excluded terms | `stages/special_terms.py` | `lite/SpecialTerms.java` |
| Index build | `index/build*.py` | `dfbuilder/CreateIndexes.java`, `ExtractMrconsoSources.java`, `ExtractTreecodes.java` |

### 3.1 Tokenization (parity-critical)
MMI position offsets must match the input exactly, so the lookup tokenizer is a
direct port of MetaMapLite's "mm" regime (`mmTokenize` in KEEP_WHITE_SPACE mode):
words are maximal runs, each punctuation char is its own token, whitespace is
kept, and offsets are assigned cumulatively. spaCy's tokenizer is **not** used
for offsets (only for POS); spaCy POS tags are attached to mm tokens by span
containment.

### 3.2 Normalization
`normalize_lookup` ports `normalizeUtf8AsciiString`: strip a leading
`[X]`/`[V]`/… parenthetical, lowercase, strip possessives (no hyphen removal).
This is used both to **build** the `cuisourceinfo` keys and to **query** them, so
case/possessive variants match.

### 3.3 Indexes (LMDB)
Built from the installed UMLS RRF, mirroring MetaMapLite's tables:

| Sub-DB | Key → value | Source |
| --- | --- | --- |
| `cuisourceinfo` | `normalize_lookup(STR)` → `cui\|sui\|str\|sab\|tty` (dupsort) | MRCONSO (ENG, non-suppressed) |
| `cuiconcept` | `cui` → preferred name | MRCONSO |
| `cuist` | `cui` → semantic-type abbreviations | MRSTY + SRDEF (TUI→abbrev) |
| `meshtc` | `normalize_lookup(MeSH term)` → tree code(s) | MRCONSO (MSH) + MRSAT (ATN=MN) |
| `vars` | inflected word → distance 1 | SPECIALIST LRAGR |

### 3.4 Lookup
For each sentence, generate all contiguous token sublists (longest-first per
start); a sublist is considered if its first token's POS is allowed and the
joined text begins alphabetic / ends alphanumeric / length > 2. The term is
looked up (original **and** normalized) in `cuisourceinfo`; matches become `Ev`s
grouped by span into an `Entity`. Longest-match drops subsumed spans unless
`--overlapping`.

### 3.5 Scoring
`score = 1000 × (centrality + variation + 2×(coverage + cohesiveness)) / 6`,
ported with MetaMapLite's exact integer arithmetic (so the classic 1000 / 833 /
666 values reproduce). Per `Scoring.java`, coverage and cohesiveness reduce to
1.0, so the mapping score is driven by **centrality** (does the match cover the
phrase head) and **variation** (per-token inflection distance via `vars`).

### 3.6 MMI ranking
`mmi/ranking.py` ports `Ranking.java`: the displayed MMI score is
`-10000 × negNRank`, where rank combines the mapping score, MeSH **tree-depth
specificity** (weight 14 — dominant), and term frequency. MeSH concepts without a
tree number get the `x.x.x.x` placeholder (depth 4), matching MetaMapLite.

### 3.7 Negation
`negex_triggers.py` contains all 261 triggers extracted verbatim from
`NegExKeyMap.java` (pre/post/pseudo/conjunction). `negation.py` ports the marking
algorithm: trigger phrases within a 6-token window negate an entity unless a
conjunction breaks the scope; pseudo-negations shadow real triggers via
longest-phrase keeping.

### 3.8 Abbreviations
Schwartz-Hearst `long form (SHORT)` detection; every occurrence of a detected
short form is linked to the long form's UMLS concepts.

## 4. Differences from MetaMap / MetaMapLite

### 4.1 vs MetaMapLite (the target)

**Faithful (ported from source):** tokenization & offsets, normalization, index
schema & contents, longest-match lookup, the 4-component score (exact integer
math), MMI ranking & line format, NegEx (full trigger set), abbreviation
detection, excluded-terms mechanism, suppressible filtering.

**Substituted / approximated:**

| Area | MetaMapLite | MetaMaPy |
| --- | --- | --- |
| Sentence split / POS | OpenNLP models | scispaCy (`en_core_sci_sm`) |
| Index store | custom memory-mapped inverted files (IRUtils) | LMDB |
| Variants | full **LVG** (spelling + inflectional + derivational) | **inflectional only**, from SPECIALIST LRAGR |
| Excluded terms list | NLM `specialterms.txt` (data package) | small bundled starter list (customizable) |
| Phrase chunking | optional OpenNLP chunker | none (lookup over whole sentence) |

**Consequences of the approximations:**
- *Different NLP models* → occasional differences in sentence boundaries / POS
  tags, which can change what gets filtered. Not a correctness issue, a model
  difference.
- *No chunker* → the phrase "head" is the sentence head, so only one match per
  sentence gets `centrality = 1` (others score 833 instead of 1000). This barely
  affects MMI ranking (MeSH tree depth dominates) but does change raw mapping
  scores. Concept *finding* is unaffected.
- *Inflectional-only variants* → the `variation` score component is faithful for
  plurals/verb forms but not for derivational/spelling variants. Because variants
  feed **only** the variation score (not matching), the practical impact is small.

### 4.2 vs full MetaMap (Prolog)

MetaMaPy deliberately does **not** implement MetaMap's heaviest machinery:
- the Prolog **minimal-commitment syntactic parser** (replaced by sentence-level
  POS filtering),
- **word-sense disambiguation** (out of scope),
- the full variant/derivation flow and multiple mapping-assembly heuristics.

It keeps MetaMap's *scoring spirit* (the 4-component formula) and, unlike
MetaMapLite, preserves an **N-best candidate lattice** end-to-end rather than
collapsing to longest-match top-1.

### 4.3 Additions / design choices not in either tool
- **JSON output** carrying the full candidate lattice with score components,
  sources, offsets, and negation — for downstream use.
- **Extension seams** (`Pipeline.refine_candidates`, `Pipeline.refine_mappings`)
  — identity by default; let a downstream consumer filter/re-rank entities.
- LMDB-backed indexes and a small, dependency-light footprint.

## 5. Known limitations

- **Not byte-validated against real MetaMapLite.** Its runtime is unavailable
  (discontinuation), so MMI parity is verified by source reading + manual
  spot-checks, not a line-by-line diff.
- **Derivational/spelling variants absent** (no LVG). Inflectional only.
- **No section/field awareness** — clinical-note section headers aren't parsed;
  the MMI `location` field is always `text`.
- **Centrality without chunking** changes raw mapping scores (see 4.1).
- **scispaCy required** for sentence/POS; results depend on the chosen model.

## 6. Data provenance

- UMLS Metathesaurus 2026AA — Active Subset, installed via MetamorphoSys (UTS license required).
- Semantic Network `SRDEF` — semantic-type abbreviations.
- SPECIALIST Lexicon `LRAGR` — inflectional variants (free, open NLM download).

All derived indexes contain licensed UMLS content and are **not** redistributable.

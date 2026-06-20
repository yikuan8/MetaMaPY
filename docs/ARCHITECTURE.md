# MetaMaPy Architecture

## Design stance: "in between" MetaMap and MetaMapLite

| Stage | Full MetaMap | MetaMapLite | **MetaMaPy** |
| --- | --- | --- | --- |
| Sentence split | text_objects.pl | OpenNLP | scispaCy |
| Tokenization | C "mm" regime | Tokenize.java | **port mm regime** (parity-critical) |
| POS tagging | NLS Tagger server | OpenNLP | scispaCy |
| Phrase boundaries | Prolog parser | optional chunker | **none** (POS-filtered sentence lookup) |
| Abbreviation | AA detection | Schwartz-Hearst | Schwartz-Hearst |
| Variants | full SPECIALIST | precomputed | inflectional + spelling (LRAGR) |
| Candidate lookup | Berkeley DB | inverted file | **LMDB longest-match** |
| Scoring | 4-component | 4-component | **4-component (exact)** |
| Mapping assembly | N-best combos | longest-match | **bounded N-best lattice** |
| WSD | WSD server | none | **out of scope** (extension point) |
| Negation | negex.pl | NegEx | NegEx |
| Output | many | MMI/BioC/brat/json | **MMI + JSON only** |

The single hard rule: **do not collapse to top-1 early.** The candidate lattice
(N-best `Ev` per `Entity`, with the four score components and offsets) survives
to the JSON output for downstream use.

## Pipeline

```
segment -> tokenize -> POS -> abbreviations
        -> candidate lookup -> score + assemble lattice
        -> [refine_candidates]    (no-op extension hook)
        -> negation -> restrict(sts/sources) -> resolve overlap
        -> [refine_mappings]      (no-op extension hook)
        -> MMI | JSON
```

## Extension seams

`Pipeline.refine_candidates` and `Pipeline.refine_mappings` are identity
functions by default — extension points where a downstream consumer can filter or
re-rank entities without changing the core. Each receives entities with full
context: sentence, span, and competing concepts with names/semtypes/sources/scores.

## Build status

1. ✅ **Data** — UMLS 2026AA installed via MetamorphoSys; `metamapy.index.build`
   produces `cuiconcept` / `cuist` / `cuisourceinfo` (suppressible-filtered);
   `metamapy.index.build_meshtc` adds the `meshtc` tree-code index. (docs/DATA_SETUP.md)
2. ✅ **MMI format spec** — decoded from MMI.java into docs/MMI_FORMAT.md.
3. ✅ **Front end** — scispaCy sentence segmentation + POS; mm tokenizer owns offsets.
4. ✅ **Normalization + lookup** — longest-match candidate generation.
5. ✅ **Scoring + restriction + NegEx negation + excluded terms + abbreviations**.
6. ✅ **Output** — MMI (MeSH-weighted scores) + JSON (candidate lattice).
7. ⬜ **Extension seams** — no-op `refine_*` hooks for downstream customization.

## Variants (partial)

The `vars` index is built from the SPECIALIST Lexicon **LRAGR** file
(`metamapy.index.build_vars`) — 153k single-word **inflectional** variants
(plurals, verb forms) at distance 1, feeding `store.lookup_variant` →
`Scoring.computeVariation`. LRAGR is a free, open NLM download (no UTS login):
`https://data.lhncbc.nlm.nih.gov/public/lsg/lexicon/2026/release/LEX_DOC/LRAGR`.

Not covered: **derivational / spelling** variants, which MetaMapLite gets from
the full **LVG** tool. LVG (`lvg2026.tgz`, also a free LSG download) could be run
for full parity, but variants affect only the `variation` *score* (integer 0/1,
weighted 1-of-6, then dominated by MeSH tree depth in MMI ranking) — not matching
or recall — so the marginal benefit is small.

## Validation note

A line-by-line oracle (running real MetaMapLite) is **not attainable** — its
runtime dependencies (NLM Maven artifacts, prebuilt data) are gone. Validation
relies on faithful source ports + manual spot-checks on clinical text.

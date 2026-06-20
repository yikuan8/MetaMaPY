# Data Setup (UMLS 2026AA)

MetaMaPy needs UMLS data installed and converted to local LMDB indexes. The data
is licensed (UTS) and is **not** part of this repo.

## 1. Source download (done)

`umls-2026AA-full.zip` (5.3 GB) downloaded to `/projects/yli94/`.
It contains: Metathesaurus (`META/`), SPECIALIST Lexicon (`LEX/`), Semantic
Network (`NET/`), Lexical Tools, and the MetamorphoSys installer.

> Rotate the UTS API key that was used to download — it was exposed in chat.

## 2. Install with MetamorphoSys

Unzip, then run MetamorphoSys to assemble the Metathesaurus into RRF:

```bash
cd /projects/yli94
unzip umls-2026AA-full.zip
cd 2026AA            # release folder
./mmsys.sh           # or run64.sh — select "Install UMLS", Metathesaurus only
```

With a full license, **install all source vocabularies** (matches MetaMap's
default coverage). Output is an RRF directory: `MRCONSO.RRF`, `MRSTY.RRF`,
`MRSAT.RRF`, `MRDEF.RRF`, ... (~1–2 h, ~40 GB).

## 3. Build MetaMaPy indexes

```bash
python -m metamapy.index.build \
    --meta /projects/yli94/2026AA/META \
    --lex  /projects/yli94/2026AA/LEX \
    --out  /projects/yli94/metamapy-indexes
export MML_INDEXDIR=/projects/yli94/metamapy-indexes
```

Produces LMDB stores: `cuisourceinfo`, `cuiconcept`, `cuist`, `meshtcrelaxed`,
`vars`, `defs` (see `src/metamapy/index/build.py`).

## RRF → index mapping

| RRF file | Columns used | Feeds |
| --- | --- | --- |
| MRCONSO.RRF | CUI, SUI, STR, SAB, TTY, ISPREF/TS | cuisourceinfo, cuiconcept |
| MRSTY.RRF | CUI, STY/TUI | cuist |
| MRSAT.RRF | CUI, ATN=MN (tree numbers) | meshtcrelaxed |
| MRDEF.RRF | CUI, DEF | defs (concept definitions) |
| LEX/LRAGR | base/inflection forms | vars |
| NET/SRDEF | semantic type ↔ group | restriction group expansion |

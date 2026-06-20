# MetaMaPy

A Python re-implementation of NLM's **MetaMapLite** for mapping free biomedical
and clinical text to **UMLS Metathesaurus** concepts. It reads plain text (e.g.
a discharge summary), finds UMLS concepts, and emits **MMI** (pipe-delimited) or
**JSON**.

The JSON output preserves the full candidate lattice — all competing concepts
per mention, with scores and character offsets — for downstream use.

> For *how it works* and *how it differs* from the original MetaMap/MetaMapLite,
> see [docs/TECHNICAL_REPORT.md](docs/TECHNICAL_REPORT.md).

## Features

- Longest-match dictionary lookup over the UMLS Metathesaurus
- MetaMap 4-component scoring (centrality, variation, coverage, cohesiveness)
- MMI ranking with MeSH tree-depth specificity
- NegEx negation detection (e.g. "no evidence of …", "denies …")
- Schwartz-Hearst abbreviation detection and linking (e.g. `… (COPD)` → later `COPD`)
- Semantic-type / source restriction
- Excluded-terms and suppressible-term filtering
- scispaCy sentence segmentation + POS tagging; parity-exact character offsets
- Output: **MMI** and **JSON** (with full candidate lattice)

## Requirements

- **Python 3.10 or 3.11** (scispaCy does not support 3.13)
- A **UMLS license** (free [UTS account](https://uts.nlm.nih.gov/)) to download the Metathesaurus
- Disk: ~40 GB for the installed UMLS RRF, ~3 GB for the built indexes

## Installation

```bash
# 1. Create an isolated environment
conda create -n metamapy python=3.11 -y
conda activate metamapy

# 2. Install MetaMaPy
git clone https://github.com/yikuan8/MetaMaPy.git
cd MetaMaPy
pip install -e .

# 3. Install the scispaCy biomedical model
pip install scispacy
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz
```

## Data setup (one-time)

MetaMaPy needs the UMLS Metathesaurus converted into local LMDB indexes. Full
walkthrough in [docs/DATA_SETUP.md](docs/DATA_SETUP.md); summary:

```bash
# A. Download & install UMLS via MetamorphoSys -> an RRF directory ($META).
#    (see docs/DATA_SETUP.md for the headless MetamorphoSys steps)

# B. Build the indexes
META=/path/to/UMLS/META            # contains MRCONSO.RRF, MRSTY.RRF, MRSAT.RRF
SRDEF=/path/to/SRDEF               # Semantic Network definitions (TUI->abbrev)
INDEX=/path/to/metamapy-indexes

python -m metamapy.index.build         --meta "$META" --srdef "$SRDEF" --out "$INDEX"
python -m metamapy.index.build_meshtc  --meta "$META" --out "$INDEX"     # MMI tree-code scores

# C. (optional) inflectional variants from the free SPECIALIST LRAGR file
python -m metamapy.index.build_vars    --lragr /path/to/LRAGR --out "$INDEX"

export MML_INDEXDIR="$INDEX"
```

## Usage

```bash
metamapy [options] INPUT...          # installed console script
python -m metamapy [options] INPUT...

# INPUT = one or more text files, or - for stdin
```

| Option | Description | Default |
| --- | --- | --- |
| `--output-format {mmi,json}` | Output format | `mmi` |
| `-o, --output PATH` | Write to file instead of stdout | stdout |
| `--restrict-to-sts LIST` | Keep only these semantic types (e.g. `dsyn,sosy`) | all |
| `--restrict-to-sources LIST` | Keep only these vocabularies (e.g. `SNOMEDCT_US,MSH`) | all |
| `--segmentation {sentences,blanklines,lines}` | How text is split | `sentences` |
| `--overlapping` | Allow overlapping concepts (vs longest-match only) | off |
| `--no-negation` | Disable NegEx negation detection | on |
| `--index-dir PATH` | Index directory | `$MML_INDEXDIR` |
| `-v` / `--silent` | Verbosity | normal |
| `--version`, `--help` | — | — |

### Examples

```bash
# MMI output for a clinical note
metamapy note.txt --index-dir "$INDEX"

# Only diagnoses, symptoms, and drugs; JSON with the full candidate lattice
metamapy note.txt --restrict-to-sts dsyn,sosy,phsu --output-format json -o out.json

# From stdin
echo "No evidence of pulmonary embolism." | metamapy - --restrict-to-sts dsyn
```

See [examples/test.txt](examples/test.txt) → [examples/test.mmi](examples/test.mmi)
for a full discharge-summary run.

### Environment variables

| Variable | Purpose |
| --- | --- |
| `MML_INDEXDIR` | Default index directory |
| `METAMAPY_SPACY_MODEL` | spaCy model (default `en_core_sci_sm`) |
| `METAMAPY_EXCLUDED_TERMS` | Path to a custom excluded-terms file |

## Output formats

**MMI** — one pipe-delimited line per concept (MetaMapLite-compatible):
```
id|MMI|score|preferred_name|cui|[semtypes]|trigger_info|location|posinfo|treecodes|
```

**JSON** — per document, each entity keeps its **N-best evidence** (competing
concepts) with CUI, preferred name, semantic types, sources, character offsets,
the four score components, and negation flag. Field reference:
[docs/MMI_FORMAT.md](docs/MMI_FORMAT.md).

## Citing MetaMaPy

If you use MetaMaPy in your research, please cite it. GitHub shows a
"Cite this repository" button generated from [CITATION.cff](CITATION.cff).

```bibtex
@software{li_metamapy,
  author  = {Li, Yikuan},
  title   = {{MetaMaPy: A Python re-implementation of MetaMapLite for UMLS concept extraction}},
  year    = {2026},
  url      = {https://github.com/yikuan8/MetaMaPy},
  version = {0.1.0}
}
```

Once a Zenodo DOI is minted (see below), cite the DOI instead.

## License & data

The MetaMaPy code is released under the MIT License (see [LICENSE](LICENSE)).
**UMLS data is not included and is not redistributable** — you must obtain it
under your own UMLS license.

## Documentation

- [docs/TECHNICAL_REPORT.md](docs/TECHNICAL_REPORT.md) — implementation & differences from MetaMap/MetaMapLite
- [docs/DATA_SETUP.md](docs/DATA_SETUP.md) — UMLS install & index build
- [docs/MMI_FORMAT.md](docs/MMI_FORMAT.md) — MMI output field reference
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — design notes & build status

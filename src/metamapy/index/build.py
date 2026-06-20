"""Build MetaMaPy's LMDB lookup indexes from installed UMLS RRF files.

Replicates the tables MetaMapLite's CreateIndexes builds (cuiconcept,
cuisourceinfo, cuist), stored as LMDB sub-databases:

  cuiconcept    : cui            -> preferred_name            (1:1)
  cuist         : cui            -> "abbr1,abbr2,..."         (semantic-type abbrevs)
  cuisourceinfo : normalize_lookup(STR) -> {"cui|sui|str|sab|tty", ...}  (DUPSORT)

Design notes (see docs/ARCHITECTURE.md):
  * cuisourceinfo is keyed on normalize_lookup(STR) (= normalizeUtf8AsciiString),
    the same normalizer EntityLookup applies to query terms, so case/possessive
    variants match. Only LAT=ENG rows are indexed (English NER).
  * Semantic types are stored as SRDEF abbreviations (e.g. "dsyn") to match the
    MMI [semtype] field; TUI->abbr comes from the Semantic Network SRDEF file.
  * Treecodes (meshtcrelaxed) and variants (vars) are built by separate passes
    later — they only refine MMI score / variation, not basic matching.

CLI:
  python -m metamapy.index.build --meta <META_DIR> --srdef <SRDEF> --out <OUT_DIR>
"""

from __future__ import annotations

import argparse
import os
import sys

import lmdb

from metamapy.stages.normalization import normalize_lookup

# MRCONSO columns (RRF)
C_CUI, C_LAT, C_TS, C_STT, C_SUI, C_ISPREF, C_SAB, C_TTY, C_STR = 0, 1, 2, 4, 5, 6, 11, 12, 14
C_SUPPRESS = 16   # SUPPRESS flag: O/E/Y suppressible, N = keep
# MRSTY columns
S_CUI, S_TUI = 0, 1

MAP_SIZE = 24 * 1024 ** 3      # 24 GiB sparse cap
COMMIT_EVERY = 200_000
# LMDB dupsort caps each key AND value at ~511 bytes; stay safely under it.
# Over-long UMLS strings can't match a real text span anyway (token-span capped).
MAX_DUP_BYTES = 480


def load_tui_to_abbr(srdef_path: str) -> dict:
    """Parse SRDEF 'STY' rows: TUI (col 1) -> abbreviation (col 8)."""
    mapping = {}
    with open(srdef_path, "r", encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) > 8 and f[0] == "STY":
                mapping[f[1]] = f[8]
    return mapping


def build_cuist(env, mrsty_path: str, tui_to_abbr: dict) -> None:
    """cui -> comma-joined semantic-type abbreviations (MRSTY is sorted by CUI)."""
    db = env.open_db(b"cuist")
    n = 0
    with env.begin(write=True, db=db) as txn:
        cur_cui = None
        abbrs = []
        with open(mrsty_path, "r", encoding="utf-8") as fh:
            for line in fh:
                f = line.split("|")
                cui, tui = f[S_CUI], f[S_TUI]
                if cui != cur_cui:
                    if cur_cui is not None and abbrs:
                        txn.put(cur_cui.encode(), ",".join(abbrs).encode())
                    cur_cui = cui
                    abbrs = []
                abbr = tui_to_abbr.get(tui, tui)
                if abbr not in abbrs:
                    abbrs.append(abbr)
                n += 1
        if cur_cui is not None and abbrs:
            txn.put(cur_cui.encode(), ",".join(abbrs).encode())
    print(f"  cuist: processed {n} MRSTY rows", file=sys.stderr)


def _is_preferred(f) -> bool:
    return (f[C_LAT] == "ENG" and f[C_TS] == "P" and f[C_STT] == "PF"
            and f[C_ISPREF] == "Y")


def build_concept_and_sourceinfo(env, mrconso_path: str) -> None:
    """cuiconcept (preferred names) + cuisourceinfo (normalized-key DUPSORT)."""
    cuiconcept = env.open_db(b"cuiconcept")
    cuisourceinfo = env.open_db(b"cuisourceinfo", dupsort=True)

    n = 0
    written_pref = 0
    written_src = 0
    skipped_long = 0
    txn = env.begin(write=True)
    try:
        cur_cui = None
        best_name = None        # preferred-flagged name
        fallback_name = None     # first ENG name seen
        for line in open(mrconso_path, "r", encoding="utf-8"):
            f = line.rstrip("\n").split("|")
            if len(f) <= C_STR:
                continue
            cui = f[C_CUI]
            if cui != cur_cui:
                if cur_cui is not None:
                    name = best_name or fallback_name
                    if name:
                        txn.put(cur_cui.encode(), name.encode(), db=cuiconcept)
                        written_pref += 1
                cur_cui = cui
                best_name = None
                fallback_name = None

            suppress = f[C_SUPPRESS] if len(f) > C_SUPPRESS else "N"
            if f[C_LAT] == "ENG" and suppress == "N":
                strv = f[C_STR]
                if fallback_name is None:
                    fallback_name = strv
                if best_name is None and _is_preferred(f):
                    best_name = strv
                key = normalize_lookup(strv)
                if key:
                    rec = "|".join([cui, f[C_SUI], strv, f[C_SAB], f[C_TTY]])
                    key_b = key.encode()
                    rec_b = rec.encode()
                    if len(key_b) <= MAX_DUP_BYTES and len(rec_b) <= MAX_DUP_BYTES:
                        txn.put(key_b, rec_b, db=cuisourceinfo, dupdata=True)
                        written_src += 1
                    else:
                        skipped_long += 1

            n += 1
            if n % COMMIT_EVERY == 0:
                txn.commit()
                txn = env.begin(write=True)
                if n % 2_000_000 == 0:
                    print(f"  ...{n} MRCONSO rows", file=sys.stderr)

        if cur_cui is not None:
            name = best_name or fallback_name
            if name:
                txn.put(cur_cui.encode(), name.encode(), db=cuiconcept)
                written_pref += 1
        txn.commit()
    except BaseException:
        txn.abort()
        raise
    print(f"  cuiconcept: {written_pref} concepts; "
          f"cuisourceinfo: {written_src} ENG source rows "
          f"({skipped_long} over-long skipped) from {n} MRCONSO rows",
          file=sys.stderr)


def build(meta_dir: str, srdef_path: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    env = lmdb.open(out_dir, map_size=MAP_SIZE, max_dbs=8)
    try:
        print("Loading TUI->abbreviation map from SRDEF...", file=sys.stderr)
        tui_to_abbr = load_tui_to_abbr(srdef_path)
        print(f"  {len(tui_to_abbr)} semantic types", file=sys.stderr)

        print("Building cuist from MRSTY...", file=sys.stderr)
        build_cuist(env, os.path.join(meta_dir, "MRSTY.RRF"), tui_to_abbr)

        print("Building cuiconcept + cuisourceinfo from MRCONSO...", file=sys.stderr)
        build_concept_and_sourceinfo(env, os.path.join(meta_dir, "MRCONSO.RRF"))
        print("Done.", file=sys.stderr)
    finally:
        env.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="metamapy.index.build",
                                description="Build MetaMaPy LMDB indexes from UMLS RRF.")
    p.add_argument("--meta", required=True, help="UMLS META dir (with MRCONSO.RRF, MRSTY.RRF)")
    p.add_argument("--srdef", required=True, help="Semantic Network SRDEF file")
    p.add_argument("--out", required=True, help="Output LMDB directory")
    args = p.parse_args(argv)
    build(args.meta, args.srdef, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

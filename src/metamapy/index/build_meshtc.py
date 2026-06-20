"""Add the MeSH tree-code index (meshtc) to an existing MetaMaPy index.

Port of MetaMapLite's ExtractTreecodes:
  * MRSAT (ATN=MN): CUI -> list of MeSH tree codes (ATV).
  * MRCONSO (SAB=MSH): for each MeSH term, write term -> tree code(s), keyed by
    normalize_lookup(STR). MeSH concepts lacking a tree number get the
    'x.x.x.x' placeholder (yields depth 4), matching MetaMapLite.

Stored as a dupsort LMDB sub-db 'meshtc'. Looked up by concept preferred name
in the MMI formatter (store.treecodes).

CLI: python -m metamapy.index.build_meshtc --meta <META_DIR> --out <INDEX_DIR>
"""

from __future__ import annotations

import argparse
import os
import sys

import lmdb

from metamapy.stages.normalization import normalize_lookup

# MRSAT: CUI|LUI|SUI|METAUI|STYPE|CODE|ATUI|SATUI|ATN|SAB|ATV|SUPPRESS|CVF
A_CUI, A_ATN, A_ATV = 0, 8, 10
# MRCONSO columns used here
C_CUI, C_SAB, C_STR = 0, 11, 14

MAX_DUP_BYTES = 480
COMMIT_EVERY = 200_000


def build_meshtc(meta_dir: str, out_dir: str) -> None:
    cui2tc = {}
    with open(os.path.join(meta_dir, "MRSAT.RRF"), encoding="utf-8") as fh:
        for line in fh:
            f = line.split("|")
            if len(f) > A_ATV and f[A_ATN] == "MN":
                cui2tc.setdefault(f[A_CUI], []).append(f[A_ATV])
    print(f"  cui->treecode entries: {len(cui2tc)}", file=sys.stderr)

    env = lmdb.open(out_dir, map_size=24 * 1024 ** 3, max_dbs=8)
    db = env.open_db(b"meshtc", dupsort=True)
    n = written = 0
    txn = env.begin(write=True)
    try:
        with open(os.path.join(meta_dir, "MRCONSO.RRF"), encoding="utf-8") as fh:
            for line in fh:
                f = line.rstrip("\n").split("|")
                if len(f) <= C_STR or f[C_SAB] != "MSH":
                    continue
                key = normalize_lookup(f[C_STR])
                if not key:
                    continue
                tcs = cui2tc.get(f[C_CUI]) or ["x.x.x.x"]
                kb = key.encode()
                if len(kb) <= MAX_DUP_BYTES:
                    for tc in tcs:
                        tb = tc.encode()
                        if len(tb) <= MAX_DUP_BYTES:
                            txn.put(kb, tb, db=db, dupdata=True)
                            written += 1
                n += 1
                if n % COMMIT_EVERY == 0:
                    txn.commit()
                    txn = env.begin(write=True)
        txn.commit()
    except BaseException:
        txn.abort()
        raise
    finally:
        env.close()
    print(f"  meshtc: {written} (term,treecode) pairs from {n} MeSH MRCONSO rows",
          file=sys.stderr)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="metamapy.index.build_meshtc")
    p.add_argument("--meta", required=True, help="UMLS META dir (MRCONSO.RRF, MRSAT.RRF)")
    p.add_argument("--out", required=True, help="Existing MetaMaPy index dir to add meshtc to")
    a = p.parse_args(argv)
    build_meshtc(a.meta, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

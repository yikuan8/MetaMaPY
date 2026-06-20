"""Build the inflectional variant index (vars) from the SPECIALIST LRAGR file.

LRAGR row: EUI | inflected_form | category | inflection | base_form | citation
We index single-word inflected forms that differ from their base as variant
distance 1 (inflectional), excluding words that are themselves base forms (those
are distance 0 / exact). This feeds Scoring.computeVariation via
store.lookup_variant(word); unknown words default to 0 (exact), matching the
prior behavior.

This is the lightweight substitute for LVG (which is unavailable): inflectional
variants only, not LVG's full derivational/spelling set.

CLI: python -m metamapy.index.build_vars --lragr <LRAGR> --out <INDEX_DIR>
"""

from __future__ import annotations

import argparse
import sys

import lmdb

I_INFLECTED, I_BASE = 1, 4
MAP_SIZE = 24 * 1024 ** 3


def build_vars(lragr_path: str, out_dir: str) -> None:
    base_singles = set()
    infl_singles = set()
    rows = 0
    with open(lragr_path, "r", encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) <= I_BASE:
                continue
            rows += 1
            infl = f[I_INFLECTED].strip()
            base = f[I_BASE].strip()
            if base and " " not in base:
                base_singles.add(base.lower())
            if infl and " " not in infl and infl.lower() != base.lower():
                infl_singles.add(infl.lower())
    variants = infl_singles - base_singles
    print(f"  LRAGR rows: {rows}; single-word bases: {len(base_singles)}; "
          f"inflectional variants: {len(variants)}", file=sys.stderr)

    env = lmdb.open(out_dir, map_size=MAP_SIZE, max_dbs=8)
    db = env.open_db(b"vars")
    n = 0
    txn = env.begin(write=True)
    try:
        for word in variants:
            wb = word.encode()
            if len(wb) <= 480:
                txn.put(wb, b"1", db=db)
                n += 1
                if n % 200_000 == 0:
                    txn.commit()
                    txn = env.begin(write=True)
        txn.commit()
    except BaseException:
        txn.abort()
        raise
    finally:
        env.close()
    print(f"  vars: {n} inflectional variant words written", file=sys.stderr)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="metamapy.index.build_vars")
    p.add_argument("--lragr", required=True, help="SPECIALIST LRAGR file")
    p.add_argument("--out", required=True, help="Existing MetaMaPy index dir")
    a = p.parse_args(argv)
    build_vars(a.lragr, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

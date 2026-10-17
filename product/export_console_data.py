#!/usr/bin/env python3
"""
product/export_console_data.py
==============================
Export the two static data files the Explorer console reads at build time:

  terraq/explorer/data/deposits.json            <- data/ground_truth/mrds_*.csv  (GeoJSON)
  terraq/explorer/data/benchmark_console.json  <- outputs/benchmark_console.json

Both land INSIDE terraq/explorer/ so the console stays self-contained.

Honest note on the deposits layer: the ground-truth CSVs in this repo hold 11
USGS MRDS occurrences in/near the Clayton Valley validation area (7 Li, 4 V).
This is NOT a global deposit database — it is the validation reference set, and
the console labels it as such. The CSVs carry region, site, codes, status, lat,
lon, dep_id and url; there is no deposit-type or development-status column, so
the GeoJSON exposes only fields that genuinely exist.

Usage:  .venv/bin/python product/export_console_data.py
"""
from __future__ import annotations
import os, csv, json, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEST = os.path.join(ROOT, "terraq", "explorer", "data")

SOURCES = [("mrds_lithium.csv", "Li", "lithium"),
           ("mrds_vanadium.csv", "V", "vanadium")]


def build_geojson():
    feats = []
    for fname, code, commodity in SOURCES:
        path = os.path.join(ROOT, "data", "ground_truth", fname)
        if not os.path.isfile(path):
            continue
        for r in csv.DictReader(open(path)):
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point",
                             "coordinates": [float(r["lon"]), float(r["lat"])]},
                "properties": {
                    # Only fields that actually exist in the CSV.
                    "site": r["site"].strip().rstrip("."),
                    "commodity": commodity,
                    "code": code,
                    "mrds_status": (r.get("status") or "").strip() or None,
                    "region": (r.get("region") or "").strip() or None,
                    "dep_id": r.get("dep_id"),
                    "url": r.get("url"),
                },
            })
    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "USGS MRDS (Mineral Resources Data System)",
            "scope": ("Validation reference set for the Clayton Valley / Silver Peak "
                      "area only — not a global deposit database."),
            "count": len(feats),
            "generated_by": "product/export_console_data.py",
        },
        "features": feats,
    }


def main():
    os.makedirs(DEST, exist_ok=True)

    gj = build_geojson()
    # .json (not .geojson) so TypeScript's resolveJsonModule can import it directly.
    gj_path = os.path.join(DEST, "deposits.json")
    with open(gj_path, "w") as f:
        json.dump(gj, f, indent=1)
    print(f"wrote {gj_path}  ({gj['metadata']['count']} sites)")

    src = os.path.join(ROOT, "outputs", "benchmark_console.json")
    if os.path.isfile(src):
        dst = os.path.join(DEST, "benchmark_console.json")
        shutil.copyfile(src, dst)
        n = len(json.load(open(dst)).get("deposits", []))
        print(f"wrote {dst}  ({n} deposit rows)")
    else:
        print(f"! {src} missing — run product/benchmark_console.py first")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

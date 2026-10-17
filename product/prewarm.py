#!/usr/bin/env python3
"""
product/prewarm.py
==================
Fill the engine cache for every Explorer preset BEFORE a demo.

Why: a cold request streams Sentinel-2 COGs from S3 and takes ~1-3 minutes, and
`server.py` serializes runs behind a single lock — so a click during a cold
prewarm queues behind it. Run this well ahead of time, never during the demo.

It writes into exactly the same job directories the server would use (same
md5(lat,lon,km) cache key), so the server picks the results up with no change to
its caching logic.

A preset is re-run when it predates the overlay work (no `confidence.tif` or no
`overlays/` folder), so older caches are upgraded in place rather than orphaned.

Usage:
    .venv/bin/python product/prewarm.py            # fill what is missing
    .venv/bin/python product/prewarm.py --force    # re-run everything
"""
from __future__ import annotations
import os, sys, csv, json, time, hashlib, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

JOBS_DIR = os.path.join(ROOT, "outputs", "jobs")

# Must stay in sync with the presets in terraq/explorer/lib/presets.ts
PRESETS = [
    ("Silver Peak (Li)",   37.7499, -117.6342, 12),
    ("Clayton Valley",     37.7800, -117.6000, 15),
    ("Foote Lithium",      37.7585, -117.5912, 10),
    ("Silver Peak Ops",    37.7672, -117.5833, 10),
    ("Silver Peak Marsh",  37.7527, -117.6398, 10),
    ("Foote Mineral Co",   37.8468, -117.5412, 12),
    ("Mohawk Mine (V)",    37.7291, -117.8134, 10),
]


def job_key(lat, lon, km):
    """Identical to server.py's cache key."""
    return hashlib.md5(f"{lat:.4f}_{lon:.4f}_{float(km)}".encode()).hexdigest()[:10]


def load_deposits():
    pts = []
    for fn, comm in [("mrds_lithium.csv", "Li"), ("mrds_vanadium.csv", "V")]:
        p = os.path.join(ROOT, "data", "ground_truth", fn)
        if os.path.exists(p):
            for r in csv.DictReader(open(p)):
                pts.append((f"{comm}:{r['site'][:13]}", float(r["lat"]), float(r["lon"])))
    return pts


def is_complete(out):
    return (os.path.isfile(os.path.join(out, "result.json"))
            and os.path.isfile(os.path.join(out, "confidence.tif"))
            and os.path.isdir(os.path.join(out, "overlays")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-run even if cached")
    args = ap.parse_args()

    from sentinel_engine import run as engine_run
    deposits = load_deposits()
    os.makedirs(JOBS_DIR, exist_ok=True)

    todo = []
    for name, lat, lon, km in PRESETS:
        out = os.path.join(JOBS_DIR, job_key(lat, lon, km))
        (todo.append((name, lat, lon, km, out)) if args.force or not is_complete(out)
         else print(f"  ✓ {name:20s} already complete ({os.path.basename(out)})"))

    if not todo:
        print("\nAll presets already cached and complete.")
        return 0

    print(f"\n{len(todo)} preset(s) to run — serial, a few minutes each.\n")
    ok = fail = 0
    for i, (name, lat, lon, km, out) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {name}  ({lat},{lon}) {km}km -> {os.path.basename(out)}")
        t0 = time.time()
        try:
            engine_run(lat, lon, km, out, deposits_latlon=deposits)
            print(f"        done in {time.time()-t0:.0f}s\n")
            ok += 1
        except Exception as e:
            print(f"        FAILED: {e}\n")
            fail += 1

    print(f"Prewarm finished: {ok} ok, {fail} failed.")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

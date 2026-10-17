#!/usr/bin/env python3
"""
product/run_validation_aois.py
==============================
Run the engine over every AOI in validation_plan.py, SERIALLY.

Serial on purpose: product/server.py guards engine_run with a single lock
because the raster stack shares GDAL state. Running these in parallel would
either block anyway or corrupt a run. One at a time, each into its own folder
under outputs/validation_runs/ so the live demo cache in outputs/jobs/ is left
completely alone.

Usage:  .venv/bin/python product/run_validation_aois.py
"""
from __future__ import annotations
import os, sys, csv, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from validation_plan import CONTROLS, LITHIUM_AOIS, RADIUS_KM   # noqa: E402

OUT = os.path.join(ROOT, "outputs", "validation_runs")


def load_deposits():
    pts = []
    for fn, comm in [("mrds_lithium.csv", "Li"), ("mrds_vanadium.csv", "V")]:
        p = os.path.join(ROOT, "data", "ground_truth", fn)
        if os.path.exists(p):
            for r in csv.DictReader(open(p)):
                pts.append((f"{comm}:{r['site'][:13]}", float(r["lat"]), float(r["lon"])))
    return pts


def main():
    from sentinel_engine import run as engine_run
    os.makedirs(OUT, exist_ok=True)
    deposits = load_deposits()

    jobs = [("control", a) for a in CONTROLS] + [("lithium", a) for a in LITHIUM_AOIS]
    index, failures = [], 0

    for i, (group, a) in enumerate(jobs, 1):
        d = os.path.join(OUT, a["id"])
        done = os.path.isfile(os.path.join(d, "clay_ratio_raw.tif"))
        print(f"\n[{i}/{len(jobs)}] {a['id']} {a['name']}  ({a['lat']},{a['lon']})"
              f"{'  — already complete, skipping' if done else ''}")
        rec = dict(group=group, dir=d, **a)
        if not done:
            t0 = time.time()
            try:
                meta, _ = engine_run(a["lat"], a["lon"], RADIUS_KM, d,
                                     deposits_latlon=deposits)
                rec.update(ok=True, seconds=round(time.time() - t0, 1),
                           coverage=meta.get("coverage"),
                           tiles=len(meta.get("tiles_used", [])),
                           date_range=meta.get("date_range"))
                print(f"        done in {rec['seconds']}s  coverage "
                      f"{(meta.get('coverage') or 0)*100:.0f}%")
            except Exception as e:
                failures += 1
                rec.update(ok=False, error=str(e)[:200])
                print(f"        FAILED: {e}")
        else:
            try:
                m = json.load(open(os.path.join(d, "result.json")))
                rec.update(ok=True, coverage=m.get("coverage"),
                           tiles=len(m.get("tiles_used", [])),
                           date_range=m.get("date_range"))
            except Exception:
                rec.update(ok=True)
        index.append(rec)
        with open(os.path.join(OUT, "index.json"), "w") as f:
            json.dump(index, f, indent=1)

    print(f"\n{len(index) - failures}/{len(index)} AOIs complete, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

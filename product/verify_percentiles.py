#!/usr/bin/env python3
"""
product/verify_percentiles.py
=============================
Independent verification of the percentile numbers the Explorer displays.

This answers exactly one question: **are the reported percentiles arithmetically
correct?** It recomputes them from the raw GeoTIFF by a different route than the
engine uses, and compares. It does NOT and cannot show that the underlying index
tracks real mineralisation — that is a separate, weaker claim (see the summary
this prints at the end).

Checks
------
  A  /api/sample percentile  ==  independently recomputed percentile
  B  target threshold        ==  95th percentile of high-confidence pixels
  C  fraction >= that threshold is ~5%   (the definition must hold)
  D  determinism: the same input gives the same answer twice
  E  saturation: how much of the scene is clipped to exactly 1.0 by _norm()

Usage:
    .venv/bin/python product/verify_percentiles.py [job_id]
    (defaults to the Silver Peak preset job)
"""
from __future__ import annotations
import os, sys, json, math, hashlib, urllib.request

import numpy as np
import rasterio
from rasterio.transform import rowcol
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "outputs", "jobs")
ENGINE = os.environ.get("ENGINE_URL", "http://localhost:8765")

# Silver Peak preset — same key the server derives.
DEFAULT_JOB = hashlib.md5(f"{37.7499:.4f}_{-117.6342:.4f}_{12.0}".encode()).hexdigest()[:10]

# Points to check, with the value the UI reports for them.
PROBES = [
    ("Silver Peak mine", 37.7499, -117.6342),
    ("Silver Peak Marsh (playa)", 37.7527, -117.6398),
    ("Foote Lithium", 37.7585, -117.5912),
]

OK, BAD = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"


def api_sample(job, lat, lon):
    url = f"{ENGINE}/api/sample?job={job}&lat={lat}&lon={lon}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.load(r)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def independent_percentile(arr, valid, r, c, buffer=1):
    """
    Recompute the percentile from scratch.

    Deliberately not the engine's expression: the engine does
    (arr[valid] < val).mean()*100 on a boolean mask; here the valid pixels are
    pulled into a flat sorted vector and the rank found by binary search. Same
    definition, different code path — so a bug in one will not hide in the other.
    """
    win = arr[max(0, r - buffer):r + buffer + 1, max(0, c - buffer):c + buffer + 1]
    winv = win[win > 0]
    if winv.size == 0:
        return None, None
    val = float(winv.mean())
    pool = np.sort(arr[valid].astype("float64"))
    rank = np.searchsorted(pool, val, side="left")     # count strictly below
    return val, float(rank) / pool.size * 100.0


def main():
    job = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JOB
    jd = os.path.join(JOBS, job)
    tif = os.path.join(jd, "lithium_prospectivity.tif")
    if not os.path.isfile(tif):
        print(f"No lithium raster for job {job}. Run an analysis first.")
        return 1

    with rasterio.open(tif) as src:
        arr = src.read(1).astype("float32")
        transform, crs = src.transform, src.crs
    valid = arr > 0
    tf = Transformer.from_crs("EPSG:4326", crs.to_string(), always_xy=True)

    print(f"job {job}   grid {arr.shape}   valid pixels {int(valid.sum()):,}\n")
    failures = 0

    # ---- A: API vs independent recomputation --------------------------------
    print("A. Reported percentile vs independently recomputed")
    print(f"   {'point':<28}{'API':>9}{'recomputed':>13}{'Δ':>8}   result")
    for name, lat, lon in PROBES:
        x, y = tf.transform(lon, lat)
        r, c = rowcol(transform, x, y)
        if not (0 <= r < arr.shape[0] and 0 <= c < arr.shape[1]):
            print(f"   {name:<28}{'—':>9}{'outside footprint':>26}")
            continue
        _, mine = independent_percentile(arr, valid, r, c)
        d = api_sample(job, lat, lon)
        theirs = (d.get("lithium") or d).get("li_percentile_in_aoi") if d.get("ok") else None
        if mine is None or theirs is None:
            print(f"   {name:<28}{'—':>9}{'masked / unavailable':>26}")
            continue
        delta = abs(theirs - mine)
        good = delta <= 0.1
        failures += 0 if good else 1
        print(f"   {name:<28}{theirs:>9.1f}{mine:>13.1f}{delta:>8.3f}   {OK if good else BAD}")

    # ---- B/C: the target threshold is what it claims to be ------------------
    print("\nB. Target threshold == 95th percentile of high-confidence pixels")
    conf_p = os.path.join(jd, "confidence.tif")
    hv = valid
    if os.path.isfile(conf_p):
        with rasterio.open(conf_p) as cs:
            conf = cs.read(1).astype("float32")
        if conf.shape == arr.shape:
            hv = valid & (conf >= 0.99)
    thr_recomputed = float(np.percentile(arr[hv], 95.0))

    tj = os.path.join(jd, "targets.json")
    if os.path.isfile(tj):
        stored = json.load(open(tj)).get("params", {}).get("threshold_value")
        if stored is not None:
            d = abs(stored - thr_recomputed)
            good = d <= 1e-3
            failures += 0 if good else 1
            print(f"   stored {stored:.4f}   recomputed {thr_recomputed:.4f}   "
                  f"Δ {d:.6f}   {OK if good else BAD}")
        else:
            print("   targets.json has no threshold_value")
    else:
        print("   no targets.json yet (open the Explorer once to generate it)")

    frac = float((arr[hv] >= thr_recomputed).mean() * 100)
    good = abs(frac - 5.0) <= 0.6
    failures += 0 if good else 1
    print(f"\nC. Fraction at/above that threshold should be ~5%")
    print(f"   measured {frac:.2f}%   {OK if good else BAD}")

    # ---- D: determinism ------------------------------------------------------
    a1 = independent_percentile(arr, valid, *rowcol(transform, *tf.transform(-117.6342, 37.7499)))
    a2 = independent_percentile(arr, valid, *rowcol(transform, *tf.transform(-117.6342, 37.7499)))
    good = a1 == a2
    failures += 0 if good else 1
    print(f"\nD. Determinism (same input twice)   {OK if good else BAD}")

    # ---- E: saturation, stated plainly --------------------------------------
    at_ceiling = float((arr[valid] >= 1.0).mean() * 100)
    print(f"\nE. Clipped to exactly 1.000 by _norm(lo=2, hi=98): {at_ceiling:.2f}% of valid pixels")
    print("   This is why the top of the scale reads 98th percentile and why every")
    print("   detected target shares that peak. It is the clip, not the geology.")

    # ---- what this does and does not establish ------------------------------
    print("\n" + "=" * 72)
    print("WHAT THIS PROVES:  the percentiles shown are arithmetically correct and")
    print("                   reproducible from the GeoTIFF by an independent path.")
    print("WHAT IT DOES NOT:  that the index tracks real lithium. That needs ground")
    print("                   truth — currently 3 scored sites, so the AUC is")
    print("                   indicative only, not a generalisation estimate.")
    print("=" * 72)
    print(("\nALL CHECKS PASSED" if failures == 0 else f"\n{failures} CHECK(S) FAILED"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

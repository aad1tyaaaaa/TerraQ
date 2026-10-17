#!/usr/bin/env python3
"""
product/benchmark_console.py
============================
Single source of truth for the Explorer console's "Top Exploration Targets" list.

Why this exists alongside benchmark_sentinel.py
-----------------------------------------------
`benchmark_sentinel.py` reports a deposit that is outside the analysed footprint,
or that falls on masked (water / vegetation / nodata) pixels, as `score 0.0,
percentile 0.0`. In a UI that reads as "we looked and found nothing", which is a
different and much stronger claim than "we had no usable data here".

This script keeps the same scoring maths but separates the three cases:

    status = "scored"             -> score + percentile are real numbers
    status = "outside_footprint"  -> score = percentile = null
    status = "masked"             -> score = percentile = null

`null` renders as "—" in the console. A deposit is NEVER shown as 0.0 unless the
index genuinely evaluated to 0.0 on valid rock.

Fixed AOI so the numbers are stable across demos: Clayton Valley / Silver Peak.

Usage:  .venv/bin/python product/benchmark_console.py
Output: outputs/benchmark_console.json   (does NOT touch benchmark.json)
"""
from __future__ import annotations
import os, sys, csv, json, math

import numpy as np
import rasterio
from rasterio.transform import rowcol
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# Fixed AOI — same coordinates as the "Silver Peak (Li)" preset.
LAT, LON, KM = 37.7499, -117.6342, 12.0
OUT_JSON = os.path.join(ROOT, "outputs", "benchmark_console.json")
RUN_DIR = os.path.join(ROOT, "outputs", "benchmark_console_run")
SEED, BUFFER, N_BG = 42, 1, 5000

GT = [("mrds_lithium.csv", "Li"), ("mrds_vanadium.csv", "V")]


def _auc_and_p(pos, neg):
    """Rank-based ROC-AUC + one-sided Mann-Whitney p (same maths as benchmark_sentinel)."""
    allv = np.concatenate([pos, neg])
    order = allv.argsort()
    ranks = np.empty(len(allv), dtype="float64")
    ranks[order] = np.arange(1, len(allv) + 1)
    sortv = allv[order]
    i = 0
    while i < len(sortv):                      # average ranks across ties
        j = i
        while j + 1 < len(sortv) and sortv[j + 1] == sortv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    n1, n2 = len(pos), len(neg)
    U1 = ranks[:n1].sum() - n1 * (n1 + 1) / 2.0
    auc = U1 / (n1 * n2)
    mu, sd = n1 * n2 / 2.0, math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
    z = (U1 - mu) / sd if sd > 0 else 0.0
    p_one = 0.5 * (1 - math.erf(z / math.sqrt(2)))
    return float(auc), float(p_one), float(z)


def main():
    tif = os.path.join(RUN_DIR, "lithium_prospectivity.tif")
    if not os.path.isfile(tif):
        print(f"No cached run at {RUN_DIR} — running the engine on the fixed AOI…")
        from sentinel_engine import run as engine_run
        engine_run(LAT, LON, KM, RUN_DIR)
    else:
        print(f"Reusing existing run at {RUN_DIR}")

    with rasterio.open(tif) as src:
        arr = src.read(1).astype("float32")
        transform, crs = src.transform, src.crs
    valid = arr > 0                               # pixels where the index evaluated
    tf = Transformer.from_crs("EPSG:4326", crs.to_string(), always_xy=True)
    H, W = arr.shape

    deposits, pos_idx = [], set()
    for fname, commodity in GT:
        path = os.path.join(ROOT, "data", "ground_truth", fname)
        if not os.path.isfile(path):
            continue
        for r in csv.DictReader(open(path)):
            lat, lon = float(r["lat"]), float(r["lon"])
            x, y = tf.transform(lon, lat)
            row, col = rowcol(transform, x, y)

            rec = {
                "site": r["site"].strip().rstrip("."),
                "commodity": commodity,
                "status_mrds": r.get("status", "").strip() or None,
                "dep_id": r.get("dep_id"),
                "url": r.get("url"),
                "lat": lat, "lon": lon,
            }

            if not (0 <= row < H and 0 <= col < W):
                # Catalogued elsewhere in Nevada — this AOI simply does not cover it.
                rec.update(status="outside_footprint", score=None, percentile=None,
                           note="Outside the analysed footprint — not evaluated.")
                deposits.append(rec)
                continue

            win = arr[max(0, row - BUFFER):row + BUFFER + 1,
                      max(0, col - BUFFER):col + BUFFER + 1]
            winv = win[win > 0]
            if winv.size == 0:
                # Inside the AOI but every pixel is water / vegetation / nodata.
                # Silver Peak Marsh lands here: a brine playa has no rock signal.
                rec.update(status="masked", score=None, percentile=None,
                           note="No valid rock pixels (water, vegetation or nodata) — "
                                "optical sensing cannot score this location.")
                deposits.append(rec)
                continue

            centre = float(winv.mean())
            pct = float((arr[valid] < centre).mean() * 100)
            rec.update(status="scored", score=round(centre, 3), percentile=round(pct, 1),
                       note=None)
            deposits.append(rec)

            if commodity == "Li":
                for dr in range(-BUFFER, BUFFER + 1):
                    for dc in range(-BUFFER, BUFFER + 1):
                        rr, cc = row + dr, col + dc
                        if 0 <= rr < H and 0 <= cc < W and arr[rr, cc] > 0:
                            pos_idx.add((rr, cc))

    # --- AUC over Li positives vs random background rock -----------------------
    auc = pval = z = None
    n_pos = n_neg = 0
    if pos_idx:
        pos = np.array([arr[r, c] for r, c in pos_idx], dtype="float32")
        rng = np.random.default_rng(SEED)
        vr, vc = np.where(valid)
        cand = [(r, c) for r, c in zip(vr, vc) if (r, c) not in pos_idx]
        if cand:
            sel = rng.choice(len(cand), size=min(N_BG, len(cand)), replace=False)
            neg = np.array([arr[cand[i]] for i in sel], dtype="float32")
            auc, pval, z = _auc_and_p(pos, neg)
            n_pos, n_neg = len(pos), len(neg)

    scored = [d for d in deposits if d["status"] == "scored"]
    li_scored = [d for d in scored if d["commodity"] == "Li"]

    report = {
        "generated_by": "product/benchmark_console.py",
        "aoi": {"lat": LAT, "lon": LON, "radius_km": KM,
                "name": "Clayton Valley / Silver Peak, Nevada"},
        "index": "Sentinel-2 L2A clay/Al-OH ratio (B11/B12) — lithium surface alteration",
        "honest_scope": (
            "Indicative validation only. Positives are a small, spatially clustered set "
            "of USGS MRDS lithium occurrences around Silver Peak. This measures whether "
            "the index ranks known sites above background in ONE scene — it is not a "
            "generalisation accuracy. Scores are relative 0-1 alteration indices, not "
            "probabilities and not proof of mineralisation."
        ),
        "nodata_policy": (
            "status='outside_footprint' or 'masked' => score and percentile are null and "
            "must render as '—'. They are never shown as 0."
        ),
        "counts": {
            "deposits_total": len(deposits),
            "scored": len(scored),
            "masked": sum(1 for d in deposits if d["status"] == "masked"),
            "outside_footprint": sum(1 for d in deposits if d["status"] == "outside_footprint"),
            "positive_pixels": int(n_pos),
            "background_pixels": int(n_neg),
        },
        "roc_auc": round(auc, 3) if auc is not None else None,
        "mannwhitney_p_one_sided": float(f"{pval:.2e}") if pval is not None else None,
        "z": round(z, 2) if z is not None else None,
        "li_median_percentile": (round(float(np.median([d["percentile"] for d in li_scored])), 1)
                                 if li_scored else None),
        "deposits": deposits,
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nWrote {OUT_JSON}")
    print(f"  ROC-AUC            : {report['roc_auc']}")
    print(f"  scored / masked / outside : {report['counts']['scored']} / "
          f"{report['counts']['masked']} / {report['counts']['outside_footprint']}")
    for d in deposits:
        val = "—" if d["percentile"] is None else f"{d['percentile']:.1f} pct"
        print(f"  [{d['commodity']}] {d['site'][:34]:34s} {d['status']:18s} {val}")


if __name__ == "__main__":
    main()

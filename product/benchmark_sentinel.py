#!/usr/bin/env python3
"""
product/benchmark_sentinel.py
=============================
Quantitative benchmark of the Sentinel-2 LITHIUM prospectivity index against
real USGS MRDS deposit locations — computed offline from a cached engine output
(no network needed).

Honest framing: the positive set is small and spatially clustered (the known
lithium occurrences sit in/around Silver Peak), so these numbers are an
*indicative validation* ("does the index rank known deposits above background?"),
NOT a generalisation accuracy. Reported with that caveat.

Metrics:
  * ROC-AUC          (rank-based = P[deposit pixel scores > background pixel])
  * Precision@top-k  (are the highest-prospectivity pixels near deposits?)
  * Mann-Whitney U p (are deposit scores significantly above background?)
  * Per-deposit percentile within the scene

Usage:
  .venv/bin/python product/benchmark_sentinel.py
"""
import os, csv, json
import numpy as np
import rasterio
from rasterio.transform import rowcol
from pyproj import Transformer

import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUN = sys.argv[1] if len(sys.argv) > 1 else "product_demo_v2"
TIF = os.path.join(ROOT, "outputs", _RUN, "lithium_prospectivity.tif")
LICSV = os.path.join(ROOT, "data", "ground_truth", "mrds_lithium.csv")
OUT = os.path.join(ROOT, "outputs", "sentinel2_benchmark")
SEED = 42
BUFFER = 1          # +/- pixels around each deposit (3x3) -> a few pixels each
N_BG = 5000         # background sample size


def main():
    os.makedirs(OUT, exist_ok=True)
    with rasterio.open(TIF) as src:
        arr = src.read(1).astype("float32")
        transform, crs = src.transform, src.crs
    valid = arr > 0                                   # rock pixels (index computed)
    tf = Transformer.from_crs("EPSG:4326", crs.to_string(), always_xy=True)

    # --- positives: pixels in a small buffer around each in-scene Li deposit ---
    deposits, pos_idx = [], set()
    for r in csv.DictReader(open(LICSV)):
        lat, lon = float(r["lat"]), float(r["lon"])
        x, y = tf.transform(lon, lat)
        row, col = rowcol(transform, x, y)
        if not (0 <= row < arr.shape[0] and 0 <= col < arr.shape[1]):
            continue
        # percentile of the centre pixel (or its neighbourhood mean) within valid rock
        win = arr[max(0, row-BUFFER):row+BUFFER+1, max(0, col-BUFFER):col+BUFFER+1]
        winv = win[win > 0]
        centre = float(winv.mean()) if winv.size else 0.0
        pctile = float((arr[valid] < centre).mean() * 100) if centre > 0 else 0.0
        on_rock = centre > 0
        deposits.append({"site": r["site"], "lat": lat, "lon": lon,
                         "score": round(centre, 3), "percentile": round(pctile, 1),
                         "on_valid_rock": on_rock})
        if on_rock:
            for dr in range(-BUFFER, BUFFER+1):
                for dc in range(-BUFFER, BUFFER+1):
                    rr, cc = row+dr, col+dc
                    if 0 <= rr < arr.shape[0] and 0 <= cc < arr.shape[1] and arr[rr, cc] > 0:
                        pos_idx.add((rr, cc))

    pos = np.array([arr[r, c] for (r, c) in pos_idx], dtype="float32")
    n_sites_used = sum(d["on_valid_rock"] for d in deposits)

    # --- negatives: random valid rock pixels not in the positive set ---
    rng = np.random.default_rng(SEED)
    vr, vc = np.where(valid)
    posset = pos_idx
    cand = [(r, c) for r, c in zip(vr, vc) if (r, c) not in posset]
    sel = rng.choice(len(cand), size=min(N_BG, len(cand)), replace=False)
    neg = np.array([arr[cand[i]] for i in sel], dtype="float32")

    # --- ROC-AUC via rank (Mann-Whitney U) ---
    def auc_and_p(p, n):
        allv = np.concatenate([p, n])
        ranks = allv.argsort().argsort().astype("float64") + 1
        # average ranks for ties
        order = allv.argsort(); sortv = allv[order]
        i = 0
        while i < len(sortv):
            j = i
            while j+1 < len(sortv) and sortv[j+1] == sortv[i]:
                j += 1
            if j > i:
                avg = (i + j) / 2.0 + 1
                ranks[order[i:j+1]] = avg
            i = j+1
        R1 = ranks[:len(p)].sum()
        U1 = R1 - len(p)*(len(p)+1)/2.0
        auc = U1 / (len(p)*len(n))
        # normal approx p-value (one-sided: positives > negatives)
        mu = len(p)*len(n)/2.0
        sd = np.sqrt(len(p)*len(n)*(len(p)+len(n)+1)/12.0)
        z = (U1 - mu)/sd if sd > 0 else 0.0
        from math import erf, sqrt
        p_one = 0.5*(1 - erf(z/np.sqrt(2)))
        return float(auc), float(p_one), float(z)

    auc, pval, z = auc_and_p(pos, neg)

    # --- hit-rate (recall) @ top-k: of the known rock-hosted deposit sites,
    #     what fraction land in the top-k% highest-prospectivity pixels?
    #     (This is the prospecting question: "drill the top X% — do we catch
    #     the known deposits?" Precision@k is uninformative here because only a
    #     handful of deposits are catalogued vs lots of un-catalogued alteration.)
    rock_pcts = [d["percentile"] for d in deposits if d["on_valid_rock"]]
    def hitrate_at(frac):
        if not rock_pcts:
            return 0.0
        cut = 100 * (1 - frac)
        return sum(1 for p in rock_pcts if p >= cut) / len(rock_pcts)

    report = {
        "dataset": "Sentinel-2 L2A clay/Al-OH lithium index (cached Clayton Valley run)",
        "note": ("Indicative validation only. Positives are a small, spatially "
                 "clustered set of known MRDS lithium occurrences (mostly Silver "
                 "Peak); brine-playa points correctly fall on masked/low pixels. "
                 "Not a generalisation accuracy."),
        "n_deposit_sites_total": len(deposits),
        "n_sites_on_valid_rock": int(n_sites_used),
        "n_positive_pixels": int(len(pos)),
        "n_background_pixels": int(len(neg)),
        "roc_auc": round(auc, 3),
        "mannwhitney_p_one_sided": float(f"{pval:.2e}"),
        "z": round(z, 2),
        "hitrate_at_top_5pct": round(hitrate_at(0.05), 3),
        "hitrate_at_top_10pct": round(hitrate_at(0.10), 3),
        "deposit_median_percentile": round(float(np.median(
            [d["percentile"] for d in deposits if d["on_valid_rock"]] or [0])), 1),
        "deposits": deposits,
    }
    with open(os.path.join(OUT, "benchmark.json"), "w") as f:
        json.dump(report, f, indent=2)

    print("="*64)
    print("SENTINEL-2 LITHIUM INDEX — BENCHMARK vs USGS MRDS")
    print("="*64)
    print(f"  Positives: {len(pos)} px from {n_sites_used} rock-hosted sites")
    print(f"  Background: {len(neg)} valid rock px")
    print(f"  ROC-AUC                 = {auc:.3f}")
    print(f"  Mann-Whitney p (1-sided)= {pval:.2e}  (z={z:.2f})")
    print(f"  Hit-rate@top-5%         = {report['hitrate_at_top_5pct']}  (deposits caught in top 5% of map)")
    print(f"  Hit-rate@top-10%        = {report['hitrate_at_top_10pct']}  (deposits caught in top 10%)")
    print(f"  Deposit median pctile   = {report['deposit_median_percentile']}")
    print("\n  Per-deposit:")
    for d in deposits:
        tag = "rock" if d["on_valid_rock"] else "playa/nodata"
        print(f"    {d['site'][:28]:28s} {tag:12s} score={d['score']:.2f} pct={d['percentile']:.0f}")
    print(f"\n  CAVEAT: {report['note']}")
    print(f"\n  Saved: {OUT}/benchmark.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
product/build_results.py
========================
Assemble a single, presentable RESULTS folder for the Sentinel-2 product:
benchmark metrics, the ratio-vs-continuum ablation, figures, and a report.

Offline — reads the cached Clayton Valley output + USGS MRDS ground truth.
Output: outputs/sentinel2_results/

Usage:  .venv/bin/python product/build_results.py
"""
import os, csv, json, shutil
import numpy as np
import rasterio
from rasterio.transform import rowcol
from pyproj import Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "outputs", "product_demo_v2")   # shipped index = B11/B12 ratio
TIF = os.path.join(RUN, "lithium_prospectivity.tif")
LICSV = os.path.join(ROOT, "data", "ground_truth", "mrds_lithium.csv")
OUT = os.path.join(ROOT, "outputs", "sentinel2_results")
SEED, BUFFER, N_BG = 42, 1, 5000

# Ablation result measured earlier (continuum-removed index, same scene/GT).
CONTINUUM_AUC = 0.462


def auc_rank(p, n):
    allv = np.concatenate([p, n])
    order = allv.argsort(); ranks = np.empty(len(allv)); ranks[order] = np.arange(1, len(allv)+1)
    R1 = ranks[:len(p)].sum(); U1 = R1 - len(p)*(len(p)+1)/2.0
    return U1/(len(p)*len(n))


def main():
    os.makedirs(OUT, exist_ok=True)
    with rasterio.open(TIF) as src:
        arr = src.read(1).astype("float32"); transform, crs = src.transform, src.crs
    valid = arr > 0
    tf = Transformer.from_crs("EPSG:4326", crs.to_string(), always_xy=True)

    deposits, pos_px = [], set()
    for r in csv.DictReader(open(LICSV)):
        lat, lon = float(r["lat"]), float(r["lon"])
        x, y = tf.transform(lon, lat); row, col = rowcol(transform, x, y)
        if not (0 <= row < arr.shape[0] and 0 <= col < arr.shape[1]):
            continue
        win = arr[max(0, row-BUFFER):row+BUFFER+1, max(0, col-BUFFER):col+BUFFER+1]
        winv = win[win > 0]; centre = float(winv.mean()) if winv.size else 0.0
        pct = float((arr[valid] < centre).mean()*100) if centre > 0 else 0.0
        deposits.append({"site": r["site"], "score": round(centre, 3),
                         "percentile": round(pct, 1), "on_rock": centre > 0})
        if centre > 0:
            for dr in range(-BUFFER, BUFFER+1):
                for dc in range(-BUFFER, BUFFER+1):
                    rr, cc = row+dr, col+dc
                    if 0 <= rr < arr.shape[0] and 0 <= cc < arr.shape[1] and arr[rr, cc] > 0:
                        pos_px.add((rr, cc))

    pos = np.array([arr[p] for p in pos_px], "float32")
    rng = np.random.default_rng(SEED)
    vr, vc = np.where(valid)
    cand = [(r, c) for r, c in zip(vr, vc) if (r, c) not in pos_px]
    sel = rng.choice(len(cand), size=min(N_BG, len(cand)), replace=False)
    neg = np.array([arr[cand[i]] for i in sel], "float32")
    auc = auc_rank(pos, neg)
    n_sites = sum(d["on_rock"] for d in deposits)
    rock_pcts = [d["percentile"] for d in deposits if d["on_rock"]]
    hit5 = sum(p >= 95 for p in rock_pcts)/len(rock_pcts) if rock_pcts else 0
    hit10 = sum(p >= 90 for p in rock_pcts)/len(rock_pcts) if rock_pcts else 0

    # ---- figure 1: deposit vs background score distribution ----
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(neg, bins=40, density=True, alpha=0.6, label=f"background (n={len(neg)})", color="#64748b")
    for i, s in enumerate(pos):
        ax.axvline(s, color="#00b4d8", alpha=0.5, lw=1.2, label="known Li deposit px" if i == 0 else None)
    ax.set_xlabel("lithium prospectivity (0–1)"); ax.set_ylabel("density")
    ax.set_title("Known lithium deposits score above background\n(Sentinel-2 B11/B12 clay index, Clayton Valley)")
    ax.legend(); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_score_distribution.png"), dpi=130); plt.close()

    # ---- figure 2: index ablation ----
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(["B11/B12 ratio\n(shipped)", "continuum-removed\n(rejected)"],
                  [auc, CONTINUUM_AUC], color=["#00b4d8", "#ef4444"])
    ax.axhline(0.5, ls="--", color="#94a3b8", label="random (0.50)")
    ax.set_ylabel("ROC-AUC vs MRDS deposits"); ax.set_ylim(0, 1)
    ax.set_title("Index ablation — simple ratio wins")
    for b, v in zip(bars, [auc, CONTINUUM_AUC]):
        ax.text(b.get_x()+b.get_width()/2, v+0.02, f"{v:.2f}", ha="center", fontweight="bold")
    ax.legend(); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_index_ablation.png"), dpi=130); plt.close()

    # ---- copy key maps ----
    for s, d in [("silver_peak_validation.png", "silver_peak_validation.png"),
                 (os.path.join(RUN, "lithium_prospectivity.png"), "lithium_prospectivity_map.png")]:
        src_p = s if os.path.isabs(s) else os.path.join(ROOT, "terraq", "public", "maps", s)
        if os.path.exists(src_p):
            shutil.copy(src_p, os.path.join(OUT, d))

    metrics = {
        "product": "Sentinel-2 L2A lithium surface-alteration index (B11/B12 clay ratio)",
        "scene": "Clayton Valley / Silver Peak, Nevada",
        "ground_truth": "USGS MRDS known lithium occurrences",
        "roc_auc": round(auc, 3),
        "hit_rate_top_5pct": round(hit5, 3),
        "hit_rate_top_10pct": round(hit10, 3),
        "n_rock_sites": int(n_sites), "n_positive_px": int(len(pos)), "n_background_px": int(len(neg)),
        "deposit_median_percentile": round(float(np.median(rock_pcts) if rock_pcts else 0), 1),
        "ablation_continuum_removed_auc": CONTINUUM_AUC,
        "deposits": deposits,
    }
    json.dump(metrics, open(os.path.join(OUT, "benchmark.json"), "w"), indent=2)

    # ---- CSV ----
    with open(os.path.join(OUT, "metrics_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        for k in ["roc_auc", "hit_rate_top_5pct", "hit_rate_top_10pct",
                  "deposit_median_percentile", "n_rock_sites", "n_positive_px",
                  "n_background_px", "ablation_continuum_removed_auc"]:
            w.writerow([k, metrics[k]])

    # ---- METRICS.md ----
    md = f"""# Sentinel-2 Product — Metrics & Benchmark

**Product:** lithium surface-alteration index (Sentinel-2 L2A, B11/B12 clay / Al-OH ratio)
**Test area:** Clayton Valley / Silver Peak, Nevada
**Ground truth:** USGS MRDS known lithium occurrences (real deposits, not pseudo-labels)

## Headline metrics (shipped model)

| Metric | Value | Meaning |
|---|---|---|
| ROC-AUC | **{auc:.2f}** | known deposit pixels rank above background |
| Hit-rate @ top 5% | **{hit5:.2f}** | fraction of rock-hosted sites in the top 5% of the map |
| Hit-rate @ top 10% | **{hit10:.2f}** | …in the top 10% |
| Deposit median percentile | **{np.median(rock_pcts) if rock_pcts else 0:.0f}** | where deposits sit on the prospectivity map |
| Positives / Background | {len(pos)} px / {len(neg)} px | from {n_sites} rock-hosted sites |

## Index ablation (why the simple ratio is shipped)

| Index | ROC-AUC | Decision |
|---|---|---|
| **B11/B12 ratio** | **{auc:.2f}** | ✅ shipped |
| Continuum-removed depth | {CONTINUUM_AUC:.2f} | ❌ rejected (worse than random; S2 has only 2 SWIR bands) |

![ablation](fig_index_ablation.png)
![distribution](fig_score_distribution.png)

## Per-deposit
| Site | type | score | percentile |
|---|---|---|---|
""" + "\n".join(
        f"| {d['site'][:30]} | {'rock' if d['on_rock'] else 'playa/nodata'} | {d['score']:.2f} | {d['percentile']:.0f} |"
        for d in deposits) + f"""

## Honest caveats
- **Small, clustered ground truth** ({n_sites} rock-hosted sites, mostly Silver Peak) → this is an
  *indicative validation* ("does the index rank known deposits above background?"), **not** a
  generalisation accuracy. Treat ROC-AUC {auc:.2f} as a credibility check, not a guarantee.
- Scores are **normalised alteration values [0,1]**, not calibrated probabilities.
- Detects **rock/clay-hosted & pegmatite** Li alteration only — **not** brine Li (under playas) or
  buried deposits (a physical limit of optical remote sensing).
- Preprocessing: SCL cloud/shadow/snow/water masking is applied; no topographic correction yet.

## Reproduce
```
.venv/bin/python product/benchmark_sentinel.py product_demo_v2   # raw numbers
.venv/bin/python product/build_results.py                        # this folder
```
"""
    open(os.path.join(OUT, "METRICS.md"), "w").write(md)
    print(f"Built results folder: {OUT}")
    print(f"  ROC-AUC={auc:.3f}  hit@5%={hit5:.2f}  sites={n_sites}")
    print("  files:", ", ".join(sorted(os.listdir(OUT))))


if __name__ == "__main__":
    main()

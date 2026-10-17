#!/usr/bin/env python3
"""
product/build_validation_card.py
================================
Task 4. Merge every Task 1 / Task 2 result into one source of truth and render a
slide-ready figure plus a plain-English summary.

Writes:
    outputs/validation_final.json    all results, sample sizes, CIs, frozen rules
    outputs/validation_card.png      one figure for a slide
    outputs/validation_summary.md    <=12 lines, plain English

Figure colours were checked with the dataviz palette validator against the
#0b0e14 surface: #17a2b8 / #d95926 / #9085e9 pass the lightness band, chroma
floor, CVD separation, normal-vision floor and contrast checks.
"""
from __future__ import annotations
import os, sys, json
from urllib.parse import quote

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from validation_plan import CONTROLS, LITHIUM_AOIS, RADIUS_KM  # noqa: E402

RUNS = os.path.join(ROOT, "outputs", "validation_runs")
STATS = json.load(open(os.path.join(ROOT, "outputs", "validation_stats.json")))
CTRL = json.load(open(os.path.join(ROOT, "outputs", "validation_controls.json")))

SURFACE, INK, MUTED = "#0b0e14", "#e7ecf3", "#8e9bab"
C_DEPOSIT, C_DISTURBED, C_DESERT = "#17a2b8", "#d95926", "#9085e9"


def pool(ids):
    out = []
    for i in ids:
        p = os.path.join(RUNS, i, "clay_ratio_raw.tif")
        if not os.path.isfile(p):
            continue
        with rasterio.open(p) as s:
            a = s.read(1).astype("float64")
        hv = np.isfinite(a) & (a > 0)
        c = os.path.join(RUNS, i, "confidence.tif")
        if os.path.isfile(c):
            with rasterio.open(c) as cs:
                cf = cs.read(1)
            if cf.shape == a.shape:
                hv &= cf >= 0.99
        v = a[hv]
        if v.size:
            out.append(np.random.default_rng(42).choice(v, min(40000, v.size), replace=False))
    return np.concatenate(out) if out else np.array([])


def main():
    desert = pool([c["id"] for c in CONTROLS if c["kind"] == "desert"])
    disturbed = pool([c["id"] for c in CONTROLS if c["kind"] == "disturbed"])
    dep = [r for r in STATS["deposits"] if r["klass"] == "positive" and r["value"] is not None]
    brine = [r for r in STATS["deposits"] if r["klass"] == "brine" and r["value"] is not None]

    # ---------------- figure ------------------------------------------------
    fig = plt.figure(figsize=(13.2, 5.6), dpi=170, facecolor=SURFACE)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.45, 1], wspace=0.22,
                          left=0.065, right=0.975, top=0.86, bottom=0.13)

    ax = fig.add_subplot(gs[0, 0], facecolor=SURFACE)
    bins = np.linspace(0.85, 2.0, 90)
    ax.hist(desert, bins=bins, density=True, color=C_DESERT, alpha=0.55,
            label=f"desert controls  (n={len(desert):,} px)")
    ax.hist(disturbed, bins=bins, density=True, histtype="step", lw=2.0,
            color=C_DISTURBED, label=f"disturbed quarry  (n={len(disturbed):,} px)")

    for i, r in enumerate(dep):
        ax.axvline(r["value"], color=C_DEPOSIT, lw=2.0, alpha=0.95,
                   label="known Li deposits" if i == 0 else None)
    for i, r in enumerate(brine):
        ax.axvline(r["value"], color=MUTED, lw=1.4, ls=":",
                   label="brine sites (not positives)" if i == 0 else None)

    ax.set_xlabel("raw lithium index  (B11/B12, before per-scene normalisation)",
                  color=MUTED, fontsize=9)
    ax.set_ylabel("density", color=MUTED, fontsize=9)
    ax.set_title("Where known deposits sit against background",
                 color=INK, fontsize=11, loc="left", pad=8)
    for s in ax.spines.values():
        s.set_color("#243044")
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(alpha=0.10, color=INK)
    leg = ax.legend(frameon=False, fontsize=8, loc="upper right")
    for t in leg.get_texts():
        t.set_color(MUTED)

    # ---------------- numbers ----------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1], facecolor=SURFACE)
    ax2.axis("off")
    ci = STATS["auc_ci95_site_bootstrap"]
    pa = STATS["permutation_all_lithium_scenes"]
    rows = [
        ("Non-brine Li sites scored", f"{STATS['counts']['positives_scored']}"),
        ("Brine sites (excluded)", f"{STATS['counts']['brine']}"),
        ("Control AOIs / background px",
         f"{STATS['counts']['control_aois']} / {STATS['counts']['background_pixels']:,}"),
        ("Cross-scene ROC-AUC", f"{STATS['cross_scene_auc']}"),
        ("95% CI (site bootstrap)", f"[{ci[0]}, {ci[1]}]" if ci else "—"),
        ("PR-AUC", f"{STATS['pr_auc']}  (base rate 0.0003)"),
        ("Enrichment, top 5%", f"{STATS['enrichment_top5pct']}×  vs chance"),
        ("Spatial permutation p", f"{pa['p_value']:.4f}  (n={pa['n_points']}, {pa['n_permutations']:,} draws)"),
    ]
    ax2.text(0, 1.02, "Validation summary", color=INK, fontsize=11, va="bottom")
    y = 0.90
    for k, v in rows:
        ax2.text(0.0, y, k, color=MUTED, fontsize=9, va="center")
        ax2.text(1.0, y, v, color=INK, fontsize=10, va="center", ha="right",
                 fontweight="semibold")
        ax2.plot([0, 1], [y - 0.045, y - 0.045], color="#1d2633", lw=0.8)
        y -= 0.105
    ax2.text(0, y - 0.01,
             "Raw index, 3-px buffer max. Brine excluded: optical sensing\n"
             "cannot detect it. Rules frozen before any run.",
             color=MUTED, fontsize=7.6, va="top")
    ax2.set_xlim(0, 1); ax2.set_ylim(0, 1.06)

    fig.suptitle("TerraQ — lithium index validation against USGS MRDS, Nevada",
                 color=INK, fontsize=12.5, x=0.065, ha="left", y=0.955)
    out_png = os.path.join(ROOT, "outputs", "validation_card.png")
    fig.savefig(out_png, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", out_png)

    # ---------------- single source of truth --------------------------------
    final = dict(
        generated_by="product/build_validation_card.py",
        radius_km=RADIUS_KM,
        analysis_rules=STATS["analysis_rules"],
        control_aois=[dict(**{k: c[k] for k in ("id", "name", "lat", "lon", "kind", "why")})
                      for c in CONTROLS],
        lithium_aois=[dict(**{k: a[k] for k in ("id", "name", "lat", "lon", "why")})
                      for a in LITHIUM_AOIS],
        task1_per_aoi=CTRL,
        counts=STATS["counts"],
        cross_scene_auc=STATS["cross_scene_auc"],
        auc_ci95_site_bootstrap=STATS["auc_ci95_site_bootstrap"],
        pr_auc=STATS["pr_auc"],
        pr_auc_base_rate=round(STATS["counts"]["positives_scored"] /
                               (STATS["counts"]["positives_scored"] +
                                STATS["counts"]["background_pixels"]), 6),
        enrichment_top5pct=STATS["enrichment_top5pct"],
        permutation_clayton_valley=STATS["permutation_clayton_valley"],
        permutation_all_lithium_scenes=STATS["permutation_all_lithium_scenes"],
        producers=STATS["producers"],
        undeveloped=STATS["undeveloped"],
        deposits=STATS["deposits"],
        duplicates_dropped=STATS.get("duplicates_dropped", []),
        note_on_old_pvalue=STATS["note_on_old_pvalue"],
        known_limitations=[
            "6 non-brine sites is a very small positive set; the AUC CI is wide.",
            "All sites are Nevada; nothing here tests another geology.",
            "Producers score above undeveloped prospects, so part of the signal may "
            "be mining disturbance rather than mineralogy.",
            "The disturbed aggregate control reaches a higher maximum than Clayton "
            "Valley, which supports that concern.",
            "Target count is capped at 12 by MAX_TARGETS, so it cannot discriminate "
            "between AOIs and is reported for completeness only.",
        ],
    )
    out_json = os.path.join(ROOT, "outputs", "validation_final.json")
    json.dump(final, open(out_json, "w"), indent=1)
    print("wrote", out_json)

    # ---- compact copy for the dashboard ------------------------------------
    # Histogram bins are precomputed here so the UI renders the real
    # distribution natively instead of embedding a PNG it cannot restyle.
    edges = np.linspace(0.85, 2.0, 60)
    centres = ((edges[:-1] + edges[1:]) / 2).round(4)

    def hist(v):
        if v.size == 0:
            return [0] * (len(edges) - 1)
        h, _ = np.histogram(v, bins=edges, density=True)
        return [round(float(x), 4) for x in h]

    ui = dict(
        generated_by="product/build_validation_card.py",
        headline=("Known lithium sites rank above background, but on 6 sites with a "
                  "wide confidence interval and an unresolved disturbance confound."),
        counts=final["counts"],
        metrics=dict(
            auc=final["cross_scene_auc"],
            auc_ci=final["auc_ci95_site_bootstrap"],
            pr_auc=final["pr_auc"],
            pr_auc_base_rate=final["pr_auc_base_rate"],
            enrichment_top5pct=final["enrichment_top5pct"],
            permutation_p=final["permutation_all_lithium_scenes"]["p_value"],
            permutation_n=final["permutation_all_lithium_scenes"]["n_points"],
            permutation_draws=final["permutation_all_lithium_scenes"]["n_permutations"],
        ),
        distribution=dict(
            bin_centres=[float(c) for c in centres],
            desert=hist(desert),
            disturbed=hist(disturbed),
        ),
        # Each site links to its own USGS MRDS record — the primary, permanent
        # source for "this location is a catalogued lithium occurrence". The
        # scholar/news links are prefilled searches rather than specific
        # articles: a search URL cannot rot and makes no claim about what any
        # one article says.
        deposits=[dict(site=r["site"], value=r["value"], maturity=r["maturity"],
                       aoi=r["aoi"], dev=r.get("dev"), dep_id=r.get("dep_id"),
                       url=r.get("url"),
                       scholar=("https://scholar.google.com/scholar?q="
                                + quote(f'"{r["site"]}" lithium Nevada')),
                       news=("https://news.google.com/search?q="
                             + quote(f'"{r["site"]}" lithium')))
                  for r in dep],
        brine=[dict(site=r["site"], value=r["value"], url=r.get("url"),
                    dev=r.get("dev")) for r in brine],
        references=[
            dict(label="USGS Mineral Resources Data System (MRDS)",
                 url="https://mrdata.usgs.gov/mrds/",
                 note="the database every site below is drawn from"),
            dict(label="USGS Mineral Commodity Summaries — Lithium",
                 url="https://pubs.usgs.gov/periodicals/mcs2024/mcs2024-lithium.pdf",
                 note="national production and resource context"),
        ],
        aoi_table=final["task1_per_aoi"],
        caveats=final["known_limitations"],
        rules=final["analysis_rules"],
    )
    ui_path = os.path.join(ROOT, "terraq", "explorer", "data", "validation.json")
    os.makedirs(os.path.dirname(ui_path), exist_ok=True)
    json.dump(ui, open(ui_path, "w"), indent=1)
    print("wrote", ui_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

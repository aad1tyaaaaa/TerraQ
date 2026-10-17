#!/usr/bin/env python3
"""
product/validation_stats.py
===========================
Task 2B. Statistics over the already-generated AOIs. No engine runs here.

All values are the RAW lithium index (clay_ratio_raw.tif, B11/B12) before the
per-scene stretch, so they are comparable across scenes. Rules are frozen in
validation_plan.py and were fixed before any run.

Outputs outputs/validation_stats.json.
"""
from __future__ import annotations
import os, re, sys, json, math, random

import numpy as np
import rasterio
from rasterio.transform import rowcol
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from validation_plan import CONTROLS, LITHIUM_AOIS, classify, maturity  # noqa: E402

RUNS = os.path.join(ROOT, "outputs", "validation_runs")
OUT = os.path.join(ROOT, "outputs", "validation_stats.json")
BUFFER_PX = 3
SEED = 42
N_BOOT = 2000
N_PERM = 10000
BG_PER_SCENE = 2000
EXCLUDE_KM = 1.0

rng = np.random.default_rng(SEED)


# --------------------------------------------------------------------------
def mrds_sites():
    """Nevada-bbox MRDS records carrying the LI commodity token."""
    gml = "/tmp/qmd_probe/mrds/li.gml"
    if not os.path.isfile(gml):
        raise SystemExit("missing MRDS pull at " + gml)
    out = []
    for f in open(gml).read().split("<gml:featureMember")[1:]:
        g = lambda k: (re.search(rf"<ms:{k}>([^<]*)</ms:{k}>", f) or [None, None])[1]
        c = re.search(r"<gml:coordinates[^>]*>([-\d\.]+),([-\d\.]+)</gml:coordinates>", f)
        if not c:
            continue
        codes = (g("code_list") or "").strip()
        if "LI" not in codes.split():
            continue
        lat, lon = float(c.group(2)), float(c.group(1))
        if not (35.0 <= lat <= 42.0 and -120.5 <= lon <= -114.0):
            continue
        name, dev = g("site_name") or "", g("dev_stat") or ""
        out.append(dict(site=name, dev=dev, codes=codes, lat=lat, lon=lon,
                        dep_id=g("dep_id"), url=g("url"),
                        klass=classify(name, dev, codes),
                        maturity=maturity(dev)))
    return out


def load_scene(d):
    raw_p = os.path.join(d, "clay_ratio_raw.tif")
    if not os.path.isfile(raw_p):
        return None
    with rasterio.open(raw_p) as src:
        raw = src.read(1).astype("float64")
        transform, crs = src.transform, src.crs
    conf_p = os.path.join(d, "confidence.tif")
    hv = np.isfinite(raw) & (raw > 0)
    if os.path.isfile(conf_p):
        with rasterio.open(conf_p) as cs:
            conf = cs.read(1).astype("float32")
        if conf.shape == raw.shape:
            hv &= conf >= 0.99
    return dict(raw=raw, hv=hv, transform=transform, crs=crs,
                tf=Transformer.from_crs("EPSG:4326", crs.to_string(), always_xy=True))


def sample_at(sc, lat, lon, buffer=BUFFER_PX):
    """MAX raw index within a 3-pixel buffer. None when outside / masked."""
    x, y = sc["tf"].transform(lon, lat)
    r, c = rowcol(sc["transform"], x, y)
    h, w = sc["raw"].shape
    if not (0 <= r < h and 0 <= c < w):
        return None, "outside_footprint"
    sl = (slice(max(0, r - buffer), r + buffer + 1),
          slice(max(0, c - buffer), c + buffer + 1))
    win, m = sc["raw"][sl], sc["hv"][sl]
    v = win[m]
    if v.size == 0:
        return None, "masked"
    return float(v.max()), "scored"


def auc_pr(pos, neg):
    """Rank ROC-AUC (ties averaged) and average precision."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if pos.size == 0 or neg.size == 0:
        return None, None
    allv = np.concatenate([pos, neg])
    order = allv.argsort()
    ranks = np.empty(allv.size, float)
    ranks[order] = np.arange(1, allv.size + 1)
    sv = allv[order]
    i = 0
    while i < sv.size:                       # average ranks across ties
        j = i
        while j + 1 < sv.size and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    n1, n2 = pos.size, neg.size
    auc = (ranks[:n1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n2)

    y = np.r_[np.ones(n1), np.zeros(n2)]
    o = np.argsort(-allv)
    y = y[o]
    tp = np.cumsum(y)
    prec = tp / np.arange(1, y.size + 1)
    rec = tp / n1
    ap = float(np.sum(np.diff(np.r_[0, rec]) * prec))
    return float(auc), ap


def main():
    sites = mrds_sites()
    scenes = {}
    for a in LITHIUM_AOIS + CONTROLS:
        sc = load_scene(os.path.join(RUNS, a["id"]))
        if sc:
            scenes[a["id"]] = sc
    print(f"scenes loaded: {sorted(scenes)}")

    # ---- deposit values ---------------------------------------------------
    records = []
    for a in LITHIUM_AOIS:
        sc = scenes.get(a["id"])
        if sc is None:
            continue
        for s in sites:
            v, st = sample_at(sc, s["lat"], s["lon"])
            if st == "outside_footprint":
                continue                      # belongs to another AOI
            rec = dict(aoi=a["id"], aoi_name=a["name"], **{k: s[k] for k in
                       ("site", "dev", "codes", "lat", "lon", "klass", "maturity",
                        "dep_id", "url")},
                       value=v, status=st)
            # keep the first AOI that contains it, so no double counting
            if not any(r["site"] == s["site"] and abs(r["lat"] - s["lat"]) < 1e-6
                       for r in records):
                records.append(rec)

    # MRDS carries separate rows for the same ground (e.g. "Ed Deposit" appears
    # as both Prospect and Occurrence at identical coordinates). Counting both
    # would be pseudo-replication — the very thing this study exists to avoid —
    # so coincident points are collapsed to one observation.
    # Collapse by DISTANCE, not rounded coordinates: the two "Ed Deposit" rows
    # sit 5 m apart, which rounding split either side of a boundary. Anything
    # inside one pixel (40 m) is one observation.
    DEDUP_M = 50.0
    _dedup, dropped_dupes = [], []
    for r in records:
        dup = None
        for q in _dedup:
            dy = (r["lat"] - q["lat"]) * 111320.0
            dx = (r["lon"] - q["lon"]) * 111320.0 * math.cos(math.radians(r["lat"]))
            if math.hypot(dx, dy) < DEDUP_M:
                dup = q
                break
        if dup is not None:
            dropped_dupes.append(f'{r["site"]} ({r["dev"]}) ~ {dup["site"]}')
            continue
        _dedup.append(r)
    records = _dedup
    if dropped_dupes:
        print(f"dropped {len(dropped_dupes)} coincident duplicate(s): {dropped_dupes}")

    pos = [r for r in records if r["klass"] == "positive" and r["status"] == "scored"]
    brine = [r for r in records if r["klass"] == "brine"]
    excl = [r for r in records if r["klass"] == "excluded"]
    print(f"positives scored: {len(pos)}   brine: {len(brine)}   excluded(plant): {len(excl)}")

    # ---- background pool --------------------------------------------------
    def background(sc, exclude_pts):
        hv = sc["hv"].copy()
        for (la, lo) in exclude_pts:
            x, y = sc["tf"].transform(lo, la)
            r, c = rowcol(sc["transform"], x, y)
            px = int(EXCLUDE_KM * 1000 / abs(sc["transform"].a)) + 1
            hv[max(0, r - px):r + px + 1, max(0, c - px):c + px + 1] = False
        v = sc["raw"][hv]
        if v.size == 0:
            return np.array([])
        n = min(BG_PER_SCENE, v.size)
        return rng.choice(v, size=n, replace=False)

    bg, bg_by = [], {}
    for a in CONTROLS:
        sc = scenes.get(a["id"])
        if sc is None:
            continue
        b = background(sc, [])
        bg_by[a["id"]] = b
        bg.append(b)
    for a in LITHIUM_AOIS:
        sc = scenes.get(a["id"])
        if sc is None:
            continue
        b = background(sc, [(s["lat"], s["lon"]) for s in sites])
        bg_by[a["id"]] = b
        bg.append(b)
    bg = np.concatenate(bg) if bg else np.array([])
    print(f"background pixels pooled: {bg.size:,}")

    pv = np.array([r["value"] for r in pos], float)
    auc, ap = auc_pr(pv, bg)

    # ---- site-level bootstrap (resample SITES, not pixels) ----------------
    boot = []
    if pv.size >= 2 and bg.size:
        for _ in range(N_BOOT):
            s = rng.choice(pv, size=pv.size, replace=True)
            a_, _p = auc_pr(s, rng.choice(bg, size=min(1500, bg.size), replace=False))
            if a_ is not None:
                boot.append(a_)
    ci = ([round(float(np.percentile(boot, 2.5)), 3),
           round(float(np.percentile(boot, 97.5)), 3)] if boot else None)

    # ---- enrichment at top 5% of the pooled distribution ------------------
    enrich = None
    if pv.size and bg.size:
        pool = np.concatenate([pv, bg])
        thr = float(np.percentile(pool, 95))
        frac = float((pv >= thr).mean())
        enrich = round(frac / 0.05, 2)

    # ---- spatial permutation in Clayton Valley ----------------------------
    perm = None
    sc0 = scenes.get("L0")
    if sc0 is not None:
        cv_pos = [r for r in pos if r["aoi"] == "L0"]
        if cv_pos:
            obs = float(np.mean([r["value"] for r in cv_pos]))
            idx = np.flatnonzero(sc0["hv"].ravel())
            h, w = sc0["raw"].shape
            flat = sc0["raw"].ravel()
            k = len(cv_pos)
            null = np.empty(N_PERM)
            for i in range(N_PERM):
                pick = rng.choice(idx, size=k, replace=False)
                vals = []
                for p in pick:                       # same 3-px buffer-max rule
                    r, c = divmod(int(p), w)
                    sl = (slice(max(0, r - BUFFER_PX), r + BUFFER_PX + 1),
                          slice(max(0, c - BUFFER_PX), c + BUFFER_PX + 1))
                    win, m = sc0["raw"][sl], sc0["hv"][sl]
                    vv = win[m]
                    vals.append(float(vv.max()) if vv.size else 0.0)
                null[i] = np.mean(vals)
            p_val = float((null >= obs).mean())
            perm = dict(n_points=k, observed_mean=round(obs, 4),
                        null_mean=round(float(null.mean()), 4),
                        null_sd=round(float(null.std()), 4),
                        percentile_of_observed=round(float((null < obs).mean() * 100), 2),
                        p_value=p_val, n_permutations=N_PERM)

    # ---- pooled permutation across ALL lithium scenes ---------------------
    # Clayton Valley on its own has very few scoreable positives, so the same
    # test is also run across every lithium AOI: relocate each scene's positives
    # within that scene's own valid mask, pool, and compare the pooled mean.
    perm_all = None
    by_scene = {}
    for r in pos:
        by_scene.setdefault(r["aoi"], []).append(r)
    usable = {k: v for k, v in by_scene.items() if k in scenes}
    if usable:
        obs_all = float(np.mean([r["value"] for r in pos]))
        null = np.empty(N_PERM)
        prepped = []
        for aoi, rs in usable.items():
            sc = scenes[aoi]
            prepped.append((sc, np.flatnonzero(sc["hv"].ravel()), len(rs),
                            sc["raw"].shape[1]))
        for i in range(N_PERM):
            vals = []
            for sc, idxs, k, w in prepped:
                for p in rng.choice(idxs, size=k, replace=False):
                    r_, c_ = divmod(int(p), w)
                    sl = (slice(max(0, r_ - BUFFER_PX), r_ + BUFFER_PX + 1),
                          slice(max(0, c_ - BUFFER_PX), c_ + BUFFER_PX + 1))
                    win, m = sc["raw"][sl], sc["hv"][sl]
                    vv = win[m]
                    vals.append(float(vv.max()) if vv.size else 0.0)
            null[i] = np.mean(vals)
        perm_all = dict(n_points=len(pos), scenes=sorted(usable),
                        observed_mean=round(obs_all, 4),
                        null_mean=round(float(null.mean()), 4),
                        null_sd=round(float(null.std()), 4),
                        percentile_of_observed=round(float((null < obs_all).mean() * 100), 2),
                        p_value=float((null >= obs_all).mean()),
                        n_permutations=N_PERM)

    # ---- producers vs undeveloped ----------------------------------------
    def grp(m):
        v = [r["value"] for r in pos if r["maturity"] == m]
        return dict(n=len(v), median=round(float(np.median(v)), 4) if v else None,
                    mean=round(float(np.mean(v)), 4) if v else None,
                    values=[round(x, 4) for x in v])

    doc = dict(
        analysis_rules=dict(
            index="RAW clay ratio B11/B12 (clay_ratio_raw.tif), before per-scene _norm",
            deposit_value="MAX raw index within a 3-pixel buffer of the MRDS point",
            null_policy="outside footprint or fully masked -> null, never 0",
            brine_rule="code_list contains BR, or name matches /brine|marsh|lake/i",
            excluded_rule='dev_stat == "Plant" (processing facility, not an occurrence)',
            background="random high-confidence pixels; >=1 km from any MRDS Li point",
            frozen_before_results=True,
            seed=SEED,
        ),
        counts=dict(positives_scored=len(pos), brine=len(brine),
                    excluded_plant=len(excl),
                    background_pixels=int(bg.size),
                    control_aois=len([a for a in CONTROLS if a["id"] in scenes]),
                    lithium_aois=len([a for a in LITHIUM_AOIS if a["id"] in scenes])),
        cross_scene_auc=round(auc, 3) if auc is not None else None,
        auc_ci95_site_bootstrap=ci,
        pr_auc=round(ap, 3) if ap is not None else None,
        enrichment_top5pct=enrich,
        permutation_clayton_valley=perm,
        permutation_all_lithium_scenes=perm_all,
        duplicates_dropped=dropped_dupes,
        producers=grp("producer"),
        undeveloped=grp("undeveloped"),
        deposits=records,
        brine_sites=[dict(site=r["site"], value=r["value"], status=r["status"],
                          aoi=r["aoi"]) for r in brine],
        note_on_old_pvalue=("The previously reported p = 6.56e-08 was computed over "
                            "pixels, treating neighbouring pixels in a 3x3 buffer as "
                            "independent samples. It is superseded by the site-level "
                            "bootstrap CI and the spatial permutation test here."),
    )
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=1)

    print(f"\ncross-scene AUC {doc['cross_scene_auc']}  CI95 {ci}  PR-AUC {doc['pr_auc']}")
    print(f"enrichment@top5% {enrich}x   permutation {perm}")
    print(f"producers {doc['producers']['n']} vs undeveloped {doc['undeveloped']['n']}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

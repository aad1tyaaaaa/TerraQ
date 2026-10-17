#!/usr/bin/env python3
"""
product/target_finder.py
========================
S2 — derive discrete exploration targets from a job's lithium raster.

Method (all thresholds documented here, nothing tuned per-scene):
  1. Consider only HIGH-CONFIDENCE pixels: the index evaluated (> 0) and, when a
     confidence raster exists, confidence >= 0.99 (i.e. rock, not vegetation /
     water / cloud / nodata).
  2. Keep pixels at or above the 95th percentile of those valid pixels.
  3. Label 4-connected components (scipy.ndimage.label).
  4. Drop clusters smaller than MIN_PIXELS (see below) — single bright pixels are
     usually sensor noise or a building edge, not an alteration halo.

MIN_PIXELS = 6. At the engine's adaptive resolution (20-40 m/px, so roughly
0.0004-0.0016 km^2 per pixel) that is about 0.25-1 ha: small enough to keep a real
outcrop, large enough to discard isolated speckle. Documented rather than tuned.

Ranking: peak percentile DESC, then area_km2 DESC. Peak leads because the question
is "how anomalous does this get", and area breaks ties toward the larger halo.

Honest framing: a target is a cluster of relatively high surface-alteration index
within ONE scene. It is not a deposit, not a probability, and brine lithium under a
playa cannot appear here at all.

Output: <job>/targets.json  (additive; never touches result.json or the cache key)
"""
from __future__ import annotations
import os, json, math

import numpy as np
import rasterio
from rasterio.transform import xy as raster_xy
from pyproj import Transformer

PERCENTILE = 95.0
MIN_PIXELS = 6
MAX_TARGETS = 12


def _nearest_reference(lat, lon, deposits):
    """Closest MRDS reference site, with great-circle distance in km."""
    best, best_km = None, None
    for name, dlat, dlon in deposits:
        dy = (dlat - lat) * 111.32
        dx = (dlon - lon) * 111.32 * math.cos(math.radians(lat))
        km = math.hypot(dx, dy)
        if best_km is None or km < best_km:
            best, best_km = name, km
    return (best, round(best_km, 2)) if best is not None else (None, None)


def find_targets(job_dir: str, deposits=None) -> dict:
    tif = os.path.join(job_dir, "lithium_prospectivity.tif")
    if not os.path.isfile(tif):
        return {"ok": False, "error": "no lithium raster for this job"}

    try:
        from scipy import ndimage
    except ImportError:
        return {"ok": False, "error": "scipy not available"}

    with rasterio.open(tif) as src:
        arr = src.read(1).astype("float32")
        transform, crs = src.transform, src.crs
        px_w, px_h = abs(transform.a), abs(transform.e)   # metres (UTM)

    valid = arr > 0
    conf_tif = os.path.join(job_dir, "confidence.tif")
    conf = None
    if os.path.isfile(conf_tif):
        try:
            with rasterio.open(conf_tif) as cs:
                conf = cs.read(1).astype("float32")
            if conf.shape == arr.shape:
                valid &= conf >= 0.99          # high-confidence pixels only
        except Exception:
            conf = None

    if not valid.any():
        return {"ok": True, "targets": [], "note": "no high-confidence pixels in this AOI",
                "params": _params()}

    thr = float(np.percentile(arr[valid], PERCENTILE))
    mask = valid & (arr >= thr)
    labels, n = ndimage.label(mask)
    if n == 0:
        return {"ok": True, "targets": [], "note": "no clusters above threshold",
                "params": _params()}

    px_km2 = (px_w * px_h) / 1_000_000.0
    to_wgs = Transformer.from_crs(crs.to_string(), "EPSG:4326", always_xy=True)
    all_valid_vals = arr[valid]

    targets = []
    for lab in range(1, n + 1):
        sel = labels == lab
        npx = int(sel.sum())
        if npx < MIN_PIXELS:
            continue
        rows, cols = np.where(sel)
        # Centroid weighted by index value, so it sits on the bright core.
        wts = arr[sel]
        rc = float((rows * wts).sum() / wts.sum())
        cc = float((cols * wts).sum() / wts.sum())
        x, y = raster_xy(transform, rc, cc)
        lon, lat = to_wgs.transform(x, y)

        peak = float(arr[sel].max())
        peak_pct = float((all_valid_vals < peak).mean() * 100)
        mean_conf = (float(conf[sel].mean()) if conf is not None and conf.shape == arr.shape
                     else None)
        near, near_km = _nearest_reference(lat, lon, deposits or [])

        targets.append({
            "centroid_lat": round(lat, 5),
            "centroid_lon": round(lon, 5),
            "area_km2": round(npx * px_km2, 4),
            "pixels": npx,
            "peak_score": round(peak, 3),
            "peak_percentile": round(peak_pct, 1),
            "mean_score": round(float(arr[sel].mean()), 3),
            "mean_confidence": round(mean_conf, 3) if mean_conf is not None else None,
            "nearest_reference_site": near,
            "nearest_reference_km": near_km,
        })

    # Rank: peak percentile DESC, then area DESC.
    targets.sort(key=lambda t: (-t["peak_percentile"], -t["area_km2"]))
    targets = targets[:MAX_TARGETS]
    for i, t in enumerate(targets, 1):
        t["id"] = f"T{i}"
        t["rank"] = i

    # The index saturates: many pixels reach the max value, so peak_percentile
    # often ties across every cluster. Say so instead of implying the ranking
    # discriminated on peak when it actually fell through to area.
    peaks = {t["peak_percentile"] for t in targets}
    ranking_note = (
        "peak_percentile is identical for all targets (the index saturates at the "
        "top of this scene), so ranking is effectively by area."
        if len(peaks) <= 1 and targets else
        "ranked by peak_percentile, then area_km2."
    )

    return {
        "ok": True,
        "targets": targets,
        "ranking_note": ranking_note,
        "params": _params(threshold_value=round(thr, 4)),
        "note": ("Clusters of relatively high surface-alteration index within THIS "
                 "scene. Not deposits, not probabilities. Brine lithium beneath a "
                 "playa cannot be detected optically and will never appear here."),
    }


def _params(threshold_value=None):
    return {
        "percentile": PERCENTILE,
        "min_pixels": MIN_PIXELS,
        "max_targets": MAX_TARGETS,
        "connectivity": "4-connected (scipy.ndimage.label)",
        "confidence_filter": "confidence >= 0.99 (rock) when confidence.tif exists",
        "ranking": "peak_percentile DESC, then area_km2 DESC",
        "threshold_value": threshold_value,
    }


def ensure_targets(job_dir: str, deposits=None) -> dict:
    """Load <job>/targets.json, generating it on first request."""
    path = os.path.join(job_dir, "targets.json")
    if os.path.isfile(path):
        try:
            return json.load(open(path))
        except (ValueError, OSError):
            pass
    out = find_targets(job_dir, deposits)
    try:
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
    except OSError:
        pass
    return out


if __name__ == "__main__":
    import sys, csv
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pts = []
    for fn, c in [("mrds_lithium.csv", "Li"), ("mrds_vanadium.csv", "V")]:
        p = os.path.join(ROOT, "data", "ground_truth", fn)
        if os.path.exists(p):
            for r in csv.DictReader(open(p)):
                pts.append((f"{c}:{r['site'].strip().rstrip('.')}",
                            float(r["lat"]), float(r["lon"])))
    for d in sys.argv[1:]:
        res = find_targets(d, pts)
        print(f"\n=== {d} ===")
        if not res.get("ok"):
            print("  ", res.get("error")); continue
        print("   params:", json.dumps(res["params"]))
        for t in res["targets"]:
            print(f"   {t['id']:3s} {t['centroid_lat']:.4f},{t['centroid_lon']:.4f} "
                  f"peak={t['peak_percentile']:5.1f}pct area={t['area_km2']:.3f}km2 "
                  f"near={t['nearest_reference_site']} ({t['nearest_reference_km']}km)")

#!/usr/bin/env python3
"""
product/sentinel_engine.py
==========================
Coordinates -> Sentinel-2 -> mineral-alteration prospectivity overlays.

Product engine: an agency supplies a location (lat/lon + radius). The engine
auto-fetches the best cloud-free Sentinel-2 L2A data (mosaicking adjacent tiles
so the output is never half-blank), computes established mineral-alteration
spectral indices, and returns georeferenced overlays + an honest report.

Outputs (in <out>/):
    rgb.png                      true-colour basemap
    lithium_prospectivity.png    clay / Al-OH alteration (rock/pegmatite Li indicator)
    vanadium_prospectivity.png   iron-oxide + mica composite (LOW-confidence V proxy)
    brine_favorability.png       playa / evaporite basin flag (INDIRECT brine clue)
    confidence.png               data-quality / confidence mask
    *.tif                        georeferenced GeoTIFFs (for GIS)
    result.json                  scene metadata + honest capability caveats

HONEST SCOPE (also embedded in result.json):
  * Lithium layer detects clay-hosted / pegmatite Li ALTERATION HALOS via the
    2200 nm Al-OH absorption (S2 B11/B12). It does NOT detect brine lithium
    (dissolved in groundwater under playas) or any buried / non-surface deposit
    — that is a physical limit of optical remote sensing, requiring geophysics.
  * Brine-favorability is an INDIRECT basin/evaporite flag, not a detection.
  * Vanadium is a weak surface proxy (iron-oxide + mica); many V ores
    (e.g. black-shale hosted) are spectrally invisible. Treat as low confidence.
  * All "prospectivity" values are normalised alteration scores in [0,1],
    NOT calibrated probabilities and NOT a guarantee of mineralisation.

No authentication required: public Earth Search STAC + open `sentinel-cogs` AWS.
"""

from __future__ import annotations
import os, sys, json, time, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

# Remote COG reads over the public S3 bucket are cold-cache slow: a first read
# of a band routinely takes ~20-25 s. A 20 s timeout therefore fails legitimate
# reads, so give GDAL enough room and let it retry the underlying HTTP range
# requests itself before we retry the whole read.
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("VSI_CACHE", "TRUE")
os.environ.setdefault("GDAL_NUM_THREADS", "ALL_CPUS")

import urllib.request
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.transform import from_origin, rowcol
from rasterio.enums import Resampling
from pyproj import Transformer

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
# Reflectance bands (scaled /10000) + SCL scene-classification layer (class index).
NEEDED = ["blue", "green", "red", "nir", "swir16", "swir22", "rededge1", "scl"]
# Sentinel-2 SCL classes to reject (clouds/shadow/snow/water/saturated/dark/nodata).
SCL_BAD = {0, 1, 2, 3, 6, 8, 9, 10, 11}


# ---------------------------------------------------------------------------
# 1. Scene discovery
# ---------------------------------------------------------------------------
def search_scenes(bbox, start, end, max_cloud=10.0, limit=20):
    body = {
        "collections": ["sentinel-2-l2a"],
        "bbox": list(bbox),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "limit": limit,
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }
    req = urllib.request.Request(
        STAC_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        feats = json.load(r).get("features", [])
    if not feats:
        raise RuntimeError(
            f"No Sentinel-2 scene for bbox={bbox} {start}..{end} cloud<{max_cloud}%."
            " Try a wider date range or higher --max-cloud.")
    return feats


def _utm_epsg_for(lon, lat):
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:32{6 if lat >= 0 else 7}{zone:02d}"


# ---------------------------------------------------------------------------
# 2. Mosaicked, reprojected band reads onto a common 20 m UTM grid
# ---------------------------------------------------------------------------
def _pick_overview(src, target_res):
    """
    Index of the coarsest COG overview that is still at least as fine as the
    grid we are about to build, or None to use full resolution.

    The target grid is typically 40-50 m while the source bands are 10 m (RGB /
    NIR) or 20 m (SWIR / SCL), so reading full resolution downloads up to 16x
    more bytes than the output can represent. Sentinel-2 COGs ship overviews
    (2/4/8/16), so we pull the pre-decimated pyramid level instead.
    """
    try:
        native = float(src.res[0])
        overviews = src.overviews(1) or []
    except Exception:
        return None
    level = None
    for i, factor in enumerate(overviews):
        if native * factor <= target_res + 1e-6:
            level = i
    return level


def _read_band_onto_grid(href, crs, transform, width, height,
                         resampling=Resampling.bilinear, target_res=None):
    """Warp one remote COG onto the exact target grid (any source UTM zone)."""
    for attempt in range(3):
        try:
            level = None
            if target_res:
                with rasterio.open(href) as probe:
                    level = _pick_overview(probe, target_res)
            # header is already in the VSI cache, so reopening is cheap
            src = (rasterio.open(href, overview_level=level) if level is not None
                   else rasterio.open(href))
            with src:
                with WarpedVRT(src, crs=crs, transform=transform,
                               width=width, height=height,
                               resampling=resampling) as vrt:
                    return vrt.read(1).astype("float32")
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"read failed {href}: {e}")
            time.sleep(2)


def read_mosaic(items, bbox, target_res=20.0, max_tiles=4):
    """Mosaic up to max_tiles items (cloud-sorted) to fill the bbox grid."""
    epsg = _utm_epsg_for((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    tf = Transformer.from_crs("EPSG:4326", epsg, always_xy=True)
    xs = [tf.transform(bbox[0], bbox[1])[0], tf.transform(bbox[2], bbox[3])[0]]
    ys = [tf.transform(bbox[0], bbox[1])[1], tf.transform(bbox[2], bbox[3])[1]]
    W, E, S, N = min(xs), max(xs), min(ys), max(ys)
    width = int(round((E - W) / target_res))
    height = int(round((N - S) / target_res))
    transform = from_origin(W, N, target_res, target_res)

    bands = {b: np.zeros((height, width), "float32") for b in NEEDED}
    filled = np.zeros((height, width), bool)
    used = []
    for item in items:
        if filled.mean() > 0.99 or len(used) >= max_tiles:
            break
        assets = item["assets"]
        if not all(b in assets for b in NEEDED):
            continue
        # read swir16 first to find this tile's valid pixels
        try:
            probe = _read_band_onto_grid(assets["swir16"]["href"], epsg,
                                         transform, width, height,
                                         target_res=target_res)
        except RuntimeError:
            continue
        new = (probe > 0) & (~filled)
        if new.sum() < 0.01 * probe.size:   # negligible new coverage
            continue
        # Read the remaining bands into a staging dict first: a transient read
        # failure on one band must skip this tile, not abort the whole request
        # (another tile may still cover the same ground).
        # These reads are network-latency-bound (remote COGs over https), and
        # rasterio releases the GIL during IO, so fetching the bands concurrently
        # cuts the wall-clock cost of a tile to roughly one band read.
        todo = [b for b in NEEDED if b != "swir16"]
        staged = {}
        try:
            with ThreadPoolExecutor(max_workers=len(todo)) as pool:
                futs = {
                    pool.submit(
                        _read_band_onto_grid, assets[b]["href"], epsg, transform,
                        width, height,
                        Resampling.nearest if b == "scl" else Resampling.bilinear,
                        target_res
                    ): b
                    for b in todo
                }
                for fut in as_completed(futs):
                    staged[futs[fut]] = fut.result()
        except RuntimeError as e:
            print(f"  ! skipping tile {item['id']}: {e}", flush=True)
            continue
        bands["swir16"][new] = probe[new]
        for b, arr in staged.items():
            bands[b][new] = arr[new]
        filled |= new
        used.append({"id": item["id"], "date": item["properties"]["datetime"][:10],
                     "cloud": item["properties"]["eo:cloud_cover"]})
    for b in bands:
        if b == "scl":
            continue                       # SCL is a class index, not reflectance
        bands[b] = bands[b] / 10000.0      # S2 L2A DN -> reflectance
    return bands, transform, epsg, float(filled.mean()), used


# ---------------------------------------------------------------------------
# 3. Mineral-alteration indices + prospectivity
# ---------------------------------------------------------------------------
def compute_indices(b):
    eps = 1e-6
    # Continuum-removed Al-OH (2200 nm) absorption depth.
    # Build a continuum line from B08 (842 nm) through B11 (1610 nm), extrapolate
    # it to B12 (2190 nm), then measure how far B12 sits below that continuum.
    # depth > 0  => a real 2200 nm absorption (clay / sericite / Li-clay), and it
    # is far less sensitive to overall SWIR brightness/slope than a raw B11/B12 ratio.
    slope = (2190.0 - 1610.0) / (1610.0 - 842.0)        # ≈ 0.755
    cont2190 = b["swir16"] + slope * (b["swir16"] - b["nir"])
    clay_depth = np.clip(1.0 - b["swir22"] / (cont2190 + eps), 0.0, 1.0)
    return dict(
        ndvi=(b["nir"] - b["red"]) / (b["nir"] + b["red"] + eps),
        clay=b["swir16"] / (b["swir22"] + eps),          # legacy ratio (kept for reference)
        clay_depth=clay_depth,                            # continuum-removed depth (primary Li)
        ironoxide=b["red"] / (b["blue"] + eps),          # ferric iron / gossan
        ferrous=b["swir16"] / (b["nir"] + eps),          # ferrous iron
        mica=b["rededge1"] / (b["swir22"] + eps),        # mica/phyllosilicate context
        brightness=(b["red"] + b["green"] + b["blue"]) / 3.0,
    )


def _norm(x, mask, lo=2, hi=98):
    v = x[mask]
    if v.size == 0:
        return np.zeros_like(x)
    a, b = np.percentile(v, lo), np.percentile(v, hi)
    return np.clip((x - a) / (b - a + 1e-9), 0, 1)


def prospectivity(b, idx):
    """Return dict of [0,1] score maps + masks."""
    valid = (b["swir16"] > 0) & (b["swir22"] > 0) & (b["red"] > 0)
    veg = idx["ndvi"] > 0.25
    water = (idx["ndvi"] < -0.1) & (b["nir"] < 0.05)
    # Sentinel-2 SCL mask: drop clouds / shadow / snow / water / saturated / nodata.
    scl = b.get("scl")
    scl_bad = np.isin(scl.astype(np.int16), list(SCL_BAD)) if scl is not None \
        else np.zeros_like(valid)
    rock = valid & ~veg & ~water & ~scl_bad

    def pctl(arr, p):
        return np.percentile(arr[rock], p) if rock.any() else 0.0

    # Salt flat / playa: bright + low Al-OH absorption (evaporite, not clay)
    playa = rock & (idx["brightness"] > pctl(idx["brightness"], 85)) \
        & (idx["clay"] < pctl(idx["clay"], 55))

    # Lithium = clay/Al-OH alteration via the B11/B12 ratio (rock/pegmatite hosted).
    # NOTE: a continuum-removed depth index (idx['clay_depth']) was tried and
    # benchmarked WORSE on real MRDS deposits (ROC-AUC 0.46 vs 0.82) — Sentinel-2's
    # 2 SWIR bands can't support true continuum removal — so the ratio is kept.
    li = _norm(idx["clay"], rock)
    # Vanadium proxy = iron-oxide + mica composite (LOW confidence)
    v = 0.6 * _norm(idx["ironoxide"], rock) + 0.4 * _norm(idx["mica"], rock)
    v = _norm(v, rock)
    # Brine favorability = indirect playa/evaporite flag (NOT a detection)
    brine = _norm(idx["brightness"], rock) * playa.astype("float32")

    for s in (li, v):
        s[~rock] = 0.0
    confidence = np.where(rock, 1.0, 0.0).astype("float32")
    confidence[veg] = 0.2
    return dict(li=li.astype("float32"), v=v.astype("float32"),
                brine=brine.astype("float32"), rock=rock, playa=playa,
                confidence=confidence)


# ---------------------------------------------------------------------------
# 4. Rendering & GeoTIFF
# ---------------------------------------------------------------------------
def _stretch(x, lo=2, hi=98):
    m = x > 0
    if m.sum() == 0:
        return np.zeros_like(x)
    a, b = np.percentile(x[m], lo), np.percentile(x[m], hi)
    return np.clip((x - a) / (b - a + 1e-9), 0, 1)


def render(bands, P, deposits, out, meta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(out, exist_ok=True)
    rgb = np.dstack([_stretch(bands["red"]), _stretch(bands["green"]),
                     _stretch(bands["blue"])])
    rock = P["rock"]

    def overlay(score, title, cmap, fname, thr=0.45, marks=None):
        fig, ax = plt.subplots(figsize=(9, 9))
        ax.imshow(rgb)
        m = np.ma.masked_where(~rock | (score < thr), score)
        im = ax.imshow(m, cmap=cmap, alpha=0.55, vmin=thr, vmax=1.0)
        for (name, r, c, kind) in (marks or []):
            col = "cyan" if kind == "rock" else "magenta"
            ax.plot(c, r, "o", mfc="none", mec=col, mew=2, ms=13)
            ax.annotate(name, (c, r), color=col, fontsize=7,
                        xytext=(5, 5), textcoords="offset points")
        plt.colorbar(im, ax=ax, fraction=0.046, label="prospectivity (0-1)")
        ax.set_title(title); ax.axis("off")
        plt.tight_layout(); plt.savefig(os.path.join(out, fname), dpi=130,
                                        bbox_inches="tight"); plt.close()

    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(rgb)
    for (name, r, c, kind) in deposits:
        col = "cyan" if kind == "rock" else "magenta"
        ax.plot(c, r, "o", mfc="none", mec=col, mew=2, ms=13)
    ax.set_title(f"Sentinel-2 RGB  ({meta['date_range']})  coverage={meta['coverage']*100:.0f}%")
    ax.axis("off"); plt.tight_layout()
    plt.savefig(os.path.join(out, "rgb.png"), dpi=130, bbox_inches="tight"); plt.close()

    overlay(P["li"], "Lithium prospectivity — clay/Al-OH alteration (2200 nm)\n"
            "rock-hosted & pegmatite indicator; NOT brine Li", "viridis",
            "lithium_prospectivity.png", marks=deposits)
    overlay(P["v"], "Vanadium prospectivity — iron-oxide + mica composite\n"
            "LOW CONFIDENCE proxy; black-shale V is not detectable", "magma",
            "vanadium_prospectivity.png", marks=deposits)
    overlay(P["brine"], "Brine-favorability (INDIRECT) — playa / evaporite basin\n"
            "a follow-up-with-geophysics flag, NOT a lithium detection", "cividis",
            "brine_favorability.png", thr=0.3)

    fig, ax = plt.subplots(figsize=(9, 9))
    im = ax.imshow(P["confidence"], cmap="Greens", vmin=0, vmax=1)
    plt.colorbar(im, ax=ax, fraction=0.046, label="confidence")
    ax.set_title("Confidence (rock=high; vegetation/water/nodata=low)")
    ax.axis("off"); plt.tight_layout()
    plt.savefig(os.path.join(out, "confidence.png"), dpi=130, bbox_inches="tight"); plt.close()


def save_geotiff(score, transform, epsg, path):
    h, w = score.shape
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1,
                       dtype="float32", crs=epsg, transform=transform,
                       compress="deflate") as dst:
        dst.write(score.astype("float32"), 1)


# ---------------------------------------------------------------------------
# 5. Top-level run
# ---------------------------------------------------------------------------
def run(lat, lon, km, out, start="2022-06-01", end="2024-10-31",
        max_cloud=10.0, deposits_latlon=None, target_res=None):
    half = km / 111.0
    bbox = (lon - half, lat - half, lon + half, lat + half)
    # Adaptive resolution: keep the output grid ~<=800px so remote reads use COG
    # overviews and stay fast. 20 m floor preserves the SWIR native resolution.
    if target_res is None:
        target_res = max(20.0, round(km * 2000.0 / 600.0 / 10.0) * 10.0)
    print(f"[1/5] Search Sentinel-2 over ({lat:.4f},{lon:.4f}) +-{km}km  res={target_res:.0f}m ...")
    feats = search_scenes(bbox, start, end, max_cloud)
    print(f"      {len(feats)} candidate scenes (best cloud {feats[0]['properties']['eo:cloud_cover']:.1f}%)")

    print("[2/5] Reading + mosaicking bands ...")
    bands, transform, epsg, coverage, used = read_mosaic(feats, bbox, target_res=target_res)
    print(f"      grid={bands['swir16'].shape}  coverage={coverage*100:.0f}%  tiles={len(used)}")
    if coverage < 0.05:
        raise RuntimeError(
            "Could not fetch usable Sentinel-2 data for this area (network too "
            "slow/unreliable, or no valid pixels). Try again, pick a cached "
            "preset, or use a smaller radius.")

    print("[3/5] Indices + prospectivity ...")
    idx = compute_indices(bands)
    P = prospectivity(bands, idx)

    deposits, tf = [], Transformer.from_crs("EPSG:4326", epsg, always_xy=True)
    for d in (deposits_latlon or []):
        name, dlat, dlon = d[0], d[1], d[2]
        x, y = tf.transform(dlon, dlat); r, c = rowcol(transform, x, y)
        if 0 <= r < P["li"].shape[0] and 0 <= c < P["li"].shape[1]:
            kind = "playa" if P["playa"][r, c] else "rock"
            deposits.append((name[:16], int(r), int(c), kind))

    print("[4/5] Rendering ...")
    meta = {"date_range": f"{start}..{end}", "tiles_used": used,
            "coverage": coverage, "crs": epsg, "grid": list(P["li"].shape),
            "bbox_lonlat": bbox, "rock_fraction": float(P["rock"].mean()),
            "playa_fraction": float(P["playa"].mean()),
            "capability_note": (
                "Lithium = clay/Al-OH alteration (rock/pegmatite only; NOT brine "
                "or buried Li). Brine-favorability is an indirect basin flag. "
                "Vanadium is a low-confidence iron+mica proxy. Scores are "
                "normalised [0,1], not calibrated probabilities.")}
    render(bands, P, deposits, out, meta)

    print("[5/5] GeoTIFFs + result.json ...")
    for key, fn in [("li", "lithium_prospectivity.tif"),
                    ("v", "vanadium_prospectivity.tif"),
                    ("brine", "brine_favorability.tif")]:
        save_geotiff(P[key], transform, epsg, os.path.join(out, fn))
    # Additive: a georeferenced confidence raster so the console can rebuild the
    # confidence overlay for a cached job without re-running the whole engine.
    save_geotiff(P["confidence"], transform, epsg, os.path.join(out, "confidence.tif"))
    # Additive: the RAW clay ratio, before _norm()'s per-scene percentile stretch.
    # Required for any cross-scene comparison: _norm clips the top 2% to exactly
    # 1.0 — which is where deposits sit — so the normalised raster cannot be
    # inverted back to a comparable value. Nothing reads this in the live app.
    save_geotiff(idx["clay"], transform, epsg, os.path.join(out, "clay_ratio_raw.tif"))

    # Additive: bare, georeferenced RGBA overlays for the Explorer console.
    # Existing decorated PNGs above are untouched — this writes <out>/overlays/.
    try:
        from overlay_export import export_overlays, confidence_summary_from
        rgb_arr = np.dstack([_stretch(bands["red"]), _stretch(bands["green"]),
                             _stretch(bands["blue"])])
        meta.update(export_overlays(out, P=P, transform=transform, epsg=epsg,
                                    rgb=rgb_arr))
        meta["confidence_summary"] = confidence_summary_from(P=P)
    except Exception as e:                      # never fail a run over an overlay
        print(f"      ! overlay export skipped: {e}")
        meta["overlay_corners"] = None
        meta["overlay_layers"] = []

    if deposits:
        meta["deposit_check"] = []
        liv, vv = P["li"][P["rock"]], P["v"][P["rock"]]
        for (name, r, c, kind) in deposits:
            lval = float(np.mean(P["li"][max(0, r-1):r+2, max(0, c-1):c+2]))
            vval = float(np.mean(P["v"][max(0, r-1):r+2, max(0, c-1):c+2]))
            meta["deposit_check"].append({
                "name": name, "type": kind,
                "li_score": round(lval, 3),
                "li_percentile": round(float((liv < lval).mean()*100), 1),
                "v_score": round(vval, 3)})
            print(f"      {name:18s} [{kind:5s}] Li {lval:.2f} ({float((liv<lval).mean()*100):.0f}pct)  V {vval:.2f}")

    with open(os.path.join(out, "result.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\nDone -> {out}/")
    return meta, P


def main():
    ap = argparse.ArgumentParser(description="Sentinel-2 mineral prospectivity engine")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--km", type=float, default=12.0)
    ap.add_argument("--out", default="outputs/product_demo")
    ap.add_argument("--start", default="2022-06-01")
    ap.add_argument("--end", default="2024-10-31")
    ap.add_argument("--max-cloud", type=float, default=10.0)
    a = ap.parse_args()
    run(a.lat, a.lon, a.km, a.out, a.start, a.end, a.max_cloud)


if __name__ == "__main__":
    main()

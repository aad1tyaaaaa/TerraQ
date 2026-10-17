#!/usr/bin/env python3
"""
product/overlay_export.py
=========================
Produce *bare* map overlays for the Explorer console — additive, nothing here
replaces or renames an existing engine output.

Why this module exists
----------------------
The engine's existing PNGs (`lithium_prospectivity.png`, `rgb.png`, …) are
matplotlib FIGURES: they carry a title, axes and a colorbar, they are padded by
`bbox_inches="tight"`, and their pixel size (e.g. 1059x1157) has no relation to
the data grid (596x480). They are great to look at and impossible to georeference,
so draping them on a slippy map puts the data in the wrong place.

This module writes, into `<job>/overlays/`:
  * grid-aligned RGBA PNGs with NO decoration,
  * alpha = 0 wherever there is no valid data (so the basemap shows through),
  * reprojected to EPSG:4326, which makes the image axis-aligned in lon/lat.

That last point matters. The engine computes in UTM (e.g. EPSG:32611). A UTM
rectangle is NOT a lon/lat rectangle — at Silver Peak, ~0.63 deg off the zone's
central meridian, grid convergence is ~0.39 deg, which smears a 24 km AOI by
roughly 160 m if you simply stretch the native raster onto a lon/lat bounding
box. Warping to EPSG:4326 first removes that error, and the four corners we
return are then exactly the image corners.

Returned corners are ordered for MapLibre's `image` source:
    [top-left, top-right, bottom-right, bottom-left], each [lon, lat].

Usage
-----
    from overlay_export import export_overlays
    corners = export_overlays(job_dir)                     # from GeoTIFFs
    corners = export_overlays(job_dir, P=P, transform=t, epsg=e, rgb=rgb)
"""
from __future__ import annotations
import os
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

OVERLAY_SUBDIR = "overlays"

# Score layers that have a GeoTIFF counterpart and so can be rebuilt for an
# already-cached job. 'rgb' and 'confidence' only exist for jobs produced by the
# newer engine (which also writes rgb.tif / confidence.tif).
SCORE_LAYERS = [
    ("li",    "lithium_prospectivity.tif",  "lithium.png",    "magma"),
    ("v",     "vanadium_prospectivity.tif", "vanadium.png",   "cividis"),
    ("brine", "brine_favorability.tif",     "brine.png",      "PuRd"),
]


def _colorize(a: np.ndarray, valid: np.ndarray, cmap_name: str) -> np.ndarray:
    """score[0..1] + validity mask -> RGBA uint8 with transparent nodata."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import colormaps
    cmap = colormaps[cmap_name]
    rgba = (cmap(np.clip(np.nan_to_num(a), 0, 1)) * 255).astype("uint8")
    # Fade the very low end out too, so a dark basemap stays readable instead of
    # being covered by a solid "zero" wash.
    alpha = np.where(valid, np.clip(60 + 195 * np.clip(a, 0, 1), 0, 255), 0)
    rgba[..., 3] = alpha.astype("uint8")
    return rgba


def _warp_to_4326(arr: np.ndarray, src_transform, src_crs, nodata=np.nan):
    """Reproject a 2-D float array to EPSG:4326. Returns (array, transform, w, h)."""
    h, w = arr.shape
    dst_transform, dw, dh = calculate_default_transform(
        src_crs, "EPSG:4326", w, h, *rasterio.transform.array_bounds(h, w, src_transform))
    dst = np.full((dh, dw), nodata, dtype="float32")
    reproject(
        source=arr.astype("float32"), destination=dst,
        src_transform=src_transform, src_crs=src_crs,
        dst_transform=dst_transform, dst_crs="EPSG:4326",
        src_nodata=nodata, dst_nodata=nodata,
        resampling=Resampling.bilinear,
    )
    return dst, dst_transform, dw, dh


def _corners(transform, width, height):
    """4326 image corners for MapLibre: TL, TR, BR, BL."""
    west, south, east, north = rasterio.transform.array_bounds(height, width, transform)
    return [[west, north], [east, north], [east, south], [west, south]]


def _write_png(path: str, rgba: np.ndarray) -> None:
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def export_overlays(job_dir: str, P=None, transform=None, epsg=None, rgb=None) -> dict:
    """
    Write bare, georeferenced RGBA overlays into <job_dir>/overlays/.

    Called two ways:
      * from sentinel_engine.run() with the in-memory arrays (P/transform/epsg/rgb)
      * for an already-cached job with no arguments -> rebuilt from its GeoTIFFs

    Returns {"overlay_corners": [...], "overlay_layers": [...]} — never raises for
    a missing layer, it just reports the ones it could build.
    """
    out_dir = os.path.join(job_dir, OVERLAY_SUBDIR)
    os.makedirs(out_dir, exist_ok=True)
    built, corners = [], None

    def handle(arr, valid, cmap, fname, src_transform, src_crs):
        nonlocal corners
        a = arr.astype("float32").copy()
        a[~valid] = np.nan
        warped, dst_t, dw, dh = _warp_to_4326(a, src_transform, src_crs)
        vmask = ~np.isnan(warped)
        rgba = _colorize(np.nan_to_num(warped), vmask, cmap)
        _write_png(os.path.join(out_dir, fname), rgba)
        built.append(fname)
        if corners is None:
            corners = _corners(dst_t, dw, dh)

    if P is not None and transform is not None and epsg is not None:
        # ---- in-memory path (new runs) -------------------------------------
        rock = P["rock"]
        for key, _tif, fname, cmap in SCORE_LAYERS:
            handle(P[key], rock, cmap, fname, transform, epsg)

        # Confidence is defined everywhere (it IS the quality map), so its mask
        # is "pixel was observed at all", not "rock".
        conf = P["confidence"]
        handle(conf, np.isfinite(conf), "Greens", "confidence.png", transform, epsg)

        if rgb is not None:
            rgb8 = (np.clip(rgb, 0, 1) * 255).astype("uint8")
            alpha = np.where(rgb.sum(axis=2) > 0, 255, 0).astype("uint8")
            rgba = np.dstack([rgb8, alpha])
            # warp each channel, then restack
            chans = []
            for i in range(4):
                w_, dst_t, dw, dh = _warp_to_4326(
                    rgba[..., i].astype("float32"), transform, epsg, nodata=0.0)
                chans.append(np.nan_to_num(w_))
                if corners is None:
                    corners = _corners(dst_t, dw, dh)
            _write_png(os.path.join(out_dir, "rgb.png"),
                       np.dstack(chans).clip(0, 255).astype("uint8"))
            built.append("rgb.png")
    else:
        # ---- cached-job path: rebuild from whatever GeoTIFFs exist ----------
        for key, tif, fname, cmap in SCORE_LAYERS:
            path = os.path.join(job_dir, tif)
            if not os.path.isfile(path):
                continue
            with rasterio.open(path) as src:
                arr = src.read(1).astype("float32")
                handle(arr, arr > 0, cmap, fname, src.transform, src.crs)

    return {"overlay_corners": corners, "overlay_layers": built}


def confidence_summary_from(P=None, meta=None) -> dict:
    """
    Fractions of the AOI by data quality, as percentages.

    Derived from the same masks the engine already computes, so it adds no new
    assumptions: 'high' = rock pixels the index could be evaluated on, 'low' =
    vegetation (confidence 0.2 in the engine), 'masked' = everything else
    (water, cloud, shadow, nodata).
    """
    if P is not None:
        conf = P["confidence"]
        total = conf.size
        high = float((conf >= 0.99).sum()) / total * 100.0
        low = float(((conf > 0.0) & (conf < 0.99)).sum()) / total * 100.0
        masked = 100.0 - high - low
    elif meta is not None:
        # Fallback for an older cached result.json that has only the fractions.
        high = float(meta.get("rock_fraction", 0.0)) * 100.0
        low = None
        masked = 100.0 - high if high else None
    else:
        return {}
    return {
        "high_pct": round(high, 1),
        "low_pct": round(low, 1) if low is not None else None,
        "masked_pct": round(masked, 1) if masked is not None else None,
        "definition": ("high = valid rock pixels the index was evaluated on; "
                       "low = vegetation; masked = water / cloud / shadow / nodata"),
    }


if __name__ == "__main__":
    import sys, json
    for d in sys.argv[1:]:
        print(d, json.dumps(export_overlays(d), indent=2))

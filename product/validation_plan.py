#!/usr/bin/env python3
"""
product/validation_plan.py
==========================
Frozen analysis plan for the validation study. Everything here was decided
BEFORE any engine run, so nothing below can be tuned to flatter a result.

Analysis rules
--------------
* Engine is used exactly as shipped. No parameter, threshold or _norm change.
* Cross-scene comparison uses the RAW lithium index (clay_ratio_raw.tif,
  B11/B12) BEFORE the per-scene percentile stretch. The normalised raster is
  scene-relative and clips the top 2% to 1.0, so it cannot be compared across
  scenes.
* Deposit value = MAX raw index within a 3-pixel buffer of the MRDS point.
* Outside footprint, or no valid pixel in the buffer -> null. Never 0.
* Site classification (objective, from MRDS fields only):
    brine      : code_list contains token "BR", or site name matches
                 /brine|marsh|lake/i   -> reported separately, NOT a positive
    excluded   : dev_stat == "Plant"   -> processing facility, not an occurrence
    positive   : everything else carrying the LI commodity token
    producer   : dev_stat in {Producer, Past Producer}
    undeveloped: dev_stat in {Prospect, Occurrence, Unknown}

Control selection criteria (applied before running)
---------------------------------------------------
* desert controls: >= 60 km from any MRDS lithium point and >= 30 km from any
  MRDS record of any commodity (screened against a 3,000-record MRDS pull).
* disturbed control: aggregate / limestone quarrying ground, deliberately NOT a
  copper or gold mine, since those carry genuine clay alteration and would not
  isolate the disturbance confound.
* All AOIs use the same 12 km radius as the Clayton Valley run.
"""

RADIUS_KM = 12.0

# ---- Task 1: controls -----------------------------------------------------
CONTROLS = [
    dict(id="C1", name="Railroad Valley",  lat=38.42, lon=-115.92, kind="desert",
         why="closed-basin playa margin, central NV; 147.8 km from nearest Li record"),
    dict(id="C2", name="Dry Lake Valley",  lat=37.95, lon=-114.92, kind="desert",
         why="eastern NV basin-fill; 117.5 km from nearest Li record"),
    dict(id="C3", name="Newark Valley",    lat=39.55, lon=-115.95, kind="desert",
         why="central-east NV basin; 155.9 km from nearest Li record"),
    dict(id="C4", name="Tule Desert",      lat=36.95, lon=-114.60, kind="desert",
         why="SE NV desert; 89.4 km from any MRDS record, 68.9 km from Li"),
    dict(id="C5", name="Gabbs Valley",     lat=38.95, lon=-118.85, kind="desert",
         why="western NV basin; 64.0 km from any MRDS record, 167.1 km from Li"),
    dict(id="D1", name="Sloan aggregate",  lat=35.95, lon=-115.22, kind="disturbed",
         why="limestone/aggregate quarrying ground S of Las Vegas; tests whether "
             "bare disturbed rock alone scores high. Not a Cu/Au mine by design."),
]

# ---- Task 2A: lithium AOIs ------------------------------------------------
# L0 repeats the Clayton Valley preset so its RAW raster exists for the
# cross-scene pool; L1-L3 are Nevada lithium outside Clayton Valley.
LITHIUM_AOIS = [
    dict(id="L0", name="Clayton Valley / Silver Peak", lat=37.7499, lon=-117.6342,
         why="the original validation area; re-run to obtain the raw raster"),
    dict(id="L1", name="Kings Valley / Ed Deposit", lat=41.7617, lon=-118.1050,
         why="McDermitt caldera margin; 3 undeveloped sites, one coded CLY LI "
             "(clay-hosted) — a non-brine setting, which Clayton Valley is not"),
    dict(id="L2", name="McDermitt Mine", lat=41.9190, lon=-117.8120,
         why="past producer carrying the LI token, separate scene from L1"),
    dict(id="L3", name="Death Valley margin", lat=37.105, lon=-117.599,
         why="two undeveloped sites (Prospect + Occurrence) ~19 km apart, both "
             "inside a single 12 km AOI"),
]

BRINE_NAME_RE = r"brine|marsh|lake"


def classify(site_name: str, dev_stat: str, code_list: str) -> str:
    """-> 'brine' | 'excluded' | 'positive'  (frozen rule, see module docstring)."""
    import re
    codes = (code_list or "").split()
    if "BR" in codes or re.search(BRINE_NAME_RE, site_name or "", re.I):
        return "brine"
    if (dev_stat or "").strip().lower() == "plant":
        return "excluded"
    return "positive"


def maturity(dev_stat: str) -> str:
    return "producer" if (dev_stat or "") in ("Producer", "Past Producer") else "undeveloped"

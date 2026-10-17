# Mineral Prospectivity Product (Sentinel-2)

Turn a **location** into **mineral-alteration prospectivity images** for lithium
and vanadium, using free Sentinel-2 satellite data (no login required).

This is the product layer built on top of the research pipeline. Unlike the
original Hyperion experiment, it (a) uses imagery that actually covers deposits,
(b) fetches data live by coordinate, and (c) states its limits honestly.

---

## What it produces

For any location you give it:

| Output | Meaning |
|---|---|
| `lithium_prospectivity.png/.tif` | Clay / Al-OH alteration (2200 nm). **Rock-hosted & pegmatite Li indicator.** |
| `vanadium_prospectivity.png/.tif` | Iron-oxide + mica composite. **Low-confidence V proxy.** |
| `brine_favorability.png/.tif` | Playa / evaporite basin flag. **Indirect** brine hint, not a detection. |
| `rgb.png` | True-colour Sentinel-2 basemap. |
| `confidence.png` | Data quality (rock = high; vegetation/water/nodata = low). |
| `result.json` | Scene metadata, coverage, deposit checks, and capability caveats. |

### Honest scope (important — say this to clients)
- **Detects:** clay-hosted / pegmatite lithium *alteration at the surface*.
- **Does NOT detect:** brine lithium (dissolved underground — a physical limit of
  optical remote sensing; needs geophysics), buried deposits, or black-shale vanadium.
- "Prospectivity" is a normalised 0–1 alteration score, **not** a calibrated
  probability and **not** a guarantee of mineralisation.

---

## How to run

Use the project Python environment (see project memory / `requirements`):
needs `numpy, scipy, scikit-learn, matplotlib, rasterio, pyproj` (+ `torch,
pennylane` for the quantum research layer, not needed for the product engine).

### Option A — standalone clickable demo (no Node needed)
```bash
<venv>/bin/python product/server.py
# open http://localhost:8765  → click the map → Analyze
```

### Option B — command line (one location)
```bash
<venv>/bin/python product/sentinel_engine.py --lat 37.7499 --lon -117.6342 --km 12 --out outputs/my_area
```

### Option C — inside the terraq dashboard
1. Start the engine API (Option A — it also serves the JSON API).
2. In `terraq/`: `pnpm install && pnpm dev`
3. Open `http://localhost:3000/live-analysis`
4. (If the engine runs elsewhere, set `NEXT_PUBLIC_ENGINE_URL`.)

---

## Validation so far (Clayton Valley, Nevada)

Scored against real USGS MRDS deposits (`data/ground_truth/`):

- **Silver Peak rock-hosted lithium occurrences → ~98th percentile** of the
  lithium-prospectivity map. The engine lights up the known mine.
- **Silver Peak Marsh (brine playa) → low score** — correct: brine Li has no
  surface signature.

This is a credibility check on a small set of points, **not** a calibrated
accuracy figure. Densifying validation (more deposits + EarthChem geochemistry)
is future work.

---

## Files
- `sentinel_engine.py` — core: fetch Sentinel-2 (Earth Search STAC) → indices → overlays.
- `server.py` — standalone web demo + JSON API.
- `../terraq/app/live-analysis/page.tsx` — dashboard page calling the API.

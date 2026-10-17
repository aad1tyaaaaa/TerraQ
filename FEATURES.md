# TerraQ — Feature Reference

*Quantum Intelligence for Earth Exploration*

**Status:** current as of 2026-10-08. Every number in this document was read from a
real artifact in this repo (`outputs/summary/metrics.txt`, `outputs/benchmark_console.json`,
or a live engine response). Nothing here is aspirational unless it says "Not built".

---

## 1. What the system is

A hybrid quantum–classical pipeline for lithium and vanadium **surface-alteration**
prospecting from satellite imagery, plus a live web console over it.

Three layers that share no code path:

| Layer | Folder | Role | Quantum? | Runnable today |
|---|---|---|---|---|
| Research pipeline | `src/`, `experiments/` | Benchmarks 7 detection methods on NASA EO-1 Hyperion | ✅ PennyLane **simulator** | ❌ see §7 |
| Product engine | `product/` | lat/lon → live Sentinel-2 → mineral indices → maps | ❌ classical | ✅ |
| Web console | `terraq/` | Dashboard (6 tabs) + Explorer console | ❌ UI | ✅ |

> The quantum work lives **only** in the research pipeline. Every map the website
> renders comes from the classical Sentinel-2 engine. These must never be
> presented as quantum results.

---

## 2. Research pipeline — measured results

Hold-out Scene 3 (never seen in training). Source: `outputs/summary/metrics.txt`.
Train positive rate 48.3 %.

| Method | Description | AUC | F1 | MCC |
|---|---|---|---|---|
| A | PCA only (classical baseline) | 0.7492 | 0.6482 | 0.3157 |
| B | PCA + classical autoencoder | 0.7617 | 0.6621 | 0.3214 |
| **C** ★ | **PCA + 6-qubit QAE** | **0.7702** | **0.6751** | **0.3510** |
| F | QAA hybrid (unsupervised) | 0.6869 | 0.4512 | 0.3515 |
| D | QSVM (ZZFeatureMap kernel) | 0.5128 | 0.5442 | 0.0661 |
| C3 | QAE → VQC | 0.5256 | 0.5927 | 0.1379 |
| C2 | QAE → QSVM | 0.4710 | 0.5483 | −0.0572 |

**The honest headline.** Method C is the best performer, beating the classical
autoencoder B by **+0.009 AUC (0.770 vs 0.762)**. McNemar C vs B gives
χ² = 2.62, **p = 0.106 — not statistically significant**. All quantum models run
on a **simulator**, never real hardware.

Use exactly these figures everywhere: **0.770 / +0.009 AUC / p = 0.106 / simulator**.

**Labelling (non-circular).** Labels come from band-ratio absorption depths computed
on the imagery itself — LiCI at 2200 nm, VMI at 2265 nm — thresholded at the
**75th percentile of the training set only** (`label_strategy="band_ratio_percentile"`,
`label_percentile=75.0`). Those indices are never fed to the classifier. Earlier
docs described this as Otsu thresholding; that was wrong and has been corrected.

---

## 3. Product engine (`product/`)

Classical. Turns a coordinate into prospectivity rasters from live Sentinel-2 L2A
(Earth Search STAC, public S3, no login).

### Outputs per job
`outputs/jobs/<md5(lat,lon,km)[:10]>/`

| File | Note |
|---|---|
| `lithium_prospectivity.png/.tif` | Clay / Al-OH ratio (B11/B12). Rock-hosted & pegmatite Li. |
| `vanadium_prospectivity.png/.tif` | Iron-oxide + mica composite. **Low confidence.** |
| `brine_favorability.png/.tif` | Playa / evaporite flag. **Indirect hint, not a detection.** |
| `confidence.tif` | Data-quality raster *(added for the console)* |
| `rgb.png`, `confidence.png` | Decorated matplotlib figures (titles, axes, colorbars) |
| `overlays/*.png` | **Bare** grid-aligned RGBA, warped to EPSG:4326 *(added for the console)* |
| `result.json` | Metadata + caveats |

> The original PNGs are matplotlib **figures**, not georeferenced rasters — their pixel
> size (e.g. 1059×1157) has no relation to the data grid (596×480). They cannot be draped
> on a map. `overlays/` exists for that: bare RGBA, alpha=0 for nodata, reprojected to
> EPSG:4326 so the image is axis-aligned in lon/lat. This removes the UTM grid-convergence
> skew (~0.39° at Silver Peak, ≈160 m across a 24 km AOI).

### `result.json` fields
`date_range`, `tiles_used[{id,date,cloud}]`, `coverage`, `crs`, `grid[2]`,
`bbox_lonlat[4]`, `rock_fraction`, `playa_fraction`, `capability_note`,
`deposit_check[]`, plus **added**: `overlay_corners` (4 lon/lat corners, TL→BL),
`overlay_layers[]`, `confidence_summary{high_pct,low_pct,masked_pct,definition}`.

Existing fields were never renamed or removed. Caches predating the additions are
backfilled in place on request — the cache key is unchanged.

### HTTP API (port 8765)

| Route | Purpose |
|---|---|
| `GET /` | Standalone demo page (no Node needed) |
| `POST /api/analyze` | `{lat,lon,km}` → run or serve from cache |
| `GET /api/jobs` | All cached analyses (centre from bbox, time from mtime) |
| `GET /api/point?job=&lat=&lon=` | Li + V index/percentile at one point |
| `GET /api/sample?job=&lat=&lon=` | **S1** — click-anywhere lithium score + `confidence_class` |
| `GET /api/targets?job=` | **S2** — anomaly clusters; writes `<job>/targets.json` |
| `GET /jobs/x/<job>/<file>` | Serves job files, incl. `overlays/` |

Runs are serialized behind one lock, so prewarm before a demo, never during.

### `targets.json` (S2, generated on first request)
Per job, alongside `result.json`; does not affect the cache key.

Method: high-confidence pixels only (index > 0 and confidence ≥ 0.99) → pixels at or
above the **95th percentile** → **4-connected** components (`scipy.ndimage.label`) →
drop clusters under **6 pixels** (≈0.25–1 ha at 20–40 m/px; documented, not tuned) →
keep the top 12. Ranked by peak percentile, then area.

Fields: `id`, `rank`, `centroid_lat/lon`, `area_km2`, `pixels`, `peak_score`,
`peak_percentile`, `mean_score`, `mean_confidence`, `nearest_reference_site`,
`nearest_reference_km`, plus `params` and `ranking_note`.

> **Honest caveat the UI repeats:** the index saturates, so `peak_percentile` is
> identical (98.0) across every cluster and the ranking falls through to area. The
> response says so explicitly rather than implying peak discriminated.

Measured on Clayton Valley: target **T10 is 0.24 km from the Silver Peak mine**,
T3 1.43 km from Foote Lithium, T11 1.05 km from Silver Peak Lithium Operations.

### Validation — `outputs/benchmark_console.json`
Fixed AOI: Clayton Valley / Silver Peak. ROC-AUC **0.80** vs background
(26 positive px, 5000 background px).

| Site | Status | Percentile |
|---|---|---|
| Silver Peak | scored | **98.0** |
| Foote Lithium Brine Operation | scored | **97.1** |
| Silver Peak Marsh (brine playa) | scored | 45.2 |
| Silver Peak Lithium Operations | **masked** | — |
| Foote Mineral Co | **masked** | — |
| 6 others (4 V, 2 Li) | **outside footprint** | — |

> `masked` and `outside_footprint` mean *no usable data*, not *low prospectivity*.
> They render as **"—"**, never 0. The older `outputs/sentinel2_results/benchmark.json`
> was computed on a different AOI and **disagrees** with this file (it reports Silver
> Peak Lithium Operations at 98.0). Only `benchmark_console.json` feeds the console.

---

## 4. Web console (`terraq/`)

Next.js 16 · React 19 · Tailwind 4 · Radix UI · MapLibre GL 5.9.

### Routes
| Route | Content |
|---|---|
| `/` | Landing page — video hero, scroll sequence |
| `/dashboard` | 6 tabs: Dashboard, Live Analysis, Satellite Maps, Method Comparison, How It Works, Data & Methodology |
| `/live-analysis` | Standalone Leaflet live-analysis panel |
| `/explorer` | **Exploration console** (below) |
| `/api/geology`, `/api/geocode`, `/api/explain` | Thin server shims |

### Explorer console
- **Globe** — MapLibre globe projection. NASA GIBS Blue Marble to z8
  (`GoogleMapsCompatible_Level8`), EOX Sentinel-2 cloudless above z8, as two raster
  layers with explicit min/max zoom. Attribution always visible.
- **Reference sites** — 11 USGS MRDS occurrences (7 Li, 4 V) from the committed
  ground-truth CSVs. Labelled as a *validation reference set*, not a global database.
- **Overlays** — real georeferenced rasters positioned by `overlay_corners`.
  5 switchable layers; unavailable ones are disabled with a tooltip.
- **Location panel** — 4 tabs (Overview / Spectral / Geology / Insights). Every field
  carries a source comment in code. Missing values render "—" with the reason.
- **Targets** — ranked from `benchmark_console.json` only.
- **Limitations box** — always visible on every tab.
- **Mineral chips** — Lithium active; Vanadium active with "low confidence";
  Cu/Ni/Co/Au/Fe/REE visible but disabled with "Roadmap".
- **Offline mode** — if the engine is unreachable: amber "engine offline" badge,
  Analyze disabled, cached results still render.
- **Click-anywhere score (S1)** — clicking inside an analysed AOI samples the lithium
  raster at that point (reprojected to the raster CRS) and shows index, percentile and
  confidence class. Outside the footprint it says *"Not analysed — run Analyze Region
  here"*; a masked pixel says so rather than showing 0.
- **Detected targets (S2)** — numbered markers on the globe plus a ranked list.
  Clicking one flies there and re-runs S1 at its centroid.
- **Geology (S5)** — Macrostrat unit, lithology, age with attribution; 5 s timeout,
  in-memory cache, graceful "no data" and "could not reach" states. Fetched once in the
  shell and shared with the AI summary.
- **AI summary (S3)** — "AI-generated summary from measured values" with a badge naming
  the source (Groq / Groq fallback / Gemini / template). See §4a.
- **Temporal panel** — "Coming soon" card, deliberately never a trend line.

### 4a. AI explanation (S3) — how it is kept honest

Server-side only (`explorer/server/explain.ts`); keys are read via `process.env` and
never reach the browser.

**Provider chain:** `GROQ_MODEL` → `GROQ_FALLBACK_MODEL` → Gemini (only if
`GEMINI_API_KEY` is set) → deterministic template. The template needs no network, so
the demo works with **zero keys**.

Both Groq model IDs (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`) were verified against
Groq's live `/openai/v1/models` endpoint before use.

**Grounding is enforced twice:**
1. The prompt carries only measured fields and forbids introducing any new number.
2. A post-check scans the reply for numbers absent from the input; a violation is
   **discarded** and the chain falls through to the next provider, then the template.

Also rejected: replies that hit the token ceiling (`finish_reason === 'length'`) or do
not end in sentence punctuation — a fragment would drop the required next step.

`reasoning_effort: 'low'`, `temperature: 0.2`, 8 s timeout per provider, and only the
final answer is displayed — reasoning output is never shown. Explanations are cached
per target id, so repeat clicks make no API call (measured 1.40 s → 0.01 s).

> **One deviation from the brief, deliberate:** `max_completion_tokens` is **700**, not
> ~200. gpt-oss bills reasoning tokens against the same budget, and at 200 the visible
> answer was cut off mid-sentence, losing the mandated next step. The prompt still
> constrains length to 3–4 sentences.

### Honesty rules enforced in the UI
1. Every number traces to `result.json`, the benchmark, `metrics.txt`, or a live response.
2. The score is a relative 0–1 index shown as a percentile or `score 0.xxx` —
   **never a probability, never "87 %"**.
3. No prospectivity trend over time, ever.
4. Brine lithium is stated as undetectable by optical sensing.
5. Vanadium always carries "low confidence".
6. Quantum claims fixed at 0.770 / +0.009 AUC / p = 0.106 / simulator.
7. No API keys in client code or any committed file.

---

## 5. Environment variables

Names only — values live in `terraq/.env.local`, which is git-ignored
(`terraq/.gitignore:11`). `terraq/.env.example` lists the same names, empty.

| Variable | Scope | Required? |
|---|---|---|
| `NEXT_PUBLIC_ENGINE_URL` | client | no (defaults to `:8765`) |
| `LLM_PROVIDER` | server | no |
| `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_FALLBACK_MODEL` | server | no |
| `GEMINI_API_KEY` | server | no |

The whole app works with every one of these empty — the AI summary falls back to a
deterministic template and everything else is key-free.

---

## 6. Running it

```bash
# one-time
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cd terraq && npm install && cd ..

# run (dashboard :3000, engine :8765 — reads the printed URLs)
bash start.sh
bash stop.sh

# fill the cache BEFORE a demo (~7 min, serial)
./.venv/bin/python product/prewarm.py

# regenerate validation + console data after an engine change
./.venv/bin/python product/benchmark_console.py
./.venv/bin/python product/export_console_data.py
```

Requires Python **3.12** (pennylane 0.38 + numpy<2 do not resolve on 3.13/3.14) and Node 18+.

---

## 7. Honest scope and known gaps

**Physical limits.** Surface alteration only. Cannot see brine lithium dissolved under
a playa, buried deposits, or black-shale vanadium. "Prospectivity" is a normalised 0–1
score within one scene — not calibrated, not comparable across scenes, not proof of
mineralisation. A high score is a lead for field follow-up.

**Not built.**
- Research pipeline cannot run: `data/processed/*.npy` Hyperion cubes are absent, and
  the `step1_convert_hyperion.py` / `step2_load_usgs_spectra.py` preprocessing scripts
  do not exist anywhere in this repo. The committed figures come from an earlier run.
- `npm run lint` fails — `eslint` was never a dependency and there is no config.
  Pre-existing, unrelated to any recent work.
- `npm run typecheck` reports **2 pre-existing errors**
  (`terraq-chart.tsx` recharts `itemStyle`, `scroll-sequence.tsx` `onerror`).
  `next.config.mjs` sets `ignoreBuildErrors: true`, so `npm run build` passes regardless.
- `TerraQ_Quantum_Prospecting.pdf` still contains the old p=0.0009 / AUC 0.776 claims.
  It is a binary and was not edited — regenerate it from the corrected `docs/`.
- Deposits layer is 11 validation sites, not a global MRDS database.
- No real quantum hardware; no per-pixel spectra exported.

---

## 8. Reproducibility

| Setting | Value |
|---|---|
| Seed | 42 (NumPy, Python, PyTorch) |
| PCA components | 25 |
| QAE qubits / layers | 6 / 3 |
| QAE training samples | 200 balanced |
| QAA qubits / latent / trash | 6 / 2 / 4 |
| Backend | PennyLane simulator |
| Test set | Scene 3 (temporal hold-out) |
| Labels | 75th-percentile LiCI + VMI, training set only, OR logic |

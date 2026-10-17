# Quantum-Enhanced Mineral Detection — Pitch Deck Content

> **Purpose**: Investor/agency pitch deck for TerraQ Quantum Mineral Detection Platform
> **Tone**: Technical credibility + commercial viability + honest scope
> **Source of truth**: every number here traces to `FEATURES.md`, which in turn reads from
> `outputs/summary/metrics.txt`, `outputs/benchmark_console.json`, or a live engine response.
> If a figure is not in `FEATURES.md`, it does not go on a slide.

---

## SLIDE 1 — Title

**TerraQ Quantum Mineral Detection**
*AI-Powered Critical Mineral Prospecting from Satellite Imagery*

- Tagline: "De-risk exploration. Reduce field costs. Find lithium faster."
- Logo / visual: Satellite → AI Engine → Prospectivity Map

---

## SLIDE 2 — The Problem

**Critical Mineral Exploration is Expensive, Slow, and Risky**

- Global lithium demand growing 20-25% annually (IEA 2024); supply pipeline is 7-12 years from discovery to production
- Traditional geological exploration costs $5-50M per project before first drill decision
- 95% of early-stage exploration targets fail — most value is destroyed in the field
- India imports 100% of lithium; KABIL (Khanij Bidesh India Ltd) actively seeking domestic sources
- Only 15% of Earth's prospective terrain has been geologically mapped at useful resolution

**The opportunity**: satellite data is free and global — the bottleneck is interpretation, not data.

---

## SLIDE 3 — Our Solution

**Satellite-to-Map Mineral Intelligence Platform**

| Input | Processing | Output |
|-------|-----------|--------|
| Click a point on the globe OR enter coordinates | Live Sentinel-2 fetch + spectral indices + masking | Prospectivity rasters, ranked targets, confidence layer |

- Fully automated: no geology PhD required to operate
- Works on free satellite data (Sentinel-2 L2A: global, 5-day revisit, 10-20m resolution, no login)
- Validated against USGS MRDS occurrences (real, independently catalogued sites)
- Results in minutes, not months — and cached results in seconds

---

## SLIDE 4 — System Architecture: Three Layers

**What is quantum, what is not — stated upfront**

| Layer | Folder | Role | Quantum? | Runnable today |
|-------|--------|------|----------|----------------|
| **Research pipeline** | `src/`, `experiments/` | Benchmarks 7 detection methods on NASA EO-1 Hyperion | ✅ PennyLane **simulator** | ❌ (input cubes not in repo) |
| **Product engine** | `product/` | lat/lon → live Sentinel-2 → mineral indices → maps | ❌ classical | ✅ |
| **Web console** | `terraq/` | Dashboard (6 tabs) + Exploration console | ❌ UI | ✅ |

> **The rule we never break**: the quantum work lives *only* in the research pipeline.
> Every map the website renders comes from the classical Sentinel-2 engine.
> These are never presented as quantum results.

*Why say this out loud?* Because every agency buyer has been burned by a vendor who
labelled a classical product "quantum". Drawing the line ourselves is the credibility.

---

## SLIDE 5 — Method Exploration: What We Tried

**Systematic comparison of 7 architectures on hyperspectral data**
*Hold-out Scene 3, never seen in training. Source: `outputs/summary/metrics.txt`.*

| Method | Architecture | AUC | F1 | MCC | Verdict |
|--------|-------------|-----|----|----|---------|
| A — PCA only | PCA(25) → Ensemble | 0.7492 | 0.6482 | 0.3157 | Classical baseline |
| B — PCA + Classical AE | PCA(25) → CAE → Ensemble | 0.7617 | 0.6621 | 0.3214 | +0.013 over A |
| **C — PCA + Quantum AE** ★ | **PCA(25) → 6-qubit QAE → Ensemble** | **0.7702** | **0.6751** | **0.3510** | **Best (+0.009 over B)** |
| F — QAA Hybrid | Quantum Associative Memory (unsupervised) | 0.6869 | 0.4512 | 0.3515 | Interesting, not competitive |
| C3 — QAE → VQC | QAE latent → VQC | 0.5256 | 0.5927 | 0.1379 | ✗ Unstable |
| D — QSVM direct | PCA(25) → ZZFeatureMap → QSVM | 0.5128 | 0.5442 | 0.0661 | ✗ Near random |
| C2 — QAE → QSVM | QAE latent → QSVM | 0.4710 | 0.5483 | −0.0572 | ✗ Worse than chance |

**Winner**: Method C — PCA → Quantum Autoencoder → Classical Ensemble

**The honest headline**: Method C beats the classical autoencoder B by **+0.009 AUC
(0.7702 vs 0.7617)**. McNemar C vs B: **χ² = 2.62, p = 0.106 — not statistically
significant**. All quantum models ran on a **simulator**, never real hardware.

*Key insight*: Quantum adds value as a feature extractor (non-linear compression), NOT as
the final classifier. Pure quantum classifiers (QSVM, VQC) fail on high-dimensional
geospatial data at current qubit counts.

> **Canonical quantum figures — use these verbatim everywhere**:
> **0.770 AUC / +0.009 over classical / p = 0.106 / simulator.**

---

## SLIDE 6 — Training Architecture Deep Dive

**Three-Stage Pipeline**

```
Stage 1: Dimensionality Reduction
  198 spectral bands → PCA(25 components) → 87% variance retained
  Preprocessing: RobustScaler (outlier-resistant normalization)

Stage 2: Quantum Feature Extraction
  6-qubit Hardware-Efficient Ansatz (HEA)
  ├── Data encoding: RY(x[i] × 0.5) angle embedding
  ├── Entanglement: CNOT chain + long-range CZ(0,5)
  ├── Variational layers: 3 × [RY + CNOT + RZ]
  ├── Loss: Mineral-weighted MSE
  └── Output: 6-dimensional quantum latent space

Stage 3: Classical Ensemble Voting
  Soft-vote of 3 classifiers on quantum features:
  ├── Random Forest: 200 trees, depth=15, balanced
  ├── Gradient Boosting: 200 trees, lr=0.05, depth=5
  └── SVM-RBF: GridSearchCV(C=[0.1,1,10], γ=[scale,0.1])
```

---

## SLIDE 7 — Training Parameters & Reproducibility

| Parameter | Value | Why |
|-----------|-------|-----|
| PCA components | 25 | Retains 87% variance; higher adds noise |
| Qubits / layers | 6 / 3 | Matches latent dimension; diminishing returns beyond 3 layers |
| QAE epochs | 50 | Converges by ~35; patience=12 early stopping |
| QAE learning rate | 0.05 | Adam optimizer; tuned from {0.01, 0.05, 0.1} |
| Training samples | 200 (balanced) | Max feasible for quantum circuit (larger → prohibitive runtime) |
| QAA qubits / latent / trash | 6 / 2 / 4 | Unsupervised comparison arm |
| Spatial CV | 5-fold, 4×4 blocks | Prevents spatial autocorrelation leakage |
| Ensemble voting | Soft (probability) | Outperforms hard voting |
| Train positive rate | 48.3% | Near-balanced; no resampling needed |
| Test set | Scene 3 (temporal hold-out) | Never seen in training |
| Seed | 42 (NumPy, Python, PyTorch) | Fully reproducible runs |
| Backend | PennyLane **simulator** | No real quantum hardware used |

**Compute**: ~4 hours on CPU (PennyLane `default.qubit` simulator).

---

## SLIDE 8 — How We Labelled the Data (Non-Circular)

**The question every reviewer asks first: "where did your ground truth come from?"**

- Labels come from **band-ratio absorption depths computed on the imagery itself**
  — LiCI at 2200 nm (Al-OH / Li-clay) and VMI at 2265 nm (V-bearing mica)
- Thresholded at the **75th percentile of the training set only**
  (`label_strategy="band_ratio_percentile"`, `label_percentile=75.0`), then OR-combined
- **Those indices are never fed to the classifier** — the model sees PCA/QAE features only,
  so it cannot trivially recover its own labels

> **Correction we publish openly**: earlier versions of our docs described this as Otsu
> thresholding. That was wrong and has been corrected. We'd rather fix the record than
> have a reviewer find it.

**Reproducibility contract**: seed 42, PCA(25), QAE 6 qubits × 3 layers, 200 balanced
training samples, Scene 3 hold-out, PennyLane simulator. Every figure on Slide 5 is
regenerable from these settings.

---

## SLIDE 9 — Sentinel-2 Production System: Measured Results

**Fixed validation AOI: Clayton Valley / Silver Peak, Nevada — a known lithium district**
*Source: `outputs/benchmark_console.json` (26 positive px vs 5,000 background px)*

| Metric | Value | Meaning |
|--------|-------|---------|
| **ROC-AUC** | **0.80** | Known sites ranked significantly higher than background |
| Scored reference sites in top 3% | **2 of 3** | Silver Peak and Foote both ≥97th percentile |

**Site-by-site — including the ones we don't score well:**

| Site | Status | Percentile |
|------|--------|-----------|
| Silver Peak | scored | **98.0** |
| Foote Lithium Brine Operation | scored | **97.1** |
| Silver Peak Marsh (brine playa) | scored | 45.2 |
| Silver Peak Lithium Operations | **masked** | — |
| Foote Mineral Co | **masked** | — |
| 6 others (4 V, 2 Li) | **outside footprint** | — |

> `masked` and `outside_footprint` mean **no usable data**, not low prospectivity.
> They render as "—", never as 0. The brine playa scoring 45.2 is the expected result,
> not a failure: optical sensing cannot see lithium dissolved under a playa.

**Spectral Indices in Production**:
- Clay / Al-OH ratio (B11/B12): rock-hosted and pegmatite lithium alteration
- Iron-oxide + mica composite: vanadium indicator (**low confidence**, always labelled)
- Playa / evaporite flag: brine *favorability* — an indirect hint, not a detection
- NDVI + SCL masking: removes vegetation, water, cloud, snow contamination

---

## SLIDE 10 — From Map to Drill Target

**A heat map is not a decision. A ranked target list is.**

The engine converts rasters into discrete, rankable anomaly clusters (`targets.json`):

```
High-confidence pixels only (index > 0, confidence ≥ 0.99)
  → pixels at or above the 95th percentile
  → 4-connected components (scipy.ndimage.label)
  → drop clusters under 6 pixels (≈0.25–1 ha at 20–40 m/px)
  → keep the top 12, ranked by peak percentile, then area
```

Each target carries: centroid lat/lon, area km², pixel count, peak & mean score,
peak percentile, mean confidence, and **distance to the nearest known reference site**.

**Measured on Clayton Valley — the blind-ish sanity check:**

| Target | Nearest known deposit | Distance |
|--------|----------------------|----------|
| **T10** | **Silver Peak mine** | **0.24 km** |
| T11 | Silver Peak Lithium Operations | 1.05 km |
| T3 | Foote Lithium | 1.43 km |

> **Caveat the UI itself repeats**: the index saturates, so `peak_percentile` is identical
> (98.0) across every cluster and the ranking effectively falls through to area. The API
> response says this explicitly rather than implying peak score discriminated between
> targets. The cluster-size floor is documented, not tuned.

---

## SLIDE 11 — The Exploration Console

**A working product, not a notebook**
*Next.js 16 · React 19 · Tailwind 4 · Radix UI · MapLibre GL 5.9*

| Capability | What it does |
|-----------|--------------|
| **Globe** | MapLibre globe projection; NASA GIBS Blue Marble to z8, EOX Sentinel-2 cloudless above. Attribution always visible. |
| **Georeferenced overlays** | 5 switchable raster layers, positioned by true lon/lat corners — not screenshots pinned to a map |
| **Click-anywhere score** | Click inside an analysed area → lithium index, percentile and confidence class at that exact pixel |
| **Detected targets** | Numbered markers + ranked list; click one to fly there and re-sample |
| **Reference sites** | 11 USGS MRDS occurrences (7 Li, 4 V) — labelled a *validation reference set*, not a global database |
| **Geology context** | Macrostrat unit, lithology and age with attribution; 5 s timeout, cached, graceful "no data" state |
| **Location panel** | 4 tabs (Overview / Spectral / Geology / Insights); every field traceable to a source |
| **Mineral chips** | Lithium active · Vanadium active with "low confidence" · Cu/Ni/Co/Au/Fe/REE visible but disabled as "Roadmap" |
| **Limitations box** | Permanently visible on every tab — not hidden in a footnote |
| **Offline mode** | Engine unreachable → amber badge, Analyze disabled, cached results still render |
| **Temporal panel** | "Coming soon" card — deliberately never a fake trend line |

**Routes**: `/` landing · `/dashboard` (6 tabs) · `/live-analysis` · `/explorer` (console)

**Engineering detail that matters**: the original matplotlib PNGs are *figures*, not
georeferenced rasters — their pixel grid has no relation to the data grid. A separate
`overlays/` export writes bare RGBA reprojected to EPSG:4326, removing UTM grid-convergence
skew (~0.39° at Silver Peak, ≈160 m across a 24 km AOI).

---

## SLIDE 12 — AI Explanation Layer — Kept Honest by Construction

**Plain-language summaries of each target, grounded in measured values only**

```
Provider chain:  Groq (primary) → Groq (fallback) → Gemini (if key set) → deterministic template
                 └── the template needs no network, so the demo runs with ZERO API keys
```

**Grounding is enforced twice:**
1. The prompt carries only measured fields and forbids introducing any new number
2. A post-check scans the reply for numbers absent from the input — a violation is
   **discarded** and the chain falls through to the next provider, then the template

Also rejected: replies that hit the token ceiling or don't end in sentence punctuation
(a truncated answer would drop the mandated "next step" recommendation).

| Property | Value |
|----------|-------|
| Execution | Server-side only; keys never reach the browser |
| Settings | `temperature 0.2`, low reasoning effort, 8 s timeout per provider |
| Reasoning output | Never displayed — final answer only |
| Caching | Per target id — repeat clicks make no API call (**1.40 s → 0.01 s** measured) |
| Model IDs | Verified against Groq's live `/models` endpoint before use |

> We tell the audience this is "AI-generated summary from measured values", with a badge
> naming which provider produced it. An LLM that can invent a number is a liability in a
> geological product; so we built it so it structurally cannot.

---

## SLIDE 13 — Honesty Rules Enforced in the Product

**These are not slogans — they are enforced in the UI code**

1. Every number traces to `result.json`, the benchmark file, `metrics.txt`, or a live response
2. The score is a relative **0–1 index** shown as a percentile or `score 0.xxx` —
   **never a probability, never "87% chance of lithium"**
3. **No prospectivity trend over time, ever** (single-scene scores are not comparable)
4. Brine lithium is stated as undetectable by optical sensing
5. Vanadium always carries a "low confidence" label
6. Quantum claims fixed at **0.770 / +0.009 AUC / p = 0.106 / simulator**
7. No API keys in client code or any committed file

**Why this is a commercial asset, not modesty**: geological surveys have procurement
memories. The vendor who said 0.80 and meant it gets the second contract.

---

## SLIDE 14 — Honest Comparison: Hyperion vs Sentinel-2

| Dimension | Hyperion (Research) | Sentinel-2 (Production) |
|-----------|-------------------|------------------------|
| Spectral bands | 198 (hyperspectral) | 13 (multispectral) |
| SWIR coverage | Continuous 900-2500nm | 2 bands only (1610, 2190nm) |
| Spatial resolution | 30m | 10-20m |
| Coverage | 7.7km swath, retired 2017 | 290km swath, global, 5-day revisit |
| Best AUC | 0.770 (quantum pipeline, hold-out scene) | 0.800 (spectral index + masking, MRDS sites) |
| Validation target | Band-ratio percentile labels (non-circular) | Real USGS MRDS occurrences |
| Status | Research prototype (cannot currently run — see Slide 20) | **Production-ready** |

*Why the production system scores higher*: the two AUCs measure different things.
Hyperion's 0.770 is pixel-level agreement with imagery-derived labels on a hold-out scene.
Sentinel-2's 0.800 is separation of 26 catalogued deposit pixels from 5,000 background
pixels. The second is the number a mining client actually cares about; the first is the
number that tells us whether quantum features help.

---

## SLIDE 15 — Dataset Limitations (Current)

### Sentinel-2 Drawbacks
| Limitation | Impact | Mitigation Path |
|-----------|--------|----------------|
| Only 2 SWIR bands | Cannot resolve individual absorption features (Al-OH vs Li-OH vs Mg-OH) | Need EMIT/PRISMA/EnMAP hyperspectral |
| 20m SWIR resolution | Misses small outcrops < 400m² | Drone or aerial hyperspectral for detail |
| Optical only | Cannot detect subsurface brine lithium (under playas) | Gravity/EM geophysics data fusion |
| Atmospheric residuals | L2A correction imperfect in arid terrain | Custom atmospheric correction |
| Cloud contamination | Monsoon regions lose 40-60% dates | Multi-temporal compositing |
| Index saturation | Top clusters all pin at the 98th percentile — ranking falls through to area | Needs calibrated, continuous index |

### Hyperion Drawbacks (Research Dataset)
| Limitation | Impact | Status |
|-----------|--------|--------|
| Retired 2017 | No new acquisitions possible | Dead instrument |
| 7.7km swath | Missed Silver Peak deposit by 13km | Cannot re-acquire |
| 7 scenes only | Insufficient geographic diversity | Not generalizable |
| Noise (low SNR) | Bands 1-7, 58-78, 120-125 unusable | Required heavy destriping |
| Labels from imagery | Weaker than catalogued ground truth, though non-circular | Superseded by MRDS validation in production |

---

## SLIDE 16 — What We Need That Current Datasets Don't Provide

**The Gap Between Current Capability and Full Solution**

| Need | Why | Source |
|------|-----|--------|
| Continuous SWIR (2000-2500nm) | Distinguish Li-clay from generic Al-OH | EMIT (ISS), PRISMA (ASI), EnMAP (DLR) |
| Thermal infrared (8-12μm) | Silicate mineral identification | ASTER, Landsat TIRS, future HyTES |
| Subsurface sensing | Brine lithium is below surface | Airborne EM, gravity surveys |
| Field spectra (ground truth) | Calibrate satellite signatures | ASD FieldSpec campaigns |
| Drill-hole geochemistry | True grade validation | Mining company partnerships |
| Topographic correction | Shadow removal in mountainous terrain | LiDAR DEMs, SRTM correction |
| Multi-temporal stack | Seasonal vegetation change masking | Time-series analysis (12+ dates) |
| Higher spatial resolution | Sub-20m outcrop discrimination | WorldView-3 (commercial, 8 SWIR bands) |
| Full MRDS ingest | Our deposit layer is 11 validation sites, not a database | USGS bulk MRDS |

**Near-term roadmap** (< 6 months): EMIT integration (free, 285 bands, 60m) gives 10×
spectral improvement over Sentinel-2 in the SWIR.

---

## SLIDE 17 — Industry Use Cases: Mining

**Primary: Critical Mineral Exploration**

| Mineral Target | Method | Market | Status in product |
|---------------|--------|--------|-------------------|
| Lithium (hard-rock / clay) | Clay alteration mapping (hectorite, jadarite) | $22B EV battery supply chain | ✅ Active |
| Vanadium | Roscoelite / V-bearing muscovite detection | Vanadium redox flow batteries | ✅ Active, low confidence |
| Lithium (brine) | Evaporite surface indicators + playa mapping | Requires geophysics fusion | ⚠️ Favorability hint only |
| Copper-Gold porphyry | Phyllic/argillic alteration zones | $180B/yr global copper market | 🔜 Roadmap |
| Rare Earth Elements | Carbonatite alteration halos | Defence, electronics | 🔜 Roadmap |
| Nickel / Cobalt laterite | Iron-oxide + serpentine mapping | Battery cathodes | 🔜 Roadmap |

**Value Proposition for Mining Companies**:
- **Pre-competitive screening**: Rank 1000 km² areas before spending $1M on field teams
- **Greenfield targeting**: Identify previously unrecognized prospects in under-explored terrain
- **Tenement evaluation**: Due diligence on acquisition targets in days, not months
- **Brownfield expansion**: Find extensions to known deposits using spectral halos

---

## SLIDE 18 — Industry Use Cases: Beyond Mining

| Industry | Application | How Our Platform Helps |
|----------|-------------|----------------------|
| **Agriculture** | Soil mineral content mapping (K, P, Ca, Fe) | Precision fertilization → 15-20% input reduction |
| **Environmental** | Acid mine drainage detection, tailings monitoring | Regulatory compliance, real-time alerting |
| **Oil & Gas** | Surface mineralogy indicating hydrocarbon seepage | Carbonate/clay anomaly maps for exploration |
| **Construction** | Aggregate & building material prospecting | Locate limestone, sandstone, clay deposits |
| **Defence & Strategic** | Critical mineral supply chain intelligence | Identify resources in allied/contested regions |
| **Carbon Sequestration** | Mapping ultramafic rocks for mineral carbonation | Serpentinite/olivine detection for CCUS sites |
| **Water Resources** | Evaporite & clay mapping for aquifer characterization | Groundwater prospecting in arid regions |
| **Insurance/Finance** | Mining asset risk assessment from satellite | Portfolio due diligence at scale |

*Note: these are adjacency opportunities on the same engine. Only the mining use cases
above have been validated against ground truth today.*

---

## SLIDE 19 — How Our Product Helps: Value Proposition

**For Government Agencies (GSI, MECL, KABIL)**

| Current Process | With TerraQ |
|----------------|---------------|
| 2-3 year regional surveys | Nationwide screening in weeks |
| $2-10M per mapping campaign | < $50K for 100,000 km² analysis |
| Requires senior geologists in field | Any officer can operate the web platform |
| Results locked in reports | Interactive maps, exportable GeoTIFF layers |
| Single point-in-time | Re-runnable with each new satellite pass |

**For Exploration Companies**

| Pain Point | Our Solution |
|-----------|-------------|
| "Where do I start?" | Engine ranks your whole tenement by prospectivity index |
| "Which anomaly do I visit?" | Top-12 ranked target list with centroids and areas |
| "Is this prospect worth drilling?" | Index + percentile + confidence class, with limits stated |
| "My geologist retired" | Interpretation logic encoded in a reproducible pipeline |
| "Board wants faster results" | Minutes per AOI; cached AOIs return instantly |
| "We can't afford airborne surveys everywhere" | Free satellite data + targeted follow-up only where score is high |

---

## SLIDE 20 — Platform Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                  TerraQ Web Console (Next.js)                │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐   │
│  │ Globe + AOI  │  │ Overlays (5)  │  │ Targets + Panel  │   │
│  │ (MapLibre)   │  │ georeferenced │  │ + AI summary     │   │
│  └──────┬───────┘  └───────▲───────┘  └──────────────────┘   │
└─────────┼──────────────────┼──────────────────────────────────┘
          │ POST /api/analyze│ GET /api/sample · /api/targets
          ▼                  │
┌───────────────────────────────────────────────────────────────┐
│            Product Engine (Python, port 8765) — CLASSICAL     │
│   ┌────────┐   ┌──────────┐   ┌──────────┐   ┌───────────┐   │
│   │ Fetch  │ → │ Preproc  │ → │ Indices  │ → │ Score +   │   │
│   │Sentinel│   │ SCL mask │   │ Clay/Fe  │   │ Targets   │   │
│   └────────┘   └──────────┘   └──────────┘   └───────────┘   │
│   Outputs: *.tif · overlays/*.png · result.json · targets.json│
└───────────────────────────────────────────────────────────────┘
          │
          ▼
  AWS Earth Search STAC (free, no auth, global Sentinel-2 L2A)

┌───────────────────────────────────────────────────────────────┐
│     Research Pipeline (separate — QUANTUM, simulator only)     │
│     Hyperion 198 bands → PCA(25) → 6-qubit QAE → Ensemble      │
│     Benchmarks 7 methods. Does not feed the web console.       │
└───────────────────────────────────────────────────────────────┘
```

Runs are serialized behind a single lock — the cache is pre-warmed before a demo, never during.

---

## SLIDE 21 — Results Summary & Key Metrics

**Production System (Sentinel-2 — what ships to customers)**

| Metric | Score | Industry Context |
|--------|-------|-----------------|
| ROC-AUC | **0.80** | At the conventional ≥0.80 threshold for an actionable screening tool |
| Scored reference sites in top 3% | 2 of 3 | Silver Peak 98.0, Foote 97.1 percentile |
| Closest auto-detected target to a known mine | **0.24 km** | T10 ↔ Silver Peak mine |
| Processing time | Minutes per AOI | Cached AOIs return instantly |
| Validation set size | 26 positive px vs 5,000 background px | Small — a limitation we state, not hide |

**Research System (Hyperion + Quantum — innovation IP)**

| Metric | Score | Significance |
|--------|-------|-------------|
| Best AUC (Method C) | 0.7702 | Quantum AE provides +0.009 over classical AE (0.7617) |
| F1 / MCC (Method C) | 0.6751 / 0.3510 | Best of all 7 methods on both |
| McNemar C vs B | χ² = 2.62, **p = 0.106** | Quantum advantage **not statistically significant** |
| Hardware | PennyLane simulator | No real QPU runs to date |

**Interpretation**: Quantum advantage is *directionally positive but unproven* at 6 qubits
on a simulator. The commercial product ships the classical Sentinel-2 engine today;
quantum is a research track with a documented, honest p-value — not a sales claim.

---

## SLIDE 22 — Known Gaps: What Is Not Built

**We publish this slide. It is why the rest of the deck is believable.**

| Gap | Detail |
|-----|--------|
| Research pipeline cannot re-run today | The Hyperion `.npy` cubes and the two preprocessing scripts are not in the repo; committed figures come from an earlier run |
| No real quantum hardware | Everything is PennyLane simulator |
| Deposit layer is small | 11 validation sites, not a global MRDS ingest |
| No per-pixel spectra export | Users get indices, not full spectral curves |
| Brine, buried, and black-shale targets | Physically out of reach of optical surface sensing |
| Score is not calibrated | A normalised 0–1 index *within one scene* — not comparable across scenes, not proof of mineralisation |
| Legacy PDF out of date | `TerraQ_Quantum_Prospecting.pdf` still carries superseded p=0.0009 / AUC 0.776 claims; regenerate from corrected `docs/` |
| Build hygiene | `npm run lint` has no config; `typecheck` reports 2 pre-existing errors (build passes via `ignoreBuildErrors`) |

**A high score is a lead for field follow-up. It is not a discovery.**

---

## SLIDE 23 — Competitive Advantage & Moat

| Advantage | Detail |
|-----------|--------|
| **Quantum IP** | Quantum autoencoder as a geospatial feature extractor; benchmarked against 6 alternatives |
| **Honest benchmarking** | Real MRDS sites, published p-values, a "what isn't built" slide — credibility with geological agencies |
| **Free data dependency** | No imagery licensing (Sentinel-2 is ESA open-access, fetched from public S3 without login) |
| **Speed** | Minutes from coordinates to ranked targets; cached AOIs instant |
| **Runs with zero API keys** | Full demo works offline-ish — AI layer degrades to a deterministic template |
| **India-ready** | Works on any terrain; specifically targeting KABIL/GSI needs for domestic lithium |
| **Reproducible** | Seed-fixed, open metrics, auditable pipeline, every UI number traceable to a file |

---

## SLIDE 24 — Roadmap

| Phase | Timeline | Deliverable |
|-------|----------|-------------|
| **NOW** | Q4 2026 | Sentinel-2 prospectivity + ranked targets, exploration console, Clayton Valley validation |
| **Phase 2** | Q1 2027 | EMIT hyperspectral integration (285 bands), full MRDS ingest, India site validation |
| **Phase 3** | Q2 2027 | Multi-sensor fusion (Sentinel + EMIT + ASTER thermal), Cu/REE detection |
| **Phase 4** | Q3 2027 | Restore + extend research pipeline; real quantum hardware (IBM/IonQ), 20+ qubit QAE |
| **Phase 5** | Q4 2027 | Field validation campaigns, drill-hole correlation, calibrated cross-scene scores |

---

## SLIDE 25 — The Ask

**What we need to scale:**

1. **Pilot partnership** with a geological survey (GSI India / USGS / CSIRO) for field validation
2. **Access to EMIT/PRISMA data** for hyperspectral upgrade
3. **Drill-hole data partnership** with a mining company for true grade calibration
4. **Compute credits** for quantum hardware access (IBM Quantum Network)

**What we deliver:**
- Working platform TODAY processing any coordinates globally
- 0.80 AUC against catalogued MRDS sites; nearest auto-detected target 0.24 km from a producing mine
- Clear, honest limitations documented — including a published "not built" list
- Quantum research track with a transparent p-value, not an oversold claim

---

## SLIDE 26 — Team & Contact

[Your team details here]

- Built by TerraQ — quantum computing + geospatial AI
- Combining remote sensing expertise with quantum machine learning research
- Published methodology, reproducible benchmarks, open validation

---

## PRESENTER NOTES (Key talking points per slide)

### Slide 2 (Problem)
- "India has zero domestic lithium production. KABIL is spending hundreds of crores on overseas acquisitions. What if we could screen Indian terrain from satellites first?"
- "The paradox: satellite data is free and abundant — but interpreting 13+ spectral bands across millions of pixels requires AI, not human eyes."

### Slide 4 (Three Layers)
- "Before anything else: the website is classical. The quantum work is a separate research track. I'm telling you this in slide four because you'd find it in slide fourteen anyway."
- If asked *why keep the quantum arm at all*: "because the feature-extraction result is real and directionally positive — and because the hardware is improving faster than our dataset is."

### Slide 5 (Method Exploration)
- "We didn't build one model — we tested seven. Pure quantum classifiers fail at 6 qubits: QSVM scores 0.47, worse than a coin flip. We publish that."
- "Our quantum win is +0.009 AUC with p = 0.106. That is **not** significant, and I'd rather say so than have your technical reviewer say it for me."

### Slide 8 (Labelling)
- "Reviewers ask: did you train on your own labels? The indices that make the labels are never shown to the classifier. And we corrected our own earlier docs that mis-described this as Otsu."

### Slide 9 (Sentinel-2 Results)
- "0.80 AUC means: pick a random known deposit pixel and a random background pixel — 80% of the time we rank the deposit higher."
- "Two of three scored sites land at the 97th–98th percentile. The third is a brine playa at 45 — exactly where it should be, because you cannot see dissolved lithium with an optical sensor."
- On masked sites: "'—' means no usable data. We never print 0 for that. Printing 0 would be a lie that looks like a measurement."

### Slide 10 (Targets)
- "This is the slide that matters commercially. T10 is 240 metres from the Silver Peak mine — found by the algorithm, not placed there."
- "And note the caveat we ship *in the API response*: the index saturates, so ranking falls through to cluster area. We'd rather hand you that than let you discover it."

### Slide 12 (AI layer)
- "The LLM cannot introduce a number. If it does, we throw the answer away and fall through to the next provider, then to a template. In a geological product, a hallucinated grade is a lawsuit."

### Slide 15 (Limitations)
- "We cannot detect brine lithium — it's underground. We say this upfront. Our system finds hard-rock/clay-hosted lithium indicators. Brine requires geophysics."
- "This honesty builds trust with agencies who are tired of vendors overclaiming."

### Slide 19 (Value Proposition)
- "Current cost for regional geochemical surveys: ₹50-200 crore for a single state. Our platform screens all of Rajasthan in a weekend for under ₹5 lakh in compute."
- "We don't replace geologists — we tell them WHERE to look first."

### Slide 22 (Known Gaps)
- "Every pitch has this slide — most of them keep it in a drawer. Ours is in the deck because you will do diligence, and I'd rather you check my gaps than find them."
- Expect the question: *"The research pipeline can't run?"* → "Correct. The Hyperion cubes aren't in the repo and two preprocessing scripts are missing. The published figures are from an earlier run. Restoring that is Phase 4."

---

## APPENDIX — Technical Backup Slides

### A1: QAE Circuit Diagram
```
q0: ─RY(x₀)─CNOT─RZ─────────────CZ─ ─ ─ Measure
q1: ─RY(x₁)──●──CNOT─RZ──────────── ─ ─ Measure
q2: ─RY(x₂)──────●──CNOT─RZ──────── ─ ─ Measure
q3: ─RY(x₃)──────────●──CNOT─RZ──── ─ ─ Measure
q4: ─RY(x₄)──────────────●──CNOT─RZ─ ─ ─ Measure
q5: ─RY(x₅)──────────────────●───RZ─CZ─ ─ Measure
     └─── Layer repeated 3× with independent parameters ───┘
```

### A2: Validation Methodology
- Sentinel-2: fixed Clayton Valley / Silver Peak AOI; 26 positive pixels from USGS MRDS occurrences vs 5,000 random background pixels; ROC-AUC 0.80. Source `outputs/benchmark_console.json`.
- Hyperion: 5-fold spatial-block CV on training scenes + Scene 3 temporal hold-out; labels = 75th-percentile LiCI (2200nm) + VMI (2265nm), training set only, OR logic.
- Statistical tests: McNemar χ² for method comparison (C vs B: χ² = 2.62, p = 0.106).
- **Note**: an older `outputs/sentinel2_results/benchmark.json` was computed on a different AOI and disagrees with the console file. Only `benchmark_console.json` feeds the console and this deck.

### A3: Spectral Index Physics
- Al-OH absorption at 2200nm: caused by octahedral Al in clay minerals (kaolinite, montmorillonite, illite)
- Li substitution in hectorite/jadarite SHIFTS absorption slightly (2190-2210nm) — detectable with hyperspectral, marginal with Sentinel-2's broad B12 (2190nm center, 175nm width)
- V-bearing mica (roscoelite) absorption near 2265nm underpins the vanadium index — weaker contrast, hence the permanent "low confidence" label
- B11/B12 ratio works because altered rocks have deeper 2200nm absorption relative to 1610nm

### A4: Data Pipeline Specifications
- Source: AWS Earth Search STAC (sentinel-cogs bucket, no authentication)
- Processing: Cloud-optimized GeoTIFFs via rasterio WarpedVRT
- Masking: Scene Classification Layer (SCL) removes cloud/shadow/water/snow
- Resolution: Adaptive 20-60m based on area size (optimizes speed vs detail)
- Projection: UTM zone auto-detected from centroid; overlays reprojected to EPSG:4326
- Job cache key: `md5(lat,lon,km)[:10]` → `outputs/jobs/<key>/`

### A5: Per-Job Output Files
| File | Note |
|------|------|
| `lithium_prospectivity.png/.tif` | Clay / Al-OH ratio (B11/B12). Rock-hosted & pegmatite Li. |
| `vanadium_prospectivity.png/.tif` | Iron-oxide + mica composite. **Low confidence.** |
| `brine_favorability.png/.tif` | Playa / evaporite flag. **Indirect hint, not a detection.** |
| `confidence.tif` | Data-quality raster |
| `rgb.png`, `confidence.png` | Decorated matplotlib figures (titles, axes, colorbars) |
| `overlays/*.png` | **Bare** grid-aligned RGBA, warped to EPSG:4326 — the map-drapable layers |
| `result.json` | Metadata + caveats |
| `targets.json` | Ranked anomaly clusters (generated on first `/api/targets` request) |

`result.json` fields: `date_range`, `tiles_used[{id,date,cloud}]`, `coverage`, `crs`,
`grid[2]`, `bbox_lonlat[4]`, `rock_fraction`, `playa_fraction`, `capability_note`,
`deposit_check[]`, `overlay_corners`, `overlay_layers[]`,
`confidence_summary{high_pct,low_pct,masked_pct,definition}`.

### A6: HTTP API (engine, port 8765)
| Route | Purpose |
|-------|---------|
| `GET /` | Standalone demo page (no Node needed) |
| `POST /api/analyze` | `{lat,lon,km}` → run or serve from cache |
| `GET /api/jobs` | All cached analyses |
| `GET /api/point?job=&lat=&lon=` | Li + V index/percentile at one point |
| `GET /api/sample?job=&lat=&lon=` | Click-anywhere lithium score + `confidence_class` |
| `GET /api/targets?job=` | Anomaly clusters; writes `<job>/targets.json` |
| `GET /jobs/x/<job>/<file>` | Serves job files, incl. `overlays/` |

Console-side shims: `/api/geology` (Macrostrat), `/api/geocode`, `/api/explain` (AI summary).

### A7: Deployment & Configuration
```bash
# one-time
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cd terraq && npm install && cd ..

# run (dashboard :3000, engine :8765)
bash start.sh
bash stop.sh

# fill the cache BEFORE a demo (~7 min, serial)
./.venv/bin/python product/prewarm.py

# regenerate validation + console data after an engine change
./.venv/bin/python product/benchmark_console.py
./.venv/bin/python product/export_console_data.py
```

Requires Python **3.12** (pennylane 0.38 + numpy<2 do not resolve on 3.13/3.14) and Node 18+.

**Environment variables** (names only; values live in git-ignored `terraq/.env.local`):
`NEXT_PUBLIC_ENGINE_URL` (client, optional) · `LLM_PROVIDER`, `GROQ_API_KEY`,
`GROQ_MODEL`, `GROQ_FALLBACK_MODEL`, `GEMINI_API_KEY` (server, all optional).
**The entire app runs with every one of these empty.**

### A8: Demo Script (5 minutes)
1. Open `/explorer` — globe, reference sites visible, limitations box in view
2. Pick Clayton Valley → **Analyze** (pre-warmed, returns from cache instantly)
3. Toggle the lithium overlay — show it is georeferenced, pan/zoom to prove it sticks
4. Click inside the AOI → index, percentile, confidence class at that pixel
5. Click outside the AOI → *"Not analysed — run Analyze Region here"* (show the honest failure)
6. Open **Detected targets** → click T10 → fly to it → note 0.24 km from Silver Peak mine
7. Open the AI summary → point at the provider badge → "measured values only"
8. Close on the Limitations box: "this is visible on every tab, not buried"

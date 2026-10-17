# Quantum Autoencoder for Anomaly Detection in Satellite Imagery

> A **hybrid quantum–classical pipeline** for lithium & vanadium mineral prospecting from satellite hyperspectral / multispectral imagery — combining a 6‑qubit Quantum Autoencoder (QAE) detector, a reproducible benchmark of 7 methods, and a live web dashboard.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![PennyLane ≥0.38](https://img.shields.io/badge/pennylane-%E2%89%A50.38-orange)](https://pennylane.ai/)
[![Next.js](https://img.shields.io/badge/next.js-dashboard-black)](https://nextjs.org/)
[![Status](https://img.shields.io/badge/status-research%20prototype-yellow)]()

<p align="center">
  <img src="outputs/sentinel2_results/silver_peak_validation.png" alt="Silver Peak lithium validation" width="80%">
</p>
<p align="center"><i>Model prospectivity vs. known USGS lithium deposits — Clayton Valley / Silver Peak, Nevada.</i></p>

---

## Table of Contents

1. [What this project is](#what-this-project-is)
2. [The three components](#the-three-components)
3. [Key results](#key-results)
4. [How it works](#how-it-works)
5. [Gallery](#gallery)
6. [Repository structure](#repository-structure)
7. [Setup & run](#setup--run)
8. [Reproducibility](#reproducibility)
9. [Honest scope & limitations](#honest-scope--limitations)
10. [References](#references)

---

## What this project is

Classical hyperspectral mineral detection struggles on high‑dimensional, noisy
satellite data — the curse of dimensionality, correlated bands, and weak/overlapping
mineral absorption features all reduce sensitivity. This project asks a focused
question:

> **Can a quantum autoencoder encode spectral patterns that a classical autoencoder
> of identical bottleneck width cannot — and does that improve mineral detection?**

To answer it, the project benchmarks **seven detection methods** (classical → fully
quantum) on NASA EO‑1 **Hyperion** scenes, and ships a separate **classical
Sentinel‑2 engine + web dashboard** so anyone can scan a real location on demand.

---

## The three components

| Component | Folder | What it is | Quantum? |
|---|---|---|---|
| **Research pipeline** | `experiments/`, `src/` | Trains & benchmarks all 7 methods on Hyperion, produces every figure/metric | ✅ Yes (QAE / QAA / QSVM / VQC) |
| **Live engine** | `product/` | Turns a lat/lon into lithium/vanadium prospectivity maps from live Sentinel‑2 data | ❌ Classical spectral indices |
| **Web dashboard** | `terraq/` | Next.js front‑end visualising results + a "Live Analysis" tab driven by the engine | ❌ UI layer |

> ⚠️ **Important distinction:** the quantum advantage is demonstrated in the **research
> pipeline** on Hyperion. The **live dashboard maps** come from the fast **classical**
> Sentinel‑2 engine. Do not present the Sentinel‑2 maps as "quantum results."

---

## Key results

> Measured on the temporal hold‑out test scene (Scene 3, never seen in training).
> Source of truth: [`outputs/summary/metrics.txt`](outputs/summary/metrics.txt).
> Train positive rate: 48.3 %.

| Method | Description | AUC | F1 | MCC | 95% CI (AUC) |
|---|---|---|---|---|---|
| **A** PCA only | Classical baseline | 0.749 | 0.648 | 0.316 | [0.717, 0.780] |
| **B** PCA + CAE | Classical autoencoder ablation | 0.762 | 0.662 | 0.321 | [0.731, 0.792] |
| **C** PCA + QAE ★ | **6‑qubit Quantum Autoencoder (best)** | **0.770** | **0.675** | **0.351** | [0.739, 0.801] |
| **F** QAA Hybrid | Unsupervised quantum anomaly + pseudo‑labels | 0.687 | 0.451 | 0.352 | [0.652, 0.723] |
| **D** QSVM | Standalone ZZFeatureMap kernel SVM | 0.513 | 0.544 | 0.066 | [0.473, 0.552] |
| **C3** QAE → VQC | End‑to‑end quantum classifier | 0.526 | 0.593 | 0.138 | [0.487, 0.565] |
| **C2** QAE → QSVM | Stacked quantum pipeline | 0.471 | 0.548 | −0.057 | [0.429, 0.509] |

**Headline:** Method **C (PCA + QAE)** is the top performer on every primary metric
(AUC, F1, MCC). The quantum feature extractor adds **+2.1% AUC over the PCA baseline (A)**
and **+0.9% AUC over the classical‑autoencoder ablation (B)** — a consistent, but modest, lift.

**Statistical test (McNemar, paired):** at the patch level, C vs B gives χ² = 2.62,
**p = 0.106**, i.e. the improvement is *not* statistically significant on this test set.
This is reported honestly as a limitation, not hidden — see
[Honest scope & limitations](#honest-scope--limitations).

<p align="center">
  <img src="outputs/summary/method_comparison_bar.png" alt="Method comparison" width="48%">
  <img src="outputs/summary/roc_curves.png" alt="ROC curves" width="48%">
</p>

---

## How it works

```
 Hyperion scene (198 bands, 30 m)
            │
            ▼
 ┌──────────────────────────────────────────────┐
 │ Preprocessing                                │
 │ • bad-band removal → 198 calibrated bands    │
 │ • center crop + 16×16 non-overlapping patches│
 │ • brightness / flatness quality filters      │
 │ • Scenes 1+2+4 → TRAIN  |  Scene 3 → TEST    │
 └───────────────────┬──────────────────────────┘
                     ▼
 ┌──────────────────────────────────────────────┐
 │ Physics-based labels (NOT used as features)  │
 │ LiCI @2200 nm (Li-OH)  ·  VMI @2265 nm (V-OH)│
 │ 75th-pct threshold, OR logic → no circularity│
 └───────────────────┬──────────────────────────┘
                     ▼
 ┌──────────────────────────────────────────────┐
 │ Shared stage: RobustScaler → PCA(25)         │  identical for ALL methods
 └───────────────────┬──────────────────────────┘
        ┌────────────┼─────────────────────────────┐
        ▼            ▼                             ▼
   A: ensemble   B: +classical AE (6D)     C: +6-qubit QAE → ⟨Z₀…Z₅⟩
   (RF+GB+SVM)      bottleneck               33-D feature vector → ensemble ★
                                            (also → C2 QSVM, C3 VQC)
        ▼
   D: ZZFeatureMap quantum kernel SVM
        ▼
   F: unsupervised QAA on background only → pseudo-labels → ensemble
```

**Method C (the contribution):** PCA(25) → tanh‑scaling → 6‑qubit Hardware‑Efficient
Ansatz QAE (data re‑uploading + 3 variational layers) → 6 expectation values
⟨Z₀⟩…⟨Z₅⟩, concatenated with the 25 PCA scores + 2 USGS spectral‑correlation features
→ 33‑D vector → RF + GradientBoost + SVM ensemble.

**QAE vs QAA:**

| | QAE (C / C2 / C3) | QAA (F) |
|---|---|---|
| Type | Supervised feature extractor | Unsupervised anomaly detector |
| Trains on | labeled mineral + background | background only |
| Loss | MSE on reconstruction | 1 − P(trash = \|0000⟩) |
| Output | 6 expectation values | scalar anomaly score ∈ [0,1] |

---

## Gallery

**Research pipeline outputs** (Hyperion, all in [`outputs/summary/`](outputs/summary)):

<p align="center">
  <img src="outputs/summary/all_maps_grid.png" alt="All 7 detection maps" width="80%">
</p>
<p align="center"><i>Detection probability maps for all seven methods.</i></p>

<p align="center">
  <img src="outputs/summary/confusion_matrices_test.png" alt="Confusion matrices" width="48%">
  <img src="outputs/summary/feature_tsne.png" alt="t-SNE of feature spaces" width="48%">
</p>
<p align="center"><i>Left: per‑method confusion matrices. Right: t‑SNE of PCA vs CAE vs QAE feature spaces.</i></p>

**Live Sentinel‑2 engine output** (classical, [`outputs/sentinel2_results/`](outputs/sentinel2_results)):

<p align="center">
  <img src="outputs/sentinel2_results/lithium_prospectivity_map.png" alt="Lithium prospectivity" width="48%">
  <img src="terraq/public/maps/confidence.png" alt="Confidence map" width="48%">
</p>
<p align="center"><i>Lithium (clay/Al‑OH) prospectivity and data‑confidence map for Clayton Valley, NV.</i></p>

---

## Repository structure

```
TerraQ/
├── README.md                    ← this file
├── PROBLEM_STATEMENT.md         ← scientific problem definition
├── STRUCTURE.md                 ← detailed structure notes
├── requirements.txt             ← Python dependencies
├── start.sh / stop.sh           ← launch / stop dashboard + engine
│
├── experiments/
│   └── run_pipeline.py          ← single entry point — runs all 7 methods
├── src/
│   ├── config.py                ← all hyperparameters (single source of truth)
│   ├── pipeline/                ← features, ensemble, metrics, maps, viz
│   └── quantum/                 ← qae.py · qaa.py · qsvm.py · vqc.py
│
├── product/                     ← classical Sentinel-2 engine + API server
│   ├── sentinel_engine.py       ← coordinate → prospectivity maps
│   ├── server.py                ← local HTTP API (port 8765)
│   └── README.md
│
├── terraq/                    ← Next.js web dashboard
│   ├── app/  components/  hooks/  lib/
│   └── public/maps/             ← committed map images (site works offline)
│
├── data/
│   ├── ground_truth/*.csv       ← MRDS deposit labels (committed)
│   ├── processed/               ← *.npy cubes (generated, gitignored)
│   └── EO1H*/                   ← raw Hyperion TIFs (gitignored, ~17 GB)
│
├── outputs/
│   ├── summary/                 ← all research figures + metrics (committed)
│   ├── sentinel2_results/       ← engine demo outputs (committed)
│   └── jobs/, product_demo_*/   ← regenerable runs (gitignored)
│
└── docs/                        ← paper outline, technical manual, quantum advantage
```

> Large/regenerable assets (raw TIFs, processed cubes, `node_modules`, `.venv`,
> build caches) are intentionally **gitignored** — the repo is ~16 MB and rebuilds
> from the steps below.

---

## Setup & run

### Prerequisites
- Python 3.12 and Node.js 18+
- `git`

### A. Both together — dashboard + engine (recommended)
```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cd terraq && npm install && cd ..

bash start.sh     # prints the URLs it actually bound to
bash stop.sh      # stops only what start.sh started
```
`start.sh` prefers `:3000` (dashboard) and `:8765` (engine) but **falls back to the
next free port** if something else on the machine already holds one — read the URLs
it prints rather than assuming `:3000`. Force specific ports with
`DASH_PORT=3005 ENGINE_PORT=8770 bash start.sh`.

### B. Web dashboard only (works offline with the committed images)
```bash
cd terraq
npm install
npm run dev            # add `-- -p 3001` if :3000 is taken
# open http://localhost:3000
```
Only the **Live Analysis** tab needs the engine; every other tab renders from images
committed under `terraq/public/maps/`.

### C. Live Analysis engine only (Sentinel‑2, classical)
```bash
./.venv/bin/python -u product/server.py     # API on http://localhost:8765
```
Use `-u`, or the per‑request progress log stays stuck in Python's block buffer.
One‑shot CLI for a single location:
```bash
./.venv/bin/python product/sentinel_engine.py \
    --lat 37.7499 --lon -117.6342 --km 12 --out outputs/my_area
```
**Expect a cold request to take several minutes** (~7 min for a 12 km radius over
Clayton Valley on a home connection). It streams Sentinel‑2 COGs from a public S3
bucket and mosaics up to 4 tiles × 8 bands, so the wall‑clock is dominated by network
latency, not compute — the bands of a tile are fetched concurrently for that reason.
Repeat requests for the same `(lat, lon, km)` are served from `outputs/jobs/` and
return instantly.

### D. Full quantum research pipeline (Hyperion)
```bash
./.venv/bin/pip install -r requirements.txt

# 1) provide raw Hyperion scenes under data/, then preprocess to data/processed/*.npy
#    (see data/README.md and the step1/step2 scripts)

# 2) run all 7 methods + generate every figure/metric  (~1 h on CPU)
./.venv/bin/python experiments/run_pipeline.py
```
Runtime is dominated by QAA parameter‑shift gradients; the QAE stage is a few minutes
on CPU. Results land in `outputs/` (per‑method folders + `outputs/summary/`).

To run without overwriting an existing set of results, redirect the output folder:
```bash
QMD_OUTPUT_DIR=outputs_rerun ./.venv/bin/python experiments/run_pipeline.py
```

On **Intel macOS** the last published PyTorch build is `2.2.2`; `pip install -r
requirements.txt` resolves to it automatically. Note that the `gdal` Python binding
is deliberately *not* a dependency — `rasterio` bundles its own GDAL and nothing here
imports `osgeo`.

---

## Reproducibility

| Setting | Value |
|---|---|
| Random seed | 42 (NumPy, Python, PyTorch) |
| PCA components | 25 |
| QAE qubits / layers | 6 / 3 |
| QAE training samples | 200 balanced (100 + / 100 −) |
| QAA qubits / latent / trash | 6 / 2 / 4 |
| Quantum backend | PennyLane simulator (no real hardware) |
| Test set | Scene 3 only (temporal hold‑out) |
| Labels | 75th-percentile threshold on LiCI + VMI, training set only (OR logic) |

A config hash is printed at pipeline start, so any parameter change is detectable.

---

## Honest scope & limitations

This is a **research prototype and candidate‑target generator**, not a discovery or
guarantee tool. Stated plainly:

- **Quantum advantage is modest and not yet statistically significant** on the
  Hyperion test set (Method C is the best performer, but McNemar C vs B p = 0.106).
- **The live dashboard is classical**, not quantum — it uses Sentinel‑2 band‑ratio
  indices (clay/Al‑OH for Li, iron‑oxide + mica for V).
- **Optical remote sensing cannot see brine lithium** (dissolved underground) or
  buried deposits — it detects *surface alteration* only.
- **"Prospectivity" is a normalised 0–1 alteration score**, not a calibrated
  probability and not proof of mineralisation. Bright anomalies away from known
  deposits are **leads to investigate**, requiring field survey and drilling to confirm.
- The quantum models run on a **simulator**; full‑scene pixel‑wise quantum inference
  is not yet practical (state‑preparation + simulation cost), which is why wide‑area
  scanning is done classically by design.

---

## References

1. Romero, Olson & Aspuru‑Guzik (2017). *Quantum autoencoders for efficient compression of quantum data.* Quantum Sci. Technol. 2(4), 045001.
2. Havlíček et al. (2019). *Supervised learning with quantum‑enhanced feature spaces.* Nature 567, 209–212.
3. Pérez‑Salinas et al. (2020). *Data re‑uploading for a universal quantum classifier.* Quantum 4, 226.
4. Biamonte et al. (2017). *Quantum machine learning.* Nature 549, 195–202.
5. Bergholm et al. (2022). *PennyLane: Automatic differentiation of hybrid quantum‑classical computations.* arXiv:1811.04968.
6. Kokaly et al. (2017). *USGS Spectral Library Version 7.* USGS Data Series 1035.
7. Van der Meer (2004). *Analysis of spectral absorption features in hyperspectral imagery.* Int. J. Appl. Earth Obs. 5(1), 55–68.

---

<p align="center"><sub>Research prototype · quantum‑classical mineral prospecting · figures and metrics are reproducible from <code>outputs/summary/</code>.</sub></p>

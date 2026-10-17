# Codebase Structure

```
TerraQ/
│
├── README.md                      Project overview
├── PROBLEM_STATEMENT.md           Scientific problem definition
├── STRUCTURE.md                   This file
├── requirements.txt               Python dependencies
│
├── src/                           ── RESEARCH PIPELINE (library code) ──
│   ├── config.py                  All hyperparameters (single source of truth)
│   ├── pipeline/
│   │   ├── features.py            Patch extraction, PCA, band-ratio labels, USGS corr
│   │   ├── ensemble.py            Classical autoencoder + RF/SVM/GBT ensemble
│   │   ├── metrics.py             AUC, F1, MCC, bootstrap CI, McNemar test
│   │   ├── maps.py                Probability-map saving
│   │   └── viz.py                 Publication figures
│   └── quantum/
│       ├── qae.py                 6-qubit Quantum Autoencoder (Method C/C2/C3)
│       ├── qsvm.py                ZZFeatureMap quantum-kernel SVM (Method D)
│       ├── qaa.py                 Quantum Anomaly Autoencoder (Method F)
│       ├── vqc.py                 Variational Quantum Classifier (Method C3)
│       └── noise.py               NISQ noise simulation (optional experiment)
│
├── experiments/
│   ├── run_pipeline.py            Main entry point — runs all 7 methods (~30–60 min)
│   ├── run_noise_analysis.py      Optional noise-resilience experiment
│   └── test_noise.py              Noise unit checks
│
├── product/                       ── DEPLOYABLE PRODUCT (Sentinel-2) ──
│   ├── sentinel_engine.py         coords → Sentinel-2 → Li/V alteration overlays
│   ├── server.py                  Standalone clickable web demo + JSON API (:8765)
│   └── README.md                  How to run the product
│
├── terraq/                      ── WEB DASHBOARD (Next.js) ──
│   ├── app/
│   │   ├── page.tsx               Main dashboard (Overview/Maps/Methods/How/Data tabs)
│   │   └── live-analysis/page.tsx Standalone route of the Live Analysis tool
│   ├── components/
│   │   ├── terraq-sidebar.tsx   Tab navigation
│   │   ├── terraq-live-analysis.tsx  Live Analysis panel (map + engine call)
│   │   └── ...                    cards, navbar, charts, ui/
│   └── public/maps/               Real Sentinel-2 output images for the Maps tab
│
├── data/
│   ├── processed/                 *.npy cubes + USGS refs — USED AT RUNTIME
│   ├── ground_truth/              USGS MRDS Li/V deposit CSVs (validation)
│   └── EO1H*_1T/                  Raw Hyperion GeoTIFF bands (only to regenerate npy)
│
├── outputs/                       ── GENERATED RESULTS ──
│   ├── A_PCA/ … F_QAA_Hybrid/     Per-method prob_map.npy + heatmap + metrics
│   ├── summary/                   Cross-method metrics, ROC/PR, LaTeX table, figures
│   ├── sentinel2_results/         ★ Sentinel-2 METRICS & BENCHMARK (report + figures)
│   ├── sentinel2_benchmark/       Raw benchmark JSON
│   ├── sentinel2_clayton_valley/  Silver Peak validation figure
│   ├── product_demo_v2/           Reference Sentinel-2 engine output
│   └── jobs/                      Engine per-request cache (powers instant presets)
│
├── docs/                          Paper outline, technical manual, slides
└── usgs_splib07/                  Raw USGS Spectral Library v7 (reference only; 6.7 GB)
```

## What runs what
- **Research results:** `python experiments/run_pipeline.py` (reads `data/processed/`, writes `outputs/`).
- **Product engine / demo:** `python product/server.py` → http://localhost:8765.
- **Dashboard:** in `terraq/` → `CI=true node node_modules/next/dist/bin/next dev -p 3000` (this drive needs npm, not pnpm).

## Notes
- `data/EO1H*_1T/` (raw TIFs) and `usgs_splib07/` are **only needed to regenerate**
  `data/processed/*.npy`. The pipeline and product do not read them at runtime.
- `outputs/` is fully regenerable; `outputs/jobs/` is a cache (safe to clear, but
  clearing it makes the dashboard's preset analyses recompute on first use).
```

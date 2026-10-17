# Problem Statement

**Project: Quantum-Enhanced Anomaly Detection for Critical Mineral Identification Using Satellite Hyperspectral Data**

---

## Background

The global demand for **lithium** and **vanadium** has surged due to their strategic importance in battery storage, electric vehicles, and grid-scale energy systems. Conventional remote sensing mineral prospecting relies on classical spectral analysis — spectral angle mapping (SAM), PCA-based anomaly detection, and shallow SVMs — which face fundamental limitations on the high-dimensional, non-linear hyperspectral data produced by NASA EO-1 Hyperion (198 bands, 400–2500 nm, 30 m spatial resolution, 50 688 features per 16×16 patch).

Quantum computing offers a path beyond these limitations. Variational quantum circuits operate in a Hilbert space of dimension 2ⁿ — for n=6 qubits, 64 dimensions — and can encode coupled multi-band spectral correlations (quantum entanglement) that are inaccessible to classical encoders of equivalent parameter count. Critically, **no quantum hardware is required**: PennyLane's `default.qubit` noiseless simulator runs these circuits on a standard CPU in 30–60 minutes, making the research immediately reproducible.

---

## Scientific Challenge

Satellite-based mineral detection involves five compounding difficulties:

1. **Curse of dimensionality** — 50 688 features per patch; mineral signal occupies 3–5 specific wavelength bands
2. **Complex multi-band correlations** — Li-OH absorption at 2200 nm is coupled to Al-OH features at 2135 and 2350 nm; V-OH at 2265 nm overlaps other phyllosilicates
3. **Low signal-to-noise ratio** — atmospheric scattering, sensor noise, and bidirectional reflectance variation mask subtle trough depths
4. **Class imbalance** — mineralised zones typically occupy 25–50 % of a scene; without careful thresholding, classifiers predict all-background
5. **Spatial autocorrelation** — adjacent patches share the same geological unit; naive random train/test splits leak geology, inflating CV scores by up to 0.15 AUC

---

## Objective

Develop and experimentally validate a **hybrid quantum–classical pipeline** that:

1. **Quantum feature extraction (QAE, Method C)** — a 6-qubit Hardware-Efficient Ansatz trained with mineral-weighted MSE encodes spectral patches into a Hilbert-space feature manifold, providing statistically significant AUC improvement over a classical autoencoder of identical bottleneck depth

2. **Fully-quantum ablation (Methods C2, C3)** — QAE → QSVM and QAE → VQC pipelines isolate the contribution of quantum kernel classification vs quantum feature extraction vs classical ensemble

3. **Quantum kernel SVM (Method D)** — ZZFeatureMap fidelity kernel (Havlíček et al. 2019) provides a standalone quantum classification baseline

4. **Unsupervised quantum anomaly detection (QAA, Method F)** — a bottleneck QAE (Romero et al. 2017) trained ONLY on background patches with Hilbert-space fidelity loss (1 − P(trash=|0000⟩)) detects mineral anomalies **without any mineral labels at any stage**

5. **Rigorous evaluation** — spatially-blocked 5-fold CV, temporal hold-out test (Scene 3), McNemar statistical tests, bootstrap 95 % confidence intervals

---

## Non-Circular Label Design

A critical methodological contribution of this project is its **label generation strategy**, which avoids the circular validation bias common in related work:

```
Step 1:  Compute LiCI = [R(2135) + R(2350)] / 2 − R(2200)   per patch
         Compute VMI  = [R(1700) + R(2350)] / 2 − R(2265)   per patch
         (spectral absorption-depth indices — no USGS matching involved)

Step 2:  Threshold LiCI and VMI at the 75th percentile of the TRAINING patches only
         (config: label_strategy='band_ratio_percentile', label_percentile=75.0)

Step 3:  label = 1  if  LiCI > li_thresh  OR  VMI > v_thresh
         label = 0  otherwise

Step 4:  Apply IDENTICAL thresholds to test patches (no data leakage)

Important: LiCI and VMI are NEVER input to any classifier.
```

This design means:
- No USGS library used in labelling → no circularity with USGS correlation features
- No training-test threshold contamination → honest generalisation measurement
- The 75th-percentile threshold with OR logic produces a 48.3 % train positive rate
  (metrics.txt) → manageable class balance

---

## Success Criteria

| Metric | Target | Achieved | Method |
|---|---|---|---|
| Test AUC | ≥ 0.75 | **0.770** ✓ | C_PCA_QAE |
| McNemar p-value | < 0.001 | **p = 0.106 — not met** | QAE vs CAE |
| Unsupervised AUC | ≥ 0.70 | **0.687 — not met** | F_QAA_Hybrid |
| False positive rate | < 30 % | reported | all methods |
| Reproducibility | single command | ✓ | `run_pipeline.py` |

---

## Data

| Scene | ID | Date | Path/Row | Split |
|---|---|---|---|---|
| 1 | EO1H0430342017071 | 2017-03-12 | P43/R34 | **TRAIN** |
| 2 | EO1H0410332013075 | 2013-03-16 | P41/R33 | **TRAIN** |
| 3 | EO1H0410332013154 | 2013-06-03 | P41/R33 | **TEST** (hold-out) |
| 4 | EO1H0410342014301 | 2014-10-28 | P41/R34 | **TRAIN** |

- **Satellite**: NASA EO-1 Hyperion (198 bands after bad-band removal, 30 m GSD)
- **Reference**: USGS Spectral Library v7 (Kokaly et al. 2017) — auxiliary features only
- **Labels**: Band-ratio absorption-depth indices — not field surveys, not USGS matching

---

## Scope Boundaries

| In scope | Out of scope |
|---|---|
| Simulator-based quantum circuits (PennyLane `default.qubit`) | Real QPU execution (noise mitigation required) |
| EO-1 Hyperion 198-band data | Multispectral sensors (Landsat, Sentinel-2) |
| Lithium and vanadium indicators | Other critical minerals (Rare Earths, Cobalt) |
| Patch-level classification | Pixel-level subpatch localisation |
| Statistical significance testing | Field-validated ground truth |

---

## References

1. Romero J et al. (2017). Quantum autoencoders for efficient compression of quantum data. *Quantum Science and Technology* 2(4), 045001.
2. Havlíček V et al. (2019). Supervised learning with quantum-enhanced feature spaces. *Nature* 567, 209–212.
3. Kokaly RF et al. (2017). USGS Spectral Library Version 7. *USGS Data Series* 1035.
4. Pérez-Salinas A et al. (2020). Data re-uploading for a universal quantum classifier. *Quantum* 4, 226.
5. Thanasilp S et al. (2022). Exponential concentration and untrainability in quantum kernel methods. *arXiv:2208.11060*.


## Challenge

Satellite-based mineral detection involves processing multi-spectral and hyperspectral data, where:

1. **Curse of dimensionality** — Hyperion provides 198 spectral bands, creating 50,688 features per 16×16 patch
2. **Complex feature correlations** — Mineral absorption features span multiple overlapping bands
3. **Low signal-to-noise ratio** — Atmospheric scattering and sensor noise degrade subtle spectral signatures
4. **Class imbalance** — Mineralized zones typically occupy <25% of a scene
5. **Spatial autocorrelation** — Adjacent patches share geology, inflating naive cross-validation scores

Existing classical approaches (PCA + SVM, classical autoencoders) often suffer from:
- High false positive rates on cloud shadows and bare soil
- Poor generalization across different geological terrains and acquisition dates
- Limited scalability when extended to large geographic regions
- Inability to capture non-linear multi-band interaction patterns

## Objective

Develop and validate a **hybrid quantum–classical model** that:

1. Exploits quantum computational principles — specifically:
   - **High-dimensional Hilbert space representations** (2^n exponential feature space)
   - **Quantum feature encoding** (Hardware-Efficient Ansatz)
   - **Quantum distance measures** (ZZFeatureMap fidelity kernel)
   - **Quantum anomaly detection** (unsupervised reconstruction in Hilbert space)

2. Detects potential **lithium, vanadium, and critical mineral anomalies** from NASA EO-1 Hyperion satellite imagery

3. Demonstrates **statistically significant improvement** over classical baselines  
   (McNemar test; p < 0.05 would be required for a significance claim —
    the measured value is p = 0.106, so no significance is claimed)

4. Includes **true unsupervised anomaly detection** (no labels used in Quantum Anomaly  
   Autoencoder training — satisfies the "anomaly detection" framing of the problem)

## Success Criteria

| Metric | Target | Method |
|--------|--------|--------|
| Test AUC | ≥ 0.75 | C_PCA_QAE |
| McNemar p-value | < 0.001 | QAE vs CAE |
| QAA pseudo-label agreement | ≥ 70% | vs band-ratio labels |
| False positive rate | < 30% | on test set |

## Data

- **Satellite**: NASA EO-1 Hyperion (198 bands, 400–2500 nm, 30m resolution)
- **Scenes**: 3 scenes covering lithium/vanadium-bearing geological formations
- **Reference spectra**: USGS Spectral Library v7 (Kokaly et al. 2017)
- **Labels**: Derived from spectral band-ratio indices (LiCI, VMI) — **not** from field surveys

#!/usr/bin/env python3
"""
experiments/run_pipeline.py
============================
QUANTUM-ENHANCED MINERAL DETECTION — FINAL PIPELINE

Faithfully replicates step3_publication_pipeline.py in a clean modular
package.  Committed results (outputs/summary/metrics.txt, hold-out Scene 3):
    C_PCA_QAE:  AUC=0.7702  F1=0.6751  MCC=0.3510
    McNemar QAE vs CAE:  chi2=2.62  p=0.1056  NOT significant

METHOD SUMMARY
--------------
  A   PCA only              (classical baseline)
  B   PCA + CAE             (classical autoencoder ablation)
  C   PCA + QAE             (proposed: quantum feature extractor)  ← best baseline
  C2  PCA + QAE → QSVM     (fully-quantum pipeline: quantum features + quantum kernel)
  C3  PCA + QAE → VQC      (end-to-end trainable quantum pipeline)
  D   QSVM                  (standalone: quantum kernel on PCA features)
  F   QAA Hybrid            (unsupervised quantum anomaly → pseudo-label → ensemble)

QUANTUM COMPONENT ROLES
-----------------------
  QAE    = FEATURE EXTRACTOR  (feeds ensemble classifier — Methods C, C2, C3)
           Input:  tanh(Z_train[:, :6])   — first 6 PCA dims
           Output: 6 quantum expectation values <Z_i>  concatenated with PCA
           Quantum advantage: exponentially large Hilbert space (2^6=64)
           captures non-linear spectral correlations that PCA/CAE cannot.

  C2-QASVM = QUANTUM KERNEL on QAE FEATURES  (Method C2 — fully quantum)
           Input:  6-dim QAE expectation values  (output of QAE, already ∈(-1,+1))
           Kernel: ZZFeatureMap fidelity K(x1,x2) = |<ϕ(x1)|ϕ(x2)>|^2
           Advantage: stacks two quantum resources—compressed quantum features
           measured in a second, independent Hilbert space.

  C3-VQC = VARIATIONAL QUANTUM CLASSIFIER on QAE FEATURES  (Method C3)
           Input:  6-dim QAE expectation values  → RY(π * x_i) angle embedding
           Trainable: StronglyEntanglingLayers(n_vqc_layers=2)
           Advantage: end-to-end differentiable quantum pipeline (QAE+VQC
           optimised independently then chained).

  QSVM   = STANDALONE CLASSIFIER  (Method D — quantum distance measures)
           Input:  tanh(Z[:, :6])         — first 6 PCA dims
           Output: class probabilities via ZZFeatureMap fidelity kernel SVC
           Kernel: K(x1,x2) = |<phi(x1)|phi(x2)>|^2  (fidelity in Hilbert space)

  QAA    = UNSUPERVISED ANOMALY DETECTOR  (Method F — no labels used)
           Input:  tanh(Z[:, :5])         — first 5 PCA dims  (2^5=32 dimensions)
           Train:  background-only patches  (no mineral labels)
           Score:  quantum reconstruction error  (high = spectral anomaly)
           Hybrid: QAA pseudo-labels feed a Method-C-style supervised ensemble

ARCHITECTURE FLOW
-----------------
  Hyperion (800x800x198) + USGS Li/V refs
      │
      ├─► 16×16 patch extraction  (brightness / std quality filters)
      │       LiCI, VMI absorption-depth indices per patch
      │       OR label:  1 if LiCI > 75th pct  OR  VMI > 75th pct
      │
      ├─► Full 198-band flatten (50,688 dims) → RobustScaler → PCA(25)
      │       Z_train: (N_tr, 25)   Z_test: (N_ts, 25)
      │
      ├─► CAE bottleneck(6) ──────────────────────────► B_PCA_CAE features
      │
      ├─► QAE encoder(6 qubits)  ─────────────────────► C_PCA_QAE features
      │       [QAE: first 6 PCA dims → 6 expectation values <Z_i>]
      │       │
      │       ├► QSVM quantum kernel (ZZFeatureMap) ─► C2: QAE→QSVM
      │       └► VQC (StronglyEntangling, 2 layers)  ─► C3: QAE→VQC
      │
      ├─► USGS Pearson corr (Li, V)  ──────────────────► aux corr(2) features
      │
      ├─► QSVM (first 6 PCA dims)  ───────────────────► Method D predictions
      │       ZZFeatureMap fidelity kernel → SVC(precomputed)
      │
      └─► QAA (first 5 PCA dims, background only)  ───► Method F anomaly scores
              Unsupervised reconstruction error → pseudo-labels → ensemble

  Ensemble (SVM+RF+GB soft-vote) on A / B / C feature sets  → Methods A/B/C

METHOD F — QUANTUM ANOMALY AUTOENCODER (HYBRID):
  Stage 1 (F): Train QAA bottleneck circuit ONLY on background patches.
               Loss = 1 − P(trash=|0000⟩)  [Romero et al. 2017 Hilbert-space fidelity]
               Anomaly score ∈ [0,1]:  0=compresses easily (background),
                                        1=resists compression (mineral anomaly)
  Stage 2 (C): Generate pseudo-labels from anomaly score percentiles.
               score > 80th pct → 1 (mineral)   score < 40th pct → 0 (background)
               middle band → uncertain (discarded)
               Train Method-C-style RF+GBT+SVM ensemble on pseudo-labelled
               PCA→QAE features (same feature space as Method C).
  This two-stage design means F = (unsupervised QAA) + (supervised C ensemble).
  Advantage: no mineral labels needed at ANY stage.

OUTPUT STRUCTURE (professional per-method subfolders):
  outputs/
    A_PCA/            prob_map.npy  probability_heatmap.png  metrics.txt
    B_PCA_CAE/        prob_map.npy  probability_heatmap.png  metrics.txt
    C_PCA_QAE/        prob_map.npy  probability_heatmap.png  metrics.txt
    C2_QAE_QSVM/      prob_map.npy  probability_heatmap.png  metrics.txt
    C3_QAE_VQC/       prob_map.npy  probability_heatmap.png  metrics.txt
    D_QSVM/           prob_map.npy  probability_heatmap.png  metrics.txt
    F_QAA_Hybrid/     prob_map.npy  probability_heatmap.png  metrics.txt
                      anomaly_scores_train.npy  anomaly_scores_test.npy
    summary/          all_metrics.txt  cv_results.txt  roc_curves.png
                      method_comparison_bar.png  confusion_matrices_*.png
                      training_loss_curves.png  feature_tsne.png  ...

DATA (4 scenes — scene3 is held-out temporal test):
  Scene 1 : EO1H0430342017071  2017-Mar  P43/R34   TRAIN
  Scene 2 : EO1H0410332013075  2013-Mar  P41/R33   TRAIN
  Scene 3 : EO1H0410332013154  2013-Jun  P41/R33   TEST (held-out)
  Scene 4 : EO1H0410342014301  2014-Oct  P41/R34   TRAIN

  NOTE: Scenes 2 & 3 share orbit P41/R33 (corr≈0.89) — similar output maps expected.
  Scene 4 is adjacent row (R34), adds geographic diversity to training.
  Scene 1 covers a different path/row (P43/R34).
"""

import os
import sys
import time
import hashlib
import json
import warnings
import random
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Ensure package root is on PYTHONPATH
# ---------------------------------------------------------------------------
_HERE  = os.path.dirname(os.path.abspath(__file__))
_ROOT  = os.path.dirname(_HERE)   # TerraQ/
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Imports from package
# ---------------------------------------------------------------------------
from src.config import CFG, SEED
from src.pipeline.features import (
    load_wavelengths, make_band_indices,
    extract_patches, make_labels_percentile,
    fit_pca, apply_pca,
    usgs_corr_feature, make_mineral_weights,
)
from src.pipeline.ensemble import (
    train_classical_ae, extract_cae_features, build_ensemble,
)
from src.pipeline.metrics import (
    compute_metrics, bootstrap_auc_ci, mcnemar_test, print_metrics,
)
from src.pipeline.maps import save_maps, save_metrics_txt
from src.pipeline.viz  import (
    plot_probability_heatmaps,
    plot_rgb_mineral_overlay,
    plot_anomaly_score_map,
    plot_roc_curves,
    plot_method_comparison,
    plot_all_maps_grid,
    plot_training_loss_curves,
    plot_confusion_matrices,
    plot_pr_curves,
    plot_cv_boxplot,
    plot_train_test_comparison,
    plot_qsvm_kernel_heatmap,
    plot_feature_tsne,
    plot_label_distribution,
    save_latex_metrics_table,
)
from src.quantum.qae  import train_qae, extract_qae_features
from src.quantum.qsvm import build_qsvm, build_qsvm_from_features
from src.quantum.vqc  import train_vqc_from_features, vqc_predict_from_features
from src.quantum.qaa  import train_qaa, qaa_anomaly_scores, generate_pseudo_labels

from sklearn.preprocessing import StandardScaler

# Reproducibility
random.seed(SEED)
np.random.seed(SEED)
try:
    import torch
    torch.manual_seed(SEED)
except ImportError:
    pass
os.environ["PYTHONHASHSEED"] = str(SEED)

os.makedirs(CFG["output_folder"], exist_ok=True)

# ---------------------------------------------------------------------------
# Method selection.  By default every method runs.  Set QMD_SKIP to a comma
# list to leave out the expensive optional ones, e.g.
#     QMD_SKIP=C2,C3,D,F python experiments/run_pipeline.py
# runs only the PCA / CAE / QAE ensemble methods (A, B, C).  A, B and C share
# one cheap code path and cannot be skipped individually.
# ---------------------------------------------------------------------------
ALL_METHODS = ["A_PCA", "B_PCA_CAE", "C_PCA_QAE",
               "C2_QAE_QSVM", "C3_QAE_VQC", "D_QSVM", "F_QAA_Hybrid"]
_ALIAS = {"A": "A_PCA", "B": "B_PCA_CAE", "C": "C_PCA_QAE", "C2": "C2_QAE_QSVM",
          "C3": "C3_QAE_VQC", "D": "D_QSVM", "F": "F_QAA_Hybrid"}
_SKIP = set()
for _tok in os.environ.get("QMD_SKIP", "").replace(" ", "").split(","):
    if not _tok:
        continue
    _full = _ALIAS.get(_tok.upper(), _tok)
    if _full not in ALL_METHODS:
        raise SystemExit(f"QMD_SKIP: unknown method {_tok!r}. "
                         f"Choose from {sorted(_ALIAS)} or {ALL_METHODS}.")
    if _full in ("A_PCA", "B_PCA_CAE", "C_PCA_QAE"):
        raise SystemExit(f"QMD_SKIP: {_full} is part of the shared ensemble path "
                         f"and cannot be skipped (it costs seconds).")
    _SKIP.add(_full)
METHODS = [m for m in ALL_METHODS if m not in _SKIP]


def want(method):
    """True if `method` is enabled for this run."""
    return method in METHODS


# Per-method output directories (one subfolder per method — professional structure)
METHOD_DIRS = {m: os.path.join(CFG["output_folder"], m) for m in METHODS}
for _method_d in METHOD_DIRS.values():
    os.makedirs(_method_d, exist_ok=True)

# Summary directory — all cross-method comparison plots + shared metrics
SUMMARY_DIR = os.path.join(CFG["output_folder"], "summary")
os.makedirs(SUMMARY_DIR, exist_ok=True)

_cfg_hash = hashlib.md5(json.dumps(
    {k: str(v) for k, v in CFG.items()}, sort_keys=True
).encode()).hexdigest()[:8]

print("=" * 72)
print("QUANTUM-ENHANCED MINERAL DETECTION — FINAL PIPELINE")
print("=" * 72)
print(f"Config hash : {_cfg_hash}  |  Seed: {SEED}"
      f"  |  {time.strftime('%Y-%m-%d %H:%M:%S')}")

# ===========================================================================
# 1.  WAVELENGTH GRID & BAND INDICES
# ===========================================================================
print(f"\n{'=' * 72}")
print("WAVELENGTH GRID & BAND INDICES")
print(f"{'=' * 72}")

HYPERION_WL = load_wavelengths(CFG["data_folder"])
BI          = make_band_indices(HYPERION_WL)
print(f"  Grid: {len(HYPERION_WL)} bands  "
      f"[{HYPERION_WL.min():.0f}–{HYPERION_WL.max():.0f} nm]")
for name, idx in BI.items():
    print(f"  {name:6s} -> band {idx:3d} ({HYPERION_WL[idx]:.1f} nm)")

# ===========================================================================
# 2.  LOAD DATA  (float32 for memory efficiency on large scenes)
# ===========================================================================
print(f"\n{'=' * 72}")
print("LOADING SCENES AND USGS REFERENCES")
print(f"{'=' * 72}")

D = CFG["data_folder"]


def load_scene(fname, tag):
    path = os.path.join(D, fname)
    assert os.path.exists(path), f"Missing: {path} — run step1 first"
    arr = np.load(path).astype(np.float32)   # float32 halves RAM vs float64
    print(f"  OK  {tag:40s}  shape={arr.shape}  dtype={arr.dtype}")
    return arr


# NOTE: Only 3 Hyperion scenes are available:
#   Scene 1 (2017, P43/R34)  &  Scene 2 (2013-Mar, P41/R33) → TRAIN
#   Scene 3 (2013-Jun, P41/R33) → TEST (held-out, same orbit as scene2)
# Scenes 2 & 3 have corr≈0.89 — same area, different dates → similar maps.
scene1 = load_scene("hyperion_scene1_198bands.npy",
                    "Scene 1 (2017-Mar P43/R34) TRAIN")
scene2 = load_scene("hyperion_scene2_198bands.npy",
                    "Scene 2 (2013-Mar P41/R33) TRAIN")
scene3 = load_scene("hyperion_scene3_198bands.npy",
                    "Scene 3 (2013-Jun P41/R33) TEST  [held-out]")
scene4 = load_scene("hyperion_scene4_198bands.npy",
                    "Scene 4 (2014-Oct P41/R34) TRAIN")
usgs_li = np.load(os.path.join(D, "lithium_usgs_198bands.npy"))
usgs_v  = np.load(os.path.join(D, "vanadium_usgs_198bands.npy"))
print(f"  USGS Li  shape={usgs_li.shape}  USGS V shape={usgs_v.shape}")

# ===========================================================================
# 3.  PATCH EXTRACTION  (all 4 scenes)
# ===========================================================================
print(f"\n{'=' * 72}")
print("PATCH EXTRACTION")
print(f"{'=' * 72}")

P = CFG["patch_size"]
BR = CFG["block_grid_r"]
BC = CFG["block_grid_c"]
BLK_SIZE = BR * BC    # 16 blocks per scene


def extract_and_free(cube, label, scene_idx_offset):
    """Extract patches then immediately free the scene cube from RAM."""
    patches, coords, li, v, blk = extract_patches(
        cube, BI, P,
        CFG["cloud_low"], CFG["cloud_high"],
        CFG["min_patch_std"], CFG["max_patches_scene"],
        BR, BC, CFG["eps"],
    )
    blk = blk + scene_idx_offset * BLK_SIZE
    print(f"  {label}: {len(patches)} patches  "
          f"(LiCI mean={li.mean():.4f}  VMI mean={v.mean():.4f})")
    return patches, coords, li, v, blk


t0 = time.time()

px1, co1, li1, v1, bl1 = extract_and_free(scene1, "Scene 1 (2017)", 0)
del scene1

px2, co2, li2, v2, bl2 = extract_and_free(scene2, "Scene 2 (2013-Mar)", 1)
del scene2

px3, co3, li3, v3, bl3 = extract_and_free(scene3, "Scene 3 (2013-Jun) [TEST]", 2)
del scene3

px4, co4, li4, v4, bl4 = extract_and_free(scene4, "Scene 4 (2014-Oct P41/R34) [TRAIN]", 3)
del scene4

print(f"\n  Patch extraction done in {time.time()-t0:.1f}s")

# Train = Scenes 1+2+4  |  Test = Scene 3 (temporal + spatial held-out)
# Scene 3 = same orbit as Scene 2 but June 2013 — genuine temporal transfer test
# Scene 4 = adjacent row (P41/R34), Oct 2014 — adds geographic diversity to training
train_patches = np.concatenate([px1, px2, px4], axis=0, dtype=np.float32)
train_li      = np.concatenate([li1, li2, li4])
train_v       = np.concatenate([v1,  v2,  v4])
train_blk     = np.concatenate([bl1, bl2, bl4])
train_coords  = co1 + co2 + co4    # list of (row,col) tuples
del px1, px2, px4, li1, li2, li4, v1, v2, v4, bl1, bl2, bl4, co1, co2, co4

test_patches  = px3.astype(np.float32)
test_li       = li3
test_v        = v3
test_coords   = co3          # save for visualization
del px3, li3, v3, co3

print(f"\n  TRAIN patches: {len(train_patches)}  (Scenes 1+2+4)")
print(f"  TEST  patches: {len(test_patches)}   (Scene 3 — held-out)")
print(f"  NOTE: Scenes 2 & 3 share same orbit (P41/R33) — similar output maps are expected.")

# ===========================================================================
# 4.  LABEL GENERATION  (non-circular OR logic at 75th percentile)
# ===========================================================================
print(f"\n{'=' * 72}")
print("LABEL GENERATION  (band-ratio absorption-depth indices, OR logic)")
print(f"{'=' * 72}")
print(f"  strategy   : {CFG['label_strategy']}")
print(f"  percentile : {CFG['label_percentile']}th  (top-25% positive rate)")

print("\n  TRAIN labels (thresholds computed from train set):")
train_labels, t_li, t_v = make_labels_percentile(
    train_li, train_v, CFG["label_percentile"]
)

print("\n  TEST labels (same thresholds applied):")
test_labels, _, _ = make_labels_percentile(
    test_li, test_v, CFG["label_percentile"], t_li, t_v
)

# Guard: both classes must be present
if train_labels.sum() == 0 or (train_labels == 0).sum() == 0:
    print("  [WARN] Single class in train — falling back to 50th percentile")
    train_labels, t_li, t_v = make_labels_percentile(
        train_li, train_v, 50.0
    )

if test_labels.sum() == 0 or (test_labels == 0).sum() == 0:
    print("  [WARN] Single class in test — using test median threshold")
    test_labels, _, _ = make_labels_percentile(
        test_li, test_v, 50.0
    )

train_pos_pct = 100.0 * train_labels.mean()

# ===========================================================================
# 5.  PCA  (full 198-band flatten -> RobustScaler -> PCA(25))
# ===========================================================================
print(f"\n{'=' * 72}")
print("PCA FEATURE EXTRACTION  (full 198-band flatten)")
print(f"{'=' * 72}")
print(f"  Input shape: {train_patches.shape}  "
      f"-> flatten -> ({len(train_patches)}, {train_patches.shape[1]*train_patches.shape[2]*train_patches.shape[3]})")

t0 = time.time()
scaler, pca, Z_train = fit_pca(train_patches, CFG["n_pca"], SEED)
Z_test              = apply_pca(test_patches, scaler, pca)
print(f"  PCA done in {time.time()-t0:.1f}s")

# Normalised PCA features for ensemble input
pca_sc = StandardScaler()
Z_train_pca = pca_sc.fit_transform(Z_train).astype(np.float32)
Z_test_pca  = pca_sc.transform(Z_test).astype(np.float32)

# ===========================================================================
# 6.  MINERAL WEIGHTS  (for QAE / CAE loss functions)
# ===========================================================================
mineral_weights_train = make_mineral_weights(train_li, train_v)
mineral_weights_test  = make_mineral_weights(test_li, test_v,
                                              li_ref=train_li, v_ref=train_v)

# ===========================================================================
# 7.  CLASSICAL AUTOENCODER  (ablation B)
# ===========================================================================
print(f"\n{'=' * 72}")
print("CLASSICAL AUTOENCODER  (ablation B)")
print(f"{'=' * 72}")

t0 = time.time()
cae_model, cae_history = train_classical_ae(
    Z_train, mineral_weights_train,
    bottleneck=CFG["cae_bottleneck"],
    epochs=CFG["cae_epochs"],
    lr=CFG["cae_lr"],
    seed=SEED,
)
cae_tr, cae_ts, _cae_sc = extract_cae_features(cae_model, Z_train, Z_test)
print(f"  CAE done in {time.time()-t0:.1f}s")

# ===========================================================================
# 8.  QUANTUM AUTOENCODER  (proposed — method C)
#
#     Role: FEATURE EXTRACTOR
#     Input : tanh(Z_train[:, :6])  —  first 6 PCA dims
#     Output: 6 quantum expectation values  [concatenated with PCA features]
# ===========================================================================
print(f"\n{'=' * 72}")
print(f"QUANTUM AUTOENCODER  (proposed — {CFG['n_qubits']} qubits,"
      f" {CFG['n_layers']} layers)")
print(f"{'=' * 72}")
print(f"  Role      : FEATURE EXTRACTOR (not a classifier)")
print(f"  Input     : tanh(Z[:, :{CFG['n_qubits']}])  "
      f"— first {CFG['n_qubits']} PCA dims")
print(f"  Output    : {CFG['n_qubits']} quantum expectation values <Z_i>")

# Stratified subsample for QAE weight training — equal mineral + background.
# Random sampling with majority imbalance causes the QAE to learn background
# geometry only, weakening its discrimination on mineral patches.
np.random.seed(SEED)
_qae_pos   = np.where(train_labels == 1)[0]
_qae_neg   = np.where(train_labels == 0)[0]
_qae_each  = min(CFG["max_qae_train"] // 2, len(_qae_pos), len(_qae_neg))
_qae_idx   = np.concatenate([
    np.random.choice(_qae_pos, _qae_each, replace=False),
    np.random.choice(_qae_neg, _qae_each, replace=False),
])
np.random.shuffle(_qae_idx)
print(f"  Training subset: {len(_qae_idx)} ({_qae_each} mineral + {_qae_each} background, stratified)")

t0 = time.time()
qae_weights, qae_history  = train_qae(
    Z_train[_qae_idx], mineral_weights_train[_qae_idx],
    n_qubits=CFG["n_qubits"], n_layers=CFG["n_layers"],
    epochs=CFG["qae_epochs"], lr=CFG["qae_lr"],
    patience=CFG["qae_patience"], seed=SEED,
)
print(f"  QAE training done in {time.time()-t0:.1f}s")

print("  Extracting QAE features (all train patches) ...")
t0 = time.time()
qae_tr_raw = extract_qae_features(Z_train, qae_weights,
                                   CFG["n_qubits"], CFG["n_layers"])
qae_ts_raw = extract_qae_features(Z_test,  qae_weights,
                                   CFG["n_qubits"], CFG["n_layers"])
qae_sc = StandardScaler()
qae_tr = qae_sc.fit_transform(qae_tr_raw).astype(np.float32)
qae_ts = qae_sc.transform(qae_ts_raw).astype(np.float32)
print(f"  QAE features: train={qae_tr.shape}  test={qae_ts.shape}"
      f"  ({time.time()-t0:.1f}s)")

if want("C2_QAE_QSVM"):   # -- optional method, see QMD_SKIP --
    # ===========================================================================
    # 8b.  METHOD C2 — QAE FEATURES → QUANTUM KERNEL SVM
    #
    #      Fully-quantum pipeline: QAE compresses spectral structure (Step 1),
    #      then a ZZFeatureMap fidelity kernel measures distances between the
    #      resulting quantum feature vectors in a second Hilbert space (Step 2).
    #
    #      Unlike Method D (QSVM on raw PCA), C2 inputs are already quantum-
    #      compressed 6-dim vectors — the kernel operates on this richer,
    #      more discriminative representation.
    #
    #      Cost: O(n_support²) kernel evaluations for training,
    #            O(N_test × n_support) for inference.
    # ===========================================================================
    print(f"\n{'=' * 72}")
    print(f"METHOD C2 — QAE FEATURES → QSVM  (fully-quantum pipeline)")
    print(f"  Input: 6-dim QAE expectation values  (∈ (-1,+1))")
    print(f"  Kernel: ZZFeatureMap fidelity  |<φ(x1)|φ(x2)>|²")
    print(f"  Support set: {CFG['c2_qasvm_n_support']} (stratified, balanced)")
    print(f"{'=' * 72}")

    t0 = time.time()
    c2_clf, K_c2_tr, K_c2_ts, _c2_idx = build_qsvm_from_features(
        qae_tr_raw, train_labels, qae_ts_raw,
        n_support=CFG["c2_qasvm_n_support"],
        seed=SEED,
    )
    c2_probs = c2_clf.predict_proba(K_c2_ts)[:, 1]
    c2_preds = (c2_probs >= 0.5).astype(np.int32)
    print(f"  C2 QAE→QSVM done in {time.time()-t0:.1f}s")

if want("C3_QAE_VQC"):   # -- optional method, see QMD_SKIP --
    # ===========================================================================
    # 8c.  METHOD C3 — QAE FEATURES → VQC
    #
    #      End-to-end trainable quantum pipeline: QAE latent vectors are
    #      angle-embedded (RY(π × x_i)) into a VQC with StronglyEntanglingLayers.
    #      The VQC is trained with class-weighted BCE on the same stratified
    #      budget as the QAE (max_vqc_train patches, 50/50 mineral/background).
    #
    #      No second tanh: QAE expvals ∈ (-1,+1) are passed directly to
    #      RY(π × x_i) giving angles ∈ (-π, π) — full Bloch-sphere coverage.
    # ===========================================================================
    print(f"\n{'=' * 72}")
    print(f"METHOD C3 — QAE FEATURES → VQC  (end-to-end trainable quantum)")
    print(f"  Input   : 6-dim QAE expectation values  (no second tanh)")
    print(f"  Encoding: RY(π × x_i)  →  angles ∈ (-π, π)")
    print(f"  Circuit : StronglyEntanglingLayers({CFG['n_vqc_layers']} layers,"
          f" {CFG['n_vqc_qubits']} qubits, {CFG['n_vqc_layers']*CFG['n_vqc_qubits']*3} params)")
    print(f"{'=' * 72}")

    np.random.seed(SEED)
    _c3_pos   = np.where(train_labels == 1)[0]
    _c3_neg   = np.where(train_labels == 0)[0]
    _c3_each  = min(CFG["max_vqc_train"] // 2, len(_c3_pos), len(_c3_neg))
    _c3_idx   = np.concatenate([
        np.random.choice(_c3_pos, _c3_each, replace=False),
        np.random.choice(_c3_neg, _c3_each, replace=False),
    ])
    np.random.shuffle(_c3_idx)
    print(f"  Training subset: {len(_c3_idx)} ({_c3_each} mineral + {_c3_each} background, stratified)")

    t0 = time.time()
    vqc_weights, vqc_history = train_vqc_from_features(
        qae_tr_raw[_c3_idx], train_labels[_c3_idx],
        n_qubits=CFG["n_vqc_qubits"],
        n_layers=CFG["n_vqc_layers"],
        epochs=CFG["vqc_epochs"],
        lr=CFG["vqc_lr"],
        patience=CFG["vqc_patience"],
        seed=SEED,
    )
    print(f"  VQC training done in {time.time()-t0:.1f}s")

    print("  C3: Running VQC inference on test set ...")
    t0 = time.time()
    c3_probs, c3_preds = vqc_predict_from_features(
        qae_ts_raw, vqc_weights,
        n_qubits=CFG["n_vqc_qubits"],
        n_layers=CFG["n_vqc_layers"],
    )
    print(f"  C3 QAE→VQC done in {time.time()-t0:.1f}s")

# ===========================================================================
# 9.  USGS SPECTRAL CORRELATION AUXILIARY FEATURES
#     (Pearson r — used as classifier features, NOT for labels)
# ===========================================================================
print(f"\n  Computing USGS spectral correlation features ...")
corr_li_tr = usgs_corr_feature(train_patches, usgs_li)
corr_v_tr  = usgs_corr_feature(train_patches, usgs_v)
corr_li_ts = usgs_corr_feature(test_patches,  usgs_li)
corr_v_ts  = usgs_corr_feature(test_patches,  usgs_v)
corr_tr_raw = np.hstack([corr_li_tr, corr_v_tr])
corr_ts_raw = np.hstack([corr_li_ts, corr_v_ts])

corr_sc = StandardScaler()
corr_tr = corr_sc.fit_transform(corr_tr_raw).astype(np.float32)
corr_ts = corr_sc.transform(corr_ts_raw).astype(np.float32)
print(f"  Corr features: train={corr_tr.shape}  test={corr_ts.shape}")

# ===========================================================================
# 10.  FEATURE SETS FOR ENSEMBLE ABLATION
# ===========================================================================
FEATURE_SETS = {
    # A: PCA only (strict baseline)
    "A_PCA": {
        "train": Z_train_pca,
        "test":  Z_test_pca,
    },
    # B: PCA + CAE bottleneck + USGS corr (classical ablation)
    "B_PCA_CAE": {
        "train": np.hstack([Z_train_pca, cae_tr, corr_tr]),
        "test":  np.hstack([Z_test_pca,  cae_ts, corr_ts]),
    },
    # C: PCA + QAE + USGS corr (proposed method — main contribution)
    "C_PCA_QAE": {
        "train": np.hstack([Z_train_pca, qae_tr, corr_tr]),
        "test":  np.hstack([Z_test_pca,  qae_ts, corr_ts]),
    },
}
for k, v in FEATURE_SETS.items():
    print(f"  {k}: train={v['train'].shape}  test={v['test'].shape}")

if want("D_QSVM"):   # -- optional method, see QMD_SKIP --
    # ===========================================================================
    # 11.  QUANTUM KERNEL SVM  (method D — standalone quantum classifier)
    #
    #      Role: STANDALONE CLASSIFIER using PCA features
    #      Input : tanh(Z[:, :n_qubits])  —  first 6 PCA dims
    #      Kernel: ZZFeatureMap fidelity K(x1,x2) = |<phi(x1)|phi(x2)>|^2
    # ===========================================================================
    print(f"\n{'=' * 72}")
    print(f"QUANTUM KERNEL SVM  (method D — standalone classifier)")
    print(f"  Role  : STANDALONE CLASSIFIER  (NOT a feature extractor)")
    print(f"  Input : tanh(Z[:, :{CFG['n_qubits']}])  — first {CFG['n_qubits']} PCA dims")
    print(f"  Kernel: ZZFeatureMap fidelity (Havlicek et al. 2019)")
    print(f"{'=' * 72}")

    t0 = time.time()
    qsvm_clf, K_qsvm_tr, K_qsvm_ts, _qsvm_idx = build_qsvm(
        Z_train, train_labels, Z_test,
        n_qubits=CFG["n_qubits"],
        n_support=CFG["qsvm_n_train"],
        seed=SEED,
    )
    qsvm_probs = qsvm_clf.predict_proba(K_qsvm_ts)[:, 1]
    qsvm_preds = (qsvm_probs >= 0.5).astype(np.int32)
    print(f"  QSVM done in {time.time()-t0:.1f}s")

if want("F_QAA_Hybrid"):   # -- optional method, see QMD_SKIP --
    # ===========================================================================
    # 12.  METHOD F — QUANTUM ANOMALY AUTOENCODER + HYBRID F+C
    #
    #  Step 1: Train QAA on background-only patches  (no labels used)
    #  Step 2: Anomaly scores = quantum reconstruction error
    #  Step 3: Pseudo-labels from anomaly percentile thresholds
    #  Step 4: Train Method-C ensemble on pseudo-labelled data
    #  Step 5: Evaluate on held-out test set
    # ===========================================================================
    print(f"\n{'=' * 72}")
    print(f"METHOD F — QUANTUM ANOMALY AUTOENCODER  ({CFG['qaa_n_qubits']} qubits,"
          f" n_latent={CFG['qaa_n_latent']}, {CFG['qaa_n_layers']} layers)")
    print(f"{'=' * 72}")
    print(f"  Stage 1 (F) : UNSUPERVISED bottleneck QAE on background only")
    print(f"  Train on    : background patches only  "
          f"(mineral_weight < {CFG['qaa_bg_percentile']}th pct)")
    print(f"  Loss        : 1 − P(trash=|0000⟩)  [Romero et al. 2017 Hilbert-space fidelity]")
    print(f"  Anomaly score: 1 − P(trash=|0000⟩) ∈ [0,1]  (0=background, 1=anomaly)")
    print(f"  Stage 2 (C) : pseudo-label score > {CFG['qaa_pseudo_hi']}th pct → mineral  |  "
          f"< {CFG['qaa_pseudo_lo']}th pct → background")
    print(f"  Hybrid F+C  : Method-C ensemble (RF+GBT+SVM) on QAE features + pseudo-labels")

    # ---- 13a. Select background patches for QAA training ----
    _mw_thresh = float(np.percentile(mineral_weights_train,
                                      CFG["qaa_bg_percentile"]))
    _bg_mask   = mineral_weights_train <= _mw_thresh
    _bg_idx    = np.where(_bg_mask)[0]
    np.random.seed(SEED)
    _bg_train_idx = np.random.choice(
        _bg_idx,
        min(len(_bg_idx), CFG["qaa_max_bg_train"]),
        replace=False,
    )
    print(f"\n  Background patches for QAA: {len(_bg_train_idx)} "
          f"(from {_bg_mask.sum()} with mw <= {_mw_thresh:.4f})")

    # ---- 13b. Train QAA ----
    t0 = time.time()
    qaa_weights, qaa_history = train_qaa(
        Z_train[_bg_train_idx],
        n_qubits=CFG["qaa_n_qubits"],
        n_latent=CFG["qaa_n_latent"],
        n_layers=CFG["qaa_n_layers"],
        epochs=CFG["qaa_epochs"],
        lr=CFG["qaa_lr"],
        patience=CFG["qaa_patience"],
        seed=SEED,
    )
    print(f"  QAA training done in {time.time()-t0:.1f}s")

    # ---- 13c. Anomaly scores for training + test ----
    print("  Computing QAA anomaly scores for TRAIN set ...")
    t0 = time.time()
    train_anomaly_scores = qaa_anomaly_scores(
        Z_train, qaa_weights,
        n_qubits=CFG["qaa_n_qubits"],
        n_latent=CFG["qaa_n_latent"],
        n_layers=CFG["qaa_n_layers"])
    print("  Computing QAA anomaly scores for TEST set ...")
    test_anomaly_scores = qaa_anomaly_scores(
        Z_test, qaa_weights,
        n_qubits=CFG["qaa_n_qubits"],
        n_latent=CFG["qaa_n_latent"],
        n_layers=CFG["qaa_n_layers"])
    print(f"  Anomaly scoring done in {time.time()-t0:.1f}s")
    print(f"  Train scores: mean={train_anomaly_scores.mean():.4f}  "
          f"std={train_anomaly_scores.std():.4f}  "
          f"[{train_anomaly_scores.min():.4f}, {train_anomaly_scores.max():.4f}]")

    # ---- 13d. Pseudo-labels ----
    print("\n  Generating pseudo-labels from anomaly scores:")
    pseudo_labels, certain_mask, _qaa_hi, _qaa_lo = generate_pseudo_labels(
        train_anomaly_scores,
        hi_pct=CFG["qaa_pseudo_hi"],
        lo_pct=CFG["qaa_pseudo_lo"],
    )

    # ---- 13e. Hybrid F+C — build feature sets for pseudo-labelled training ----
    Z_pseudo    = FEATURE_SETS["C_PCA_QAE"]["train"][certain_mask]
    y_pseudo    = pseudo_labels[certain_mask].astype(np.int32)
    blk_pseudo  = train_blk[certain_mask]

    _n_cls = len(np.unique(y_pseudo))
    if _n_cls < 2:
        print("  [WARN] Pseudo-labels contain only one class — "
              "lowering hi_pct to 70 and lo_pct to 30 for fallback")
        pseudo_labels, certain_mask, _qaa_hi, _qaa_lo = generate_pseudo_labels(
            train_anomaly_scores, hi_pct=70.0, lo_pct=30.0)
        Z_pseudo   = FEATURE_SETS["C_PCA_QAE"]["train"][certain_mask]
        y_pseudo   = pseudo_labels[certain_mask].astype(np.int32)
        blk_pseudo = train_blk[certain_mask]

    # Test features unchanged (uses same C_PCA_QAE features)
    X_pseudo_test = FEATURE_SETS["C_PCA_QAE"]["test"]

    # ---- 13f. Train Hybrid ensemble on pseudo-labelled data ----
    print(f"\n  Training Hybrid F+C ensemble on {len(Z_pseudo)} pseudo-labelled patches "
          f"({int(y_pseudo.sum())} pos / {int((y_pseudo==0).sum())} neg) ...")
    t0 = time.time()
    hybrid_clf = build_ensemble(
        Z_pseudo, y_pseudo,
        rf_trees=CFG["rf_trees"], gb_trees=CFG["gb_trees"],
        gb_lr=CFG["gb_lr"], svm_cv=CFG["svm_cv"], seed=SEED,
    )
    hybrid_probs = hybrid_clf.predict_proba(X_pseudo_test)[:, 1]
    hybrid_preds = (hybrid_probs >= 0.5).astype(np.int32)
    print(f"  Hybrid F+C done in {time.time()-t0:.1f}s")


# ===========================================================================
# 13.  SPATIALLY BLOCKED 5-FOLD CV  (on training data only)
# ===========================================================================
print(f"\n{'=' * 72}")
print(f"SPATIALLY BLOCKED {CFG['cv_folds']}-FOLD CROSS-VALIDATION")
print(f"{'=' * 72}")

unique_blks = np.unique(train_blk)
np.random.seed(SEED)
np.random.shuffle(unique_blks)
fold_blks = np.array_split(unique_blks, CFG["cv_folds"])

cv_results = {k: {"auc": [], "f1": []} for k in FEATURE_SETS}

for fold_i, val_blks in enumerate(fold_blks):
    val_mask   = np.isin(train_blk, val_blks)
    tr_mask    = ~val_mask
    if tr_mask.sum() == 0 or val_mask.sum() == 0:
        continue
    y_tr_cv = train_labels[tr_mask]
    y_val_cv = train_labels[val_mask]
    if len(np.unique(y_tr_cv)) < 2 or len(np.unique(y_val_cv)) < 2:
        print(f"  Fold {fold_i+1}: skipped (single class)")
        continue

    print(f"\n  Fold {fold_i+1}  |  train={tr_mask.sum()}  val={val_mask.sum()}")
    for method_name, fset in FEATURE_SETS.items():
        X_cv_tr  = fset["train"][tr_mask]
        X_cv_val = fset["train"][val_mask]
        clf_cv   = build_ensemble(X_cv_tr, y_tr_cv,
                                  rf_trees=CFG["rf_trees"],
                                  gb_trees=CFG["gb_trees"],
                                  gb_lr=CFG["gb_lr"],
                                  svm_cv=CFG["svm_cv"],
                                  seed=SEED)
        prob_cv  = clf_cv.predict_proba(X_cv_val)[:, 1]
        pred_cv  = (prob_cv >= 0.5).astype(np.int32)

        from sklearn.metrics import roc_auc_score, f1_score as _f1
        auc_cv = roc_auc_score(y_val_cv, prob_cv)
        f1_cv  = _f1(y_val_cv, pred_cv, zero_division=0)
        cv_results[method_name]["auc"].append(auc_cv)
        cv_results[method_name]["f1"].append(f1_cv)
        print(f"    {method_name}  AUC={auc_cv:.4f}  F1={f1_cv:.4f}")

print("\n  CV Summary:")
for method_name, res in cv_results.items():
    aucs = res["auc"]
    f1s  = res["f1"]
    if aucs:
        print(f"  {method_name}  AUC={np.mean(aucs):.4f}±{np.std(aucs):.4f}"
              f"  F1={np.mean(f1s):.4f}±{np.std(f1s):.4f}")

# ===========================================================================
# 14.  TRAIN FINAL ENSEMBLE ON FULL TRAINING SET
# ===========================================================================
print(f"\n{'=' * 72}")
print("FITTING FINAL ENSEMBLES  (full training set)")
print(f"{'=' * 72}")

ensemble_clfs = {}
for method_name, fset in FEATURE_SETS.items():
    print(f"\n  [{method_name}]  dim={fset['train'].shape[1]}")
    clf = build_ensemble(
        fset["train"], train_labels,
        rf_trees=CFG["rf_trees"], gb_trees=CFG["gb_trees"],
        gb_lr=CFG["gb_lr"], svm_cv=CFG["svm_cv"], seed=SEED,
    )
    ensemble_clfs[method_name] = clf

# ===========================================================================
# 14b.  TRAIN-SET EVALUATION  (overfitting / generalization check)
# ===========================================================================
print(f"\n{'=' * 72}")
print("TRAIN-SET EVALUATION  (generalization gap check)")
print(f"{'=' * 72}")

train_results = []
train_probs   = {}
train_preds   = {}

from sklearn.metrics import roc_auc_score as _auc_score
for method_name, clf in ensemble_clfs.items():
    X_tr_m   = FEATURE_SETS[method_name]["train"]
    tr_prob  = clf.predict_proba(X_tr_m)[:, 1]
    tr_pred  = (tr_prob >= 0.5).astype(np.int32)
    tr_m     = compute_metrics(train_labels, tr_pred, tr_prob,
                               label=f"{method_name}_TRAIN")
    train_results.append(tr_m)
    train_probs[method_name] = tr_prob
    train_preds[method_name] = tr_pred
    tr_auc = _auc_score(train_labels, tr_prob)
    print(f"  {method_name} TRAIN  AUC={tr_auc:.4f}  "
          f"F1={tr_m['f1']:.4f}  MCC={tr_m['mcc']:.4f}")

if want("D_QSVM"):
    # QSVM  train evaluation (only on the subset used for training)
    qsvm_train_probs = qsvm_clf.predict_proba(K_qsvm_tr)[:, 1]
    qsvm_train_preds = (qsvm_train_probs >= 0.5).astype(np.int32)
    _qsvm_train_labels = train_labels[_qsvm_idx]
    train_probs["D_QSVM"] = qsvm_train_probs
    train_preds["D_QSVM"] = qsvm_train_preds
    _qsvm_tr_auc = _auc_score(_qsvm_train_labels, qsvm_train_probs)
    print(f"  D_QSVM  TRAIN (subset={len(_qsvm_idx)})  AUC={_qsvm_tr_auc:.4f}")

if want("F_QAA_Hybrid"):
    # Method F train evaluation
    hybrid_train_probs = hybrid_clf.predict_proba(
        FEATURE_SETS["C_PCA_QAE"]["train"])[:, 1]
    hybrid_train_preds = (hybrid_train_probs >= 0.5).astype(np.int32)
    train_probs["F_QAA_Hybrid"] = hybrid_train_probs
    train_preds["F_QAA_Hybrid"] = hybrid_train_preds
    _f_tr_auc = _auc_score(train_labels, hybrid_train_probs)
    print(f"  F_QAA_Hybrid  TRAIN  AUC={_f_tr_auc:.4f}")

if want("C2_QAE_QSVM"):
    # Method C2 train evaluation (on the stratified support subset)
    c2_train_probs = c2_clf.predict_proba(K_c2_tr)[:, 1]
    c2_train_preds = (c2_train_probs >= 0.5).astype(np.int32)
    _c2_train_labels = train_labels[_c2_idx]
    train_probs["C2_QAE_QSVM"] = c2_train_probs
    train_preds["C2_QAE_QSVM"] = c2_train_preds
    _c2_tr_auc = _auc_score(_c2_train_labels, c2_train_probs)
    print(f"  C2_QAE_QSVM   TRAIN (support subset={len(_c2_idx)})  AUC={_c2_tr_auc:.4f}")

if want("C3_QAE_VQC"):
    # Method C3 train evaluation (full training set inference)
    c3_train_probs, c3_train_preds = vqc_predict_from_features(
        qae_tr_raw, vqc_weights,
        n_qubits=CFG["n_vqc_qubits"],
        n_layers=CFG["n_vqc_layers"],
    )
    train_probs["C3_QAE_VQC"] = c3_train_probs
    train_preds["C3_QAE_VQC"] = c3_train_preds
    _c3_tr_auc = _auc_score(train_labels, c3_train_probs)
    print(f"  C3_QAE_VQC    TRAIN  AUC={_c3_tr_auc:.4f}")

# ===========================================================================
# 15.  EVALUATION ON HELD-OUT TEST SET
# ===========================================================================
print(f"\n{'=' * 72}")
print("HELD-OUT TEST SET EVALUATION  (Scene 3)")
print(f"{'=' * 72}")

all_results = []
all_probs   = {}
all_preds   = {}

for method_name, clf in ensemble_clfs.items():
    X_ts     = FEATURE_SETS[method_name]["test"]
    probs    = clf.predict_proba(X_ts)[:, 1]
    preds    = (probs >= 0.5).astype(np.int32)
    ci_lo, ci_hi = bootstrap_auc_ci(test_labels, probs,
                                     n=CFG["bootstrap_n"],
                                     ci=CFG["ci_level"],
                                     seed=SEED)
    m = compute_metrics(test_labels, preds, probs, label=method_name)
    m["auc_ci"] = (ci_lo, ci_hi)
    all_results.append(m)
    all_probs[method_name] = probs
    all_preds[method_name] = preds
    print_metrics(m)
    print(f"             AUC 95%CI = [{ci_lo:.4f}, {ci_hi:.4f}]")

if want("D_QSVM"):
    # QSVM (method D)
    m_qsvm = compute_metrics(test_labels, qsvm_preds, qsvm_probs, label="D_QSVM")
    ci_lo, ci_hi = bootstrap_auc_ci(test_labels, qsvm_probs,
                                     n=CFG["bootstrap_n"], ci=CFG["ci_level"])
    m_qsvm["auc_ci"] = (ci_lo, ci_hi)
    all_results.append(m_qsvm)
    all_probs["D_QSVM"] = qsvm_probs
    all_preds["D_QSVM"] = qsvm_preds
    print_metrics(m_qsvm)
    print(f"             AUC 95%CI = [{ci_lo:.4f}, {ci_hi:.4f}]")

if want("F_QAA_Hybrid"):
    # Method F: Hybrid QAA
    m_f = compute_metrics(test_labels, hybrid_preds, hybrid_probs,
                          label="F_QAA_Hybrid")
    ci_lo, ci_hi = bootstrap_auc_ci(test_labels, hybrid_probs,
                                     n=CFG["bootstrap_n"], ci=CFG["ci_level"])
    m_f["auc_ci"] = (ci_lo, ci_hi)
    all_results.append(m_f)
    all_probs["F_QAA_Hybrid"] = hybrid_probs
    all_preds["F_QAA_Hybrid"] = hybrid_preds
    print_metrics(m_f)
    print(f"             AUC 95%CI = [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  [Method F] Pseudo-label thresholds: hi={_qaa_hi:.4f} lo={_qaa_lo:.4f}")
    print(f"  [Method F] Pseudo-training size: {len(Z_pseudo)}  "
          f"({int(y_pseudo.sum())} pos / {int((y_pseudo==0).sum())} neg)")

if want("C2_QAE_QSVM"):
    # Method C2: QAE → QSVM
    m_c2 = compute_metrics(test_labels, c2_preds, c2_probs, label="C2_QAE_QSVM")
    ci_lo, ci_hi = bootstrap_auc_ci(test_labels, c2_probs,
                                     n=CFG["bootstrap_n"], ci=CFG["ci_level"],
                                     seed=SEED)
    m_c2["auc_ci"] = (ci_lo, ci_hi)
    all_results.append(m_c2)
    all_probs["C2_QAE_QSVM"] = c2_probs
    all_preds["C2_QAE_QSVM"] = c2_preds
    print_metrics(m_c2)
    print(f"             AUC 95%CI = [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  [C2] Quantum features → quantum kernel: fully-quantum pipeline")

if want("C3_QAE_VQC"):
    # Method C3: QAE → VQC
    m_c3 = compute_metrics(test_labels, c3_preds, c3_probs, label="C3_QAE_VQC")
    ci_lo, ci_hi = bootstrap_auc_ci(test_labels, c3_probs,
                                     n=CFG["bootstrap_n"], ci=CFG["ci_level"],
                                     seed=SEED)
    m_c3["auc_ci"] = (ci_lo, ci_hi)
    all_results.append(m_c3)
    all_probs["C3_QAE_VQC"] = c3_probs
    all_preds["C3_QAE_VQC"] = c3_preds
    print_metrics(m_c3)
    print(f"             AUC 95%CI = [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  [C3] QAE features → VQC: end-to-end trainable quantum pipeline")

# ===========================================================================
# 16.  McNEMAR TESTS  (quantum advantage significance)
# ===========================================================================
print(f"\n{'=' * 72}")
print("McNEMAR STATISTICAL TESTS")
print(f"{'=' * 72}")

mcnemar_pairs = [
    ("C_PCA_QAE",   "B_PCA_CAE"),    # QAE vs CAE  (main quantum advantage claim)
    ("C_PCA_QAE",   "A_PCA"),        # QAE vs PCA baseline
    ("B_PCA_CAE",   "A_PCA"),        # CAE vs PCA  (classical improvement)
    ("F_QAA_Hybrid","A_PCA"),        # Hybrid F vs PCA baseline
    ("F_QAA_Hybrid","C_PCA_QAE"),    # Hybrid F vs supervised QAE
    # ---- C2 and C3 pairwise tests -----------------------------------------
    ("C2_QAE_QSVM", "C_PCA_QAE"),    # C2 (QAE→QSVM) vs C (QAE→ensemble)
    ("C3_QAE_VQC",  "C_PCA_QAE"),    # C3 (QAE→VQC) vs C (QAE→ensemble)
    ("C2_QAE_QSVM", "C3_QAE_VQC"),   # C2 vs C3  (QSVM vs VQC on same features)
    ("C2_QAE_QSVM", "D_QSVM"),       # C2 (QAE features) vs D (PCA features) for QSVM
]
mcnemar_results = []
for (na, nb) in mcnemar_pairs:
    if na in all_preds and nb in all_preds:
        chi2v, pv = mcnemar_test(test_labels, all_preds[na], all_preds[nb])
        sig = "** SIGNIFICANT **" if pv < 0.05 else "not significant"
        print(f"  {na} vs {nb}:  chi2={chi2v:.4f}  p={pv:.4f}  {sig}")
        mcnemar_results.append((na, nb, chi2v, pv))

# ===========================================================================
# 17.  SAVE RESULTS
# ===========================================================================
print(f"\n{'=' * 72}")
print("SAVING RESULTS")
print(f"{'=' * 72}")

save_maps(all_probs, test_labels, CFG["output_folder"],
          test_coords=test_coords, method_dirs=METHOD_DIRS)
metrics_path = save_metrics_txt(
    all_results, mcnemar_results,
    SUMMARY_DIR,
    train_pos_pct,
)

# Save per-method individual metrics.txt to each method folder
for _mr in all_results:
    _mn = _mr.get("label", "")
    if _mn in METHOD_DIRS:
        _mp = os.path.join(METHOD_DIRS[_mn], "metrics.txt")
        with open(_mp, "w", encoding="utf-8") as _mf:
            _mf.write(f"Method  : {_mn}\n")
            _mf.write("=" * 40 + "\n")
            for _k in ("auc", "f1", "mcc", "precision", "recall", "acc"):
                if _k in _mr:
                    _mf.write(f"{_k.upper():12s} = {_mr[_k]:.4f}\n")
            if "auc_ci" in _mr:
                _lo, _hi = _mr["auc_ci"]
                _mf.write(f"AUC 95% CI   = [{_lo:.4f}, {_hi:.4f}]\n")
        print(f"  Method metrics: {_mp}")

if want("F_QAA_Hybrid"):
    # Save QAA anomaly scores to F_QAA_Hybrid folder
    np.save(os.path.join(METHOD_DIRS["F_QAA_Hybrid"], "anomaly_scores_train.npy"),
            train_anomaly_scores)
    np.save(os.path.join(METHOD_DIRS["F_QAA_Hybrid"], "anomaly_scores_test.npy"),
            test_anomaly_scores)
    print(f"  Anomaly scores: {METHOD_DIRS['F_QAA_Hybrid']}/anomaly_scores_*.npy")

# Save CV summary
cv_path = os.path.join(SUMMARY_DIR, "cv_results.txt")
with open(cv_path, "w", encoding="utf-8") as f:
    f.write("Spatially Blocked CV Results\n")
    f.write("=" * 40 + "\n")
    for method_name, res in cv_results.items():
        aucs = res["auc"]
        f1s  = res["f1"]
        if aucs:
            f.write(f"{method_name}  AUC={np.mean(aucs):.4f}+-{np.std(aucs):.4f}"
                    f"  F1={np.mean(f1s):.4f}+-{np.std(f1s):.4f}\n")

print(f"\nMetrics saved to : {metrics_path}")
print(f"CV results saved : {cv_path}")
print(f"Summary folder   : {SUMMARY_DIR}")

# ===========================================================================
# 19.  VISUALIZATIONS  (comprehensive senior-researcher output)
# ===========================================================================
print(f"\n{'=' * 72}")
print("GENERATING OUTPUT VISUALIZATIONS")
print(f"{'=' * 72}")

patch_size_viz = CFG["patch_size"]

# 1. Per-method probability heatmaps
plot_probability_heatmaps(
    all_probs, test_coords, test_labels, SUMMARY_DIR,
    patch_size=patch_size_viz,
    method_dirs=METHOD_DIRS,
)

# 2. RGB overlay (no cube at this point — fast path without reloading)
plot_rgb_mineral_overlay(
    all_probs.get("C_PCA_QAE", list(all_probs.values())[0]),
    test_coords, test_labels, SUMMARY_DIR,
    scene_cube=None,
    method_name="C_PCA_QAE",
    patch_size=patch_size_viz,
)

if want("F_QAA_Hybrid"):
    # 3. Anomaly score map (Method F) — saved to F_QAA_Hybrid/ and summary/
    plot_anomaly_score_map(
        train_anomaly_scores, test_anomaly_scores,
        test_coords, test_labels, METHOD_DIRS["F_QAA_Hybrid"],
        patch_size=patch_size_viz,
    )

# 4. ROC curves
plot_roc_curves(all_probs, test_labels, SUMMARY_DIR)

# 5. Method comparison bar chart
plot_method_comparison(all_results, SUMMARY_DIR)

# 6. All maps in one grid
plot_all_maps_grid(
    all_probs, test_coords, test_labels, SUMMARY_DIR,
    patch_size=patch_size_viz,
)

# 7. Training loss convergence curves (including VQC / C3)
plot_training_loss_curves(
    cae_history, qae_history,
    qaa_history if want("F_QAA_Hybrid") else {},
    SUMMARY_DIR,
    vqc_history=vqc_history if want("C3_QAE_VQC") else None,
)

# 8. Confusion matrices — test set
plot_confusion_matrices(
    test_preds=all_preds,
    test_labels=test_labels,
    output_folder=SUMMARY_DIR,
    train_preds=train_preds,
    train_labels=train_labels,
)

# 9. Precision-Recall curves
plot_pr_curves(all_probs, test_labels, SUMMARY_DIR)

# 10. CV fold box-plots
plot_cv_boxplot(cv_results, SUMMARY_DIR)

# 11. Train vs Test generalization gap
plot_train_test_comparison(cv_results, all_results, SUMMARY_DIR)

# 12. QSVM quantum kernel matrix heatmap
if want("D_QSVM"):
    plot_qsvm_kernel_heatmap(
        K_qsvm_tr, _qsvm_idx, train_labels, SUMMARY_DIR,
    )

# 13. t-SNE feature space
plot_feature_tsne(
    Z_train_pca, qae_tr_raw, cae_tr, train_labels,
    Z_test_pca,  qae_ts_raw, cae_ts, test_labels,
    SUMMARY_DIR,
)

# 14. Label / index distribution
plot_label_distribution(
    train_li, train_v, train_labels,
    test_li,  test_v,  test_labels,
    SUMMARY_DIR,
)

# 15. LaTeX + CSV metrics table
save_latex_metrics_table(all_results, mcnemar_results, SUMMARY_DIR)

print(f"\n{'=' * 72}")
print("PIPELINE COMPLETE")
print(f"{'=' * 72}")
print(f"\nOutput structure:")
print(f"  {CFG['output_folder']}/")
for _m in METHODS:
    print(f"    {_m + '/':<18}→ prob_map.npy  probability_heatmap.png  metrics.txt")
    if _m == "F_QAA_Hybrid":
        print(f"                        anomaly_scores_train.npy  anomaly_scores_test.npy")
if _SKIP:
    print(f"\n  Skipped this run (QMD_SKIP): {', '.join(sorted(_SKIP))}")
print(f"    summary/          → all_metrics.txt  cv_results.txt  roc_curves.png")
print(f"                        method_comparison_bar.png  training_loss_curves.png")
print(f"                        confusion_matrices_*.png  feature_tsne.png  ...")

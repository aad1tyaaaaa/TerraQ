#!/usr/bin/env python3
"""
experiments/run_noise_analysis.py
==================================
NISQ Noise Resilience Analysis for Quantum Mineral Detection

Systematically evaluates the QAE+ensemble pipeline under realistic
quantum hardware noise conditions:

  1. Depolarizing noise sweep  (0.0 → 0.1)
  2. Amplitude damping sweep   (0.0 → 0.05)
  3. Finite shot noise sweep   (256 → 8192 shots)
  4. Combined noise scenario   (depolarizing + shot noise)

Generates publication-quality figures:
  - fig_noise_depolarizing.png  — AUC degradation vs depolarizing rate
  - fig_noise_amplitude_damping.png — AUC degradation vs T1 decay
  - fig_noise_shots.png — AUC vs finite shot count
  - fig_noise_combined.png — combined analysis summary

All results saved to outputs/noise_analysis.json for reproducibility.

Prerequisites
-------------
Run the main pipeline first:
    python experiments/run_pipeline.py

This script loads the trained QAE weights and ensemble classifiers
from the pipeline run, then re-evaluates under noise conditions.

Usage
-----
    cd TerraQ
    python experiments/run_noise_analysis.py
"""

import os
import sys
import time
import json
import warnings
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
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
    compute_metrics, bootstrap_auc_ci, print_metrics,
)
from src.quantum.qae import train_qae, extract_qae_features
from src.quantum.noise import (
    extract_noisy_qae_features,
    run_noise_sweep_qae,
    run_shot_noise_sweep,
)
from sklearn.preprocessing import StandardScaler

# Reproducibility
import random
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
os.environ["PYTHONHASHSEED"] = str(SEED)

NOISE_DIR = os.path.join(CFG["output_folder"], "noise_analysis")
os.makedirs(NOISE_DIR, exist_ok=True)

print("=" * 72)
print("NISQ NOISE RESILIENCE ANALYSIS")
print("=" * 72)
print(f"  Depolarizing levels : {CFG['noise_depol_levels']}")
print(f"  Amplitude damping   : {CFG['noise_ad_levels']}")
print(f"  Shot counts         : {CFG['noise_shots_list']}")
print(f"  Output directory    : {NOISE_DIR}")

# ===========================================================================
# 1. LOAD DATA & RECONSTRUCT PIPELINE STATE
# ===========================================================================
print(f"\n{'=' * 72}")
print("LOADING DATA & RECONSTRUCTING PIPELINE STATE")
print(f"{'=' * 72}")

D = CFG["data_folder"]
HYPERION_WL = load_wavelengths(D)
BI = make_band_indices(HYPERION_WL)


def load_scene(fname, tag):
    path = os.path.join(D, fname)
    assert os.path.exists(path), f"Missing: {path} — run step1 first"
    arr = np.load(path).astype(np.float32)
    print(f"  OK  {tag:40s}  shape={arr.shape}")
    return arr


scene1 = load_scene("hyperion_scene1_198bands.npy", "Scene 1 TRAIN")
scene2 = load_scene("hyperion_scene2_198bands.npy", "Scene 2 TRAIN")
scene3 = load_scene("hyperion_scene3_198bands.npy", "Scene 3 TEST")
scene4 = load_scene("hyperion_scene4_198bands.npy", "Scene 4 TRAIN")
usgs_li = np.load(os.path.join(D, "lithium_usgs_198bands.npy"))
usgs_v  = np.load(os.path.join(D, "vanadium_usgs_198bands.npy"))

# Patch extraction
P  = CFG["patch_size"]
BR = CFG["block_grid_r"]
BC = CFG["block_grid_c"]
BLK_SIZE = BR * BC

print("\n  Extracting patches ...")


def extract_and_free(cube, label, offset):
    patches, coords, li, v, blk = extract_patches(
        cube, BI, P, CFG["cloud_low"], CFG["cloud_high"],
        CFG["min_patch_std"], CFG["max_patches_scene"], BR, BC, CFG["eps"],
    )
    blk = blk + offset * BLK_SIZE
    print(f"  {label}: {len(patches)} patches")
    return patches, coords, li, v, blk


px1, _, li1, v1, bl1 = extract_and_free(scene1, "Scene 1", 0); del scene1
px2, _, li2, v2, bl2 = extract_and_free(scene2, "Scene 2", 1); del scene2
px3, _, li3, v3, bl3 = extract_and_free(scene3, "Scene 3", 2); del scene3
px4, _, li4, v4, bl4 = extract_and_free(scene4, "Scene 4", 3); del scene4

train_patches = np.concatenate([px1, px2, px4], axis=0, dtype=np.float32)
train_li = np.concatenate([li1, li2, li4])
train_v  = np.concatenate([v1, v2, v4])
del px1, px2, px4, li1, li2, li4, v1, v2, v4

test_patches = px3.astype(np.float32)
test_li, test_v = li3, v3
del px3, li3, v3

print(f"  TRAIN: {len(train_patches)}  TEST: {len(test_patches)}")

# Labels
print("\n  Generating labels ...")
train_labels, t_li, t_v = make_labels_percentile(
    train_li, train_v, CFG["label_percentile"])
test_labels, _, _ = make_labels_percentile(
    test_li, test_v, CFG["label_percentile"], t_li, t_v)

# PCA
print("\n  Fitting PCA ...")
scaler, pca, Z_train = fit_pca(train_patches, CFG["n_pca"], SEED)
Z_test = apply_pca(test_patches, scaler, pca)

pca_sc = StandardScaler()
Z_train_pca = pca_sc.fit_transform(Z_train).astype(np.float32)
Z_test_pca  = pca_sc.transform(Z_test).astype(np.float32)

# Mineral weights
mineral_weights_train = make_mineral_weights(train_li, train_v)

# USGS correlation features
print("  Computing USGS correlation features ...")
corr_li_tr = usgs_corr_feature(train_patches, usgs_li)
corr_v_tr  = usgs_corr_feature(train_patches, usgs_v)
corr_li_ts = usgs_corr_feature(test_patches, usgs_li)
corr_v_ts  = usgs_corr_feature(test_patches, usgs_v)
corr_sc = StandardScaler()
corr_tr = corr_sc.fit_transform(np.hstack([corr_li_tr, corr_v_tr])).astype(np.float32)
corr_ts = corr_sc.transform(np.hstack([corr_li_ts, corr_v_ts])).astype(np.float32)

# ===========================================================================
# 2. TRAIN QAE (same as pipeline)
# ===========================================================================
print(f"\n{'=' * 72}")
print("TRAINING QAE (same parameters as main pipeline)")
print(f"{'=' * 72}")

np.random.seed(SEED)
_pos = np.where(train_labels == 1)[0]
_neg = np.where(train_labels == 0)[0]
_each = min(CFG["max_qae_train"] // 2, len(_pos), len(_neg))
_idx = np.concatenate([
    np.random.choice(_pos, _each, replace=False),
    np.random.choice(_neg, _each, replace=False),
])
np.random.shuffle(_idx)

t0 = time.time()
qae_weights, qae_history = train_qae(
    Z_train[_idx], mineral_weights_train[_idx],
    n_qubits=CFG["n_qubits"], n_layers=CFG["n_layers"],
    epochs=CFG["qae_epochs"], lr=CFG["qae_lr"],
    patience=CFG["qae_patience"], seed=SEED,
)
print(f"  QAE training done in {time.time()-t0:.1f}s")

# Extract ideal QAE features
print("  Extracting ideal QAE features ...")
qae_tr_raw = extract_qae_features(Z_train, qae_weights, CFG["n_qubits"], CFG["n_layers"])
qae_ts_raw = extract_qae_features(Z_test, qae_weights, CFG["n_qubits"], CFG["n_layers"])
qae_sc = StandardScaler()
qae_tr = qae_sc.fit_transform(qae_tr_raw).astype(np.float32)
qae_ts = qae_sc.transform(qae_ts_raw).astype(np.float32)

# ===========================================================================
# 3. TRAIN ENSEMBLE (Method C)
# ===========================================================================
print(f"\n{'=' * 72}")
print("TRAINING METHOD C ENSEMBLE (for noise evaluation)")
print(f"{'=' * 72}")

X_train_C = np.hstack([Z_train_pca, qae_tr, corr_tr])
X_test_C  = np.hstack([Z_test_pca, qae_ts, corr_ts])

ensemble_C = build_ensemble(
    X_train_C, train_labels,
    rf_trees=CFG["rf_trees"], gb_trees=CFG["gb_trees"],
    gb_lr=CFG["gb_lr"], svm_cv=CFG["svm_cv"], seed=SEED,
)

# Ideal performance baseline
ideal_probs = ensemble_C.predict_proba(X_test_C)[:, 1]
ideal_preds = (ideal_probs >= 0.5).astype(np.int32)
ideal_metrics = compute_metrics(test_labels, ideal_preds, ideal_probs, "C_PCA_QAE_ideal")
print_metrics(ideal_metrics)
ideal_auc = ideal_metrics["roc_auc"]

# ===========================================================================
# 4. NOISE SWEEP — DEPOLARIZING
# ===========================================================================
print(f"\n{'=' * 72}")
print("NOISE SWEEP — DEPOLARIZING CHANNEL")
print(f"{'=' * 72}")

t0 = time.time()
depol_results = run_noise_sweep_qae(
    Z_test, test_labels, qae_weights, ensemble_C, qae_sc,
    Z_test_pca, corr_ts,
    n_qubits=CFG["n_qubits"], n_layers=CFG["n_layers"],
    noise_levels=CFG["noise_depol_levels"],
    noise_type="depolarizing",
)
print(f"\n  Depolarizing sweep done in {time.time()-t0:.1f}s")

# ===========================================================================
# 5. NOISE SWEEP — AMPLITUDE DAMPING
# ===========================================================================
print(f"\n{'=' * 72}")
print("NOISE SWEEP — AMPLITUDE DAMPING")
print(f"{'=' * 72}")

t0 = time.time()
ad_results = run_noise_sweep_qae(
    Z_test, test_labels, qae_weights, ensemble_C, qae_sc,
    Z_test_pca, corr_ts,
    n_qubits=CFG["n_qubits"], n_layers=CFG["n_layers"],
    noise_levels=CFG["noise_ad_levels"],
    noise_type="amplitude_damping",
)
print(f"\n  Amplitude damping sweep done in {time.time()-t0:.1f}s")

# ===========================================================================
# 6. SHOT NOISE SWEEP
# ===========================================================================
print(f"\n{'=' * 72}")
print("SHOT NOISE SWEEP — FINITE MEASUREMENT SAMPLING")
print(f"{'=' * 72}")

t0 = time.time()
shot_results = run_shot_noise_sweep(
    Z_test, test_labels, qae_weights, ensemble_C, qae_sc,
    Z_test_pca, corr_ts,
    n_qubits=CFG["n_qubits"], n_layers=CFG["n_layers"],
    shots_list=CFG["noise_shots_list"],
)
print(f"\n  Shot noise sweep done in {time.time()-t0:.1f}s")

# ===========================================================================
# 7. SAVE RESULTS
# ===========================================================================
print(f"\n{'=' * 72}")
print("SAVING RESULTS")
print(f"{'=' * 72}")

all_results = {
    "ideal_baseline": {
        "roc_auc": ideal_metrics["roc_auc"],
        "f1": ideal_metrics["f1"],
        "mcc": ideal_metrics["mcc"],
    },
    "depolarizing_sweep": depol_results,
    "amplitude_damping_sweep": ad_results,
    "shot_noise_sweep": shot_results,
}

results_path = os.path.join(NOISE_DIR, "noise_analysis.json")
with open(results_path, "w") as f:
    json.dump(all_results, f, indent=2)
print(f"  Results saved to: {results_path}")

# ===========================================================================
# 8. PUBLICATION-QUALITY PLOTS
# ===========================================================================
print(f"\n{'=' * 72}")
print("GENERATING PUBLICATION FIGURES")
print(f"{'=' * 72}")

# --- Style ---
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 12,
    "axes.linewidth": 1.2,
    "xtick.major.width": 1.0,
    "ytick.major.width": 1.0,
})


def _plot_noise_sweep(results, xlabel, title, fname, ideal_auc, log_scale=False):
    """Generic noise sweep plotter."""
    levels = [v["noise_level"] if "noise_level" in v else v["shots"]
              for v in results.values()]
    aucs = [v["roc_auc"] for v in results.values()]
    f1s  = [v["f1"] for v in results.values()]
    mccs = [v["mcc"] for v in results.values()]

    fig, ax1 = plt.subplots(1, 1, figsize=(8, 5))

    color_auc = "#2563eb"
    color_f1  = "#16a34a"
    color_mcc = "#dc2626"

    ax1.plot(levels, aucs, "o-", color=color_auc, linewidth=2.5,
             markersize=8, label="ROC-AUC", zorder=5)
    ax1.plot(levels, f1s, "s--", color=color_f1, linewidth=2.0,
             markersize=6, label="F1-Score", zorder=4)
    ax1.plot(levels, mccs, "^:", color=color_mcc, linewidth=2.0,
             markersize=6, label="MCC", zorder=3)

    # Ideal baseline reference line
    ax1.axhline(y=ideal_auc, color=color_auc, linewidth=1.0,
                linestyle=":", alpha=0.5,
                label=f"Ideal AUC = {ideal_auc:.4f}")

    # NISQ hardware reference band (IBM Eagle typical range)
    if "depol" in fname.lower():
        ax1.axvspan(0.001, 0.01, alpha=0.1, color="gray",
                    label="IBM Eagle range")

    ax1.set_xlabel(xlabel, fontsize=13)
    ax1.set_ylabel("Metric Value", fontsize=13)
    ax1.set_title(title, fontsize=14, fontweight="bold")
    ax1.legend(loc="lower left", fontsize=10, framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-0.1, 1.05)

    if log_scale and all(l > 0 for l in levels):
        ax1.set_xscale("log")

    fig.tight_layout()
    out_path = os.path.join(NOISE_DIR, fname)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# Plot 1: Depolarizing noise
_plot_noise_sweep(
    depol_results,
    xlabel="Depolarizing probability (p)",
    title="QAE Pipeline: Depolarizing Noise Resilience",
    fname="fig_noise_depolarizing.png",
    ideal_auc=ideal_auc,
)

# Plot 2: Amplitude damping
_plot_noise_sweep(
    ad_results,
    xlabel="Amplitude damping parameter (γ)",
    title="QAE Pipeline: Amplitude Damping Resilience",
    fname="fig_noise_amplitude_damping.png",
    ideal_auc=ideal_auc,
)

# Plot 3: Shot noise
_plot_noise_sweep(
    shot_results,
    xlabel="Number of shots",
    title="QAE Pipeline: Finite Shot Noise Effect",
    fname="fig_noise_shots.png",
    ideal_auc=ideal_auc,
    log_scale=True,
)

# Plot 4: Combined summary figure
print("\n  Generating combined summary figure ...")
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# Panel 1: Depolarizing
depol_levels = [v["noise_level"] for v in depol_results.values()]
depol_aucs   = [v["roc_auc"] for v in depol_results.values()]
axes[0].plot(depol_levels, depol_aucs, "o-", color="#2563eb",
             linewidth=2.5, markersize=8, label="ROC-AUC")
axes[0].axhline(y=ideal_auc, color="#2563eb", linewidth=1.0,
                linestyle=":", alpha=0.5)
axes[0].axvspan(0.001, 0.01, alpha=0.1, color="gray",
                label="IBM Eagle range")
axes[0].set_xlabel("Depolarizing p", fontsize=12)
axes[0].set_ylabel("ROC-AUC", fontsize=12)
axes[0].set_title("(a) Depolarizing Noise", fontsize=13, fontweight="bold")
axes[0].legend(fontsize=9)
axes[0].grid(True, alpha=0.3)
axes[0].set_ylim(0.3, 0.85)

# Panel 2: Amplitude damping
ad_levels = [v["noise_level"] for v in ad_results.values()]
ad_aucs   = [v["roc_auc"] for v in ad_results.values()]
axes[1].plot(ad_levels, ad_aucs, "s-", color="#16a34a",
             linewidth=2.5, markersize=8, label="ROC-AUC")
axes[1].axhline(y=ideal_auc, color="#16a34a", linewidth=1.0,
                linestyle=":", alpha=0.5)
axes[1].set_xlabel("Amplitude damping γ", fontsize=12)
axes[1].set_ylabel("ROC-AUC", fontsize=12)
axes[1].set_title("(b) Amplitude Damping", fontsize=13, fontweight="bold")
axes[1].legend(fontsize=9)
axes[1].grid(True, alpha=0.3)
axes[1].set_ylim(0.3, 0.85)

# Panel 3: Shot noise
shot_counts = [v["shots"] for v in shot_results.values()]
shot_aucs   = [v["roc_auc"] for v in shot_results.values()]
axes[2].plot(shot_counts, shot_aucs, "^-", color="#dc2626",
             linewidth=2.5, markersize=8, label="ROC-AUC")
axes[2].axhline(y=ideal_auc, color="#dc2626", linewidth=1.0,
                linestyle=":", alpha=0.5)
axes[2].set_xlabel("Number of shots", fontsize=12)
axes[2].set_ylabel("ROC-AUC", fontsize=12)
axes[2].set_title("(c) Finite Shot Noise", fontsize=13, fontweight="bold")
axes[2].set_xscale("log")
axes[2].legend(fontsize=9)
axes[2].grid(True, alpha=0.3)
axes[2].set_ylim(0.3, 0.85)

fig.suptitle("NISQ Noise Resilience Analysis — QAE Pipeline",
             fontsize=15, fontweight="bold", y=1.02)
fig.tight_layout()
combined_path = os.path.join(NOISE_DIR, "fig_noise_combined.png")
fig.savefig(combined_path, dpi=200, bbox_inches="tight")
plt.close(fig)
print(f"  Saved: {combined_path}")

# ===========================================================================
# 9. SUMMARY REPORT
# ===========================================================================
print(f"\n{'=' * 72}")
print("NOISE RESILIENCE SUMMARY")
print(f"{'=' * 72}")

# Find degradation thresholds
print(f"\n  Ideal baseline AUC: {ideal_auc:.4f}")
print(f"\n  Depolarizing noise:")
for key, v in depol_results.items():
    delta = v["roc_auc"] - ideal_auc
    print(f"    p={v['noise_level']:.4f}  AUC={v['roc_auc']:.4f}  "
          f"Δ={delta:+.4f}  ({100*delta/max(ideal_auc, 0.01):+.1f}%)")

print(f"\n  Amplitude damping:")
for key, v in ad_results.items():
    delta = v["roc_auc"] - ideal_auc
    print(f"    γ={v['noise_level']:.4f}  AUC={v['roc_auc']:.4f}  "
          f"Δ={delta:+.4f}  ({100*delta/max(ideal_auc, 0.01):+.1f}%)")

print(f"\n  Shot noise:")
for key, v in shot_results.items():
    delta = v["roc_auc"] - ideal_auc
    print(f"    shots={v['shots']:5d}  AUC={v['roc_auc']:.4f}  "
          f"Δ={delta:+.4f}  ({100*delta/max(ideal_auc, 0.01):+.1f}%)")

# Save plain-text report
report_path = os.path.join(NOISE_DIR, "noise_analysis_report.txt")
with open(report_path, "w", encoding="utf-8") as f:
    f.write("NISQ NOISE RESILIENCE ANALYSIS\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Ideal baseline AUC: {ideal_auc:.4f}\n\n")

    f.write("DEPOLARIZING NOISE\n")
    f.write("-" * 40 + "\n")
    for key, v in depol_results.items():
        delta = v["roc_auc"] - ideal_auc
        f.write(f"  p={v['noise_level']:.4f}  AUC={v['roc_auc']:.4f}  "
                f"F1={v['f1']:.4f}  MCC={v['mcc']:.4f}  Δ={delta:+.4f}\n")

    f.write("\nAMPLITUDE DAMPING\n")
    f.write("-" * 40 + "\n")
    for key, v in ad_results.items():
        delta = v["roc_auc"] - ideal_auc
        f.write(f"  γ={v['noise_level']:.4f}  AUC={v['roc_auc']:.4f}  "
                f"F1={v['f1']:.4f}  MCC={v['mcc']:.4f}  Δ={delta:+.4f}\n")

    f.write("\nSHOT NOISE\n")
    f.write("-" * 40 + "\n")
    for key, v in shot_results.items():
        delta = v["roc_auc"] - ideal_auc
        f.write(f"  shots={v['shots']:5d}  AUC={v['roc_auc']:.4f}  "
                f"F1={v['f1']:.4f}  MCC={v['mcc']:.4f}  Δ={delta:+.4f}\n")

print(f"\n  Report saved to: {report_path}")
print(f"\n{'=' * 72}")
print("NOISE ANALYSIS COMPLETE")
print(f"{'=' * 72}")

"""
src/pipeline/viz.py
===================
All output visualizations for the quantum mineral detection pipeline.

Creates PNG files in the output folder:
  1. probability_heatmap_<method>.png  — per-method prediction map
  2. rgb_mineral_overlay.png           — scene RGB + mineral detections
  3. anomaly_score_map.png             — Method F QAA anomaly scores
  4. roc_curves.png                    — all-methods ROC curves
  5. method_comparison_bar.png         — AUC / F1 / MCC bar chart

SCENE CONTEXT (why 2013 scenes look similar)
--------------------------------------------
Scene 2 (EO1H0410332013075, P41/R33, Mar-2013) and
Scene 3 (EO1H0410332013154, P41/R33, Jun-2013) cover exactly the
same geographic orbit path. Correlation ≈ 0.89 in reflectance.
The output maps will therefore look structurally similar — this is
correct geology, NOT a data or code error.

Scene 1 (EO1H0430342017071, P43/R34, Mar-2017) covers a different
path/row and shows distinct spatial patterns (corr ≈ 0.68 vs scene2).
"""

from __future__ import annotations

import os
import warnings
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")          # non-interactive backend — always works
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import LinearSegmentedColormap, Normalize
    _MPL = True
except ImportError:
    _MPL = False
    warnings.warn("matplotlib not available — visualization skipped.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_mpl(fn_name: str) -> bool:
    if not _MPL:
        warnings.warn(f"{fn_name}: matplotlib is not installed — skipped.")
        return False
    return True


def _prob_to_grid(
    probs: np.ndarray,
    coords: list,
    scene_h: int = 800,
    scene_w: int = 800,
    patch_size: int = 16,
    fill: float = np.nan,
) -> np.ndarray:
    """Map patch-level probabilities back to a 2D scene grid."""
    grid = np.full((scene_h // patch_size, scene_w // patch_size), fill)
    for k, (r, c) in enumerate(coords):
        gi = r // patch_size
        gj = c // patch_size
        if 0 <= gi < grid.shape[0] and 0 <= gj < grid.shape[1]:
            grid[gi, gj] = probs[k]
    return grid


def _scene_rgb(scene_cube: np.ndarray, r_band=29, g_band=20, b_band=10) -> np.ndarray | None:
    """
    Create an 8-bit RGB image from Hyperion scene.
    Default bands: ~660 nm (R), ~549 nm (G), ~447 nm (B).
    """
    if scene_cube is None or scene_cube.ndim != 3:
        return None
    H, W, B = scene_cube.shape
    r_b = min(r_band, B - 1)
    g_b = min(g_band, B - 1)
    b_b = min(b_band, B - 1)

    def stretch(band):
        lo, hi = np.nanpercentile(band, 2), np.nanpercentile(band, 98)
        if hi <= lo:
            return np.zeros_like(band, dtype=np.uint8)
        return np.clip((band - lo) / (hi - lo), 0, 1)

    rgb = np.stack([
        stretch(scene_cube[:, :, r_b]),
        stretch(scene_cube[:, :, g_b]),
        stretch(scene_cube[:, :, b_b]),
    ], axis=-1)
    return (rgb * 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# 1.  Probability heatmaps per method
# ---------------------------------------------------------------------------

def plot_probability_heatmaps(
    all_probs: dict,
    test_coords: list,
    test_labels: np.ndarray,
    output_folder: str,
    scene_h: int = 800,
    scene_w: int = 800,
    patch_size: int = 16,
    method_dirs: dict | None = None,
) -> None:
    """
    Save one heatmap PNG per method showing detection probability.

    Color scheme: blue (low) → yellow (high)
    Black circles = ground-truth positives

    When ``method_dirs`` is supplied each method's PNG is saved to its own
    subfolder (e.g. outputs/C_PCA_QAE/probability_heatmap.png) as well as
    to ``output_folder`` for backward compatibility.
    """
    if not _require_mpl("plot_probability_heatmaps"):
        return

    cmap = plt.cm.plasma

    for method, probs in all_probs.items():
        grid = _prob_to_grid(probs, test_coords, scene_h, scene_w, patch_size)

        fig, ax = plt.subplots(figsize=(7, 7), dpi=120)
        im = ax.imshow(grid, cmap=cmap, vmin=0, vmax=1,
                       interpolation="nearest", aspect="equal")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04,
                     label="Detection probability")

        # Overlay ground-truth positive positions
        pos_idx = np.where(test_labels == 1)[0]
        for idx in pos_idx:
            r, c = test_coords[idx]
            ax.add_patch(mpatches.Circle(
                (c // patch_size, r // patch_size), radius=0.4,
                color="lime", fill=False, linewidth=0.6, alpha=0.7))

        ax.set_title(
            f"Method {method} — Detection Probability Map\n"
            f"Green circles = ground-truth mineral patches  "
            f"({len(pos_idx)}/{len(test_labels)} pos)",
            fontsize=9)
        ax.set_xlabel("Patch column"); ax.set_ylabel("Patch row")

        fig.tight_layout()

        # Save to per-method subfolder (professional structure)
        if method_dirs and method in method_dirs:
            os.makedirs(method_dirs[method], exist_ok=True)
            method_fname = os.path.join(method_dirs[method],
                                        "probability_heatmap.png")
            fig.savefig(method_fname, bbox_inches="tight")
            print(f"  Saved: {method_fname}")

        # Also save to root output_folder (backward compat)
        fname = os.path.join(output_folder,
                             f"probability_heatmap_{method}.png")
        fig.savefig(fname, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 2.  RGB composite + mineral detection overlay
# ---------------------------------------------------------------------------

def plot_rgb_mineral_overlay(
    best_method_probs: np.ndarray,
    test_coords: list,
    test_labels: np.ndarray,
    output_folder: str,
    scene_cube: np.ndarray | None = None,
    threshold: float = 0.5,
    scene_h: int = 800,
    scene_w: int = 800,
    patch_size: int = 16,
    method_name: str = "C_PCA_QAE",
    scene_label: str = "Scene 3 (2013-Jun, P41/R33) — Test",
) -> None:
    """
    RGB scene image (or grey fallback) with detection overlay.

    Red fills        = predicted mineral (above threshold)
    Green borders    = true positives
    Yellow borders   = false positives
    Blue borders     = false negatives
    """
    if not _require_mpl("plot_rgb_mineral_overlay"):
        return

    preds = (best_method_probs >= threshold).astype(np.int32)

    fig, axes = plt.subplots(1, 2, figsize=(14, 7), dpi=120)

    # --- Left: RGB ---
    rgb = _scene_rgb(scene_cube) if scene_cube is not None else None
    if rgb is not None:
        axes[0].imshow(rgb, aspect="equal")
        axes[0].set_title(f"Hyperion RGB False-Colour\n{scene_label}", fontsize=9)
    else:
        # Fall-back: show detection probability grid in greyscale
        grid_bg = _prob_to_grid(
            best_method_probs, test_coords, scene_h, scene_w, patch_size, fill=0.5)
        axes[0].imshow(grid_bg, cmap="gray", aspect="equal", vmin=0, vmax=1)
        axes[0].set_title(f"Probability (grey — no cube loaded)\n{scene_label}",
                          fontsize=9)

    # Patch rectangles on RGB
    for k, (r, c) in enumerate(test_coords):
        pred_k  = int(preds[k])
        label_k = int(test_labels[k])

        if pred_k == 1:
            rect = mpatches.Rectangle(
                (c, r), patch_size, patch_size,
                linewidth=0, facecolor="red", alpha=0.35)
            axes[0].add_patch(rect)

        if pred_k == 1 and label_k == 1:
            color = "lime"
        elif pred_k == 1 and label_k == 0:
            color = "yellow"
        elif pred_k == 0 and label_k == 1:
            color = "dodgerblue"
        else:
            continue

        rect = mpatches.Rectangle(
            (c, r), patch_size, patch_size,
            linewidth=1.0, edgecolor=color, facecolor="none", alpha=0.9)
        axes[0].add_patch(rect)

    legend_els = [
        mpatches.Patch(facecolor="red",       alpha=0.4, label="Predicted mineral"),
        mpatches.Patch(edgecolor="lime",      facecolor="none", label="True positive"),
        mpatches.Patch(edgecolor="yellow",    facecolor="none", label="False positive"),
        mpatches.Patch(edgecolor="dodgerblue",facecolor="none", label="False negative"),
    ]
    axes[0].legend(handles=legend_els, loc="upper right", fontsize=7)
    axes[0].set_xlabel("Column (pixels)"); axes[0].set_ylabel("Row (pixels)")

    # --- Right: probability heatmap ---
    grid = _prob_to_grid(
        best_method_probs, test_coords, scene_h, scene_w, patch_size)
    im = axes[1].imshow(grid, cmap="hot", vmin=0, vmax=1,
                        interpolation="nearest", aspect="equal")
    plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04,
                 label="Detection probability")
    axes[1].set_title(f"Method {method_name} — Probability Map\n"
                      f"(threshold={threshold:.2f})", fontsize=9)
    axes[1].set_xlabel("Patch column"); axes[1].set_ylabel("Patch row")

    fig.suptitle(
        f"Quantum Mineral Detection Results — {method_name}\n"
        f"Why do 2013 scenes look similar? Scenes 2 & 3 share the same\n"
        f"orbit path (P41/R33) — same geology, different acquisition dates.",
        fontsize=8)

    fname = os.path.join(output_folder, "rgb_mineral_overlay.png")
    fig.tight_layout()
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 3.  Anomaly score map (Method F)
# ---------------------------------------------------------------------------

def plot_anomaly_score_map(
    anomaly_scores: np.ndarray,
    test_anomaly_scores: np.ndarray,
    test_coords: list,
    test_labels: np.ndarray,
    output_folder: str,
    scene_h: int = 800,
    scene_w: int = 800,
    patch_size: int = 16,
) -> None:
    """
    Two-panel figure:
      Left : Anomaly score heatmap over test scene
      Right: Score distribution (QAA background vs mineral)
    """
    if not _require_mpl("plot_anomaly_score_map"):
        return

    grid = _prob_to_grid(
        test_anomaly_scores, test_coords, scene_h, scene_w, patch_size,
        fill=0.0)

    fig, axes = plt.subplots(1, 2, figsize=(13, 6), dpi=120)

    # Heatmap
    lo = float(np.nanpercentile(grid[grid > 0], 2)) if (grid > 0).any() else 0.0
    hi = float(np.nanpercentile(grid[grid > 0], 98)) if (grid > 0).any() else 1.0
    im = axes[0].imshow(grid, cmap="YlOrRd", vmin=lo, vmax=hi,
                        interpolation="nearest", aspect="equal")
    plt.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04,
                 label="QAA anomaly score")
    axes[0].set_title(
        "Method F — Quantum Anomaly Score Map\n"
        "(high score = unusual spectrum = potential mineral)",
        fontsize=9)
    axes[0].set_xlabel("Patch column"); axes[0].set_ylabel("Patch row")

    # Ground-truth overlay
    pos_idx = np.where(test_labels == 1)[0]
    for idx in pos_idx:
        r, c = test_coords[idx]
        axes[0].add_patch(mpatches.Circle(
            (c // patch_size, r // patch_size), radius=0.45,
            color="cyan", fill=False, linewidth=0.8))

    # Score distribution
    pos_scores = test_anomaly_scores[test_labels == 1]
    neg_scores = test_anomaly_scores[test_labels == 0]
    bins = np.linspace(test_anomaly_scores.min(), test_anomaly_scores.max(), 40)
    axes[1].hist(neg_scores, bins=bins, alpha=0.65, label="Background",
                 color="steelblue", density=True)
    axes[1].hist(pos_scores, bins=bins, alpha=0.65, label="Mineral (GT)",
                 color="tomato", density=True)
    axes[1].set_xlabel("QAA anomaly score"); axes[1].set_ylabel("Density")
    axes[1].set_title("Score Distribution\n(QAA trained on background only)",
                      fontsize=9)
    axes[1].legend(fontsize=8)

    fig.suptitle(
        "Method F: Quantum Anomaly Autoencoder (QAA)\n"
        "Unsupervised — no mineral labels used during training",
        fontsize=9)

    fname = os.path.join(output_folder, "anomaly_score_map.png")
    fig.tight_layout()
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 4.  ROC curves
# ---------------------------------------------------------------------------

def plot_roc_curves(
    all_probs: dict,
    test_labels: np.ndarray,
    output_folder: str,
) -> None:
    """
    One ROC curve per method.  AUC annotated in legend.
    Reference diagonal (random) shown as dashed grey.
    """
    if not _require_mpl("plot_roc_curves"):
        return

    try:
        from sklearn.metrics import roc_curve, auc as _auc
    except ImportError:
        warnings.warn("scikit-learn required for ROC curves.")
        return

    # Color palette aligned to methods A–F
    palette = {
        "A_PCA"      : "#4e79a7",
        "B_PCA_CAE"  : "#f28e2b",
        "C_PCA_QAE"  : "#e15759",
        "D_QSVM"     : "#76b7b2",
        "E_VQC"      : "#59a14f",
        "F_QAA_Hybrid": "#b07aa1",
    }
    default_colors = plt.cm.tab10.colors

    fig, ax = plt.subplots(figsize=(7, 6), dpi=130)
    ax.plot([0, 1], [0, 1], "k--", linewidth=0.8, alpha=0.5, label="Random (AUC=0.50)")

    for i, (method, probs) in enumerate(all_probs.items()):
        fpr, tpr, _ = roc_curve(test_labels, probs)
        roc_auc = _auc(fpr, tpr)
        color = palette.get(method, default_colors[i % len(default_colors)])
        lw = 2.5 if method == "C_PCA_QAE" else 1.5
        ax.plot(fpr, tpr, color=color, linewidth=lw,
                label=f"{method}  (AUC={roc_auc:.4f})")

    ax.set_xlabel("False Positive Rate", fontsize=11)
    ax.set_ylabel("True Positive Rate", fontsize=11)
    ax.set_title(
        "ROC Curves — Quantum Mineral Detection\n"
        "Test set: Scene 3 (2013-Jun, P41/R33)", fontsize=10)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1]); ax.set_ylim([0, 1.02])

    fname = os.path.join(output_folder, "roc_curves.png")
    fig.tight_layout()
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 5.  Method comparison bar chart
# ---------------------------------------------------------------------------

def plot_method_comparison(
    all_results: list,
    output_folder: str,
) -> None:
    """
    Grouped bar chart: AUC / F1 / MCC for every method.

    Highlights:
      - C_PCA_QAE  (proposed, main contribution)
      - F_QAA_Hybrid (new Method F)
    in a deeper colour.  95% CI bars shown for AUC if available.
    """
    if not _require_mpl("plot_method_comparison"):
        return

    methods = [r["label"] for r in all_results]
    aucs    = [r.get("roc_auc", r.get("auc", 0.0)) for r in all_results]
    f1s     = [r.get("f1",   0.0) for r in all_results]
    mccs    = [r.get("mcc",  0.0) for r in all_results]

    auc_ci_lo = []
    auc_ci_hi = []
    for i, r in enumerate(all_results):
        ci = r.get("auc_ci", None)
        if ci is not None:
            auc_ci_lo.append(max(0.0, aucs[i] - ci[0]))
            auc_ci_hi.append(max(0.0, ci[1] - aucs[i]))
        else:
            auc_ci_lo.append(0.0)
            auc_ci_hi.append(0.0)

    n_methods = len(methods)
    x = np.arange(n_methods)
    width = 0.25

    highlight = {"C_PCA_QAE", "F_QAA_Hybrid"}

    def _alpha(m):
        return 1.0 if m in highlight else 0.7

    fig, ax = plt.subplots(figsize=(max(8, n_methods * 1.4), 6), dpi=130)

    bars_auc = ax.bar(x - width,      aucs, width, label="AUC",
                      color=["#e15759" if m in highlight else "#4e79a7"
                             for m in methods],
                      alpha=0.85,
                      yerr=[auc_ci_lo, auc_ci_hi],
                      capsize=3, error_kw={"elinewidth": 1})

    bars_f1  = ax.bar(x,               f1s, width, label="F1",
                      color=["#d37295" if m in highlight else "#59a14f"
                             for m in methods],
                      alpha=0.85)

    bars_mcc = ax.bar(x + width,       mccs, width, label="MCC",
                      color=["#b07aa1" if m in highlight else "#76b7b2"
                             for m in methods],
                      alpha=0.85)

    # Value labels
    for bars in (bars_auc, bars_f1, bars_mcc):
        for bar in bars:
            h = bar.get_height()
            if abs(h) > 0.01:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.01,
                        f"{h:.3f}", ha="center", va="bottom", fontsize=6,
                        rotation=45)

    ax.axhline(0.5, color="grey", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(methods, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title(
        "Method Comparison — Quantum Mineral Detection\n"
        "Red/purple = main contributions (C: QAE, F: QAA Hybrid)",
        fontsize=10)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(axis="y", alpha=0.3)

    fname = os.path.join(output_folder, "method_comparison_bar.png")
    fig.tight_layout()
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 6.  Summary figure  (all 5 probability maps in one grid)
# ---------------------------------------------------------------------------

def plot_all_maps_grid(
    all_probs: dict,
    test_coords: list,
    test_labels: np.ndarray,
    output_folder: str,
    scene_h: int = 800,
    scene_w: int = 800,
    patch_size: int = 16,
) -> None:
    """
    Single figure with one sub-panel per method — easy publication comparison.
    """
    if not _require_mpl("plot_all_maps_grid"):
        return

    n = len(all_probs)
    ncols = min(3, n)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols,
                              figsize=(ncols * 5, nrows * 4.5), dpi=120)
    axes_flat = np.array(axes).flatten() if n > 1 else [axes]

    for ax, (method, probs) in zip(axes_flat, all_probs.items()):
        grid = _prob_to_grid(probs, test_coords, scene_h, scene_w, patch_size)
        im = ax.imshow(grid, cmap="hot", vmin=0, vmax=1,
                       interpolation="nearest", aspect="equal")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title(method, fontsize=9)
        # Ground-truth dots
        pos_idx = np.where(test_labels == 1)[0]
        for idx in pos_idx:
            r, c = test_coords[idx]
            ax.plot(c // patch_size, r // patch_size, "c.", markersize=2, alpha=0.6)

    # Hide unused axes
    for ax in axes_flat[n:]:
        ax.set_visible(False)

    fig.suptitle(
        "All Methods — Detection Probability Maps  (Test Scene 3)\n"
        "Cyan dots = ground-truth mineral patches",
        fontsize=10)
    fname = os.path.join(output_folder, "all_maps_grid.png")
    fig.tight_layout()
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 7.  Training loss curves  (convergence diagnostic)
# ---------------------------------------------------------------------------

def plot_training_loss_curves(
    cae_history:  dict,
    qae_history:  dict,
    qaa_history:  dict,
    output_folder: str,
    vqc_history:  dict | None = None,
) -> None:
    """
    Plot CAE, QAE, QAA and (optionally) VQC training / validation loss.

    When vqc_history is provided a 2×2 grid is used; otherwise 1×3.
    """
    if not _require_mpl("plot_training_loss_curves"):
        return

    n_plots = 4 if vqc_history else 3
    if n_plots == 4:
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        axes = axes.flatten()
    else:
        fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    # --- CAE ---
    ax = axes[0]
    if cae_history.get("train"):
        ax.plot(cae_history["train"], label="train", color="steelblue")
    if cae_history.get("val"):
        ax.plot(cae_history["val"],   label="val",   color="orange", linestyle="--")
    ax.set_title("Classical AE (Method B)\nLoss vs Epoch")
    ax.set_xlabel("Epoch"); ax.set_ylabel("Weighted MSE")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    # --- QAE ---
    ax = axes[1]
    if qae_history.get("train"):
        ax.plot(qae_history["train"], label="train", color="steelblue")
    if qae_history.get("val"):
        ax.plot(qae_history["val"],   label="val",   color="orange", linestyle="--")
    ax.set_title("Quantum AE (Methods C / C2 / C3)\nLoss vs Epoch")
    ax.set_xlabel("Epoch"); ax.set_ylabel("Weighted MSE")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    # --- QAA ---
    ax = axes[2]
    if qaa_history.get("bg_loss"):
        ax.plot(qaa_history["bg_loss"], label="bg_loss", color="forestgreen")
    ax.set_title("Quantum Anomaly AE (Method F)\nBackground Loss vs Epoch")
    ax.set_xlabel("Epoch"); ax.set_ylabel("Reconstruction MSE")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    # --- VQC (C3) — optional ---
    if vqc_history and n_plots == 4:
        ax = axes[3]
        if vqc_history.get("train"):
            ax.plot(vqc_history["train"], label="train", color="steelblue")
        if vqc_history.get("val"):
            ax.plot(vqc_history["val"],   label="val",   color="orange",
                    linestyle="--")
        ax.set_title("VQC on QAE Features (Method C3)\nLoss vs Epoch")
        ax.set_xlabel("Epoch"); ax.set_ylabel("Weighted BCE")
        ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    fig.suptitle("Training Convergence Curves", fontsize=12, fontweight="bold")
    fname = os.path.join(output_folder, "training_loss_curves.png")
    fig.tight_layout()
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 8.  Confusion matrices  (train and test)
# ---------------------------------------------------------------------------

def plot_confusion_matrices(
    test_preds:  dict,
    test_labels: np.ndarray,
    output_folder: str,
    train_preds:  dict | None = None,
    train_labels: np.ndarray | None = None,
) -> None:
    """Plot normalised confusion matrices for every method, for test (and optionally train)."""
    if not _require_mpl("plot_confusion_matrices"):
        return
    from sklearn.metrics import confusion_matrix

    method_names = list(test_preds.keys())
    n = len(method_names)

    for split, preds_dict, labels in [
        ("test",  test_preds,              test_labels),
        ("train", train_preds or {},       train_labels if train_labels is not None else test_labels),
    ]:
        if not preds_dict:
            continue

        ncols = min(n, 4)
        nrows = int(np.ceil(n / ncols))
        fig, axes = plt.subplots(nrows, ncols,
                                  figsize=(3.5 * ncols, 3.2 * nrows),
                                  squeeze=False)
        axes_flat = axes.flatten()

        for i, name in enumerate(method_names):
            if name not in preds_dict:
                axes_flat[i].set_visible(False)
                continue
            ax = axes_flat[i]
            # Handle subset labels for QSVM (shorter array for train)
            prd = preds_dict[name]
            lbl = labels[:len(prd)]
            cm = confusion_matrix(lbl, prd)
            cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)
            im = ax.imshow(cm_norm, cmap="Blues", vmin=0, vmax=1)
            for ri in range(2):
                for ci in range(2):
                    ax.text(ci, ri, f"{cm[ri, ci]}\n({cm_norm[ri, ci]:.2f})",
                            ha="center", va="center", fontsize=9,
                            color="white" if cm_norm[ri, ci] > 0.5 else "black")
            ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
            ax.set_xticklabels(["Pred 0", "Pred 1"], fontsize=8)
            ax.set_yticklabels(["True 0", "True 1"], fontsize=8)
            ax.set_title(name, fontsize=9, fontweight="bold")
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        for ax in axes_flat[len(method_names):]:
            ax.set_visible(False)

        fig.suptitle(f"Confusion Matrices — {split.upper()} Set\n"
                     "(row = true class, col = predicted class)",
                     fontsize=11, fontweight="bold")
        fname = os.path.join(output_folder, f"confusion_matrices_{split}.png")
        fig.tight_layout()
        fig.savefig(fname, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 9.  Precision-Recall curves
# ---------------------------------------------------------------------------

def plot_pr_curves(
    all_probs:    dict,
    test_labels:  np.ndarray,
    output_folder: str,
) -> None:
    """Precision-Recall curves for all methods (better than ROC for imbalanced data)."""
    if not _require_mpl("plot_pr_curves"):
        return
    from sklearn.metrics import precision_recall_curve, auc as sk_auc

    _COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    fig, ax = plt.subplots(figsize=(7, 6))
    baseline = test_labels.mean()
    ax.axhline(y=baseline, color="grey", linestyle=":", linewidth=1.2,
               label=f"Random (prevalence={baseline:.3f})")

    for i, (name, probs) in enumerate(all_probs.items()):
        lbl = test_labels[:len(probs)]
        prec, rec, _ = precision_recall_curve(lbl, probs)
        pr_auc = sk_auc(rec, prec)
        color = _COLORS[i % len(_COLORS)]
        ax.plot(rec, prec, color=color, linewidth=1.8,
                label=f"{name}  (PR-AUC={pr_auc:.4f})")

    ax.set_xlabel("Recall",    fontsize=11)
    ax.set_ylabel("Precision", fontsize=11)
    ax.set_title("Precision-Recall Curves — Test Set\n"
                 "(higher curves → better detection at any recall threshold)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1]); ax.set_ylim([0, 1])

    fname = os.path.join(output_folder, "pr_curves.png")
    fig.tight_layout()
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 10.  Cross-validation fold box-plot
# ---------------------------------------------------------------------------

def plot_cv_boxplot(
    cv_results:    dict,
    output_folder: str,
) -> None:
    """Box-plots of AUC and F1 distributions across CV folds per method."""
    if not _require_mpl("plot_cv_boxplot"):
        return

    methods = [m for m, r in cv_results.items() if r.get("auc")]
    if not methods:
        warnings.warn("plot_cv_boxplot: no CV results to plot.")
        return

    auc_data = [cv_results[m]["auc"] for m in methods]
    f1_data  = [cv_results[m]["f1"]  for m in methods]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

    bp1 = ax1.boxplot(auc_data, patch_artist=True, notch=False,
                      medianprops=dict(color="black", linewidth=2))
    ax1.set_xticklabels(methods, rotation=15, ha="right", fontsize=9)
    ax1.set_title("CV AUC per Method", fontsize=11, fontweight="bold")
    ax1.set_ylabel("ROC-AUC"); ax1.grid(True, axis="y", alpha=0.3)
    ax1.axhline(0.5, color="grey", linestyle=":", linewidth=1)

    bp2 = ax2.boxplot(f1_data, patch_artist=True, notch=False,
                      medianprops=dict(color="black", linewidth=2))
    ax2.set_xticklabels(methods, rotation=15, ha="right", fontsize=9)
    ax2.set_title("CV F1 per Method", fontsize=11, fontweight="bold")
    ax2.set_ylabel("F1 Score"); ax2.grid(True, axis="y", alpha=0.3)

    _COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for patch, color in zip(bp1["boxes"], _COLORS[:len(methods)]):
        patch.set_facecolor(color); patch.set_alpha(0.7)
    for patch, color in zip(bp2["boxes"], _COLORS[:len(methods)]):
        patch.set_facecolor(color); patch.set_alpha(0.7)

    fig.suptitle(f"Spatially Blocked CV ({len(auc_data[0])} folds)\n"
                 "Train-side performance distribution",
                 fontsize=11, fontweight="bold")
    fname = os.path.join(output_folder, "cv_fold_boxplot.png")
    fig.tight_layout()
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 11.  Train vs Test generalization gap
# ---------------------------------------------------------------------------

def plot_train_test_comparison(
    cv_results:    dict,
    all_results:   list,
    output_folder: str,
) -> None:
    """Side-by-side bar chart: CV-mean AUC (train) vs test AUC per method."""
    if not _require_mpl("plot_train_test_comparison"):
        return

    test_auc_map = {m["label"]: m.get("roc_auc", m.get("auc", 0.0)) for m in all_results}
    methods = [m for m in cv_results if cv_results[m].get("auc")]
    if not methods:
        return

    cv_mean  = [np.mean(cv_results[m]["auc"]) for m in methods]
    cv_std   = [np.std(cv_results[m]["auc"])  for m in methods]
    test_auc = [test_auc_map.get(m, 0.0)      for m in methods]

    x = np.arange(len(methods))
    w = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))
    bars1 = ax.bar(x - w/2, cv_mean, w, yerr=cv_std, capsize=4,
                   color="#1f77b4", alpha=0.8, label="CV AUC (train, mean±std)")
    bars2 = ax.bar(x + w/2, test_auc, w,
                   color="#ff7f0e", alpha=0.8, label="Test AUC (held-out)")

    ax.set_xticks(x)
    ax.set_xticklabels(methods, rotation=15, ha="right", fontsize=9)
    ax.set_ylabel("ROC-AUC")
    ax.set_ylim(0, 1.05)
    ax.axhline(0.5, color="grey", linestyle=":", linewidth=1, label="Random")
    ax.set_title("Generalization Gap: CV Train AUC vs Held-Out Test AUC\n"
                 "(small gap → model generalises well)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)

    for bar in bars1:
        ax.annotate(f"{bar.get_height():.3f}",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7)
    for bar in bars2:
        ax.annotate(f"{bar.get_height():.3f}",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7)

    fname = os.path.join(output_folder, "train_test_generalization.png")
    fig.tight_layout()
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 12.  QSVM quantum kernel matrix heatmap
# ---------------------------------------------------------------------------

def plot_qsvm_kernel_heatmap(
    K_tr:          np.ndarray,
    qsvm_idx:      np.ndarray,
    train_labels:  np.ndarray,
    output_folder: str,
) -> None:
    """Heatmap of the ZZFeatureMap kernel matrix, sorted by label."""
    if not _require_mpl("plot_qsvm_kernel_heatmap"):
        return

    sub_labels = train_labels[qsvm_idx]
    sort_order = np.argsort(sub_labels)
    K_sorted   = K_tr[np.ix_(sort_order, sort_order)]
    y_sorted   = sub_labels[sort_order]
    n_neg = int((y_sorted == 0).sum())

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(K_sorted, cmap="viridis", aspect="auto",
                   interpolation="nearest")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04,
                 label="Fidelity |⟨φ(x₁)|φ(x₂)⟩|²")

    ax.axhline(n_neg - 0.5, color="red",  linewidth=1.5, linestyle="--")
    ax.axvline(n_neg - 0.5, color="red",  linewidth=1.5, linestyle="--")
    ax.set_title("ZZFeatureMap Quantum Kernel Matrix (sorted by label)\n"
                 "Red line = class boundary  |  top-left = background  |  bottom-right = mineral",
                 fontsize=9, fontweight="bold")
    ax.set_xlabel(f"Sample index (n={len(qsvm_idx)})")
    ax.set_ylabel(f"Sample index (n={len(qsvm_idx)})")

    import matplotlib.patches as mpatches
    handles = [
        mpatches.Patch(color="white", label=f"Background: {n_neg}"),
        mpatches.Patch(color="red",   label=f"Mineral: {len(qsvm_idx)-n_neg}"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8)

    fname = os.path.join(output_folder, "qsvm_kernel_matrix.png")
    fig.tight_layout()
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 13.  t-SNE feature visualisation  (train + test, 3 feature spaces)
# ---------------------------------------------------------------------------

def plot_feature_tsne(
    Z_tr_pca:   np.ndarray,
    qae_tr:     np.ndarray,
    cae_tr:     np.ndarray,
    train_labels: np.ndarray,
    Z_ts_pca:   np.ndarray,
    qae_ts:     np.ndarray,
    cae_ts:     np.ndarray,
    test_labels:  np.ndarray,
    output_folder: str,
    max_samples: int = 800,
) -> None:
    """3-panel t-SNE: PCA-only, PCA+CAE, PCA+QAE features for train+test."""
    if not _require_mpl("plot_feature_tsne"):
        return
    try:
        from sklearn.manifold import TSNE
    except ImportError:
        warnings.warn("plot_feature_tsne: sklearn not available — skipped.")
        return

    rng = np.random.default_rng(42)

    def _subsample(X_tr, X_ts, y_tr, y_ts, n):
        n_tr = min(n * 2 // 3, len(X_tr))
        n_ts = min(n - n_tr, len(X_ts))
        idx_tr = rng.choice(len(X_tr), n_tr, replace=False)
        idx_ts = rng.choice(len(X_ts), n_ts, replace=False)
        X = np.vstack([X_tr[idx_tr], X_ts[idx_ts]])
        y = np.concatenate([y_tr[idx_tr], y_ts[idx_ts]])
        split = np.array(["train"] * n_tr + ["test"] * n_ts)
        return X, y, split

    panels = [
        ("PCA only",         Z_tr_pca,                                 Z_ts_pca),
        ("PCA + CAE (B)",    np.hstack([Z_tr_pca, cae_tr]),            np.hstack([Z_ts_pca, cae_ts])),
        ("PCA + QAE (C)",    np.hstack([Z_tr_pca, qae_tr]),            np.hstack([Z_ts_pca, qae_ts])),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    _clr = {(1, "train"): "#d62728", (1, "test"): "#ff9896",
            (0, "train"): "#1f77b4", (0, "test"): "#aec7e8"}
    _MKRS = {"train": "o", "test": "*"}

    for ax, (title, X_tr_f, X_ts_f) in zip(axes, panels):
        X, y, split = _subsample(X_tr_f, X_ts_f, train_labels, test_labels, max_samples)
        # Drop NaN/Inf
        finite = np.all(np.isfinite(X), axis=1)
        X, y, split = X[finite], y[finite], split[finite]
        if len(X) < 10:
            ax.set_title(f"{title}\n(insufficient data)")
            continue
        # sklearn >=1.5 renamed `n_iter` to `max_iter`; support both.
        try:
            tsne = TSNE(n_components=2, perplexity=min(30, len(X) - 1),
                        random_state=42, max_iter=300, init="pca")
        except TypeError:
            tsne = TSNE(n_components=2, perplexity=min(30, len(X) - 1),
                        random_state=42, n_iter=300, init="pca")
        emb = tsne.fit_transform(X.astype(np.float32))

        for lbl_val in [0, 1]:
            for spl in ["train", "test"]:
                mask = (y == lbl_val) & (split == spl)
                if not mask.any():
                    continue
                ax.scatter(emb[mask, 0], emb[mask, 1],
                           c=_clr[(lbl_val, spl)],
                           marker=_MKRS[spl],
                           s=18 if spl == "train" else 30,
                           alpha=0.7, linewidths=0,
                           label=f"{'mineral' if lbl_val else 'bg'}-{spl}")

        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.set_xticks([]); ax.set_yticks([])

    handles, labels_ = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels_, loc="lower center", ncol=4, fontsize=8,
               bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("t-SNE Feature Space Visualisation\n"
                 "(circles=train, stars=test; red=mineral, blue=background)",
                 fontsize=11, fontweight="bold")
    fname = os.path.join(output_folder, "feature_tsne.png")
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 14.  Label distribution and band-ratio index histograms
# ---------------------------------------------------------------------------

def plot_label_distribution(
    train_li: np.ndarray,
    train_v:  np.ndarray,
    train_labels: np.ndarray,
    test_li:  np.ndarray,
    test_v:   np.ndarray,
    test_labels: np.ndarray,
    output_folder: str,
) -> None:
    """Histograms of LiCI and VMI indices split by class for train and test."""
    if not _require_mpl("plot_label_distribution"):
        return

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    specs = [
        (axes[0, 0], train_li, train_labels, "LiCI — Train"),
        (axes[0, 1], train_v,  train_labels, "VMI  — Train"),
        (axes[1, 0], test_li,  test_labels,  "LiCI — Test"),
        (axes[1, 1], test_v,   test_labels,  "VMI  — Test"),
    ]
    for ax, idx_arr, lbl_arr, title in specs:
        for cls, color, name in [(0, "#1f77b4", "background"),
                                  (1, "#d62728", "mineral")]:
            mask = lbl_arr == cls
            if mask.sum() > 0:
                ax.hist(idx_arr[mask], bins=40, alpha=0.55,
                        color=color, label=f"{name} (n={mask.sum()})",
                        density=True, edgecolor="none")
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.set_xlabel("Index value")
        ax.set_ylabel("Density")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    n_tr_pos = int(train_labels.sum())
    n_ts_pos = int(test_labels.sum())
    fig.suptitle(
        f"Mineral Index Distributions by Class\n"
        f"Train: {n_tr_pos} mineral / {len(train_labels)-n_tr_pos} bg  |  "
        f"Test: {n_ts_pos} mineral / {len(test_labels)-n_ts_pos} bg",
        fontsize=11, fontweight="bold")
    fname = os.path.join(output_folder, "label_distribution.png")
    fig.tight_layout()
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")


# ---------------------------------------------------------------------------
# 15.  LaTeX / CSV metrics summary table
# ---------------------------------------------------------------------------

def save_latex_metrics_table(
    all_results:      list,
    mcnemar_results:  list,
    output_folder:    str,
) -> None:
    """Write publication-ready LaTeX and CSV tables of all metrics."""
    # Build McNemar p-value lookup
    mcn_p = {}
    for (na, nb, chi2, pv) in mcnemar_results:
        mcn_p[(na, nb)] = pv
        mcn_p[(nb, na)] = pv

    rows = []
    for m in all_results:
        lbl   = m["label"]
        auc   = m.get("roc_auc", m.get("auc", 0.0))
        f1    = m["f1"]
        mcc   = m["mcc"]
        prec  = m.get("precision", float("nan"))
        rec   = m.get("recall",    float("nan"))
        ci    = m.get("auc_ci", (float("nan"), float("nan")))
        rows.append((lbl, auc, f1, mcc, prec, rec, ci))

    # --- LaTeX ---
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Mineral Detection Performance Comparison (Test Set)}",
        r"\label{tab:results}",
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"Method & AUC (95\% CI) & F1 & MCC & Precision & Recall & McNemar$^*$ \\",
        r"\midrule",
    ]
    for (lbl, auc, f1, mcc, prec, rec, ci) in rows:
        vs_c = mcn_p.get((lbl, "C_PCA_QAE"), float("nan"))
        sig  = r"$p$=" + (f"{vs_c:.3f}" if np.isfinite(vs_c) else "--")
        ci0  = ci[0] if np.isfinite(ci[0]) else float("nan")
        ci1  = ci[1] if np.isfinite(ci[1]) else float("nan")
        ci_str = f"[{ci0:.3f}, {ci1:.3f}]" if np.isfinite(ci0) else "--"
        line = (f"{lbl} & {auc:.4f} {ci_str} & {f1:.4f} & {mcc:.4f} & "
                f"{prec:.4f} & {rec:.4f} & {sig} \\\\")
        lines.append(line)
    lines += [
        r"\bottomrule",
        r"\multicolumn{7}{l}{\footnotesize $^*$McNemar vs C\_PCA\_QAE; bold = $p < 0.05$}\\",
        r"\end{tabular}",
        r"\end{table}",
    ]
    latex_path = os.path.join(output_folder, "metrics_latex_table.tex")
    with open(latex_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  Saved: {latex_path}")

    # --- CSV ---
    import csv
    csv_path = os.path.join(output_folder, "metrics_table.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Method", "AUC", "AUC_CI_lo", "AUC_CI_hi",
                          "F1", "MCC", "Precision", "Recall",
                          "McNemar_vs_C_p"])
        for (lbl, auc, f1, mcc, prec, rec, ci) in rows:
            vs_c = mcn_p.get((lbl, "C_PCA_QAE"), "")
            writer.writerow([lbl, f"{auc:.6f}",
                             f"{ci[0]:.6f}", f"{ci[1]:.6f}",
                             f"{f1:.6f}", f"{mcc:.6f}",
                             f"{prec:.6f}", f"{rec:.6f}",
                             f"{vs_c:.6f}" if isinstance(vs_c, float) else ""])
    print(f"  Saved: {csv_path}")

"""
src/pipeline/maps.py
====================
Save mineral probability / anomaly maps and uncertainty maps.
"""

from __future__ import annotations

import os
import numpy as np


def save_maps(probs_dict:    dict,
              test_labels:   np.ndarray,
              output_folder: str,
              test_coords:   list | None = None,
              method_dirs:   dict | None = None) -> None:
    """
    Save per-method probability maps as .npy files.

    Parameters
    ----------
    probs_dict    : {method_name: probs_array}  class-1 probabilities
    test_labels   : (N,) ground-truth labels
    output_folder : root outputs/ directory (shared files go here)
    test_coords   : list of (row, col) tuples (optional — used for spatial viz)
    method_dirs   : {method_name: folder_path}  per-method subdirectories.
                    When provided, each method's prob_map.npy is saved into
                    its own subfolder (professional structure).
    """
    os.makedirs(output_folder, exist_ok=True)

    # Individual method probability maps — saved to per-method subfolder when
    # available, and also to root for backward compatibility.
    for name, probs in probs_dict.items():
        # Per-method dir (professional)
        if method_dirs and name in method_dirs:
            os.makedirs(method_dirs[name], exist_ok=True)
            np.save(os.path.join(method_dirs[name], "prob_map.npy"), probs)
            print(f"  Saved: {method_dirs[name]}/prob_map.npy")
        # Root level (backward compat)
        path = os.path.join(output_folder, f"{name}_prob_map.npy")
        np.save(path, probs)

    # Anomaly map: mean probability across all ensemble methods
    ensemble_methods = [v for k, v in probs_dict.items()
                        if k in ("A_PCA", "B_PCA_CAE", "C_PCA_QAE")]
    if ensemble_methods:
        anomaly = np.mean(np.stack(ensemble_methods, axis=0), axis=0)
        np.save(os.path.join(output_folder, "anomaly_map.npy"), anomaly)

    # Uncertainty map: std of ensemble probabilities
    if len(ensemble_methods) > 1:
        uncertainty = np.std(np.stack(ensemble_methods, axis=0), axis=0)
        np.save(os.path.join(output_folder, "uncertainty_map.npy"), uncertainty)

    # Ground-truth label map
    np.save(os.path.join(output_folder, "test_labels.npy"), test_labels)

    # Patch coordinates (row, col) for spatial reconstruction
    if test_coords is not None:
        np.save(os.path.join(output_folder, "test_coords.npy"),
                np.array(test_coords, dtype=np.int32))

    print(f"  Maps saved to {output_folder}")


def save_metrics_txt(results: list,
                     mcnemar_results: list,
                     output_folder: str,
                     train_pos_pct: float) -> str:
    """
    Write all metrics to a human-readable text file.

    Parameters
    ----------
    results         : list of metric dicts (from compute_metrics)
    mcnemar_results : list of (name_a, name_b, chi2, p) tuples
    output_folder   : str
    train_pos_pct   : float  percentage of positive labels in training set

    Returns
    -------
    Path to the saved metrics file.
    """
    os.makedirs(output_folder, exist_ok=True)
    path = os.path.join(output_folder, "metrics.txt")
    lines = []
    lines.append("=" * 72)
    lines.append("QUANTUM MINERAL DETECTION — FINAL RESULTS")
    lines.append("=" * 72)
    lines.append(f"Train positives: {train_pos_pct:.1f}%")
    lines.append("")

    for m in results:
        lbl = m.get("label", "")
        auc = m["roc_auc"]
        ci  = m.get("auc_ci", (None, None))
        ci_str = (f"[{ci[0]:.4f}, {ci[1]:.4f}]"
                  if ci[0] is not None else "N/A")
        lines.append(f"{lbl}")
        lines.append(f"  AUC     = {auc:.4f}  95%CI = {ci_str}")
        lines.append(f"  F1      = {m['f1']:.4f}")
        lines.append(f"  MCC     = {m['mcc']:.4f}")
        lines.append(f"  kappa   = {m['kappa']:.4f}")
        lines.append(f"  bal_acc = {m['bal_acc']:.4f}")
        lines.append(f"  PR-AUC  = {m['pr_auc']:.4f}")
        lines.append(f"  Brier   = {m['brier']:.4f}")
        tn, fp, fn, tp_ = m["tn"], m["fp"], m["fn"], m["tp"]
        lines.append(f"  CM: TN={tn}  FP={fp}  FN={fn}  TP={tp_}")
        lines.append("")

    if mcnemar_results:
        lines.append("-" * 50)
        lines.append("McNemar Statistical Tests")
        lines.append("-" * 50)
        for (na, nb, chi2v, pv) in mcnemar_results:
            sig = "SIGNIFICANT" if pv < 0.05 else "not significant"
            lines.append(f"  {na} vs {nb}:  chi2={chi2v:.2f}  p={pv:.4f}  {sig}")
        lines.append("")

    text = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    return path

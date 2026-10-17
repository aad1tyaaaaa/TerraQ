"""
src/pipeline/metrics.py
=======================
Evaluation utilities: metrics, bootstrap AUC CI, McNemar test.

All functions are pure Python / NumPy / sklearn — no quantum dependencies.
"""

import numpy as np
from scipy.stats import chi2
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, f1_score,
    roc_auc_score, average_precision_score, brier_score_loss,
    cohen_kappa_score, matthews_corrcoef, confusion_matrix,
)


# ---------------------------------------------------------------------------
# Full metric dictionary
# ---------------------------------------------------------------------------

def compute_metrics(y_true:  np.ndarray,
                    y_pred:  np.ndarray,
                    y_prob:  np.ndarray,
                    label:   str = "") -> dict:
    """
    Return a dict of all evaluation metrics for one classifier.

    Parameters
    ----------
    y_true : (N,) int   ground-truth binary labels
    y_pred : (N,) int   predicted binary labels (threshold = 0.5)
    y_prob : (N,) float class-1 probabilities
    label  : str        human-readable method name

    Returns
    -------
    dict with keys: label, acc, bal_acc, f1, roc_auc, pr_auc,
                    brier, kappa, mcc, cm, tp, fp, fn, tn
    """
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    m = {
        "label"   : label,
        "acc"     : float(accuracy_score(y_true, y_pred)),
        "bal_acc" : float(balanced_accuracy_score(y_true, y_pred)),
        "f1"      : float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc" : float(roc_auc_score(y_true, y_prob)),
        "pr_auc"  : float(average_precision_score(y_true, y_prob)),
        "brier"   : float(brier_score_loss(y_true, y_prob)),
        "kappa"   : float(cohen_kappa_score(y_true, y_pred)),
        "mcc"     : float(matthews_corrcoef(y_true, y_pred)),
        "cm"      : confusion_matrix(y_true, y_pred).tolist(),
        "tp"      : int(tp),
        "fp"      : int(fp),
        "fn"      : int(fn),
        "tn"      : int(tn),
    }
    return m


# ---------------------------------------------------------------------------
# Bootstrap AUC 95% CI
# ---------------------------------------------------------------------------

def bootstrap_auc_ci(y_true: np.ndarray,
                     y_prob: np.ndarray,
                     n:      int   = 1000,
                     ci:     float = 0.95,
                     seed:   int   = 42) -> tuple:
    """
    Compute bootstrap 95% confidence interval for AUC.

    Returns
    -------
    (lo, hi)  — lower and upper bounds of the CI
    """
    rng  = np.random.default_rng(seed)
    aucs = []
    for _ in range(n):
        idx = rng.integers(0, len(y_true), len(y_true))
        yt, yp = y_true[idx], y_prob[idx]
        if len(np.unique(yt)) < 2:
            continue
        aucs.append(float(roc_auc_score(yt, yp)))
    if len(aucs) == 0:
        return 0.5, 0.5
    alpha = 1.0 - ci
    lo = float(np.percentile(aucs, alpha / 2 * 100))
    hi = float(np.percentile(aucs, (1 - alpha / 2) * 100))
    return lo, hi


# ---------------------------------------------------------------------------
# McNemar's test  (quantum advantage significance)
# ---------------------------------------------------------------------------

def mcnemar_test(y_true: np.ndarray,
                 pred_a: np.ndarray,
                 pred_b: np.ndarray) -> tuple:
    """
    McNemar's test with continuity correction (Edwards 1948).

    Tests H0: classifiers A and B have equal error rates.

    Parameters
    ----------
    y_true : (N,) ground-truth labels
    pred_a : (N,) predictions from classifier A
    pred_b : (N,) predictions from classifier B

    Returns
    -------
    (chi2_statistic, p_value)
    """
    b = int(np.sum((pred_a == y_true) & (pred_b != y_true)))  # A right, B wrong
    c = int(np.sum((pred_a != y_true) & (pred_b == y_true)))  # A wrong, B right
    if b + c == 0:
        return 0.0, 1.0
    chi2_stat = (abs(b - c) - 1.0) ** 2 / (b + c)
    p_val     = float(1.0 - chi2.cdf(chi2_stat, df=1))
    return float(chi2_stat), p_val


# ---------------------------------------------------------------------------
# Pretty-print helper
# ---------------------------------------------------------------------------

def print_metrics(m: dict) -> None:
    """Print a formatted summary of one metric dict."""
    lbl = m.get("label", "")
    print(f"  {lbl:<12}  AUC={m['roc_auc']:.4f}  F1={m['f1']:.4f}"
          f"  MCC={m['mcc']:.4f}  kappa={m['kappa']:.4f}")
    print(f"             bal_acc={m['bal_acc']:.4f}  PR={m['pr_auc']:.4f}"
          f"  Brier={m['brier']:.4f}")
    tn, fp, fn, tp = m["tn"], m["fp"], m["fn"], m["tp"]
    print(f"             CM: TN={tn}  FP={fp}  FN={fn}  TP={tp}")

"""
src/quantum/qsvm.py
===================
Quantum Kernel Support Vector Machine  (method D — standalone classifier).

Role: CLASSIFIER (takes PCA features directly)
-------
The QSVM uses a quantum fidelity kernel to measure distances between
data points in a high-dimensional Hilbert space.  An SVC is trained
ENTIRELY on these quantum distances — no classical distance is used.

The QSVM is a standalone method (ablation D).  It is NOT a feature
extractor and is NOT part of the ensemble (methods A/B/C).

Input: tanh(Z[:, :n_qubits])   — first 6 PCA dims, scaled to (-1,+1)
              (same conditioning as QAE)

ZZFeatureMap (depth-1)
----------------------
  Encodes x into quantum state |ϕ(x)⟩:
    H + RZ(2*x_i)                        on each qubit      (single-qubit)
    CNOT + RZ(2*(π-x_i)(π-x_j)) + CNOT  for adjacent pairs (two-qubit ZZ)

  Quantum kernel:
    K(x₁, x₂) = |⟨ϕ(x₁)|ϕ(x₂)⟩|² = P(|00…0⟩)

  This is the FIDELITY between two quantum states — a genuine quantum
  distance operating in Hilbert space, as required by the problem statement.

Reference
---------
  Havlíček V et al. (2019) "Supervised learning with quantum-enhanced
  feature spaces." Nature 567, 209-212.

Usage
-----
    from src.quantum.qsvm import build_qsvm
    clf, K_tr, K_ts, idx = build_qsvm(
        Z_train, y_train, Z_test,
        n_qubits=CFG["n_qubits"],
        n_support=CFG["qsvm_n_train"],
    )
    probs = clf.predict_proba(K_ts)[:, 1]
"""

import numpy as np
import pennylane as qml
from sklearn.svm import SVC


# ---------------------------------------------------------------------------
# ZZFeatureMap circuit factory
# ---------------------------------------------------------------------------

def _make_qkernel_circuit(n_qubits: int):
    """
    Return a PennyLane QNode for the ZZ fidelity kernel circuit.

    K(x₁, x₂) = P(|00…0⟩) = |⟨0| U†(x₂) U(x₁) |0⟩|²
    """
    dev = qml.device("default.qubit", wires=n_qubits)

    def _zzfm(x):
        """One repetition of ZZFeatureMap (depth-1)."""
        for i in range(n_qubits):
            qml.Hadamard(wires=i)
            qml.RZ(2.0 * float(x[i]), wires=i)
        for i in range(n_qubits - 1):
            qml.CNOT(wires=[i, i + 1])
            qml.RZ(
                2.0 * (np.pi - float(x[i])) * (np.pi - float(x[i + 1])),
                wires=i + 1,
            )
            qml.CNOT(wires=[i, i + 1])

    @qml.qnode(dev, interface="numpy")
    def qkernel_circuit(x1, x2):
        _zzfm(x1)
        qml.adjoint(_zzfm)(x2)
        return qml.probs(wires=list(range(n_qubits)))

    return qkernel_circuit


# ---------------------------------------------------------------------------
# Kernel matrix builder
# ---------------------------------------------------------------------------

def compute_kernel_matrix(X_rows: np.ndarray,
                          X_cols: np.ndarray,
                          circuit,
                          tag:    str = "") -> np.ndarray:
    """
    Build an (n_rows × n_cols) quantum fidelity kernel matrix.

    K[i, j] = P(|00…0⟩) when circuit runs U†(x_cols[j]) U(x_rows[i])

    Parameters
    ----------
    X_rows, X_cols : (N, n_qubits) arrays — tanh-scaled PCA features
    circuit        : QNode returned by _make_qkernel_circuit
    tag            : str  for progress printing

    Returns
    -------
    K : (n_rows, n_cols) float64 kernel matrix
    """
    K = np.zeros((len(X_rows), len(X_cols)), dtype=np.float64)
    for i, xi in enumerate(X_rows):
        for j, xj in enumerate(X_cols):
            K[i, j] = float(circuit(
                np.asarray(xi, dtype=np.float64),
                np.asarray(xj, dtype=np.float64),
            )[0])
        if (i + 1) % 25 == 0 or (i + 1) == len(X_rows):
            print(f"    {tag} row {i+1}/{len(X_rows)}"
                  f"  ({100*(i+1)/len(X_rows):.0f}%) ...")
    return K


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_qsvm(Z_train:   np.ndarray,
               y_train:   np.ndarray,
               Z_test:    np.ndarray,
               n_qubits:  int = 6,
               n_support: int = 150,
               seed:      int = 42) -> tuple:
    """
    Build and train a Quantum Kernel SVM classifier.

    The QSVM is a standalone CLASSIFIER that uses PCA features as input.
    It does NOT extract features for downstream use.

    Parameters
    ----------
    Z_train   : (N_train, >=n_qubits) PCA features
    y_train   : (N_train,) binary labels
    Z_test    : (N_test,  >=n_qubits) PCA features
    n_qubits  : int  qubits in ZZFeatureMap  (= 6, matches n_qubits in CFG)
    n_support : int  support set size (kernel is O(N^2); 150 is standard)
    seed      : int  random seed for support set sampling

    Returns
    -------
    (clf, K_train, K_test, support_idx)
      clf         : fitted SVC(kernel='precomputed', probability=True)
      K_train     : (n_support, n_support) quantum kernel matrix
      K_test      : (N_test, n_support)   quantum kernel matrix
      support_idx : indices into Z_train that form the support set
    """
    # tanh-scale first n_qubits PCA dims -> same conditioning as QAE
    np.random.seed(seed)
    idx    = np.random.choice(len(Z_train), n_support, replace=False)
    X_tr   = np.tanh(Z_train[idx, :n_qubits].astype(np.float64))
    y_sub  = y_train[idx]
    X_ts   = np.tanh(Z_test[:, :n_qubits].astype(np.float64))

    circuit = _make_qkernel_circuit(n_qubits)

    print(f"  Building train-train kernel ({n_support}×{n_support}) ...")
    K_tr = compute_kernel_matrix(X_tr, X_tr, circuit, "Train-Train")
    print(f"  Building test-train  kernel ({len(Z_test)}×{n_support}) ...")
    K_ts = compute_kernel_matrix(X_ts, X_tr, circuit, "Test-Train ")

    clf = SVC(kernel="precomputed", probability=True,
              class_weight="balanced", C=1.0, random_state=seed)
    clf.fit(K_tr, y_sub)

    # For precomputed kernel SVC, support vectors are stored differently
    n_sv = len(clf.support_)
    print(f"  SVM support vectors: {n_sv}")
    print(f"  QSVM preliminary AUC (train data — indicative only):")
    from sklearn.metrics import roc_auc_score
    tr_probs = clf.predict_proba(K_tr)[:, 1]
    print(f"    train AUC = {roc_auc_score(y_sub, tr_probs):.4f}")

    return clf, K_tr, K_ts, idx


# ---------------------------------------------------------------------------
# C2:  QAE features → QSVM  (fully quantum pipeline after PCA)
# ---------------------------------------------------------------------------

def build_qsvm_from_features(X_tr_raw:  np.ndarray,
                              y_train:   np.ndarray,
                              X_ts_raw:  np.ndarray,
                              n_support: int = 150,
                              seed:      int = 42) -> tuple:
    """
    Build a Quantum Kernel SVM on pre-extracted features (Method C2).

    Unlike build_qsvm() which takes raw PCA features and slices/tanh-scales
    internally, this function accepts already-processed feature vectors —
    specifically the 6-dim QAE expectation values from extract_qae_features().

    This creates the fully-quantum pipeline:
        PCA (198→25) → QAE encoder (25→6, quantum) → QSVM quantum kernel

    QAE expectation values are PauliZ expectation values ∈ (-1, +1).
    We clip to [-1, 1] (no second tanh — that would compress the already
    bounded range unnecessarily) and feed directly into the ZZ kernel.

    The ZZ kernel measures fidelity in a 2^n Hilbert space spanned by
    the quantum features, giving a richer distance metric than the RBF kernel
    on the same data.

    Parameters
    ----------
    X_tr_raw  : (N_train, n_qubits) — QAE expectation values, already ∈ (-1,+1)
    y_train   : (N_train,) binary labels  (needed for stratified support set)
    X_ts_raw  : (N_test,  n_qubits) — QAE expectation values for test set
    n_support : int  support candidates (kernel is O(N²); 150 is standard)
    seed      : int  random seed

    Returns
    -------
    (clf, K_train, K_test, support_idx)
      clf         : fitted SVC(kernel='precomputed', probability=True)
      K_train     : (n_support, n_support) quantum kernel matrix
      K_test      : (N_test, n_support)   quantum kernel matrix
      support_idx : indices into X_tr_raw / y_train forming the support set
    """
    n_qubits = X_tr_raw.shape[1]
    np.random.seed(seed)

    # Stratified support set — equal mineral + background.
    # Random sampling with a skewed class ratio creates a poor kernel
    # (most support vectors from majority class → poor minority separation).
    pos_idx = np.where(y_train == 1)[0]
    neg_idx = np.where(y_train == 0)[0]
    n_each  = min(n_support // 2, len(pos_idx), len(neg_idx))
    idx     = np.concatenate([
        np.random.choice(pos_idx, n_each, replace=False),
        np.random.choice(neg_idx, n_each, replace=False),
    ])
    np.random.shuffle(idx)

    # Clip to [-1, 1] — QAE PauliZ expectation values are inherently bounded,
    # but floating-point operations can occasionally push slightly outside.
    X_tr  = np.clip(X_tr_raw[idx].astype(np.float64), -1.0, 1.0)
    y_sub = y_train[idx]
    X_ts  = np.clip(X_ts_raw.astype(np.float64), -1.0, 1.0)

    circuit = _make_qkernel_circuit(n_qubits)

    print(f"  [C2] Building train-train kernel ({len(idx)}×{len(idx)},"
          f" {n_each} pos + {n_each} neg, stratified) ...")
    K_tr = compute_kernel_matrix(X_tr, X_tr, circuit, "C2-Train-Train")
    print(f"  [C2] Building test-train  kernel ({len(X_ts)}×{len(idx)}) ...")
    K_ts = compute_kernel_matrix(X_ts, X_tr, circuit, "C2-Test-Train ")

    clf = SVC(kernel="precomputed", probability=True,
              class_weight="balanced", C=1.0, random_state=seed)
    clf.fit(K_tr, y_sub)

    n_sv = len(clf.support_)
    print(f"  [C2] SVC support vectors : {n_sv}")
    from sklearn.metrics import roc_auc_score
    tr_probs = clf.predict_proba(K_tr)[:, 1]
    print(f"  [C2] Train AUC (support set) : {roc_auc_score(y_sub, tr_probs):.4f}")

    return clf, K_tr, K_ts, idx

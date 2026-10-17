"""
src/quantum/noise.py
====================
Noise-aware quantum circuit factories for publication-grade resilience analysis.

Implements three physically motivated noise channels:

1. **Depolarizing noise** — random Pauli errors after every entangling layer.
   Models gate imperfections on superconducting/trapped-ion QPUs.
   p_depol ∈ [0, 0.1] covers current NISQ hardware range.

2. **Amplitude damping** — energy dissipation (T1 decay).
   Models spontaneous emission during circuit execution.
   gamma ∈ [0, 0.1] for realistic QPU conditions.

3. **Finite shot noise** — statistical sampling of expectation values.
   Replaces analytic ⟨Z⟩ with shot-sampled estimates.
   shots ∈ {256, 1024, 4096, 8192} typical for NISQ experiments.

Reference hardware noise budgets (2024-2025):
  IBM Eagle r3  : 1q error ~0.02%, 2q error ~0.5%, T1 ~300µs
  IonQ Forte    : 1q error ~0.03%, 2q error ~0.5%, T1 ~10s
  Rigetti Ankaa : 1q error ~0.1%,  2q error ~1.5%, T1 ~30µs

Usage
-----
    from src.quantum.noise import (
        make_noisy_qae_circuit,
        make_noisy_qkernel_circuit,
        make_noisy_qaa_circuit,
        extract_noisy_qae_features,
        run_noise_sweep_qae,
        run_shot_noise_sweep,
    )

    # Drop-in replacement for ideal QAE circuit
    noisy_qae = make_noisy_qae_circuit(6, 3, p_depol=0.01)

    # Systematic noise sweep
    results = run_noise_sweep_qae(...)
"""

import numpy as np
import pennylane as qml
from typing import Optional

try:
    import torch
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _insert_depolarizing(n_qubits: int, p: float):
    """Insert depolarizing noise on all qubits."""
    for i in range(n_qubits):
        qml.DepolarizingChannel(p, wires=i)


def _insert_amplitude_damping(n_qubits: int, gamma: float):
    """Insert amplitude damping noise on all qubits."""
    for i in range(n_qubits):
        qml.AmplitudeDamping(gamma, wires=i)


def _insert_noise_layer(n_qubits: int, p_depol: float, gamma_ad: float):
    """Insert all applicable noise channels after an entangling layer."""
    if p_depol > 0:
        _insert_depolarizing(n_qubits, p_depol)
    if gamma_ad > 0:
        _insert_amplitude_damping(n_qubits, gamma_ad)


# ---------------------------------------------------------------------------
# 1. Noisy QAE circuit factory
# ---------------------------------------------------------------------------

def make_noisy_qae_circuit(
    n_qubits: int,
    n_layers: int,
    p_depol: float = 0.0,
    gamma_ad: float = 0.0,
    shots: Optional[int] = None,
):
    """
    Build a PennyLane QNode for the HE-QAE circuit with noise channels.

    The circuit structure matches qae.py exactly (RY encoding, CNOT chain,
    CZ long-range, data re-uploading), with noise channels inserted after
    each entangling layer and before measurement.

    Parameters
    ----------
    n_qubits : int   — number of qubits (must match trained weights)
    n_layers : int   — number of entangling layers
    p_depol  : float — depolarizing channel probability per qubit per layer
    gamma_ad : float — amplitude damping parameter per qubit per layer
    shots    : int   — finite shot count (None = analytic expectation values)

    Returns
    -------
    QNode with signature: circuit(x, weights) -> list of n_qubits expvals
    """
    use_noise = (p_depol > 0) or (gamma_ad > 0)
    use_shots = shots is not None

    # Device selection:
    #   noise channels -> default.mixed (density matrix)
    #   no noise       -> default.qubit (statevector, faster)
    dev_name = "default.mixed" if use_noise else "default.qubit"
    dev = qml.device(dev_name, wires=n_qubits, shots=shots)

    # Interface / diff_method selection:
    #   shot-based  -> interface=None, diff_method=None (forward-only)
    #   noisy       -> backprop on default.mixed
    #   ideal       -> adjoint on default.qubit
    if use_shots:
        iface, dm = None, None
    elif use_noise:
        iface, dm = "torch", "backprop"
    else:
        iface, dm = "torch", "adjoint"

    @qml.qnode(dev, interface=iface, diff_method=dm)
    def noisy_hea_qae(x, weights):
        # Data encoding — identical to qae._make_hea_qae_circuit
        for i in range(n_qubits):
            qml.RY(x[i], wires=i)

        # Entangling layers with noise
        for l in range(n_layers):
            for i in range(n_qubits - 1):
                qml.RY(weights[l, i], wires=i)
            qml.RY(weights[l, n_qubits - 1], wires=n_qubits - 1)
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])

            # Noise AFTER each entangling layer
            _insert_noise_layer(n_qubits, p_depol, gamma_ad)

        # Long-range entanglement
        qml.CZ(wires=[0, n_qubits - 1])

        # Data re-uploading
        for i in range(n_qubits):
            qml.RY(x[i] * 0.5, wires=i)

        # Final measurement noise
        if p_depol > 0:
            _insert_depolarizing(n_qubits, p_depol)

        return [qml.expval(qml.PauliZ(i)) for i in range(n_qubits)]

    return noisy_hea_qae


# ---------------------------------------------------------------------------
# 2. Noisy QSVM kernel circuit factory
# ---------------------------------------------------------------------------

def make_noisy_qkernel_circuit(
    n_qubits: int,
    p_depol: float = 0.0,
    gamma_ad: float = 0.0,
    shots: Optional[int] = None,
):
    """
    Build a PennyLane QNode for the ZZ fidelity kernel with noise.

    Matches qsvm._make_qkernel_circuit() exactly, with noise channels
    inserted after the ZZFeatureMap encoding.

    Parameters
    ----------
    n_qubits : int   — number of qubits
    p_depol  : float — depolarizing channel probability
    gamma_ad : float — amplitude damping parameter
    shots    : int   — finite shot count (None = analytic)
    """
    use_noise = (p_depol > 0) or (gamma_ad > 0)
    dev_name = "default.mixed" if use_noise else "default.qubit"
    dev = qml.device(dev_name, wires=n_qubits, shots=shots)

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
    def noisy_qkernel(x1, x2):
        _zzfm(x1)
        # Noise after encoding x1
        _insert_noise_layer(n_qubits, p_depol, gamma_ad)
        qml.adjoint(_zzfm)(x2)
        # Noise after adjoint encoding
        _insert_noise_layer(n_qubits, p_depol, gamma_ad)
        return qml.probs(wires=list(range(n_qubits)))

    return noisy_qkernel


# ---------------------------------------------------------------------------
# 3. Noisy QAA bottleneck circuit factory
# ---------------------------------------------------------------------------

def make_noisy_qaa_circuit(
    n_qubits: int = 6,
    n_latent: int = 2,
    n_layers: int = 3,
    p_depol: float = 0.0,
    gamma_ad: float = 0.0,
    shots: Optional[int] = None,
):
    """
    Build a PennyLane QNode for the QAA bottleneck circuit with noise.

    Matches qaa._make_qae_bottleneck_circuit() exactly, with noise
    channels inserted after each variational layer.

    Parameters
    ----------
    n_qubits : int   — total qubits (latent + trash)
    n_latent : int   — number of latent qubits
    n_layers : int   — HEA depth
    p_depol  : float — depolarizing noise
    gamma_ad : float — amplitude damping
    shots    : int   — finite shot count (None = analytic)
    """
    trash_wires = list(range(n_latent, n_qubits))
    n_params = n_qubits * n_layers

    use_noise = (p_depol > 0) or (gamma_ad > 0)
    use_shots = shots is not None
    dev_name = "default.mixed" if use_noise else "default.qubit"
    dev = qml.device(dev_name, wires=n_qubits, shots=shots)

    if use_shots:
        dm = None
    elif use_noise:
        dm = "backprop"
    else:
        dm = "adjoint"

    @qml.qnode(dev, diff_method=dm)
    def noisy_qaa(x, weights):
        # Data encoding
        for i in range(n_qubits):
            qml.RY(float(x[i]), wires=i)

        # Variational encoder layers with noise
        idx = 0
        for _layer in range(n_layers):
            for i in range(n_qubits):
                qml.RY(float(weights[idx]), wires=i)
                idx += 1
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])
            if n_qubits > 2:
                qml.CZ(wires=[0, n_qubits - 1])

            # Noise after each entangling layer
            _insert_noise_layer(n_qubits, p_depol, gamma_ad)

        # Re-upload
        for i in range(n_qubits):
            qml.RY(float(x[i]) * 0.5, wires=i)

        # Final noise before measurement
        if p_depol > 0:
            _insert_depolarizing(n_qubits, p_depol)

        return qml.probs(wires=trash_wires)

    return noisy_qaa, n_params, trash_wires


# ---------------------------------------------------------------------------
# 4. Noisy feature extraction helpers
# ---------------------------------------------------------------------------

def extract_noisy_qae_features(
    Z: np.ndarray,
    weights,
    n_qubits: int = 6,
    n_layers: int = 3,
    p_depol: float = 0.01,
    gamma_ad: float = 0.0,
    shots: Optional[int] = None,
    n_repeats: int = 1,
) -> np.ndarray:
    """
    Run QAE encoder inference with noise on all samples.

    When shots is not None or n_repeats > 1, averages over multiple
    circuit executions to reduce statistical variance.

    Parameters
    ----------
    Z         : (N, D) float32 — PCA features
    weights   : (n_layers, n_qubits) tensor — trained QAE weights
    n_qubits  : int
    n_layers  : int
    p_depol   : float — depolarizing noise level
    gamma_ad  : float — amplitude damping level
    shots     : int   — finite shot count (None = analytic)
    n_repeats : int   — repetitions to average (for shot noise)

    Returns
    -------
    (N, n_qubits) float32 array of noisy quantum features.
    """
    if not _HAS_TORCH:
        raise ImportError("PyTorch is required for noisy QAE feature extraction")

    circuit = make_noisy_qae_circuit(
        n_qubits, n_layers, p_depol=p_depol,
        gamma_ad=gamma_ad, shots=shots,
    )

    # Determine if circuit uses torch interface
    use_torch_iface = (shots is None) and _HAS_TORCH

    feats = []
    if use_torch_iface:
        with torch.no_grad():
            Xq = torch.tanh(torch.tensor(Z[:, :n_qubits], dtype=torch.float32))
            for i, x in enumerate(Xq):
                if n_repeats > 1:
                    accum = np.zeros(n_qubits, dtype=np.float64)
                    for _ in range(n_repeats):
                        q = torch.stack(circuit(x, weights))
                        accum += q.numpy()
                    feats.append((accum / n_repeats).astype(np.float32))
                else:
                    q = torch.stack(circuit(x, weights))
                    feats.append(q.numpy())
                if (i + 1) % 100 == 0:
                    print(f"    Noisy QAE extraction: {i+1}/{len(Xq)} ...",
                          end="\r", flush=True)
    else:
        # Shot-based or numpy interface — pass numpy arrays
        Xq = np.tanh(Z[:, :n_qubits].astype(np.float64))
        if _HAS_TORCH:
            w_np = weights.detach().numpy().astype(np.float64)
        else:
            w_np = np.asarray(weights, dtype=np.float64)
        for i, x in enumerate(Xq):
            if n_repeats > 1:
                accum = np.zeros(n_qubits, dtype=np.float64)
                for _ in range(n_repeats):
                    out = circuit(x, w_np)
                    accum += np.array([float(o) for o in out])
                feats.append((accum / n_repeats).astype(np.float32))
            else:
                out = circuit(x, w_np)
                feats.append(np.array([float(o) for o in out], dtype=np.float32))
            if (i + 1) % 100 == 0:
                print(f"    Noisy QAE extraction: {i+1}/{len(Xq)} ...",
                      end="\r", flush=True)

    if len(Xq) >= 100:
        print(f"    Noisy QAE extraction: {len(Xq)}/{len(Xq)} done.         ")

    return np.array(feats, dtype=np.float32)


def noisy_qaa_anomaly_scores(
    Z: np.ndarray,
    weights: np.ndarray,
    n_qubits: int = 6,
    n_latent: int = 2,
    n_layers: int = 3,
    p_depol: float = 0.01,
    gamma_ad: float = 0.0,
    shots: Optional[int] = None,
) -> np.ndarray:
    """
    Compute QAA bottleneck anomaly scores with noise.

    score(x) = 1 − P(trash qubits = |0...0⟩)

    Parameters
    ----------
    Z        : (N, n_pca) PCA features
    weights  : (n_params,) trained QAA weights
    p_depol  : float — depolarizing noise
    gamma_ad : float — amplitude damping
    shots    : int   — finite shots

    Returns
    -------
    scores : (N,) float32 anomaly scores ∈ [0, 1]
    """
    circuit, _, _ = make_noisy_qaa_circuit(
        n_qubits, n_latent, n_layers,
        p_depol=p_depol, gamma_ad=gamma_ad, shots=shots,
    )

    X = np.tanh(Z[:, :n_qubits].astype(np.float64))
    w = weights.astype(np.float64)

    scores = np.empty(len(X), dtype=np.float32)
    for i, x in enumerate(X):
        probs = circuit(x, w)
        scores[i] = float(1.0 - probs[0])
        if (i + 1) % 200 == 0:
            print(f"    Noisy QAA scoring {i+1}/{len(X)} ...",
                  end="\r", flush=True)

    if len(X) >= 200:
        print(f"    Noisy QAA scoring: {len(X)}/{len(X)} done.         ")

    return scores


# ---------------------------------------------------------------------------
# 5. Noise sweep API
# ---------------------------------------------------------------------------

def run_noise_sweep_qae(
    Z_test: np.ndarray,
    y_test: np.ndarray,
    qae_weights,
    ensemble_clf,
    qae_scaler,
    Z_test_pca_scaled: np.ndarray,
    corr_test_scaled: np.ndarray,
    n_qubits: int = 6,
    n_layers: int = 3,
    noise_levels: list = None,
    noise_type: str = "depolarizing",
) -> dict:
    """
    Systematic noise sweep for QAE+ensemble pipeline.

    For each noise level, re-extracts QAE features with noise, rebuilds
    the full feature vector [PCA | QAE_noisy | corr], and computes
    classification metrics.

    Parameters
    ----------
    Z_test             : (N, D) raw PCA features (before QAE)
    y_test             : (N,) ground-truth labels
    qae_weights        : trained QAE weights tensor
    ensemble_clf       : fitted ensemble classifier (for method C)
    qae_scaler         : fitted StandardScaler for QAE features
    Z_test_pca_scaled  : (N, 25) pre-scaled PCA features
    corr_test_scaled   : (N, 2) pre-scaled USGS correlation features
    noise_levels       : list of float — noise parameter values
    noise_type         : "depolarizing" or "amplitude_damping"

    Returns
    -------
    dict mapping noise_level_str -> {"roc_auc", "f1", "mcc", "acc", ...}
    """
    from sklearn.metrics import (
        roc_auc_score, f1_score, matthews_corrcoef,
        accuracy_score, balanced_accuracy_score,
    )

    if noise_levels is None:
        noise_levels = [0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1]

    results = {}

    for p in noise_levels:
        print(f"\n  [NOISE SWEEP] {noise_type}={p:.4f} ...")
        p_depol = p if noise_type == "depolarizing" else 0.0
        gamma = p if noise_type == "amplitude_damping" else 0.0

        # Extract noisy QAE features
        noisy_feats = extract_noisy_qae_features(
            Z_test, qae_weights, n_qubits, n_layers,
            p_depol=p_depol, gamma_ad=gamma,
        )

        # Scale features using TRAINING scaler (no re-fitting!)
        noisy_feats_sc = qae_scaler.transform(noisy_feats)

        # Build full feature vector: [PCA | QAE_noisy | corr]
        X_full = np.hstack([Z_test_pca_scaled, noisy_feats_sc, corr_test_scaled])

        # Predict
        preds = ensemble_clf.predict(X_full)
        probs = ensemble_clf.predict_proba(X_full)[:, 1]

        # Metrics
        try:
            auc = float(roc_auc_score(y_test, probs))
        except ValueError:
            auc = 0.5

        key = f"{p:.4f}"
        results[key] = {
            "noise_level": p,
            "noise_type": noise_type,
            "roc_auc": auc,
            "f1": float(f1_score(y_test, preds, zero_division=0)),
            "mcc": float(matthews_corrcoef(y_test, preds)),
            "acc": float(accuracy_score(y_test, preds)),
            "bal_acc": float(balanced_accuracy_score(y_test, preds)),
        }

        print(f"             AUC={auc:.4f}  "
              f"F1={results[key]['f1']:.4f}  "
              f"MCC={results[key]['mcc']:.4f}")

    return results


def run_shot_noise_sweep(
    Z_test: np.ndarray,
    y_test: np.ndarray,
    qae_weights,
    ensemble_clf,
    qae_scaler,
    Z_test_pca_scaled: np.ndarray,
    corr_test_scaled: np.ndarray,
    n_qubits: int = 6,
    n_layers: int = 3,
    shots_list: list = None,
) -> dict:
    """
    Sweep over finite shot counts for QAE pipeline.

    At each shot count, the QAE expectation values are sampled from
    finite measurements (averaged over 3 repetitions to reduce variance).

    Parameters
    ----------
    shots_list : list of int — shot counts to evaluate

    Returns
    -------
    dict mapping shots_str -> metrics dict
    """
    from sklearn.metrics import (
        roc_auc_score, f1_score, matthews_corrcoef,
        accuracy_score, balanced_accuracy_score,
    )

    if shots_list is None:
        shots_list = [256, 1024, 4096, 8192]

    results = {}

    for n_shots in shots_list:
        print(f"\n  [SHOT SWEEP] shots={n_shots} ...")

        noisy_feats = extract_noisy_qae_features(
            Z_test, qae_weights, n_qubits, n_layers,
            p_depol=0.0, gamma_ad=0.0,
            shots=n_shots, n_repeats=3,
        )

        noisy_feats_sc = qae_scaler.transform(noisy_feats)
        X_full = np.hstack([Z_test_pca_scaled, noisy_feats_sc, corr_test_scaled])

        preds = ensemble_clf.predict(X_full)
        probs = ensemble_clf.predict_proba(X_full)[:, 1]

        try:
            auc = float(roc_auc_score(y_test, probs))
        except ValueError:
            auc = 0.5

        key = str(n_shots)
        results[key] = {
            "shots": n_shots,
            "roc_auc": auc,
            "f1": float(f1_score(y_test, preds, zero_division=0)),
            "mcc": float(matthews_corrcoef(y_test, preds)),
            "acc": float(accuracy_score(y_test, preds)),
            "bal_acc": float(balanced_accuracy_score(y_test, preds)),
        }

        print(f"             AUC={auc:.4f}  F1={results[key]['f1']:.4f}")

    return results

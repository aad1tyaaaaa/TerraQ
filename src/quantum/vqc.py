"""
src/quantum/vqc.py
==================
Variational Quantum Classifier  (method E — standalone classifier).

Role: CLASSIFIER (the QUANTUM CIRCUIT IS the classifier)
-------
The VQC takes PCA features as input, processes them through a parameterised
quantum circuit, and outputs a class probability — all classification logic
is performed by the quantum circuit.  There is NO classical decision layer.

The VQC is a standalone method (ablation E).  It is NOT a feature extractor
and is NOT part of the ensemble (methods A/B/C).

The only classical component is the upstream PCA dimensionality reduction.

Architecture  (4 qubits, 2 layers)
------------------------------------
  Input : tanh(Z[:, :4])   — first 4 PCA dims, scaled to (-1, +1)

  1. AngleEmbedding:
        RY(π × x_i)  on qubit i  — maps tanh-scaled input to Bloch sphere
        Angles span [-π, π] for full Bloch-sphere coverage.

  2. StronglyEntanglingLayers  (2 layers, 24 Euler-angle parameters):
        per layer: RZ-RY-RZ rotations + CNOT ring on all qubits.
        Creates high-expressive entangled quantum state.

  3. Measurement:
        ⟨Z₀⟩  on qubit 0  →  expectation value ∈ [-1, +1]
        p = σ(3 × ⟨Z₀⟩)   where σ = sigmoid

  Class probability p ∈ [0.05, 0.95] — the 3× scale factor keeps the
  sigmoid from saturating while spanning a useful probability range.

  Note: we measure qubit 0 (= original Schuld et al. 2020 convention).

Loss: class-imbalance-weighted binary cross-entropy
    L = Σ_i w_i × BCE(p_i, y_i)
    where w_i = n_neg/n_pos  for positive class,  1.0 for negative class.

Reference
---------
  Schuld M et al. (2020) "Circuit-centric quantum classifiers."
  Physical Review A 101, 032308.

Usage
-----
    from src.quantum.vqc import train_vqc, vqc_predict
    weights         = train_vqc(Z_train[idx], y_train[idx], CFG)
    probs, preds    = vqc_predict(Z_test, weights, CFG["n_vqc_qubits"])
"""

import numpy as np
import torch
import pennylane as qml


# ---------------------------------------------------------------------------
# VQC circuit factory
# ---------------------------------------------------------------------------

def _make_vqc_circuit(n_qubits: int, n_layers: int):
    """
    Return a PennyLane QNode for the VQC circuit.

    x       : (n_qubits,) input features, tanh-scaled to (-1, +1)
    weights : (n_layers, n_qubits, 3) Euler-angle parameters

    Returns: expval(PauliZ[0])  ∈ [-1, +1]
    """
    dev = qml.device("default.qubit", wires=n_qubits)

    @qml.qnode(dev, interface="torch", diff_method="adjoint")
    def vqc_circuit(x, weights):
        """
        1. AngleEmbedding: x_i → RY(π × x_i) on qubit i
           (angles span [-π, π] for full Bloch-sphere coverage)
        2. StronglyEntanglingLayers: RZ-RY-RZ + CNOT ring per layer
        3. Measure ⟨Z₀⟩ on qubit 0 → sigmoid(3×) = class probability
        """
        qml.AngleEmbedding(np.pi * x, wires=range(n_qubits), rotation="Y")
        qml.StronglyEntanglingLayers(weights, wires=range(n_qubits))
        return qml.expval(qml.PauliZ(0))   # qubit 0 — original convention

    return vqc_circuit


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_vqc(Z_tr:     np.ndarray,
              y_tr:     np.ndarray,
              n_qubits: int   = 4,
              n_layers: int   = 2,
              epochs:   int   = 50,
              lr:       float = 0.05,
              patience: int   = 12,
              seed:     int   = 42) -> torch.Tensor:
    """
    Train VQC weights using class-weighted binary cross-entropy.

    Parameters
    ----------
    Z_tr      : (N, >=n_qubits) PCA features  (first n_qubits dims used)
    y_tr      : (N,) binary labels
    n_qubits  : int   qubits = number of PCA dims encoded  (= 4)
    n_layers  : int   StronglyEntanglingLayers depth  (= 2)
    epochs    : int   max training epochs
    lr        : float Adam learning rate
    patience  : int   early stopping patience

    Returns
    -------
    best_weights : torch.Tensor  shape (n_layers, n_qubits, 3)
    """
    torch.manual_seed(seed)
    circuit = _make_vqc_circuit(n_qubits, n_layers)

    # Xavier-style init for rotation angles
    with torch.no_grad():
        weights = torch.randn(n_layers, n_qubits, 3) * 0.3
    weights.requires_grad_(True)
    opt = torch.optim.Adam([weights], lr=lr)

    # tanh-scale first n_qubits PCA dims to (-1, +1)
    Xv = torch.tanh(torch.tensor(Z_tr[:, :n_qubits], dtype=torch.float32))
    yv = torch.tensor(y_tr, dtype=torch.float32)

    # 10% validation split
    n_val  = max(1, len(Xv) // 10)
    Xv_tr  = Xv[:-n_val];    yv_tr = yv[:-n_val]
    Xv_val = Xv[-n_val:];    yv_val = yv[-n_val:]

    # Class balance: up-weight minority (positive) class
    n_pos  = yv_tr.sum().item()
    n_neg  = len(yv_tr) - n_pos
    pos_w  = n_neg / (n_pos + 1e-9)

    best_val, pat, best_w = float("inf"), 0, None

    for ep in range(epochs):
        accum_grad = torch.zeros_like(weights)
        ep_loss    = 0.0
        for idx in range(len(Xv_tr)):
            if weights.grad is not None:
                weights.grad.zero_()
            logit = circuit(Xv_tr[idx], weights).float()  # Double -> Float32
            prob  = torch.sigmoid(logit * 3.0)
            w     = pos_w if yv_tr[idx] > 0.5 else 1.0
            loss  = w * torch.nn.functional.binary_cross_entropy(
                        prob.unsqueeze(0), yv_tr[idx].unsqueeze(0))
            loss.backward()
            accum_grad = accum_grad + weights.grad.detach()
            ep_loss   += loss.item()
        with torch.no_grad():
            weights.grad = accum_grad / len(Xv_tr)
        opt.step()

        # Validation loss
        with torch.no_grad():
            vl = 0.0
            for idx in range(len(Xv_val)):
                logit = circuit(Xv_val[idx], weights).float()
                prob  = torch.sigmoid(logit * 3.0)
                ww    = pos_w if yv_val[idx] > 0.5 else 1.0
                vl += ww * torch.nn.functional.binary_cross_entropy(
                          prob.unsqueeze(0), yv_val[idx].unsqueeze(0)).item()
            vl /= max(1, len(Xv_val))

        if ep % 10 == 0:
            print(f"    Epoch {ep:3d}  train={ep_loss/len(Xv_tr):.4f}"
                  f"  val={vl:.4f}")
        if vl < best_val - 1e-5:
            best_val, pat = vl, 0
            best_w = weights.detach().clone()
        else:
            pat += 1
            if pat >= patience:
                print(f"    VQC early stop at epoch {ep+1}"
                      f"  best_val={best_val:.4f}")
                break

    return best_w if best_w is not None else weights.detach()


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def vqc_predict(Z:        np.ndarray,
                weights:  torch.Tensor,
                n_qubits: int = 4,
                n_layers: int = 2) -> tuple:
    """
    Run VQC inference on all samples.

    The quantum circuit outputs the class-1 probability directly:
        p = sigmoid(3 × ⟨Z₀⟩)

    Parameters
    ----------
    Z        : (N, >=n_qubits) PCA features
    weights  : (n_layers, n_qubits, 3) trained weights

    Returns
    -------
    (probs, preds)
      probs : (N,) float32 class-1 probabilities
      preds : (N,) int32   binary predictions (threshold = 0.5)
    """
    circuit = _make_vqc_circuit(n_qubits, n_layers)
    probs   = []
    with torch.no_grad():
        Xv = torch.tanh(torch.tensor(Z[:, :n_qubits], dtype=torch.float32))
        for x in Xv:
            logit = circuit(x, weights).float()
            p     = torch.sigmoid(logit * 3.0).item()
            probs.append(p)
    probs = np.array(probs, dtype=np.float32)
    preds = (probs >= 0.5).astype(np.int32)
    return probs, preds


# ===========================================================================
# C3:  QAE features → VQC  (end-to-end trainable quantum pipeline)
# ===========================================================================

def train_vqc_from_features(X_tr:     np.ndarray,
                             y_tr:     np.ndarray,
                             n_qubits: int   = 6,
                             n_layers: int   = 2,
                             epochs:   int   = 50,
                             lr:       float = 0.05,
                             patience: int   = 15,
                             seed:     int   = 42) -> tuple:
    """
    Train VQC on pre-extracted features (Method C3: PCA→QAE→VQC).

    Unlike train_vqc() which applies internal tanh-scaling to raw PCA dims,
    this function accepts already-extracted QAE expectation values in (-1, +1).
    Internal tanh is deliberately SKIPPED — the QAE outputs are already bounded
    and a second tanh would compress them to (-0.76, +0.76), losing resolution
    in the tails.  Instead the values are mapped to AngleEmbedding angles via:

        RY(π × x_i)   where x_i ∈ (-1, +1)  →  angles ∈ (-π, π)

    This gives full Bloch-sphere coverage — the same intended range as the
    original VQC, but without the distortion of a double-tanh cascade.

    The training loop accumulates parameter-shift gradients across the
    mini-batch in all-sample mode (no stochastic batching), consistent with
    the SPSA convention used for quantum gradient accumulation.

    Parameters
    ----------
    X_tr      : (N, n_qubits) QAE expectation values  (already ∈ (-1, +1))
    y_tr      : (N,) binary labels
    n_qubits  : int   qubits in VQC  (should match QAE n_qubits = 6)
    n_layers  : int   StronglyEntanglingLayers depth
    epochs    : int   max training epochs
    lr        : float Adam learning rate
    patience  : int   early-stopping patience (larger than train_vqc since
                      QAE features are smoother and need more iterations)
    seed      : int   random seed

    Returns
    -------
    (best_weights, history)
      best_weights : torch.Tensor  shape (n_layers, n_qubits, 3)
      history      : dict {"train": [float, ...], "val": [float, ...]}
    """
    torch.manual_seed(seed)
    circuit = _make_vqc_circuit(n_qubits, n_layers)

    # Xavier-style init for rotation angles — same as train_vqc
    with torch.no_grad():
        weights = torch.randn(n_layers, n_qubits, 3) * 0.3
    weights.requires_grad_(True)
    opt = torch.optim.Adam([weights], lr=lr)

    # QAE features are already in (-1, +1); NO tanh scaling.
    # Multiply by π inside AngleEmbedding (handled by the circuit).
    # Here we just convert to torch tensor — values used as-is.
    Xv = torch.tensor(X_tr[:, :n_qubits], dtype=torch.float32)
    yv = torch.tensor(y_tr, dtype=torch.float32)

    # 10% validation split
    n_val  = max(1, len(Xv) // 10)
    Xv_tr  = Xv[:-n_val];    yv_tr = yv[:-n_val]
    Xv_val = Xv[-n_val:];    yv_val = yv[-n_val:]

    # Class imbalance: up-weight positive (minority) class
    n_pos = yv_tr.sum().item()
    n_neg = len(yv_tr) - n_pos
    pos_w = n_neg / (n_pos + 1e-9)

    history   = {"train": [], "val": []}
    best_val  = float("inf")
    pat       = 0
    best_w    = None

    for ep in range(epochs):
        accum_grad = torch.zeros_like(weights)
        ep_loss    = 0.0
        for i in range(len(Xv_tr)):
            if weights.grad is not None:
                weights.grad.zero_()
            # Pass feature directly — circuit applies np.pi * x internally
            logit = circuit(Xv_tr[i], weights).float()
            prob  = torch.sigmoid(logit * 3.0)
            w     = pos_w if yv_tr[i] > 0.5 else 1.0
            loss  = w * torch.nn.functional.binary_cross_entropy(
                        prob.unsqueeze(0), yv_tr[i].unsqueeze(0))
            loss.backward()
            accum_grad = accum_grad + weights.grad.detach()
            ep_loss   += loss.item()

        with torch.no_grad():
            weights.grad = accum_grad / len(Xv_tr)
        opt.step()

        # Validation loss
        with torch.no_grad():
            vl = 0.0
            for i in range(len(Xv_val)):
                logit = circuit(Xv_val[i], weights).float()
                prob  = torch.sigmoid(logit * 3.0)
                ww    = pos_w if yv_val[i] > 0.5 else 1.0
                vl   += ww * torch.nn.functional.binary_cross_entropy(
                            prob.unsqueeze(0), yv_val[i].unsqueeze(0)).item()
            vl /= max(1, len(Xv_val))

        tl = ep_loss / len(Xv_tr)
        history["train"].append(float(tl))
        history["val"].append(float(vl))

        if ep % 10 == 0:
            print(f"    [C3-VQC] Epoch {ep:3d}  train={tl:.4f}  val={vl:.4f}")

        if vl < best_val - 1e-5:
            best_val, pat = vl, 0
            best_w = weights.detach().clone()
        else:
            pat += 1
            if pat >= patience:
                print(f"    [C3-VQC] Early stop at epoch {ep+1}"
                      f"  best_val={best_val:.4f}")
                break

    final_w = best_w if best_w is not None else weights.detach()
    return final_w, history


def vqc_predict_from_features(X:        np.ndarray,
                               weights:  "torch.Tensor",
                               n_qubits: int = 6,
                               n_layers: int = 2) -> tuple:
    """
    Run VQC inference on pre-extracted QAE features (Method C3).

    Like vqc_predict() but skips the internal tanh — QAE expectation values
    are already bounded in (-1, +1) and are used directly as angles via
    the circuit's AngleEmbedding: RY(π × x_i).

    Parameters
    ----------
    X        : (N, n_qubits) QAE expectation values  (already ∈ (-1, +1))
    weights  : (n_layers, n_qubits, 3) trained weights from train_vqc_from_features
    n_qubits : int
    n_layers : int

    Returns
    -------
    (probs, preds)
      probs : (N,) float32 class-1 probabilities
      preds : (N,) int32   binary predictions (threshold 0.5)
    """
    circuit = _make_vqc_circuit(n_qubits, n_layers)
    probs   = []
    with torch.no_grad():
        # No tanh — QAE features are already ∈ (-1, +1)
        Xv = torch.tensor(X[:, :n_qubits], dtype=torch.float32)
        for x in Xv:
            logit = circuit(x, weights).float()
            p     = torch.sigmoid(logit * 3.0).item()
            probs.append(p)
    probs = np.array(probs, dtype=np.float32)
    preds = (probs >= 0.5).astype(np.int32)
    return probs, preds

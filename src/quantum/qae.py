"""
src/quantum/qae.py
==================
Hardware-Efficient Quantum Autoencoder (HE-QAE).

Role: FEATURE EXTRACTOR
-------
The QAE compresses the first N_Q PCA components into N_Q quantum
expectation values <Z_i>.  These are concatenated with PCA features
to form a richer 33-dim feature vector for the downstream ensemble.

The QAE is NOT a classifier.

Architecture (6 qubits, 3 layers)
----------------------------------
  Input:  tanh(Z_train[:, :6])   — first 6 PCA dims, scaled to (-1,+1)
  Ansatz per layer l:
    RY(w[l, i]) on each qubit i   — trainable rotations
    CNOT chain: 0->1, 1->2, ..., (N-2)->(N-1)
  Long-range: CZ(0, N-1)
  Re-upload:  RY(x[i]*0.5) on each qubit   (data re-uploading)
  Output: [<Z_0>, <Z_1>, ..., <Z_5>]  ∈ [-1, +1]^6

Loss: mineral-weighted MSE
    L = Σ_i (1 + w_i) ||tanh(z_i[:6]) - q_i||^2

Reference
---------
  Romero et al. (2017) "Quantum autoencoders for efficient compression
  of quantum data." Quantum Sci. Technol. 2, 045001.
  Hardware-Efficient Ansatz: Kandala et al. (2017) Nature 549, 242-246.

Usage
-----
    from src.quantum.qae import train_qae, extract_qae_features
    weights = train_qae(Z_train, mineral_weights_train, CFG)
    qae_tr  = extract_qae_features(Z_train, weights, CFG["n_qubits"])
    qae_ts  = extract_qae_features(Z_test,  weights, CFG["n_qubits"])
"""

import numpy as np
import torch
import pennylane as qml


# ---------------------------------------------------------------------------
# HE-QAE circuit (6 qubits, 3 layers)
# ---------------------------------------------------------------------------

def _make_hea_qae_circuit(n_qubits: int, n_layers: int):
    """
    Build and return a PennyLane QNode for the HE-QAE circuit.

    x       : (n_qubits,)       data encoding angles  [tanh-scaled PCA dims]
    weights : (n_layers, n_qubits) trainable rotation angles

    Returns: list of n_qubits expectation values <Z_i> ∈ [-1, +1]
    """
    dev = qml.device("default.qubit", wires=n_qubits)

    @qml.qnode(dev, interface="torch", diff_method="adjoint")
    def hea_qae(x, weights):
        # Data encoding — RY angle embedding
        for i in range(n_qubits):
            qml.RY(x[i], wires=i)

        # Entangling layers
        for l in range(n_layers):
            for i in range(n_qubits - 1):
                qml.RY(weights[l, i], wires=i)
            qml.RY(weights[l, n_qubits - 1], wires=n_qubits - 1)
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])

        # Long-range entanglement
        qml.CZ(wires=[0, n_qubits - 1])

        # Data re-uploading (improves expressibility)
        for i in range(n_qubits):
            qml.RY(x[i] * 0.5, wires=i)

        return [qml.expval(qml.PauliZ(i)) for i in range(n_qubits)]

    return hea_qae


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_qae(Z_tr:  np.ndarray,
              mw:    np.ndarray,
              n_qubits: int = 6,
              n_layers: int = 3,
              epochs:   int = 25,
              lr:       float = 0.05,
              patience: int = 8,
              seed:     int = 42) -> torch.Tensor:
    """
    Train QAE weights on training set with mineral-weighted MSE loss.

    PCA features are tanh-scaled to (-1, +1) before quantum encoding so
    that RY angles are well-conditioned and output expectation values
    (also in [-1,+1]) can be compared directly via MSE.

    Parameters
    ----------
    Z_tr     : (N, >=n_qubits) PCA features  (use first n_qubits dims)
    mw       : (N,)  mineral weights  max(LiCI_norm, VMI_norm)
    n_qubits : int   qubits = feature compression dimension (= 6)
    n_layers : int   entangling layers  (= 3)
    epochs   : int   max training epochs
    lr       : float Adam learning rate
    patience : int   early stopping patience

    Returns
    -------
    (best_weights, history)  where best_weights is torch.Tensor shape
    (n_layers, n_qubits) and history = {"train": [...], "val": [...]}.
    """
    torch.manual_seed(seed)
    circuit = _make_hea_qae_circuit(n_qubits, n_layers)

    weights = torch.randn(n_layers, n_qubits, requires_grad=True)
    opt     = torch.optim.Adam([weights], lr=lr)

    n_val   = max(1, len(Z_tr) // 10)
    # tanh-scale first n_qubits PCA dims to (-1, +1)
    Zq_all  = torch.tanh(torch.tensor(Z_tr[:, :n_qubits], dtype=torch.float32))
    mw_all  = torch.tensor(mw, dtype=torch.float32)
    Zq_tr   = Zq_all[:-n_val];    mw_tr = mw_all[:-n_val]
    Zq_val  = Zq_all[-n_val:];    mw_val = mw_all[-n_val:]

    best_val, pat, best_w = float("inf"), 0, None
    history = {"train": [], "val": []}

    for ep in range(epochs):
        # Per-sample gradient accumulation
        accum_grad = torch.zeros_like(weights)
        ep_loss    = 0.0
        for idx in range(len(Zq_tr)):
            if weights.grad is not None:
                weights.grad.zero_()
            q_out      = torch.stack(circuit(Zq_tr[idx], weights))
            recon_loss = torch.mean((Zq_tr[idx] - q_out) ** 2) * (1.0 + mw_tr[idx])
            recon_loss.backward()
            accum_grad = accum_grad + weights.grad.detach()
            ep_loss   += recon_loss.item()
        with torch.no_grad():
            weights.grad = accum_grad / len(Zq_tr)
        opt.step()

        # Validation loss
        with torch.no_grad():
            vl = 0.0
            for idx in range(len(Zq_val)):
                qo = torch.stack(circuit(Zq_val[idx], weights))
                vl += (torch.mean((Zq_val[idx] - qo) ** 2)
                       * (1.0 + mw_val[idx])).item()
            vl /= max(1, len(Zq_val))

        tl_mean = ep_loss / max(1, len(Zq_tr))
        history["train"].append(tl_mean)
        history["val"].append(vl)

        if ep % 5 == 0:
            print(f"    Epoch {ep:3d}  train={tl_mean:.4f}  val={vl:.4f}")
        if vl < best_val - 1e-5:
            best_val, pat = vl, 0
            best_w = weights.detach().clone()
        else:
            pat += 1
            if pat >= patience:
                print(f"    QAE early stop at epoch {ep+1}  best_val={best_val:.4f}")
                break

    final_w = best_w if best_w is not None else weights.detach()
    return final_w, history


# ---------------------------------------------------------------------------
# Feature extraction (inference)
# ---------------------------------------------------------------------------

def extract_qae_features(Z:        np.ndarray,
                         weights:  torch.Tensor,
                         n_qubits: int = 6,
                         n_layers: int = 3) -> np.ndarray:
    """
    Run HE-QAE encoder on all samples and return expectation values.

    Parameters
    ----------
    Z        : (N, >=n_qubits) PCA features
    weights  : (n_layers, n_qubits) trained QAE weights

    Returns
    -------
    (N, n_qubits) float32 array of quantum expectation values
    """
    circuit = _make_hea_qae_circuit(n_qubits, n_layers)
    feats   = []
    with torch.no_grad():
        for z in torch.tanh(torch.tensor(Z[:, :n_qubits], dtype=torch.float32)):
            q = torch.stack(circuit(z, weights))
            feats.append(q.numpy())
    return np.array(feats, dtype=np.float32)

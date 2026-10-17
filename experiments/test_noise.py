"""Quick sanity check for the noise module."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np
from src.quantum.noise import (
    make_noisy_qae_circuit,
    make_noisy_qkernel_circuit,
    make_noisy_qaa_circuit,
)

print("=== Testing Noisy QAE Circuit ===")
circ = make_noisy_qae_circuit(6, 3, p_depol=0.01)
x = torch.tanh(torch.randn(6))
w = torch.randn(3, 6)
out = [float(o) for o in circ(x, w)]
assert all(-1.01 <= o <= 1.01 for o in out), f"Invalid outputs: {out}"
print(f"  Output: {[f'{o:.4f}' for o in out]}")
print("  PASSED")

print("\n=== Testing Noisy QSVM Kernel ===")
circ_k = make_noisy_qkernel_circuit(4, p_depol=0.01)
x1 = np.tanh(np.random.randn(4))
x2 = np.tanh(np.random.randn(4))
probs = circ_k(x1, x2)
k_val = float(probs[0])
print(f"  Kernel value: {k_val:.6f}")
assert 0 <= k_val <= 1, f"Invalid kernel: {k_val}"
print("  PASSED")

print("\n=== Testing Noisy QAA Circuit ===")
circ_q, n_p, tw = make_noisy_qaa_circuit(6, 2, 3, p_depol=0.01)
print(f"  n_params={n_p}, trash_wires={tw}")
w_q = np.random.randn(n_p) * 0.1
x_q = np.tanh(np.random.randn(6))
probs_q = circ_q(x_q, w_q)
score = float(1.0 - probs_q[0])
print(f"  Anomaly score: {score:.6f}")
assert 0 <= score <= 1, f"Invalid score: {score}"
print("  PASSED")

print("\n=== Testing Shot Noise (QAE with 1024 shots) ===")
circ_shots = make_noisy_qae_circuit(4, 2, p_depol=0.0, shots=1024)
xs = np.tanh(np.random.randn(4))
ws = np.random.randn(2, 4)
out_s = [float(o) for o in circ_shots(xs, ws)]
print(f"  Shot output: {[f'{o:.4f}' for o in out_s]}")
print("  PASSED")

print("\n" + "=" * 40)
print("ALL NOISE TESTS PASSED")
print("=" * 40)

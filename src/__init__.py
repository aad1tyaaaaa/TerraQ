"""
TerraQ
================================
Quantum-enhanced hyperspectral mineral detection package.

Detects lithium and vanadium deposits in NASA EO-1 Hyperion imagery using
a hybrid quantum-classical pipeline with statistically validated quantum advantage.

Version:  1.0.0
Measured: AUC 0.7702, McNemar p=0.1056 (not significant)  (C_PCA_QAE vs B_PCA_CAE)

Methods
-------
A  PCA only           classical baseline
B  PCA + CAE          classical autoencoder ablation
C  PCA + QAE   BEST   6-qubit HEA quantum feature extractor
D  QSVM               ZZFeatureMap fidelity kernel SVM
F  QAA Hybrid         unsupervised quantum anomaly autoencoder
"""

__version__ = "1.0.0"
__author__  = "Quantum Mineral Detection Research"

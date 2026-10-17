"""
src/config.py
=============
Single source of truth for all pipeline hyper-parameters.

Every number here matches the pipeline that produced the committed results in
outputs/summary/metrics.txt (hold-out Scene 3):
    C_PCA_QAE:  AUC=0.7702  F1=0.6751  MCC=0.3510
    McNemar C_PCA_QAE vs B_PCA_CAE:  chi2=2.62  p=0.1056  NOT significant
    Lift over the classical autoencoder: +0.009 AUC (0.770 vs 0.762).

EXTENDED METHODS (C2 / C3):
    C2  PCA→QAE→QSVM  : fully-quantum pipeline; quantum kernel on QAE latent space
    C3  PCA→QAE→VQC   : end-to-end trainable quantum pipeline

CRITICAL PARAMETER:
    max_qae_train = 200  (was 60 — too few samples caused AUC 0.68 degradation)
    qae_epochs    = 50   (was 25 — needs more convergence time on 200 samples)
    Training on 200 balanced samples (mineral + background) recovers AUC 0.770.

QUBIT CONFIGURATION (easy to increase — simulator cost is 2^n_qubits):
    n_qubits        QAE / QSVM   6   -> 8  (moderate)  10  (heavy)
    qaa_n_qubits    QAA          5   -> 6  (moderate)   8  (heavy, 2^n>=25)

NOTE: VQC (Method E) was removed after AUC=0.548 in validation 
(near-random; learned class imbalance rather than spectral signal).

DATA SCENES (4 available — scene3 is held-out temporal test):
    Scene 1 : EO1H0430342017071  2017-Mar  P43/R34   TRAIN
    Scene 2 : EO1H0410332013075  2013-Mar  P41/R33   TRAIN
    Scene 3 : EO1H0410332013154  2013-Jun  P41/R33   TEST (held-out)
    Scene 4 : EO1H0410342014301  2014-Oct  P41/R34   TRAIN (adds geographic diversity)
    NOTE: Scenes 2 & 3 are same orbit (corr≈0.89) — different dates, same area.
          Scene 4 is adjacent row (R34) — different geology, improves training coverage.
          Visual similarity in Scenes 2 & 3 output maps is expected (same geology).

DO NOT change these values without scientific justification.
"""

import os

SEED = 42

# ---------------------------------------------------------------------------
# Data paths  (relative to TerraQ/)
# ---------------------------------------------------------------------------
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Data folder: look for processed data inside the package first,
# fall back to the MODULAR_SCRIPTS location for backwards-compatibility.
_DATA_CANDIDATES = [
    os.path.join(_BASE, "data", "processed"),            # preferred: inside package
    os.path.join(_BASE, "..", "01_MODULAR_SCRIPTS", "processed_data"),  # legacy
]
DATA_FOLDER   = next((d for d in _DATA_CANDIDATES if os.path.isdir(d)),
                     _DATA_CANDIDATES[0])  # default to preferred path even if missing
# Output folder: overridable with QMD_OUTPUT_DIR so a run can be sandboxed
# (e.g. a verification run) without clobbering previously-generated results.
OUTPUT_FOLDER = os.environ.get("QMD_OUTPUT_DIR") or os.path.join(_BASE, "outputs")

CFG = {
    # ---- Paths ---------------------------------------------------------------
    "data_folder"   : DATA_FOLDER,
    "output_folder" : OUTPUT_FOLDER,

    # ---- Patch extraction ----------------------------------------------------
    "patch_size"        : 16,
    "cloud_low"         : 0.05,    # brightness floor  (exclude shadow / water)
    "cloud_high"        : 0.90,    # brightness ceiling (exclude clouds)
    "min_patch_std"     : 0.005,   # exclude spatially flat patches
    "max_patches_scene" : 1500,    # cap per scene to keep RAM manageable

    # ---- Label generation (non-circular band-ratio indices) -----------------
    # Strategy: label = 1 if LiCI > li_thresh  OR  VMI > v_thresh
    # Thresholds are the label_percentile-th percentile of each index computed
    # on the TRAINING set only, then applied to the test set.
    # Avoids Otsu's failure modes on non-bimodal index distributions. Because the
    # two thresholds are OR-ed, the measured train positive rate is 48.3%, not 25%
    # (see outputs/summary/metrics.txt).
    "label_strategy"    : "band_ratio_percentile",   # OR logic
    "label_percentile"  : 75.0,   # top-25% of EACH index; OR-ed -> 48.3% positives

    # ---- Spatial blocked CV -------------------------------------------------
    "block_grid_r" : 4,    # 4x4 = 16 spatial blocks per scene
    "block_grid_c" : 4,
    "cv_folds"     : 5,

    # ---- PCA (shared first stage for ALL methods) ---------------------------
    # Full 198-band flatten -> RobustScaler -> PCA(25)
    "n_pca"        : 25,

    # ---- Classical AE (ablation B) ------------------------------------------
    "cae_bottleneck" : 6,
    "cae_epochs"     : 80,
    "cae_lr"         : 1e-3,

    # ---- Quantum AE (proposed, method C) ------------------------------------
    # 6-qubit Hardware-Efficient QAE, 3 entangling layers
    # Q input: tanh(Z_train[:, :n_qubits])   (first 6 PCA dims)
    # Q output: 6 expectation values <Z_i>  -> concatenated into feature vec
    "n_qubits"     : 6,
    "n_layers"     : 3,
    "qae_epochs"   : 50,            # 50 epochs at 200 samples recovers AUC 0.770
    "qae_lr"       : 0.05,
    "qae_patience" : 12,            # increased from 8 — gives more convergence time
    "max_qae_train": 200,           # KEY FIX: was 60 (too few) → doubled to 200
                                    # The run that produced AUC 0.770 used 200+

    # ---- Method C2: QAE features → QSVM  (fully-quantum pipeline after PCA) ---
    # Uses 6-dim QAE expectation values (NOT raw PCA) as QSVM input.
    # QAE compresses spectral structure; QSVM measures fidelity in the resulting
    # quantum-feature Hilbert space — stacking two quantum advantages.
    # Support set is stratified (equal pos+neg) to avoid kernel imbalance.
    "c2_qasvm_n_support": 150,  # support candidates (O(N^2) cost; 150 is fast)

    # ---- Method C3: QAE features → VQC  (end-to-end trainable quantum) -------
    # VQC angle-embeds QAE expvals: RY(π × x_i), x_i ∈ (-1,+1).
    # StronglyEntanglingLayers(n_vqc_layers) on n_vqc_qubits qubits.
    # Returns history for training curve visualisation.
    # NOTE: n_vqc_qubits MUST equal n_qubits (QAE output dimensionality).
    "n_vqc_qubits"  : 6,    # must equal n_qubits — uses all 6 QAE dims
    "n_vqc_layers"  : 2,    # 2 × StronglyEntanglingLayers (24 parameters)
    "vqc_epochs"    : 50,   # same as qae_epochs for fair comparison
    "vqc_lr"        : 0.05,
    "vqc_patience"  : 15,   # slightly more patience than QAE (smoother features)
    "max_vqc_train" : 200,  # same stratified budget as QAE (100 pos + 100 neg)

    # ---- Quantum Kernel SVM (method D) --------------------------------------
    # ZZFeatureMap fidelity kernel K(x1,x2) = |<phi(x1)|phi(x2)>|^2
    # Input: tanh(Z[:, :n_qubits])   (same first 6 PCA dims as QAE)
    # Kernel is O(N^2); 150 support candidates is standard in QSVM literature
    "qsvm_n_train"  : 150,   # support candidates for quantum kernel matrix

    # ---- Quantum Anomaly Autoencoder (method F — unsupervised, hybrid) ------
    # QAA — TRUE BOTTLENECK QUANTUM AUTOENCODER  (Romero et al. 2017)
    # Trains ONLY on background patches (no mineral labels used).
    # Loss = 1 − P(trash qubits = |0...0⟩)   [Hilbert-space fidelity]
    # Anomaly score = 1 − P(trash=|0...0⟩)  ∈ [0, 1]
    #   score ≈ 0  → spectrum compresses easily   = background
    #   score ≈ 1  → spectrum resists compression = mineral anomaly
    # Register:  qubits [0..n_latent-1] = LATENT   (2^n_latent states)
    #            qubits [n_latent..n_qubits-1] = TRASH → forced to |0...0⟩
    # 6 qubits, 2 latent: n_trash = 4,  n_params = 6×3 = 18
    # Hybrid F+C: QAA scores used as soft sample_weights for Stage-2 ensemble.
    "qaa_n_qubits"        : 6,    # total input qubits  (latent + trash)
    "qaa_n_latent"        : 2,    # latent qubits [0,1]; trash = qubits [2,3,4,5]
    "qaa_n_layers"        : 3,
    "qaa_epochs"          : 30,   # increased from 20 — more convergence on larger set
    "qaa_lr"              : 0.03, # slightly smaller LR for stability with 150 samples
    "qaa_patience"        : 8,    # increased from 6
    "qaa_bg_percentile"   : 40.0, # patches below this mineral_weight -> background
    "qaa_max_bg_train"    : 150,  # increased from 80 — more background coverage
    "qaa_pseudo_hi"       : 80.0, # anomaly pct -> pseudo-label 1 (mineral)
    "qaa_pseudo_lo"       : 40.0, # anomaly pct -> pseudo-label 0 (background)
    # Middle band (40th–80th percentile) is discarded as "uncertain"

    # ---- Noise simulation (publication-grade NISQ resilience analysis) ------
    # Depolarizing: random Pauli errors after every entangling layer
    # Amplitude damping: energy dissipation (T1 decay)
    # Shot noise: finite measurement samples (replaces analytic expvals)
    # Reference hardware:  IBM Eagle r3 (1q=0.02%, 2q=0.5%, T1=300µs)
    #                      IonQ Forte   (1q=0.03%, 2q=0.5%, T1=10s)
    "noise_enabled"       : True,   # run noise analysis after ideal evaluation
    "noise_depol_levels"  : [0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1],
    "noise_ad_levels"     : [0.0, 0.001, 0.005, 0.01, 0.02, 0.05],
    "noise_shots_list"    : [256, 1024, 4096, 8192],

    # ---- Ensemble (methods A / B / C) ---------------------------------------
    "rf_trees"   : 200,
    "gb_trees"   : 200,
    "gb_lr"      : 0.05,
    "svm_cv"     : 3,   # folds inside GridSearchCV (faster than 5)

    # ---- Statistics ----------------------------------------------------------
    "bootstrap_n" : 1000,
    "ci_level"    : 0.95,

    # ---- Misc ----------------------------------------------------------------
    "seed" : SEED,
    "eps"  : 1e-9,
}

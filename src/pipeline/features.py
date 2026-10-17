"""
src/pipeline/features.py
========================
Physics-based feature engineering for the mineral detection pipeline.

Responsibilities
----------------
1.  Wavelength grid + band lookup (HYPERION_WL, BI)
2.  Non-circular label generation via band-ratio absorption-depth indices
    - LiCI : depth of 2200 nm Al-OH / Li-OH trough
    - VMI  : depth of 2265 nm V-OH trough (roscoelite)
    - OR logic at the 75th-percentile threshold on the TRAINING SET
3.  Non-overlapping patch extraction with cloud / flatness quality filters
4.  Full 198-band PCA (RobustScaler -> PCA(25))  — shared first stage for all methods
5.  USGS spectral correlation auxiliary features (not used for labels -> no circularity)
6.  Mineral weighting: max(LiCI_norm, VMI_norm) for loss functions
7.  Spatial block IDs for blocked cross-validation

Note: QSVM and VQC are CLASSIFIERS that take PCA features as input.
      QAE    is a FEATURE EXTRACTOR  that takes PCA features as input.
      None of them are involved in label generation.

References
----------
  Clark et al. (2007) USGS Spectral Library v6.
  Van der Meer (2004) Int J Remote Sens 25(1), 55-65.
  Havlicek et al. (2019) Nature 567, 209-212.
"""

import os
import numpy as np
from sklearn.preprocessing import RobustScaler
from sklearn.decomposition import PCA


# ---------------------------------------------------------------------------
# Hyperion wavelength grid  (198 bands, 427–2395 nm)
# ---------------------------------------------------------------------------

def load_wavelengths(data_folder: str) -> np.ndarray:
    """Load or synthesize the 198-band Hyperion wavelength grid (nm)."""
    path = os.path.join(data_folder, "hyperion_wavelengths.npy")
    if os.path.exists(path):
        return np.load(path)
    wl = np.concatenate([
        np.linspace(427.0,  925.0,  50),
        np.linspace(932.0, 2395.0, 148),
    ])
    np.save(path, wl)
    return wl


def make_band_indices(wl: np.ndarray) -> dict:
    """Return a dict of physically meaningful band indices for mineral detection."""
    def find(nm):
        return int(np.argmin(np.abs(wl - nm)))
    return {
        "B680" : find(680),    # goethite / chlorophyll reference
        "B850" : find(850),    # ferric iron shoulder
        "B1700": find(1700),   # SWIR reference shoulder
        "B2135": find(2135),   # left shoulder of 2200 nm Al-OH feature
        "B2200": find(2200),   # Al-OH / Li-OH absorption  (Li-clay core)
        "B2265": find(2265),   # V-OH absorption (roscoelite core)
        "B2350": find(2350),   # second Al-OH feature / right shoulder
    }


# ---------------------------------------------------------------------------
# Mineral absorption-depth indices  (NON-CIRCULAR labels)
# ---------------------------------------------------------------------------

def mineral_indices_from_cube(cube: np.ndarray, BI: dict, eps: float = 1e-9) -> dict:
    """
    Compute per-pixel band-ratio absorption-depth indices.

    LiCI (Lithium Clay Index):
        baseline(2200) = [R(2135) + R(2350)] / 2
        LiCI = baseline(2200) - R(2200)          (positive = absorption)

    VMI (Vanadium Mineral Index):
        t = (2265 - 2200) / (2350 - 2200) ≈ 0.433
        baseline(2265) = R(2200) + t * [R(2350) - R(2200)]
        VMI = baseline(2265) - R(2265)            (positive = absorption)

    FII (Ferric Iron Index):
        FII = R(850) / (R(680) + eps)

    Parameters
    ----------
    cube : (H, W, B) float32 normalised reflectance
    BI   : band index dict from make_band_indices()

    Returns
    -------
    dict with keys 'LiCI', 'VMI', 'FII', each shape (H, W)
    """
    R = cube
    baseline_2200 = (R[:, :, BI["B2135"]] + R[:, :, BI["B2350"]]) / 2.0
    LiCI = baseline_2200 - R[:, :, BI["B2200"]]

    t_v = (2265 - 2200) / (2350 - 2200)
    baseline_2265 = (R[:, :, BI["B2200"]]
                     + t_v * (R[:, :, BI["B2350"]] - R[:, :, BI["B2200"]]))
    VMI  = baseline_2265 - R[:, :, BI["B2265"]]

    FII  = R[:, :, BI["B850"]] / (R[:, :, BI["B680"]] + eps)

    return {"LiCI": LiCI, "VMI": VMI, "FII": FII}


# ---------------------------------------------------------------------------
# Patch extraction
# ---------------------------------------------------------------------------

def extract_patches(cube: np.ndarray,
                    BI: dict,
                    patch_size: int,
                    cloud_lo: float,
                    cloud_hi: float,
                    min_std: float,
                    max_patches: int,
                    block_grid_r: int,
                    block_grid_c: int,
                    eps: float = 1e-9):
    """
    Extract non-overlapping (patch_size × patch_size) patches from cube.

    Quality filters:
      - mean brightness in [cloud_lo, cloud_hi]   (exclude cloud / shadow)
      - patch std > min_std                        (exclude spectrally flat)
      - all finite values

    Returns
    -------
    patches   : (N, P, P, B) float32
    coords    : list of (row, col) top-left corners
    li_vals   : (N,) mean LiCI per patch
    v_vals    : (N,) mean VMI  per patch
    blk_ids   : (N,) int  spatial block index  [for blocked CV]
    """
    H, W, B = cube.shape
    idx_map  = mineral_indices_from_cube(cube, BI, eps)
    brightness = np.nanmean(cube, axis=2)

    block_h = H / block_grid_r
    block_w = W / block_grid_c

    patches, coords, li_vals, v_vals, blk_ids = [], [], [], [], []

    for i in range(0, H - patch_size, patch_size):
        for j in range(0, W - patch_size, patch_size):
            if len(patches) >= max_patches:
                break
            bright = np.nanmean(brightness[i:i+patch_size, j:j+patch_size])
            if not (cloud_lo < bright < cloud_hi):
                continue
            p = cube[i:i+patch_size, j:j+patch_size, :]
            if not np.isfinite(p).all():
                continue
            if p.std() < min_std:
                continue
            li_px = idx_map["LiCI"][i:i+patch_size, j:j+patch_size]
            v_px  = idx_map["VMI"] [i:i+patch_size, j:j+patch_size]
            patches.append(p)
            coords.append((i, j))
            li_vals.append(float(np.nanmean(li_px)))
            v_vals.append(float(np.nanmean(v_px)))
            blk_r = int(min(block_grid_r - 1, i / block_h))
            blk_c = int(min(block_grid_c - 1, j / block_w))
            blk_ids.append(blk_r * block_grid_c + blk_c)
        if len(patches) >= max_patches:
            break

    if len(patches) == 0:
        P, Bands = patch_size, B
        return (np.zeros((1, P, P, Bands), dtype=np.float32),
                [(0, 0)],
                np.array([0.0], dtype=np.float32),
                np.array([0.0], dtype=np.float32),
                np.array([0],   dtype=np.int32))

    return (np.array(patches, dtype=np.float32),
            coords,
            np.array(li_vals, dtype=np.float32),
            np.array(v_vals,  dtype=np.float32),
            np.array(blk_ids, dtype=np.int32))


# ---------------------------------------------------------------------------
# Label generation  (OR logic, 75th-percentile threshold)
# ---------------------------------------------------------------------------

def make_labels_percentile(li_scores: np.ndarray,
                           v_scores:  np.ndarray,
                           label_percentile: float = 75.0,
                           li_thresh: float = None,
                           v_thresh:  float = None) -> tuple:
    """
    Generate binary mineral / non-mineral labels.

    Strategy
    --------
    label = 1  if  LiCI > li_thresh  OR  VMI > v_thresh

    Thresholds are the label_percentile-th percentile of each index,
    computed ONLY on the training set, then applied to test set.

    This gives ~25% positive rate on the training set.
    Labels are derived from band-ratio indices (LiCI, VMI), which are
    NEVER used as classifier features -> no circular relationship.

    Parameters
    ----------
    li_thresh, v_thresh : float or None
        If None (training call) : thresholds computed from this dataset.
        If float (test call)    : apply pre-computed training thresholds.

    Returns
    -------
    (labels, li_thresh, v_thresh)
    """
    if li_thresh is None:   # training set call
        li_thresh = float(np.percentile(li_scores, label_percentile))
        v_thresh  = float(np.percentile(v_scores,  label_percentile))
        mode = "Computed"
    else:
        mode = "Applied"

    # OR logic: positive if EITHER index exceeds its threshold
    labels = ((li_scores > li_thresh) | (v_scores > v_thresh)).astype(np.int32)

    print(f"  [{mode}] li_thresh={li_thresh:.6f}  v_thresh={v_thresh:.6f}")
    print(f"  Positive labels: {labels.sum()} / {len(labels)}"
          f"  ({100 * labels.mean():.1f}%)")
    return labels, li_thresh, v_thresh


# ---------------------------------------------------------------------------
# PCA  (full 198-band flatten -> RobustScaler -> PCA(25))
# ---------------------------------------------------------------------------

def fit_pca(train_patches: np.ndarray,
            n_pca: int,
            seed: int = 42):
    """
    Fit RobustScaler + PCA on training patches.

    Input:  (N, P, P, B) float32 patches   (full 198-band spatial flatten)
    Output: (scaler, pca, Z_train)
      - Z_train: (N, n_pca) float32 PCA scores
    """
    N = len(train_patches)
    # Full 198-band flatten: 16x16x198 = 50,688 dimensions
    X_raw = train_patches.reshape(N, -1).astype(np.float64)
    scaler = RobustScaler(copy=False)
    X_sc   = scaler.fit_transform(X_raw)
    pca    = PCA(n_components=n_pca, random_state=seed)
    Z      = pca.fit_transform(X_sc).astype(np.float32)
    del X_raw, X_sc
    var = pca.explained_variance_ratio_.sum()
    print(f"  Explained variance ({n_pca} PCs): {var:.3f}")
    print(f"  Z_train shape: {Z.shape}")
    return scaler, pca, Z


def apply_pca(test_patches: np.ndarray,
              scaler,
              pca) -> np.ndarray:
    """
    Apply fitted RobustScaler + PCA to test patches.

    Returns (N_test, n_pca) float32.
    """
    N = len(test_patches)
    X_raw = test_patches.reshape(N, -1).astype(np.float64)
    X_sc  = scaler.transform(X_raw)
    Z     = pca.transform(X_sc).astype(np.float32)
    del X_raw, X_sc
    print(f"  Z_test  shape: {Z.shape}")
    return Z


# ---------------------------------------------------------------------------
# USGS spectral correlation auxiliary features
# (used as classifier features ONLY — never for labels -> no circularity)
# ---------------------------------------------------------------------------

def usgs_corr_feature(patches: np.ndarray,
                      usgs_ref: np.ndarray) -> np.ndarray:
    """
    Pearson correlation between the mean spectrum of each patch and a
    USGS reference spectrum.

    Returns (N, 1) float32 array with values in [-1, 1].
    """
    scores = []
    for p in patches:
        spec = np.nanmean(p, axis=(0, 1))
        c    = float(np.corrcoef(spec, usgs_ref)[0, 1])
        scores.append(0.0 if np.isnan(c) else c)
    return np.array(scores, dtype=np.float32).reshape(-1, 1)


# ---------------------------------------------------------------------------
# Mineral weights for loss functions
# (min-max of raw indices; NOT used for labels)
# ---------------------------------------------------------------------------

def minmax_norm(x: np.ndarray,
                ref: np.ndarray = None,
                eps: float = 1e-9) -> np.ndarray:
    """Min-max normalise x to [0, 1].  ref = reference array (use train set)."""
    if ref is None:
        ref = x
    lo, hi = ref.min(), ref.max()
    return np.clip((x - lo) / (hi - lo + eps), 0.0, 1.0)


def make_mineral_weights(li_scores: np.ndarray,
                         v_scores:  np.ndarray,
                         li_ref: np.ndarray = None,
                         v_ref:  np.ndarray = None) -> np.ndarray:
    """
    Compute per-patch mineral salience weight = max(LiCI_norm, VMI_norm).

    These weights are used inside QAE and CAE loss functions to focus
    reconstruction effort on spectrally interesting patches.
    They are NOT used for labels.
    """
    li_n = minmax_norm(li_scores, ref=li_ref).astype(np.float32)
    v_n  = minmax_norm(v_scores,  ref=v_ref ).astype(np.float32)
    return np.maximum(li_n, v_n)

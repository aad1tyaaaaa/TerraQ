"""
src/pipeline/ensemble.py
========================
Classical Autoencoder (ablation B) and ensemble classifier builder.

The ensemble classifier (SVM + RF + GB soft-vote) is the final decision
maker for methods A, B, and C.  It operates on 33-dimensional feature
vectors:  [PCA(25) | AE_bottleneck(6) | USGS_corr(2)]

Note: QSVM and VQC are NOT part of this ensemble — they are standalone
      classifiers (methods D and E respectively) that feed directly from PCA.
"""

import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.ensemble import (RandomForestClassifier,
                               GradientBoostingClassifier,
                               VotingClassifier)
from sklearn.model_selection import GridSearchCV


# ---------------------------------------------------------------------------
# Classical Autoencoder  (ablation method B)
# ---------------------------------------------------------------------------

class ClassicalAE(nn.Module):
    """
    Symmetric bottleneck autoencoder:  25 -> mid -> 6 -> mid -> 25

    Trained with mineral-weighted MSE reconstruction loss.
    The 6-dimensional encoder output is the feature vector for ablation B.
    """

    def __init__(self, in_dim: int, bottleneck: int):
        super().__init__()
        mid = max(bottleneck + 4, 12)
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, mid),
            nn.LeakyReLU(0.1),
            nn.Linear(mid, bottleneck),
        )
        self.decoder = nn.Sequential(
            nn.Linear(bottleneck, mid),
            nn.LeakyReLU(0.1),
            nn.Linear(mid, in_dim),
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z), z

    def encode(self, x):
        return self.encoder(x)


def train_classical_ae(Z_tr: np.ndarray,
                       mw:   np.ndarray,
                       bottleneck: int = 6,
                       epochs:     int = 80,
                       lr:         float = 1e-3,
                       patience:   int = 20,
                       seed:       int = 42):
    """
    Train ClassicalAE with mineral-weighted MSE + early stopping.

    Returns
    -------
    (model, history)  where history = {"train": [...], "val": [...]}
    """
    torch.manual_seed(seed)
    model = ClassicalAE(Z_tr.shape[1], bottleneck)
    opt   = torch.optim.Adam(model.parameters(), lr=lr)
    Zt    = torch.from_numpy(Z_tr.astype(np.float32))
    mwt   = torch.from_numpy(mw .astype(np.float32))

    n_val  = max(1, len(Zt) // 10)
    Zt_tr  = Zt[:-n_val];    mwt_tr = mwt[:-n_val]
    Zt_val = Zt[-n_val:];    mwt_val = mwt[-n_val:]

    best_val, pat_cnt, best_state = float("inf"), 0, None
    history = {"train": [], "val": []}

    for ep in range(epochs):
        model.train()
        opt.zero_grad()
        recon, _ = model(Zt_tr)
        w_factor = 1.0 + mwt_tr.unsqueeze(1)
        loss = (w_factor * (Zt_tr - recon) ** 2).mean()
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            rv, _ = model(Zt_val)
            w_val = 1.0 + mwt_val.unsqueeze(1)
            vl    = (w_val * (Zt_val - rv) ** 2).mean().item()
            tl    = loss.item()
        history["train"].append(tl)
        history["val"].append(vl)

        if vl < best_val - 1e-5:
            best_val, pat_cnt = vl, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            pat_cnt += 1
            if pat_cnt >= patience:
                print(f"    CAE early stop at epoch {ep+1}  val_loss={best_val:.4f}")
                break

    if best_state:
        model.load_state_dict(best_state)
    return model, history


def extract_cae_features(cae_model: ClassicalAE,
                         Z_train: np.ndarray,
                         Z_test:  np.ndarray) -> tuple:
    """
    Encode train/test PCA features through CAE bottleneck.

    Returns
    -------
    (cae_feats_train_sc, cae_feats_test_sc, cae_scaler)
    Both arrays are (N, bottleneck) StandardScaler-normalized float32.
    """
    cae_model.eval()
    with torch.no_grad():
        f_tr = cae_model.encode(torch.from_numpy(Z_train.astype(np.float32))).numpy()
        f_ts = cae_model.encode(torch.from_numpy(Z_test .astype(np.float32))).numpy()
    scaler = StandardScaler()
    f_tr_sc = scaler.fit_transform(f_tr).astype(np.float32)
    f_ts_sc = scaler.transform(f_ts).astype(np.float32)
    print(f"  CAE features: train={f_tr_sc.shape}  test={f_ts_sc.shape}")
    return f_tr_sc, f_ts_sc, scaler


# ---------------------------------------------------------------------------
# Ensemble Classifier  (methods A, B, C)
# ---------------------------------------------------------------------------

def build_ensemble(X_tr: np.ndarray,
                   y_tr: np.ndarray,
                   rf_trees:  int   = 200,
                   gb_trees:  int   = 200,
                   gb_lr:     float = 0.05,
                   svm_cv:    int   = 3,
                   seed:      int   = 42):
    """
    Build and fit a soft-voting ensemble:  SVM (GridSearchCV) + RF + GB.

    The ensemble serves as the final classifier for feature sets A, B, C.
    It does NOT involve any quantum component.

    Parameters
    ----------
    X_tr     : (N, D) feature matrix  (D = 25, or 33 for B/C)
    y_tr     : (N,)   binary labels
    rf_trees : int    number of RF estimators
    gb_trees : int    number of GB estimators
    gb_lr    : float  GB learning rate
    svm_cv   : int    inner CV folds for SVM grid search
    seed     : int    random seed

    Returns
    -------
    Fitted VotingClassifier
    """
    # --- SVM with grid search (RBF kernel, class_weight=balanced) ----------
    svm_base = SVC(kernel="rbf", probability=True,
                   class_weight="balanced", random_state=seed)
    gs = GridSearchCV(
        svm_base,
        {"C": [0.1, 1.0, 10.0], "gamma": ["scale", 0.1]},
        cv=svm_cv, scoring="f1", n_jobs=-1, verbose=0,
    )
    gs.fit(X_tr, y_tr)
    svm_clf = gs.best_estimator_
    print(f"    SVM best: C={gs.best_params_['C']}, "
          f"gamma={gs.best_params_['gamma']}")

    # --- Random Forest  (class_weight=balanced) ----------------------------
    rf_clf = RandomForestClassifier(
        n_estimators=rf_trees, max_depth=15,
        min_samples_split=10,  class_weight="balanced",
        random_state=seed, n_jobs=-1,
    )
    rf_clf.fit(X_tr, y_tr)

    # --- Gradient Boosting  (no native class_weight; balanced via subsample) -
    gb_clf = GradientBoostingClassifier(
        n_estimators=gb_trees, max_depth=5,
        learning_rate=gb_lr, random_state=seed,
    )
    gb_clf.fit(X_tr, y_tr)

    # --- Soft-voting ensemble ----------------------------------------------
    vc = VotingClassifier(
        [("svm", svm_clf), ("rf", rf_clf), ("gb", gb_clf)],
        voting="soft",
    )
    vc.fit(X_tr, y_tr)
    return vc

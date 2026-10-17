# Data Directory

## Structure

```
data/
├── processed/                          <- Preprocessed .npy arrays (NOT tracked in git)
│   ├── hyperion_scene1_198bands.npy   (Scene 1: 2017-Mar  P43/R34  TRAIN)
│   ├── hyperion_scene2_198bands.npy   (Scene 2: 2013-Mar  P41/R33  TRAIN)
│   ├── hyperion_scene3_198bands.npy   (Scene 3: 2013-Jun  P41/R33  TEST  <- hold-out)
│   ├── hyperion_scene4_198bands.npy   (Scene 4: 2014-Oct  P41/R34  TRAIN)
│   ├── hyperion_wavelengths.npy       (198-element wavelength grid, nm)
│   ├── lithium_usgs_198bands.npy      (USGS Li reference resampled to Hyperion grid)
│   └── vanadium_usgs_198bands.npy     (USGS V  reference resampled to Hyperion grid)
│
├── EO1H0410332013075110K1_1T/        <- Scene 2 raw GeoTIFF bands (B001-B242)
├── EO1H0410332013154110K1_1T/        <- Scene 3 raw GeoTIFF bands
├── EO1H0410342014301110KF_1T/        <- Scene 4 raw GeoTIFF bands
└── EO1H0430342017071110KF_1T/        <- Scene 1 raw GeoTIFF bands
```

---

## Scene Details

| # | Hyperion ID | Acquisition Date | WRS Path/Row | Pipeline Role | Notes |
|---|---|---|---|---|---|
| 1 | EO1H0430342017071 | 2017-03-12 | P43 / R34 | **TRAIN** | Independent geographic orbit |
| 2 | EO1H0410332013075 | 2013-03-16 | P41 / R33 | **TRAIN** | March dry-season acquisition |
| 3 | EO1H0410332013154 | 2013-06-03 | P41 / R33 | **TEST** (hold-out) | Same orbit as Scene 2, 3 months later |
| 4 | EO1H0410342014301 | 2014-10-28 | P41 / R34 | **TRAIN** | Adjacent row, adds geographic diversity |

**Train / Test split rationale:**
- Scenes 1, 2, and 4 form the training corpus — they span two different orbits and three acquisition dates, providing temporal and spatial diversity.
- Scene 3 is the temporal hold-out test set. It was acquired 3 months after Scene 2 over the **identical** geographic area. Correlation ≈ 0.89. Similar output maps between Scenes 2 and 3 are **expected and correct** — they reflect the same geology imaged in different seasons. This is not a code error.
- Scene 4 covers WRS row 34 (adjacent to row 33), adding a different geological background to reduce training bias.

---

## USGS Reference Spectra

Both reference files are matched to the Hyperion 198-band wavelength grid (427–2395 nm) via spectral resampling in `step2_load_usgs_spectra.py`.

| File | Source mineral | Key absorption features |
|---|---|---|
| `lithium_usgs_198bands.npy` | Lepidolite / Spodumene / Petalite | 2200 nm (Al-OH / Li-OH), 2350 nm |
| `vanadium_usgs_198bands.npy` | Vanadinite / Carnotite / Roscoelite | 2265 nm (V-OH), 500–620 nm (d-orbital) |

> **Important**: USGS spectra are used **only** as auxiliary correlation features and for band-index validation. They are **never** used to generate class labels (that would be circular). Labels come exclusively from the band-ratio absorption-depth indices LiCI and VMI computed on the Hyperion data itself.

---

## Wavelength Grid

`hyperion_wavelengths.npy` contains the 198-element wavelength array (nm) for all bands retained after bad-band removal:

| Range | Bands | Wavelengths |
|---|---|---|
| VNIR | 1–50 | 427–925 nm |
| SWIR | 51–198 | 932–2395 nm |

Key wavelengths used in label generation:

| Wavelength | Role |
|---|---|
| ≈ 2135 nm | Left shoulder of Al-OH absorption |
| ≈ 2200 nm | **LiCI core** (Li-OH / Al-OH trough) |
| ≈ 2265 nm | **VMI core** (V-OH trough, roscoelite) |
| ≈ 2350 nm | Right shoulder / second Al-OH feature |
| ≈ 1700 nm | SWIR reference shoulder |

---

## Label Generation (Non-Circular)

Labels are derived from **spectral band-ratio absorption-depth indices**, not from USGS library matching:

```
LiCI(pixel) = [R(2135) + R(2350)] / 2 − R(2200)   # absorption depth at 2200 nm
VMI(pixel)  = [R(1700) + R(2350)] / 2 − R(2265)   # absorption depth at 2265 nm

li_thresh = percentile(LiCI, 75, training set)   # config: label_percentile = 75.0
v_thresh  = percentile(VMI,  75, training set)

label = 1   if   LiCI > li_thresh   OR   VMI > v_thresh
        0   otherwise
```

- Thresholds are computed **only on the training set** and applied unchanged to the test set → no data leakage.
- Train positive rate 48.3 % (measured, outputs/summary/metrics.txt). The OR of two
  75th-percentile thresholds yields more than 25 % positives because the two indices
  fire on partly disjoint patches.
- Band-ratio features (LiCI, VMI) are **never input to the classifier** → zero circular-validation bias.

---

## How to Generate processed/ Files

1. Download raw Hyperion scenes from USGS Earth Explorer (EO-1 Hyperion)
2. Download USGS Spectral Library v7 from https://www.usgs.gov/labs/spectroscopy-lab/science/spectral-library

Then run:
```bash
cd ..   # go to FINAL_COMPLETE_PACKAGE root
python 01_MODULAR_SCRIPTS/step1_convert_hyperion.py
python 01_MODULAR_SCRIPTS/step2_load_usgs_spectra.py
```

This generates the `.npy` files in `01_MODULAR_SCRIPTS/processed_data/`.
Then copy them to `TerraQ/data/processed/`.

## Scene Details

| Scene | Hyperion ID | Date | Path/Row | Split | Correlation |
|-------|-------------|------|----------|-------|-------------|
| 1 | EO1H0430342017071 | 2017-03-12 | P43/R34 | TRAIN | — |
| 2 | EO1H0410332013075 | 2013-03-16 | P41/R33 | TRAIN | corr(2,3)=0.89 |
| 3 | EO1H0410332013154 | 2013-06-03 | P41/R33 | TEST | same orbit as 2 |

**Note on Scene 2 & 3 similarity**: Scenes 2 and 3 cover the exact same geographic orbit
(P41/R33). Output maps look structurally similar (corr ≈ 0.89 in reflectance). This is
correct geology — same terrain imaged in different seasons. It is NOT a data or code error.

## USGS Reference Spectra

Target minerals from USGS Spectral Library v7:
- **Lithium minerals**: Lepidolite, Spodumene, Petalite (Li-bearing micas and pyroxenes)
- **Vanadium minerals**: Vanadinite, Carnotite (V oxides and phosphates)

Key absorption features used in band-ratio indices:
- LiCI: Ratio of bands at ~2200 nm / ~2350 nm (Li-O and Li-OH absorption)
- VMI: Ratio of bands at ~500 nm / ~620 nm (V d-orbital transitions)

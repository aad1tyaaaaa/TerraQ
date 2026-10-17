# Data directory
#
# data/raw/hyperion/
#   ├── EO1H0430342017071110KF_1T/   ← Scene 1 GeoTIFFs
#   ├── EO1H0410332013075110K1_1T/   ← Scene 2 GeoTIFFs
#   ├── EO1H0410332013154110K1_1T/   ← Scene 3 GeoTIFFs  (TEST)
#   └── EO1H0410342014301110KF_1T/   ← Scene 4 GeoTIFFs
#
# data/raw/usgs_splib07/
#   ├── ASCIIdata/                   ← USGS Spectral Library v7 ASCII files
#   └── ...
#
# data/processed/                    ← auto-created by preprocessing scripts
#   ├── hyperion_scene1_198bands.npy
#   ├── hyperion_scene2_198bands.npy
#   ├── hyperion_scene3_198bands.npy
#   ├── hyperion_scene4_198bands.npy
#   ├── lithium_usgs_198bands.npy
#   └── vanadium_usgs_198bands.npy
#
# To pre-process:
#   python -m src.preprocessing.convert_hyperion
#   python -m src.preprocessing.load_usgs_spectra

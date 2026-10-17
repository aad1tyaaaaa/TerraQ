#!/usr/bin/env python3
"""
product/validation_plan_v2.py
=============================
Round 2 of the validation study: vanadium (Nevada) and an India spot-check.
Everything here was decided BEFORE any run, same as round 1.

VANADIUM — frozen rules
-----------------------
MRDS lists V in the commodity string for many polymetallic Ag/Pb/Zn/Cu/W
systems where vanadium is a trace associate, not the deposit. Scoring a
"vanadium index" against those would be measuring the wrong thing, so:

    v_dominant   : V is the FIRST commodity token, OR the record lists <= 2
                   commodities and includes V          -> the positives
    polymetallic : anything else carrying a V token     -> reported separately

A deliberate test of our own stated limitation: the Gibellini district is
BLACK-SHALE hosted vanadium, and this project claims throughout that black-shale
V has no usable surface signature. If Gibellini scores low, that CONFIRMS the
caveat rather than contradicting the tool. Either outcome is reported.

INDIA — why this is a spot check, not a validation
--------------------------------------------------
Two blockers, both measured rather than assumed:
  1. GSI Bhukosh and NGDR are unreachable from this environment (connection
     timeout / DNS failure), so India's own deposit database is unavailable.
  2. MRDS does carry 961 records inside the India bbox, but of the 17 with a
     Li or V token, most are administrative placeholders — records literally
     named "Bihar", "Orissa", "Maharashtra State", "Summary of Deposits In
     Mysore". A state centroid cannot validate a 40 m pixel.

Only two India records carry deposit-level names AND non-placeholder
coordinates. Two points is a spot check. The reported-occurrence sites from the
project gazetteer are town/district centroids, which is stated wherever they
appear. Nothing here is presented as a validation.
"""

RADIUS_KM = 12.0

# ---- Vanadium, Nevada -----------------------------------------------------
VANADIUM_AOIS = [
    dict(id="V1", name="Gibellini district", lat=39.2067, lon=-116.0969,
         why="4 V-dominant MRDS records; black-shale hosted — the direct test of "
             "our own 'black-shale V is not detectable' claim"),
    dict(id="V2", name="Bullion / Iron Girl", lat=41.1938, lon=-118.5360,
         why="3 V-dominant records, iron-associated vanadium"),
    dict(id="V3", name="Speeter / Valley Forge", lat=35.8100, lon=-115.5196,
         why="3 V-dominant records, southern Nevada"),
    dict(id="V4", name="Coleville area", lat=38.6010, lon=-119.4994,
         why="2 V-dominant records, western Nevada"),
]

# ---- India ----------------------------------------------------------------
# Tagged by coordinate quality so nothing silently mixes precisions.
INDIA_AOIS = [
    dict(id="I1", name="Mayurbhanj (Kaduani/Kumhardh)", lat=21.9494, lon=86.4302,
         commodity="vanadium", coord_quality="deposit-level MRDS record",
         why="named localities, non-placeholder coordinates"),
    dict(id="I2", name="Shaltora area", lat=23.4160, lon=86.9168,
         commodity="vanadium", coord_quality="deposit-level MRDS record",
         why="named locality, non-placeholder coordinates"),
    dict(id="I3", name="Katghora, Korba", lat=22.5025, lon=82.5428,
         commodity="lithium", coord_quality="TOWN CENTROID — not the deposit",
         why="reported pegmatite block; geocoded town centre only"),
    dict(id="I4", name="Marlagalla / Mandya", lat=12.5223, lon=76.8975,
         commodity="lithium", coord_quality="TOWN CENTROID — not the deposit",
         why="reported pegmatite occurrence; geocoded town centre only"),
]

# Indian background. Thar desert gives exposed rock comparable to Nevada; the
# Deccan control sits in the same vegetated belt as I1/I2, so the comparison is
# like-for-like rather than desert-vs-monsoon.
INDIA_CONTROLS = [
    dict(id="IC1", name="Thar desert (Jaisalmer E)", lat=26.95, lon=71.45,
         kind="desert", why="exposed arid rock, no catalogued Li/V nearby"),
    dict(id="IC2", name="Deccan interior (Vidarbha)", lat=20.35, lon=78.10,
         kind="vegetated", why="same climatic belt as the eastern V sites, so "
                               "rock fraction is comparable"),
]

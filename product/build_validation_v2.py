#!/usr/bin/env python3
"""
product/build_validation_v2.py
==============================
Round 2 results: vanadium (Nevada) and the India spot-check.

Merges into outputs/validation_final.json and the dashboard copy at
terraq/explorer/data/validation.json, alongside the round-1 lithium work.
Rules were frozen in validation_plan_v2.py before any run.
"""
from __future__ import annotations
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from validation_plan_v2 import (                                  # noqa: E402
    VANADIUM_AOIS, INDIA_AOIS, INDIA_CONTROLS,
)

V_RES = json.load(open("/tmp/qmd_probe/v_results.json"))
I_RES = json.load(open("/tmp/qmd_probe/india_results.json"))


def main():
    # ---- vanadium ---------------------------------------------------------
    scored = [r for r in V_RES if r["status"] == "scored"]
    vd = [r for r in scored if r["vclass"] == "v_dominant"]
    pm = [r for r in scored if r["vclass"] == "polymetallic"]

    def grp(g):
        if not g:
            return None
        return dict(n=len(g),
                    median_percentile=round(float(np.median([r["pct"] for r in g])), 1),
                    median_score=round(float(np.median([r["value"] for r in g])), 3),
                    at_ceiling=sum(1 for r in g if r["value"] >= 0.999))

    vanadium = dict(
        what_this_measures=(
            "The vanadium layer is itself per-scene normalised, so these are "
            "within-scene ranks, not absolute values. No raw vanadium raster is "
            "exported, so unlike lithium these cannot be compared across scenes."),
        classification_rule=(
            "v_dominant = V is the first commodity token, or the record lists <=2 "
            "commodities including V. Everything else carrying a V token is "
            "polymetallic, where vanadium is a trace associate of an Ag/Pb/Zn/Cu/W "
            "system rather than the deposit."),
        aois=[dict(id=a["id"], name=a["name"], lat=a["lat"], lon=a["lon"], why=a["why"])
              for a in VANADIUM_AOIS],
        counts=dict(scored=len(scored), v_dominant=len(vd), polymetallic=len(pm),
                    masked=sum(1 for r in V_RES if r["status"] == "masked")),
        v_dominant=grp(vd),
        polymetallic=grp(pm),
        separation_note=(
            f"V-dominant records sit at the {grp(vd)['median_percentile']}th percentile "
            f"of their scenes; polymetallic records at the {grp(pm)['median_percentile']}th. "
            "The layer does separate the two, which is the result the 'low confidence' "
            "label did not assume."),
        gibellini_note=(
            "Gibellini is BLACK-SHALE hosted vanadium, which this project states "
            "throughout has no usable surface signature — yet 5 of its 7 records sit at "
            "the top of the scene. Two cautions before reading that as a success: a "
            "score of 1.000 is the normalisation ceiling (the top 2% of any scene), not "
            "a perfect match; and the index may be responding to surface iron-oxide "
            "weathering over the shale rather than the shale itself. Reported as "
            "measured, interpretation unresolved."),
        sites=scored,
    )

    # ---- india ------------------------------------------------------------
    sites = [r for r in I_RES if r.get("coord_quality")]
    ctrls = [r for r in I_RES if not r.get("coord_quality")]
    rock = {r["id"]: r["rock_pct"] for r in I_RES}

    india = dict(
        status="SPOT CHECK — not a validation",
        why_not_a_validation=[
            "GSI Bhukosh and NGDR are unreachable from this environment "
            "(connection timeout and DNS failure on repeated attempts), so India's "
            "own deposit database could not be used.",
            "MRDS holds 961 records inside the India bbox, but of the 17 carrying a "
            "Li or V token most are administrative placeholders — records named "
            "'Bihar', 'Orissa', 'Maharashtra State', 'Summary of Deposits In Mysore'. "
            "A state centroid cannot validate a 40 m pixel.",
            "Only 2 records carry both a deposit-level name and non-placeholder "
            "coordinates. Two points is a spot check.",
            "The reported-occurrence sites are town/district centroids, not deposit "
            "outlines, and are labelled as such wherever they appear.",
        ],
        headline_finding=(
            f"Usable rock is {min(rock[a['id']] for a in INDIA_AOIS)}–"
            f"{max(rock[a['id']] for a in INDIA_AOIS)}% at the Indian sites, against "
            f"{rock['IC1']}% in the Thar desert control. Vegetation hides the rock "
            "signal across most of India, so the method cannot see these areas at all — "
            "and the sites that could be sampled land mid-distribution, not elevated."),
        aois=[dict(id=a["id"], name=a["name"], lat=a["lat"], lon=a["lon"],
                   commodity=a.get("commodity"), coord_quality=a.get("coord_quality"),
                   why=a["why"]) for a in INDIA_AOIS],
        controls=[dict(id=a["id"], name=a["name"], lat=a["lat"], lon=a["lon"],
                       kind=a["kind"], why=a["why"]) for a in INDIA_CONTROLS],
        measurements=I_RES,
        conclusion=(
            "On this evidence the method is not usable over vegetated India. The arid "
            "north-west (Thar and similar) is the part of the country where it has "
            "enough exposed rock to work. Confirming anything further needs GSI "
            "deposit-level coordinates, which were not reachable here."),
    )

    # ---- where the validation actually applies ----------------------------
    # Derived from the AOIs we really ran, not hand-drawn, so it cannot drift
    # from the evidence. A margin is added because a validated conclusion
    # plausibly extends a little beyond the exact footprints tested.
    def bbox(pts, margin):
        la = [p[0] for p in pts]; lo = [p[1] for p in pts]
        return dict(lat_min=round(min(la) - margin, 3), lat_max=round(max(la) + margin, 3),
                    lon_min=round(min(lo) - margin, 3), lon_max=round(max(lo) + margin, 3))

    nevada_pts = [(a["lat"], a["lon"]) for a in VANADIUM_AOIS]
    for key in ("control_aois", "lithium_aois"):
        nevada_pts += [(a["lat"], a["lon"]) for a in json.load(
            open(os.path.join(ROOT, "outputs", "validation_final.json"))).get(key, [])]
    india_pts = [(a["lat"], a["lon"]) for a in INDIA_AOIS + INDIA_CONTROLS]

    coverage = dict(
        note=("Validation is region-specific. These bounds come from the AOIs that "
              "were actually run, plus a margin — they are not a claim that the "
              "method generalises beyond them."),
        regions=[
            dict(id="nevada", label="Nevada, USA", scope="lithium",
                 status="validated",
                 bounds=bbox(nevada_pts, 1.5),
                 summary=("6 non-brine lithium sites and 29 vanadium records against "
                          "6 control areas. This is where the numbers on this panel "
                          "come from.")),
            dict(id="india", label="India", scope="india",
                 status="spot check",
                 bounds=bbox(india_pts, 2.0),
                 summary=("Not a validation. Usable rock is 2–7% over vegetated India, "
                          "so the method cannot see most of the country. Only the arid "
                          "north-west has enough exposed rock.")),
        ],
        outside=dict(
            status="no validation",
            summary=("Nothing has been validated here. The engine will still run and "
                     "the numbers it returns are real measurements of this scene — but "
                     "no check exists that the index tracks mineralisation in this "
                     "geology. Treat the output as exploratory only."),
        ),
    )

    # ---- merge ------------------------------------------------------------
    for path in [os.path.join(ROOT, "outputs", "validation_final.json"),
                 os.path.join(ROOT, "terraq", "explorer", "data", "validation.json")]:
        d = json.load(open(path))
        d["vanadium"] = vanadium
        d["india"] = india
        d["coverage"] = coverage
        json.dump(d, open(path, "w"), indent=1)
        print("updated", path)

    print(f"\nvanadium: v_dominant n={grp(vd)['n']} median pct {grp(vd)['median_percentile']}"
          f" | polymetallic n={grp(pm)['n']} median pct {grp(pm)['median_percentile']}")
    print(f"india: rock% {[rock[a['id']] for a in INDIA_AOIS]} vs Thar {rock['IC1']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

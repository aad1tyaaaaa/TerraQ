#!/usr/bin/env python3
"""
product/build_gazetteer.py
==========================
Build a small, local gazetteer of REPORTED critical-mineral occurrences so the
Explorer's search box can find them instantly, with no geocoder call.

Why this exists
---------------
Names like "Marlagalla-Allapatna" or "Salal-Haimana" are mining/geological
labels, not settlements — public geocoders do not carry them. On top of that the
public Nominatim instance rate-limits a shared IP (observed HTTP 429), so during
a demo the search box can silently return nothing. A committed local list is
instant, works offline, and cannot be throttled.

Honesty rules this file follows
-------------------------------
* Coordinates are NOT typed in by hand. Each site is resolved through a public
  geocoder from candidate search terms, and the term + provider that resolved it
  is recorded in the output.
* A site that cannot be resolved is OMITTED, never guessed.
* The coordinate is a town/district centroid, not the deposit outline. Every
  record says so, and the UI repeats it.
* Reported tonnages ARE carried, but only as `reported`: a verbatim third-party
  claim with an explicit source, never as something this system measured. The UI
  renders them in a separate, labelled block so they can never be mistaken for an
  engine reading.
* The supplied figures do not state a resource classification (inferred /
  indicated / measured), which in resource reporting is the difference between a
  guess and a bankable number. That omission is recorded and surfaced, not
  papered over.

Usage:  .venv/bin/python product/build_gazetteer.py
Output: terraq/explorer/data/gazetteer.json
"""
from __future__ import annotations
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "terraq", "explorer", "data", "gazetteer.json")

UA = "terraq-explorer/1.0 (research prototype; mineral prospecting demo)"
OPEN_METEO = "https://geocoding-api.open-meteo.com/v1/search"
NOMINATIM = "https://nominatim.openstreetmap.org/search"

# label            : what the user is likely to type
# aliases          : other spellings worth matching locally
# query_candidates : terms handed to the geocoder, best first
REPORTED = {
    "Salal-Haimana, Reasi": "~5.9 million tonnes lithium",
    "Katghora, Korba": "India's first commercially auctioned lithium block",
    "Marlagalla-Allapatna, Mandya": "~1,600 tonnes lithium",
    "Sambhar Salt Lake": "Saline brine under exploration for liquid extraction",
    "Jodhpur paleo-channel brines": "Paleo-channel brines under exploratory drilling",
    "Barmer paleo-channel brines": "Paleo-channel brines under exploratory drilling",
    "Papum Pare (Depo / Tamang)": "13.79 million tonnes primary land-based vanadium",
    "Gulf of Khambhat (Alang coast)": "Offshore vanadium-enriched titanomagnetite",
    "Mayurbhanj": "Vanadiferous titanomagnetite processed for V recovery",
    "Dublabera, East Singhbhum": "Vanadium as a by-product of titaniferous magnetite",
    "Shimoga iron-ore belt": "Vanadium recovered as slag during steel manufacture",
    "Hassan iron-ore belt": "Vanadium recovered as slag during steel manufacture"
}

SITES = [
    # ---- Lithium ----------------------------------------------------------
    dict(label="Salal-Haimana, Reasi", commodity="lithium", region="Jammu & Kashmir",
         setting="Bauxite-associated clay occurrence",
         aliases=["Salal", "Haimana", "Reasi"],
         query_candidates=["Reasi, Jammu and Kashmir, India", "Salal, Jammu and Kashmir"]),
    dict(label="Katghora, Korba", commodity="lithium", region="Chhattisgarh",
         setting="Hard-rock pegmatite block",
         aliases=["Katghora", "Korba"],
         query_candidates=["Katghora, Chhattisgarh, India", "Korba, Chhattisgarh, India"]),
    dict(label="Marlagalla-Allapatna, Mandya", commodity="lithium", region="Karnataka",
         setting="Pegmatite occurrence",
         aliases=["Marlagalla", "Allapatna", "Mandya"],
         query_candidates=["Mandya, Karnataka, India", "Srirangapatna, Karnataka, India"]),
    dict(label="Sambhar Salt Lake", commodity="lithium", region="Rajasthan",
         setting="Saline brine — NOT detectable optically",
         aliases=["Sambhar", "Sambhar Lake"],
         query_candidates=["Sambhar, Rajasthan, India", "Sambhar Lake Town, Rajasthan"]),
    dict(label="Jodhpur paleo-channel brines", commodity="lithium", region="Rajasthan",
         setting="Sub-surface brine — NOT detectable optically",
         aliases=["Jodhpur"],
         query_candidates=["Jodhpur, Rajasthan, India"]),
    dict(label="Barmer paleo-channel brines", commodity="lithium", region="Rajasthan",
         setting="Sub-surface brine — NOT detectable optically",
         aliases=["Barmer"],
         query_candidates=["Barmer, Rajasthan, India"]),

    # ---- Vanadium ---------------------------------------------------------
    dict(label="Papum Pare (Depo / Tamang)", commodity="vanadium",
         region="Arunachal Pradesh", setting="Carbonaceous phyllite",
         aliases=["Papum Pare", "Depo", "Tamang", "Daba Gamlin", "Itanagar"],
         query_candidates=["Itanagar, Arunachal Pradesh, India",
                           "Naharlagun, Arunachal Pradesh, India"]),
    dict(label="Gulf of Khambhat (Alang coast)", commodity="vanadium", region="Gujarat",
         setting="Offshore titanomagnetite sediment — marine, not land surface",
         aliases=["Khambhat", "Alang", "Cambay"],
         query_candidates=["Alang, Gujarat, India", "Khambhat, Gujarat, India"]),
    dict(label="Mayurbhanj", commodity="vanadium", region="Odisha",
         setting="Vanadiferous titanomagnetite belt",
         aliases=["Mayurbhanj", "Baripada"],
         query_candidates=["Baripada, Odisha, India", "Mayurbhanj, Odisha, India"]),
    dict(label="Dublabera, East Singhbhum", commodity="vanadium", region="Jharkhand",
         setting="Titaniferous magnetite belt",
         aliases=["Dublabera", "Singhbhum", "Jamshedpur"],
         query_candidates=["Jamshedpur, Jharkhand, India",
                           "Ghatshila, Jharkhand, India"]),
    dict(label="Shimoga iron-ore belt", commodity="vanadium", region="Karnataka",
         setting="Iron-ore pockets, V recovered as slag by-product",
         aliases=["Shimoga", "Shivamogga"],
         query_candidates=["Shivamogga, Karnataka, India", "Shimoga, Karnataka, India"]),
    dict(label="Hassan iron-ore belt", commodity="vanadium", region="Karnataka",
         setting="Iron-ore pockets, V recovered as slag by-product",
         aliases=["Hassan"],
         query_candidates=["Hassan, Karnataka, India"]),
]


def _get(url: str, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def via_open_meteo(q: str):
    name = q.split(",")[0].strip()
    url = f"{OPEN_METEO}?name={urllib.parse.quote(name)}&count=5&language=en&format=json"
    try:
        rows = (_get(url) or {}).get("results") or []
    except Exception:
        return None
    for x in rows:
        if x.get("country_code") == "IN":          # these sites are all in India
            return dict(lat=round(float(x["latitude"]), 4),
                        lon=round(float(x["longitude"]), 4),
                        resolved_name=x.get("name"),
                        admin=x.get("admin1"),
                        provider="open-meteo", query=name)
    return None


def via_nominatim(q: str):
    url = (f"{NOMINATIM}?q={urllib.parse.quote(q)}&format=jsonv2"
           f"&addressdetails=1&limit=3&countrycodes=in")
    try:
        rows = _get(url)
    except Exception:
        return None
    time.sleep(1.2)                                 # usage policy
    if not rows:
        return None
    x = rows[0]
    return dict(lat=round(float(x["lat"]), 4), lon=round(float(x["lon"]), 4),
                resolved_name=(x.get("display_name") or "").split(",")[0],
                admin=(x.get("address") or {}).get("state"),
                provider="nominatim", query=q)


def main():
    out, missing = [], []
    for site in SITES:
        found = None
        for q in site["query_candidates"]:
            found = via_open_meteo(q) or via_nominatim(q)
            if found:
                break
        if not found:
            missing.append(site["label"])
            print(f"  ✗ {site['label']:38s} UNRESOLVED — omitted")
            continue
        out.append({
            "label": site["label"],
            "commodity": site["commodity"],
            "region": site["region"],
            "setting": site["setting"],
            "aliases": site["aliases"],
            "lat": found["lat"],
            "lon": found["lon"],
            # Provenance, so nothing here looks hand-typed.
            "resolved_from": found["query"],
            "resolved_name": found["resolved_name"],
            "geocoder": found["provider"],
            "precision": "town/district centroid — not the deposit outline",
            # Verbatim third-party claim. Never produced or checked by this system.
            "reported": REPORTED.get(site["label"]),
        })
        print(f"  ✓ {site['label']:38s} {found['lat']:>9.4f},{found['lon']:>9.4f}  "
              f"({found['provider']}: {found['resolved_name']})")

    doc = {
        "note": ("Reported critical-mineral occurrences used to make the search box "
                 "useful for this domain. Coordinates are town/district centroids "
                 "resolved by a public geocoder, NOT deposit outlines, and NOT "
                 "measurements by this system. Presence here is not evidence of "
                 "anything — press Analyze to get a measured value."),
        "reported_source": (
            "Figures supplied by the project owner from public reporting. They are "
            "third-party claims that this system has neither produced nor verified, "
            "and no resource classification (inferred / indicated / measured) was "
            "stated for them — check the original source before relying on any of "
            "them."),
        "generated_by": "product/build_gazetteer.py",
        "count": len(out),
        "omitted_unresolved": missing,
        "sites": out,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {OUT}  ({len(out)} sites, {len(missing)} omitted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

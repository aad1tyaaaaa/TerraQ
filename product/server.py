#!/usr/bin/env python3
"""
product/server.py
=================
Clickable web demo for the mineral-prospectivity engine.

Pure standard-library HTTP server (no Flask/FastAPI needed) wrapping
sentinel_engine.run(). Click a point on the map -> the backend fetches
Sentinel-2, runs the indices, and returns the overlay images + an honest
report.

Run:
    <venv>/bin/python product/server.py
Then open  http://localhost:8765

Routes:
    GET  /                      demo page (Leaflet map + controls)
    POST /api/analyze           {lat,lon,km} -> runs engine, returns JSON
    GET  /jobs/<id>/<file>      serves generated PNGs
"""
from __future__ import annotations
import os, sys, json, csv, time, hashlib, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sentinel_engine import run as engine_run   # noqa: E402
from overlay_export import (                    # noqa: E402
    export_overlays, confidence_summary_from, OVERLAY_SUBDIR,
)
from target_finder import ensure_targets        # noqa: E402

JOBS_DIR = os.path.join(ROOT, "outputs", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)
PORT = int(os.environ.get("PORT", "8765"))

# Preload MRDS ground-truth points (for overlay markers / honesty)
def _load_deposits():
    pts = []
    for fn, comm in [("mrds_lithium.csv", "Li"), ("mrds_vanadium.csv", "V")]:
        p = os.path.join(ROOT, "data", "ground_truth", fn)
        if os.path.exists(p):
            for r in csv.DictReader(open(p)):
                pts.append((f"{comm}:{r['site'][:13]}", float(r["lat"]), float(r["lon"])))
    return pts
DEPOSITS = _load_deposits()

_lock = threading.Lock()   # engine uses shared GDAL env; serialize runs


def ensure_overlays(job_dir, meta):
    """
    Backfill bare georeferenced overlays for a job cached before they existed.

    Rebuilds them from the job's GeoTIFFs and merges `overlay_corners` /
    `overlay_layers` / `confidence_summary` into result.json. The cache key is
    derived from (lat, lon, km) only, so nothing here invalidates an old cache —
    an old job simply gains the new fields in place.
    """
    need = (not meta.get("overlay_corners")
            or not os.path.isdir(os.path.join(job_dir, OVERLAY_SUBDIR)))
    if need:
        try:
            meta.update(export_overlays(job_dir))
        except Exception as e:
            print(f"  ! overlay backfill failed for {job_dir}: {e}")
            meta.setdefault("overlay_corners", None)
            meta.setdefault("overlay_layers", [])
    if not meta.get("confidence_summary"):
        meta["confidence_summary"] = confidence_summary_from(meta=meta)
    try:
        with open(os.path.join(job_dir, "result.json"), "w") as f:
            json.dump(meta, f, indent=2)
    except OSError:
        pass
    return meta


def sample_lithium(job, lat, lon):
    """
    S1 — click-anywhere lithium score for one lat/lon inside an analysed job.

    Reads the job's lithium GeoTIFF, reprojecting the lat/lon into the raster's
    own CRS (UTM) before sampling — the rasters are not in EPSG:4326.

    Returns nulls plus a reason when there is nothing to report, so the UI can
    show "—". A masked pixel is NOT a low score: it means the index could not be
    evaluated there at all.

    Shape: {li_score, li_percentile_in_aoi, confidence_class, status, reason}
    """
    import numpy as np
    import rasterio
    from rasterio.transform import rowcol
    from pyproj import Transformer

    job_dir = os.path.join(JOBS_DIR, job)
    tif = os.path.join(job_dir, "lithium_prospectivity.tif")
    if not os.path.isfile(tif):
        return {"ok": False, "error": "job has no lithium raster"}

    with rasterio.open(tif) as src:
        arr = src.read(1).astype("float32")
        tf = Transformer.from_crs("EPSG:4326", src.crs.to_string(), always_xy=True)
        x, y = tf.transform(lon, lat)            # lon/lat -> raster CRS
        r, c = rowcol(src.transform, x, y)

    base = {"ok": True, "job": job, "lat": lat, "lon": lon,
            "li_score": None, "li_percentile_in_aoi": None,
            "confidence_class": None,
            "scale_note": ("Relative 0-1 alteration index within THIS scene and its "
                           "percentile among valid pixels of this scene. Not a "
                           "probability; not comparable across scenes.")}

    h, w = arr.shape
    if not (0 <= r < h and 0 <= c < w):
        base.update(status="outside_footprint", reason="outside analysed area")
        return base

    # Confidence class from the engine's own confidence raster when present.
    conf_class, conf_val = None, None
    conf_tif = os.path.join(job_dir, "confidence.tif")
    if os.path.isfile(conf_tif):
        try:
            with rasterio.open(conf_tif) as cs:
                carr = cs.read(1)
                if 0 <= r < carr.shape[0] and 0 <= c < carr.shape[1]:
                    conf_val = float(carr[r, c])
                    conf_class = ("high" if conf_val >= 0.99
                                  else "low" if conf_val > 0.0 else "masked")
        except Exception:
            conf_class = None
    base["confidence_class"] = conf_class

    win = arr[max(0, r - 1):r + 2, max(0, c - 1):c + 2]
    winv = win[win > 0]
    if winv.size == 0:
        base.update(status="masked", reason="masked: vegetation/water/nodata")
        return base

    valid = arr > 0
    val = float(winv.mean())
    base.update(
        status="scored",
        li_score=round(val, 3),
        li_percentile_in_aoi=round(float((arr[valid] < val).mean() * 100), 1),
        reason=None,
    )
    if conf_class is None:
        base["confidence_class"] = "high"   # it scored, so the index was evaluable
    return base


def sample_point(job, lat, lon):
    """
    Index value + within-scene percentile at one lat/lon of an analysed job.

    Mirrors benchmark_console.py: a point is only given a number when the index
    actually evaluated there. 'outside_footprint' and 'masked' return null so the
    UI can show "—" instead of a misleading 0.
    """
    import numpy as np
    import rasterio
    from rasterio.transform import rowcol
    from pyproj import Transformer

    out = {}
    for key, tif in [("lithium", "lithium_prospectivity.tif"),
                     ("vanadium", "vanadium_prospectivity.tif")]:
        path = os.path.join(JOBS_DIR, job, tif)
        if not os.path.isfile(path):
            out[key] = {"status": "unavailable", "score": None, "percentile": None}
            continue
        with rasterio.open(path) as src:
            arr = src.read(1).astype("float32")
            tf = Transformer.from_crs("EPSG:4326", src.crs.to_string(), always_xy=True)
            x, y = tf.transform(lon, lat)
            r, c = rowcol(src.transform, x, y)
        h, w = arr.shape
        if not (0 <= r < h and 0 <= c < w):
            out[key] = {"status": "outside_footprint", "score": None, "percentile": None,
                        "note": "Outside the analysed area — not evaluated."}
            continue
        win = arr[max(0, r - 1):r + 2, max(0, c - 1):c + 2]
        winv = win[win > 0]
        if winv.size == 0:
            out[key] = {"status": "masked", "score": None, "percentile": None,
                        "note": ("No valid rock pixels here (water, vegetation, cloud "
                                 "or nodata) — optical sensing cannot score this spot.")}
            continue
        valid = arr > 0
        val = float(winv.mean())
        out[key] = {
            "status": "scored",
            "score": round(val, 3),
            "percentile": round(float((arr[valid] < val).mean() * 100), 1),
        }
    out["lat"], out["lon"], out["job"] = lat, lon, job
    out["scale_note"] = ("Relative 0-1 alteration index within THIS scene, and its "
                         "percentile among valid pixels of this scene. Not a "
                         "probability and not comparable across scenes.")
    return {"ok": True, **out}


def list_jobs():
    """
    Every cached analysis, newest first.

    lat/lon/km are NOT stored in result.json, so the centre is derived from
    `bbox_lonlat` and the radius from its half-height (the engine builds the bbox
    as lat +/- km/111). The timestamp is the result.json mtime — the engine does
    not record a run time of its own.
    """
    jobs = []
    for job in os.listdir(JOBS_DIR):
        rj = os.path.join(JOBS_DIR, job, "result.json")
        if not os.path.isfile(rj):
            continue
        try:
            meta = json.load(open(rj))
        except (ValueError, OSError):
            continue
        bbox = meta.get("bbox_lonlat") or [None] * 4
        if None in bbox:
            continue
        w, s, e, n = bbox
        jobs.append({
            "job": job,
            "lat": round((s + n) / 2.0, 4),
            "lon": round((w + e) / 2.0, 4),
            "km": round((n - s) / 2.0 * 111.0, 1),   # inverse of the engine's bbox maths
            "timestamp": os.path.getmtime(rj),
            "coverage": round(meta.get("coverage", 0) * 100),
            "tiles": len(meta.get("tiles_used", [])),
            "date_range": meta.get("date_range", ""),
            "bbox_lonlat": bbox,
            "has_overlays": bool(meta.get("overlay_corners")),
        })
    jobs.sort(key=lambda j: j["timestamp"], reverse=True)
    return {"ok": True, "jobs": jobs}

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Mineral Prospectivity — Sentinel-2</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=stylesheet href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 body{margin:0;font-family:system-ui,Arial;background:#0b0e14;color:#e7ecf3}
 header{padding:14px 20px;background:#11151f;border-bottom:1px solid #222b3a}
 h1{font-size:18px;margin:0} .sub{color:#8aa0b8;font-size:12px;margin-top:3px}
 .wrap{display:flex;gap:0;height:calc(100vh - 58px)}
 #map{flex:1;min-width:320px} .panel{width:430px;overflow-y:auto;padding:16px;background:#0b0e14}
 .row{display:flex;gap:8px;align-items:center;margin:8px 0;flex-wrap:wrap}
 input,button{background:#161c28;color:#e7ecf3;border:1px solid #2a3546;border-radius:8px;padding:8px}
 button{background:#2563eb;border:0;cursor:pointer;font-weight:600}
 button:disabled{opacity:.5;cursor:wait}
 label{font-size:12px;color:#8aa0b8;width:42px}
 img{width:100%;border-radius:8px;border:1px solid #222b3a;margin-top:6px}
 .cap{font-size:11px;color:#d7b46a;background:#1c1810;border:1px solid #3a2f12;border-radius:8px;padding:10px;margin:10px 0;line-height:1.5}
 table{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px}
 td,th{border-bottom:1px solid #1d2633;padding:4px;text-align:left}
 .tag{font-size:10px;padding:1px 6px;border-radius:6px}
 .rock{background:#0e3a2a;color:#5fe0a8} .playa{background:#3a1030;color:#e07ad0}
 .muted{color:#8aa0b8;font-size:12px}
</style></head><body>
<header><h1>Mineral Prospectivity Engine — Sentinel-2</h1>
<div class=sub>Click the map (or type coordinates) to analyse an area for lithium / vanadium surface alteration.</div></header>
<div class=wrap>
 <div id=map></div>
 <div class=panel>
  <div class=row><label>Lat</label><input id=lat value="37.7499" style="width:110px">
   <label>Lon</label><input id=lon value="-117.6342" style="width:110px"></div>
  <div class=row><label>Radius</label><input id=km type=range min=4 max=20 value=12 oninput="kmv.textContent=this.value+' km'">
   <span id=kmv class=muted>12 km</span>
   <button id=go onclick=analyze()>Analyze</button></div>
  <div class=row><span class=muted>Presets:</span>
   <button style="background:#243044" onclick="setp(37.7499,-117.6342)">Silver Peak (Li)</button>
   <button style="background:#243044" onclick="setp(37.78,-117.60)">Clayton Valley</button></div>
  <div id=status class=muted></div>
  <div id=results></div>
 </div>
</div>
<script>
 var map=L.map('map').setView([37.76,-117.62],11);
 L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'OSM'}).addTo(map);
 var marker=L.marker([37.7499,-117.6342]).addTo(map);
 function setp(la,lo){document.getElementById('lat').value=la;document.getElementById('lon').value=lo;
   marker.setLatLng([la,lo]);map.setView([la,lo],11);}
 map.on('click',function(e){setp(e.latlng.lat.toFixed(4),e.latlng.lng.toFixed(4));});
 function analyze(){
   var lat=parseFloat(lat_.value),lon=parseFloat(lon_.value),km=parseFloat(km_.value);
   var go=document.getElementById('go');go.disabled=true;
   var st=document.getElementById('status');
   st.textContent='Fetching Sentinel-2 and computing (can take 1-3 min)...';
   document.getElementById('results').innerHTML='';
   fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({lat:lat,lon:lon,km:km})})
    .then(r=>r.json()).then(d=>{
      go.disabled=false;
      if(!d.ok){st.textContent='Error: '+d.error;return;}
      st.textContent='Done — '+d.coverage+'% coverage, tiles: '+d.tiles+' ('+d.date_range+')';
      var h='<div class=cap><b>How to read this:</b> '+d.caveat+'</div>';
      var imgs=[['Lithium prospectivity (clay/Al-OH)','lithium_prospectivity.png'],
                ['Vanadium prospectivity (low confidence)','vanadium_prospectivity.png'],
                ['Brine-favorability (indirect basin flag)','brine_favorability.png'],
                ['Sentinel-2 RGB','rgb.png'],['Confidence','confidence.png']];
      imgs.forEach(function(x){h+='<div class=muted style="margin-top:10px">'+x[0]+'</div><img src="'+d.base+'/'+x[1]+'?t='+Date.now()+'">';});
      if(d.deposit_check&&d.deposit_check.length){
        h+='<table><tr><th>Known deposit</th><th>type</th><th>Li</th><th>%ile</th><th>V</th></tr>';
        d.deposit_check.forEach(function(x){h+='<tr><td>'+x.name+'</td><td><span class="tag '+x.type+'">'+x.type+'</span></td><td>'+x.li_score+'</td><td>'+x.li_percentile+'</td><td>'+x.v_score+'</td></tr>';});
        h+='</table><div class=muted style="margin-top:6px">Markers: cyan=rock-hosted, magenta=playa/brine (correctly not detected).</div>';}
      document.getElementById('results').innerHTML=h;
    }).catch(e=>{go.disabled=false;st.textContent='Request failed: '+e;});
 }
 var lat_=document.getElementById('lat'),lon_=document.getElementById('lon'),km_=document.getElementById('km');
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quieter logs
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):   # CORS preflight for cross-origin (Next.js) calls
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            return self._send(200, PAGE, "text/html")
        if self.path.split("?")[0] == "/api/jobs":
            return self._send(200, json.dumps(list_jobs()))
        if self.path.split("?")[0] == "/api/targets":
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            job = (q.get("job") or [""])[0]
            if "/" in job or ".." in job or not os.path.isdir(os.path.join(JOBS_DIR, job)):
                return self._send(404, json.dumps({"ok": False, "error": "no such job"}))
            try:
                # Generated on first request and cached as <job>/targets.json.
                # Does not touch result.json or the (lat,lon,km) cache key.
                pts = [(n, la, lo) for (n, la, lo) in DEPOSITS]
                return self._send(200, json.dumps(
                    ensure_targets(os.path.join(JOBS_DIR, job), pts)))
            except Exception as e:
                return self._send(500, json.dumps({"ok": False, "error": str(e)}))
        if self.path.split("?")[0] == "/api/sample":
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            try:
                job = q["job"][0]
                lat, lon = float(q["lat"][0]), float(q["lon"][0])
            except (KeyError, IndexError, ValueError):
                return self._send(400, json.dumps(
                    {"ok": False, "error": "need job, lat, lon"}))
            if "/" in job or ".." in job or not os.path.isdir(os.path.join(JOBS_DIR, job)):
                return self._send(404, json.dumps({"ok": False, "error": "no such job"}))
            try:
                return self._send(200, json.dumps(sample_lithium(job, lat, lon)))
            except Exception as e:
                return self._send(500, json.dumps({"ok": False, "error": str(e)}))
        if self.path.split("?")[0] == "/api/point":
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            try:
                job = q["job"][0]
                lat, lon = float(q["lat"][0]), float(q["lon"][0])
            except (KeyError, IndexError, ValueError):
                return self._send(400, json.dumps(
                    {"ok": False, "error": "need job, lat, lon"}))
            if not os.path.isdir(os.path.join(JOBS_DIR, job)) or "/" in job or ".." in job:
                return self._send(404, json.dumps({"ok": False, "error": "no such job"}))
            try:
                return self._send(200, json.dumps(sample_point(job, lat, lon)))
            except Exception as e:
                return self._send(500, json.dumps({"ok": False, "error": str(e)}))
        if self.path.startswith("/jobs/"):
            rel = self.path.split("?")[0].lstrip("/")   # jobs/x/<job>/<file>
            parts = rel.split("/")[2:]                    # [<job>, (overlays,) <file>]
            if any(p in ("", ".", "..") for p in parts):
                return self._send(400, "bad path", "text/plain")
            fp = os.path.join(JOBS_DIR, *parts)
            if os.path.commonpath([os.path.abspath(fp), JOBS_DIR]) != JOBS_DIR:
                return self._send(400, "bad path", "text/plain")
            if os.path.isfile(fp):
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), "image/png")
            return self._send(404, "not found", "text/plain")
        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/analyze":
            return self._send(404, json.dumps({"ok": False, "error": "no route"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            lat, lon, km = float(req["lat"]), float(req["lon"]), float(req.get("km", 12))
        except Exception as e:
            return self._send(400, json.dumps({"ok": False, "error": f"bad request: {e}"}))

        job = hashlib.md5(f"{lat:.4f}_{lon:.4f}_{km}".encode()).hexdigest()[:10]
        out = os.path.join(JOBS_DIR, job)
        cached = os.path.join(out, "result.json")
        try:
            from_cache = os.path.isfile(cached) and os.path.isfile(
                os.path.join(out, "lithium_prospectivity.png"))
            if from_cache:
                meta = json.load(open(cached))     # instant repeat clicks
                meta = ensure_overlays(out, meta)  # backfill for pre-overlay caches
            else:
                with _lock:
                    meta, _ = engine_run(lat, lon, km, out, deposits_latlon=DEPOSITS)
            resp = {
                "ok": True, "base": f"/jobs/x/{job}",
                "job": job,
                "cached": from_cache,
                "coverage": round(meta["coverage"] * 100),
                "tiles": len(meta.get("tiles_used", [])),
                "date_range": meta.get("date_range", ""),
                "caveat": meta.get("capability_note", ""),
                "deposit_check": meta.get("deposit_check", []),
                # --- new, additive fields for the Explorer console ---
                "overlay_corners": meta.get("overlay_corners"),
                "overlay_layers": meta.get("overlay_layers", []),
                "confidence_summary": meta.get("confidence_summary", {}),
                "bbox_lonlat": meta.get("bbox_lonlat"),
                "crs": meta.get("crs"),
                "grid": meta.get("grid"),
                "rock_fraction": meta.get("rock_fraction"),
                "playa_fraction": meta.get("playa_fraction"),
                "tiles_used": meta.get("tiles_used", []),
            }
            return self._send(200, json.dumps(resp))
        except Exception as e:
            return self._send(500, json.dumps({"ok": False, "error": str(e)}))


if __name__ == "__main__":
    print(f"Mineral prospectivity demo -> http://localhost:{PORT}")
    print(f"Jobs saved to {JOBS_DIR}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

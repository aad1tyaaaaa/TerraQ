'use client'

// Live Analysis panel — click an area, the Sentinel-2 engine returns
// lithium / vanadium surface-alteration prospectivity overlays.
// Dark basemap + clear deposit markers + legend, matching the terraq theme.
//
// Talks to the Python engine (product/server.py). Override with
// NEXT_PUBLIC_ENGINE_URL; defaults to http://localhost:8765.

import { useEffect, useRef, useState } from 'react'
import { Satellite, Loader2, ArrowLeft } from 'lucide-react'

const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL || 'http://localhost:8765'
const CYAN = '#00F2FF'

// Known USGS MRDS deposits drawn on the map for reference.
// Quick presets — all real USGS MRDS occurrences in the Clayton Valley / Silver Peak
// lithium district, plus the nearest catalogued vanadium site for contrast.
const PRESETS: { label: string; lat: number; lon: number; km?: number; hint: string }[] = [
  { label: 'Silver Peak (Li)',  lat: 37.7499, lon: -117.6342, km: 12,
    hint: 'Albemarle Silver Peak — the only producing lithium mine in the USA' },
  { label: 'Clayton Valley',    lat: 37.7800, lon: -117.6000, km: 15,
    hint: 'Basin-wide view of the Clayton Valley lithium district' },
  { label: 'Foote Lithium',     lat: 37.7585, lon: -117.5912, km: 10,
    hint: 'Foote Lithium Brine Operation — rock-hosted alteration scores ~97th pct' },
  { label: 'Silver Peak Ops',   lat: 37.7672, lon: -117.5833, km: 10,
    hint: 'Silver Peak Lithium Operations, north-east of the main mine' },
  { label: 'Silver Peak Marsh', lat: 37.7527, lon: -117.6398, km: 10,
    hint: 'The brine playa — scores LOW by design; optical RS cannot see brine Li' },
  { label: 'Foote Mineral Co',  lat: 37.8468, lon: -117.5412, km: 12,
    hint: 'Northern end of the district' },
  { label: 'Mohawk Mine (V)',   lat: 37.7291, lon: -117.8134, km: 10,
    hint: 'Nearest catalogued vanadium occurrence — low-confidence V proxy' },
]

const MRDS: { name: string; lat: number; lon: number; kind: 'Li' | 'V' }[] = [
  { name: 'Silver Peak (Li mine)', lat: 37.7499, lon: -117.6342, kind: 'Li' },
  { name: 'Silver Peak Marsh', lat: 37.7527, lon: -117.6398, kind: 'Li' },
  { name: 'Foote Lithium Brine', lat: 37.7585, lon: -117.5912, kind: 'Li' },
  { name: 'Silver Peak Lithium Ops', lat: 37.7672, lon: -117.5833, kind: 'Li' },
  { name: 'Foote Mineral Co', lat: 37.8468, lon: -117.5412, kind: 'Li' },
  { name: 'Lithium Occurrence', lat: 37.1103, lon: -117.7056, kind: 'Li' },
  { name: 'Little Sand Spring Li', lat: 37.0999, lon: -117.4926, kind: 'Li' },
  { name: 'Mohawk Mine (V)', lat: 37.7291, lon: -117.8134, kind: 'V' },
  { name: 'Baxter Spring (V)', lat: 38.4383, lon: -117.1179, kind: 'V' },
  { name: 'Topaz Prospect (V)', lat: 38.7291, lon: -117.2037, kind: 'V' },
]

type DepositCheck = {
  name: string; type: string; li_score: number; li_percentile: number; v_score: number
}
type Result = {
  ok: boolean; error?: string; base?: string; coverage?: number; tiles?: number
  date_range?: string; caveat?: string; deposit_check?: DepositCheck[]
}

const LAYERS: [string, string, string][] = [
  ['Lithium Prospectivity', 'lithium_prospectivity.png', 'Clay / Al-OH alteration (2200 nm). Rock-hosted & pegmatite Li indicator — not brine Li.'],
  ['Vanadium Prospectivity', 'vanadium_prospectivity.png', 'Iron-oxide + mica composite. Low-confidence proxy; black-shale V is not detectable.'],
  ['Brine Favorability', 'brine_favorability.png', 'Indirect playa / evaporite basin flag — a follow-up-with-geophysics hint, not a detection.'],
  ['Sentinel-2 RGB', 'rgb.png', 'True-colour basemap of the analysed area.'],
  ['Confidence', 'confidence.png', 'Data quality: rock = high; vegetation / water / nodata = low.'],
]

const CARD =
  'rounded-2xl border border-white/12 bg-white/[0.04] shadow-[0_8px_24px_rgba(0,242,255,0.06),inset_0_1px_0_rgba(255,255,255,0.12)]'

export function TerraQLiveAnalysis() {
  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMap = useRef<any>(null)
  const markerRef = useRef<any>(null)
  const circleRef = useRef<any>(null)
  const radiusRaf = useRef<number | null>(null)
  const [lat, setLat] = useState(37.7499)
  const [lon, setLon] = useState(-117.6342)
  const [km, setKm] = useState(12)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [result, setResult] = useState<Result | null>(null)

  useEffect(() => {
    if (!document.getElementById('leaflet-css')) {
      const css = document.createElement('link')
      css.id = 'leaflet-css'
      css.rel = 'stylesheet'
      css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
      document.head.appendChild(css)
    }
    const init = () => {
      const L = (window as any).L
      if (!L || !mapRef.current || leafletMap.current) return
      const map = L.map(mapRef.current, { zoomControl: true }).setView([lat, lon], 11)
      // Standard OpenStreetMap basemap (readable, shows terrain & roads).
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19, attribution: '© OpenStreetMap',
      }).addTo(map)

      // Known deposits as clear coloured dots with hover labels.
      MRDS.forEach(d => {
        L.circleMarker([d.lat, d.lon], {
          radius: 6, weight: 2,
          color: d.kind === 'Li' ? CYAN : '#f59e0b',
          fillColor: d.kind === 'Li' ? CYAN : '#f59e0b',
          fillOpacity: 0.55,
        }).addTo(map).bindTooltip(
          `${d.name} — known ${d.kind === 'Li' ? 'lithium' : 'vanadium'} site`,
          { direction: 'top' })
      })

      // Live search-radius circle (animates as the slider changes).
      circleRef.current = L.circle([lat, lon], {
        radius: km * 1000, color: CYAN, weight: 2, opacity: 0.9,
        fillColor: CYAN, fillOpacity: 0.08, dashArray: '6 6',
      }).addTo(map)

      // Selected-location marker (on top of the circle).
      markerRef.current = L.marker([lat, lon]).addTo(map)
        .bindTooltip('Your selected location', { permanent: false })

      // Legend.
      const legend = L.control({ position: 'bottomright' })
      legend.onAdd = () => {
        const div = L.DomUtil.create('div')
        div.style.cssText =
          'background:rgba(10,14,20,.85);border:1px solid rgba(255,255,255,.15);' +
          'border-radius:10px;padding:8px 10px;font:11px system-ui;color:#e7ecf3;line-height:1.6'
        div.innerHTML =
          `<div style="font-weight:600;margin-bottom:4px">Legend</div>` +
          `<div><span style="display:inline-block;width:18px">📍</span> Selected location</div>` +
          `<div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${CYAN};margin-right:7px"></span>Known lithium site (USGS)</div>` +
          `<div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#f59e0b;margin-right:7px"></span>Known vanadium site (USGS)</div>`
        return div
      }
      legend.addTo(map)

      map.on('click', (e: any) => {
        setLat(+e.latlng.lat.toFixed(4))
        setLon(+e.latlng.lng.toFixed(4))
        markerRef.current.setLatLng(e.latlng)
      })
      leafletMap.current = map
    }
    if ((window as any).L) { init() } else {
      const s = document.createElement('script')
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
      s.onload = init
      document.body.appendChild(s)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Move the marker + radius circle (and pan to it) when coordinates change.
  useEffect(() => {
    if (!leafletMap.current) return
    markerRef.current?.setLatLng([lat, lon])
    circleRef.current?.setLatLng([lat, lon])
    leafletMap.current.panTo([lat, lon], { animate: true, duration: 0.4 })
  }, [lat, lon])

  // Smoothly animate the circle radius when the slider changes.
  useEffect(() => {
    const circle = circleRef.current
    if (!circle) return
    const target = km * 1000
    const start = circle.getRadius()
    if (Math.abs(target - start) < 1) { circle.setRadius(target); return }
    if (radiusRaf.current) cancelAnimationFrame(radiusRaf.current)
    const t0 = performance.now(), dur = 300
    const step = (now: number) => {
      const p = Math.min(1, (now - t0) / dur)
      const e = 1 - Math.pow(1 - p, 3) // ease-out
      circle.setRadius(start + (target - start) * e)
      if (p < 1) radiusRaf.current = requestAnimationFrame(step)
    }
    radiusRaf.current = requestAnimationFrame(step)
  }, [km])

  function reset() {
    setResult(null)
    setStatus('')
  }

  async function analyze() {
    setLoading(true); setResult(null)
    setStatus('Fetching Sentinel-2 and computing mineral indices (a new location can take 1–3 min)…')
    try {
      const r = await fetch(`${ENGINE}/api/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat, lon, km }),
      })
      const d: Result = await r.json()
      if (!d.ok) { setStatus('⚠ ' + (d.error || 'Analysis failed')); setLoading(false); return }
      setResult(d)
      setStatus(`✓ Done — ${d.coverage}% coverage, ${d.tiles} tile(s), ${d.date_range}`)
    } catch (e: any) {
      setStatus(`⚠ Request failed: ${e.message}. Is the engine running at ${ENGINE}?`)
    }
    setLoading(false)
  }

  const inputCls =
    'block bg-white/6 border border-white/15 rounded-xl px-3 py-2 text-sm w-full mt-1 text-white focus:outline-none focus:border-[#00F2FF]/60'

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tight">Live Analysis</h1>
        <p className="text-muted-foreground text-lg">
          Click a location on the map (or enter coordinates) to analyse it for lithium /
          vanadium surface alteration from live Sentinel-2 imagery.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">
        <div ref={mapRef}
          className="lg:col-span-3 h-[460px] lg:h-[620px] rounded-2xl overflow-hidden border border-white/12 z-0" />

        <div className={`${CARD} p-6 lg:col-span-2`}>
          <p className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: CYAN }}>Target Area</p>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs text-muted-foreground">Latitude
              <input value={lat} onChange={e => setLat(+e.target.value)} className={inputCls} />
            </label>
            <label className="text-xs text-muted-foreground">Longitude
              <input value={lon} onChange={e => setLon(+e.target.value)} className={inputCls} />
            </label>
          </div>
          <div className="mt-4">
            <div className="flex justify-between text-xs text-muted-foreground mb-1">
              <span>Search radius</span><span className="font-mono" style={{ color: CYAN }}>{km} km</span>
            </div>
            <input type="range" min={4} max={20} value={km} onChange={e => setKm(+e.target.value)}
              className="w-full" style={{ accentColor: CYAN }} />
          </div>

          {/* Big, obviously-clickable Analyze button */}
          <button onClick={analyze} disabled={loading}
            className="mt-5 w-full flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-white text-sm font-bold tracking-wide disabled:opacity-60 transition-transform active:scale-[0.98] hover:brightness-110"
            style={{ background: CYAN, boxShadow: '0 6px 22px rgba(0,242,255,0.35)' }}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Satellite className="w-4 h-4" />}
            {loading ? 'Analyzing…' : 'Analyze this area'}
          </button>

          <div className="mt-4 text-xs">
            <span className="text-muted-foreground">Quick presets</span>
            <span className="text-muted-foreground/60"> — Clayton Valley lithium district (Esmeralda Co., NV)</span>
            <div className="flex flex-wrap gap-2 mt-2">
              {PRESETS.map(p => {
                const active = Math.abs(lat - p.lat) < 1e-4 && Math.abs(lon - p.lon) < 1e-4
                return (
                  <button key={p.label} title={p.hint}
                    onClick={() => { setLat(p.lat); setLon(p.lon); if (p.km) setKm(p.km) }}
                    className="rounded-lg px-3 py-1.5 border transition hover:bg-white/15"
                    style={active
                      ? { background: 'rgba(0,242,255,0.15)', borderColor: CYAN, color: CYAN }
                      : { background: 'rgba(255,255,255,0.10)', borderColor: 'rgba(255,255,255,0.12)' }}>
                    {p.label}
                  </button>
                )
              })}
            </div>
          </div>
          <p className="text-sm text-muted-foreground mt-4 min-h-[20px]">{status}</p>

          {result?.caveat && (
            <div className="text-[11px] leading-relaxed text-amber-300/90 bg-amber-400/5 border border-amber-400/25 rounded-xl p-3 mt-2">
              <b>How to read this:</b> {result.caveat}
            </div>
          )}

          {result?.deposit_check && result.deposit_check.length > 0 && (
            <table className="w-full text-[11px] mt-3">
              <thead><tr className="text-muted-foreground text-left">
                <th className="py-1">Known deposit (USGS MRDS)</th><th>type</th><th>Li</th><th>%ile</th><th>V</th>
              </tr></thead>
              <tbody>
                {result.deposit_check.map((x, i) => (
                  <tr key={i} className="border-t border-white/8">
                    <td className="py-1">{x.name}</td>
                    <td><span className={x.type === 'rock' ? 'text-emerald-400' : 'text-fuchsia-400'}>{x.type}</span></td>
                    <td>{x.li_score}</td><td>{x.li_percentile}</td><td>{x.v_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {result?.base && (
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold tracking-tight">Results</h2>
          <button onClick={reset}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 border border-white/15 text-sm font-semibold transition">
            <ArrowLeft className="w-4 h-4" /> New analysis
          </button>
        </div>
      )}

      {result?.base && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {LAYERS.map(([title, file, desc]) => (
            <div key={file} className={`${CARD} p-3 overflow-hidden`}>
              <div className="text-sm font-semibold px-1">{title}</div>
              <div className="text-[11px] text-muted-foreground mb-2 px-1">{desc}</div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`${ENGINE}${result.base}/${file}?t=${Date.now()}`}
                alt={title} loading="lazy" className="w-full rounded-xl border border-white/10" />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

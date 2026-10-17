'use client'

// MapLibre globe. Loaded via next/dynamic with ssr:false from ExplorerShell —
// MapLibre touches `window` at module scope and cannot be server-rendered.
//
// Basemap strategy (both key-free):
//   z0–8   NASA GIBS Blue Marble (EPSG:3857 / GoogleMapsCompatible). GIBS only
//          serves this product to z8, so it is capped there.
//   z8–19  EOX Sentinel-2 cloudless. Attribution is required and shown.
// MapLibre does not swap sources by zoom on its own, so these are two raster
// layers with explicit minzoom/maxzoom.
//
// Score overlays use an `image` source positioned by the four EPSG:4326 corners
// the engine returns (`overlay_corners`). The engine warps to 4326 before
// writing the PNG, so the image is axis-aligned and there is no UTM skew.

import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import depositsGeojson from '../data/deposits.json'
import { OVERLAY_LAYERS } from '../lib/presets'
import type { Corners, FoundTarget } from '../lib/types'

const CYAN = '#00F2FF'
const AMBER = '#f59e0b'

const GIBS =
  'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg'
const EOX = 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg'

export interface GlobeMapProps {
  lat: number
  lon: number
  km: number
  activeLayer: string
  overlayBase: string | null
  overlayCorners: Corners | null
  availableLayers: string[]
  /** S2 targets drawn as numbered markers. */
  targets?: FoundTarget[]
  activeTargetId?: string | null
  onPick: (lat: number, lon: number) => void
  onTargetClick?: (t: FoundTarget) => void
}

export default function GlobeMap({
  lat, lon, km, activeLayer, overlayBase, overlayCorners, availableLayers,
  targets = [], activeTargetId = null, onPick, onTargetClick,
}: GlobeMapProps) {
  const host = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const marker = useRef<maplibregl.Marker | null>(null)
  const ready = useRef(false)
  const flown = useRef(false)
  const onPickRef = useRef(onPick)
  onPickRef.current = onPick
  const targetMarkers = useRef<maplibregl.Marker[]>([])
  const onTargetRef = useRef(onTargetClick)
  onTargetRef.current = onTargetClick

  // --- init once ----------------------------------------------------------
  useEffect(() => {
    if (!host.current || map.current) return

    let flyTimer: number | undefined
    let resizeObs: ResizeObserver | undefined

    const m = new maplibregl.Map({
      container: host.current,
      center: [lon, lat],
      zoom: 2.2,
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          gibs: {
            type: 'raster', tiles: [GIBS], tileSize: 256, maxzoom: 8,
            attribution: 'Imagery &copy; NASA EOSDIS GIBS (Blue Marble)',
          },
          eox: {
            type: 'raster', tiles: [EOX], tileSize: 256, maxzoom: 19,
            attribution:
              'Sentinel-2 cloudless 2020 by <a href="https://eox.at" target="_blank" rel="noreferrer">EOX IT Services GmbH</a> (contains modified Copernicus Sentinel data 2020)',
          },
        },
        layers: [
          { id: 'bg', type: 'background', paint: { 'background-color': '#05080c' } },
          { id: 'gibs', type: 'raster', source: 'gibs', maxzoom: 8 },
          { id: 'eox', type: 'raster', source: 'eox', minzoom: 8 },
        ],
      },
    })
    map.current = m

    m.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right')
    m.addControl(new maplibregl.AttributionControl({ compact: false }), 'bottom-right')
    m.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left')

    m.on('style.load', () => {
      // Globe projection (MapLibre v5+). Falls back silently on older builds.
      try { m.setProjection({ type: 'globe' }) } catch { /* mercator is fine */ }

      // --- MRDS reference sites ------------------------------------------
      m.addSource('deposits', { type: 'geojson', data: depositsGeojson as any })
      m.addLayer({
        id: 'deposits-glow', type: 'circle', source: 'deposits',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 6, 12, 18],
          'circle-color': ['match', ['get', 'commodity'], 'lithium', CYAN, AMBER],
          'circle-opacity': 0.18, 'circle-blur': 0.9,
        },
      })
      m.addLayer({
        id: 'deposits-dot', type: 'circle', source: 'deposits',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3, 12, 6],
          'circle-color': ['match', ['get', 'commodity'], 'lithium', CYAN, AMBER],
          'circle-stroke-width': 1.5, 'circle-stroke-color': '#04121a',
        },
      })

      const popup = new maplibregl.Popup({ closeButton: false, offset: 10 })
      m.on('mouseenter', 'deposits-dot', e => {
        m.getCanvas().style.cursor = 'pointer'
        const f: any = e.features?.[0]
        if (!f) return
        const p = f.properties
        popup.setLngLat(f.geometry.coordinates.slice())
          .setHTML(
            `<div style="font:12px system-ui;color:#0b0e14">
               <b>${p.site}</b><br/>USGS MRDS reference site
               <br/>commodity: ${p.commodity}${p.mrds_status ? ` · ${p.mrds_status}` : ''}
             </div>`)
          .addTo(m)
      })
      m.on('mouseleave', 'deposits-dot', () => {
        m.getCanvas().style.cursor = ''
        popup.remove()
      })

      // --- AOI ring --------------------------------------------------------
      m.addSource('aoi', { type: 'geojson', data: ringFeature(lat, lon, km) })
      m.addLayer({
        id: 'aoi-fill', type: 'fill', source: 'aoi',
        paint: { 'fill-color': CYAN, 'fill-opacity': 0.06 },
      })
      m.addLayer({
        id: 'aoi-line', type: 'line', source: 'aoi',
        paint: { 'line-color': CYAN, 'line-width': 1.5, 'line-dasharray': [3, 2] },
      })

      marker.current = new maplibregl.Marker({ color: CYAN })
        .setLngLat([lon, lat]).addTo(m)

      ready.current = true

      // Fly in from the globe so the first impression is the whole Earth.
      // `idle` alone is not reliable here: at globe zoom the basemap keeps
      // streaming tiles, so idle can be delayed indefinitely and the fly-in
      // never happens. Whichever of idle / timeout comes first wins, guarded so
      // it only ever runs once.
    })

    // Intro fly-in: globe first, then down to the selected area.
    // Scheduled here rather than from a style event — whether `style.load` has
    // already fired by the time a listener attaches is timing-dependent, and a
    // missed event left the map stuck at globe zoom. A plain timer always runs;
    // the instance check keeps React StrictMode's discarded first map from
    // flying (or from claiming the one-shot flag).
    flyTimer = window.setTimeout(() => {
      if (flown.current || map.current !== m) return
      flown.current = true
      m.flyTo({ center: [lon, lat], zoom: 10.5, duration: 3200, essential: true })
    }, 2200)

    // The map lives in a user-resizable panel. MapLibre sizes its canvas from
    // the container at construction time and does NOT track later changes, so
    // without this the canvas keeps its old width and the globe ends up
    // stretched or clipped while dragging the splitter.
    // rAF-throttled: a drag fires a continuous stream of resize entries.
    let resizeRaf = 0
    const ro = new ResizeObserver(() => {
      if (resizeRaf) return
      resizeRaf = requestAnimationFrame(() => {
        resizeRaf = 0
        if (map.current === m) m.resize()
      })
    })
    ro.observe(host.current!)
    resizeObs = ro

    m.on('click', e => {
      // Ignore clicks that land on a deposit dot (the popup handles those).
      const hits = m.queryRenderedFeatures(e.point, { layers: ['deposits-dot'] })
      if (hits.length) {
        const c = (hits[0].geometry as any).coordinates
        onPickRef.current(+c[1].toFixed(4), +c[0].toFixed(4))
        return
      }
      onPickRef.current(+e.lngLat.lat.toFixed(4), +e.lngLat.lng.toFixed(4))
    })

    return () => {
      if (flyTimer) window.clearTimeout(flyTimer)
      resizeObs?.disconnect()
      m.remove()
      map.current = null
      ready.current = false
      // Must reset: React StrictMode mounts this twice in development, and a
      // stale `true` here would suppress the fly-in on the surviving mount.
      flown.current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // --- marker + AOI follow the selection ----------------------------------
  useEffect(() => {
    const m = map.current
    if (!m || !ready.current) return
    marker.current?.setLngLat([lon, lat])
    const src = m.getSource('aoi') as maplibregl.GeoJSONSource | undefined
    src?.setData(ringFeature(lat, lon, km) as any)
    m.easeTo({ center: [lon, lat], duration: 700 })
  }, [lat, lon, km])

  // --- score overlay ------------------------------------------------------
  useEffect(() => {
    const m = map.current
    if (!m || !ready.current) return

    const spec = OVERLAY_LAYERS.find(l => l.id === activeLayer)
    const have = spec && availableLayers.includes(spec.file)

    if (m.getLayer('overlay')) m.removeLayer('overlay')
    if (m.getSource('overlay')) m.removeSource('overlay')
    if (!overlayBase || !overlayCorners || !spec || !have) return

    m.addSource('overlay', {
      type: 'image',
      // overlay_export.py writes the bare PNGs into <job>/overlays/.
      url: `${overlayBase}/overlays/${spec.file}?t=${Date.now()}`,
      coordinates: overlayCorners,
    })
    m.addLayer(
      { id: 'overlay', type: 'raster', source: 'overlay', paint: { 'raster-opacity': 0.85 } },
      m.getLayer('deposits-glow') ? 'deposits-glow' : undefined,
    )
  }, [activeLayer, overlayBase, overlayCorners, availableLayers])

  // --- S2: numbered target markers ---------------------------------------
  useEffect(() => {
    const m = map.current
    if (!m || !ready.current) return

    targetMarkers.current.forEach(mk => mk.remove())
    targetMarkers.current = []

    targets.forEach(t => {
      const el = document.createElement('button')
      el.textContent = String(t.rank)
      const active = activeTargetId === t.id
      el.style.cssText =
        `width:22px;height:22px;border-radius:50%;cursor:pointer;` +
        `font:700 11px system-ui;display:grid;place-items:center;` +
        `color:#04121a;background:${active ? '#fff' : CYAN};` +
        `border:2px solid ${active ? CYAN : '#04121a'};` +
        `box-shadow:0 0 0 ${active ? 6 : 3}px rgba(0,242,255,0.25);`
      el.title =
        `Target ${t.id} — ${t.area_km2.toFixed(2)} km², peak ${t.peak_percentile}th pct` +
        (t.nearest_reference_site
          ? `\nnearest known site: ${t.nearest_reference_site} (${t.nearest_reference_km} km)`
          : '')
      el.addEventListener('click', ev => {
        ev.stopPropagation()
        onTargetRef.current?.(t)
      })
      targetMarkers.current.push(
        new maplibregl.Marker({ element: el })
          .setLngLat([t.centroid_lon, t.centroid_lat])
          .addTo(m),
      )
    })

    return () => {
      targetMarkers.current.forEach(mk => mk.remove())
      targetMarkers.current = []
    }
  }, [targets, activeTargetId])

  // h-full/w-full, NOT absolute inset-0: maplibre-gl.css declares
  // `.maplibregl-map { position: relative }`, which has the same specificity as
  // Tailwind's `.absolute` and loads later, so it wins — `inset-0` then does
  // nothing and the container collapses to 0 height.
  return <div ref={host} className="h-full w-full" />
}

/** Circle of radius km as a GeoJSON polygon (64-gon), corrected for latitude. */
function ringFeature(lat: number, lon: number, km: number) {
  const pts: [number, number][] = []
  const dLat = km / 111.32
  const dLon = km / (111.32 * Math.cos((lat * Math.PI) / 180))
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * Math.PI * 2
    pts.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)])
  }
  return {
    type: 'Feature' as const,
    properties: {},
    geometry: { type: 'Polygon' as const, coordinates: [pts] },
  }
}

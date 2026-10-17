'use client'

// Explorer console: globe + controls + analysis panel + targets.
// Reuses the existing UI primitives (Badge, Button, Tabs, Skeleton) — no second
// component library is introduced.

import { useCallback, useEffect, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import Link from 'next/link'
import {
  Satellite, Loader2, Search, ArrowLeft, WifiOff, Database, Printer, Crosshair,
  Sparkles, FlaskConical, X,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { LocationPanel } from './LocationPanel'
import { TargetsPanel } from './TargetsPanel'
import { FoundTargets } from './FoundTargets'
import { AskPanel } from './AskPanel'
import { ValidationCard } from './ValidationCard'
import { ScanOverlay } from './ScanOverlay'
import {
  ResizablePanelGroup, ResizablePanel, ResizableHandle,
} from '@/components/ui/resizable'
import { PRESETS, MINERALS, OVERLAY_LAYERS } from '../lib/presets'
import { useGeology } from '../lib/useGeology'
import { parseCoordinates, formatCoord } from '../lib/coords'
import { buildMeta } from '../lib/exportTargets'
import { searchGazetteer, isUndetectable, type GazetteerSite } from '../lib/gazetteer'
import {
  analyze, samplePoint, sampleLithium, fetchTargets, fetchJobs,
  engineReachable, ENGINE,
} from '../lib/engine'
import type {
  AnalyzeResult, JobSummary, PointResponse, SampleResponse,
  TargetsResponse, FoundTarget,
} from '../lib/types'

// MapLibre reads `window` at import time, so it cannot be server-rendered.
const GlobeMap = dynamic(() => import('./GlobeMap'), {
  ssr: false,
  loading: () => <div className="h-full w-full grid place-items-center text-zinc-500 text-sm">Loading globe…</div>,
})

const CYAN = '#00F2FF'

export function ExplorerShell() {
  const [lat, setLat] = useState(37.7499)
  const [lon, setLon] = useState(-117.6342)
  const [km, setKm] = useState(12)
  const [label, setLabel] = useState<string | null>('Silver Peak (Li)')

  const [result, setResult] = useState<AnalyzeResult | null>(null)
  const [point, setPoint] = useState<PointResponse | null>(null)
  const [sample, setSample] = useState<SampleResponse | null>(null)
  const [targets, setTargets] = useState<TargetsResponse | null>(null)
  const [targetsLoading, setTargetsLoading] = useState(false)
  const [activeTarget, setActiveTarget] = useState<FoundTarget | null>(null)
  const [targetTab, setTargetTab] = useState<'detected' | 'known'>('detected')
  const [askOpen, setAskOpen] = useState(false)
  const [validationOpen, setValidationOpen] = useState(false)
  const [layer, setLayer] = useState('lithium')
  const [mineral, setMineral] = useState('lithium')

  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [online, setOnline] = useState<boolean | null>(null)

  // S5: one geology lookup for the selected point, shared with the panel and S3.
  const { unit: geology, state: geoState } = useGeology(lat, lon)

  const [query, setQuery] = useState('')
  const searchTimer = useRef<number | null>(null)

  // --- engine reachability + cached jobs ----------------------------------
  const refreshJobs = useCallback(async () => {
    const up = await engineReachable()
    setOnline(up)
    if (up) {
      try { setJobs(await fetchJobs()) } catch { /* keep previous */ }
    }
  }, [])

  useEffect(() => { refreshJobs() }, [refreshJobs])

  /** Is the current (lat,lon,km) already cached? Then "Analyze" is instant. */
  const cachedJob = jobs.find(
    j => Math.abs(j.lat - lat) < 1e-3 && Math.abs(j.lon - lon) < 1e-3 && Math.abs(j.km - km) < 0.6,
  )

  // --- analysis ------------------------------------------------------------
  async function runAnalysis() {
    setLoading(true); setResult(null); setPoint(null); setSample(null)
    setTargets(null); setActiveTarget(null)
    setStatus(cachedJob
      ? 'Loading cached result…'
      : 'Fetching Sentinel-2 and computing indices — a new location takes 1–3 min…')
    try {
      const d = await analyze(lat, lon, km)
      if (!d.ok) { setStatus(`⚠ ${d.error || 'Analysis failed'}`); setLoading(false); return }
      setResult(d)
      setStatus(`${d.cached ? 'Cached' : 'Computed'} — ${d.coverage}% coverage, ${d.tiles} tile(s), ${d.date_range}`)
      // S1 + vanadium in parallel; both are fast local raster reads.
      try {
        const [sm, pt] = await Promise.all([
          sampleLithium(d.job, lat, lon).catch(() => null),
          samplePoint(d.job, lat, lon).catch(() => null),
        ])
        setSample(sm); setPoint(pt)
      } catch { setSample(null); setPoint(null) }
      // S2: targets are derived from the raster; generated on first request.
      setTargetsLoading(true)
      fetchTargets(d.job)
        .then(t => setTargets(t))
        .catch(() => setTargets(null))
        .finally(() => setTargetsLoading(false))
      refreshJobs()
    } catch (e: any) {
      setOnline(false)
      setStatus(`⚠ Engine unreachable at ${ENGINE}. Showing cached areas only.`)
    }
    setLoading(false)
  }

  // Re-sample the point when the user moves inside an already-analysed scene.
  useEffect(() => {
    if (!result?.job) return
    let cancelled = false
    Promise.all([
      sampleLithium(result.job, lat, lon).catch(() => null),
      samplePoint(result.job, lat, lon).catch(() => null),
    ]).then(([sm, pt]) => {
      if (cancelled) return
      setSample(sm); setPoint(pt)
    })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, lon])

  function pick(newLat: number, newLon: number, name?: string) {
    setLat(newLat); setLon(newLon); setLabel(name ?? null)
  }

  /** Fly to a detected target and re-sample (S1) at its centroid. */
  function selectTarget(t: FoundTarget) {
    setActiveTarget(t)
    pick(t.centroid_lat, t.centroid_lon, `Target ${t.id} · ${t.area_km2.toFixed(2)} km²`)
  }

  // --- geocoding (Nominatim, via our own throttled route) ------------------
  type Hit = {
    name: string; context: string; lat: number; lon: number
    kind?: string; approximate?: boolean
  }
  const [hits, setHits] = useState<Hit[]>([])
  const [searching, setSearching] = useState(false)
  const [searchNote, setSearchNote] = useState<string | null>(null)
  /** A pasted coordinate resolves instantly, with no network call at all. */
  const typedCoord = parseCoordinates(query)
  /** Known mineral sites, matched locally — instant and immune to geocoder limits. */
  const siteHits: GazetteerSite[] = typedCoord ? [] : searchGazetteer(query)

  function onQuery(v: string) {
    setQuery(v)
    if (searchTimer.current) window.clearTimeout(searchTimer.current)

    // Coordinates are answered locally — don't spend a geocode call on them.
    setSearchNote(null)
    if (parseCoordinates(v)) { setHits([]); setSearching(false); return }
    if (v.trim().length < 2) { setHits([]); setSearching(false); return }

    setSearching(true)
    searchTimer.current = window.setTimeout(async () => {
      try {
        const r = await fetch(`/api/geocode?q=${encodeURIComponent(v)}`)
        const d = await r.json()
        setHits(d.results ?? [])
        setSearchNote(d.message ?? null)
      } catch { setHits([]) } finally { setSearching(false) }
    }, 250)
  }

  function choose(la: number, lo: number, label: string) {
    pick(la, lo, label)
    setHits([]); setQuery(''); setActiveTarget(null)
  }

  const activeMineral = MINERALS.find(m => m.id === mineral)

  return (
    <div className="h-screen w-full flex flex-col bg-[#05080c] text-zinc-100 overflow-hidden">
      {/* ── top bar ─────────────────────────────────────────────── */}
      <header className="flex items-center gap-3 px-4 py-2.5 border-b border-white/10 shrink-0">
        {/* Site identity — the Explorer is a route of the terraq site, not a
            detached tool, so it carries the same logo and a route back in. */}
        <Link href="/" className="flex items-center gap-2 shrink-0 group">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/terraq-mark.png" alt="TerraQ"
               className="h-7 w-7 rounded-full object-cover ring-1 ring-cyan-400/25" />
          <span className="text-sm font-semibold tracking-wide hidden sm:block
                           group-hover:text-cyan-300 transition-colors">
            TerraQ
          </span>
        </Link>

        <span className="text-white/15 hidden sm:block">/</span>

        <Link href="/dashboard"
              className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 shrink-0">
          <ArrowLeft className="w-3.5 h-3.5" /> Dashboard
        </Link>

        <span className="text-xs font-semibold text-cyan-300 hidden md:block shrink-0">
          Explorer
        </span>

        <div className="relative flex-1 max-w-md">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            value={query}
            onChange={e => onQuery(e.target.value)}
            placeholder="Search a place, or paste 34.08, 74.80"
            className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-1.5 text-xs
                       focus:outline-none focus:border-cyan-400/50"
          />
          {(typedCoord || searching || hits.length > 0 || siteHits.length > 0) && query.trim() && (
            <div className="absolute z-20 mt-1 w-full rounded-lg border border-white/15
                            bg-[#0b1118] shadow-xl max-h-72 overflow-y-auto">
              {/* A pasted coordinate — offered immediately, no lookup needed. */}
              {typedCoord && (
                <button
                  onClick={() => choose(typedCoord.lat, typedCoord.lon,
                                        formatCoord(typedCoord.lat, typedCoord.lon))}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-white/10">
                  <Crosshair className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span className="text-[13px] font-mono">
                    {formatCoord(typedCoord.lat, typedCoord.lon)}
                  </span>
                  <span className="ml-auto text-[11px] text-zinc-500">
                    go to coordinate
                  </span>
                </button>
              )}

              {/* Known mineral sites first — this is the tool's own domain, and
                  these names (Katghora, Marlagalla-Allapatna, Papum Pare …) are
                  absent from public geocoders. */}
              {siteHits.length > 0 && (
                <div className="border-b border-white/10">
                  <p className="px-3 pt-2 pb-1 text-[11px] text-zinc-500">
                    Reported mineral sites
                  </p>
                  {siteHits.map(st => (
                    <button key={st.label}
                            onClick={() => choose(st.lat, st.lon, st.label)}
                            className="block w-full text-left px-3 py-2 hover:bg-white/10">
                      <div className="flex items-baseline gap-2">
                        <span className="text-[13px] text-zinc-100 truncate">{st.label}</span>
                        <span className={`text-[10px] px-1.5 rounded shrink-0 ${
                          st.commodity === 'lithium'
                            ? 'bg-[#17a2b8]/20 text-[#5ecfe0]'
                            : 'bg-[#d95926]/20 text-[#eda100]'
                        }`}>
                          {st.commodity === 'lithium' ? 'Li' : 'V'}
                        </span>
                      </div>
                      <div className="flex items-baseline gap-2 text-[11px] text-zinc-500">
                        <span className="truncate">
                          {st.region}
                          {isUndetectable(st) && (
                            <span className="text-amber-300/80"> · not optically detectable</span>
                          )}
                        </span>
                        <span className="ml-auto font-mono shrink-0">
                          {st.lat.toFixed(3)}, {st.lon.toFixed(3)}
                        </span>
                      </div>
                      {st.reported && (
                        <div className="text-[11px] text-zinc-500 mt-0.5 truncate">
                          <span className="text-zinc-600">reported: </span>{st.reported}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}

              {searching && !typedCoord && (
                <div className="px-3 py-2 text-[12px] text-zinc-500">Searching…</div>
              )}

              {searchNote && (
                <div className="px-3 py-2 text-[11px] text-amber-300/80">{searchNote}</div>
              )}

              {hits[0]?.approximate && (
                <div className="px-3 pt-2 pb-1 text-[11px] text-amber-300/80">
                  No exact match — showing the nearest places found.
                </div>
              )}

              {hits.map((h, i) => (
                <button key={`${h.lat},${h.lon},${i}`}
                        onClick={() => choose(h.lat, h.lon, h.name)}
                        className="block w-full text-left px-3 py-2 hover:bg-white/10">
                  <div className="flex items-baseline gap-2">
                    <span className="text-[13px] text-zinc-100 truncate">{h.name}</span>
                    {h.kind && (
                      <span className="text-[11px] text-zinc-500 shrink-0">{h.kind}</span>
                    )}
                  </div>
                  <div className="flex items-baseline gap-2 text-[11px] text-zinc-500">
                    <span className="truncate">{h.context}</span>
                    <span className="ml-auto font-mono shrink-0">
                      {h.lat.toFixed(3)}, {h.lon.toFixed(3)}
                    </span>
                  </div>
                </button>
              ))}

              {!searching && !typedCoord && hits.length === 0 && siteHits.length === 0 && (
                <div className="px-3 py-2 text-[12px] text-zinc-500">
                  Nothing found. Try a broader name, or paste coordinates like
                  <span className="font-mono text-zinc-400"> 34.08, 74.80</span>.
                </div>
              )}
            </div>
          )}
        </div>

        <div className="font-mono text-[11px] text-zinc-400 hidden md:block">
          {lat.toFixed(4)}, {lon.toFixed(4)}
        </div>

        {online === false && (
          <Badge variant="outline" className="text-[10px] border-amber-400/40 text-amber-300 gap-1">
            <WifiOff className="w-3 h-3" /> engine offline
          </Badge>
        )}
        {cachedJob && (
          <Badge variant="outline" className="text-[10px] border-emerald-400/40 text-emerald-300 gap-1">
            <Database className="w-3 h-3" /> cached
          </Badge>
        )}

        <button
          onClick={() => { setValidationOpen(v => !v); setAskOpen(false) }}
          aria-pressed={validationOpen}
          title="How well does this index match known deposits?"
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border
                      transition shrink-0 ${
            validationOpen
              ? 'border-cyan-400/60 bg-cyan-400/15 text-cyan-200'
              : 'border-white/15 text-zinc-300 hover:bg-white/10'
          }`}>
          <FlaskConical className="w-3.5 h-3.5" />
          <span className="hidden lg:inline">Validation</span>
        </button>

        <button
          onClick={() => { setAskOpen(v => !v); setValidationOpen(false) }}
          aria-pressed={askOpen}
          title="Ask where to look (general knowledge, not measured)"
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border
                      transition shrink-0 ${
            askOpen
              ? 'border-violet-400/60 bg-violet-400/15 text-violet-200'
              : 'border-white/15 text-zinc-300 hover:bg-white/10'
          }`}>
          <Sparkles className="w-3.5 h-3.5" />
          <span className="hidden lg:inline">Ask</span>
        </button>

        <Button size="sm" onClick={runAnalysis} disabled={loading || online === false}
                className="gap-1.5 text-xs font-bold"
                style={{ background: CYAN, color: '#04121a' }}>
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                   : <Satellite className="w-3.5 h-3.5" />}
          {loading ? 'Analyzing…' : 'Analyze Region'}
        </Button>
      </header>

      {/* ── mineral chips ───────────────────────────────────────── */}
      <div className="flex items-center gap-1.5 px-4 py-2 border-b border-white/10 overflow-x-auto shrink-0">
        {MINERALS.map(m => (
          <button key={m.id}
                  disabled={!m.enabled}
                  title={m.note}
                  onClick={() => { if (m.enabled) { setMineral(m.id); setLayer(m.id) } }}
                  className={`shrink-0 rounded-full px-3 py-1 text-[11px] border transition ${
                    !m.enabled ? 'opacity-40 cursor-not-allowed border-white/10 text-zinc-500'
                    : mineral === m.id ? 'border-cyan-400/60 bg-cyan-400/15 text-cyan-300'
                    : 'border-white/15 text-zinc-300 hover:bg-white/10'
                  }`}>
            {m.label}
            {m.badge && (
              <span className="ml-1.5 text-[9px] opacity-70">({m.badge})</span>
            )}
          </button>
        ))}
      </div>

      {/*
        While the splitter is being dragged, suppress text selection across the
        page. Without this a drag that starts a few pixels off the handle
        highlights the panel's text instead of resizing, which is what it looked
        like in testing. Scoped to the drag state so normal copy/paste still works.
      */}
      <style>{`
        body:has([data-slot="resizable-handle"][data-resize-handle-state="drag"]) {
          user-select: none;
          -webkit-user-select: none;
          cursor: col-resize;
        }
      `}</style>

      {/* ── body ────────────────────────────────────────────────── */}
      {/*
        Drag the handle to trade map width for panel width. `autoSaveId` persists
        the split per browser, so a chosen layout survives a reload.
        The map panel has a real minimum so the globe never collapses to a sliver,
        and the analysis panel caps out before the map becomes useless.
      */}
      <ResizablePanelGroup
        direction="horizontal"
        autoSaveId="terraq-explorer-split"
        className="flex-1 min-h-0"
      >
        {/* map */}
        <ResizablePanel defaultSize={72} minSize={35} className="relative min-w-0">
          <GlobeMap
            lat={lat} lon={lon} km={km}
            activeLayer={layer}
            overlayBase={result ? `${ENGINE}${result.base}` : null}
            overlayCorners={result?.overlay_corners ?? null}
            availableLayers={result?.overlay_layers ?? []}
            targets={targets?.targets ?? []}
            activeTargetId={activeTarget?.id ?? null}
            onPick={(la, lo) => { setActiveTarget(null); pick(la, lo) }}
            onTargetClick={selectTarget}
          />

          {/* layer switch + legend */}
          {result?.overlay_corners && (
            <div className="absolute top-3 left-3 z-10 rounded-xl border border-white/15 bg-[#0b1118]/90 backdrop-blur p-2.5 max-w-[230px]">
              <p className="text-[9px] uppercase tracking-widest text-zinc-500 mb-1.5">Layer</p>
              <div className="flex flex-col gap-0.5">
                {OVERLAY_LAYERS.map(l => {
                  const have = result.overlay_layers?.includes(l.file)
                  return (
                    <button key={l.id}
                            disabled={!have}
                            title={have ? l.desc : 'Not available for this cached run'}
                            onClick={() => setLayer(l.id)}
                            className={`text-left text-[11px] rounded px-2 py-1 transition ${
                              !have ? 'opacity-35 cursor-not-allowed'
                              : layer === l.id ? 'bg-cyan-400/15 text-cyan-300'
                              : 'hover:bg-white/10 text-zinc-300'
                            }`}>
                      {l.label}
                    </button>
                  )
                })}
              </div>
              <div className="mt-2 pt-2 border-t border-white/10">
                <p className="text-[9px] text-zinc-400 mb-1">
                  {OVERLAY_LAYERS.find(l => l.id === layer)?.label} (relative, 0–1)
                </p>
                <div className="h-1.5 rounded-full"
                     style={{ background: 'linear-gradient(90deg,#000004,#51127c,#b73779,#fc8961,#fcfdbf)' }} />
                <div className="flex justify-between text-[9px] text-zinc-500 mt-0.5">
                  <span>Low</span><span>High</span>
                </div>
              </div>
            </div>
          )}

          {/* radius + presets */}
          {/* bottom-9 keeps clear of MapLibre's scale control at bottom-left. */}
          <div className="absolute bottom-9 left-3 z-10 rounded-xl border border-white/15 bg-[#0b1118]/90 backdrop-blur p-3 max-w-[330px]">
            <div className="flex justify-between text-[10px] text-zinc-400 mb-1">
              <span>Search radius</span>
              <span className="font-mono" style={{ color: CYAN }}>{km} km</span>
            </div>
            <input type="range" min={4} max={20} value={km}
                   onChange={e => setKm(+e.target.value)}
                   className="w-full" style={{ accentColor: CYAN }} />
            <div className="flex flex-wrap gap-1 mt-2">
              {PRESETS.map(p => (
                <button key={p.label} title={p.hint}
                        onClick={() => { setKm(p.km); pick(p.lat, p.lon, p.label) }}
                        className={`rounded px-2 py-0.5 text-[10px] border transition ${
                          Math.abs(lat - p.lat) < 1e-4 && Math.abs(lon - p.lon) < 1e-4
                            ? 'border-cyan-400/60 bg-cyan-400/15 text-cyan-300'
                            : 'border-white/15 text-zinc-300 hover:bg-white/10'
                        }`}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {status && !loading && (
            <div className="absolute top-3 right-3 z-10 max-w-xs rounded-lg border border-white/15 bg-[#0b1118]/90 backdrop-blur px-3 py-2 text-[11px] text-zinc-300">
              {status}
            </div>
          )}

          {/* Shown only while the engine is working. Scoped to the map column so
              the panel and header stay usable underneath. */}
          {loading && <ScanOverlay cached={!!cachedJob} />}
        </ResizablePanel>

        <ResizableHandle
          withHandle
          aria-label="Resize map and analysis panel"
          /* z-20 + a wider ::after: the grab zone straddles the map, and
             MapLibre's canvas claims pointer events for panning, so the handle
             has to sit above it or a drag that starts on the seam pans the map
             instead of resizing. */
          className="group relative z-20 w-px bg-white/10 cursor-col-resize
                     transition-colors
                     hover:bg-cyan-400/60 data-[resize-handle-state=drag]:bg-cyan-400
                     after:w-6 print:hidden
                     [&>div]:bg-white/10 [&>div]:border-white/20 [&>div]:h-7 [&>div]:w-3.5
                     [&>div]:transition-colors hover:[&>div]:bg-cyan-400/25
                     hover:[&>div]:border-cyan-400/60"
        />

        {/* right rail — `@container` so the cards below respond to THIS panel's
            width rather than the viewport's, which is what actually changes. */}
        <ResizablePanel
          defaultSize={28} minSize={20} maxSize={55}
          className="@container border-l border-white/10 min-w-0 print:!flex-[1_1_100%]"
        >
          <aside className="h-full overflow-y-auto p-4 space-y-5">
            {/* The assistant takes over the rail rather than adding to it —
                the panel was already dense, and these are different jobs. */}
            {validationOpen ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <p className="text-[12px] text-zinc-400">
                    How the live index scores against known deposits
                  </p>
                  <button onClick={() => setValidationOpen(false)}
                          aria-label="Close validation"
                          className="ml-auto text-zinc-400 hover:text-zinc-200">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <ValidationCard lat={lat} lon={lon} placeName={label} />
              </div>
            ) : askOpen ? (
              <AskPanel
                onClose={() => setAskOpen(false)}
                onGoTo={(la, lo, lbl) => {
                  setActiveTarget(null)
                  pick(la, lo, lbl)
                  setAskOpen(false)
                }}
              />
            ) : (
            <>
          <LocationPanel
            lat={lat} lon={lon} km={km}
            result={result} point={point} sample={sample}
            geology={geology} geoState={geoState}
            activeTarget={activeTarget}
            loading={loading} locationName={label}
          />

          {/*
            One "Targets" section with a toggle, instead of two stacked lists
            that each carried their own heading and explanatory blurb.
            Detected = found in the scene you are looking at (S2).
            Known    = catalogued USGS sites from the fixed benchmark.
          */}
          <div className="border-t border-white/10 pt-4 space-y-3">
            <div className="flex items-center gap-1 p-0.5 rounded-lg bg-white/5 w-fit">
              {([
                ['detected', 'Detected here'],
                ['known', 'Known deposits'],
              ] as const).map(([id, label]) => (
                <button key={id} onClick={() => setTargetTab(id)}
                  className={`px-2.5 py-1 rounded-md text-[12px] transition ${
                    targetTab === id
                      ? 'bg-white/12 text-zinc-100 font-medium'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}>
                  {label}
                  {id === 'detected' && targets?.targets?.length ? (
                    <span className="ml-1.5 text-[10px] text-zinc-500">
                      {targets.targets.length}
                    </span>
                  ) : null}
                </button>
              ))}
            </div>

            {targetTab === 'detected' ? (
              <FoundTargets
                data={targets} loading={targetsLoading}
                activeId={activeTarget?.id ?? null}
                onSelect={selectTarget}
                exportMeta={result && targets
                  ? buildMeta(result, targets, lat, lon, km) : null}
              />
            ) : (
              <TargetsPanel onSelect={(la, lo, name) => {
                setActiveTarget(null); pick(la, lo, name)
              }} />
            )}
          </div>

          {/* Temporal — deliberately not implemented. */}
          <div className="border-t border-white/10 pt-4">
            <h3 className="font-semibold text-sm mb-1">Signal stability over time</h3>
            <div className="rounded-xl border border-dashed border-white/15 bg-white/[0.02] p-3">
              <Badge variant="outline" className="text-[9px] border-white/20 text-zinc-400">
                Coming soon
              </Badge>
              <p className="text-[10px] text-zinc-500 mt-2 leading-relaxed">
                This would re-compute the index across several acquisition dates and
                report its variability. It is deliberately NOT shown as a trend:
                mineralogy does not change year to year, so any apparent trend would
                be vegetation, season or mining activity — not a geological signal.
              </p>
            </div>
          </div>

          <Button variant="outline" size="sm" onClick={() => window.print()}
                  className="w-full gap-1.5 text-xs border-white/15">
            <Printer className="w-3.5 h-3.5" /> Print / save report
          </Button>
            </>
            )}
          </aside>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}

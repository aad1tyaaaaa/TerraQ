'use client'

// Right-hand analysis panel. EVERY displayed field carries a comment naming the
// real source it came from. Nothing here is synthesised: if the engine did not
// return a value, the field renders as "—" with the reason.

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertTriangle, ExternalLink, Sparkles, Loader2, ChevronDown, Quote,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import type {
  AnalyzeResult, PointResponse, SampleResponse, FoundTarget,
} from '../lib/types'
import { buildExplanation } from '../lib/explain'
import { jobFile } from '../lib/engine'
import type { GeologyUnit, GeologyState } from '../lib/useGeology'
import depositsData from '../data/deposits.json'
import { findSiteNear, REPORTED_SOURCE, isUndetectable } from '../lib/gazetteer'
import {
  IndexReadout, QualityBar, INDEX_HUE,
} from './Readouts'

const CARD = 'rounded-xl border border-white/12 bg-white/[0.04] p-4'

export interface LocationPanelProps {
  lat: number
  lon: number
  km: number
  result: AnalyzeResult | null
  point: PointResponse | null
  /** S1: lithium score at the clicked point (null before any analysis). */
  sample: SampleResponse | null
  /** S5: geology at this point, fetched once in the shell and shared with S3. */
  geology: GeologyUnit | null
  geoState: GeologyState
  /** S2 target currently selected, if any — drives the S3 explanation. */
  activeTarget: FoundTarget | null
  loading: boolean
  locationName: string | null
}

export function LocationPanel({
  lat, lon, km, result, point, sample, geology, geoState, activeTarget,
  loading, locationName,
}: LocationPanelProps) {
  // Known MRDS sites inside the current radius — counted from the committed
  // validation set in explorer/data/deposits.json (source: USGS MRDS CSVs).
  const within = (depositsData as any).features.filter((f: any) => {
    const [dlon, dlat] = f.geometry.coordinates
    const dx = (dlon - lon) * 111.32 * Math.cos((lat * Math.PI) / 180)
    const dy = (dlat - lat) * 111.32
    return Math.sqrt(dx * dx + dy * dy) <= km
  })

  // Vanadium still comes from /api/point; lithium now comes from /api/sample (S1).
  const v = point?.vanadium

  // A reported occurrence at this spot, if there is one. Shown in its own block,
  // never mixed with the engine's numbers.
  const site = findSiteNear(lat, lon)

  // ---- S3: grounded explanation -------------------------------------------
  // Facts sent to the server are ONLY measured values; the route refuses any
  // reply that contains a number absent from them.
  const [ai, setAi] = useState<{ text: string; source: string; cached: boolean } | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  const aiKey = activeTarget
    ? `t:${result?.job}:${activeTarget.id}`
    : `p:${result?.job}:${lat.toFixed(4)},${lon.toFixed(4)}`

  useEffect(() => {
    if (!result) { setAi(null); return }
    let cancelled = false
    setAiLoading(true); setAi(null)

    const facts = {
      target: activeTarget ? {
        id: activeTarget.id,
        area_km2: activeTarget.area_km2,
        peak_percentile: activeTarget.peak_percentile,
        peak_score: activeTarget.peak_score,
        mean_confidence: activeTarget.mean_confidence,
        nearest_reference_site: activeTarget.nearest_reference_site,
        nearest_reference_km: activeTarget.nearest_reference_km,
      } : null,
      sample: sample ? {
        status: sample.status,
        li_score: sample.li_score,
        li_percentile_in_aoi: sample.li_percentile_in_aoi,
        confidence_class: sample.confidence_class,
        reason: sample.reason,
      } : null,
      confidence_summary: result.confidence_summary ?? null,
      coverage: result.coverage ?? null,
      date_range: result.date_range ?? null,
      geology: geoState === 'ok' && geology
        ? { name: geology.name, lith: geology.lith, age: geology.age }
        : null,
      capability_note: result.caveat ?? null,
    }

    fetch('/api/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ facts, cacheKey: aiKey }),
    })
      .then(r => r.json())
      .then(d => { if (!cancelled) setAi(d) })
      .catch(() => { if (!cancelled) setAi(null) })
      .finally(() => { if (!cancelled) setAiLoading(false) })

    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiKey, sample?.status, geoState])

  const explanation = buildExplanation({
    lat, lon, km, result, point,
    depositsWithin: within.length,
    geologyUnit: geology,
  })

  // No own scroll container here: the parent <aside> scrolls. Nesting two
  // scrollers made the Targets list below unreachable.
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight leading-tight">
          {locationName || 'Selected location'}
        </h2>
        {/* Source: the map selection / coordinate inputs. */}
        <p className="text-[11px] text-zinc-400 mt-1">
          <span className="font-mono">{lat.toFixed(4)}, {lon.toFixed(4)}</span>
          <span className="text-zinc-600"> · </span>
          {km} km search radius
        </p>
        {result && (
          <p className="text-[12px] text-zinc-500 mt-1.5">
            Values rank pixels <b className="font-medium text-zinc-400">within this
            scene</b>.
          </p>
        )}
      </div>

      {/* A reported claim is independent of any measurement, so it shows as
          soon as you are at the site — not only after Analyze has run. */}
            {site?.reported && (
              <div className="rounded-xl border border-zinc-500/30 bg-zinc-500/[0.07] p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Quote className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                  <span className="text-[12px] font-medium text-zinc-300">
                    Reported by others — not measured here
                  </span>
                </div>
                <p className="text-[13px] text-zinc-200">{site.reported}</p>
                <p className="text-[11px] text-zinc-500 mt-1">
                  {site.label} · {site.region} · {site.setting}
                </p>
                {isUndetectable(site) && (
                  <p className="text-[11px] text-amber-300/80 mt-1.5">
                    This target type cannot be seen by optical sensing at all, so
                    the measured values below say nothing about it either way.
                  </p>
                )}
                <details className="mt-2">
                  <summary className="text-[11px] text-zinc-500 cursor-pointer">
                    Where this figure comes from
                  </summary>
                  <p className="text-[11px] text-zinc-500 mt-1 leading-relaxed">
                    {REPORTED_SOURCE}
                  </p>
                </details>
              </div>
            )}

      <Tabs defaultValue="overview" className="flex-1">
        <TabsList className="grid grid-cols-4 w-full bg-white/5">
          <TabsTrigger value="overview" className="text-xs">Overview</TabsTrigger>
          <TabsTrigger value="spectral" className="text-xs">Spectral</TabsTrigger>
          <TabsTrigger value="geology" className="text-xs">Geology</TabsTrigger>
          <TabsTrigger value="insights" className="text-xs">Insights</TabsTrigger>
        </TabsList>

        {/* ---------------------------------------------------------------- */}
        <TabsContent value="overview" className="space-y-3 mt-4">
          {loading && <Skeleton className="h-28 w-full bg-white/5" />}

          {!loading && !result && (
            <div className={`${CARD} text-sm text-zinc-400`}>
              No analysis for this location yet. Press <b>Analyze Region</b>.
            </div>
          )}

          {/* S1: clicked beyond the analysed footprint — be explicit rather than
              showing a stale or zeroed number for the new point. */}
          {!loading && result && sample?.status === 'outside_footprint' && (
            <div className="rounded-xl border border-cyan-400/30 bg-cyan-400/5 p-4 text-sm">
              <p className="font-semibold text-cyan-300">Not analysed</p>
              <p className="text-xs text-zinc-300 mt-1">
                This point lies outside the analysed area. Press
                <b> Analyze Region</b> to run the engine here.
              </p>
            </div>
          )}

          {!loading && result && (
            <>
              {/* Side-by-side once this panel is wide enough; stacked below that.
                  @container units, so it reacts to the drag handle, not the window. */}
              <div className="grid grid-cols-1 @md:grid-cols-2 gap-3 items-start">
              {/* Lithium is the hero readout — exactly one hero figure per view.
                  Source: GET /api/sample (S1) -> li_percentile_in_aoi / li_score. */}
              <IndexReadout
                title="Lithium — clay / Al-OH alteration"
                hero
                hue={INDEX_HUE.lithium}
                percentile={sample?.li_percentile_in_aoi}
                score={sample?.li_score}
                emptyReason={sample?.reason}
                badge={sample?.confidence_class ? (
                  <Badge variant="outline"
                    className={`text-[11px] py-0 px-1.5 ${
                      sample.confidence_class === 'high'
                        ? 'border-emerald-400/40 text-emerald-300'
                        : 'border-amber-400/40 text-amber-300'
                    }`}>
                    {sample.confidence_class} confidence
                  </Badge>
                ) : undefined}
                footnote="Rock-hosted and pegmatite lithium only. Brine lithium under a playa is invisible to optical sensing at any score."
              />

              {/* Secondary readout. Source: GET /api/point -> vanadium.percentile */}
              <IndexReadout
                title="Vanadium — iron-oxide + mica proxy"
                hue={INDEX_HUE.vanadium}
                percentile={v?.percentile}
                score={v?.score}
                emptyReason={v?.note}
                badge={
                  <Badge variant="outline"
                         className="text-[11px] py-0 px-1.5 border-amber-400/40 text-amber-300">
                    low confidence
                  </Badge>
                }
                footnote="A weak proxy, not a vanadium detection. Black-shale vanadium has no usable surface signature."
              />
              </div>

              {/* Source: result.json -> confidence_summary + coverage (engine masks). */}
              <QualityBar
                high={result.confidence_summary?.high_pct}
                masked={result.confidence_summary?.masked_pct}
                coverage={result.coverage}
              />

              {/* Source: explorer/data/deposits.json (USGS MRDS validation set) */}
              <div className={CARD}>
                <p className="text-[11px] font-medium text-zinc-400 mb-2">
                  Known deposits within {km} km
                  <span className="text-zinc-600"> · {within.length}</span>
                </p>
                {within.length === 0 && (
                  <p className="text-[11px] text-zinc-400 leading-snug">
                    None nearby. The reference set covers the Clayton Valley
                    validation area only, so an empty list here says nothing about
                    this location's potential.
                  </p>
                )}
                {within.map((f: any) => (
                  <div key={f.properties.dep_id}
                       className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs py-1 border-t border-white/5 first:border-0">
                    <span>{f.properties.site}</span>
                    <span className="text-zinc-500">
                      {f.properties.commodity}
                      {f.properties.mrds_status ? ` · ${f.properties.mrds_status}` : ''}
                    </span>
                  </div>
                ))}
              </div>

              {/* Source: result.json -> overlays/lithium.png (bare georeferenced PNG) */}
              {result.overlay_layers?.includes('lithium.png') && (
                <div className={CARD}>
                  <p className="text-[11px] font-medium text-zinc-400 mb-2">
                    Lithium layer across the whole search area
                  </p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={jobFile(result.base, 'overlays/lithium.png')}
                       alt="Lithium alteration index across the analysed area"
                       className="w-full rounded-lg border border-white/10 bg-black/40" />
                  <div className="mt-2">
                    <div className="h-1.5 rounded-full"
                         style={{ background: 'linear-gradient(90deg,#000004,#51127c,#b73779,#fc8961,#fcfdbf)' }} />
                    <div className="flex justify-between text-[11px] text-zinc-500 mt-1">
                      <span>lower alteration</span><span>higher</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </TabsContent>

        {/* ---------------------------------------------------------------- */}
        <TabsContent value="spectral" className="space-y-3 mt-4">
          <div className={`${CARD} text-xs text-zinc-300 space-y-2`}>
            <p className="font-semibold text-sm">Index definitions</p>
            <p>
              <b>Lithium</b> — Sentinel-2 SWIR clay / Al-OH ratio (B11/B12), the
              2200 nm absorption associated with Li-bearing clays and pegmatite
              alteration.
            </p>
            <p>
              <b>Vanadium</b> — 0.6 × iron-oxide + 0.4 × mica composite, then
              renormalised. A weak proxy, not a V detection.
            </p>
            <p>
              <b>Brine favorability</b> — scene brightness restricted to playa /
              evaporite pixels. An indirect basin hint only.
            </p>
            <p className="text-zinc-500 border-t border-white/10 pt-2">
              Per-pixel spectra are not exported by the engine, so no spectral
              curve is shown here. Sentinel-2 has 2 SWIR bands, which is why the
              pipeline uses a band ratio rather than true continuum removal —
              a continuum-removed variant benchmarked worse (AUC 0.46 vs 0.82)
              and was rejected.
            </p>
          </div>

          {result && (
            <div className={`${CARD} text-xs`}>
              {/* Source: result.json -> tiles_used[] */}
              <p className="text-[11px] uppercase tracking-widest text-zinc-500 mb-2">
                Scenes used
              </p>
              {result.tiles_used?.map(t => (
                <div key={t.id} className="flex justify-between py-0.5 font-mono text-[11px]">
                  <span>{t.id}</span>
                  <span className="text-zinc-500">
                    {t.date} · {(t.cloud * 100).toFixed(1)}% cloud
                  </span>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* ---------------------------------------------------------------- */}
        <TabsContent value="geology" className="space-y-3 mt-4">
          <div className={CARD}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[11px] uppercase tracking-widest text-zinc-500">
                Mapped bedrock
              </p>
              <a href="https://macrostrat.org" target="_blank" rel="noreferrer"
                 className="text-[11px] text-cyan-400 flex items-center gap-1">
                Macrostrat <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            {geoState === 'loading' && <Skeleton className="h-16 w-full bg-white/5" />}
            {geoState === 'none' && (
              <p className="text-sm text-zinc-400">
                Macrostrat has no mapped unit at this point.
              </p>
            )}
            {geoState === 'error' && (
              <p className="text-sm text-zinc-400">
                Could not reach Macrostrat (timeout). This panel is optional —
                nothing else depends on it.
              </p>
            )}
            {geoState === 'ok' && geology && (
              <div className="space-y-1 text-sm">
                <p className="font-semibold">{geology.name || '—'}</p>
                <p className="text-zinc-400 text-xs">Lithology: {geology.lith || '—'}</p>
                <p className="text-zinc-400 text-xs">Age: {geology.age || '—'}</p>
                <p className="text-[11px] text-zinc-500 pt-1">
                  Third-party reference data. Not produced by this pipeline and
                  not used in any score.
                </p>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ---------------------------------------------------------------- */}
        <TabsContent value="insights" className="space-y-3 mt-4">
          <div className={CARD}>
            <p className="text-[11px] uppercase tracking-widest text-zinc-500 mb-2">
              Summary
            </p>
            {!result && <p className="text-sm text-zinc-400">Run an analysis first.</p>}
            {result && (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-[11px] font-semibold">
                    AI-generated summary from measured values
                  </span>
                  {aiLoading && <Loader2 className="w-3 h-3 animate-spin text-zinc-500" />}
                  {ai && (
                    <Badge variant="outline"
                      className={`text-[11px] py-0 px-1.5 ml-auto ${
                        ai.source === 'template'
                          ? 'border-white/20 text-zinc-400'
                          : 'border-cyan-400/40 text-cyan-300'
                      }`}>
                      {ai.source === 'groq' ? 'Groq'
                        : ai.source === 'groq-fallback' ? 'Groq (fallback)'
                        : ai.source === 'gemini' ? 'Gemini' : 'template'}
                    </Badge>
                  )}
                </div>

                {aiLoading && <Skeleton className="h-16 w-full bg-white/5" />}
                {ai && (
                  <p className="text-xs leading-relaxed text-zinc-300">{ai.text}</p>
                )}

                <details className="mt-3">
                  <summary className="text-[11px] text-zinc-500 cursor-pointer">
                    Deterministic breakdown (no model)
                  </summary>
                  <div className="space-y-2 text-xs leading-relaxed text-zinc-400 mt-2">
                    {explanation.map((p, i) => <p key={i}>{p}</p>)}
                  </div>
                </details>
              </>
            )}
            <p className="text-[11px] text-zinc-500 mt-3 pt-2 border-t border-white/10">
              Built only from the measured values on this page. Any reply containing a
              number not present in those values is discarded and the deterministic
              template is shown instead.
            </p>
          </div>
        </TabsContent>
      </Tabs>

      {/*
        One headline caveat stays on screen; the rest is one click away. The
        facts are unchanged — five permanent bullets simply trained people to
        stop reading them.
      */}
      <details className="group rounded-xl border border-amber-400/25 bg-amber-400/5 px-3 py-2">
        <summary className="flex items-center gap-1.5 cursor-pointer list-none
                            text-[12px] text-amber-200/90 marker:content-['']">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span className="font-medium">Surface alteration only — a lead, not a discovery.</span>
          <ChevronDown className="w-3.5 h-3.5 ml-auto shrink-0 transition-transform
                                  group-open:rotate-180" />
        </summary>
        <ul className="list-disc list-inside space-y-1 mt-2 text-[12px] leading-relaxed
                       text-amber-200/80">
          <li>Buried deposits are not detectable.</li>
          <li>Brine lithium is invisible to optical sensing — a low score over a
              playa says nothing about brine potential.</li>
          <li>Scores rank pixels within one scene. They are not calibrated
              probabilities and not comparable between scenes.</li>
          <li>Vanadium is a low-confidence proxy; black-shale V has no surface
              signature.</li>
        </ul>
      </details>
    </div>
  )
}

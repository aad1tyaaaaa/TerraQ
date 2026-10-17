'use client'

// "Top Exploration Targets".
//
// SINGLE source: explorer/data/benchmark_console.json, produced by
// product/benchmark_console.py on one fixed Clayton Valley AOI. It is NOT mixed
// with outputs/sentinel2_results/benchmark.json — that file was computed on a
// different AOI and disagrees with this one (e.g. Silver Peak Lithium Operations
// is 98th percentile there and masked here). Mixing them would put two
// contradictory numbers on screen.
//
// A site with status 'masked' or 'outside_footprint' has score === null and
// renders as "—". It is never shown as 0.

import benchmark from '../data/benchmark_console.json'
import { priorityFor } from '../lib/presets'
import { Badge } from '@/components/ui/badge'
import type { BenchmarkDeposit } from '../lib/types'

const CARD = 'rounded-xl border border-white/12 bg-white/[0.04] p-3'

const STATUS_COPY: Record<string, string> = {
  masked: 'No valid rock pixels (water / vegetation / nodata) — not scorable here.',
  outside_footprint: 'Outside the benchmark AOI — not evaluated.',
}

export function TargetsPanel({ onSelect }: {
  onSelect: (lat: number, lon: number, label: string) => void
}) {
  const rows = (benchmark.deposits as BenchmarkDeposit[])
    .slice()
    .sort((a, b) => {
      // scored first, by descending percentile; unscored keep a stable order
      if (a.percentile === null && b.percentile === null) return 0
      if (a.percentile === null) return 1
      if (b.percentile === null) return -1
      return b.percentile - a.percentile
    })

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-zinc-500">AOI: {benchmark.aoi.name}</p>

      <p className="text-[11px] text-zinc-500 leading-relaxed">
        USGS MRDS sites ranked by the lithium alteration index within one fixed
        scene (ROC-AUC {benchmark.roc_auc ?? '—'} against background, n=
        {benchmark.counts.positive_pixels} positive pixels). Percentiles are
        relative to this scene only.
      </p>

      {/* One flow: no inner scroll container, so the parent aside scrolls cleanly. */}
      <div className="grid grid-cols-1 @lg:grid-cols-2 gap-1.5">
        {rows.map(d => {
          const pri = priorityFor(d.percentile)
          const clickable = d.status !== 'outside_footprint'
          return (
            <button
              key={`${d.site}-${d.dep_id ?? d.lat}`}
              onClick={() => clickable && onSelect(d.lat, d.lon, d.site)}
              className={`${CARD} w-full text-left transition hover:bg-white/[0.07] ${
                clickable ? '' : 'opacity-60 cursor-default'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-semibold truncate">{d.site}</p>
                  <p className="text-[11px] text-zinc-500">
                    {d.commodity === 'Li' ? 'Lithium' : 'Vanadium'}
                    {d.status_mrds ? ` · ${d.status_mrds}` : ''}
                    {' · '}{d.lat.toFixed(3)}, {d.lon.toFixed(3)}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  {d.percentile !== null ? (
                    <>
                      <p className="text-sm font-bold">{d.percentile.toFixed(0)}th</p>
                      <p className="text-[11px] text-zinc-500">percentile</p>
                    </>
                  ) : (
                    <p className="text-sm font-bold text-zinc-500"
                       title={STATUS_COPY[d.status]}>—</p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-1.5 mt-1.5">
                {pri ? (
                  <Badge variant="outline" className={`text-[11px] py-0 px-1.5 ${pri.cls}`}>
                    {pri.label}
                  </Badge>
                ) : (
                  <Badge variant="outline"
                         className="text-[11px] py-0 px-1.5 text-zinc-400 border-white/15">
                    {d.status === 'masked' ? 'Not scorable' : 'Not evaluated'}
                  </Badge>
                )}
                {d.commodity === 'V' && (
                  <Badge variant="outline"
                         className="text-[11px] py-0 px-1.5 text-amber-300 border-amber-400/40">
                    low confidence
                  </Badge>
                )}
              </div>

              {d.note && (
                <p className="text-[11px] text-zinc-500 mt-1 leading-snug">{d.note}</p>
              )}
            </button>
          )
        })}
      </div>

      <p className="text-[11px] text-zinc-500 leading-relaxed border-t border-white/10 pt-2">
        Priority bands are presentation buckets over a relative index
        (≥95 High, ≥80 Moderate, ≥50 Low). They are not calibrated probabilities
        and imply no likelihood of mineralisation.
      </p>
    </div>
  )
}

'use client'

// S2 — targets derived from the current job's lithium raster (GET /api/targets).
//
// Distinct from TargetsPanel, which ranks KNOWN USGS sites from the fixed
// benchmark. This one finds anomalies the engine located in the scene you are
// looking at. Both are real; they answer different questions.

import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Download } from 'lucide-react'
import type { TargetsResponse, FoundTarget } from '../lib/types'
import { downloadTargets, type ExportFormat, type ExportMeta } from '../lib/exportTargets'

const CARD = 'rounded-xl border border-white/12 bg-white/[0.04] p-3'

export function FoundTargets({
  data, loading, activeId, onSelect, exportMeta,
}: {
  data: TargetsResponse | null
  loading: boolean
  activeId: string | null
  onSelect: (t: FoundTarget) => void
  /** Run provenance written into every exported file; null disables export. */
  exportMeta: ExportMeta | null
}) {
  return (
    <div className="space-y-2">
      {loading && <Skeleton className="h-24 w-full bg-white/5" />}

      {!loading && !data && (
        <p className="text-xs text-zinc-400">
          Run an analysis to detect targets in the imagery.
        </p>
      )}

      {!loading && data && data.targets.length === 0 && (
        <p className="text-xs text-zinc-400">
          {data.note || 'No clusters passed the threshold in this area.'}
        </p>
      )}

      {!loading && data && data.targets.length > 0 && (
        <>
          <p className="text-[11px] text-zinc-500 leading-relaxed">
            Pixels at or above the {data.params.percentile}th percentile of
            high-confidence rock, grouped into {data.params.connectivity} clusters of at
            least {data.params.min_pixels} pixels. {data.ranking_note}
          </p>

          {/* Two columns once the panel is dragged wide; one when narrow. */}
          <div className="grid grid-cols-1 @lg:grid-cols-2 gap-1.5">
            {data.targets.map(t => (
              <button key={t.id} onClick={() => onSelect(t)}
                className={`${CARD} w-full text-left transition hover:bg-white/[0.07] ${
                  activeId === t.id ? 'ring-1 ring-cyan-400/60 bg-cyan-400/10' : ''
                }`}>
                <div className="flex items-start gap-2">
                  <span className="shrink-0 w-5 h-5 rounded-full bg-cyan-400 text-[#04121a]
                                   text-[11px] font-bold grid place-items-center mt-0.5">
                    {t.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold">
                      {t.area_km2.toFixed(2)} km² anomaly
                    </p>
                    <p className="text-[11px] text-zinc-500 font-mono">
                      {t.centroid_lat.toFixed(4)}, {t.centroid_lon.toFixed(4)}
                    </p>
                    <p className="text-[11px] text-zinc-400 mt-1">
                      peak {t.peak_percentile.toFixed(0)}th pct · score{' '}
                      {t.peak_score.toFixed(3)}
                      {t.mean_confidence !== null && (
                        <> · conf {(t.mean_confidence * 100).toFixed(0)}%</>
                      )}
                    </p>
                    {t.nearest_reference_site && (
                      <p className="text-[11px] text-zinc-500 mt-0.5">
                        nearest known site: {t.nearest_reference_site.replace(/^(Li|V):/, '')}
                        {' '}— {t.nearest_reference_km} km
                      </p>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>

          {exportMeta && (
            <div className="flex items-center gap-1.5 pt-1">
              <span className="flex items-center gap-1 text-[11px] text-zinc-500">
                <Download className="w-3 h-3" /> Download targets
              </span>
              {(['csv', 'geojson', 'kml'] as ExportFormat[]).map(f => (
                <button key={f}
                        onClick={() => downloadTargets(f, data.targets, exportMeta)}
                        className="rounded px-2 py-0.5 text-[11px] uppercase tracking-wide
                                   border border-white/15 text-zinc-300
                                   hover:bg-white/10 hover:border-cyan-400/40 transition">
                  {f}
                </button>
              ))}
            </div>
          )}

          <p className="text-[11px] text-zinc-500 leading-relaxed border-t border-white/10 pt-2">
            Clusters of relatively high surface alteration within this scene — not
            deposits and not probabilities. Brine lithium beneath a playa cannot be
            detected optically and will never appear as a target. Exported files
            carry the scene IDs and job hash so results stay traceable.
          </p>
        </>
      )}
    </div>
  )
}

export function targetBadge(t: FoundTarget) {
  return (
    <Badge variant="outline" className="text-[11px] py-0 px-1.5 border-cyan-400/40 text-cyan-300">
      {t.id}
    </Badge>
  )
}

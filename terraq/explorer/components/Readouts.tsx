'use client'

import { Info } from 'lucide-react'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'

// Presentation pieces for the Selected-location panel.
//
// Colour choices here were validated with the dataviz palette validator against
// this app's surface (#05080c), not eyeballed:
//   index accents  #17a2b8 + #d95926 -> all categorical checks PASS
//   quality ramp   #5ecfe0 / #17a2b8 / #115c68 -> all ordinal checks PASS
// The brand cyan #00F2FF was REJECTED for fills: OKLCH L 0.875, far outside the
// 0.48-0.67 band — it glares as a large area. It stays as a thin UI accent only.

export const INDEX_HUE = {
  lithium: '#17a2b8',
  vanadium: '#d95926',
} as const

export const QUALITY_HUE = {
  high: '#5ecfe0',
  low: '#17a2b8',
  masked: '#115c68',
} as const

/** 1st / 2nd / 3rd / 4th … — the panel previously rendered "52th". */
export function ordinal(n: number): string {
  const i = Math.round(n)
  const mod100 = i % 100
  if (mod100 >= 11 && mod100 <= 13) return `${i}th`
  return `${i}${['th', 'st', 'nd', 'rd'][i % 10] ?? 'th'}`
}

/**
 * Plain-language reading of a within-scene percentile.
 * Thresholds match PRIORITY_BANDS in lib/presets.ts. These describe RANK within
 * one scene — deliberately not words like "likely" or "probable", which would
 * imply a probability the index does not carry.
 */
export function band(p: number) {
  if (p >= 95) return { label: 'Strong anomaly', hint: 'among the highest readings in this scene' }
  if (p >= 80) return { label: 'Elevated', hint: 'clearly above most of this scene' }
  if (p >= 50) return { label: 'Moderate', hint: 'around the middle of this scene' }
  if (p >= 20) return { label: 'Subdued', hint: 'below most of this scene' }
  return { label: 'Background', hint: 'among the lowest readings in this scene' }
}

/**
 * Index readout: hero number + a meter showing where the point sits on the
 * 0-100 within-scene percentile scale.
 *
 * A meter is the right form for "a single ratio against a limit" — the track is
 * the whole scene, the fill is this point's rank in it. The unfilled track is a
 * darker step of the SAME hue so the state reads across the whole bar.
 */
export function IndexReadout({
  title, percentile, score, hue, hero = false, badge, footnote, emptyReason,
}: {
  title: string
  percentile: number | null | undefined
  score: number | null | undefined
  hue: string
  hero?: boolean
  badge?: React.ReactNode
  footnote: string
  emptyReason?: string | null
}) {
  const has = percentile !== null && percentile !== undefined
  const b = has ? band(percentile) : null

  return (
    <div className="rounded-xl border border-white/12 bg-white/[0.04] p-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="flex items-center gap-1.5 text-[12px] font-medium text-zinc-300">
          {title}
          {/* The caveat used to sit permanently under every card. Same words,
              one hover away — so the card reads as a number, not an essay. */}
          <TooltipProvider delayDuration={150}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" aria-label={`About ${title}`}
                        className="text-zinc-500 hover:text-zinc-300 transition-colors">
                  <Info className="w-3.5 h-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="left" className="max-w-[240px] text-[11px] leading-relaxed">
                {footnote}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </span>
        {badge}
      </div>

      {!has ? (
        <>
          <p className={`${hero ? 'text-4xl' : 'text-2xl'} font-semibold text-zinc-600 leading-none`}>
            —
          </p>
          <p className="text-[11px] text-zinc-400 mt-2 leading-snug">
            {emptyReason || 'No value could be measured at this point.'}
          </p>
        </>
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            {/* Hero figure: proportional (not tabular) figures at display size. */}
            <span className={`${hero ? 'text-4xl @lg:text-5xl' : 'text-3xl'} font-semibold leading-none`}>
              {ordinal(percentile)}
            </span>
            <span className="text-xs text-zinc-400">percentile</span>
          </div>

          <p className="text-sm font-medium mt-1.5" style={{ color: hue }}>
            {b!.label}
            <span className="text-zinc-400 font-normal"> — {b!.hint}</span>
          </p>

          {/* Meter: fill = this point, track = the rest of the scene. */}
          <div
            className="mt-3 h-2 w-full rounded-full overflow-hidden"
            style={{ background: 'rgba(255,255,255,0.07)' }}
            role="img"
            aria-label={`${ordinal(percentile)} percentile of this scene`}
          >
            <div
              className="h-full rounded-full transition-[width] duration-500"
              style={{ width: `${Math.max(2, Math.min(100, percentile))}%`, background: hue }}
            />
          </div>
          <div className="flex justify-between text-[10px] text-zinc-500 mt-1">
            <span>lowest in scene</span>
            <span>highest</span>
          </div>

          {score !== null && score !== undefined && (
            <p className="text-[12px] text-zinc-500 mt-2">
              Index <span className="font-medium text-zinc-300">{score.toFixed(3)}</span>
              {' '}of 1 — a ranking, not a probability.
            </p>
          )}
        </>
      )}

    </div>
  )
}

/**
 * Data quality as a part-to-whole stacked bar.
 *
 * Three ordered classes on one hue ramp (light = usable, dark = unusable), with
 * a 2px surface gap between segments and every segment direct-labelled, so the
 * classes never depend on colour alone.
 */
export function QualityBar({
  high, masked, coverage,
}: {
  high: number | null | undefined
  masked: number | null | undefined
  coverage: number | null | undefined
}) {
  const h = high ?? null
  const m = masked ?? null
  // "low" (vegetation) is whatever the engine did not attribute to the other two.
  const low = h !== null && m !== null ? Math.max(0, +(100 - h - m).toFixed(1)) : null

  const segs = [
    { key: 'high', label: 'Usable rock', value: h, hue: QUALITY_HUE.high,
      note: 'the index was computed on these pixels' },
    { key: 'low', label: 'Vegetation', value: low, hue: QUALITY_HUE.low,
      note: 'plant cover hides the rock signal' },
    { key: 'masked', label: 'Masked', value: m, hue: QUALITY_HUE.masked,
      note: 'water, cloud, shadow or no data' },
  ].filter(s => s.value !== null && s.value > 0)

  return (
    <div className="rounded-xl border border-white/12 bg-white/[0.04] p-4">
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <span className="flex items-center gap-1.5 text-[12px] font-medium text-zinc-300">
          Data quality
          <TooltipProvider delayDuration={150}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" aria-label="About data quality"
                        className="text-zinc-500 hover:text-zinc-300 transition-colors">
                  <Info className="w-3.5 h-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="left" className="max-w-[240px] text-[11px] leading-relaxed">
                Usable rock = pixels the index was computed on. Vegetation hides the
                rock signal. Masked = water, cloud, shadow or no data.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </span>
        {coverage !== null && coverage !== undefined && (
          <span className="text-[11px] text-zinc-400">
            <span className="font-medium text-zinc-200">{coverage}%</span> of the
            requested area imaged
          </span>
        )}
      </div>

      {segs.length === 0 ? (
        <p className="text-sm text-zinc-500 mt-1">—</p>
      ) : (
        <>
          <p className="text-sm text-zinc-300 mb-2.5">
            <span className="font-semibold text-base">{h}%</span> of this area was
            usable rock the index could actually be measured on.
          </p>

          {/* 2px gaps between fills, as the mark spec requires. */}
          <div className="flex gap-[2px] h-2.5 w-full mb-2.5">
            {segs.map(s => (
              <div key={s.key} title={`${s.label} — ${s.value}%`}
                   className="h-full first:rounded-l-full last:rounded-r-full"
                   style={{ width: `${s.value}%`, background: s.hue }} />
            ))}
          </div>

          <ul className="space-y-1">
            {segs.map(s => (
              <li key={s.key} className="flex items-baseline gap-2 text-[11px]">
                <span className="w-2 h-2 rounded-sm shrink-0 translate-y-[1px]"
                      style={{ background: s.hue }} />
                <span className="text-zinc-300 font-medium w-[86px] shrink-0">{s.label}</span>
                <span className="text-zinc-200 tabular-nums w-10 shrink-0">{s.value}%</span>
                <span className="text-zinc-500 hidden @md:inline">{s.note}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

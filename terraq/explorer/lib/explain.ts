// Deterministic, template-based explanation of a result.
//
// There is no LLM here and no network call. Every sentence is assembled from
// numbers that came back from the engine, so the console behaves identically
// with zero API keys configured. If a value is missing we say so rather than
// filling the gap.
//
// Rules this template obeys (same ones a model would have been given):
//   * never call the score a probability
//   * always surface the limitation that applies to what was shown
//   * end with a concrete next step, since a score is a lead, not a finding

import type { AnalyzeResult, PointResponse } from './types'

export interface ExplainInput {
  lat: number
  lon: number
  km: number
  result: AnalyzeResult | null
  point: PointResponse | null
  depositsWithin: number
  nearestDeposit?: { site: string; commodity: string; km: number } | null
  geologyUnit?: {
    name?: string | null; lith?: string | null; age?: string | null
  } | null
}

function pctPhrase(p: number) {
  if (p >= 95) return `in the top ${(100 - p).toFixed(0)}% of pixels in this scene`
  if (p >= 80) return `above about ${p.toFixed(0)}% of pixels in this scene`
  return `around the ${p.toFixed(0)}th percentile of this scene`
}

export function buildExplanation(i: ExplainInput): string[] {
  const out: string[] = []
  const li = i.point?.lithium

  // 1. What was measured, and where.
  if (i.result) {
    out.push(
      `This ${i.km} km area around ${i.lat.toFixed(4)}, ${i.lon.toFixed(4)} was analysed ` +
      `from ${i.result.tiles} Sentinel-2 tile(s) (${i.result.date_range}) with ` +
      `${i.result.coverage}% of the requested footprint covered.`,
    )
  }

  // 2. The number itself — or an explicit statement that there isn't one.
  if (li?.status === 'scored' && li.percentile !== null && li.score !== null) {
    out.push(
      `The clay / Al-OH lithium alteration index at the selected point is ` +
      `${li.score.toFixed(3)} on a relative 0–1 scale, which places it ` +
      `${pctPhrase(li.percentile)}. This is a ranking within this scene, not a ` +
      `probability of mineralisation and not comparable to another scene.`,
    )
  } else if (li?.status === 'masked') {
    out.push(
      `No lithium index value exists at this exact point: every pixel in the ` +
      `immediate neighbourhood is water, vegetation, cloud or nodata, so the ` +
      `index could not be evaluated. That is a data gap, not a low score.`,
    )
  } else if (li?.status === 'outside_footprint') {
    out.push(
      `The selected point falls outside the analysed footprint, so it has no ` +
      `value. Re-run the analysis centred closer to it.`,
    )
  }

  // 3. Data quality + known deposits, when we actually have them.
  const cs = i.result?.confidence_summary
  if (cs && cs.high_pct !== null && cs.high_pct !== undefined) {
    out.push(
      `${cs.high_pct}% of the area is high-confidence rock the index could be ` +
      `computed on` +
      (cs.masked_pct !== null && cs.masked_pct !== undefined
        ? `, and ${cs.masked_pct}% is masked (water, vegetation, cloud or nodata)`
        : '') +
      `. ${i.depositsWithin} catalogued USGS MRDS site(s) fall inside this radius.`,
    )
  }

  if (i.geologyUnit?.name) {
    const bits = [i.geologyUnit.name, i.geologyUnit.lith, i.geologyUnit.age]
      .filter(Boolean).join(' · ')
    out.push(`Mapped bedrock at this point: ${bits} (Macrostrat).`)
  }

  // 4. The limitation that actually applies here, then a next step.
  const playa = i.result?.playa_fraction
  if (playa !== null && playa !== undefined && playa > 0.05) {
    out.push(
      `Note that ${(playa * 100).toFixed(0)}% of this area is playa/evaporite. ` +
      `Optical remote sensing cannot detect brine lithium dissolved beneath a ` +
      `playa — a low score there says nothing about brine potential.`,
    )
  } else {
    out.push(
      `This method sees surface alteration only. Buried deposits and brine ` +
      `lithium are invisible to it regardless of score.`,
    )
  }

  out.push(
    li?.status === 'scored' && (li.percentile ?? 0) >= 90
      ? `Suggested next step: treat this as a lead and follow up with soil / rock-chip ` +
        `sampling and an airborne hyperspectral or field spectrometer survey before ` +
        `any drill planning.`
      : `Suggested next step: compare against the higher-ranked targets in this scene ` +
        `before committing field time here.`,
  )

  return out
}

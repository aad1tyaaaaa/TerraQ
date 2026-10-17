// Task 3 — export detected targets as CSV, GeoJSON or KML.
//
// Everything is built client-side from the targets.json the engine already
// produced, plus the run metadata from result.json, so an exported file carries
// enough provenance to be re-checked later: scene IDs, acquisition dates and the
// job hash go into the header (CSV), the top-level properties (GeoJSON) or the
// document description (KML).
//
// Honesty: percentile is the within-scene rank, and every export repeats that in
// the header so a file that outlives this session cannot be read as an absolute
// measurement.

import type { FoundTarget, TargetsResponse, AnalyzeResult } from './types'

export type ExportFormat = 'csv' | 'geojson' | 'kml'

export interface ExportMeta {
  job: string
  lat: number
  lon: number
  km: number
  dateRange: string
  coverage: number
  sceneIds: string[]
  rankingNote: string
}

export function buildMeta(result: AnalyzeResult, targets: TargetsResponse,
                          lat: number, lon: number, km: number): ExportMeta {
  return {
    job: result.job,
    lat, lon, km,
    dateRange: result.date_range ?? '',
    coverage: result.coverage ?? 0,
    sceneIds: (result.tiles_used ?? []).map(t => t.id),
    rankingNote: targets.ranking_note ?? '',
  }
}

const PROVENANCE = (m: ExportMeta) => [
  `TerraQ detected targets`,
  `job=${m.job}`,
  `aoi=${m.lat.toFixed(4)},${m.lon.toFixed(4)} radius_km=${m.km}`,
  `scenes=${m.sceneIds.join('|') || 'n/a'}`,
  `date_range=${m.dateRange}`,
  `coverage_pct=${m.coverage}`,
  `note=percentile is the rank WITHIN THIS SCENE, not an absolute measure, not a probability`,
  `ranking=${m.rankingNote}`,
]

function esc(v: unknown) {
  const s = v === null || v === undefined ? '' : String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function toCSV(targets: FoundTarget[], m: ExportMeta) {
  const head = PROVENANCE(m).map(l => `# ${l}`).join('\n')
  const cols = ['id', 'rank', 'lat', 'lon', 'area_km2', 'peak_percentile',
                'peak_score', 'mean_confidence', 'nearest_reference_site',
                'distance_km']
  const rows = targets.map(t => [
    t.id, t.rank, t.centroid_lat, t.centroid_lon, t.area_km2,
    t.peak_percentile, t.peak_score,
    t.mean_confidence ?? '', t.nearest_reference_site ?? '',
    t.nearest_reference_km ?? '',
  ].map(esc).join(','))
  return `${head}\n${cols.join(',')}\n${rows.join('\n')}\n`
}

function toGeoJSON(targets: FoundTarget[], m: ExportMeta) {
  return JSON.stringify({
    type: 'FeatureCollection',
    properties: {
      generator: 'TerraQ Explorer',
      job: m.job,
      aoi: { lat: m.lat, lon: m.lon, radius_km: m.km },
      scene_ids: m.sceneIds,
      date_range: m.dateRange,
      coverage_pct: m.coverage,
      ranking_note: m.rankingNote,
      caveat: 'percentile is the within-scene rank, not an absolute measure and ' +
              'not a probability; surface alteration only',
    },
    features: targets.map(t => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [t.centroid_lon, t.centroid_lat] },
      properties: {
        id: t.id, rank: t.rank, area_km2: t.area_km2,
        peak_percentile: t.peak_percentile, peak_score: t.peak_score,
        mean_confidence: t.mean_confidence,
        nearest_reference_site: t.nearest_reference_site,
        distance_km: t.nearest_reference_km,
      },
    })),
  }, null, 1)
}

/** XML text escape — target names can carry & and quotes. */
function xml(s: unknown) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&apos;')
}

function toKML(targets: FoundTarget[], m: ExportMeta) {
  const desc = xml(PROVENANCE(m).join('\n'))
  const marks = targets.map(t => `    <Placemark>
      <name>${xml(`${t.id} · ${t.area_km2.toFixed(2)} km²`)}</name>
      <description>${xml(
        `rank ${t.rank}\npeak ${t.peak_percentile} percentile (within this scene)\n` +
        `peak index ${t.peak_score}\n` +
        `mean confidence ${t.mean_confidence ?? 'n/a'}\n` +
        `nearest reference: ${t.nearest_reference_site ?? 'n/a'}` +
        `${t.nearest_reference_km != null ? ` (${t.nearest_reference_km} km)` : ''}`)}</description>
      <styleUrl>#terraq-target</styleUrl>
      <Point><coordinates>${t.centroid_lon},${t.centroid_lat},0</coordinates></Point>
    </Placemark>`).join('\n')

  return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${xml(`TerraQ targets — ${m.lat.toFixed(4)}, ${m.lon.toFixed(4)}`)}</name>
    <description>${desc}</description>
    <Style id="terraq-target">
      <IconStyle>
        <color>ffb8a217</color>
        <scale>1.1</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>
      </IconStyle>
    </Style>
${marks}
  </Document>
</kml>
`
}

export function buildExport(fmt: ExportFormat, targets: FoundTarget[], m: ExportMeta) {
  if (fmt === 'csv') {
    return { body: toCSV(targets, m), mime: 'text/csv;charset=utf-8', ext: 'csv' }
  }
  if (fmt === 'geojson') {
    return { body: toGeoJSON(targets, m), mime: 'application/geo+json', ext: 'geojson' }
  }
  return {
    body: toKML(targets, m),
    mime: 'application/vnd.google-earth.kml+xml',
    ext: 'kml',
  }
}

/** Trigger a browser download. */
export function downloadTargets(fmt: ExportFormat, targets: FoundTarget[], m: ExportMeta) {
  const { body, mime, ext } = buildExport(fmt, targets, m)
  const url = URL.createObjectURL(new Blob([body], { type: mime }))
  const a = document.createElement('a')
  a.href = url
  a.download = `terraq-targets-${m.job}.${ext}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

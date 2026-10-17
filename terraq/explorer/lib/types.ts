// Shapes returned by the Python engine (product/server.py).
// Every field here exists in a real response — see outputs/jobs/<id>/result.json.

/** Image corners for MapLibre, exactly four: [TL, TR, BR, BL] as [lon, lat]. */
export type Corners = [
  [number, number], [number, number], [number, number], [number, number],
]

/** A value that the engine could not evaluate. Rendered as "—", never as 0. */
export type Nullable<T> = T | null

export type PointStatus = 'scored' | 'masked' | 'outside_footprint' | 'unavailable'

export interface PointSample {
  status: PointStatus
  /** Relative 0–1 alteration index within this scene. null unless status==='scored'. */
  score: Nullable<number>
  /** Percentile among valid pixels of this scene. null unless status==='scored'. */
  percentile: Nullable<number>
  note?: string
}

export interface PointResponse {
  ok: boolean
  lat: number
  lon: number
  job: string
  lithium: PointSample
  vanadium: PointSample
  scale_note: string
}

/** Per-deposit check the engine runs for MRDS sites inside the analysed area. */
export interface DepositCheck {
  name: string
  type: 'rock' | 'playa' | string
  li_score: number
  li_percentile: number
  v_score: number
}

export interface ConfidenceSummary {
  high_pct: Nullable<number>
  low_pct: Nullable<number>
  masked_pct: Nullable<number>
  definition?: string
}

export interface TileUsed {
  id: string
  date: string
  cloud: number
}

/** POST /api/analyze */
export interface AnalyzeResult {
  ok: boolean
  error?: string
  job: string
  base: string
  cached: boolean
  coverage: number
  tiles: number
  date_range: string
  caveat: string
  deposit_check: DepositCheck[]
  /** [TL, TR, BR, BL] in [lon, lat] — EPSG:4326, so no UTM skew. */
  overlay_corners: Nullable<Corners>
  overlay_layers: string[]
  confidence_summary: ConfidenceSummary
  bbox_lonlat: Nullable<number[]>
  crs: Nullable<string>
  grid: Nullable<number[]>
  rock_fraction: Nullable<number>
  playa_fraction: Nullable<number>
  tiles_used: TileUsed[]
}

/** GET /api/sample — S1 click-anywhere lithium score. */
export interface SampleResponse {
  ok: boolean
  job: string
  lat: number
  lon: number
  status: 'scored' | 'masked' | 'outside_footprint'
  /** Relative 0-1 index. null unless status === 'scored'. */
  li_score: Nullable<number>
  /** Percentile among valid pixels of this scene. null unless scored. */
  li_percentile_in_aoi: Nullable<number>
  confidence_class: Nullable<'high' | 'low' | 'masked'>
  reason: Nullable<string>
  scale_note: string
}

/** One cluster from GET /api/targets (S2). */
export interface FoundTarget {
  id: string
  rank: number
  centroid_lat: number
  centroid_lon: number
  area_km2: number
  pixels: number
  peak_score: number
  peak_percentile: number
  mean_score: number
  mean_confidence: Nullable<number>
  nearest_reference_site: Nullable<string>
  nearest_reference_km: Nullable<number>
}

/** GET /api/targets */
export interface TargetsResponse {
  ok: boolean
  targets: FoundTarget[]
  ranking_note: string
  note?: string
  params: {
    percentile: number
    min_pixels: number
    max_targets: number
    connectivity: string
    confidence_filter: string
    ranking: string
    threshold_value: Nullable<number>
  }
}

/** GET /api/jobs */
export interface JobSummary {
  job: string
  lat: number
  lon: number
  km: number
  timestamp: number
  coverage: number
  tiles: number
  date_range: string
  bbox_lonlat: number[]
  has_overlays: boolean
}

/** A row of outputs/benchmark_console.json (via explorer/data). */
export interface BenchmarkDeposit {
  site: string
  commodity: 'Li' | 'V' | string
  status: 'scored' | 'masked' | 'outside_footprint'
  status_mrds: Nullable<string>
  score: Nullable<number>
  percentile: Nullable<number>
  lat: number
  lon: number
  note: Nullable<string>
  url?: string
  dep_id?: string
}

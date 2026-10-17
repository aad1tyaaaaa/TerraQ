// Quick locations. Must stay in sync with PRESETS in product/prewarm.py so that
// every preset is served from cache during a demo.

export interface Preset {
  label: string
  lat: number
  lon: number
  km: number
  hint: string
}

export const PRESETS: Preset[] = [
  { label: 'Silver Peak (Li)', lat: 37.7499, lon: -117.6342, km: 12,
    hint: 'Albemarle Silver Peak — the only producing lithium mine in the USA' },
  { label: 'Clayton Valley', lat: 37.78, lon: -117.6, km: 15,
    hint: 'Basin-wide view of the Clayton Valley lithium district' },
  { label: 'Foote Lithium', lat: 37.7585, lon: -117.5912, km: 10,
    hint: 'Foote Lithium Brine Operation — rock-hosted alteration scores high' },
  { label: 'Silver Peak Ops', lat: 37.7672, lon: -117.5833, km: 10,
    hint: 'Silver Peak Lithium Operations, north-east of the main mine' },
  { label: 'Silver Peak Marsh', lat: 37.7527, lon: -117.6398, km: 10,
    hint: 'The brine playa — scores low by design; optical RS cannot see brine Li' },
  { label: 'Foote Mineral Co', lat: 37.8468, lon: -117.5412, km: 12,
    hint: 'Northern end of the district' },
  { label: 'Mohawk Mine (V)', lat: 37.7291, lon: -117.8134, km: 10,
    hint: 'Nearest catalogued vanadium occurrence — low-confidence V proxy' },
]

/** Mineral filter chips. Only Li and V have any engine output at all. */
export interface MineralChip {
  id: string
  label: string
  enabled: boolean
  badge?: string
  note: string
}

export const MINERALS: MineralChip[] = [
  { id: 'lithium', label: 'Lithium', enabled: true,
    note: 'Clay / Al-OH alteration at 2200 nm. Rock-hosted & pegmatite only — not brine.' },
  { id: 'vanadium', label: 'Vanadium', enabled: true, badge: 'low confidence',
    note: 'Iron-oxide + mica composite. Black-shale vanadium has no usable surface signature.' },
  { id: 'copper', label: 'Copper', enabled: false, badge: 'Roadmap', note: 'Not implemented.' },
  { id: 'nickel', label: 'Nickel', enabled: false, badge: 'Roadmap', note: 'Not implemented.' },
  { id: 'cobalt', label: 'Cobalt', enabled: false, badge: 'Roadmap', note: 'Not implemented.' },
  { id: 'gold', label: 'Gold', enabled: false, badge: 'Roadmap', note: 'Not implemented.' },
  { id: 'iron', label: 'Iron', enabled: false, badge: 'Roadmap', note: 'Not implemented.' },
  { id: 'ree', label: 'REE', enabled: false, badge: 'Roadmap', note: 'Not implemented.' },
]

/** Map layers, keyed by the bare overlay filenames written by overlay_export.py. */
export const OVERLAY_LAYERS: {
  id: string; file: string; label: string; desc: string
}[] = [
  { id: 'lithium', file: 'lithium.png', label: 'Lithium prospectivity',
    desc: 'Clay / Al-OH alteration index (relative, 0–1). Rock-hosted & pegmatite Li.' },
  { id: 'vanadium', file: 'vanadium.png', label: 'Vanadium prospectivity',
    desc: 'Iron-oxide + mica composite. Low-confidence proxy.' },
  { id: 'brine', file: 'brine.png', label: 'Brine favorability',
    desc: 'Indirect playa / evaporite basin hint — not a detection.' },
  { id: 'rgb', file: 'rgb.png', label: 'Sentinel-2 RGB',
    desc: 'True-colour image of the analysed area.' },
  { id: 'confidence', file: 'confidence.png', label: 'Data confidence',
    desc: 'Rock = high; vegetation / water / cloud / nodata = low.' },
]

/**
 * Priority bands for the targets list, applied to the within-scene percentile.
 * These are presentation buckets over a RELATIVE index — they are not calibrated
 * probabilities and carry no implied likelihood of mineralisation.
 */
export const PRIORITY_BANDS = [
  { min: 95, label: 'High', cls: 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10' },
  { min: 80, label: 'Moderate', cls: 'text-cyan-300 border-cyan-400/40 bg-cyan-400/10' },
  { min: 50, label: 'Low', cls: 'text-amber-300 border-amber-400/40 bg-amber-400/10' },
  { min: 0, label: 'Background', cls: 'text-zinc-400 border-white/15 bg-white/5' },
]

export function priorityFor(percentile: number | null) {
  if (percentile === null || percentile === undefined) return null
  return PRIORITY_BANDS.find(b => percentile >= b.min) ?? PRIORITY_BANDS[PRIORITY_BANDS.length - 1]
}

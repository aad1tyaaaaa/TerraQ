// Parse a typed location that is already a coordinate, so the user can paste a
// precise point instead of hunting for a place name.
//
// Accepted:
//   37.7499, -117.6342          decimal, comma or whitespace separated
//   37.7499 -117.6342
//   37.7499N 117.6342W          hemisphere suffixes (or prefixes)
//   37°44'59.6"N 117°38'03.1"W  degrees / minutes / seconds
//   37 44 59.6 N, 117 38 3.1 W
//
// Returns null when the text is not a coordinate, so the caller falls through to
// place-name geocoding.

export interface ParsedCoord {
  lat: number
  lon: number
  /** How it was written, for the UI to echo back. */
  kind: 'decimal' | 'dms'
}

const NS = /[NnSs]/
const EW = /[EeWw]/

function applyHemisphere(value: number, hemi: string | undefined) {
  if (!hemi) return value
  const h = hemi.toUpperCase()
  const mag = Math.abs(value)
  return h === 'S' || h === 'W' ? -mag : mag
}

function dmsToDeg(d: number, m = 0, s = 0) {
  // Sign lives on the degrees component for negative decimal-style input.
  const sign = d < 0 ? -1 : 1
  return sign * (Math.abs(d) + m / 60 + s / 3600)
}

export function parseCoordinates(raw: string): ParsedCoord | null {
  const text = raw.trim()
  if (!text) return null

  // --- decimal pair ---------------------------------------------------------
  const dec = text.match(
    /^([NnSs])?\s*(-?\d{1,3}(?:\.\d+)?)\s*([NnSs])?\s*[, ]\s*([EeWw])?\s*(-?\d{1,3}(?:\.\d+)?)\s*([EeWw])?$/,
  )
  if (dec) {
    const [, nsA, latS, nsB, ewA, lonS, ewB] = dec
    const lat = applyHemisphere(parseFloat(latS), nsA || nsB)
    const lon = applyHemisphere(parseFloat(lonS), ewA || ewB)
    if (inRange(lat, lon)) return { lat, lon, kind: 'decimal' }
  }

  // --- degrees / minutes / seconds -----------------------------------------
  // Pull two groups of up to three numbers, each optionally followed by a letter.
  const dmsRe =
    /(-?\d{1,3})\s*[°d:\s]\s*(\d{1,2}(?:\.\d+)?)?\s*['’m:\s]?\s*(\d{1,2}(?:\.\d+)?)?\s*["”s]?\s*([NnSsEeWw])?/g
  const groups: { deg: number; min: number; sec: number; hemi?: string }[] = []
  let mt: RegExpExecArray | null
  while ((mt = dmsRe.exec(text)) !== null && groups.length < 2) {
    if (mt[0].trim() === '') continue
    groups.push({
      deg: parseFloat(mt[1]),
      min: mt[2] ? parseFloat(mt[2]) : 0,
      sec: mt[3] ? parseFloat(mt[3]) : 0,
      hemi: mt[4],
    })
  }
  if (groups.length === 2 && (NS.test(text) || EW.test(text))) {
    let [a, b] = groups
    // "117W 37N" — swap if the hemispheres say the order is lon-first.
    if (a.hemi && EW.test(a.hemi) && b.hemi && NS.test(b.hemi)) [a, b] = [b, a]
    const lat = applyHemisphere(dmsToDeg(a.deg, a.min, a.sec), a.hemi)
    const lon = applyHemisphere(dmsToDeg(b.deg, b.min, b.sec), b.hemi)
    if (inRange(lat, lon)) return { lat, lon, kind: 'dms' }
  }

  return null
}

function inRange(lat: number, lon: number) {
  return (
    Number.isFinite(lat) && Number.isFinite(lon) &&
    Math.abs(lat) <= 90 && Math.abs(lon) <= 180
  )
}

/** Pretty label for a parsed coordinate. */
export function formatCoord(lat: number, lon: number) {
  return `${lat.toFixed(4)}, ${lon.toFixed(4)}`
}

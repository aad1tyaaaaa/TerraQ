// Nominatim geocoding proxy.
//
// Nominatim's usage policy requires an identifying User-Agent and at most ~1
// request per second. Both are enforced here rather than in the browser, so the
// policy holds no matter how fast someone types. Results are cached per query.
//
// Beyond a plain lookup this does two things the raw API does not:
//   * returns a short name + a separate context line (state / country), so the
//     dropdown is scannable instead of one long comma-soup string
//   * falls back to a relaxed query when the exact text finds nothing, and marks
//     the result `approximate` so the UI can say "nearest match" rather than
//     silently pretending it found what was asked for

const OPEN_METEO = 'https://geocoding-api.open-meteo.com/v1/search'
const NOMINATIM = 'https://nominatim.openstreetmap.org/search'
const UA = 'terraq-explorer/1.0 (research prototype; mineral prospecting demo)'
const TTL_MS = 24 * 60 * 60 * 1000
const MIN_INTERVAL_MS = 1100

export interface GeoHit {
  name: string
  context: string
  lat: number
  lon: number
  kind: string
  approximate?: boolean
}

/**
 * Open-Meteo's geocoder: key-free, fast, and not aggressively rate-limited,
 * which is why it runs first. The public Nominatim instance returns HTTP 429 to
 * a shared IP under light use — during testing it rejected every lookup — so
 * relying on it alone made the search box silently return nothing.
 * Its weakness is coverage: populated places only, no bays, lakes or regions.
 */
async function queryOpenMeteo(q: string, limit: number): Promise<GeoHit[]> {
  const name = q.split(',')[0].trim()
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), 5000)
  try {
    const url = `${OPEN_METEO}?name=${encodeURIComponent(name)}` +
                `&count=${limit}&language=en&format=json`
    const r = await fetch(url, { signal: ctl.signal, headers: { 'User-Agent': UA } })
    if (!r.ok) return []
    const j = await r.json()
    return (j?.results ?? []).map((x: any) => ({
      name: x.name,
      context: [x.admin1, x.country].filter(Boolean).join(', '),
      lat: +Number(x.latitude).toFixed(4),
      lon: +Number(x.longitude).toFixed(4),
      kind: (x.feature_code || '').startsWith('PPL') ? 'place' : '',
    }))
  } catch {
    return []
  } finally {
    clearTimeout(timer)
  }
}

const cache = new Map<string, { at: number; results: GeoHit[] }>()
let lastCall = 0

/** "Clayton Valley, Esmeralda County, Nevada, United States" -> name + context. */
function split(display: string, addr: Record<string, string> | undefined) {
  const parts = display.split(',').map(p => p.trim()).filter(Boolean)
  const name = parts[0] ?? display
  const context = addr
    ? [addr.state || addr.county || addr.region, addr.country]
        .filter(Boolean).join(', ')
    : parts.slice(1).slice(-2).join(', ')
  return { name, context }
}

async function queryNominatim(q: string, limit: number): Promise<any[]> {
  // Serialise and space out upstream calls to respect the usage policy.
  const wait = Math.max(0, MIN_INTERVAL_MS - (Date.now() - lastCall))
  if (wait > 0) await new Promise(r => setTimeout(r, wait))
  lastCall = Date.now()

  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), 6000)
  try {
    const url =
      `${NOMINATIM}?q=${encodeURIComponent(q)}&format=jsonv2` +
      `&addressdetails=1&limit=${limit}`
    const r = await fetch(url, { signal: ctl.signal, headers: { 'User-Agent': UA } })
    if (!r.ok) throw new Error(`nominatim HTTP ${r.status}`)
    return (await r.json()) as any[]
  } finally {
    clearTimeout(timer)
  }
}

function toHits(rows: any[], approximate = false): GeoHit[] {
  const seen = new Set<string>()
  const out: GeoHit[] = []
  for (const x of rows) {
    const lat = +Number(x.lat).toFixed(4)
    const lon = +Number(x.lon).toFixed(4)
    const key = `${lat},${lon}`
    if (seen.has(key)) continue          // Nominatim often repeats a place
    seen.add(key)
    const { name, context } = split(x.display_name ?? '', x.address)
    out.push({
      name,
      context,
      lat,
      lon,
      kind: (x.type || x.category || '').replace(/_/g, ' '),
      ...(approximate ? { approximate: true } : {}),
    })
  }
  return out
}

export async function geocode(qRaw: string | null) {
  const q = (qRaw ?? '').trim()
  if (q.length < 2) return { status: 200, body: { results: [] } }

  const key = q.toLowerCase()
  const hit = cache.get(key)
  if (hit && Date.now() - hit.at < TTL_MS) {
    return { status: 200, body: { results: hit.results, cached: true } }
  }

  // Open-Meteo first (fast, reliable), Nominatim only to fill the gaps it has
  // — bays, lakes, regions and other non-settlement features.
  let results = await queryOpenMeteo(q, 6)
  let rateLimited = false

  if (results.length < 3) {
    try {
      const extra = toHits(await queryNominatim(q, 6))
      const seen = new Set(results.map(r => `${r.lat},${r.lon}`))
      for (const e of extra) {
        if (!seen.has(`${e.lat},${e.lon}`)) { results.push(e); seen.add(`${e.lat},${e.lon}`) }
      }
    } catch (e: any) {
      if (String(e?.message ?? e).includes('429')) rateLimited = true
    }
  }

  // Still nothing: retry looser, dropping the most specific token — usually the
  // mistyped one — and mark the result so the UI can say "nearest match".
  if (results.length === 0 && !rateLimited) {
    const words = q.split(/\s+/)
    const relaxed = words.length > 1 ? words.slice(0, -1).join(' ') : q.slice(0, -2)
    if (relaxed.length >= 2) {
      results = (await queryOpenMeteo(relaxed, 4)).map(r => ({ ...r, approximate: true }))
    }
  }

  cache.set(key, { at: Date.now(), results })
  return {
    status: 200,
    body: {
      results,
      // Surfaced so the UI can say WHY nothing came back, instead of implying
      // the place does not exist.
      ...(rateLimited && results.length === 0
        ? { error: 'rate_limited',
            message: 'Map search is temporarily rate-limited. Known mineral sites and coordinates still work.' }
        : {}),
    },
  }
}

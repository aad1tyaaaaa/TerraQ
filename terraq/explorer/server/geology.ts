// Macrostrat proxy, kept here so the route file under app/ stays a thin re-export.
//
// Why proxy at all: calling Macrostrat from the browser is a cross-origin request
// we do not control, and we want a short timeout plus a cache so a slow third
// party can never stall the panel.
//
// This is reference data only. It is displayed for context and never feeds any
// score the pipeline computes.

const MACROSTRAT = 'https://macrostrat.org/api/v2/geologic_units/map'
const TIMEOUT_MS = 5000
const TTL_MS = 60 * 60 * 1000

// Process-local cache. Resets on server restart, which is fine for a demo.
const cache = new Map<string, { at: number; body: unknown }>()

export async function geologyAt(latRaw: string | null, lngRaw: string | null) {
  const lat = Number(latRaw)
  const lng = Number(lngRaw)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return { status: 400, body: { error: 'lat and lng required' } }
  }

  const key = `${lat.toFixed(3)},${lng.toFixed(3)}`
  const hit = cache.get(key)
  if (hit && Date.now() - hit.at < TTL_MS) {
    return { status: 200, body: hit.body }
  }

  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS)
  try {
    const r = await fetch(`${MACROSTRAT}?lat=${lat}&lng=${lng}`, {
      signal: ctl.signal,
      headers: { 'User-Agent': 'terraq-explorer/1.0 (research prototype)' },
    })
    if (!r.ok) throw new Error(`macrostrat HTTP ${r.status}`)
    const j = await r.json()
    const u = j?.success?.data?.[0]

    const body = u
      ? {
          unit: {
            name: u.name ?? u.strat_name ?? null,
            lith: u.lith ?? null,
            age: u.b_age && u.t_age ? `${u.t_age}–${u.b_age} Ma` : (u.age ?? null),
            source: 'Macrostrat /api/v2/geologic_units/map',
          },
        }
      : { unit: null, note: 'No mapped unit at this location.' }

    cache.set(key, { at: Date.now(), body })
    return { status: 200, body }
  } catch (e: any) {
    // Never fail loudly — the panel degrades to "could not reach Macrostrat".
    return {
      status: 200,
      body: { unit: null, error: e?.name === 'AbortError' ? 'timeout' : String(e?.message ?? e) },
    }
  } finally {
    clearTimeout(timer)
  }
}

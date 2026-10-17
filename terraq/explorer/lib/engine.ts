// Client for the Python engine (product/server.py).
// Override the base URL with NEXT_PUBLIC_ENGINE_URL; defaults to :8765.

import type {
  AnalyzeResult, JobSummary, PointResponse, SampleResponse, TargetsResponse,
} from './types'

export const ENGINE =
  process.env.NEXT_PUBLIC_ENGINE_URL || 'http://localhost:8765'

/** Absolute URL for a file inside a job folder (overlays included). */
export function jobFile(base: string, file: string) {
  return `${ENGINE}${base}/${file}`
}

export class EngineUnreachable extends Error {}

async function getJSON<T>(path: string, timeoutMs = 15000): Promise<T> {
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), timeoutMs)
  try {
    const r = await fetch(`${ENGINE}${path}`, { signal: ctl.signal })
    if (!r.ok) throw new EngineUnreachable(`${path} -> HTTP ${r.status}`)
    return (await r.json()) as T
  } catch (e: any) {
    throw new EngineUnreachable(e?.message || 'engine unreachable')
  } finally {
    clearTimeout(t)
  }
}

/** Cached analyses. Used to show which areas already have results offline. */
export async function fetchJobs(): Promise<JobSummary[]> {
  const d = await getJSON<{ ok: boolean; jobs: JobSummary[] }>('/api/jobs')
  return d.jobs ?? []
}

/**
 * S1 — lithium index + percentile + confidence class at one point.
 * Returns nulls with a reason when the point is outside the AOI or masked.
 */
export async function sampleLithium(
  job: string, lat: number, lon: number,
): Promise<SampleResponse> {
  return getJSON<SampleResponse>(
    `/api/sample?job=${encodeURIComponent(job)}&lat=${lat}&lon=${lon}`,
  )
}

/** S2 — anomaly clusters detected in a job's lithium raster. */
export async function fetchTargets(job: string): Promise<TargetsResponse> {
  return getJSON<TargetsResponse>(
    `/api/targets?job=${encodeURIComponent(job)}`, 30000,
  )
}

/** Index value + percentile at one point of an analysed job. */
export async function samplePoint(
  job: string, lat: number, lon: number,
): Promise<PointResponse> {
  return getJSON<PointResponse>(
    `/api/point?job=${encodeURIComponent(job)}&lat=${lat}&lon=${lon}`,
  )
}

/**
 * Run (or fetch from cache) an analysis.
 * A cold request streams Sentinel-2 from S3 and can take minutes, hence the
 * long timeout — the engine also serializes runs behind a single lock.
 */
export async function analyze(
  lat: number, lon: number, km: number, timeoutMs = 600000,
): Promise<AnalyzeResult> {
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), timeoutMs)
  try {
    const r = await fetch(`${ENGINE}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lon, km }),
      signal: ctl.signal,
    })
    return (await r.json()) as AnalyzeResult
  } catch (e: any) {
    throw new EngineUnreachable(e?.message || 'engine unreachable')
  } finally {
    clearTimeout(t)
  }
}

/** Is the engine answering at all? Used to switch the UI into cached-only mode. */
export async function engineReachable(): Promise<boolean> {
  try {
    const ctl = new AbortController()
    const t = setTimeout(() => ctl.abort(), 4000)
    const r = await fetch(`${ENGINE}/api/jobs`, { signal: ctl.signal })
    clearTimeout(t)
    return r.ok
  } catch {
    return false
  }
}

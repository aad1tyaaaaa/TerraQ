'use client'

// S5 — geology lookup lifted out of the panel so S3 (AI explanation) can read the
// same result instead of fetching it a second time.
//
// Hits our own /api/geology route, which proxies Macrostrat with a 5 s timeout and
// an in-memory cache. The route never throws: a failure comes back as
// { unit: null, error } so the panel can degrade instead of breaking.

import { useEffect, useState } from 'react'

export interface GeologyUnit {
  name?: string | null
  lith?: string | null
  age?: string | null
  source?: string
}

export type GeologyState = 'loading' | 'ok' | 'none' | 'error'

export function useGeology(lat: number, lon: number) {
  const [unit, setUnit] = useState<GeologyUnit | null>(null)
  const [state, setState] = useState<GeologyState>('loading')

  useEffect(() => {
    let cancelled = false
    setState('loading')
    setUnit(null)

    fetch(`/api/geology?lat=${lat}&lng=${lon}`)
      .then(r => r.json())
      .then(d => {
        if (cancelled) return
        if (d?.error && !d?.unit) { setState('error'); return }
        if (d?.unit?.name || d?.unit?.lith) { setUnit(d.unit); setState('ok') }
        else setState('none')
      })
      .catch(() => { if (!cancelled) setState('error') })

    return () => { cancelled = true }
  }, [lat, lon])

  return { unit, state }
}

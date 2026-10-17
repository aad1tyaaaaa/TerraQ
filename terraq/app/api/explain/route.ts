// Thin route shim — logic lives in terraq/explorer/server/explain.ts.
// API keys are read there via process.env and never leave the server.

import { explainTarget, type ExplainFacts } from '@/explorer/server/explain'

export async function POST(request: Request) {
  let facts: ExplainFacts
  let cacheKey: string
  try {
    const body = await request.json()
    facts = body?.facts ?? {}
    cacheKey = String(body?.cacheKey ?? JSON.stringify(facts).slice(0, 200))
  } catch {
    return Response.json({ error: 'bad request' }, { status: 400 })
  }

  const result = await explainTarget(facts, cacheKey)
  return Response.json(result)
}

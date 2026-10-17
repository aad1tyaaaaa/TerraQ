// Thin route shim — all logic lives in terraq/explorer/server/geology.ts.
// A Next.js route handler must physically live under app/, so this file exists
// only to satisfy that convention.

import { geologyAt } from '@/explorer/server/geology'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const { status, body } = await geologyAt(
    searchParams.get('lat'),
    searchParams.get('lng'),
  )
  return Response.json(body, { status })
}

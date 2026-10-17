// Thin route shim — logic lives in terraq/explorer/server/geocode.ts.

import { geocode } from '@/explorer/server/geocode'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const { status, body } = await geocode(searchParams.get('q'))
  return Response.json(body, { status })
}

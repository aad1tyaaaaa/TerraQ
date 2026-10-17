// Thin route shim — logic lives in terraq/explorer/server/assistant.ts.
// API keys are read there via process.env and never reach the client.

import { askAssistant, type AssistantTurn } from '@/explorer/server/assistant'

export async function POST(request: Request) {
  let history: AssistantTurn[]
  try {
    const body = await request.json()
    history = Array.isArray(body?.messages) ? body.messages.slice(-10) : []
  } catch {
    return Response.json({ error: 'bad request' }, { status: 400 })
  }
  if (history.length === 0) {
    return Response.json({ error: 'no messages' }, { status: 400 })
  }
  return Response.json(await askAssistant(history))
}

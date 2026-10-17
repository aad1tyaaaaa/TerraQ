// A general-knowledge assistant for picking WHERE to look.
//
// This is deliberately walled off from everything else in the Explorer. The rest
// of the app only ever shows numbers the engine measured; this surface answers
// from a language model's training data, which is a completely different kind of
// claim. Mixing the two would let an invented "deposit" sit next to a measured
// 98th-percentile reading and read as equally evidenced.
//
// So the contract is:
//   * it may discuss geography, geology, valleys, basins, known mining districts
//   * it may suggest coordinates worth analysing
//   * it may NEVER state that a mineral is present anywhere, or quote a score
//   * every answer is labelled "general knowledge" in the UI
//   * anything quantitative has to come from pressing Analyze
//
// Suggested places come back on `COORDS:` lines, which the UI turns into buttons
// that hand the coordinate to the engine — the one honest path from "where
// should I look" to an actual measurement.

export type AssistantSource = 'groq' | 'groq-fallback' | 'gemini' | 'unavailable'

export interface AssistantTurn {
  role: 'user' | 'assistant'
  content: string
}

const SYSTEM = [
  'You help a geologist decide WHERE to point a satellite mineral-prospecting tool.',
  'You answer from general knowledge of geography and geology — valleys, basins,',
  'pegmatite belts, salars, known mining districts — worldwide, including India.',
  '',
  'Hard rules you must never break:',
  '- NEVER state or imply that a mineral deposit exists at a location. You discuss',
  '  what a region is geologically known for, not what is there now.',
  '- NEVER invent or quote a score, percentile, grade, tonnage or probability.',
  '  You have no measurements. The tool produces those, you do not.',
  '- If you are unsure whether something is accurate, say so plainly.',
  '- Make clear that anything you say is background knowledge that must be checked',
  '  by actually running the analysis.',
  '',
  'When you suggest somewhere worth analysing, end your reply with one line per',
  'place, in exactly this form and nothing else on the line:',
  'COORDS: <lat>, <lon> — <short place name>',
  'Give at most 4. Use decimal degrees. Only suggest places you are reasonably',
  'confident actually exist at those coordinates.',
  '',
  'Keep prose under 120 words. Plain sentences, no markdown headings or bullets.',
].join('\n')

export interface AssistantReply {
  text: string
  places: { lat: number; lon: number; name: string }[]
  source: AssistantSource
  error?: string
}

/** Pull the COORDS: lines out of the model's reply and off the visible text. */
function extractPlaces(raw: string) {
  const places: { lat: number; lon: number; name: string }[] = []
  const lines = raw.split('\n')
  const kept: string[] = []

  for (const line of lines) {
    const m = line.match(
      /^\s*COORDS:\s*(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*[—–-]\s*(.+?)\s*$/i,
    )
    if (m) {
      const lat = parseFloat(m[1])
      const lon = parseFloat(m[2])
      if (Math.abs(lat) <= 90 && Math.abs(lon) <= 180 && places.length < 4) {
        places.push({ lat, lon, name: m[3].replace(/[*_`]/g, '').trim() })
      }
      continue
    }
    kept.push(line)
  }
  return { text: kept.join('\n').trim(), places }
}

function clean(raw: string) {
  return raw
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .replace(/^#+\s.*$/gm, '')
    .trim()
}

async function callGroq(
  model: string, apiKey: string, history: AssistantTurn[],
): Promise<string | null> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), 12000)
  try {
    const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      signal: ctl.signal,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        temperature: 0.4,
        max_completion_tokens: 900,
        reasoning_effort: 'low',   // gpt-oss: keep the trace short and hidden
        messages: [{ role: 'system', content: SYSTEM }, ...history],
      }),
    })
    if (!r.ok) return null
    const j = await r.json()
    if (j?.choices?.[0]?.finish_reason === 'length') {
      // Truncated: better to retry/fall through than show half a sentence.
      const partial = j?.choices?.[0]?.message?.content
      return typeof partial === 'string' && /[.!?]\s*$/.test(partial.trim())
        ? clean(partial) : null
    }
    const text = j?.choices?.[0]?.message?.content
    return typeof text === 'string' && text.trim() ? clean(text) : null
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

async function callGemini(
  apiKey: string, history: AssistantTurn[],
): Promise<string | null> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), 12000)
  try {
    const r = await fetch(
      'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
      {
        method: 'POST',
        signal: ctl.signal,
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': apiKey },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: SYSTEM }] },
          contents: history.map(h => ({
            role: h.role === 'assistant' ? 'model' : 'user',
            parts: [{ text: h.content }],
          })),
          generationConfig: { temperature: 0.4, maxOutputTokens: 900 },
        }),
      },
    )
    if (!r.ok) return null
    const j = await r.json()
    const text = j?.candidates?.[0]?.content?.parts?.[0]?.text
    return typeof text === 'string' && text.trim() ? clean(text) : null
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

export async function askAssistant(history: AssistantTurn[]): Promise<AssistantReply> {
  const groqKey = process.env.GROQ_API_KEY
  const geminiKey = process.env.GEMINI_API_KEY
  const primary = process.env.GROQ_MODEL
  const fallback = process.env.GROQ_FALLBACK_MODEL

  const attempts: { source: AssistantSource; run: () => Promise<string | null> }[] = []
  if (groqKey && primary) {
    attempts.push({ source: 'groq', run: () => callGroq(primary, groqKey, history) })
  }
  if (groqKey && fallback) {
    attempts.push({
      source: 'groq-fallback', run: () => callGroq(fallback, groqKey, history),
    })
  }
  if (geminiKey) {
    attempts.push({ source: 'gemini', run: () => callGemini(geminiKey, history) })
  }

  for (const a of attempts) {
    const raw = await a.run()
    if (!raw) continue
    const { text, places } = extractPlaces(raw)
    if (!text) continue
    return { text, places, source: a.source }
  }

  // No key configured, or every provider failed. There is no honest canned
  // answer to an open question, so say so rather than inventing one.
  return {
    text:
      'The assistant is unavailable — no language-model provider is configured or ' +
      'reachable. Everything else in the Explorer still works: use the search box ' +
      'or the map to pick a location and press Analyze Region for measured results.',
    places: [],
    source: 'unavailable',
  }
}

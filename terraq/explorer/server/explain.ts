// S3 — grounded explanation of one target.
//
// Server-side only. Keys are read from process.env inside this module and never
// returned, logged, or sent to the client.
//
// Provider chain: GROQ_MODEL -> GROQ_FALLBACK_MODEL -> Gemini (only if a key is
// set) -> deterministic template. The template always exists, so the demo works
// with zero keys configured.
//
// Grounding is enforced twice:
//   1. The prompt carries ONLY real measured fields and forbids new numbers.
//   2. A post-check rejects any reply containing a number that is not present in
//      the input. A model that invents a figure gets discarded, not displayed.

export interface ExplainFacts {
  target?: {
    id?: string
    area_km2?: number | null
    peak_percentile?: number | null
    peak_score?: number | null
    mean_confidence?: number | null
    nearest_reference_site?: string | null
    nearest_reference_km?: number | null
  } | null
  sample?: {
    status?: string
    li_score?: number | null
    li_percentile_in_aoi?: number | null
    confidence_class?: string | null
    reason?: string | null
  } | null
  confidence_summary?: {
    high_pct?: number | null
    low_pct?: number | null
    masked_pct?: number | null
  } | null
  coverage?: number | null
  date_range?: string | null
  geology?: { name?: string | null; lith?: string | null; age?: string | null } | null
  capability_note?: string | null
  lat?: number
  lon?: number
}

export type ExplainSource = 'groq' | 'groq-fallback' | 'gemini' | 'template'

const SYSTEM = [
  'You explain one mineral-exploration target to a geologist.',
  'Use ONLY the numbers given in the user message. Never introduce a number that is not there.',
  'The lithium value is a RELATIVE 0-1 surface-alteration index and its percentile within one satellite scene.',
  'Never call it a probability, a likelihood, a grade, a concentration, or a chance of mineralisation.',
  'Always mention at least one real limitation: the method sees surface alteration only,',
  'and brine lithium dissolved beneath a playa cannot be detected optically.',
  'Write 3 to 4 sentences of plain prose. No headings, no bullet points, no markdown.',
  'End with exactly one recommended next step: either soil/rock-chip sampling or a hyperspectral follow-up survey.',
].join(' ')

/** Every number that legitimately appears in the input, as strings. */
function allowedNumbers(facts: ExplainFacts): Set<string> {
  const out = new Set<string>()
  const walk = (v: unknown) => {
    if (typeof v === 'number' && Number.isFinite(v)) {
      out.add(String(v))
      out.add(String(Math.round(v)))
      out.add(v.toFixed(1))
      out.add(v.toFixed(2))
      out.add(v.toFixed(3))
      // percentiles are often written "98th"
      out.add(String(Math.round(v)))
    } else if (typeof v === 'string') {
      ;(v.match(/\d+(?:\.\d+)?/g) || []).forEach(n => out.add(n))
    } else if (Array.isArray(v)) v.forEach(walk)
    else if (v && typeof v === 'object') Object.values(v).forEach(walk)
  }
  walk(facts)
  // Small integers used in ordinary prose ("one", "3 to 4 sentences", years).
  ;['0', '1', '2', '3', '4', '100'].forEach(n => out.add(n))
  return out
}

/**
 * Reject a reply that contains a number absent from the input.
 * Returns the offending token, or null when the text is clean.
 */
export function findInventedNumber(text: string, facts: ExplainFacts): string | null {
  const allowed = allowedNumbers(facts)
  const found = text.match(/\d+(?:\.\d+)?/g) || []
  for (const n of found) {
    if (allowed.has(n)) continue
    // tolerate a trailing-zero spelling difference, e.g. 98.0 written as 98
    const f = parseFloat(n)
    if ([...allowed].some(a => Math.abs(parseFloat(a) - f) < 1e-9)) continue
    return n
  }
  return null
}

/** Deterministic fallback — no network, always available. */
export function templateExplanation(f: ExplainFacts): string {
  const parts: string[] = []
  const t = f.target
  const s = f.sample

  if (t?.id) {
    parts.push(
      `Target ${t.id} is a ${t.area_km2 ?? '—'} km² cluster of elevated clay/Al-OH ` +
      `surface alteration, peaking at the ${t.peak_percentile ?? '—'}th percentile of ` +
      `this scene on a relative 0-1 index.`,
    )
  } else if (s?.status === 'scored') {
    parts.push(
      `The selected point scores ${s.li_score} on a relative 0-1 alteration index, ` +
      `at the ${s.li_percentile_in_aoi}th percentile of this scene.`,
    )
  } else {
    parts.push(
      `No alteration value could be computed at this point` +
      (s?.reason ? ` (${s.reason})` : '') + `.`,
    )
  }

  if (t?.nearest_reference_site && t?.nearest_reference_km != null) {
    parts.push(
      `The nearest catalogued USGS site is ${t.nearest_reference_site.replace(/^(Li|V):/, '')}, ` +
      `about ${t.nearest_reference_km} km away.`,
    )
  }
  if (f.geology?.name) {
    parts.push(`Mapped bedrock here is ${f.geology.name}.`)
  }
  if (f.confidence_summary?.high_pct != null) {
    parts.push(
      `${f.confidence_summary.high_pct}% of the analysed area is high-confidence rock.`,
    )
  }

  parts.push(
    `This is surface alteration only — it is not a probability of mineralisation, and ` +
    `brine lithium dissolved beneath a playa cannot be detected optically at any score.`,
  )
  parts.push(
    `Recommended next step: soil and rock-chip sampling across the anomaly before any ` +
    `drill planning.`,
  )
  return parts.join(' ')
}

/** Strip any reasoning the model leaked into the visible answer. */
function cleanReply(raw: string): string {
  let t = raw.trim()
  t = t.replace(/<think>[\s\S]*?<\/think>/gi, '')
  t = t.replace(/<\/?[a-z_]+>/gi, '')
  t = t.replace(/^\s*(analysis|reasoning|thought)\s*:[\s\S]*?(?=\n\n|$)/i, '')
  t = t.replace(/^#+\s.*$/gm, '')
  t = t.replace(/^[-*]\s+/gm, '')
  return t.replace(/\s+/g, ' ').trim()
}

async function callGroq(
  model: string, facts: ExplainFacts, apiKey: string,
): Promise<string | null> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), 8000)
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
        temperature: 0.2,
        // The brief said ~200 tokens, but gpt-oss is a reasoning model and its
        // reasoning tokens are billed against this same budget — at 200 the
        // visible answer was being cut off mid-sentence, losing the required
        // "next step". 700 leaves room for low-effort reasoning plus 3-4
        // sentences; the prompt still constrains the answer's length.
        max_completion_tokens: 700,
        // gpt-oss is a reasoning model: keep effort low and never show the trace.
        reasoning_effort: 'low',
        messages: [
          { role: 'system', content: SYSTEM },
          { role: 'user', content: JSON.stringify(facts) },
        ],
      }),
    })
    if (!r.ok) return null
    const j = await r.json()
    const msg = j?.choices?.[0]?.message
    // Only the final answer; `reasoning` is deliberately ignored.
    const text = typeof msg?.content === 'string' ? msg.content : ''
    if (!text) return null
    // A truncated answer (hit the token ceiling) loses the required next step,
    // so treat it as a failure and fall through rather than showing a fragment.
    if (j?.choices?.[0]?.finish_reason === 'length') return null
    return cleanReply(text)
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

async function callGemini(facts: ExplainFacts, apiKey: string): Promise<string | null> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), 8000)
  try {
    const r = await fetch(
      'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
      {
        method: 'POST',
        signal: ctl.signal,
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': apiKey },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: SYSTEM }] },
          contents: [{ role: 'user', parts: [{ text: JSON.stringify(facts) }] }],
          generationConfig: { temperature: 0.2, maxOutputTokens: 200 },
        }),
      },
    )
    if (!r.ok) return null
    const j = await r.json()
    const text = j?.candidates?.[0]?.content?.parts?.[0]?.text
    return text ? cleanReply(text) : null
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

// Per-target cache so repeat clicks never hit the API again.
const cache = new Map<string, { text: string; source: ExplainSource }>()

export async function explainTarget(facts: ExplainFacts, cacheKey: string) {
  const hit = cache.get(cacheKey)
  if (hit) return { ...hit, cached: true }

  const groqKey = process.env.GROQ_API_KEY
  const geminiKey = process.env.GEMINI_API_KEY
  const primary = process.env.GROQ_MODEL
  const fallback = process.env.GROQ_FALLBACK_MODEL

  const attempts: { source: ExplainSource; run: () => Promise<string | null> }[] = []
  if (groqKey && primary) {
    attempts.push({ source: 'groq', run: () => callGroq(primary, facts, groqKey) })
  }
  if (groqKey && fallback) {
    attempts.push({
      source: 'groq-fallback', run: () => callGroq(fallback, facts, groqKey),
    })
  }
  if (geminiKey) {
    attempts.push({ source: 'gemini', run: () => callGemini(facts, geminiKey) })
  }

  for (const a of attempts) {
    const text = await a.run()
    if (!text) continue
    const bad = findInventedNumber(text, facts)
    if (bad) {
      // Grounding violated — discard and fall through to the next provider.
      continue
    }
    // Reject anything that still reads as a fragment.
    if (!/[.!?]\s*$/.test(text)) continue
    const out = { text, source: a.source }
    cache.set(cacheKey, out)
    return { ...out, cached: false }
  }

  const out = { text: templateExplanation(facts), source: 'template' as ExplainSource }
  cache.set(cacheKey, out)
  return { ...out, cached: false }
}

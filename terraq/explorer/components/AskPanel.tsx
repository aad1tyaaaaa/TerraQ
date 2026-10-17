'use client'

// The "where should I look" assistant — deliberately a separate surface.
//
// Everything else in the Explorer reports measurements. This reports a language
// model's general knowledge, which is a different kind of claim, so it is
// visually distinct and labelled on every answer. It can suggest regions; it
// cannot tell you what is there. Pressing "Analyze" on a suggestion is the only
// path from a hunch to a number, and that number comes from the engine.
//
// Suggested coordinates are NOT trusted. Models drift on exact numbers (in
// testing it placed Salar de Uyuni about 150 km off), so each suggestion is
// re-geocoded by name through OpenStreetMap first, and only falls back to the
// model's own figure when the name cannot be resolved — flagged when it does.

import { useRef, useState } from 'react'
import { Sparkles, Send, X, Loader2, MapPin, AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface Place { lat: number; lon: number; name: string }
interface Msg {
  role: 'user' | 'assistant'
  content: string
  places?: Place[]
  source?: string
}

const SUGGESTIONS = [
  'Which valleys in India are worth checking for lithium?',
  'Where are the main pegmatite belts worldwide?',
  'What makes a basin favourable for brine lithium?',
]

export function AskPanel({
  onGoTo, onClose,
}: {
  onGoTo: (lat: number, lon: number, label: string) => void
  onClose: () => void
}) {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [resolving, setResolving] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  async function send(text: string) {
    const q = text.trim()
    if (!q || busy) return
    const next: Msg[] = [...msgs, { role: 'user', content: q }]
    setMsgs(next); setInput(''); setBusy(true)
    try {
      const r = await fetch('/api/assistant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: next.map(m => ({ role: m.role, content: m.content })),
        }),
      })
      const d = await r.json()
      setMsgs([...next, {
        role: 'assistant', content: d.text ?? 'No reply.',
        places: d.places ?? [], source: d.source,
      }])
    } catch {
      setMsgs([...next, {
        role: 'assistant',
        content: 'Could not reach the assistant. The rest of the Explorer is unaffected.',
        source: 'unavailable',
      }])
    } finally {
      setBusy(false)
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }))
    }
  }

  /** Trust OpenStreetMap over the model for the actual coordinate. */
  async function goTo(p: Place) {
    setResolving(p.name)
    let { lat, lon } = p
    let verified = false
    try {
      const r = await fetch(`/api/geocode?q=${encodeURIComponent(p.name)}`)
      const d = await r.json()
      const hit = (d.results ?? [])[0]
      // Only accept the geocoder if it lands near what the model said — a very
      // distant "match" usually means it resolved a different place entirely.
      if (hit) {
        const dLat = Math.abs(hit.lat - p.lat)
        const dLon = Math.abs(hit.lon - p.lon)
        if (dLat < 6 && dLon < 6) { lat = hit.lat; lon = hit.lon; verified = true }
      }
    } catch { /* keep the model's coordinate */ }
    setResolving(null)
    onGoTo(lat, lon, verified ? p.name : `${p.name} (unverified)`)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Banner — the wall between this and the measured panel. */}
      <div className="flex items-start gap-2 px-3 py-2 rounded-lg border
                      border-violet-400/30 bg-violet-400/10 mb-3">
        <Sparkles className="w-4 h-4 text-violet-300 shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="text-[12px] font-semibold text-violet-200">
            General knowledge — not measured
          </p>
          <p className="text-[11px] text-violet-200/70 leading-snug">
            Suggests where to look. It cannot tell you what is there — only
            Analyze does that.
          </p>
        </div>
        <button onClick={onClose} aria-label="Close assistant"
                className="ml-auto text-zinc-400 hover:text-zinc-200 shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-0.5">
        {msgs.length === 0 && (
          <div className="space-y-2">
            <p className="text-[12px] text-zinc-400">Try asking:</p>
            {SUGGESTIONS.map(s => (
              <button key={s} onClick={() => send(s)}
                      className="block w-full text-left text-[12px] px-3 py-2 rounded-lg
                                 border border-white/12 bg-white/[0.04]
                                 hover:bg-white/[0.08] transition">
                {s}
              </button>
            ))}
          </div>
        )}

        {msgs.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'text-right' : ''}>
            {m.role === 'user' ? (
              <p className="inline-block text-[12px] px-3 py-2 rounded-lg
                            bg-cyan-400/15 text-cyan-100 max-w-[90%] text-left">
                {m.content}
              </p>
            ) : (
              <div className="rounded-lg border border-violet-400/20 bg-violet-400/[0.06] p-3">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Badge variant="outline"
                         className="text-[10px] py-0 px-1.5 border-violet-400/40 text-violet-300">
                    general knowledge
                  </Badge>
                  {m.source && m.source !== 'unavailable' && (
                    <span className="text-[10px] text-zinc-500">{m.source}</span>
                  )}
                </div>
                <p className="text-[12px] leading-relaxed text-zinc-300 whitespace-pre-line">
                  {m.content}
                </p>

                {m.places && m.places.length > 0 && (
                  <div className="mt-2.5 space-y-1">
                    <p className="text-[11px] text-zinc-500">
                      Go to a place and measure it:
                    </p>
                    {m.places.map(p => (
                      <button key={p.name} onClick={() => goTo(p)}
                              disabled={resolving !== null}
                              className="flex items-center gap-2 w-full text-left text-[12px]
                                         px-2.5 py-1.5 rounded-md border border-white/12
                                         bg-white/[0.04] hover:bg-white/[0.09]
                                         disabled:opacity-50 transition">
                        {resolving === p.name
                          ? <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                          : <MapPin className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                        <span className="truncate">{p.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {busy && (
          <div className="flex items-center gap-2 text-[12px] text-zinc-500">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {msgs.length > 0 && (
        <p className="flex items-start gap-1.5 text-[11px] text-amber-300/70 mt-2 leading-snug">
          <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
          Background knowledge only, and it can be wrong — place names are
          re-checked against OpenStreetMap, but verify anything before acting on it.
        </p>
      )}

      <form onSubmit={e => { e.preventDefault(); send(input) }}
            className="flex gap-2 mt-3 shrink-0">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about a region…"
          className="flex-1 bg-white/5 border border-white/12 rounded-lg px-3 py-2
                     text-[12px] focus:outline-none focus:border-violet-400/50"
        />
        <button type="submit" disabled={busy || !input.trim()}
                aria-label="Send"
                className="px-3 rounded-lg bg-violet-500/80 hover:bg-violet-500
                           disabled:opacity-40 transition">
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  )
}

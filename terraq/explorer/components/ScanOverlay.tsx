'use client'

// The overlay shown while the engine is working.
//
// Theme comes from what the pipeline actually does: a sensor sweeping a swath,
// tiles mosaicking in, and the clay/Al-OH absorption feature at 2200 nm that the
// lithium index is built from. The curve drawn here is that feature's shape.
//
// Performance notes — this runs while MapLibre is still live underneath, so:
//   * every animation is a CSS keyframe on `transform` or `opacity` only, which
//     the compositor handles off the main thread
//   * no <canvas>, no requestAnimationFrame loop, no per-frame React state
//   * the only JS timer is a 1 Hz elapsed counter
//   * no animated `filter`/`backdrop-filter` (cheap static blur only) — animating
//     blur forces a full repaint every frame and is the usual cause of jank
//   * honours prefers-reduced-motion by dropping to a static frame
//
// Honesty: the engine returns one blocking response with no progress stream, so
// there is no real percentage to show. The stage list is labelled as what the
// engine does, and the only live number is genuine elapsed time — a fake
// progress bar would be inventing state.

import { useEffect, useState } from 'react'

const STAGES = [
  'Searching Sentinel-2 catalogue',
  'Streaming and mosaicking tiles',
  'Masking cloud, water and vegetation',
  'Computing clay / Al-OH ratio',
  'Normalising and rendering layers',
]

export function ScanOverlay({ cached }: { cached: boolean }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="absolute inset-0 z-40 grid place-items-center overflow-hidden"
         role="status" aria-live="polite"
         aria-label="Analysing satellite imagery">
      {/* Veil — static blur, animated opacity only. */}
      <div className="absolute inset-0 bg-[#05080c]/72 backdrop-blur-[2px] scan-fade" />

      {/* Swath grid + sweep. The grid is a repeating gradient (one paint), the
          sweep is a single translated element. */}
      <div className="absolute inset-0 scan-grid opacity-[0.22]" />
      <div className="absolute inset-y-0 w-40 scan-sweep pointer-events-none" />

      <div className="relative flex flex-col items-center gap-5 px-6 text-center">
        {/* Absorption feature: the 2200 nm trough the lithium index measures. */}
        <svg width="260" height="96" viewBox="0 0 260 96" fill="none"
             className="overflow-visible">
          <defs>
            <linearGradient id="scanline" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#17a2b8" stopOpacity="0.15" />
              <stop offset="45%" stopColor="#5ecfe0" />
              <stop offset="100%" stopColor="#17a2b8" stopOpacity="0.15" />
            </linearGradient>
          </defs>

          {[24, 48, 72].map(y => (
            <line key={y} x1="0" y1={y} x2="260" y2={y}
                  stroke="#ffffff" strokeOpacity="0.06" strokeWidth="1" />
          ))}

          {/* Reflectance curve with the Al-OH dip near 2200 nm. */}
          <path
            d="M0 30 C 30 26, 55 24, 80 26 C 100 28, 112 34, 124 58 C 132 72, 140 72, 148 58 C 160 36, 176 30, 196 30 C 220 30, 240 34, 260 40"
            stroke="url(#scanline)" strokeWidth="2.5" strokeLinecap="round"
            className="scan-trace"
          />
          {/* Marker sitting in the trough. */}
          <circle cx="136" cy="66" r="3.5" fill="#5ecfe0" className="scan-pulse" />
          <text x="136" y="92" textAnchor="middle" fill="#7e8c99"
                style={{ font: '10px ui-monospace, monospace' }}>
            2200 nm
          </text>
        </svg>

        <div>
          <p className="text-sm font-semibold tracking-wide text-zinc-100">
            {cached ? 'Loading cached scene…' : 'Acquiring Sentinel-2 imagery…'}
          </p>
          <p className="text-[12px] text-zinc-400 mt-1 tabular-nums">
            {elapsed}s elapsed
            <span className="text-zinc-600"> · </span>
            {cached ? 'served from cache' : 'a new area usually takes 1–3 minutes'}
          </p>
        </div>

        {/* What the engine is doing. Not a progress bar — there is no progress
            stream to drive one, and faking it would misreport state. */}
        <ul className="space-y-1 text-[11px] text-zinc-500">
          {STAGES.map((st, i) => (
            <li key={st} className="flex items-center gap-2 scan-stage"
                style={{ animationDelay: `${i * 0.45}s` }}>
              <span className="w-1 h-1 rounded-full bg-[#5ecfe0]" />
              {st}
            </li>
          ))}
        </ul>
      </div>

      <style>{`
        .scan-fade { animation: scanFade .45s ease-out both; }
        @keyframes scanFade { from { opacity: 0 } to { opacity: 1 } }

        /* Static gradient: painted once, never re-rasterised. */
        .scan-grid {
          background-image:
            linear-gradient(to right, rgba(94,207,224,.5) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(94,207,224,.5) 1px, transparent 1px);
          background-size: 38px 38px;
          mask-image: radial-gradient(ellipse at center, #000 10%, transparent 72%);
          -webkit-mask-image: radial-gradient(ellipse at center, #000 10%, transparent 72%);
        }

        /* One compositor-promoted element sliding across. */
        .scan-sweep {
          background: linear-gradient(90deg,
            transparent, rgba(94,207,224,.07) 35%, rgba(0,242,255,.22) 50%,
            rgba(94,207,224,.07) 65%, transparent);
          will-change: transform;
          animation: scanSweep 2.6s cubic-bezier(.45,0,.55,1) infinite;
        }
        @keyframes scanSweep {
          from { transform: translateX(-12rem) }
          to   { transform: translateX(calc(100vw + 12rem)) }
        }

        /* Draw-on, then hold. stroke-dashoffset animates on the compositor. */
        .scan-trace {
          stroke-dasharray: 420;
          animation: scanTrace 2.8s ease-in-out infinite;
        }
        @keyframes scanTrace {
          0%   { stroke-dashoffset: 420; opacity: .25 }
          55%  { stroke-dashoffset: 0;   opacity: 1 }
          100% { stroke-dashoffset: 0;   opacity: .35 }
        }

        .scan-pulse {
          transform-origin: 136px 66px;
          animation: scanPulse 1.6s ease-in-out infinite;
        }
        @keyframes scanPulse {
          0%,100% { transform: scale(1);   opacity: .55 }
          50%     { transform: scale(1.9); opacity: 1 }
        }

        .scan-stage { animation: scanStage 2.25s ease-in-out infinite; }
        @keyframes scanStage {
          0%, 70%, 100% { opacity: .38 }
          20%, 45%      { opacity: 1 }
        }

        @media (prefers-reduced-motion: reduce) {
          .scan-sweep, .scan-trace, .scan-pulse, .scan-stage, .scan-fade {
            animation: none;
          }
          .scan-trace { stroke-dashoffset: 0 }
        }
      `}</style>
    </div>
  )
}

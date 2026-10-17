'use client'

import Link from 'next/link'
import {
  ArrowRight,
  Atom,
  Layers,
  BarChart3,
  Eye,
  Globe,
} from 'lucide-react'
import { ScrollSequence } from '@/components/scroll-sequence'

export default function LandingPage() {
  return (
    <div className="relative w-full overflow-y-auto overflow-x-hidden bg-[#0a0a0f] text-white">
      {/* Background grid */}
      <div className="fixed inset-0 bg-[linear-gradient(rgba(34,211,238,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.03)_1px,transparent_1px)] bg-[size:64px_64px] pointer-events-none" />

      {/* ── HERO ──────────────────────────────────── */}
      <section className="relative min-h-screen flex items-end">
        {/* Background video */}
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 w-full h-full object-cover"
        >
          <source src="/landing-hero.mp4" type="video/mp4" />
        </video>

        {/* Content positioned bottom-left like the reference */}
        <div className="relative z-10 flex flex-col gap-6 px-12 sm:px-16 pb-16 pt-32 max-w-3xl">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/terraq-mark.png" alt=""
                 className="w-9 h-9 rounded-full object-cover ring-1 ring-cyan-400/30" />
            <div className="leading-tight">
              <span className="block text-lg font-semibold tracking-wide">TerraQ</span>
              <span className="block text-[10px] uppercase tracking-[0.2em] text-white/50">
                Quantum Intelligence for Earth Exploration
              </span>
            </div>
          </div>

          {/* Heading */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black leading-[1.1] tracking-tight">
            Quantum Intelligence
            <br />
            for <span className="text-cyan-400">Critical Minerals</span>
          </h1>

          {/* Subtitle */}
          <p className="text-sm sm:text-base text-white/70 leading-relaxed max-w-md">
            A hybrid quantum–classical pipeline that transforms NASA hyperspectral satellite imagery into actionable insights for lithium and vanadium exploration.
          </p>

          {/* Feature pills row with dividers */}
          <div className="flex flex-wrap items-start gap-0 mt-4">
            {[
              { icon: Atom, title: '6-Qubit', desc: 'Quantum\nAutoencoder' },
              { icon: Layers, title: '198-Band', desc: 'Hyperion\nImagery' },
              { icon: Eye, title: 'Unsupervised', desc: 'Anomaly\nDetection' },
              { icon: BarChart3, title: 'High-Resolution', desc: 'Mineral\nMapping' },
            ].map((item, i) => (
              <div key={item.title} className="flex items-start">
                {i > 0 && <div className="w-px h-12 bg-white/20 mx-5 mt-1" />}
                <div className="flex flex-col items-center text-center gap-1">
                  <item.icon className="w-6 h-6 text-cyan-400 mb-1" />
                  <span className="text-xs sm:text-sm font-bold">{item.title}</span>
                  <span className="text-[10px] sm:text-xs text-white/50 whitespace-pre-line">{item.desc}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Entry points */}
          <div className="flex flex-wrap items-center gap-3 mt-4">
            <Link
              href="/dashboard"
              className="group w-fit inline-flex items-center gap-3 px-7 py-3 rounded-xl bg-cyan-500 text-white font-bold text-sm shadow-[0_0_30px_rgba(34,211,238,0.3)] hover:shadow-[0_0_50px_rgba(34,211,238,0.5)] hover:bg-cyan-400 transition-all duration-300"
            >
              Enter Dashboard
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>

            {/* Second entry point: the live exploration console. */}
            <Link
              href="/explorer"
              className="group w-fit inline-flex items-center gap-3 px-7 py-3 rounded-xl border border-cyan-400/40 bg-white/5 backdrop-blur text-white font-bold text-sm hover:bg-white/10 hover:border-cyan-400/70 transition-all duration-300"
            >
              <Globe className="w-4 h-4 text-cyan-400" />
              Open Explorer
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── SCROLL-LINKED FRAME SEQUENCE ───────────── */}
      <ScrollSequence />
    </div>
  )
}

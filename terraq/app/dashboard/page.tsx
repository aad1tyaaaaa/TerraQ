'use client'

import { useState } from 'react'
import { TerraQSidebar } from '@/components/terraq-sidebar'
import { TerraQNavbar } from '@/components/terraq-navbar'
import {
  DetectionRankingCard,
  DetectionQualityCard,
  MineralRecallCard,
  MethodFSpecificityCard,
  LiveMLOutputCard,
  SatelliteMapCard,
} from '@/components/terraq-cards'
import { MethodComparisonChart } from '@/components/terraq-chart'
import { TerraQLiveAnalysis } from '@/components/terraq-live-analysis'
import { ValidationCard } from '@/explorer/components/ValidationCard'
import { BentoGrid, BentoGridItem } from '@/components/ui/bento-grid'
import { MapIcon, CheckCircle2, Cpu, BarChart, Activity, Zap, Layers, Microscope, Info, Satellite, Grid3X3, ArrowDownToLine, BrainCircuit, Scan, ShieldAlert, Sparkles, Download } from 'lucide-react'

type NavItem = 'overview' | 'maps' | 'methods' | 'how' | 'data' | 'live'

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<NavItem>('overview')
  const [selectedScene, setSelectedScene] = useState('scene_001')
  const [selectedMethod, setSelectedMethod] = useState('method_c')

  return (
    <div className="h-screen w-full flex overflow-hidden bg-[#27272A]">
      {/* Sidebar */}
      <TerraQSidebar activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Navbar */}
        <TerraQNavbar />

        {/* Dashboard Content */}
        <div className="flex-1 overflow-y-auto p-8 space-y-8">
          {/* Dashboard Tab Content */}
          {activeTab === 'overview' && (
            <div className="space-y-10 max-w-7xl mx-auto pb-8">

              {/* ── HEADER ─────────────────────────────── */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
                  <p className="text-muted-foreground text-sm mt-0.5">End-to-end pipeline from raw imagery to mineral detection</p>
                </div>
                <div className="flex gap-3 items-center">
                  <select
                    value={selectedScene}
                    onChange={e => setSelectedScene(e.target.value)}
                    className="appearance-none bg-[#1e1e22] border border-white/10 rounded-xl px-5 py-2.5 pr-10 text-sm text-white font-medium shadow-md hover:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/60 transition-all cursor-pointer"
                    style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%2322d3ee' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m4 6 4 4 4-4'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px center' }}
                  >
                    <option value="scene_001">Scene 1 — P43/R34, California (train)</option>
                    <option value="scene_002">Scene 2 — P41/R33, Nevada (train)</option>
                    <option value="scene_003">Scene 3 — P41/R33, Nevada (test)</option>
                  </select>
                  <select
                    value={selectedMethod}
                    onChange={e => setSelectedMethod(e.target.value)}
                    className="appearance-none bg-[#1e1e22] border border-white/10 rounded-xl px-5 py-2.5 pr-10 text-sm text-white font-medium shadow-md hover:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/60 transition-all cursor-pointer"
                    style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%2322d3ee' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m4 6 4 4 4-4'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px center' }}
                  >
                    <option value="method_c">Method C ★ (Best)</option>
                    <option value="method_b">Method B</option>
                    <option value="method_a">Method A</option>
                    <option value="method_f">Method F</option>
                  </select>
                  <button className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-[#1e1e22] text-sm font-bold shadow-[0_0_20px_rgba(34,211,238,0.25)] hover:shadow-[0_0_30px_rgba(34,211,238,0.4)] hover:brightness-110 transition-all active:scale-[0.97]">
                    <Download className="w-4 h-4" />
                    Export Report
                  </button>
                </div>
              </div>

              {/* ── STEP 1: RAW INPUT ──────────────────────────── */}
              <section className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full bg-white/10 text-white text-xs font-bold uppercase tracking-widest">Step 1</span>
                  <h2 className="text-xl font-bold">Raw Input</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="magic-bento-card magic-bento-card--border-glow relative md:col-span-2 rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <img src="/dashboard/hero banner.jpg" alt="Raw Input Scene" className="w-full object-cover" />
                  </div>
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] p-6 flex flex-col justify-between">
                    <div>
                      <p className="text-xs font-semibold text-primary uppercase tracking-widest mb-4">Scene Metadata</p>
                      <div className="space-y-3 text-sm">
                        {[
                          ['Scene', 'EO-1 Hyperion'],
                          ['Resolution', '800 × 800 px'],
                          ['Spectral Bands', '198 bands'],
                          ['Wavelength', '427–2395 nm'],
                          ['Patch Count', '845 tiles'],
                          ['Patch Size', '16 × 16 px'],
                        ].map(([label, value]) => (
                          <div key={label} className="flex justify-between border-b border-white/10 pb-2 last:border-0">
                            <span className="text-muted-foreground">{label}</span>
                            <span className="font-mono text-white">{value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-4 pt-4 border-t border-white/10">Cloud-masked via brightness thresholds. 48% of tiles labeled mineral.</p>
                  </div>
                </div>
              </section>

              {/* ── STEP 2: FEATURE PROCESSING ─────────────────── */}
              <section className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full bg-white/10 text-white text-xs font-bold uppercase tracking-widest">Step 2</span>
                  <h2 className="text-xl font-bold">Feature Processing</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] p-6 space-y-4">
                    <p className="text-xs font-semibold text-primary uppercase tracking-widest">PCA Compression</p>
                    <div className="font-mono text-center text-primary text-sm bg-primary/10 border border-primary/20 rounded-xl p-4">845 × 50,688 → 845 × 25</div>
                    <p className="text-xs text-muted-foreground">Retains ~90% of spectral variance. Removes noise before the quantum stage.</p>
                  </div>
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] p-6 space-y-4">
                    <p className="text-xs font-semibold text-primary uppercase tracking-widest">Quantum Features (QAE)</p>
                    <div className="space-y-2 text-xs font-mono text-muted-foreground bg-white/5 border border-white/10 rounded-xl p-4">
                      {['RY rotation gates', 'CNOT entanglement', 'CZ long-range link'].map(g => (
                        <p key={g} className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />{g}
                        </p>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">6 qubits → 6 quantum features in 64-D Hilbert space.</p>
                  </div>
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] p-6 space-y-4">
                    <p className="text-xs font-semibold text-primary uppercase tracking-widest">Final Feature Vector</p>
                    <div className="space-y-3">
                      {[
                        { label: '25 PCA features', pct: 75 },
                        { label: '6 QAE features', pct: 18 },
                        { label: '2 USGS features', pct: 7 },
                      ].map(f => (
                        <div key={f.label} className="space-y-1">
                          <div className="flex justify-between text-xs text-muted-foreground">
                            <span>{f.label}</span><span>{f.pct}%</span>
                          </div>
                          <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                            <div className="h-full bg-primary rounded-full" style={{ width: `${f.pct}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">33 total features fed to ensemble classifier.</p>
                  </div>
                </div>
              </section>

              {/* ── STEP 3: PREDICTION OUTPUT ──────────────────── */}
              <section className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full bg-white/10 text-white text-xs font-bold uppercase tracking-widest">Step 3</span>
                  <h2 className="text-xl font-bold">Prediction Output</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
                  <div className="magic-bento-card magic-bento-card--border-glow relative md:col-span-3 rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <div className="px-5 pt-4 pb-2 flex items-center justify-between">
                      <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">Detection Probability Heatmap</p>
                    </div>
                    <div className="relative group">
                      <img src="/dashboard/bestmethodmineralmap.jpg" alt="Detection Heatmap" className="w-full object-cover" />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100">
                        <p className="text-white text-sm font-semibold text-center px-6">Higher values indicate higher detection probability</p>
                      </div>
                    </div>
                    <div className="px-5 py-3 flex items-center gap-3">
                      <span className="text-xs text-muted-foreground">Low</span>
                      <div className="h-2 flex-1 rounded-full bg-linear-to-r from-black via-primary/40 to-primary" />
                      <span className="text-xs text-muted-foreground">High</span>
                    </div>
                  </div>
                  <div className="magic-bento-card magic-bento-card--border-glow relative md:col-span-2 rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] p-6 space-y-4">
                    <p className="text-xs font-semibold text-primary uppercase tracking-widest">Threshold Analysis</p>
                    <div className="space-y-3 text-sm">
                      {[
                        { label: 'True Positive Rate (Recall)', value: '76%', color: 'text-primary' },
                        { label: 'False Positive Rate', value: '41%', color: 'text-red-400' },
                        { label: 'Detection Threshold', value: '0.50', color: 'text-white' },
                        { label: 'AUC Score', value: '0.770', color: 'text-primary', highlight: true },
                      ].map(row => (
                        <div key={row.label} className={`flex justify-between items-center p-3 rounded-xl border ${row.highlight ? 'bg-primary/10 border-primary/20' : 'bg-white/5 border-white/10'}`}>
                          <span className="text-muted-foreground">{row.label}</span>
                          <span className={`font-mono font-bold ${row.color}`}>{row.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              {/* ── STEP 4: BEST METHOD HIGHLIGHT ──────────────── */}
              <section className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full bg-white/10 text-white text-xs font-bold uppercase tracking-widest">Step 4</span>
                  <h2 className="text-xl font-bold">Best Method Highlight</h2>
                </div>
                <div className="rounded-2xl border border-primary/30 bg-primary/5 backdrop-blur-2xl shadow-[0_12px_40px_rgba(0,242,255,0.18),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                  <div className="grid grid-cols-1 md:grid-cols-2">
                    <img src="/dashboard/bestmethodmineralmap.jpg" alt="Best Method Mineral Map" className="w-full h-full object-cover min-h-64" />
                    <div className="p-8 flex flex-col justify-between">
                      <div className="space-y-4">
                        <span className="inline-block px-3 py-1.5 rounded-full bg-white/10 text-white text-xs font-black uppercase tracking-widest shadow-[0_0_16px_rgba(255,255,255,0.4)]">★ Best Model</span>
                        <h3 className="text-3xl font-black tracking-tight text-white">Method C</h3>
                        <p className="text-muted-foreground text-sm">PCA → QAE → Ensemble Classifier. Combines 25 PCA + 6 quantum + 2 USGS features. Best of the seven methods tested on this dataset.</p>
                        <div className="grid grid-cols-3 gap-3 pt-2">
                          {[['AUC', '0.770'], ['F1', '0.675'], ['MCC', '0.35']].map(([label, value]) => (
                            <div key={label} className="bg-white/5 border border-white/10 rounded-xl p-3 text-center">
                              <div className="text-2xl font-black text-primary">{value}</div>
                              <div className="text-xs text-muted-foreground mt-1">{label}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground mt-6 pt-4 border-t border-white/10">+0.009 AUC over the classical autoencoder B (0.770 vs 0.762). Note: the gap is not statistically significant (McNemar p = 0.106) — the quantum stage adds feature diversity, not a proven accuracy gain on this dataset. Simulator only.</p>
                    </div>
                  </div>
                </div>
              </section>

              {/* ── STEP 5: PERFORMANCE EVALUATION ─────────────── */}
              <section className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full bg-white/10 text-white text-xs font-bold uppercase tracking-widest">Step 5</span>
                  <h2 className="text-xl font-bold">Performance Evaluation</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <div className="px-5 pt-4 pb-2">
                      <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">Scoreboard — AUC · F1 · MCC</p>
                    </div>
                    <img src="/dashboard/scoreboard.jpeg" alt="Scoreboard" className="w-full object-cover" />
                  </div>
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <div className="px-5 pt-4 pb-2">
                      <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">ROC Curves — All Methods</p>
                    </div>
                    <img src="/dashboard/Performance curves.jpg" alt="Performance Curves" className="w-full object-cover" />
                  </div>
                </div>
              </section>

              {/* ── STEP 6: ERROR ANALYSIS ──────────────────────── */}
              <section className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full bg-white/10 text-white text-xs font-bold uppercase tracking-widest">Step 6</span>
                  <h2 className="text-xl font-bold">Error Analysis</h2>
                </div>
                <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                  <div className="px-5 pt-4 pb-2">
                    <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">Confusion Matrix — All Methods</p>
                  </div>
                  <img src="/dashboard/Error breakdown.jpg" alt="Error Breakdown" className="w-full object-cover" />
                  <div className="px-6 py-4 grid grid-cols-3 gap-4 border-t border-white/10">
                    <div className="text-center">
                      <p className="text-xs font-semibold text-primary uppercase tracking-widest">True Positive</p>
                      <p className="text-xs text-muted-foreground mt-1">Correctly detected mineral patches</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs font-semibold text-red-400 uppercase tracking-widest">False Positive</p>
                      <p className="text-xs text-muted-foreground mt-1">Background flagged as mineral</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs font-semibold text-orange-400 uppercase tracking-widest">False Negative</p>
                      <p className="text-xs text-muted-foreground mt-1">Missed mineral patches</p>
                    </div>
                  </div>
                </div>
              </section>

              {/* ── STEP 7: METHOD COMPARISON ───────────────────── */}
              <section className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full bg-white/10 text-white text-xs font-bold uppercase tracking-widest">Step 7</span>
                  <h2 className="text-xl font-bold">Method Comparison</h2>
                  <span className="text-muted-foreground text-sm">All 7 Methods Side-by-Side</span>
                </div>
                <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                  <img src="/dashboard/All 7 methods compared.jpeg" alt="All 7 Methods Compared" className="w-full object-cover" />
                  <div className="px-6 py-4 grid grid-cols-2 sm:grid-cols-4 gap-4 border-t border-white/10">
                    {[
                      { method: 'Method A', arch: 'PCA → Ensemble', auc: '0.749', best: false, worst: false },
                      { method: 'Method B', arch: 'PCA → CAE → Ensemble', auc: '0.762', best: false, worst: false },
                      { method: 'Method C ★', arch: 'PCA → QAE → Ensemble', auc: '0.770', best: true, worst: false },
                      { method: 'Method F', arch: 'QAA Background-only', auc: '0.687', best: false, worst: true },
                    ].map(m => (
                      <div key={m.method} className={`p-3 rounded-xl border text-center ${
                        m.best ? 'bg-primary/10 border-primary/30' : m.worst ? 'bg-red-500/5 border-red-500/20' : 'bg-white/5 border-white/10'
                      }`}>
                        <p className={`text-xs font-bold ${ m.best ? 'text-primary' : m.worst ? 'text-red-400' : 'text-white'}`}>{m.method}</p>
                        <p className="text-xs text-muted-foreground mt-0.5 truncate">{m.arch}</p>
                        <p className={`text-xl font-black mt-1 ${m.best ? 'text-primary' : m.worst ? 'text-red-400' : 'text-white'}`}>{m.auc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              {/* ── SCOPE & LIMITATIONS (honesty callout) ─────────── */}
              <section className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full bg-amber-400/20 text-white text-xs font-bold uppercase tracking-widest">Scope</span>
                  <h2 className="text-xl font-bold">Scope &amp; Limitations</h2>
                </div>
                <div className="rounded-2xl border border-amber-400/25 bg-amber-400/5 backdrop-blur-2xl shadow-[0_12px_34px_rgba(251,191,36,0.08),inset_0_1px_0_rgba(255,255,255,0.12)] p-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    {[
                      ['Metrics vs pseudo-labels', 'AUC/F1 are measured against band-ratio spectral indices, not field-verified deposits. They show agreement with a heuristic, not confirmed mineralisation.'],
                      ['Quantum advantage is modest', 'Method C leads the classical autoencoder B by +0.009 AUC (0.770 vs 0.762), but the difference is not statistically significant (McNemar p = 0.106). Quantum models run on a simulator, not real hardware. Quantum adds feature diversity, not a proven accuracy gain.'],
                      ['Surface alteration only', 'Optical/hyperspectral sensing detects clay-hosted & pegmatite Li alteration at the surface. It cannot see brine lithium (under playas) or buried deposits — that requires geophysics.'],
                      ['Vanadium is low-confidence', 'Many V ores (e.g. black-shale hosted) have no usable surface spectral signature. V outputs are weak proxies.'],
                    ].map(([t, d]) => (
                      <div key={t} className="p-4 rounded-xl bg-white/5 border border-white/10">
                        <p className="font-semibold text-amber-300/90">{t}</p>
                        <p className="text-muted-foreground text-xs mt-1 leading-relaxed">{d}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

            </div>
          )}

          {/* Live Analysis Tab Content */}
          {activeTab === 'live' && (
            <TerraQLiveAnalysis />
          )}

          {/* How It Works Tab Content */}
          {activeTab === 'how' && (
            <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <div className="flex flex-col gap-2">
                <h1 className="text-4xl font-bold tracking-tight">The Big Picture</h1>
                <p className="text-muted-foreground text-lg">A step-by-step visual guide — from satellite image to mineral map.</p>
              </div>
              <BentoGrid enableSpotlight={false}>
                <BentoGridItem
                  title="01 — Satellite Image"
                  description={
                    <div className="space-y-4 pt-2">
                      <p>NASA EO-1 Hyperion captures hyperspectral images.</p>
                      <div className="flex gap-2">
                        <span className="px-2 py-1 bg-primary/10 border border-primary/20 rounded-md text-xs font-mono text-primary">800×800 px</span>
                        <span className="px-2 py-1 bg-primary/10 border border-primary/20 rounded-md text-xs font-mono text-primary">198 bands</span>
                      </div>
                      <p className="text-sm text-muted-foreground">Unlike RGB, it sees SWIR range (2000–2500 nm) where minerals absorb light.</p>
                    </div>
                  }
                  className="md:col-span-2 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<Satellite className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title="02 — Patch Extraction"
                  description={
                    <div className="space-y-2 pt-2">
                      <p>Image is sliced into 845 non-overlapping tiles.</p>
                      <p className="text-xs text-muted-foreground font-mono bg-white/5 p-2 rounded border border-white/10 w-fit">Shape: 16×16 px</p>
                      <p className="text-sm">Clouds, shadows, and flat water are filtered out.</p>
                    </div>
                  }
                  className="md:col-span-1 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<Grid3X3 className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title="03 — Compress 198 Bands"
                  description={
                    <div className="space-y-4 pt-2">
                      <p>Reducing 50,688 dimensions into 25 key features using PCA, removing noise.</p>
                      <div className="h-2 w-full bg-gradient-to-r from-primary to-primary/20 rounded-full overflow-hidden shadow-[0_0_10px_rgba(0,242,255,0.5)]" />
                    </div>
                  }
                  className="md:col-span-1 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<ArrowDownToLine className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                   title="04 — Quantum Circuit"
                   description={
                     <div className="space-y-2 pt-2">
                       <p>Extracts 6 quantum features in a 64-D Hilbert space, adding feature diversity to the ensemble.</p>
                       <div className="bg-primary/10 p-3 rounded-lg border border-primary/30 flex items-center gap-3">
                         <Zap className="w-5 h-5 text-primary animate-pulse" />
                         <span className="text-sm font-semibold text-primary">6-qubit QAE Circuit</span>
                       </div>
                     </div>
                   }
                   className="md:col-span-1 md:row-span-1 hover:border-primary/50 transition-colors"
                   icon={<BrainCircuit className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title="05 — AI Classifiers Vote"
                  description={
                    <div className="space-y-3 pt-2">
                      <p>3 AI classifiers vote: "Mineral or Not?"</p>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span className="px-2 py-1 bg-white/10 rounded-full border border-white/20">SVM</span>
                        <span className="px-2 py-1 bg-white/10 rounded-full border border-white/20">Random Forest</span>
                        <span className="px-2 py-1 bg-white/10 rounded-full border border-white/20">Gradient Boost</span>
                      </div>
                    </div>
                  }
                  className="md:col-span-1 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<Cpu className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title="06 — Mineral Map"
                  description={
                    <div className="h-full flex flex-col justify-center space-y-4 pt-2">
                      <p className="text-lg">Generates a spatial mineral probability map of the region, highlighting anomalies with precision.</p>
                    </div>
                  }
                  className="md:col-span-3 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<MapIcon className="w-8 h-8 text-primary" />}
                />
              </BentoGrid>

              {/* How It Works Images */}
              <div className="space-y-4">
                <div className="flex flex-col gap-1">
                  <h2 className="text-2xl font-bold tracking-tight">Visual Reference</h2>
                  <p className="text-muted-foreground text-sm">Pipeline diagrams illustrating the full end-to-end flow.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <div className="px-5 pt-4 pb-2">
                      <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">How It Works — Pipeline Overview</p>
                    </div>
                    <img src="/how it works/how it works.jpeg" alt="How It Works — Pipeline Overview" className="w-full object-cover" />
                  </div>
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <div className="px-5 pt-4 pb-2">
                      <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">How It Works — Detailed Breakdown</p>
                    </div>
                    <img src="/how it works/how it works 1.jpeg" alt="How It Works — Detailed Breakdown" className="w-full object-cover" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Data & Methodology Tab Content */}
          {activeTab === 'data' && (
            <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <div className="flex flex-col gap-2">
                <h1 className="text-4xl font-bold tracking-tight">Data & Methodology</h1>
                <p className="text-muted-foreground text-lg">The core technical breakdown: from Ground-Truth to Quantum Autoencoders.</p>
              </div>

              {/* Measured validation of the live Sentinel-2 index against USGS
                  MRDS. Rendered from explorer/data/validation.json, the same
                  source of truth as outputs/validation_final.json. */}
              <ValidationCard />

              <div className="h-px bg-white/10" />
              <BentoGrid enableSpotlight={false}>
                <BentoGridItem
                  title="Spectral-Index Pseudo-Labels"
                  description={
                    <div className="space-y-4 pt-2">
                      <div className="space-y-3 text-sm">
                         <div className="p-3 bg-white/5 border border-white/10 rounded-xl relative overflow-hidden group">
                            <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                            <span className="font-bold text-primary">LiCI (Lithium)</span>: Absorption dip at 2200 nm.
                         </div>
                         <div className="p-3 bg-white/5 border border-white/10 rounded-xl relative overflow-hidden group">
                            <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                            <span className="font-bold text-primary">VMI (Vanadium)</span>: Absorption dip at 2265 nm.
                         </div>
                      </div>
                      <p className="text-xs text-amber-300/80">Labels are derived from band-ratio spectral indices, not field surveys. They are <span className="font-semibold">pseudo-labels</span>, so reported accuracy measures agreement with these indices — not verified mineral presence. 48% of tiles labelled mineral.</p>
                    </div>
                  }
                  className="md:col-span-2 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<Microscope className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title="PCA Compression"
                  description={
                    <div className="space-y-3 pt-2">
                      <p className="text-sm">Squeezing high dimensions:</p>
                      <div className="font-mono text-xs text-primary bg-primary/10 p-2 rounded border border-primary/20 text-center">
                        845 × 50,688 → 845 × 25
                      </div>
                      <p className="text-xs text-muted-foreground">Keeps ~90% of spectral info.</p>
                    </div>
                  }
                  className="md:col-span-1 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<Layers className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title={
                    <div className="flex items-center gap-2">
                      Quantum Autoencoder
                      <span className="px-2 py-0.5 rounded-full bg-primary/20 text-[10px] font-bold text-primary animate-pulse border border-primary/30 uppercase tracking-widest">Main</span>
                    </div>
                  }
                  description={
                    <div className="space-y-4 pt-2">
                      <p className="text-sm">Instead of a classical NN, a 6-qubit quantum circuit compresses the data.</p>
                      <div className="bg-white/5 p-4 rounded-lg border border-white/10 text-xs font-mono text-muted-foreground space-y-2">
                        <p className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" /> RY rotation gates</p>
                        <p className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" /> CNOT entanglement</p>
                        <p className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" /> CZ long-range link</p>
                      </div>
                      <p className="text-sm font-bold text-primary">Operates in 64-D Hilbert space.</p>
                    </div>
                  }
                  className="md:col-span-2 md:row-span-2 hover:border-primary/50 transition-colors"
                  icon={<Zap className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title="Unsupervised QAA"
                  description={
                    <div className="space-y-3 pt-2">
                      <p className="text-sm">Finds mineral hotspots with ZERO labels.</p>
                      <p className="text-xs bg-red-500/10 text-red-400 p-3 rounded border border-red-500/20 font-semibold text-center">
                        Anomaly = Can't Compress
                      </p>
                    </div>
                  }
                  className="md:col-span-1 md:row-span-1 hover:border-red-500/50 transition-colors"
                  icon={<ShieldAlert className="w-8 h-8 text-red-400" />}
                />
                <BentoGridItem
                  title="USGS Spectral Library"
                  description={
                     <div className="space-y-2 pt-2 text-sm text-muted-foreground">
                        <p>Lab-measured pure mineral signatures used to create extra features for the ensemble.</p>
                        <p className="text-primary font-semibold mt-4">Lithium & Vanadium Targets</p>
                     </div>
                  }
                  className="md:col-span-1 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<Scan className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title="Real Validation — USGS MRDS"
                  description={
                    <div className="space-y-3 pt-2 text-sm">
                      <p className="text-muted-foreground">Independent ground truth from the USGS Mineral Resources Data System — actual known deposit locations, used to sanity-check the maps.</p>
                      <div className="p-3 bg-emerald-500/10 border border-emerald-500/25 rounded-xl text-emerald-300 text-xs font-semibold">
                        ✓ The producing Silver Peak lithium mine is detected at the 98th percentile of the alteration map.
                      </div>
                      <p className="text-xs text-muted-foreground">Brine-hosted points correctly score low (no surface signature). Small sample — a credibility check, not a calibrated accuracy.</p>
                    </div>
                  }
                  className="md:col-span-2 md:row-span-1 hover:border-emerald-500/50 transition-colors"
                  icon={<CheckCircle2 className="w-8 h-8 text-emerald-400" />}
                />
              </BentoGrid>

              {/* Data Methodology Images */}
              <div className="space-y-4">
                <div className="flex flex-col gap-1">
                  <h2 className="text-2xl font-bold tracking-tight">Visual Reference</h2>
                  <p className="text-muted-foreground text-sm">Supplementary methodology diagrams and data visualisations.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <div className="px-5 pt-4 pb-2">
                      <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">Data Methodology — Fig. 1</p>
                    </div>
                    <img src="/data methodology/data methodology 1.jpg" alt="Data Methodology 1" className="w-full object-cover" />
                  </div>
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <div className="px-5 pt-4 pb-2">
                      <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">Data Methodology — Fig. 2</p>
                    </div>
                    <img src="/data methodology/data methodology 2.jpg" alt="Data Methodology 2" className="w-full object-cover" />
                  </div>
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <div className="px-5 pt-4 pb-2">
                      <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">Data Methodology — Fig. 3</p>
                    </div>
                    <img src="/data methodology/data methodology 3.jpeg" alt="Data Methodology 3" className="w-full object-cover" />
                  </div>
                  <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                    <div className="px-5 pt-4 pb-2">
                      <p className="text-xs font-semibold text-white/70 uppercase tracking-widest">Data Methodology — Fig. 4</p>
                    </div>
                    <img src="/data methodology/data methodology 4.jpeg" alt="Data Methodology 4" className="w-full object-cover" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Satellite Maps Tab Content */}
          {activeTab === 'maps' && (
            <div className="max-w-7xl mx-auto space-y-8">
              <div className="flex flex-col gap-2">
                <h1 className="text-4xl font-bold tracking-tight">Deployment Outputs — Sentinel-2</h1>
                <p className="text-muted-foreground text-lg">Real mineral-alteration maps produced by the live engine over Clayton Valley, Nevada (Silver Peak lithium district). For a custom area, use the <span className="text-white font-semibold">Live Analysis</span> tab.</p>
              </div>

              {/* Hero — validated against the producing Silver Peak mine */}
              <div className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-primary/30 bg-primary/5 shadow-[0_12px_40px_rgba(0,242,255,0.16),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden">
                <div className="px-5 pt-4 pb-2 flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full bg-white/10 text-white text-xs font-black uppercase tracking-widest">Validated</span>
                  <p className="text-sm font-semibold">Clay / Al-OH alteration vs the producing Silver Peak lithium mine — detected at the 98th percentile</p>
                </div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/maps/silver_peak_validation.png" alt="Silver Peak clay-alteration validation" loading="lazy" className="w-full object-cover" />
              </div>

              {/* Real engine output layers */}
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {[
                  ['Lithium Prospectivity', '/maps/lithium.png', 'Clay / Al-OH alteration (2200 nm). Rock-hosted & pegmatite Li indicator — not brine Li.'],
                  ['Vanadium Prospectivity', '/maps/vanadium.png', 'Iron-oxide + mica composite. Low-confidence proxy; black-shale V is not detectable.'],
                  ['Brine Favorability', '/maps/brine.png', 'Indirect playa / evaporite basin flag — a follow-up-with-geophysics hint, not a detection.'],
                  ['Sentinel-2 RGB', '/maps/rgb.png', 'True-colour basemap of the analysed area.'],
                  ['Confidence', '/maps/confidence.png', 'Data quality: rock = high; vegetation / water / nodata = low.'],
                ].map(([title, src, desc]) => (
                  <div key={src} className="magic-bento-card magic-bento-card--border-glow relative rounded-2xl border border-white/12 bg-white/4 shadow-[0_12px_34px_rgba(0,242,255,0.1),inset_0_1px_0_rgba(255,255,255,0.16)] overflow-hidden p-3">
                    <p className="text-sm font-semibold px-1">{title}</p>
                    <p className="text-[11px] text-muted-foreground mb-2 px-1">{desc}</p>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={src} alt={title} loading="lazy" className="w-full rounded-xl border border-white/10" />
                  </div>
                ))}
              </div>

              <div className="rounded-2xl border border-amber-400/25 bg-amber-400/5 p-5 text-xs text-amber-300/90 leading-relaxed">
                <b>How to read these:</b> values are normalised alteration scores in [0,1], not calibrated probabilities. Optical sensing detects surface clay / pegmatite alteration only — it cannot see brine lithium (under playas) or buried deposits. Vanadium is a low-confidence proxy.
              </div>
            </div>
          )}

          {/* Method Comparison Tab Content */}
          {activeTab === 'methods' && (
            <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <div className="flex flex-col gap-2">
                <h1 className="text-4xl font-bold tracking-tight">Method Comparison</h1>
                <p className="text-muted-foreground text-lg">A guided evaluation pipeline — 7 architectures benchmarked from initial output to final model selection.</p>
              </div>
              <BentoGrid enableSpotlight={false}>
                <BentoGridItem
                  title="Step 1: Model Performance Snapshot"
                  description={
                    <div className="overflow-x-auto mt-4">
                      <p className="text-xs text-muted-foreground mb-3">Initial evaluation of all methods across AUC, F1, and MCC. Establishes the baseline for downstream selection.</p>
                      <table className="w-full text-xs text-left border-collapse">
                        <thead>
                          <tr className="border-b border-border text-muted-foreground">
                            <th className="pb-3 font-semibold">Method</th>
                            <th className="pb-3 font-semibold">Architecture</th>
                            <th className="pb-3 font-semibold text-right" title="Overall ranking ability">AUC ↗</th>
                          </tr>
                        </thead>
                        <tbody className="text-foreground">
                          <tr className="border-b border-border/50 hover:bg-white/5 transition-colors">
                            <td className="py-3">Method A</td>
                            <td className="py-3 text-muted-foreground">PCA → Ensemble</td>
                            <td className="py-3 font-mono text-right">0.749</td>
                          </tr>
                          <tr className="border-b border-border/50 hover:bg-white/5 transition-colors">
                            <td className="py-3">Method B</td>
                            <td className="py-3 text-muted-foreground">PCA → CAE → Ensemble</td>
                            <td className="py-3 font-mono text-right">0.762</td>
                          </tr>
                          <tr className="border-b border-primary/20 bg-primary/5 hover:bg-primary/10 transition-colors">
                            <td className="py-3 text-primary font-bold">Method C ★ (Selected Model)</td>
                            <td className="py-3 text-primary">PCA → QAE → Ensemble</td>
                            <td className="py-3 font-mono text-primary font-bold text-right">0.770</td>
                          </tr>
                          <tr className="border-b border-border/50 hover:bg-white/5 transition-colors">
                            <td className="py-3 text-red-400 font-bold">Method F</td>
                            <td className="py-3 text-red-400">QAA Background-only</td>
                            <td className="py-3 font-mono text-red-400 text-right">0.687</td>
                          </tr>
                          <tr className="border-b border-border/50 hover:bg-white/5 transition-colors text-muted-foreground">
                            <td className="py-3">Method D</td>
                            <td className="py-3">QSVM (quantum kernel)</td>
                            <td className="py-3 font-mono text-right">0.513</td>
                          </tr>
                          <tr className="border-b border-border/50 hover:bg-white/5 transition-colors text-muted-foreground">
                            <td className="py-3">Method C2</td>
                            <td className="py-3">QAE → QSVM (fully quantum)</td>
                            <td className="py-3 font-mono text-right">0.471</td>
                          </tr>
                          <tr className="hover:bg-white/5 transition-colors text-muted-foreground">
                            <td className="py-3">Method C3</td>
                            <td className="py-3">QAE → VQC (fully quantum)</td>
                            <td className="py-3 font-mono text-right">0.526</td>
                          </tr>
                        </tbody>
                      </table>
                      <p className="text-[11px] text-muted-foreground mt-3 leading-relaxed">
                        All 7 methods shown. The fully-quantum classifiers (D / C2 / C3) sit at or below random (~0.50) — quantum kernels suffer exponential concentration on this data. Method C beats the classical baselines only marginally and <span className="text-amber-300/90">not significantly</span> (McNemar vs PCA p≈0.33).
                      </p>
                    </div>
                  }
                  className="md:col-span-2 md:row-span-2 hover:border-primary/50 transition-colors"
                  icon={<BarChart className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title="Step 4: Best Model Selection"
                  description={
                    <div className="space-y-4 pt-2">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 rounded bg-primary/20 text-primary text-xs font-bold border border-primary/30">+0.009 AUC</span>
                        <span className="text-sm text-muted-foreground">vs classical autoencoder (not significant, p≈0.33).</span>
                      </div>
                      <p className="text-sm">Chosen as the top performer of the seven methods tested. The QAE adds feature diversity to the ensemble; on this dataset it performs on par with the classical autoencoder rather than beating it decisively. Final model used in the downstream prediction pipeline.</p>
                      <div className="p-3 bg-white/10 border border-white/20 text-white text-xs font-mono rounded-lg shadow-inner text-center font-bold">
                        Features: 25 PCA + 6 QAE + 2 USGS
                      </div>
                    </div>
                  }
                  className="md:col-span-1 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<Zap className="w-8 h-8 text-primary" />}
                />
                <BentoGridItem
                  title="Step 6: Unsupervised Detection Path"
                  description={
                    <div className="space-y-3 pt-2">
                      <div className="flex items-end gap-2">
                         <div className="text-4xl font-black text-red-400 tracking-tighter">95.4%</div>
                         <div className="pb-1 text-sm font-semibold text-red-400/80">Specificity</div>
                      </div>
                      <p className="text-sm text-muted-foreground">Alternative pipeline without labeled data — 0 training labels used. Optimized for anomaly detection, not classification accuracy. Anomalies surface as reconstruction failures.</p>
                    </div>
                  }
                  className="md:col-span-1 md:row-span-1 hover:border-red-500/50 transition-colors"
                  icon={<ShieldAlert className="w-8 h-8 text-red-400" />}
                />
                <BentoGridItem
                  title="Step 7: Model Limitations"
                  description={
                    <div className="space-y-2 pt-2">
                       <p className="text-sm text-foreground">Performance constraints of fully quantum approaches. Methods C2 (QSVM) and C3 (VQC) underperformed the hybrid ensemble.</p>
                       <p className="text-sm text-muted-foreground leading-relaxed">At 200 training samples, the classical ensemble holds a capacity advantage. Fully quantum classifiers require larger labeled datasets. Indicates need for hybrid architectures in low-data regimes.</p>
                    </div>
                  }
                  className="md:col-span-3 md:row-span-1 hover:border-primary/50 transition-colors"
                  icon={<Activity className="w-8 h-8 text-primary" />}
                />
              </BentoGrid>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

'use client'

import { Progress } from '@/components/ui/progress'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Info } from 'lucide-react'
import React from 'react'

// ---------------------------------------------------------------------------
// Source of truth for every number in this file:
//   outputs/summary/metrics.txt — hold-out Scene 3, method C_PCA_QAE unless noted.
//     C_PCA_QAE : AUC 0.7702  F1 0.6751  CM TN=270 FP=191 FN=91 TP=293
//     F_QAA_Hybrid : CM TN=440 FP=21 FN=266 TP=118
//   Derived: recall = TP/(TP+FN) = 293/384 = 76.3%
//            specificity (F) = TN/(TN+FP) = 440/461 = 95.4%
// Do not edit these by hand — re-read metrics.txt if the pipeline is ever re-run.
// ---------------------------------------------------------------------------
const C_AUC = 0.7702
const C_F1 = 0.6751

export function DetectionRankingCard() {
  return (
    <div className="rounded-2xl p-6 border border-white/15 bg-white/6 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.12),inset_0_1px_0_rgba(255,255,255,0.2)] col-span-1">
      <div className="flex justify-between items-start mb-6">
        <h3 className="text-gray-200 font-semibold">Detection Ranking Score</h3>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="w-4 h-4 text-gray-500 hover:text-gray-300 cursor-help" />
            </TooltipTrigger>
            <TooltipContent className="bg-[#27272A] border-[#3F3F46] text-gray-200 text-xs">
              AUC 0.770 — a 77.0% chance the model ranks a mineral patch above a
              background patch. Hold-out Scene 3; quantum models run on a simulator.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      
      <div className="flex flex-col items-center justify-center py-8">
        <div className="relative w-32 h-32 flex items-center justify-center">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
            {/* Background circle */}
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              stroke="#1a1a1a"
              strokeWidth="8"
            />
            {/* Progress circle */}
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              stroke="#d1d5db"
              strokeWidth="8"
              strokeDasharray={`${2 * Math.PI * 54 * C_AUC} ${2 * Math.PI * 54}`}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute text-center">
            <div className="text-3xl font-bold text-gray-200">{C_AUC.toFixed(3)}</div>
            <div className="text-xs text-gray-500">AUC</div>
          </div>
        </div>
      </div>

      <div className="text-center text-xs text-gray-500 mt-4">
        Method C · PCA+QAE • hold-out Scene 3
      </div>
    </div>
  )
}

export function DetectionQualityCard() {
  return (
    <div className="rounded-2xl p-6 border border-white/15 bg-white/6 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.12),inset_0_1px_0_rgba(255,255,255,0.2)] col-span-1">
      <div className="flex justify-between items-start mb-6">
        <h3 className="text-gray-200 font-semibold">Detection Quality</h3>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="w-4 h-4 text-gray-500 hover:text-gray-300 cursor-help" />
            </TooltipTrigger>
            <TooltipContent className="bg-[#27272A] border-[#3F3F46] text-gray-200 text-xs">
              Balances finding minerals (recall) with avoiding false alarms (precision)
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      <div className="space-y-4">
        <div className="flex items-baseline gap-3">
          <div className="text-3xl font-bold text-gray-200">{C_F1.toFixed(3)}</div>
          <div className="text-xs text-gray-500">F1 Score</div>
        </div>

        {/*
          Real F1 per method from metrics.txt, ordered as in the comparison chart.
          This replaces a previous decorative sparkline whose values were invented
          and read as a trend over time — there is no time axis in these results.
        */}
        <div className="h-12 bg-[#27272A] rounded border border-[#3F3F46] flex items-end justify-around px-3 py-2">
          {[
            { m: 'A', f1: 0.6482 }, { m: 'B', f1: 0.6621 }, { m: 'C', f1: 0.6751 },
            { m: 'F', f1: 0.4512 }, { m: 'D', f1: 0.5442 }, { m: 'C3', f1: 0.5927 },
            { m: 'C2', f1: 0.5483 },
          ].map(({ m, f1 }) => (
            <div
              key={m}
              title={`Method ${m} — F1 ${f1.toFixed(3)}`}
              className={`w-1 rounded-sm ${m === 'C' ? 'bg-[#00F2FF]' : 'bg-gray-500'}`}
              style={{ height: `${f1 * 40}px` }}
            />
          ))}
        </div>
        <p className="text-[10px] text-gray-600">
          F1 by method (A·B·C·F·D·C3·C2) — cyan is C, the best. Not a time series.
        </p>
      </div>

      <div className="text-xs text-gray-500 mt-4">
        Composite metric: (2 × Precision × Recall) / (Precision + Recall)
      </div>
    </div>
  )
}

export function MineralRecallCard() {
  // recall = TP / (TP + FN) = 293 / 384 (metrics.txt, C_PCA_QAE confusion matrix)
  const value = 76.3
  return (
    <div className="rounded-2xl p-6 border border-white/15 bg-white/6 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.12),inset_0_1px_0_rgba(255,255,255,0.2)] col-span-1">
      <div className="flex justify-between items-start mb-6">
        <h3 className="text-gray-200 font-semibold">Mineral Recall</h3>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="w-4 h-4 text-gray-500 hover:text-gray-300 cursor-help" />
            </TooltipTrigger>
            <TooltipContent className="bg-[#27272A] border-[#3F3F46] text-gray-200 text-xs">
              Correctly flagged 293 of 384 positive patches in the hold-out test scene.
              Patches are 16×16 pixel tiles, not individual deposits.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      <div className="space-y-4">
        <div className="text-3xl font-bold text-gray-200">{value}%</div>
        <Progress value={value} className="h-2" />
      </div>

      <div className="text-xs text-gray-500 mt-4">
        293 of 384 positive patches recovered
      </div>
    </div>
  )
}

export function MethodFSpecificityCard() {
  // specificity = TN / (TN + FP) = 440 / 461 (metrics.txt, F_QAA_Hybrid)
  const value = 95.4
  return (
    <div className="rounded-2xl p-6 border border-white/15 bg-white/6 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.12),inset_0_1px_0_rgba(255,255,255,0.2)] col-span-1">
      <div className="flex justify-between items-start mb-6">
        <h3 className="text-gray-200 font-semibold">Method F Specificity</h3>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="w-4 h-4 text-gray-500 hover:text-gray-300 cursor-help" />
            </TooltipTrigger>
            <TooltipContent className="bg-[#27272A] border-[#3F3F46] text-gray-200 text-xs">
              Only 21 false positives out of 461 background patches.
              Method F is the unsupervised quantum anomaly detector.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      <div className="space-y-4">
        <div className="text-3xl font-bold text-gray-200">{value}%</div>
        <Progress value={value} className="h-2" />
      </div>

      <div className="text-xs text-gray-500 mt-4">
        21 false positives out of 461 background patches
      </div>
    </div>
  )
}

export function LiveMLOutputCard() {
  return (
    <div className="rounded-2xl p-8 border border-dashed border-white/20 bg-white/6 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.12),inset_0_1px_0_rgba(255,255,255,0.2)] col-span-1 md:col-span-2 lg:col-span-3 min-h-80 flex flex-col items-center justify-center">
      <div className="text-gray-500 space-y-4 text-center">
        <svg
          className="w-16 h-16 mx-auto opacity-50"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
        <p className="text-sm font-medium">Live ML Model Output</p>
        <p className="text-xs">Awaiting Live Quantum Model Generation...</p>
      </div>
    </div>
  )
}

export function SatelliteMapCard() {
  const [activeMethod, setActiveMethod] = React.useState<'classical' | 'hybrid' | 'quantum'>('quantum')

  return (
    <div className="rounded-2xl p-6 border border-white/15 bg-white/6 backdrop-blur-2xl shadow-[0_12px_34px_rgba(0,242,255,0.12),inset_0_1px_0_rgba(255,255,255,0.2)] col-span-1 md:col-span-2">
      <h3 className="text-gray-200 font-semibold mb-4">Satellite Detection Maps</h3>
      
      <div className="space-y-4">
        {/* Method Toggle Buttons */}
        <div className="flex gap-3">
          {[
            { id: 'classical' as const, label: 'Classical' },
            { id: 'hybrid' as const, label: 'Hybrid' },
            { id: 'quantum' as const, label: 'Quantum ★' },
          ].map((method) => (
            <button
              key={method.id}
              onClick={() => setActiveMethod(method.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
                activeMethod === method.id
                  ? 'bg-gray-800 text-white border-gray-800'
                  : 'bg-transparent text-gray-400 border-[#3F3F46] hover:text-gray-200 hover:border-gray-600'
              }`}
            >
              {method.label}
            </button>
          ))}
        </div>

        {/* Map Placeholder */}
        <div className="bg-[#27272A] border border-[#3F3F46] rounded-lg h-48 flex items-center justify-center">
          <div className="text-center text-gray-500 space-y-2">
            <div className="text-sm">
              {activeMethod === 'quantum' ? '🔬' : activeMethod === 'hybrid' ? '⚡' : '📡'} {activeMethod.toUpperCase()} Method Active
            </div>
            <div className="text-xs text-gray-600">
              Satellite imagery overlay — Comparative Analysis across 7 Methodologies
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

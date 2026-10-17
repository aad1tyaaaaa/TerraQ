'use client'

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

// Source of truth: outputs/summary/metrics.txt (hold-out Scene 3).
// These are the seven real pipeline methods. Earlier versions of this file
// carried invented labels ("Classical+AI", "Fully Quantum") and numbers that
// map to no method in the pipeline — replaced with the measured values.
const data = [
  { name: 'A · PCA', AUC: 0.7492, F1: 0.6482 },
  { name: 'B · PCA+CAE', AUC: 0.7617, F1: 0.6621 },
  { name: 'C · PCA+QAE', AUC: 0.7702, F1: 0.6751 },
  { name: 'F · QAA Hybrid', AUC: 0.6869, F1: 0.4512 },
  { name: 'D · QSVM', AUC: 0.5128, F1: 0.5442 },
  { name: 'C3 · QAE→VQC', AUC: 0.5256, F1: 0.5927 },
  { name: 'C2 · QAE→QSVM', AUC: 0.4710, F1: 0.5483 },
]

interface ChartTooltipProps {
  active?: boolean
  payload?: Array<{
    name: string
    value: number
    color: string
  }>
  label?: string
}

const CustomTooltip = ({ active, payload, label }: ChartTooltipProps) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#27272A]/95 border border-[#3F3F46] rounded p-3 shadow-lg">
        <p className="text-gray-200 text-sm font-medium">{label}</p>
        {payload.map((entry, index) => (
          <p
            key={index}
            className="text-xs"
            style={{ color: entry.color }}
          >
            {entry.name}: {entry.value.toFixed(3)}
          </p>
        ))}
      </div>
    )
  }
  return null
}

export function MethodComparisonChart() {
  return (
    <div className="bg-[#27272A] rounded-2xl p-6 border border-[#3F3F46] col-span-1 md:col-span-2 lg:col-span-3">
      <h3 className="text-gray-200 font-semibold mb-1">Method Comparison</h3>
      <p className="text-xs text-gray-500 mb-6">
        Hold-out Scene 3 (Hyperion). Best: C · PCA+QAE, AUC 0.770 — +0.009 AUC over the
        classical autoencoder B (0.770 vs 0.762), McNemar p = 0.106, not significant.
        Quantum models run on a simulator.
      </p>

      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#3F3F46" />
          <XAxis
            dataKey="name"
            tick={{ fill: '#9ca3af', fontSize: 10 }}
            interval={0}
            axisLine={{ stroke: '#3F3F46' }}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: '#9ca3af', fontSize: 12 }}
            axisLine={{ stroke: '#3F3F46' }}
          />
          <Tooltip cursor={false} content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="square"
            itemStyle={{ color: '#d1d5db', fontSize: '12px' }}
          />
          <Bar dataKey="AUC" fill="#d1d5db" radius={[8, 8, 0, 0]} />
          <Bar dataKey="F1" fill="#9ca3af" radius={[8, 8, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-7 gap-3">
        {data.map((method) => (
          <div key={method.name} className="bg-[#27272A] rounded-lg p-3 text-center border border-[#3F3F46]">
            <p className="text-xs text-gray-500 mb-2">{method.name}</p>
            <p className="text-sm font-semibold text-gray-200">
              AUC: {method.AUC.toFixed(3)}
            </p>
            <p className="text-xs text-gray-400">F1: {method.F1.toFixed(3)}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

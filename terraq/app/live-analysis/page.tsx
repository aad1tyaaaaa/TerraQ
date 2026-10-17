'use client'

// Standalone route for the Live Analysis tool.
//
// This used to carry its own copy of the map + controls markup, which then
// drifted from the version rendered inside the dashboard. It now renders the
// single shared component so both entry points stay identical.
//
// The component talks to the Python engine (product/server.py); point it
// somewhere else with NEXT_PUBLIC_ENGINE_URL (default http://localhost:8765).

import { TerraQLiveAnalysis } from '@/components/terraq-live-analysis'

export default function LiveAnalysisPage() {
  return (
    <main className="min-h-screen px-6 py-10">
      <TerraQLiveAnalysis />
    </main>
  )
}

'use client'

import { useState } from 'react'
import { Search } from 'lucide-react'

export function TerraQNavbar() {
  const [searchQuery, setSearchQuery] = useState('')

  return (
    <div className="h-24 bg-[#27272A] border-b border-border flex items-center justify-between px-8 shrink-0 shadow-lg">
      <div className="flex-1" /> {/* Spacer */}

      {/* Search Bar */}
      <div className="flex-1 max-w-2xl mx-auto">
        <div className="flex items-center gap-3 bg-white/5 backdrop-blur-sm px-6 py-4 rounded-2xl border border-white/15 shadow-xl">
          <Search className="w-6 h-6 text-primary" />
          <input
            type="text"
            placeholder="Search detections, minerals, regions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent text-lg text-white placeholder:text-muted-foreground outline-none align-middle flex-1"
          />
        </div>
      </div>

      <div className="flex-1" />
    </div>
  )
}


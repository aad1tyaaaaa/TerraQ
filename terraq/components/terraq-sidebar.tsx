'use client'

import { useRouter } from 'next/navigation'
import {
  BarChart3,
  Map,
  Zap,
  HelpCircle,
  Database,
  Satellite,
  Globe,
  LogOut,
} from 'lucide-react'

type NavItem = 'overview' | 'maps' | 'methods' | 'how' | 'data' | 'live'

interface SidebarProps {
  activeTab: NavItem
  onTabChange: (tab: NavItem) => void
}

export function TerraQSidebar({ activeTab, onTabChange }: SidebarProps) {
  const router = useRouter()
  const navItems = [
    { id: 'overview' as NavItem, label: 'Dashboard', icon: BarChart3 },
    { id: 'live' as NavItem, label: 'Live Analysis', icon: Satellite },
    { id: 'maps' as NavItem, label: 'Satellite Maps', icon: Map },
    { id: 'methods' as NavItem, label: 'Method Comparison', icon: Zap },
    { id: 'how' as NavItem, label: 'How It Works', icon: HelpCircle },
    { id: 'data' as NavItem, label: 'Data & Methodology', icon: Database },
  ]

  return (
    <div className="w-72 bg-[#27272A] border-r border-border flex flex-col h-screen shrink-0">
      {/* Logo Section */}
      <div className="flex-1 flex items-center justify-center p-6 border-b border-border">
        <div className="flex flex-col items-center gap-2">
          <img
            src="/terraq-mark.png"
            alt="TerraQ"
            className="h-20 w-20 rounded-full object-cover ring-1 ring-primary/30"
          />
          <div className="text-center">
            <p className="text-base font-semibold tracking-wide text-foreground">TerraQ</p>
            <p className="text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
              Earth Exploration
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Items */}
      <nav className="p-4 space-y-2 flex-grow">
        {navItems.map((item) => {
          const IconComponent = item.icon
          const isActive = activeTab === item.id
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                isActive
                  ? 'bg-primary text-background'
                  : 'text-muted-foreground hover:bg-card hover:text-foreground'
              }`}
            >
              <IconComponent className={`w-5 h-5 ${isActive ? 'text-background' : 'text-primary'}`} />
              <span className="text-sm font-semibold">{item.label}</span>
            </button>
          )
        })}

        {/* Explorer console — a separate route, not one of the 6 dashboard tabs. */}
        <button
          onClick={() => router.push('/explorer')}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-muted-foreground hover:bg-card hover:text-foreground transition-all duration-200"
        >
          <Globe className="w-5 h-5 text-primary" />
          <span className="text-sm font-semibold">Explorer</span>
          <span className="ml-auto text-[9px] uppercase tracking-wider text-primary/70">new</span>
        </button>
      </nav>

      {/* Logout Button */}
      <div className="p-4 border-t border-border">
        <button
          onClick={() => router.push('/')}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-all duration-200"
        >
          <LogOut className="w-5 h-5" />
          <span className="text-sm font-semibold">Log Out</span>
        </button>
      </div>
    </div>
  )
}


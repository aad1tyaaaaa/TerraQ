import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import './globals.css'
import { ThemeProvider } from '@/components/theme-provider'
import { GlobalMagicEffect } from '@/components/magic-global-effect'

const _geist = Geist({ subsets: ["latin"] });
const _geistMono = Geist_Mono({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: 'TerraQ — Quantum Intelligence for Earth Exploration',
  description: 'Quantum intelligence for Earth exploration — satellite mineral prospecting for lithium and vanadium',
  generator: 'v0.app',
  icons: {
    icon: '/terraq-icon.png',
    apple: '/terraq-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
<html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <ThemeProvider 
          attribute="class" 
          defaultTheme="dark" 
          enableSystem={false}
          disableTransitionOnChange
        >
          <GlobalMagicEffect />
          {children}
          {process.env.NODE_ENV === 'production' && <Analytics />}
        </ThemeProvider>
      </body>
    </html>
  )
}

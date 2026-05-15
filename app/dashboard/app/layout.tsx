import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import NavLinks from '@/components/NavLinks'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = { title: 'VoiceAgent — Dashboard' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.className}>
      <body className="flex min-h-screen bg-slate-50 text-slate-900 antialiased">
        {/* Sidebar */}
        <aside className="w-56 shrink-0 bg-slate-950 flex flex-col border-r border-slate-800">
          {/* Brand */}
          <div className="px-5 pt-6 pb-5 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-900/40">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
              </div>
              <div>
                <p className="text-white text-sm font-bold tracking-tight leading-none">VoiceAgent</p>
                <p className="text-slate-500 text-[10px] mt-0.5">Outbound Platform</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <NavLinks />

          {/* Footer status */}
          <div className="px-5 py-4 border-t border-slate-800">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-60"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
              </span>
              <span className="text-[11px] text-slate-500">All systems operational</span>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 min-h-screen overflow-auto bg-slate-50">
          {children}
        </main>
      </body>
    </html>
  )
}

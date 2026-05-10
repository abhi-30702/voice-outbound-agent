import './globals.css'
import Link from 'next/link'
import type { Metadata } from 'next'

export const metadata: Metadata = { title: 'Voice Agent Dashboard' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen bg-gray-50">
        <nav className="w-48 shrink-0 bg-gray-900 text-white flex flex-col p-4 gap-3">
          <span className="text-base font-bold mb-2">Dashboard</span>
          <Link href="/" className="text-sm hover:text-gray-300">Live Monitor</Link>
          <Link href="/campaigns" className="text-sm hover:text-gray-300">Campaigns</Link>
          <Link href="/kpi" className="text-sm hover:text-gray-300">KPI</Link>
        </nav>
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </body>
    </html>
  )
}

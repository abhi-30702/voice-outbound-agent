'use client'

import { useRouter } from 'next/navigation'

const RANGES = [
  { label: 'Today', value: 'today' },
  { label: '7 days', value: '7d' },
  { label: '30 days', value: '30d' },
]

export default function RangeSelector({ current }: { current: string }) {
  const router = useRouter()
  return (
    <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-xl p-1 shadow-sm">
      {RANGES.map(r => (
        <button
          key={r.value}
          onClick={() => router.push(`/kpi?range=${r.value}`)}
          className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all duration-150 ${
            current === r.value
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  )
}
